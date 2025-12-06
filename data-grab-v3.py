import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, date, timedelta
import warnings

# --- Configuration ---
TRADING_DAYS_PER_YEAR = 252
LOOKBACK_YEARS = 5
US_MARKET_CLOSE_TIME = time(16, 30)

def return_prev_close_and_current(ticker_string):
    """
    Retrieves the previous day's close price and the current price for a given ticker.
    """
    try:
        ticker = yf.Ticker(ticker_string)
        ticker_info = ticker.info
        
        precision = 4 if ticker_string == "^TNX" else 2

        # 1. Get Previous Close
        previous_close = ticker_info.get('previousClose')
        
        if previous_close is None or previous_close == 0:
            hist = ticker.history(interval="1d", period="2d", auto_adjust=False)
            if not hist.empty and len(hist) >= 1:
                previous_close = hist['Close'].iloc[-1]
            else:
                 return None

        # 2. Get Current Price
        current_price = ticker_info.get('regularMarketPrice')
        if current_price is None or current_price == 0:
            current_price = ticker_info.get('currentPrice')
        
        if current_price is None or current_price == 0:
            if 'hist' not in locals():
                hist = ticker.history(interval="1d", period="1d", auto_adjust=False)
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
             
        if current_price is None or current_price == 0:
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
    
    for ticker in tickers:
        price_data.append(return_prev_close_and_current(ticker))
    
    if any(p is None for p in price_data):
        print("Warning: One or more tickers failed to retrieve data. Returning 0 change.")
        return [0.00, 0.0000]

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
        percent_change =  round(dollar_change / total_portfolio_at_open, 4)
        
    return [dollar_change, percent_change]

