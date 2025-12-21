from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import feedparser

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

print("Login Successful! 🎉 Complete Bot with Strict Risk Management Started\n")

# Risk Management Variables
max_trades_per_day = 3
trades_today = 0
first_trade_lost = False   # <--- YOUR RULE: If True → no more trades today
in_trade = False
entry_premium = 0
option_symbol = ""
option_token = ""
trade_direction = ""  # "CALL" or "PUT"
news_sentiment = 0.0
analyzer = SentimentIntensityAnalyzer()
last_news_update = 0

# News sentiment
def fetch_news_sentiment():
    global news_sentiment, last_news_update
    feeds = [
        "https://www.moneycontrol.com/rss/latestnews.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/2146842.cms",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/businessNews"
    ]
    headlines = []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed)
            for entry in parsed.entries[:5]:
                headlines.append(entry.title)
        except:
            pass
    if headlines:
        scores = [analyzer.polarity_scores(h)['compound'] for h in headlines]
        news_sentiment = sum(scores) / len(scores)
        print(f"News Sentiment: {news_sentiment:.2f}")
    last_news_update = time.time()

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
        return 0

# Data + indicators
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

# Rule counts with news boost
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
    
    if news_sentiment > 0.2: bull += 2
    if news_sentiment < -0.2: bear += 2
    
    return bull, bear

# Select option
def select_best_option(trade_type, spot):
    today = datetime.now()
    thursday = today + timedelta(days=(3 - today.weekday() + 7) % 7)
    if today.weekday() > 3:
        thursday += timedelta(weeks=1)
    expiry = thursday.strftime("%d%b%Y").upper()
    try:
        chain_data = obj.getOptionChain("NFO", f"NIFTY{expiry}", "999901")
        chain = pd.DataFrame(chain_data['data'])
        atm = round(spot / 50) * 50
        strikes = [atm, atm-50, atm-100] if trade_type == "CE" else [atm, atm+50, atm+100]
        filtered = chain[(chain['strikeprice'].isin(strikes)) & (chain['tradingsymbol'].str.contains(trade_type))]
        if filtered.empty:
            return None, None
        best = filtered.sort_values(by=['openinterest', 'volume'], ascending=False).iloc[0]
        return best['tradingsymbol'], best['token']
    except:
        return None, None

# Paper trade entry
def paper_entry(symbol, token, direction):
    global in_trade, entry_premium, option_symbol, option_token, trade_direction, trades_today
    premium = get_option_premium(symbol, token)
    if premium == 0:
        return
    print(f"\n=== PAPER BUY {direction} ===")
    print(f"Symbol: {symbol}")
    print(f"Entry Premium: {premium}")
    print(f"Quantity: 25")
    print("=== SIMULATED TRADE ===\n")
    in_trade = True
    entry_premium = premium
    option_symbol = symbol
    option_token = token
    trade_direction = direction
    trades_today += 1

# Check exit and update first_trade_lost
def check_exit():
    global in_trade, first_trade_lost, trades_today
    if not in_trade:
        return
    current_premium = get_option_premium(option_symbol, option_token)
    if current_premium == 0:
        return
    pnl_pct = (current_premium - entry_premium) / entry_premium * 100 if trade_direction == "CALL" else (entry_premium - current_premium) / entry_premium * 100
    
    if pnl_pct >= 50:
        print(f">>> 50% PROFIT TARGET HIT! Exit at {current_premium} (+{pnl_pct:.1f}%)")
        in_trade = False
        if trades_today == 1 and pnl_pct < 0:
            first_trade_lost = True
    elif pnl_pct <= -30:
        print(f">>> STOP LOSS HIT! Exit at {current_premium} ({pnl_pct:.1f}%)")
        in_trade = False
        if trades_today == 1:
            first_trade_lost = True
    elif datetime.now().hour >= 15 and datetime.now().minute >= 10:
        print(f">>> EOD EXIT at {current_premium} (PnL: {pnl_pct:.1f}%)")
        in_trade = False
        if trades_today == 1 and pnl_pct < 0:
            first_trade_lost = True

# Main loop
try:
    while True:
        now = datetime.now()
        
        # News update
        if time.time() - last_news_update > 3600:
            fetch_news_sentiment()
        
        # Market hours
        if now.weekday() >= 5 or now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour >= 15:
            print(f"[{now.strftime('%H:%M:%S')}] Market closed - waiting...")
            time.sleep(60)
            continue
        
        # Reset daily at 9:00 AM
        if now.hour == 9 and now.minute < 5:
            trades_today = 0
            first_trade_lost = False
            in_trade = False
        
        df = get_data_and_indicators()
        if df is not None:
            spot = get_nifty_price()
            bull, bear = get_rule_counts(df)
            status = f"Trades: {trades_today}/{max_trades_per_day}"
            if first_trade_lost:
                status += " | FIRST TRADE LOST → NO MORE TRADES TODAY"
            print(f"[{now.strftime('%H:%M:%S')}] Nifty: {spot:.1f} | Bull: {bull} | Bear: {bear} | {status} | News: {news_sentiment:.2f}")
            
            check_exit()  # Check if current trade hit target/SL
            
            # Entry condition
            if (trades_today < max_trades_per_day and not in_trade and not first_trade_lost and abs(news_sentiment) < 0.6):
                if bull >= 6:
                    sym, tok = select_best_option("CE", spot)
                    if sym:
                        paper_entry(sym, tok, "CALL")
                elif bear >= 6:
                    sym, tok = select_best_option("PE", spot)
                    if sym:
                        paper_entry(sym, tok, "PUT")
        
        time.sleep(30)

except KeyboardInterrupt:
    print("\nBot stopped safely.")