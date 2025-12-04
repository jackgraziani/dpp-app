import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

# Suppress the specific FutureWarning related to auto_adjust default change
# We address the root cause below by setting auto_adjust=False, but this is a safeguard
#warnings.simplefilter(action='ignore', category=FutureWarning)

# --- Configuration ---
TRADING_DAYS_PER_YEAR = 252
LOOKBACK_YEARS = 5

def return_prev_close_and_current(ticker_string):
    """
    Retrieves the previous day's close price and the current price for a given ticker.
    Uses yfinance's .info attribute for robust and quick access to current pricing.

    Args:
        ticker_string (str): The stock ticker symbol (e.g., 'AAPL', 'GOOGL').

    Returns:
        list: A list containing [previous_close_price, current_price],
              or None if data retrieval fails.
    """
    try:
        ticker = yf.Ticker(ticker_string)
        ticker_info = ticker.info
        
        # Determine precision for output
        precision = 4 if ticker_string == "^TNX" else 2

        # 1. Get Previous Close Price (Most reliable from .info)
        previous_close = ticker_info.get('previousClose')
        
        # Fallback for previous close if .info is incomplete
        if previous_close is None or previous_close == 0:
            hist = ticker.history(interval="1d", period="2d", auto_adjust=False)
            if not hist.empty and len(hist) >= 1:
                # Use the last available daily close as the previous close
                previous_close = hist['Close'].iloc[-1]
            else:
                 print(f"Error: Could not retrieve previous close for {ticker_string}.")
                 return None

        # 2. Get Current Price
        # Prioritize regularMarketPrice, then currentPrice
        current_price = ticker_info.get('regularMarketPrice')
        if current_price is None or current_price == 0:
            current_price = ticker_info.get('currentPrice')
        
        # Final fallback: use the last available daily close
        if current_price is None or current_price == 0:
            print(f"Warning: Current price for {ticker_string} not found in .info. Using the last available close.")
            if 'hist' not in locals(): # Check if we already fetched history above
                hist = ticker.history(interval="1d", period="1d", auto_adjust=False)
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
             
        if current_price is None or current_price == 0:
            print(f"Critical Error: Failed to retrieve current price for {ticker_string}.")
            return None

        return [
            round(float(previous_close), precision), 
            round(float(current_price), precision)
        ]

    except Exception as e:
        print(f"General error retrieving data for {ticker_string}: {e}")
        return None

def run_calcs(portfolio_data):
    """
    Calculates the dollar and percent change for the entire portfolio 
    between the previous close and the current price.
    """
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    price_data = []
    
    # Error catching for all data retrieval
    for ticker in tickers:
        price_data.append(return_prev_close_and_current(ticker))
    
    # Check if any necessary data failed to retrieve
    if any(p is None for p in price_data):
        print("Warning: One or more tickers failed to retrieve data. Returning 0 change.")
        return [0.00, 0.0000] # Return 0 gain

    total_portfolio_at_open = 0
    for i in range(len(tickers)):
        # Ensure price_data[i] is not None before accessing elements
        if price_data[i]:
            total_portfolio_at_open += num_shares[i] * price_data[i][0]

    total_portfolio_current = 0
    for i in range(len(tickers)):
        if price_data[i]:
            total_portfolio_current += num_shares[i] * price_data[i][1]
    
    dollar_change = round(total_portfolio_current - total_portfolio_at_open, 2)
    
    if total_portfolio_at_open == 0:
        percent_change = 0.0000
    else:
        percent_change =  round(dollar_change / total_portfolio_at_open, 4)
        
    return [dollar_change, percent_change]

# --- Beta Calculation (Improved Efficiency and Warning Fix) ---
def calculate_beta(portfolio_tickers, market_ticker, lookback_years):
    """
    Calculates the Beta of the portfolio using historical daily returns 
    over a specified lookback period (e.g., 5 years).
    Uses a single download call for efficiency and explicitly sets auto_adjust=False
    to avoid the FutureWarning.
    """
    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=lookback_years)
    
    try:
        # 1. Fetch all data in one request for alignment and speed
        all_tickers = [market_ticker] + portfolio_tickers
        
        # FIX: Explicitly set auto_adjust=False to suppress the FutureWarning
        data = yf.download(all_tickers, 
                           start=start_date, 
                           end=end_date, 
                           progress=False, 
                           auto_adjust=False)['Close']
        
        # 2. Calculate Returns
        mkt_returns = data[market_ticker].pct_change()
        
        # Calculate simple average return across all portfolio components
        if portfolio_tickers:
            port_returns = data[portfolio_tickers].pct_change().mean(axis=1)
        else:
            return 1.0 # Default if no stocks are in the portfolio 

        # 3. Merge returns and calculate Beta
        combined_returns = pd.DataFrame({
            'Portfolio_Return': port_returns,
            'Market_Return': mkt_returns
        }).dropna()
        
        if len(combined_returns) < 126: # Requires at least ~6 months of data (half a year)
             return 1.0 # Default to 1.0 if data is too sparse

        # The slope (Beta) is returned at index 0
        regression_results = np.polyfit(
            combined_returns['Market_Return'], 
            combined_returns['Portfolio_Return'], 
            1
        )
        
        return regression_results[0] 

    except Exception as e:
        print(f"Error during Beta calculation: {e}. Defaulting to Beta = 1.0.")
        return 1.0 