def calculate_beta(portfolio_tickers, market_ticker, lookback_years):
    """
    Calculates the Beta of the portfolio using historical daily returns.
    """
    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=lookback_years)
    
    try:
        all_tickers = [market_ticker] + portfolio_tickers
        
        # Download historical data
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, auto_adjust=False)['Close']
        
        # Handle single ticker case (yf returns Series instead of DF if only 1 ticker)
        if isinstance(data, pd.Series):
             data = data.to_frame()

        mkt_returns = data[market_ticker].pct_change()
        
        if portfolio_tickers:
            # If multiple tickers, ensure we align columns correctly
            valid_tickers = [t for t in portfolio_tickers if t in data.columns]
            if not valid_tickers: return 1.0
            port_returns = data[valid_tickers].pct_change().mean(axis=1)
        else:
            return 1.0 

        combined_returns = pd.DataFrame({
            'Portfolio_Return': port_returns,
            'Market_Return': mkt_returns
        }).dropna()
        
        if len(combined_returns) < 126: 
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
    """
    try:
        tnx_data = return_prev_close_and_current("^TNX")
        if tnx_data:
            annual_rfr = tnx_data[1] / 100
        else:
            raise Exception("TNX data retrieval failed")
    except Exception:
        annual_rfr = 0.04 
        
    daily_rfr = annual_rfr / TRADING_DAYS_PER_YEAR
    portfolio_data_benchmark = {"tickers": [benchmark_ticker], "num_shares": [1]}   
    benchmark_gain = run_calcs(portfolio_data_benchmark)[1]
    
    beta = calculate_beta(portfolio_tickers, benchmark_ticker, LOOKBACK_YEARS)
    daily_alpha = portfolio_gain - (daily_rfr + beta * (benchmark_gain - daily_rfr))

    return daily_alpha

def get_last_updated_time(reference_ticker):
    """Returns formatted update time string."""
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
    except Exception:
        current_datetime = datetime.now()
        return f"{current_datetime.strftime('%I:%M%p')} (Error Fallback)"

# --- NEW FUNCTION: Backtest ---
def backtest_portfolio(portfolio_data, period_years):
    """
    Backtests the portfolio over a specified number of years.
    Returns Total Portfolio Return, Total Benchmark Return, and Total Alpha.
    """
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    benchmark_ticker = "^GSPC"
    rfr_ticker = "^TNX"
    
    # 1. Define Dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_years*365)
    
    # 2. Bulk Download Data (Portfolio + Benchmark + RFR)
    download_list = tickers + [benchmark_ticker, rfr_ticker]
    try:
        # We use 'Adj Close' for backtesting to account for dividends/splits over time
        raw_data = yf.download(download_list, start=start_date, end=end_date, progress=False, auto_adjust=False)
        price_data = raw_data['Close']
        
        # Clean data: Drop rows where the benchmark or any stock is NaN (simulate 'common trading days')
        price_data = price_data.dropna()
        
        if price_data.empty:
            print("Error: No overlapping data found for these tickers in the given period.")
            return

    except Exception as e:
        print(f"Backtest Data Error: {e}")
        return

    # 3. Calculate Portfolio Value History
    # Create a DataFrame to hold value of each position
    position_values = pd.DataFrame(index=price_data.index)
    
    for i, ticker in enumerate(tickers):
        if ticker in price_data.columns:
            position_values[ticker] = price_data[ticker] * num_shares[i]
            
    # Sum across rows to get total daily portfolio value
    portfolio_series = position_values.sum(axis=1)
    
    # 4. Calculate Total Returns (Cumulative for the period)
    start_val = portfolio_series.iloc[0]
    end_val = portfolio_series.iloc[-1]
    portfolio_total_return = (end_val - start_val) / start_val
    
    benchmark_start = price_data[benchmark_ticker].iloc[0]
    benchmark_end = price_data[benchmark_ticker].iloc[-1]
    benchmark_total_return = (benchmark_end - benchmark_start) / benchmark_start
    
    # 5. Calculate Average RFR for the period
    # TNX is in yield percentage (e.g., 4.5), need decimal (0.045)
    avg_rfr_annual = price_data[rfr_ticker].mean() / 100
    # De-annualize RFR for the specific period duration (simple approx)
    period_rfr = avg_rfr_annual * period_years

    # 6. Calculate Beta specific to this backtest period
    # We calculate daily returns specifically for this window to get an accurate Beta
    port_daily_rets = portfolio_series.pct_change().dropna()
    bench_daily_rets = price_data[benchmark_ticker].pct_change().dropna()
    
    # Merge and align
    combined = pd.DataFrame({'Port': port_daily_rets, 'Bench': bench_daily_rets}).dropna()
    cov_matrix = np.cov(combined['Bench'], combined['Port'])
    beta_period = cov_matrix[0, 1] / cov_matrix[0, 0] # Covariance / Variance of Market

    # 7. Calculate Jensen's Alpha (Over the period)
    # Alpha = Actual_Return - [Risk_Free + Beta * (Market_Return - Risk_Free)]
    expected_return = period_rfr + beta_period * (benchmark_total_return - period_rfr)
    alpha_period = portfolio_total_return - expected_return
    
    # --- Output ---
    #print(f"Backtest Period: {price_data.index[0].date()} to {price_data.index[-1].date()}")
    #print(f"Initial Value:   ${start_val:,.2f}")
    #print(f"Final Value:     ${end_val:,.2f}")
    #print("-" * 30)
    print(f"Portfolio Return: {portfolio_total_return:.2%}")
    print(f"S&P 500 Return:   {benchmark_total_return:.2%}")
    #print(f"Period Beta:      {beta_period:.2f}")
    print(f"Alpha Generated:  {alpha_period:.2%} (Excess return vs risk-adjusted expectation)")

    return [100*round(float(portfolio_total_return), 4),100*round(float(benchmark_total_return),4), 100*round(float(alpha_period),4)]

def main():
    # Example input section
    portfolio_data = {"tickers": [], "num_shares": []}
    
    while True:
        ticker = input('Enter a ticker ("!" to stop): ').upper()
        if ticker == "!":
            break
        try:
            val = input("How many shares: ")
            num_shares = int(val)
            portfolio_data["tickers"].append(ticker)
            portfolio_data["num_shares"].append(num_shares)
        except ValueError:
            print("Invalid input.")

    # Hardcoded fallback
    if not portfolio_data["tickers"]:
        print("\nNo input detected. Using example portfolio.")
        portfolio_data = {"tickers": ["BKR", "CF", "MRK", "PINS"], "num_shares": [11, 11, 11, 11]}

    raw_equity_output = run_calcs(portfolio_data)
    
    # Format the change output
    dollar_change = raw_equity_output[0]
    percent_change = raw_equity_output[1]
    
    if dollar_change < 0:
        formatted_equity = f"-{round(abs(percent_change)*100, 2)}% (-${abs(dollar_change)})"
    else:
        formatted_equity = f"+{round(percent_change*100, 2)}% (+${dollar_change})"
   
    # Alpha Calculation
    benchmark_ticker = "^GSPC" 
    raw_alpha = alpha(percent_change, benchmark_ticker, portfolio_data["tickers"])
    formatted_alpha = f"{raw_alpha*100:+.2f}%"
    raw_backtest_results = backtest_portfolio(portfolio_data, 5)
    formatted_backtest_results = []
    for result in raw_backtest_results:
        if result >= 0:
            formatted_backtest_results.append("+"+str(round(result, 4)))
        else:
            formatted_backtest_results.append(round(result, 4))
    print("===============")
    last_updated = get_last_updated_time("SPY")
    print(f"Last updated: {last_updated}")
    print()
    print(f"[Daily] Portfolio Return: {formatted_equity}")
    print(f"[Daily] Alpha: {formatted_alpha}")
    print()
    # --- Run Backtest Prompt ---
    print(f"[Backtest 5y] Portfolio Return: {formatted_backtest_results[0]}%")
    print(f"[Backtest 5y] Benchmark Return: {formatted_backtest_results[1]}%")
    print(f"[Backtest 5y] Alpha: {formatted_backtest_results[2]}%")
    print("===============")
if __name__ == "__main__":
    main()