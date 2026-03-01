# flow_monitor.py
import pandas as pd
import requests

def fetch_recent_trades(currency="BTC", count=50):
    """Fetches the latest trades and safely handles block trade data."""
    url = f"https://deribit.com/api/v2/public/get_last_trades_by_currency?currency={currency}&kind=option&count={count}"
    try:
        response = requests.get(url, timeout=10).json()
    
        if 'result' in response and 'trades' in response['result']:
            trades = pd.DataFrame(response['result']['trades'])
        
        trades = pd.DataFrame(response['result']['trades'])

        # Defensive check for block trades
        trades['is_block'] = trades['block_trade_id'].notnull() if 'block_trade_id' in trades.columns else False
            
        # Format for UI display
        trades['time'] = pd.to_datetime(trades['timestamp'], unit='ms').dt.strftime('%H:%M:%S')
        trades['is_call'] = trades['instrument_name'].str.contains("-C")
        
        # Select only necessary columns to keep the UI dataframe light
        cols = ['time', 'instrument_name', 'direction', 'price', 'amount', 'is_block', 'is_call']
        return trades[[c for c in cols if c in trades.columns]]
    
    except Exception:
        return pd.DataFrame()

def get_flow_sentiment(trades_df):
    """Calculates the percentage of taker buy volume."""
    if trades_df.empty or 'direction' not in trades_df.columns:
        return 50.0  # Return neutral 50% if no data
    
    # Identify Bullish flows
    # Taker Buys on Calls = Aggressive bullish
    # Taker Sells on Puts = Selling insurance (bullish bias)
    bullish_condition = (
        (trades_df['is_call'] & (trades_df['direction'] == 'buy')) | 
        (~trades_df['is_call'] & (trades_df['direction'] == 'sell'))
    )
    
    bull_vol = trades_df[bullish_condition]['amount'].sum()
    total_vol = trades_df['amount'].sum()
    
    return (bull_vol / total_vol) * 100 if total_vol > 0 else 50.0

# def get_global_bias(currency="BTC"):
#     """Fetches both and returns a single sentiment score (0-100)."""
#     # Fetch all trades (don't filter by type yet)
#     url = f"https://deribit.com/api/v2/public/get_last_trades_by_currency?currency={currency}&kind=option&count=100"
#     response = requests.get(url).json()
    
#     if 'result' not in response: return 50
    
#     df = pd.DataFrame(response['result']['trades'])
#     df['is_call'] = df['instrument_name'].str.endswith('-C')
    
#     # Logic: 
#     # Bullish = (Buy Calls) + (Sell Puts)
#     # Bearish = (Buy Puts) + (Sell Calls)
    
#     bullish_vol = df[(df['is_call'] & (df['direction'] == 'buy')) | 
#                      (~df['is_call'] & (df['direction'] == 'sell'))]['amount'].sum()
    
#     total_vol = df['amount'].sum()
    
#     return (bullish_vol / total_vol) * 100 if total_vol > 0 else 50

# # flow_monitor.py

# def get_global_sentiment(currency="BTC"):
#     """Combines all recent option trades into a single Bull/Bear score."""
#     url = f"https://deribit.com/api/v2/public/get_last_trades_by_currency?currency={currency}&kind=option&count=100"
#     response = requests.get(url).json()
    
#     if 'result' not in response or not response['result']['trades']:
#         return 50.0
    
#     df = pd.DataFrame(response['result']['trades'])
#     df['is_call'] = df['instrument_name'].str.contains("-C")
    
#     # Logic: Bullish = (Taker Buy Calls) OR (Taker Sell Puts)
#     bullish_condition = (
#         (df['is_call'] & (df['direction'] == 'buy')) | 
#         (~df['is_call'] & (df['direction'] == 'sell'))
#     )
    
#     bull_vol = df[bullish_condition]['amount'].sum()
#     total_vol = df['amount'].sum()
    
#     return (bull_vol / total_vol) * 100 if total_vol > 0 else 50.0