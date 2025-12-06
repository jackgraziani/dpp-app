import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def backtest_portfolio(portfolio_data, period_years=5):
    """
    Backtests the portfolio over a specified number of years.
    
    Parameters:
    - portfolio_data: Dict with keys "tickers" (list of str) and "num_shares" (list of int/float)
    - period_years: Integer number of years to look back (default 5)
    
    Returns:
    - backtested_alpha: The Jensen's Alpha of the portfolio over the period (in percent format, e.g., 5.5 for 5.5%)
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
        # Use 'Adj Close' to account for dividends/splits over the long term
        raw_data = yf.download(download_list, start=start_date, end=end_date, progress=False, auto_adjust=False)
        price_data = raw_data['Close']
        
        # Clean data: Drop rows where the benchmark or any stock is NaN (simulate 'common trading days')
        price_data = price_data.dropna()
        
        if price_data.empty:
            print("Error: No overlapping data found for these tickers in the given period.")
            return None

    except Exception as e:
        print(f"Backtest Data Error: {e}")
        return None

    # 3. Calculate Portfolio Value History
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
    port_daily_rets = portfolio_series.pct_change().dropna()
    bench_daily_rets = price_data[benchmark_ticker].pct_change().dropna()
    
    # Merge and align
    combined = pd.DataFrame({'Port': port_daily_rets, 'Bench': bench_daily_rets}).dropna()
    cov_matrix = np.cov(combined['Bench'], combined['Port'])
    beta_period = cov_matrix[0, 1] / cov_matrix[0, 0] 

    # 7. Calculate Jensen's Alpha (Over the period)
    # Alpha = Actual_Return - [Risk_Free + Beta * (Market_Return - Risk_Free)]
    expected_return = period_rfr + beta_period * (benchmark_total_return - period_rfr)
    alpha_period = portfolio_total_return - expected_return
    
    # Return formatted Alpha (multiplied by 100 for percentage reading)
    return 100 * round(float(alpha_period), 4)

def main():
    print(backtest_portfolio({"tickers": ['GOOGL'], "num_shares":[1]}))

if __name__ == "__main__":
    main()