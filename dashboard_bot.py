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

# Credentials from environment or manual input
api_key = os.getenv("aMIKAmfm")
client_code = os.getenv("S1339383")
password = os.getenv("0713")
totp_secret = os.getenv("BCMFG5RQGQXOYCTY7ZTS6GTEBI")

# Sidebar for manual input if not in env
st.sidebar.header("Login Credentials")
api_key = st.sidebar.text_input("API Key", value=api_key or "", type="password")
client_code = st.sidebar.text_input("Client Code", value=client_code or "")
password = st.sidebar.text_input("PIN", value=password or "", type="password")
totp_secret = st.sidebar.text_input("TOTP Secret", value=totp_secret or "", type="password")

if st.sidebar.button("Login to Angel One"):
    if not all([api_key, client_code, password, totp_secret]):
        st.sidebar.error("All fields are required")
    else:
        try:
            obj = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_secret).now()
            data = obj.generateSession(client_code, password, totp)
            if data['status']:
                st.session_state.obj = obj
                st.session_state.logged_in = True
                st.sidebar.success("Logged In Successfully! 🎉")
            else:
                st.sidebar.error(f"Login Failed: {data.get('message', 'Unknown error')}")
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.stop()

obj = st.session_state.obj

# Rest of the code (chart, data fetch) same as before
st.sidebar.header("Chart Settings")
index_choice = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
timeframe = st.sidebar.selectbox("Time Frame", ["1minute", "5minute", "15minute", "30minute", "60minute"])

tokens = {"NIFTY": "26000", "BANKNIFTY": "26009"}
token = tokens[index_choice]

def fetch_candles(token, tf):
    from_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d 09:00")
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
            st.warning("No candle data - market closed or weekend")
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
    st.info("No data available right now (weekend or pre-market). Monday 9:15 AM से live data आएगा।")
else:
    # Indicators and chart
    df['EMA9'] = df['close'].ewm(span=9).mean()
    df['EMA21'] = df['close'].ewm(span=21).mean()
    df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candles"))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], line=dict(color='orange'), name="EMA9"))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='blue'), name="EMA21"))
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='purple'), name="VWAP"))
    fig.update_layout(title=f"{index_choice} - {timeframe.upper()} Chart", height=600, xaxis_rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)

    try:
        ltp = obj.ltpData("NSE", index_choice, token)['data']['ltp']
        st.metric(f"Current {index_choice} Price", ltp)
    except:
        st.metric(f"Current {index_choice} Price", "N/A (market closed)")

st.success("Bot connected! Waiting for market open (Monday 9:15 AM) for live data & trades.")
