import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import os

st.set_page_config(page_title="My Pro Trading Bot", layout="wide")
st.title("🚀 My Professional Nifty Options Bot - Angel One Style")

st.markdown("**Live Charts | Multiple Indices | Custom Time Frames | Paper Trading | Auto-Learning**")

# Sidebar
st.sidebar.header("https://apiconnect.angelone.in")
api_key = st.sidebar.text_input("aMIKAmfm", type="password")
client_code = st.sidebar.text_input("S1339383")
password = st.sidebar.text_input("0713", type="password")
totp_secret = st.sidebar.text_input("BCMFG5RQGQXOYCTY7ZTS6GTEBI", type="password")

if st.sidebar.button("Login"):
    try:
        obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = obj.generateSession(client_code, password, totp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.logged_in = True
            st.sidebar.success("Logged In Successfully!")
        else:
            st.sidebar.error("Login Failed")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.header("Chart Settings")
index_choice = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY", "SENSEX"])
timeframe = st.sidebar.selectbox("Time Frame", ["1minute", "5minute", "15minute", "30minute", "60minute", "day"])

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.stop()

obj = st.session_state.obj

# Token mapping
tokens = {
    "NIFTY": "26000",
    "BANKNIFTY": "26009",
    "SENSEX": "1"  # Sensex token (BSE)
}

token = tokens[index_choice]

# Fetch candle data
def fetch_candles(token, tf):
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 09:00")
    to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    param = {
        "exchange": "NSE" if index_choice != "SENSEX" else "BSE",
        "symboltoken": token,
        "interval": tf.upper(),
        "fromdate": from_date,
        "todate": to_date
    }
    try:
        data = obj.getCandleData(param)['data']
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    except:
        return pd.DataFrame()

df = fetch_candles(token, timeframe)

if df.empty:
    st.error("No data fetched - market closed or error")
    st.stop()

# Indicators
df['EMA9'] = df['close'].ewm(span=9).mean()
df['EMA21'] = df['close'].ewm(span=21).mean()
df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()

# Chart
fig = go.Figure()

fig.add_trace(go.Candlestick(x=df.index,
                             open=df['open'],
                             high=df['high'],
                             low=df['low'],
                             close=df['close'],
                             name="Candles"))

fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], line=dict(color='orange', width=1), name="EMA9"))
fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='blue', width=1), name="EMA21"))
fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='purple', width=1), name="VWAP"))

fig.update_layout(title=f"{index_choice} - {timeframe.upper()} Chart",
                  xaxis_title="Time",
                  yaxis_title="Price",
                  xaxis_rangeslider_visible=True,
                  height=600)

st.plotly_chart(fig, use_container_width=True)

# Current price
try:
    ltp = obj.ltpData("NSE" if index_choice != "SENSEX" else "BSE", index_choice, token)['data']['ltp']
    st.metric(f"Current {index_choice} Price", ltp)
except:
    st.metric(f"Current {index_choice} Price", "N/A")

# Trade history
if os.path.exists("trade_log.csv"):
    trade_df = pd.read_csv("trade_log.csv")
    st.subheader("Trade History")
    st.dataframe(trade_df)
else:
    st.info("No trades yet - trade_log.csv will appear after first trade")

st.caption("Professional Dashboard like Angel One | Multiple Indices & Time Frames | Paper Mode")