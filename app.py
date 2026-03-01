import streamlit as st
import numpy as np
import pandas as pd
import datetime
from core import data_provider as dp, analytics as an, rel_val as rv
from components import visualizations as vis, scanner as scan, flow_monitor as flow
from styles import apply_custom_styles
from streamlit_autorefresh import st_autorefresh

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 1. CONFIG & REFRESH ---
st.set_page_config(
    layout="wide", # Changed to wide to better accommodate the new grid layouts
    page_title="Crypto Options Command Center",
    initial_sidebar_state="expanded"
)
apply_custom_styles()

st.title("Crypto Options Command Center")

#Refresh timer (every 60 seconds)
count = st_autorefresh(interval=60000, limit=None, key="datarefresh")
last_updated = datetime.datetime.now().strftime("%H:%M:%S")

# --- 2. SIDEBAR CONTROLS ---
st.sidebar.write(f"⏱️ **Last Updated:** {last_updated}")
asset = st.sidebar.selectbox("Asset", ["BTC", "ETH"])
option_type = st.sidebar.radio("Option Type", ["Calls", "Puts"])
type_code = "C" if option_type == "Calls" else "P"
if st.sidebar.button("🔄 Refresh"):
    st.cache_data.clear()  # Clears cache to ensure we get live data from APIs
    st.rerun()             # Forces the script to restart immediately

st.sidebar.subheader("SABR Sensitivity")
# Allow user to choose how many BPS constitutes a "Signal"
edge_threshold = st.sidebar.slider(
    "Signal Threshold (BPS)", 
    min_value=50, 
    max_value=500, 
    value=100, 
    step=25,
    help="Basis Points deviation from SABR curve required to trigger a signal."
)
# --- 3. FETCH GLOBAL DATA ---
# Fetch spot prices once to use everywhere
cg_prices = dp.get_coingecko_spot()
btc_p, eth_p = cg_prices.get('BTC', 0), cg_prices.get('ETH', 0)
current_spot = btc_p if asset == "BTC" else eth_p

# Fetch core options and volatility data
raw_options = dp.fetch_options_data(asset)
rv_history = dp.fetch_rv_data(asset)
trade_flow = flow.fetch_recent_trades(asset)

# Process data for the views
processed_options = an.process_mesh_data(raw_options)
if not processed_options.empty:
    processed_options.columns = [c.lower() for c in processed_options.columns]
latest_rv = rv_history['rv'].iloc[-1] if not rv_history.empty else 0

# Inject VRP and find Median IV
if not processed_options.empty:
    processed_options = an.process_scanner_with_vrp(processed_options, latest_rv)
    latest_iv = processed_options[processed_options['type'] == type_code]['mark_iv'].median() * 100
else:
    latest_iv = 0

#4 SIDEBAR CONTROLS PT 2 (DATA-DEPENDENT WIDGETS)
if not processed_options.empty:
    available_expiries = sorted(
    processed_options['expiry'].unique(), 
    key=lambda x: datetime.datetime.strptime(x, '%d%b%y')
)
    selected_expiry = st.sidebar.selectbox("Select Expiry for SABR Fit", available_expiries)
else:
    selected_expiry = None

# --- 5. TOP SUMMARY BAR ---
price_col1, price_col2, price_col3, price_col4 = st.columns(4)
price_col1.metric(f"{asset} Spot", f"${current_spot:,.2f}")
price_col2.metric("Realized Vol (RV)", f"{latest_rv:.1f}%")
price_col3.metric("Median IV", f"{latest_iv:.1f}%")
price_col4.markdown(f"**Market Status**\n\n{'🟢 Active' if current_spot > 0 else '🔴 Offline'}")

# --- 6. GLOBAL MARKET SENTIMENT ---
st.divider()
st.subheader("📡 Global Market Sentiment")

global_score = flow.get_flow_sentiment(trade_flow)
col_g1, col_g2 = st.columns([2, 1])

with col_g1:
    st.plotly_chart(vis.create_sentiment_gauge(global_score), use_container_width=True)

with col_g2:
    st.write("### Current Bias")
    if global_score > 60:
        st.success(f"🔥 **BULLISH BIAS**\n\nWhales are aggressively buying {asset} calls or selling puts.")
    elif global_score < 40:
        st.error(f"❄️ **BEARISH BIAS**\n\nProtective put buying is dominating the {asset} tape.")
    else:
        st.warning(f"⚖️ **NEUTRAL BIAS**\n\nMarket is in a tug-of-war. Theta (time decay) is the winner here.")
    st.metric("Sentiment Score", f"{global_score:.1f}%")

# 7. SABR SMILE FITTING & OUTLIER DETECTION
st.divider()
st.subheader(f"🎯 SABR Volatility Smile: {selected_expiry}")

