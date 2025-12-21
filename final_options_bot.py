from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# === YOUR CREDENTIALS ===
api_key = "aMIKAmfm"              # From SmartAPI dashboard
client_code = "S1339383"      # Your Angel One user ID (like A12345)
password = "0713"                 # Your trading PIN (not login password)
totp_secret = "BCMFG5RQGQXOYCTY7ZTS6GTEBI" 

# Login
obj = SmartConnect(api_key=api_key)
totp_code = pyotp.TOTP(totp_secret).now()
login_data = obj.generateSession(client_code, password, totp_code)

if not login_data['status']:
    print("Login Failed:", login_data['message'])
    exit()

print("Login Successful! 🎉 Final Automated Nifty Options Bot Started!\n")

# Global variables
trades_today = 0
max_trades_per_day = 3
in_trade = False
entry_price_option = 0
option_symbol = ""
option_token = ""
trade_type = ""  # "CE" or "PE"

# Get Nifty spot price
def get_nifty_price():
    data = obj.ltpData("NSE", "NIFTY", "26000")
    return data['data']['ltp']

# Get full options chain for current weekly expiry
def get_options_chain():
    # Find current weekly expiry (Thursday expiry for Nifty)
    today = datetime.now()
    thursday = today + timedelta(days=(3 - today.weekday() + 7) % 7)  # Next Thursday
    if today.weekday() > 3:  # After Thursday, next week
        thursday += timedelta(weeks=1)
    expiry = thursday.strftime("%d%b%Y").upper()  # e.g., 25DEC2025
    
    # Option chain request
    params = {
        "exchange": "NFO",
        "tradingsymbol": f"NIFTY{expiry}",
        "symboltoken": "999901"  # Dummy token for chain
    }
    chain = obj.optionChain(params)
    if 'data' not in chain or not chain['data']:
        print("No options chain data")
        return None
    return pd.DataFrame(chain['data'])

# Select best option (ATM or slightly OTM)
def select_option(chain_df, trade_type, spot_price):
    # Round to nearest 50 strike
    atm_strike = round(spot_price / 50) * 50
    
    # For Call: ATM or 50-100 OTM (slightly lower strike for better delta)
    # For Put: ATM or 50-100 OTM
    if trade_type == "CE":
        strikes = [atm_strike, atm_strike - 50, atm_strike - 100]
    else:
        strikes = [atm_strike, atm_strike + 50, atm_strike + 100]
    
    filtered = chain_df[(chain_df['strikeprice'].isin(strikes)) & (chain_df['tradingsymbol'].str.contains(trade_type))]
    if filtered.empty:
        return None, None
    
    # Pick highest OI + volume (most liquid)
    best = filtered.sort_values(by=['openinterest', 'volume'], ascending=False).iloc[0]
    return best['tradingsymbol'], best['symboltoken']

# Place SIMULATED order (paper trading - safe!)
def place_paper_order(symbol, token, trade_type, quantity=25):
    global in_trade, entry_price_option, option_symbol, option_token
    print(f"\n=== PAPER ORDER PLACED ===")
    print(f"Type: BUY {trade_type} (Call or Put)")
    print(f"Symbol: {symbol}")
    print(f"Quantity: {quantity} (1 lot = 25)")
    print(f"Order Type: MARKET (for speed)")
    print("=== THIS IS SIMULATED - NO REAL MONEY USED ===\n")
    
    in_trade = True
    entry_price_option = obj.ltpData("NFO", symbol, token)['data']['ltp']
    option_symbol = symbol
    option_token = token
    print(f"Entry Premium: ≈ {entry_price_option}")

# Get historical data and add indicators (same as before)
def get_data_and_indicators():
    historicParam = {
        "exchange": "NSE",
        "symboltoken": "26000",
        "interval": "ONE_MINUTE",
        "fromdate": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d 09:00"),
        "todate": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    raw = obj.getCandleData(historicParam)['data']
    if not raw:
        return None
    df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.astype(float)
    
    # Add indicators (same as v2)
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['rsi'] = 100 - (100 / (1 + rs))
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
    
    return df

# Bullish/Bearish rule counts (same 20 rules)
def get_signal_counts(df):
    c = df['close'].iloc[-1]
    bull = bear = 0
    if c > df['vwap'].iloc[-1]: bull += 1
    if df['rsi'].iloc[-1] > 50: bull += 1
    if df['rsi'].iloc[-1] < 30: bull += 1
    if df['macd'].iloc[-1] > df['macd_signal'].iloc[-1]: bull += 1
    if c > df['ema9'].iloc[-1] > df['ema21'].iloc[-1]: bull += 1
    
    if c < df['vwap'].iloc[-1]: bear += 1
    if df['rsi'].iloc[-1] < 50: bear += 1
    if df['rsi'].iloc[-1] > 70: bear += 1
    if df['macd'].iloc[-1] < df['macd_signal'].iloc[-1]: bear += 1
    if c < df['ema21'].iloc[-1] < df['ema9'].iloc[-1]: bear += 1
    
    return bull, bear

# Main loop
try:
    while True:
        now = datetime.now()
        # Only trade during market hours (9:15 AM - 3:15 PM)
        if now.weekday() >= 5 or now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour >= 15:
            print(f"[{now.strftime('%H:%M:%S')}] Market closed or outside hours - waiting...")
            time.sleep(60)
            continue
        
        df = get_data_and_indicators()
        if df is not None and len(df) > 50:
            spot_price = get_nifty_price()
            bull_count, bear_count = get_signal_counts(df)
            print(f"[{now.strftime('%H:%M:%S')}] Nifty: {spot_price:.1f} | Bull Rules: {bull_count}/10 | Bear Rules: {bear_count}/10 | Trades Today: {trades_today}")
            
            if trades_today < max_trades_per_day and not in_trade:
                chain = get_options_chain()
                if chain is not None:
                    if bull_count >= 6:
                        symbol, token = select_option(chain, "CE", spot_price)
                        if symbol:
                            place_paper_order(symbol, token, "CALL")
                            trade_type = "CE"
                            trades_today += 1
                    elif bear_count >= 6:
                        symbol, token = select_option(chain, "PE", spot_price)
                        if symbol:
                            place_paper_order(symbol, token, "PUT")
                            trade_type = "PE"
                            trades_today += 1
        
        time.sleep(30)

except KeyboardInterrupt:
    print("\nBot stopped by user. Safe exit!")