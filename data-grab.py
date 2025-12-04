import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
import numpy as np

# TODO: robust error catching (i.e., file doesn't break down when can't find the data)

# --- Configuration ---
TRADING_DAYS_PER_YEAR = 252
LOOKBACK_YEARS = 5

def return_prev_close_and_current(ticker_string):
    """
    Retrieves the previous day's close price and the current price for a given ticker.

    Args:
        ticker_string (str): The stock ticker symbol (e.g., 'AAPL', 'GOOGL').

    Returns:
        list: A list containing [previous_close_price, current_price],
              or None if data retrieval fails.
    """
    prices = []
    ticker = yf.Ticker(ticker_string)
    daily_data = None # Initialize to handle scope

    # --- 1. Get the official Previous Close Price ---
    # Retrieve 2 days of daily data (1d interval) to ensure we get the 
    # row corresponding to the previous trading day's close.
    # We use 'period="2d"' to get *up to* the last two daily records.
    try:
        daily_data = ticker.history(interval="1d", period="2d", auto_adjust=False)
    except Exception as e:
        print(f"Error retrieving daily history for {ticker_string}: {e}")
        return None

    # Check for sufficient daily data
    if daily_data.empty or len(daily_data) < 2:
        print(f"Error: Could not retrieve sufficient daily data for {ticker_string}.")
        return None
        
    # The 'Close' price of the **second-to-last** row (index -2) is the 
    # official previous day's close price.
    try:
        previous_close = daily_data.iloc[-2]['Close']
        # Added precision handling for ^TNX
        precision = 4 if ticker_string == "^TNX" else 2 
        prices.append(round(float(previous_close), precision))
    except IndexError:
        print(f"Error: Insufficient data points to determine previous close for {ticker_string}.")
        return None


    # --- 2. Get the Current Price (Using .info for best result) ---
    current_price = None
    try:
        current_data = ticker.info
        
        # Priority 1: Use 'regularMarketPrice' as it's often the most recent price,
        # including after-hours/pre-market if the market is closed.
        current_price = current_data.get('regularMarketPrice')

        # Priority 2: Fallback to 'currentPrice'
        if current_price is None or current_price == 0:
            current_price = current_data.get('currentPrice')
            
        # If both attempts failed, fall through to the minute/daily history fallback
        if current_price is None or current_price == 0:
             raise ValueError("Primary .info keys returned invalid data.")
             
    except Exception:
        # Fallback to the historical method if .info fails or returns bad data
        print(f"Warning: .info failed or was incomplete for {ticker_string}. Falling back to minute/daily data.")
        
        # Try 1-minute data for the latest minute close
        minute_data = ticker.history(interval="1m", period="1d", auto_adjust=False)
        
        if minute_data.empty:
            # Final Fallback: The latest available daily Close price
            current_price = daily_data.iloc[-1]['Close'] 
        else:
            # Use Adj Close from the 1m data for the latest price
            current_price = minute_data['Adj Close'].iloc[-1]
    
    # Check if a price was successfully retrieved
    if current_price is None or current_price == 0:
        print(f"Critical Error: Failed to retrieve current price for {ticker_string}.")
        return None
    
    precision = 4 if ticker_string == "^TNX" else 2
    prices.append(round(float(current_price), precision))
    
    return prices
    
def run_calcs(portfolio_data):

    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    price_data = []
    
    for ticker in portfolio_data["tickers"]:
        price_data.append(return_prev_close_and_current(ticker))
    
    # Simple check to prevent errors downstream if data is None
    if any(p is None for p in price_data):
        return [0, 0] # Return 0 gain

    total_portfolio_at_open = 0
    for i in range(len(tickers)):
        total_portfolio_at_open += num_shares[i]*price_data[i][0]

    total_portfolio_current = 0
    for i in range(len(tickers)):
        total_portfolio_current += num_shares[i]*price_data[i][1]
    
    dollar_change = round(total_portfolio_current - total_portfolio_at_open, 2)
    
    if total_portfolio_at_open == 0:
        percent_change = 0
    else:
        percent_change =  round(dollar_change / total_portfolio_at_open, 4)
        
    return [dollar_change, percent_change]