if selected_expiry:
    
    expiry_df = processed_options[processed_options['expiry'].str.lower() == selected_expiry.lower()].copy()
    lower_bound = current_spot * 0.5
    upper_bound = current_spot * 1.5
    expiry_df = expiry_df[(expiry_df['strike'] >= lower_bound) & (expiry_df['strike'] <= upper_bound)]
    expiry_df = expiry_df.sort_values('strike')

    if len(expiry_df) > 5:
        F = current_spot
        T = expiry_df['dte'].iloc[0] / 365.0
        
        try:
            # 1. Fit Parameters
            alpha, rho, nu = an.fit_sabr(expiry_df['strike'].values, expiry_df['mark_iv'].values, F, T)
            
            # 2. Curve Generation
            smooth_strikes = np.linspace(expiry_df['strike'].min(), expiry_df['strike'].max(), 100)
            sabr_curve = [an.sabr_hagan(F, K, T, alpha, 0.5, rho, nu) for K in smooth_strikes]
            
            # 3. Calculate Deviation
            expiry_df['sabr_iv'] = expiry_df['strike'].apply(lambda k: an.sabr_hagan(F, k, T, alpha, 0.5, rho, nu))
            expiry_df['edge_bps'] = (expiry_df['mark_iv'] - expiry_df['sabr_iv']) * 10000
            
            # 4. Visualization
            fig_sabr = vis.create_sabr_plot(expiry_df, smooth_strikes, sabr_curve)
            st.plotly_chart(fig_sabr, use_container_width=True)
            
            # 5. Outlier Table
            outliers = an.get_sabr_signals(expiry_df, edge_threshold, current_spot)
            if not outliers.empty:
                outliers['expected_pnl'] = outliers.apply(lambda r: an.get_expected_pnl(r, current_spot), axis=1)
                st.write(f"### 🚩 Trade Signals (> {edge_threshold} BPS Deviation)")
                
                #TRADE EXECUTION INTERFACE
                with st.expander("🚀 Log New Trade Position", expanded=False):
                    log_col1, log_col2, log_col3 = st.columns([2, 1, 1])
                    
                    with log_col1:
                        selected_ticker = st.selectbox("Select Contract:", outliers['instrument_name'].tolist())
                    with log_col2:
                        trade_qty = st.number_input("Qty (Units):", min_value=0.1, value=1.0, step=0.1)
                    with log_col3:
                        st.write(" ") # Padding
                        if st.button("Add to Portfolio", use_container_width=True):
                            # Grab the data for the specific ticker
                            trade_row = outliers[outliers['instrument_name'] == selected_ticker].iloc[0].to_dict()
                            trade_row['qty'] = trade_qty
                            trade_row['entry_spot'] = current_spot
                            trade_row['entry_iv'] = trade_row['mark_iv'] = trade_row['mark_iv'] if trade_row['mark_iv'] > 2 else trade_row['mark_iv'] * 100
                            trade_row['target_sabr_iv'] = trade_row['sabr_iv'] if trade_row['sabr_iv'] > 2 else trade_row['sabr_iv'] * 100
                            trade_row['timestamp'] = datetime.datetime.now().strftime("%H:%M:%S")
                            
                            # Append to Session State
                            st.session_state.portfolio.append(trade_row)
                            st.toast(f"Logged {trade_qty} {selected_ticker}", icon="✅")

                #SIGNAL TABLE
                st.dataframe(
                    outliers[['instrument_name', 'mark_iv', 'sabr_iv', 'edge_bps', 'delta', 'Action', 'Hedge_Action']].sort_values('edge_bps', ascending=False),
                    column_config={
                        "instrument_name": "Contract",
                        "mark_iv": st.column_config.NumberColumn("Market IV", format="%.2f"),
                        "edge_bps": st.column_config.NumberColumn("Edge (BPS)", format="%d"),
                        "delta": st.column_config.NumberColumn("Delta", format="%.3f"),
                        "Hedge_Action": "Execution: Hedge per 1 Unit"
                    },
                    use_container_width=True, hide_index=True
                )
            else:
                st.success(f"✅ No significant deviations found (> {edge_threshold} BPS).")

                # Model Metrics
                p1, p2, p3 = st.columns(3)
                p1.metric("Alpha (Vol Level)", f"{alpha:.2f}")
                p2.metric("Rho (Skew)", f"{rho:.2f}")
                p3.metric("Nu (Vol-of-Vol)", f"{nu:.2f}")

        except Exception as e:
            st.error(f"SABR Fit Error: {e}")
else:
    st.info("Please select an expiry in the sidebar to view SABR analysis.")