# --- End Beta Calculation ---

def alpha(portfolio_gain, benchmark_ticker, portfolio_tickers): 
    """
    Calculates the daily Alpha of the portfolio.
    Alpha = R_p - [R_f + Beta * (R_m - R_f)]
    """
    
    # Calculate Daily Risk-Free Rate (R_f_Daily)
    try:
        # Get the current yield for ^TNX (10-Year Treasury Yield) and convert to decimal
        tnx_data = return_prev_close_and_current("^TNX")
        if tnx_data:
            annual_rfr = tnx_data[1] / 100
        else:
            raise Exception("TNX data retrieval failed")
    except (TypeError, IndexError, Exception):
        annual_rfr = 0.04 # Default RFR if ^TNX fetch fails (4.00%)
        
    daily_rfr = annual_rfr / TRADING_DAYS_PER_YEAR

    # Get the benchmark's daily gain (R_m_Daily)
    portfolio_data_benchmark = {"tickers": [benchmark_ticker], "num_shares": [1]}   
    benchmark_gain = run_calcs(portfolio_data_benchmark)[1]
    
    # Calculate Beta using the historical return series
    beta = calculate_beta(portfolio_tickers, benchmark_ticker, LOOKBACK_YEARS)

    # Daily Alpha formula (Jensen's Alpha adapted for daily calculation)
    # R_p = portfolio_gain (which is the daily percentage return, R_p_Daily)
    daily_alpha = portfolio_gain - (daily_rfr + beta * (benchmark_gain - daily_rfr))

    return daily_alpha

def main():
    # Example input section
    portfolio_data = {"tickers": [], "num_shares": []}
    still_asking = True
    while still_asking:
        ticker = input('Enter a ticker ("!" to stop): ').upper()
        if ticker != "!":
            try:
                num_shares = int(input("How many shares: "))
                portfolio_data["tickers"].append(ticker)
                portfolio_data["num_shares"].append(num_shares)
            except ValueError:
                print("Invalid number of shares. Please enter an integer.")
        else:
            still_asking = False
    
    # If no data was entered, use the hardcoded example data
    if not portfolio_data["tickers"]:
        print("No input detected. Running with hardcoded example portfolio.")
        portfolio_data = {"tickers": ["BKR", "CF", "MRK", "PINS"], "num_shares": [11, 11, 11, 11]}

    # --- Run Calculations ---
    raw_equity_output = run_calcs(portfolio_data)
    formatted_equity_output = []
    
    # Format the change output
    dollar_change = raw_equity_output[0]
    percent_change = raw_equity_output[1]
    
    if dollar_change < 0:
        formatted_equity_output.append("-$" + str(abs(dollar_change)))
        formatted_equity_output.append("-"+str(round(abs(percent_change)*100, 2))+"%") 
    else:
        formatted_equity_output.append("+$" + str(dollar_change))
        formatted_equity_output.append("+"+str(round(percent_change*100, 2))+"%")
   
    # --- Run Alpha Calculation ---
    benchmark_ticker = "^GSPC" # S&P 500.
    portfolio_gain = percent_change
    portfolio_tickers = portfolio_data["tickers"] 
    
    raw_alpha = alpha(portfolio_gain, benchmark_ticker, portfolio_tickers)
    if raw_alpha < 0:
        formatted_alpha = "-"+str(round((abs(raw_alpha)*100), 2))+"%" 
    else:
        formatted_alpha = "+"+str(round((raw_alpha*100), 2))+"%"


    print(f"[Daily] Potfolio Return: {formatted_equity_output[1]} ({formatted_equity_output[0]})")
    print(f"[Daily] Alpha Generated: {formatted_alpha}")

if __name__ == "__main__":
    main()