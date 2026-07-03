#!/usr/bin/env python3
"""Test Alpaca bars endpoint with correct parameters"""
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import json

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "").strip()

headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# Date range
start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
end = datetime.now().strftime("%Y-%m-%d")

# Test data endpoint
url = "https://data.alpaca.markets/v2/stocks/SPY/bars"
params = {
    "timeframe": "1Day",
    "start": start,
    "end": end,
    "limit": 100,
}

print(f"URL: {url}")
print(f"Params: {json.dumps(params, indent=2)}")
print(f"Headers: APCA-API-KEY-ID={ALPACA_API_KEY[:10]}...")

try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"\nStatus: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response keys: {list(data.keys())}")
        if "bars" in data:
            print(f"SUCCESS! Got {len(data['bars'])} bars")
            print(f"First bar: {data['bars'][0]}")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
