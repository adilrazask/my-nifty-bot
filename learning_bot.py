from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import feedparser
import os

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

print("Login Successful! 🎉 Learning Bot Started - Will Log Trades & Improve Itself\n")

# Variables
trades_today = 0
max_trades_per_day = 3
first_trade_lost = False
in_trade = False
entry_premium = 0
option_symbol = ""
option_token = ""
trade_direction = ""
current_bull_count = 0
current_bear_count = 0
news_sentiment = 0.0
analyzer = SentimentIntensityAnalyzer()
last_news_update = 0
trade_log_file = "trade_log.csv"

# Trade log
if os.path.exists(trade_log_file):
    trade_df = pd.read_csv(trade_log_file)
    print(f"Loaded past {len(trade_df)} trades for learning")
else:
    trade_df = pd.DataFrame(columns=["date", "direction", "symbol", "entry_premium", "exit_premium", "pnl_pct", "bull_count", "bear_count", "news_sentiment"])
    trade_df.to_csv(trade_log_file, index=False)
    print("Created new trade_log.csv file")

# Simple learning threshold
def update_signal_threshold():
    if len(trade_df) < 10:
        return 6
    recent = trade_df.tail(20)
    win_rate = len(recent[recent['pnl_pct'] > 0]) / len(recent)
    if win_rate > 0.6:
        print(f"Good performance - Threshold reduced to 5")
        return 5
    elif win_rate < 0.4:
        print(f"Need caution - Threshold increased to 7")
        return 7
    return 6

signal_threshold = update_signal_threshold()

# Get Nifty price
def get_nifty_price():
    try:
        return obj.ltpData("NSE", "NIFTY", "26000")['data']['ltp']
    except:
        return 0

# Get option premium
def get_option_premium(symbol, token):
    try:
        return obj.ltpData("NFO", symbol, token)['data']['ltp']
    except:
        return entry_premium  # fallback

# Get data and indicators
def get_data_and_indicators():
    historicParam = {
        "exchange": "NSE",
        "symboltoken": "26000",
        "interval": "ONE_MINUTE",
        "fromdate": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d 09:00"),
        "todate": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    raw = obj.getCandleData(historicParam).get('data', [])
    if not raw:
        return None
    df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.astype(float)
    if len(df) < 50:
        return None
    
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

# Rule counts
def get_rule_counts(df):
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

# Select option
def select_best_option(trade_type, spot):
    # Simple placeholder - real chain fetch in final version
    return f"NIFTY25DEC{round(spot/50)*50}{trade_type}", "12345"

# Paper entry
def paper_entry(symbol, token, direction, bull, bear):
    global in_trade, entry_premium, option_symbol, option_token, trade_direction, current_bull_count, current_bear_count, trades_today
    premium = 100  # placeholder
    print(f"\n=== PAPER BUY {direction} ===\nSymbol: {symbol}\nEntry Premium: {premium}\n")
    in_trade = True
    entry_premium = premium
    option_symbol = symbol
    option_token = token
    trade_direction = direction
    current_bull_count = bull
    current_bear_count = bear
    trades_today += 1

# Exit and log
def check_exit_and_log():
    global in_trade, first_trade_lost, signal_threshold
    if not in_trade:
        return
    current_premium = 120 if trade_direction == "CALL" else 80  # placeholder for testing
    if trade_direction == "CALL":
        pnl_pct = (current_premium - entry_premium) / entry_premium * 100
    else:
        pnl_pct = (entry_premium - current_premium) / entry_premium * 100
    
    exit_reason = "TEST_EXIT"  # placeholder
    if True:  # for testing
        print(f">>> EXIT: {exit_reason} | PnL: {pnl_pct:.1f}%")
        new_trade = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "direction": trade_direction,
            "symbol": option_symbol,
            "entry_premium": entry_premium,
            "exit_premium": current_premium,
            "pnl_pct": pnl_pct,
            "bull_count": current_bull_count,
            "bear_count": current_bear_count,
            "news_sentiment": news_sentiment
        }
        global trade_df
        trade_df = pd.concat([trade_df, pd.DataFrame([new_trade])], ignore_index=True)
        trade_df.to_csv(trade_log_file, index=False)
        print(f"Trade logged! Total: {len(trade_df)}")
        signal_threshold = update_signal_threshold()
        in_trade = False
        if trades_today == 1 and pnl_pct < 0:
            first_trade_lost = True

# Main loop
try:
    while True:
        now = datetime.now()
        df = get_data_and_indicators()
        if df is not None:
            spot = get_nifty_price()
            bull, bear = get_rule_counts(df)
            print(f"[{now.strftime('%H:%M:%S')}] Nifty: {spot:.1f} | Bull: {bull} | Bear: {bear} | Threshold: {signal_threshold}")
            
            check_exit_and_log()
            
            if trades_today < max_trades_per_day and not in_trade and not first_trade_lost:
                if bull >= signal_threshold:
                    sym, tok = select_best_option("CE", spot)
                    paper_entry(sym, tok, "CALL", bull, bear)
                    check_exit_and_log()  # immediate test exit for learning demo
        
        time.sleep(30)
except KeyboardInterrupt:
    print("\nBot stopped.")