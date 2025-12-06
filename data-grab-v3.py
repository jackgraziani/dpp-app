import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, date, timedelta
import warnings

# Suppress the specific FutureWarning related to auto_adjust default change
# warnings.simplefilter(action='ignore', category=FutureWarning)

# --- Configuration ---
TRADING_DAYS_PER_YEAR = 252
LOOKBACK_YEARS = 5
US_MARKET_CLOSE_TIME = time(16, 30)

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
        percent_change = round(dollar_change / total_portfolio_at_open, 4)
        
    return [dollar_change, percent_change]

# --- Beta Calculation ---
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
        all_tickers = [market_ticker] + portfolio_tickers
        
        data = yf.download(
            all_tickers, 
            start=start_date, 
            end=end_date, 
            progress=False, 
            auto_adjust=False
        )['Close']
        
        mkt_returns = data[market_ticker].pct_change()
        
        if portfolio_tickers:
            port_returns = data[portfolio_tickers].pct_change().mean(axis=1)
        else:
            return 1.0 

        combined_returns = pd.DataFrame({
            'Portfolio_Return': port_returns,
            'Market_Return': mkt_returns
        }).dropna()
        
        if len(combined_returns) < 126: # ~6 months
            return 1.0 

        regression_results = np.polyfit(
            combined_returns['Market_Return'], 
            combined_returns['Portfolio_Return'], 
            1
        )
        
        return regression_results[0]

    except Exception as e:
        print(f"Error during Beta calculation: {e}. Defaulting to Beta = 1.0.")
        return 1.0 

def alpha(portfolio_gain, benchmark_ticker, portfolio_tickers): 
    """
    Calculates the daily Alpha of the portfolio.
    Alpha = R_p - [R_f + Beta * (R_m - R_f)]
    """
    # Calculate Daily Risk-Free Rate (R_f_Daily)
    try:
        tnx_data = return_prev_close_and_current("^TNX")
        if tnx_data:
            annual_rfr = tnx_data[1] / 100
        else:
            raise Exception("TNX data retrieval failed")
    except (TypeError, IndexError, Exception):
        annual_rfr = 0.04 # Default RFR if ^TNX fetch fails (4.00%)
        
    daily_rfr = annual_rfr / TRADING_DAYS_PER_YEAR

    portfolio_data_benchmark = {"tickers": [benchmark_ticker], "num_shares": [1]}   
    benchmark_gain = run_calcs(portfolio_data_benchmark)[1]
    
    beta = calculate_beta(portfolio_tickers, benchmark_ticker, LOOKBACK_YEARS)

    daily_alpha = portfolio_gain - (daily_rfr + beta * (benchmark_gain - daily_rfr))

    return daily_alpha

def get_last_updated_time(reference_ticker):
    """
    Determines the last update time based on the market data availability, 
    returning the specific date formatted as MM/DD/YY.
    """
    from datetime import datetime, time
    
    US_MARKET_CLOSE_TIME = time(16, 30) 
    
    try:
        ref_ticker = yf.Ticker(reference_ticker)
        ref_info = ref_ticker.info
        
        market_timestamp = ref_info.get('regularMarketTime') 
        current_datetime = datetime.now()
        
        current_date_str = current_datetime.strftime("%m/%d/%y") 
        current_time_str = current_datetime.strftime("%I:%M%p").replace(" 0", " ")
        
        if market_timestamp:
            data_datetime = datetime.fromtimestamp(market_timestamp)
            data_date_str = data_datetime.strftime("%m/%d/%y")
            
            if data_datetime.date() == current_datetime.date() and current_datetime.time() < US_MARKET_CLOSE_TIME:
                return f"{current_time_str} on {current_date_str}" 
            else:
                if current_datetime.time() >= US_MARKET_CLOSE_TIME and data_datetime.date() == current_datetime.date():
                    return f"4:30PM on {data_date_str}"
                return f"4:30PM on {data_date_str}"

        return f"{current_time_str} on {current_date_str} (Live Run Fallback)"
        
    except Exception as e:
        current_datetime = datetime.now()
        current_date_str = current_datetime.strftime("%m/%d/%y")
        current_time_str = current_datetime.strftime("%I:%M%p").replace(" 0", " ")
        print(f"Error fetching market time: {e}. Defaulting to current time.")
        return f"{current_time_str} on {current_date_str} (Error Fallback)"

