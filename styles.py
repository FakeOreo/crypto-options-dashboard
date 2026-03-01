import streamlit as st

def apply_custom_styles():
    """
    Injects custom CSS to enlarge text for better readability on trading desks
    and adjusts the layout margins.
    """
    st.markdown("""
        <style>
        /* Increase font for all dataframes/tables */
        [data-testid="stTable"] {
            font-size: 20px !important;
        }
        [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
            font-size: 18px !important;
        }
        
        /* Increase font for sidebar labels (Asset, Option Type) */
        [data-testid="stWidgetLabel"] p {
            font-size: 24px !important;
            font-weight: bold !important;
        }
        
        /* Increase size of the general markdown text */
        .stMarkdown p {
            font-size: 20px !important;
        }

        /* Reduce top padding to give it a 'Command Center' feel */
        .block-container {
            padding-top: 2rem; 
            padding-bottom: 0rem;
        }
        
        /* Custom styling for the sentiment metric */
        [data-testid="stMetricValue"] {
            font-size: 40px !important;
        }
        [data-testid="stTable"] { font-size: 20px !important; }
        [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { font-size: 18px !important; }
        [data-testid="stWidgetLabel"] p { font-size: 24px !important; font-weight: bold !important; }
        .stMarkdown p { font-size: 20px !important; }
        .block-container { padding-top: 2rem; padding-bottom: 0rem; }
        [data-testid="stMetricValue"] { font-size: 40px !important; }        
        </style>
        """, unsafe_allow_html=True)