# --- NEW REQUIRED FUNCTION TO CALCULATE BETA (the 1D vector requirement) ---
def calculate_beta(portfolio_tickers, market_ticker, lookback_years):
    """
    Calculates the Beta of the portfolio using historical daily returns 
    over a specified lookback period (e.g., 5 years).
    """
    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=lookback_years)
    
    try:
        # 1. Fetch Market Returns Series (^GSPC)
        mkt_data = yf.download(market_ticker, start=start_date, end=end_date, progress=False)['Close']
        mkt_returns = mkt_data.pct_change()

        # 2. Fetch Portfolio Component Data and calculate simple average return
        port_data_list = []
        for ticker in portfolio_tickers:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)['Close']
            port_data_list.append(df.rename(ticker))

        port_prices = pd.concat(port_data_list, axis=1, join='inner')
        port_returns = port_prices.pct_change().mean(axis=1)

        # 3. Merge returns and calculate Beta
        combined_returns = pd.DataFrame({
            'Portfolio_Return': port_returns,
            'Market_Return': mkt_returns
        }).dropna()
        
        if len(combined_returns) < 252: # Need at least 1 year of data
             return 1.0 # Default to 1.0 if data is too sparse

        # np.polyfit requires 1D vector input (the historical return series)
        # The slope (Beta) is returned at index 0
        regression_results = np.polyfit(
            combined_returns['Market_Return'], 
            combined_returns['Portfolio_Return'], 
            1
        )
        
        return regression_results[0] 

    except Exception:
        # Returns 1.0 if any data fetching or calculation fails
        return 1.0 

# --- END NEW REQUIRED FUNCTION ---

def alpha(portfolio_gain, benchmark_ticker, portfolio_tickers): # Added portfolio_tickers argument
    
    # Calculate RFR
    try:
        annual_rfr = (return_prev_close_and_current("^TNX")[1])/100
    except (TypeError, IndexError):
        annual_rfr = 0.04 # Default RFR if ^TNX fetch fails
        
    daily_rfr = annual_rfr / TRADING_DAYS_PER_YEAR

    # Get the benchmark's daily gain (R_m_Daily)
    portfolio_data_benchmark = {"tickers": [benchmark_ticker], "num_shares": [1]}   
    benchmark_gain = run_calcs(portfolio_data_benchmark)[1]
    
    # FIX: Calculate Beta using the new function which fetches the historical 1D vector
    # This returns a scalar (single number) for Beta.
    beta = calculate_beta(portfolio_tickers, benchmark_ticker, LOOKBACK_YEARS)

    # Daily Alpha formula uses the scalar beta
    daily_alpha = portfolio_gain - (daily_rfr + beta * (benchmark_gain - daily_rfr))

    return daily_alpha

def main():
    portfolio_data = {"tickers": [], "num_shares": []}
    still_asking = True
    while still_asking:
        ticker = input('enter a ticker ("!" to stop): ').upper()
        if ticker != "!":
            num_shares = int(input("How many shares: "))
            portfolio_data["tickers"].append(ticker)
            portfolio_data["num_shares"].append(num_shares)
        else:
            still_asking = False
        

    portfolio_data = {"tickers": ["BKR", "CF", "MRK", "PINS"], "num_shares": [11, 11, 11, 11]}

    raw_equity_output = run_calcs(portfolio_data)
    formatted_equity_output = []
    
    if raw_equity_output[0] < 0:
        formatted_equity_output.append("-$" + str(raw_equity_output[0])[1:])
        formatted_equity_output.append("-"+str(round(raw_equity_output[1]*100, 4))[1:]+"%") 
    else:
        formatted_equity_output.append("+$" + str(raw_equity_output[0]))
        formatted_equity_output.append("+"+str(round(raw_equity_output[1]*100, 4))+"%")
   
    benchmark_ticker = "^GSPC" # S&P 500.
    portfolio_gain = raw_equity_output[1]
    portfolio_tickers = portfolio_data["tickers"] # Needed for Beta calculation
    
    
    print(formatted_equity_output)
    # FIX: Pass the portfolio tickers to the alpha function
    print(alpha(portfolio_gain, benchmark_ticker, portfolio_tickers)) 
if __name__ == "__main__":
    main()