# --- 8. ACTIVE POSITIONS & LIVE PNL ---
st.divider()
st.subheader("💼 Active Portfolio Tracker")

if st.session_state.portfolio:
    portfolio_df = pd.DataFrame(st.session_state.portfolio)
    current_iv_map = dict(zip(processed_options['instrument_name'], processed_options['mark_iv']))
    
    # Calculate Live PnL (Simplified: current_spot vs entry_spot for the hedge)
    portfolio_df['spot_pnl'] = (current_spot - portfolio_df['entry_spot']) * portfolio_df['delta'] * portfolio_df['qty']
    # If we sold the option (Action: Sell), and spot went up, we make money on the Long Spot hedge.
    
# Header Row
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
    h1.write("**Contract**")
    h2.write("**Direction**")
    h3.write("**Qty**")
    h4.write("**Entry IV**")
    h5.write("**Target IV**")
    h6.write("**Hedge PnL**")
    h7.write("**IV Edge**")   
    h8.write("**Action**")
    st.divider()

    total_vol_pnl = 0   # To track total unrealized edge

    # 2. Loop through and create rows with individual "Close" buttons
    # We use a copy of the list so we can remove items while looping
    for index, trade in enumerate(st.session_state.portfolio):
       
        live_iv = current_iv_map.get(trade['instrument_name'], 0) * 100 # Standardize to %
        entry_iv = trade['entry_iv'] 
        target_iv = trade['target_sabr_iv']

        initial_gap = entry_iv - target_iv
        current_gap = live_iv - target_iv

        # Calculate Vol PnL: (Current IV - SABR IV) * Vega * Qty
        # Here we approximate current "vol profit" as (Entry - Current) for sellers
        action_str = trade.get('Action','')
        is_sell = trade['Action'].startswith("🔴")
        dir_text="Sell" if is_sell else "Buy"
        dir_color = "red" if is_sell else "green"
        iv_progress = entry_iv - live_iv if is_sell else live_iv - entry_iv
        
        # Current Vol Profit (Unrealized)
        row_vol_pnl = iv_progress * trade['vega'] * trade['qty']
        total_vol_pnl += row_vol_pnl

        row_hedge_pnl = (current_spot - trade['entry_spot']) * trade['delta'] * trade['qty']
        
        r1, r2, r3, r4, r5, r6, r7, r8 = st.columns([2, 1, 1, 1, 1, 1, 1,1])
        
        r1.write(f"**{trade['instrument_name']}**")
        r2.markdown(f"**:{dir_color}[{dir_text}]**")
        r3.write(f"{trade['qty']}")
        r4.write(f"{trade['entry_iv']:.1f}%")
        r5.write(f"{target_iv:.1f}%")
        # Color-coded PnL
        pnl_color = "green" if row_hedge_pnl >= 0 else "red"
        r6.markdown(f":{pnl_color}[${row_hedge_pnl:.2f}]")
        
        diff_to_target=abs(live_iv-target_iv)
        if diff_to_target < 0.5:
            r7.write("🎯 Target Met")
        else:
            remaining_edge = live_iv - target_iv if is_sell else target_iv - live_iv
            edge_color = "green" if remaining_edge > 0 else "blue" # Blue if we overshot target
            r7.markdown(f":{edge_color}[{remaining_edge:+.1f}% to Target]")
        
        if r8.button("Close", key=f"close_{index}_{trade['instrument_name']}"):
            st.session_state.portfolio.pop(index)
            st.rerun()

    # 3. Summary Metrics
    st.divider()
    
    total_hedge_pnl = ( (current_spot - portfolio_df['entry_spot']) * portfolio_df['delta'] * portfolio_df['qty'] ).sum()
    # 1. Calculate Theoretical Vol PnL (Target - Entry)
    theoretical_vol_pnl = 0
    for trade in st.session_state.portfolio:
        is_sell = "Sell" in trade.get('Action', '') or "🔴" in trade.get('Action', '')
        # The total points we expect to capture if the model is right
        points_to_target = trade['entry_iv'] - trade['target_sabr_iv'] if is_sell else trade['target_sabr_iv'] - trade['entry_iv']
        theoretical_vol_pnl += points_to_target * trade.get('vega', 0) * trade['qty']

    total_col1, total_col2, total_col3 = st.columns(3)
    
    # Current PnL (Live)
    current_total_pnl = total_hedge_pnl + total_vol_pnl
    total_col1.metric(
        "Current Unrealized PnL", 
        f"${current_total_pnl:,.2f}", 
        delta=f"${total_vol_pnl:+.2f} from Vol",
        help="What you would realize if you closed all positions at current market prices."
    )
    
    # Theoretical PnL (At Target)
    max_expected_pnl = total_hedge_pnl + theoretical_vol_pnl
    total_col2.metric(
        "Max Potential PnL", 
        f"${max_expected_pnl:,.2f}", 
        delta=f"${theoretical_vol_pnl:+.2f} Potential",
        help="Total PnL if Mark IV converges perfectly to your SABR Target IV."
    )
    
    # Risk Metric
    total_delta = (portfolio_df['delta'] * portfolio_df['qty']).sum()
    total_col3.metric("Net Portfolio Delta", f"{total_delta:.3f}")
