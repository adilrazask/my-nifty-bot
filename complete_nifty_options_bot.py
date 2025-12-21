from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import feedparser

# === YOUR CREDENTIALS (REPLACE THESE) ===
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

print("Login Successful! 🎉 Complete Nifty Options Bot Started (Paper Trading Mode)\n")

# Global variables
trades_today = 0
max_trades_per_day = 3
in_trade = False
trade_type = ""  # "CE" or "PE"
option_symbol = ""
option_token = ""
news_sentiment = 0.0
analyzer = SentimentIntensityAnalyzer()
last_news_update = 0

# Fetch news sentiment (Indian + International)
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
        print(f"News Sentiment Updated: {news_sentiment:.2f} (+ve = bullish bias, -ve = bearish bias)")
    last_news_update = time.time()

# Get Nifty spot price
def get_nifty_price():
    try:
        data = obj.ltpData("NSE", "NIFTY", "26000")
        return data['data']['ltp']
    except:
        return 0

# Get historical 1-min data and add indicators
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
    
    # Indicators
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

# Count bullish and bearish rules
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
    
    # News boost
    if news_sentiment > 0.2: bull += 2
    if news_sentiment < -0.2: bear += 2
    
    return bull, bear

# Get options chain and select best option
def select_best_option(trade_type, spot_price):
    today = datetime.now()
    thursday = today + timedelta(days=(3 - today.weekday() + 7) % 7)
    if today.weekday() > 3:
        thursday += timedelta(weeks=1)
    expiry = thursday.strftime("%d%b%Y").upper()
    
    try:
        chain_data = obj.getOptionChain("NFO", f"NIFTY{expiry}", "999901")
        chain = pd.DataFrame(chain_data['data'])
        atm = round(spot_price / 50) * 50
        strikes = [atm, atm-50, atm-100] if trade_type == "CE" else [atm, atm+50, atm+100]
        filtered = chain[(chain['strikeprice'].isin(strikes)) & (chain['tradingsymbol'].str.contains(trade_type))]
        if filtered.empty:
            return None, None
        best = filtered.sort_values(by=['openinterest', 'volume'], ascending=False).iloc[0]
        return best['tradingsymbol'], best['token']
    except:
        return None, None

# Paper trade order
def paper_trade(symbol, token, direction):
    global trades_today, in_trade, trade_type
    try:
        premium = obj.ltpData("NFO", symbol, token)['data']['ltp']
    except:
        premium = 0
    print(f"\n=== PAPER TRADE EXECUTED ===")
    print(f"Direction: BUY {direction}")
    print(f"Symbol: {symbol}")
    print(f"Premium: ≈ {premium}")
    print(f"Quantity: 25 (1 lot)")
    print("=== SIMULATED - NO REAL MONEY ===\n")
    in_trade = True
    trade_type = direction
    trades_today += 1

# Main loop
try:
    while True:
        now = datetime.now()
        
        # Update news every hour
        if time.time() - last_news_update > 3600:
            fetch_news_sentiment()
        
        # Market hours check
        if now.weekday() >= 5 or now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour >= 15:
            print(f"[{now.strftime('%H:%M:%S')}] Market closed - monitoring news & data...")
            time.sleep(60)
            continue
        
        df = get_data_and_indicators()
        if df is not None:
            spot = get_nifty_price()
            bull_count, bear_count = get_rule_counts(df)
            print(f"[{now.strftime('%H:%M:%S')}] Nifty: {spot:.1f} | Bull: {bull_count}/10+ | Bear: {bear_count}/10+ | Trades: {trades_today}/{max_trades_per_day} | News: {news_sentiment:.2f}")
            
            if trades_today < max_trades_per_day and not in_trade and abs(news_sentiment) < 0.6:  # Block on extreme news
                if bull_count >= 6:
                    sym, tok = select_best_option("CE", spot)
                    if sym:
                        paper_trade(sym, tok, "CALL")
                elif bear_count >= 6:
                    sym, tok = select_best_option("PE", spot)
                    if sym:
                        paper_trade(sym, tok, "PUT")
        
        time.sleep(30)

except KeyboardInterrupt:
    print("\nBot stopped safely. Goodbye!")