# Create directory structure
mkdir -p crypto-options-dashboard
cd crypto-options-dashboard
mkdir -p src/api src/models src/analyzers src/dashboard src/utils data

# Install required packages
pip install requests==2.31.0 pandas==2.1.4 numpy==2.0.0 streamlit==1.28.1 plotly==5.18.0 scipy==1.11.4 python-dotenv==1.0.0