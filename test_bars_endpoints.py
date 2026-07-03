#!/usr/bin/env python3
"""Test different Alpaca bars endpoints"""
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

params = {
    "timeframe": "1Day",
    "limit": 5,
}

# Test different bars endpoint formats
endpoints = [
    "https://paper-api.alpaca.markets/v1/bars/SPY",
    "https://paper-api.alpaca.markets/v1/bars",  # with query param
    "https://data.alpaca.markets/v1/bars/SPY",
    "https://data.alpaca.markets/v2/stocks/SPY/bars",
]

for url in endpoints:
    if "bars/SPY" in url:
        test_url = url
        test_params = params
    else:
        test_url = url
        test_params = {"symbols": "SPY", **params}
    
    try:
        print(f"\nTesting: {test_url}")
        response = requests.get(test_url, params=test_params, headers=headers, timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"  Response type: {type(data)}")
                if isinstance(data, dict):
                    print(f"  Keys: {list(data.keys())[:5]}")
                    if "bars" in data:
                        print(f"  Got {len(data['bars'])} bars - SUCCESS!")
                elif isinstance(data, list):
                    print(f"  Got list with {len(data)} items")
            except:
                print(f"  Response (text): {response.text[:200]}")
        else:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

# Try with symbol as query param
print("\n\n=== Testing with symbol in query ===")
urls = [
    "https://paper-api.alpaca.markets/v1/bars",
    "https://data.alpaca.markets/v1/bars",
]

for base in urls:
    try:
        print(f"\nTesting: {base}?symbols=SPY")
        response = requests.get(f"{base}", params={"symbols": "SPY", "timeframe": "1Day"}, headers=headers, timeout=10)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Keys: {list(data.keys())}")
    except Exception as e:
        print(f"  Error: {e}")
