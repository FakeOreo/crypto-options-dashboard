# visualizations.py
import plotly.graph_objects as go
import numpy as np

def create_3d_surface(df, option_type="C"):
    plot_data = df[df['type'] == option_type].copy()
    
    if plot_data.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available for this contract type")
        return fig

    fig = go.Figure(data=[go.Mesh3d(
        x=plot_data['strike'], 
        y=plot_data['dte'], 
        z=plot_data['mark_iv'],
        intensity=plot_data['mark_iv'], 
        colorscale='Viridis',
        opacity=0.8,
        colorbar=dict(title="IV", thickness=15)
    )])

    fig.update_layout(
        scene=dict(
            xaxis_title='Strike Price',
            yaxis_title='Days to Expiry',
            zaxis_title='IV',
            aspectmode='manual', # Allows the chart to stretch
            aspectratio=dict(x=1, y=1, z=0.5)
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=700, # Increased height
        template="plotly_dark"
    )
    return fig

# # Sentiment Gauge Visualization

def create_sentiment_gauge(score):
    if score is None or np.isnan(score):
        score = 50.0
        
    color = "#ef5350" if score < 40 else "#66bb6a" if score > 60 else "#d1d1d1"
    
    # Math for the needle tip
    # We map 0-100 to 180-0 degrees
    theta = 180 - (score / 100 * 180)
    rad = np.deg2rad(theta)
    
    # Needle coordinates (Scatter plot logic)
    # The center of a go.Indicator gauge is always at [0.5, 0.28] roughly
    needle_length = 0.2
    x_origin = 0.5
    y_origin = 0.22
    x_needle = [x_origin, x_origin + needle_length * np.cos(rad)]
    y_needle = [y_origin, y_origin + needle_length * np.sin(rad)]

    fig = go.Figure()

    # 1. The Background Gauge
    fig.add_trace(go.Indicator(
        mode="gauge",
        value=score,
        domain={'x': [0.15, 0.85], 'y': [0.05, 0.85]},
        number={
            'font': {'size': 42, 'color': color}, 
            'suffix': "%", 
            'valueformat': '.1f'},
        gauge={
            'axis': {'range': [0, 100], 'visible': False},
            'bar': {'color': "rgba(0,0,0,0)"}, # Hidden
            'steps': [
                {'range': [0, 40], 'color': "rgba(239, 83, 80, 0.4)"},
                {'range': [40, 60], 'color': "rgba(128, 128, 128, 0.2)"},
                {'range': [60, 100], 'color': "rgba(102, 187, 106, 0.4)"}
            ],
            'borderwidth': 0
        }
    ))

    # 2. The Needle (using Scatter to ensure it stays "Round")
    fig.add_trace(go.Scatter(
        x=x_needle,
        y=y_needle,
        mode='lines+markers',
        line=dict(color='white', width=5),
        marker=dict(size=[15, 0], color='white'), # Size 15 creates the center hub
        hoverinfo='skip',
        cliponaxis= False
    ))
    # 3. MANUAL TEXT OVERLAY (The Score)
    fig.add_trace(go.Scatter(
        x=[0.5],
        y=[0.08],
        text=[f"{score:.1f}%"],
        mode="text",
        textfont=dict(size=30, color=color, family="Arial"),
        hoverinfo='skip'
    ))

    fig.update_layout(
        xaxis=dict(range=[0, 1], visible=False, fixedrange=True),
        yaxis=dict(range=[0, 1], visible=False, fixedrange=True),
        height=300,
        margin=dict(l=30, r=30, t=50, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig

def create_sabr_plot(df, curve_strikes, curve_vols):
    fig = go.Figure()

    # Market Data Points
    fig.add_trace(go.Scatter(
        x=df['strike'], y=df['mark_iv'],
        mode='markers', name='Market IV',
        marker=dict(color='cyan', size=8)
    ))

    # Fitted SABR Curve
    fig.add_trace(go.Scatter(
        x=curve_strikes, y=curve_vols,
        mode='lines', name='SABR Fitted Curve',
        line=dict(color='magenta', width=2, dash='dash')
    ))

    fig.update_layout(
        title="Market IV vs. SABR Model",
        xaxis_title="Strike Price",
        yaxis_title="Implied Volatility",
        template="plotly_dark",
        hovermode="x unified"
    )
    return fig