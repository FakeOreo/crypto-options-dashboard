# rel_val.py
import pandas as pd
import numpy as np

def get_cross_asset_summary(btc_options, eth_options, btc_rv_df, eth_rv_df):
    """
    Aggregates metrics for both BTC and ETH to compare them.
    Returns a structured dictionary of metrics for the UI grid.
    """
    results = {}
    
    # Define assets to iterate through
    assets = [
        ('BTC', btc_options, btc_rv_df),
        ('ETH', eth_options, eth_rv_df)
    ]
    
    for name, options_df, rv_df in assets:
        # 1. Mean Implied Vol (ATM Proxy)
        iv = options_df['mark_iv'].mean() if not options_df.empty else 0
        
        # 2. Latest Realized Vol
        rv = rv_df['rv'].iloc[-1] if not rv_df.empty else 0
        
        # 3. IV Z-Score (Using the 10% standard deviation proxy from your app.py)
        z_score = (iv - rv) / (rv * 0.1) if rv > 0 else 0
        
        # 4. VRP Yield
        vrp_yield = ((iv - rv) / iv * 100) if iv > 0 else 0
        
        results[name] = {
            'iv': iv,
            'rv': rv,
            'z_score': z_score,
            'vrp_yield': vrp_yield
        }
    
    # 5. Calculate the Relative Value Spread (ETH IV / BTC IV Ratio)
    btc_iv = results['BTC']['iv']
    eth_iv = results['ETH']['iv']
    
    iv_ratio = eth_iv / btc_iv if btc_iv != 0 else 0
    
    # Traditional "Status" logic from your rel_val.py
    if iv_ratio < 1.05:
        status = "ETH Lagging"
    elif iv_ratio < 1.25:
        status = "Normal"
    else:
        status = "ETH Rich"
        
    results['spread'] = {
        'ratio': iv_ratio,
        'status': status
    }
    
    return results