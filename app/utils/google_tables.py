import configparser

import gspread

# Config
conf = configparser.ConfigParser()
conf.read("config/config.ini")
# GoogleTables
# Open a sheet from a spreadsheet in one go
gc = gspread.service_account(filename="./config/google-service-account-key.json")
sh = gc.open_by_key(conf["google"]["spreadsheet"])
users_wks = sh.get_worksheet(0)
try:
    promo_wks = sh.get_worksheet(1)
except gspread.WorksheetNotFound:
    promo_wks = sh.add_worksheet("Promocodes", 0, 4, index=1)
