from SmartApi import SmartConnect
import pyotp

# === PUT YOUR DETAILS HERE (REPLACE THE TEXT IN QUOTES) ===
api_key = "aMIKAmfm"              # From SmartAPI dashboard
client_code = "S1339383"      # Your Angel One user ID (like A12345)
password = "0713"                 # Your trading PIN (not login password)
totp_secret = "BCMFG5RQGQXOYCTY7ZTS6GTEBI"      # The long secret string from Google Authenticator QR

# Create the connection object
obj = SmartConnect(api_key=api_key)

# Generate the current TOTP code (changes every 30 seconds)
totp_code = pyotp.TOTP(totp_secret).now()
print("350069:", totp_code)   # Should match your Authenticator app

# Try to login
try:
    login_data = obj.generateSession(client_code, password, totp_code)
    print("Login Successful! 🎉")
    print("Your Name:", login_data['data']['name'])
    print("JWT Token received (session active)")

    # Test: Get live price of Nifty
    nifty_ltp = obj.ltpData("NSE", "NIFTY", "26000")  # 26000 is Nifty token
    print("Current Nifty Price:", nifty_ltp['data']['ltp'])

except Exception as e:
    print("Login Failed 😞")
    print("Error:", e)
