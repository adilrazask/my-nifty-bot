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

# Get credentials from environment (Render safe)
api_key = os.getenv("aMIKAmfm")
client_code = os.getenv("aMIKAmfm")
password = os.getenv("0713")
totp_secret = os.getenv("BCMFG5RQGQXOYCTY7ZTS6GTEBI")
st.sidebar.write(f"API Key loaded: { 'Yes' if api_key else 'No' }")
st.sidebar.write(f"Client Code: {client_code}")
st.sidebar.write(f"TOTP Secret loaded: { 'Yes' if totp_secret else 'No' }")
st.sidebar.header("Bot Status")

if not all([api_key, client_code, password, totp_secret]):
    st.sidebar.error("Credentials not set in Render Environment Variables")
    st.stop()

# Auto login
if 'logged_in' not in st.session_state:
    try:
        obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = obj.generateSession(client_code, password, totp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.logged_in = True
            st.sidebar.success("Auto Logged In Successfully! 🎉")
        else:
            st.sidebar.error(f"Login Failed: {data.get('message', 'Unknown')}")
            st.stop()
    except Exception as e:
        st.sidebar.error(f"Login Error: {str(e)}")
        st.stop()

obj = st.session_state.obj

st.sidebar.header("Chart Settings")
index_choice = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
timeframe = st.sidebar.selectbox("Time Frame", ["1minute", "5minute", "15minute", "30minute", "60minute"])

# Token
tokens = {
    "NIFTY": "26000",
    "BANKNIFTY": "26009"
}
token = tokens[index_choice]

# Fetch candles
def fetch_candles(token, tf):
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 09:00")
    to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    param = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": tf.upper(),
        "fromdate": from_date,
        "todate": to_date
    }
    try:
        response = obj.getCandleData(param)
        data = response.get('data', [])
        if not data:
            st.warning("No candle data - market may be closed or slow")
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df.astype(float)
    except Exception as e:
        st.error(f"Data error: {str(e)}")
        return pd.DataFrame()

df = fetch_candles(token, timeframe)

if df.empty:
    st.error("No data fetched - market closed or API issue")
    st.info("Check if market is open or credentials")
    st.stop()

# Indicators
df['EMA9'] = df['close'].ewm(span=9).mean()
df['EMA21'] = df['close'].ewm(span=21).mean()
df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()

# Chart
fig = go.Figure()
fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candles"))
fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], line=dict(color='orange'), name="EMA9"))
fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='blue'), name="EMA21"))
fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='purple'), name="VWAP"))

fig.update_layout(title=f"{index_choice} - {timeframe.upper()} Live Chart", height=600, xaxis_rangeslider_visible=True)
st.plotly_chart(fig, use_container_width=True)

# Current price
try:
    ltp = obj.ltpData("NSE", index_choice, token)['data']['ltp']
    st.metric(f"Current {index_choice} Price", ltp)
except:
    st.metric(f"Current {index_choice} Price", "Error")

st.success("Dashboard Live — Data Loaded!")
