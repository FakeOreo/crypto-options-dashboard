import pandas as pd
import numpy as np
from datetime import datetime
from scipy.optimize import minimize
from scipy.stats import norm


def process_mesh_data(df):
    """Prepares data for the 3D surface"""
    df[['asset', 'expiry', 'strike', 'type']] = df['instrument_name'].str.split('-', expand=True)
    df['strike'] = pd.to_numeric(df['strike'])
    df['mark_iv'] = df['mark_iv'] / 100 
    df['dte'] = (pd.to_datetime(df['expiry'], format='%d%b%y') - datetime.utcnow()).dt.days
    return df[df['dte'] > 0]

def calculate_z_score(current_iv, rv_series, window=30):
    """Calculates how expensive IV is relative to RV history"""
    rv_mean = rv_series.tail(window).mean()
    rv_std = rv_series.tail(window).std()
    return (current_iv - rv_mean) / rv_std

def process_scanner_with_vrp(df, realized_vol):
    """
    Adds VRP metrics to the options dataframe.
    realized_vol should be the single current float value for BTC or ETH.
    """
    if df.empty:
        return df
    
    # Ensure both are on the same 0.0 - 1.0 scale
    rv_normalized = realized_vol / 100 if realized_vol > 2 else realized_vol
    
    # Calculate raw VRP and VRP Yield
    df['vrp_raw'] = df['mark_iv'] - realized_vol
    df['vrp_yield'] = (df['vrp_raw'] / df['mark_iv']) * 100
    
    # Optional: Calculate 'Edge' score
    # A score that combines VRP with liquidity (open interest)
    # if 'open_interest' in df.columns:
    #     df['edge_score'] = df['vrp_yield'] * np.log1p(df['open_interest'])
        
    return df

def calculate_ewma(current_val, previous_val, alpha=0.2):
    """New Smoothing Logic"""
    if previous_val is None or previous_val == 0:
        return current_val
    return (current_val * alpha) + (previous_val * (1 - alpha))

def calculate_greeks(S, K, T, sigma, r=0, option_type='c'):
    """
    Calculates Delta Gamma, and Vega using Black-Scholes.
    S: Spot, K: Strike, T: Time (Years), sigma: IV (Decimal)
    """
    if T <= 0 or sigma <= 0:
        return 0, 0, 0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    # Delta
    if option_type.lower() in ['c', 'call', 'calls']:
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1
        
    # Gamma (Same for both Calls and Puts)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    
    # Vega (Change in price per 1% change in IV)
    vega = S * np.sqrt(T) * norm.pdf(d1) * 0.01

    return delta, gamma, vega


def sabr_hagan(F, K, T, alpha, beta, rho, nu):
    """Calculates Implied Volatility using the Hagan SABR approximation."""
    if T <= 0: return 0
    if F == K: # ATM Formula
        numeric = 1 + (((1-beta)**2/24 * alpha**2/(F**(2-2*beta))) + 
                       (0.25 * rho*beta*nu*alpha/(F**(1-beta))) + 
                       ((2-3*rho**2)/24 * nu**2)) * T
        return (alpha / (F**(1-beta))) * numeric
    
    # Non-ATM Formula
    logFK = np.log(F/K)
    f0k0 = (F*K)**((1-beta)/2)
    z = (nu/alpha) * f0k0 * logFK
    x_z = np.log((np.sqrt(1 - 2*rho*z + z**2) + z - rho) / (1 - rho))
    
    denominator = f0k0 * (1 + ((1-beta)**2/24 * logFK**2) + ((1-beta)**4/1920 * logFK**4))
    multiplier = z / x_z
    content = 1 + (((1-beta)**2/24 * alpha**2/(f0k0**2)) + 
                   (0.25 * rho*beta*nu*alpha/f0k0) + 
                   ((2-3*rho**2)/24 * nu**2)) * T
    
    return (alpha / denominator) * multiplier * content

def fit_sabr(market_strikes, market_vols, F, T):
    """Fits Alpha, Rho, and Nu to market data (Fixing Beta at 0.5)."""
    beta = 0.5
    
    def objective(params):
        alpha, rho, nu = params
        if alpha <= 0 or not (-1 < rho < 1) or nu <= 0:
            return 1e12
        model_vols = [sabr_hagan(F, K, T, alpha, beta, rho, nu) for K in market_strikes]
        return np.sum((np.array(market_vols) - np.array(model_vols))**2)

    # Initial Guesses: alpha (ATM vol), rho (tilt), nu (smile curve)
    initial_guess = [market_vols.mean(), -0.1, 0.5]
    res = minimize(objective, initial_guess, method='Nelder-Mead')
    return res.x # Returns [alpha, rho, nu]

# Identifies outliers and calculates delta hedging requirements.
def get_sabr_signals(df, threshold,current_spot):
    if df.empty:
        return df

    # Filter by the user-defined threshold (e.g., 100 BPS)
    outliers = df[df['edge_bps'].abs() > threshold].copy()
    
    if outliers.empty:
        return outliers

    def apply_greeks(row):
        T = row['dte'] / 365.0
        iv = row['mark_iv'] / 100 if row['mark_iv'] > 2 else row['mark_iv']
        d, g, v = calculate_greeks(current_spot, row['strike'], T, iv, option_type=row['type'])
        return pd.Series({'delta': d, 'gamma': g, 'vega': v})

    outliers[['delta', 'gamma', 'vega']] = outliers.apply(apply_greeks, axis=1)

    # Determine Action
    outliers['Action'] = outliers['edge_bps'].apply(
        lambda x: "🔴 OVERPRICED (Sell)" if x > 0 else "🟢 CHEAP (Buy)"
    )

    # Calculate Hedge Action
    def calculate_hedge(row):
        qty = abs(row['delta'])
        if row['Action'].startswith("🔴"):
            return f"Buy {qty:.3f} Spot" if row['delta'] > 0 else f"Sell {qty:.3f} Spot"
        else:
            return f"Sell {qty:.3f} Spot" if row['delta'] > 0 else f"Buy {qty:.3f} Spot"

    outliers['Hedge_Action'] = outliers.apply(calculate_hedge, axis=1)
    return outliers

def calculate_vega(S, K, T, sigma, r=0):
    """Calculates Black-Scholes Vega (change in price per 1% change in IV)."""
    if T <= 0 or sigma <= 0:
        return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    # Vega formula: S * sqrt(T) * pdf(d1)
    return S * np.sqrt(T) * norm.pdf(d1) * 0.01

def get_expected_pnl(row, current_spot):
    """Estimates dollar profit if IV reverts to SABR curve."""
    T = row['dte'] / 365.0
    iv = row['mark_iv'] / 100
    # Calculate Vega for 1 unit
    vega_1unit = calculate_vega(current_spot, row['strike'], T, iv)
    # Edge in % (not BPS)
    iv_diff_pct = (row['mark_iv'] - row['sabr_iv']) 
    return vega_1unit * iv_diff_pct