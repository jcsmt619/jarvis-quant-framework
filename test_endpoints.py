#!/usr/bin/env python3
"""Test different Alpaca API endpoints"""
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "").strip()

headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# Test different endpoints
endpoints = [
    "https://paper-api.alpaca.markets/v2/account",
    "https://api.alpaca.markets/v2/account",
    "https://alpaca.markets/v2/account",
]

for url in endpoints:
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"\n{url}")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200 and "account" in response.text.lower():
            print(f"  ✓ WORKING!")
            print(f"  Response keys: {list(response.json().keys())[:5]}")
        elif response.status_code == 200:
            print(f"  Response: {response.text[:100]}")
        else:
            print(f"  Response: {response.text[:100]}")
    except Exception as e:
        print(f"\n{url}")
        print(f"  Error: {e}")

# Also test bars endpoint
print("\n\n=== Testing BARS Endpoint ===")
base_urls = [
    "https://paper-api.alpaca.markets",
    "https://api.alpaca.markets",
]

for base in base_urls:
    url = f"{base}/v2/stocks/SPY/bars"
    params = {
        "timeframe": "1Day",
        "limit": 5,
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"\n{url}")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if "bars" in data:
                print(f"  ✓ WORKING! Got {len(data['bars'])} bars")
            else:
                print(f"  Response keys: {list(data.keys())}")
        else:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"\n{url}")
        print(f"  Error: {e}")