else:
    st.info("No open trades tracked. Log a signal above to start monitoring.")

# --- 9. CROSS-ASSET RELATIVE VALUE ---
st.divider()
st.subheader("🔗 Cross-Asset Relative Value (Live Deribit)")

# Fetch all data needed for cross-asset comparison
ca_metrics = rv.get_cross_asset_summary(
    dp.fetch_options_data("BTC"), dp.fetch_options_data("ETH"),
    dp.fetch_rv_data("BTC"), dp.fetch_rv_data("ETH")
)

col_rv1, col_rv2, col_rv3, col_rv4 = st.columns(4)
for i, sym in enumerate(["BTC", "ETH"]):
    col_rv1.metric(f"{sym} ATM IV", f"{ca_metrics[sym]['iv']:.1f}%")
    col_rv2.metric(f"{sym} RV", f"{ca_metrics[sym]['rv']:.1f}%")
    z = ca_metrics[sym]['z_score']
    col_rv3.metric(f"Z-Score ({sym})", f"{z:.2f}", delta="Rich" if z > 1.5 else "Cheap" if z < -1.5 else "Fair")
    col_rv4.metric(f"VRP Yield ({sym})", f"{ca_metrics[sym]['vrp_yield']:.1f}%")

# --- 10. ALPHA SELL VOL SIGNALS ---
st.divider()
st.subheader("🚨 Alpha Sell Vol Signals (High VRP + High PoP)")
sell_candidates = scan.get_top_sell_signals(processed_options, latest_rv, current_spot)

if not sell_candidates.empty:
    st.dataframe(
        sell_candidates[['instrument_name', 'mark_iv', 'vrp_yield', 'pop', 'edge_score']], 
        column_config={
            "instrument_name": "Contract",
            "mark_iv": st.column_config.NumberColumn("IV", format="%.2f"),
            "vrp_yield": st.column_config.NumberColumn("VRP Yield", format="%.1f%%"),
            "pop": st.column_config.ProgressColumn("Prob. of Profit", min_value=0, max_value=100, format="%.0f%%"),
            "open_interest": st.column_config.NumberColumn("Open Interest", format="%d"),
            "edge_score": st.column_config.NumberColumn("Edge Score", format="%.1f")
        },
        use_container_width=True
    )
else:
    st.info("No strong sell signals at the moment. Waiting for better opportunities...")


# --- 11. VOLATILITY OPPORTUNITIES SCANNER ---
st.divider()
st.subheader("💡 Volatility Opportunities Scanner")
cheap_df, expensive_df = scan.scan_best_opportunities(processed_options, latest_rv)

col_c1, col_c2 = st.columns(2)
with col_c1:
    st.write("🟢 Potential 'Cheap' Buys (Low IV vs RV)")
    st.dataframe(cheap_df, use_container_width=True)
with col_c2:
    st.write("🔴 Potential 'Expensive' Sells (High IV vs RV)")
    st.dataframe(expensive_df, use_container_width=True)


# --- 12. LIVE OPTIONS FLOW TAPE ---
st.divider()
st.subheader(f"⚡ Live {asset} Tape (Recent Blocks & Large Trades)")

if not trade_flow.empty:
    def highlight_blocks(row):
        return ['background-color: #1d2129' if row.is_block else '' for _ in row]

    st.dataframe(trade_flow.style.apply(highlight_blocks, axis=1), use_container_width=True, height=300)
else:
    st.info("Waiting for new trade data...")


# --- 13. 3D VOLATILITY MODEL ---
st.divider()
st.subheader(f"📊 {asset} {option_type} Volatility Landscape")

col_metrics, col_chart = st.columns([1, 4]) 
with col_metrics:
    z_score = an.calculate_z_score(latest_iv, rv_history['rv'])
    st.metric("ATM IV", f"{latest_iv:.1f}%")
    st.metric("Realized Vol", f"{latest_rv:.1f}%")
    st.metric("IV Z-Score", f"{z_score:.2f}", delta_color="inverse")
    st.info(f"Viewing: {asset} {option_type}")

with col_chart:
    fig = vis.create_3d_surface(processed_options, type_code)
    st.plotly_chart(fig, use_container_width=True)