# --- NEW: Backtest Function ---
def backtest_portfolio(portfolio_data, benchmark_ticker="^GSPC", lookback_years=LOOKBACK_YEARS):
    """
    Backtests the given portfolio over the specified lookback period.

    Assumptions:
    - Static portfolio: number of shares is constant over the period.
    - Weights are based on current market prices (approximate).
    
    Returns:
        dict with:
        - 'portfolio_cum_return': cumulative portfolio return over the period
        - 'benchmark_cum_return': cumulative benchmark return over the period
        - 'alpha_cum': cumulative alpha = portfolio_cum_return - benchmark_cum_return
    """
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    
    if not tickers:
        raise ValueError("Portfolio is empty. Provide at least one ticker.")

    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=lookback_years)

    # Download price history for benchmark + all portfolio tickers
    all_tickers = [benchmark_ticker] + tickers
    data = yf.download(
        all_tickers,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=False
    )["Close"]

    # Drop rows with all NaNs
    data = data.dropna(how="all")

    # Separate benchmark and portfolio prices
    benchmark_prices = data[benchmark_ticker].dropna()

    # Align portfolio prices to benchmark's date index
    port_prices = data[tickers].reindex(benchmark_prices.index).dropna(how="all")

    # If some days are missing for some tickers, forward-fill
    port_prices = port_prices.ffill().dropna(how="all")

    # Re-align benchmark to final portfolio index
    benchmark_prices = benchmark_prices.reindex(port_prices.index)

    # Portfolio value each day: sum(shares_i * price_i)
    shares_series = pd.Series(num_shares, index=tickers)
    portfolio_values = (port_prices * shares_series).sum(axis=1)

    # Cumulative returns:
    portfolio_cum_return = portfolio_values.iloc[-1] / portfolio_values.iloc[0] - 1.0
    benchmark_cum_return = benchmark_prices.iloc[-1] / benchmark_prices.iloc[0] - 1.0

    alpha_cum = portfolio_cum_return - benchmark_cum_return

    return {
        "portfolio_cum_return": portfolio_cum_return,
        "benchmark_cum_return": benchmark_cum_return,
        "alpha_cum": alpha_cum,
        "start_date": portfolio_values.index[0],
        "end_date": portfolio_values.index[-1],
    }

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
    
    if not portfolio_data["tickers"]:
        print("No input detected. Running with hardcoded example portfolio.")
        portfolio_data = {"tickers": ["BKR", "CF", "MRK", "PINS"], "num_shares": [11, 11, 11, 11]}

    # --- Run Daily Calculations ---
    raw_equity_output = run_calcs(portfolio_data)
    
    dollar_change = raw_equity_output[0]
    percent_change = raw_equity_output[1]
    
    if dollar_change < 0:
        formatted_equity_output = [
            "-$" + str(abs(dollar_change)),
            "-" + str(round(abs(percent_change)*100, 2)) + "%"
        ]
    else:
        formatted_equity_output = [
            "+$" + str(dollar_change),
            "+" + str(round(percent_change*100, 2)) + "%"
        ]
   
    benchmark_ticker = "^GSPC"
    portfolio_gain = percent_change
    portfolio_tickers = portfolio_data["tickers"] 
    
    raw_alpha = alpha(portfolio_gain, benchmark_ticker, portfolio_tickers)
    if raw_alpha < 0:
        formatted_alpha = "-" + str(round(abs(raw_alpha)*100, 2)) + "%" 
    else:
        formatted_alpha = "+" + str(round(raw_alpha*100, 2)) + "%"

    # --- Run Backtest ---
    backtest_results = backtest_portfolio(portfolio_data, benchmark_ticker)
    port_cum = backtest_results["portfolio_cum_return"]
    bench_cum = backtest_results["benchmark_cum_return"]
    alpha_cum = backtest_results["alpha_cum"]

    # Format as percentages
    port_cum_str = f"{port_cum*100:.2f}%"
    bench_cum_str = f"{bench_cum*100:.2f}%"
    alpha_cum_str = f"{alpha_cum*100:.2f}%"

    last_updated = get_last_updated_time("SPY")
    print("====================")
    print(f"Last updated: {last_updated}")
    print()
    print(f"[Daily] Portfolio Return: {formatted_equity_output[1]} ({formatted_equity_output[0]})")
    print(f"[Daily] Alpha Generated: {formatted_alpha}")
    print()
    print(f"[Backtest {LOOKBACK_YEARS}y] Portfolio Cumulative Return: {port_cum_str}")
    print(f"[Backtest {LOOKBACK_YEARS}y] S&P 500 Cumulative Return:  {bench_cum_str}")
    print(f"[Backtest {LOOKBACK_YEARS}y] Cumulative Alpha:           {alpha_cum_str}")
    print("====================")
if __name__ == "__main__":
    main()