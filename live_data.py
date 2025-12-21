from SmartApi import SmartConnect
import pyotp
import time

# === YOUR DETAILS HERE ===
api_key = "aMIKAmfm"              # From SmartAPI dashboard
client_code = "S1339383"      # Your Angel One user ID (like A12345)
password = "0713"                 # Your trading PIN (not login password)
totp_secret = "BCMFG5RQGQXOYCTY7ZTS6GTEBI"      # The long secret string from Google Authenticator QR

# Create object and login
obj = SmartConnect(api_key=api_key)
totp_code = pyotp.TOTP(totp_secret).now()
login_data = obj.generateSession(client_code, password, totp_code)

if login_data['status'] == True:
    print("Login Successful! 🎉")
    print("Your Name:", login_data['data']['name'])
    print("Starting live Nifty price updates...\n")
else:
    print("Login Failed:", login_data['message'])
    exit()  # Stop if login fails

# Main loop: Get Nifty price every 10 seconds forever
try:
    while True:
        try:
            nifty_data = obj.ltpData("NSE", "NIFTY", "26000")
            price = nifty_data['data']['ltp']
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] Current Nifty Price: {price}")
        except Exception as e:
            print("Error fetching price:", e)
        
        time.sleep(10)  # Wait 10 seconds before next update

except KeyboardInterrupt:
    print("\nStopped by user. Goodbye!")