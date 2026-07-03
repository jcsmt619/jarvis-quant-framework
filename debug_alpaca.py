#!/usr/bin/env python3
"""Debug Alpaca API response"""
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "").strip()
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://alpaca.markets").strip()

print(f"API Key loaded: {bool(ALPACA_API_KEY)}")
print(f"API Key first 10 chars: {ALPACA_API_KEY[:10]}")
print(f"API Secret loaded: {bool(ALPACA_SECRET_KEY)}")
print(f"Base URL: {ALPACA_BASE_URL}")

# Try a simple account status call
url = f"{ALPACA_BASE_URL}/v2/account"
headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

print(f"\nTesting Alpaca API with account endpoint...")
print(f"URL: {url}")

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Text: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
