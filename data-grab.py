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

def return_open_and_current(ticker_string):
    open_and_current = []
    
    ticker = yf.Ticker(ticker_string)
    # Requesting 1-day, 1-minute interval data
    data = ticker.history(interval="1m", period="1d")

    if data.empty:
        print(f"Error: Could not retrieve data for {ticker_string}.")
        return None # Return None or handle error as needed
    else:
        # --- 1. Get the 9:30 AM Opening Price (More Robust Method) ---
        try:
            # The first row (index 0) of the 1-minute data for the current day
            # is typically the 9:30 AM bar. We use the 'Open' price 
            # as it represents the official price at 9:30:00 AM.
            price_at_open = data.iloc[0]['Open']
            
            # Optional: Check the timestamp to confirm it's 9:30 AM
            first_timestamp = data.index[0]
            if first_timestamp.tz_localize(None).time().strftime('%H:%M:%S') != '09:30:00':
                 print(f"Warning: First data point for {ticker_string} is at {first_timestamp.time().strftime('%H:%M:%S')}, not 09:30:00.")

            open_and_current.append(round(float(price_at_open), 2))
            
        except IndexError:
            # This can happen if the market hasn't opened yet and the DataFrame is empty/incomplete
            print(f"\nCould not find 9:30 AM price for {ticker_string}. Market may not be open yet.")
            return None # Return None or handle error as needed

        # --- 2. Get the Current Price (remains the same) ---
        current_price = data['Close'].iloc[-1]
        # last_update_time = data.index[-1].strftime('%H:%M:%S') # Retaining for reference
        open_and_current.append(round(float(current_price), 2))
        
        return open_and_current
    
def run_calcs(portfolio_data):
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    price_data = []
    
    for ticker in portfolio_data["tickers"]:
        price_data.append(return_open_and_current(ticker))
    
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
    raw_output_dirty = run_calcs(portfolio_data) # might do 0.8999999 instead of 0.90
    raw_output = [raw_output_dirty[0], round(raw_output_dirty[1], 4)]
    formatted_output = []
    if raw_output[0] < 0:
        formatted_output.append("-$" + str(raw_output[0])[1:])
        formatted_output.append("-"+str(raw_output[1]*100)[1:]+"%") 
    else:
        formatted_output.append("+$" + str(raw_output[0]))
        formatted_output.append("+"+str(raw_output[1]*100)+"%")
   
    for data_point in formatted_output:
        print(data_point)

if __name__ == "__main__":
    main()