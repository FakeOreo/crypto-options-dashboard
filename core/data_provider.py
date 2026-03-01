import requests
import pandas as pd
import streamlit as st

@st.cache_data(ttl=60)
def fetch_options_data(currency="BTC"):
    url = f"https://deribit.com/api/v2/public/get_book_summary_by_currency?currency={currency}&kind=option"
    try:
        response = requests.get(url, timeout=10).json()
        return pd.DataFrame(response['result']) if 'result' in response else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()
    
def fetch_rv_data(currency="BTC"):
    url = f"https://deribit.com/api/v2/public/get_historical_volatility?currency={currency}"
    try:
        response = requests.get(url, timeout=10).json()
        if 'result' in response:
            df = pd.DataFrame(response['result'], columns=['timestamp', 'rv'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def get_market_vols():
    """Fetches mean Implied Volatility for BTC and ETH from Deribit"""
    vols = {}
    for currency in ['BTC', 'ETH']:
        # Using the same endpoint as fetch_options_data for consistency
        url = f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={currency}&kind=option"
        try:
            response = requests.get(url, timeout=10).json()
            if 'result' in response:
                ivs = [item['mark_iv'] for item in response['result'] if 'mark_iv' in item]
                vols[currency] = sum(ivs) / len(ivs) if ivs else 0
            else:
                vols[currency] = 0
        except Exception:
            vols[currency] = 0
    return vols

def get_trade_flows(asset):
    """
    Fetches recent trades and explicitly removes the unwanted 
    'is_call' and 'is_block' columns.
    """
    # 1. Fetch the raw data from your existing flow module
    from components import flow_monitor as flow
    df = flow.fetch_recent_trades(asset)
    
    if df is not None and not df.empty:
        # 2. List the columns you actually want to keep
        keep_cols = ['time', 'instrument_name', 'direction', 'price', 'amount']
        
        # 3. Return only those columns (ignores is_call, is_block, etc.)
        return df[[col for col in keep_cols if col in df.columns]]
    
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_coingecko_spot():
    """Fetches live BTC and ETH prices from CoinGecko free API"""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
    try:
        response = requests.get(url, timeout=5).json()
        prices = {
            'BTC': response.get('bitcoin', {}).get('usd', 0),
            'ETH': response.get('ethereum', {}).get('usd', 0)
        }
        return prices
    except Exception as e:
        print(f"CoinGecko Error: {e}")
        return {'BTC': 0, 'ETH': 0}