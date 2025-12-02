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

    # 1. Get the official Daily OPEN price using a 1-day interval
    daily_data = ticker.history(interval="1d", period="2d", auto_adjust=False)
    
    if daily_data.empty or len(daily_data) < 2:
        print(f"Error: Could not retrieve daily data for {ticker_string}.")
        return None
        
    # The 'Open' price of the last (today's) row is the official 9:30 AM open
    price_at_open = daily_data.iloc[-1]['Open']
    open_and_current.append(round(float(price_at_open), 2))

    # 2. Get the Current Price using the 1-minute interval data
    # (Use 1m data to ensure you get the absolute latest minute)
    minute_data = ticker.history(interval="1m", period="1d", auto_adjust=False)
    
    if minute_data.empty:
        # Fallback to daily close if 1m data fails
        current_price = daily_data.iloc[-1]['Close'] 
    else:
        # Use Adj Close from the 1m data for the latest price
        current_price = minute_data['Adj Close'].iloc[-1]
        
    open_and_current.append(round(float(current_price), 2))
    return open_and_current
    
def run_calcs(portfolio_data):
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    price_data = []
    
    for ticker in portfolio_data["tickers"]:
        price_data.append(return_open_and_current(ticker))
    
    # pene = [[50.04, price_data[0][1]], [79.83, price_data[1][1]],[101.12, price_data[2][1]],[26.91, price_data[3][1]]]
    # print("what we're looking for:", pene)
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