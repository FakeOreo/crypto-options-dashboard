# scanner.py
import pandas as pd
import numpy as np

def scan_best_opportunities(df, rv_val):
    """Identifies top 3 cheap and top 3 expensive contracts(IV>RV)."""
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    
    # We want contracts with volume so we don't buy 'ghost' options
    active_options = df[df['volume'] > 0].copy()
    
    if active_options.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Calculate the spread between IV and RV
    # We multiply mark_iv by 100 to bring it to the same scale as rv_val
    active_options['vol_edge'] = (active_options['mark_iv'] * 100) - rv_val
    
    # Sort for Value
    # Cheap: IV is much lower than RV
    cheap = active_options.sort_values(by='vol_edge').head(3)
    
    # Expensive: IV is much higher than RV
    expensive = active_options.sort_values(by='vol_edge', ascending=False).head(3)
    
    cols = ['instrument_name', 'mark_iv', 'vol_edge']
    return cheap[cols], expensive[cols]


#Sell Vol 
def get_top_sell_signals(df, realized_vol, spot_price):
    """
    Refines the options list into specific high-edge sell signals.
    """
    if df.empty or spot_price <=0:
        return pd.DataFrame()


# 1. Identify Type and Strike from the name
    # Format: BTC-27FEB26-40000-P
    details = df['instrument_name'].str.split('-', expand=True)
    df['strike'] = pd.to_numeric(details[2])
    df['type'] = details[3]

    # 2. Determine if the option is Out-of-the-Money (OTM)
    # Sellers usually only want to sell OTM options for high PoP
    df['is_otm'] = False
    df.loc[(df['type'] == 'C') & (df['strike'] > spot_price), 'is_otm'] = True
    df.loc[(df['type'] == 'P') & (df['strike'] < spot_price), 'is_otm'] = True

    # 3. Refined PoP Logic
    if 'delta' in df.columns and not df['delta'].isna().all():
        df['pop'] = (1 - df['delta'].abs()) * 100
    else:
        # Improved Fallback: If it's ITM, PoP is very low. 
        # If OTM, it scales with distance.
        def calculate_proxy_pop(row):
            dist = abs(row['strike'] - spot_price) / spot_price
            if row['is_otm']:
                return min(99, 50 + (dist * 150)) # OTM: High PoP
            else:
                return max(1, 10 - (dist * 150))  # ITM: Very Low PoP
        
        df['pop'] = df.apply(calculate_proxy_pop, axis=1)

    # 4. Filter for only OTM options with positive Edge
    # This prevents the 40k Call from appearing as a "Sell Signal" if BTC is 60k
    signals = df[(df['vrp_yield'] > 10) & (df['is_otm'] == True)].copy()

    if not signals.empty:
        signals['edge_score'] = (signals['vrp_yield'] * (signals['pop'] / 100)) * np.log1p(signals['open_interest'])
        return signals.sort_values(by='edge_score', ascending=False).head(10)

    return pd.DataFrame()    # # 1. Clean and Calculate VRP Yield
    # # (IV - RV) / IV -> The percentage of premium that is 'pure' overpricing
    # # We normalize realized_vol (e.g., 50.0 -> 0.5) to match mark_iv scale
    # rv_normalized = realized_vol / 100
    # df['vrp_yield'] = ((df['mark_iv'] - rv_normalized) / df['mark_iv']) * 100
    
    # # 2. Extract Strike and Type (if not already present)
    # # Assumes format: BTC-27FEB26-40000-P
    # if 'strike' not in df.columns:
    #     df['strike'] = df['instrument_name'].str.split('-').str[2].astype(float)
    # if 'option_type' not in df.columns:
    #     df['option_type'] = df['instrument_name'].str.split('-').str[3]

    # # 3. Logic: Is it Out-of-the-Money (OTM)?
    # # A Call is OTM if Strike > Spot | A Put is OTM if Strike < Spot
    # df['is_otm'] = (
    #     ((df['option_type'] == 'C') & (df['strike'] > spot_price)) |
    #     ((df['option_type'] == 'P') & (df['strike'] < spot_price))
    # )

    # # 4. Refined PoP Logic
    # if 'delta' in df.columns and not df['delta'].isna().all():
    #     # For OTM options, PoP is 1 - |Delta|
    #     # For ITM options, PoP is |Delta| (roughly, though usually we don't sell these)
    #     df['pop'] = df.apply(
    #         lambda x: (1 - abs(x['delta'])) * 100 if x['is_otm'] else (abs(x['delta'])) * 100, 
    #         axis=1
    #     )
    # else:
    #     # Improved Fallback: Distance only helps if it's OTM
    #     def calculate_fallback_pop(row):
    #         dist = abs(row['strike'] - spot_price) / spot_price
    #         if row['is_otm']:
    #             return min(99, 80 + (dist * 100))
    #         else:
    #             return max(1, 20 - (dist * 100)) # High distance ITM = Very low PoP
        
    #     df['pop'] = df.apply(calculate_fallback_pop, axis=1)

    # # 5. Filtering for the "Seller's Sweet Spot"
    # # CRITICAL: Only sell OTM options with positive VRP
    # signals = df[(df['vrp_yield'] > 10) & (df['is_otm'] == True)].copy()

    # if not signals.empty:
    #     signals['edge_score'] = signals['vrp_yield'] * (signals['pop'] / 100)
    #     return signals.sort_values(by='edge_score', ascending=False).head(10)

    # return pd.DataFrame()

    # # 1. Clean and Calculate VRP Yield
    # # (IV - RV) / IV -> The percentage of premium that is 'pure' overpricing
    # df['vrp_yield'] = ((df['mark_iv'] - realized_vol) / df['mark_iv']) * 100
    
    # # 2. Probability of Profit (PoP)
    # # Using Delta as a proxy. Note: Deribit provides 'greeks' in the ticker or ticker-like responses.
    # # If delta isn't in your summary df, you can approximate it or ensure it's fetched.
    # if 'delta' not in df.columns:
    #     # We extract the strike price from the instrument name (e.g., BTC-27MAR26-70000-C)
    #     df['strike'] = df['instrument_name'].str.split('-').str[2].astype(float)
            
    #     # Simple proxy: Options further from spot have higher PoP
    #     # This isn't perfect Delta, but it prevents the crash and gives a 'Safety' score
    #     dist = abs(df['strike'] - spot_price) / spot_price
    #     df['pop'] = (80 + (dist * 100)).clip(upper=99) # Proxy: 80% base + distance
    #     df['delta'] = 0.25 # Temporary placeholder for the column display
    # else:
    #     df['pop'] = (1 - df['delta'].abs()) * 100

    # # 3. Filtering for the "Seller's Sweet Spot"
    # # We want OTM options (Delta 0.1 to 0.3) with positive VRP
    # filtered_df = df[df['vrp_yield'] > 10].copy()

    # # 4. Scoring the 'Edge'
    # # High VRP + High PoP = The Best Trades
    # filtered_df['edge_score'] = filtered_df['vrp_yield'] * (filtered_df['pop'] / 100)
    
    # return filtered_df.sort_values(by='edge_score', ascending=False).head(10)