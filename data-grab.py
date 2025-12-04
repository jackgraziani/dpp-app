import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

# TODO: robust error catching (i.e., file doesn't break down when can't find the data)

# --- Configuration ---
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

import yfinance as yf

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

    # --- 1. Get the official Previous Close Price ---
    # Retrieve 2 days of daily data (1d interval) to ensure we get the 
    # row corresponding to the previous trading day's close.
    # We use 'period="2d"' to get *up to* the last two daily records.
    daily_data = ticker.history(interval="1d", period="2d", auto_adjust=False)
    
    # Check if we have at least 2 rows of daily data (yesterday and today)
    if daily_data.empty or len(daily_data) < 2:
        print(f"Error: Could not retrieve sufficient daily data for {ticker_string}.")
        return None
        
    # The 'Close' price of the **second-to-last** row (index -2) is the 
    # official previous day's close price.
    # Note: If called *before* 9:30 AM EST, the last row will be yesterday's data,
    # and this will return the day before's close, which is still the correct 
    # 'Previous Close' reference value used on trading day platforms.
    try:
        previous_close = daily_data.iloc[-2]['Close']
        prices.append(round(float(previous_close), 2))
    except IndexError:
        print(f"Error: Insufficient data points to determine previous close for {ticker_string}.")
        return None


    # --- 2. Get the Current Price ---
    # Use 1-minute interval data for the current day to get the absolute latest minute price.
    minute_data = ticker.history(interval="1m", period="1d", auto_adjust=False)
    
    if minute_data.empty:
        # Fallback to the latest daily Close/Adj Close price if 1m data fails (e.g., after market close)
        # The last row ('iloc[-1]') contains the most recent available closing price.
        current_price = daily_data.iloc[-1]['Close'] 
    else:
        # Use Adj Close from the 1m data for the latest price
        current_price = minute_data['Adj Close'].iloc[-1]
        
    prices.append(round(float(current_price), 2))
    
    return prices
    
def run_calcs(portfolio_data):
    print(portfolio_data)
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    price_data = []
    
    for ticker in portfolio_data["tickers"]:
        price_data.append(return_prev_close_and_current(ticker))

    print(price_data)

    total_portfolio_at_open = 0
    for i in range(len(tickers)):
        total_portfolio_at_open += num_shares[i]*price_data[i][0]

    total_portfolio_current = 0
    for i in range(len(tickers)):
        total_portfolio_current += num_shares[i]*price_data[i][1]
    
    dollar_change = round(total_portfolio_current - total_portfolio_at_open, 2)
    percent_change =  round(dollar_change / total_portfolio_at_open, 4)
    return [dollar_change, percent_change]



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

    raw_output = run_calcs(portfolio_data)
    formatted_output = []
    if raw_output[0] < 0:
        formatted_output.append("-$" + str(raw_output[0])[1:])
        formatted_output.append("-"+str(round(raw_output[1]*100, 4))[1:]+"%") 
    else:
        formatted_output.append("+$" + str(raw_output[0]))
        formatted_output.append("+"+str(round(raw_output[1]*100, 4))+"%")
   
    return formatted_output

if __name__ == "__main__":
    print(main())