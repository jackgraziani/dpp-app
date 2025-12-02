import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

# TODO: robust error catching (i.e., file doesn't break down when can't find the data)

# --- Configuration ---
def return_open_and_current(ticker_string):
    open_and_current = []
    MARKET_OPEN_TIME = '09:30:00'
    ticker = yf.Ticker(ticker_string)
    data = ticker.history(interval="1m", period="1d")

    if data.empty:
        print("Error: Could not retrieve data.")
    else:
        # Define Timezone and Target Time
        eastern = pytz.timezone('US/Eastern') 

        # Create a timezone-aware datetime object for 9:30 AM today
        today_date_str = datetime.now().strftime('%Y-%m-%d')
        naive_dt_open = datetime.strptime(f'{today_date_str} {MARKET_OPEN_TIME}', '%Y-%m-%d %H:%M:%S')
        
        # Make it timezone-aware (matching the data index)
        target_dt_open_aware = eastern.localize(naive_dt_open)

        # 3. Get the 9:30 AM Price using direct index lookup
        try:
            # Direct lookup (which relies on the index being timezone-aware)
            price_at_open = data.loc[target_dt_open_aware, 'Close']
            open_and_current.append(round(float(price_at_open), 2))
            
        except KeyError:
            print("\nCould not find exact 9:30 AM price. Market may not be open yet or data is missing.")

        # 4. Get the Current Price (This part remains the same)
        current_price = data['Close'].iloc[-1]
        last_update_time = data.index[-1].strftime('%H:%M:%S')
        open_and_current.append(round(float(current_price), 2))
        return(open_and_current)
    
def run_calcs(portfolio_data):
    tickers = portfolio_data["tickers"]
    num_shares = portfolio_data["num_shares"]
    price_data = []
    
    for ticker in portfolio_data["tickers"]:
        price_data.append(return_open_and_current(ticker))
    
    total_portfolio_at_open = 0
    for i in range(len(tickers)):
        total_portfolio_at_open += num_shares[i]*price_data[i][0]

    total_portfolio_current = 0
    for i in range(len(tickers)):
        total_portfolio_current += num_shares[i]*price_data[i][1]

    
    dollar_change = round(total_portfolio_current - total_portfolio_at_open, 2)
    percent_change =  round(dollar_change / total_portfolio_at_open, 4)
    return (dollar_change, percent_change)



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
        


    #portfolio_data = {"tickers": ["MRK", "PINS", "BKR", "CF"], "num_shares": [11, 11, 11, 11]}
    raw_output = run_calcs(portfolio_data)
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