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

print("Login Successful! 🎉 Starting Rule Bot v2 (20 Strong Rules)...\n")

# Get 1-minute historical data for Nifty
def get_data():
    historicParam = {
        "exchange": "NSE",
        "symboltoken": "26000",
        "interval": "ONE_MINUTE",
        "fromdate": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d 09:00"),
        "todate": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    raw = obj.getCandleData(historicParam)['data']
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df.astype(float)

# Calculate indicators manually
def add_indicators(df):
    if len(df) < 50:
        return df
    
    # EMA
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    
    # RSI (14)
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    
    # Supertrend (10,3)
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = df['high'].rolling(10).max() - df['low'].rolling(10).min()  # Simplified ATR
    df['upper'] = hl2 + (3 * df['atr'])
    df['lower'] = hl2 - (3 * df['atr'])
    df['supertrend'] = np.nan
    df['supertrend_dir'] = 0  # 1 = up, -1 = down
    for i in range(1, len(df)):
        if df['close'].iloc[i-1] > df['upper'].iloc[i-1]:
            df.loc[df.index[i], 'supertrend'] = df['lower'].iloc[i]
            df.loc[df.index[i], 'supertrend_dir'] = 1
        elif df['close'].iloc[i-1] < df['lower'].iloc[i-1]:
            df.loc[df.index[i], 'supertrend'] = df['upper'].iloc[i]
            df.loc[df.index[i], 'supertrend_dir'] = -1
        else:
            df.loc[df.index[i], 'supertrend'] = df['supertrend'].iloc[i-1]
            df.loc[df.index[i], 'supertrend_dir'] = df['supertrend_dir'].iloc[i-1]
    
    # VWAP (session)
    df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
    
    # Previous day high/low (approx)
    prev_day = df[df.index.date == (datetime.now().date() - timedelta(days=1))]
    df['pdh'] = prev_day['high'].max() if not prev_day.empty else np.nan
    df['pdl'] = prev_day['low'].min() if not prev_day.empty else np.nan
    
    return df

# 20 Strong Rules (True/False)
def bullish_rules(df):
    c = df['close'].iloc[-1]
    count = 0
    if c > df['vwap'].iloc[-1]: count += 1                     # 1. Above VWAP
    if df['rsi'].iloc[-1] > 50: count += 1                      # 2. RSI > 50
    if df['rsi'].iloc[-1] < 30: count += 1                      # 3. RSI oversold bounce potential
    if df['macd'].iloc[-1] > df['macd_signal'].iloc[-1]: count += 1  # 4. MACD bullish cross
    if c > df['supertrend'].iloc[-1]: count += 1               # 5. Above Supertrend
    if df['supertrend_dir'].iloc[-1] == 1: count += 1          # 6. Supertrend up
    if c > df['ema9'].iloc[-1] > df['ema21'].iloc[-1]: count += 1  # 7. EMA alignment
    if c > df['pdh'].iloc[-1]: count += 1                       # 8. Above previous day high
    if df['low'].iloc[-1] <= df['vwap'].iloc[-1] and c > df['vwap'].iloc[-1]: count += 1  # 9. VWAP bounce
    if df['macd'].iloc[-1] > 0: count += 1                      # 10. MACD above zero
    return count

def bearish_rules(df):
    c = df['close'].iloc[-1]
    count = 0
    if c < df['vwap'].iloc[-1]: count += 1
    if df['rsi'].iloc[-1] < 50: count += 1
    if df['rsi'].iloc[-1] > 70: count += 1
    if df['macd'].iloc[-1] < df['macd_signal'].iloc[-1]: count += 1
    if c < df['supertrend'].iloc[-1]: count += 1
    if df['supertrend_dir'].iloc[-1] == -1: count += 1
    if c < df['ema21'].iloc[-1] < df['ema9'].iloc[-1]: count += 1
    if c < df['pdl'].iloc[-1]: count += 1
    if df['high'].iloc[-1] >= df['vwap'].iloc[-1] and c < df['vwap'].iloc[-1]: count += 1
    if df['macd'].iloc[-1] < 0: count += 1
    return count

# Main loop
trades_today = 0
max_trades = 3
last_signal = ""

try:
    while True:
        df = get_data()
        if not df.empty:
            df = add_indicators(df)
            if len(df) > 50:
                bull_count = bullish_rules(df)
                bear_count = bearish_rules(df)
                current_price = df['close'].iloc[-1]
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Nifty: {current_price:.1f} | Bull: {bull_count}/10 | Bear: {bear_count}/10")
                
                if trades_today < max_trades:
                    if bull_count >= 6 and last_signal != "CALL":
                        print(">>> STRONG BUY CALL SIGNAL!!! <<<")
                        last_signal = "CALL"
                        trades_today += 1  # Placeholder for real order
                    elif bear_count >= 6 and last_signal != "PUT":
                        print(">>> STRONG BUY PUT SIGNAL!!! <<<")
                        last_signal = "PUT"
                        trades_today += 1
        
        time.sleep(30)  # Check every 30 seconds

except KeyboardInterrupt:
    print("\nBot stopped.")