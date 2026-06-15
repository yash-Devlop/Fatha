import os, sys
from Managers.account_manager import AccountManager
from Managers.costing_manager import CostingManager

client_save_dir        = "C:\\Fatha\\data\\client\\clients.csv"
ledger_save_dir        = "C:\\Fatha\\data\\ledger"
owner_data_dir         = "C:\\Fatha\\data\\owner.csv"
products_data_dir      = "C:\\Fatha\\data\\products\\products.csv"
client_rates_data_dir  = "C:\\Fatha\\data\\products\\client_rates.csv"
temp_bill_data         = "C:\\Fatha\\data\\bill_data\\temp\\temp_bills.json"
performa_bill_data     = "C:\\Fatha\\data\\bill_data\\temp\\performa_bills.json"
permanent_bill_data    = "C:\\Fatha\\data\\bill_data\\permanent\\bills.json"
costing_data_dir       = "C:\\Fatha\\data\\costing"
log_path               = "C:\\Fatha\\logs\\logs.log"

acc_manager = AccountManager(
    client_save_dir, ledger_save_dir, owner_data_dir,
    products_data_dir, client_rates_data_dir,
    temp_bill_data, performa_bill_data, permanent_bill_data
)

costing_manager = CostingManager(costing_data_dir)

state_code_map = {
    "Andhra Pradesh": "28", "Arunachal Pradesh": "12", "Assam": "18",
    "Bihar": "10", "Chhattisgarh": "22", "Goa": "30", "Gujarat": "24",
    "Haryana": "06", "Himachal Pradesh": "02", "Jharkhand": "20",
    "Karnataka": "29", "Kerala": "32", "Madhya Pradesh": "23",
    "Maharashtra": "27", "Manipur": "14", "Meghalaya": "17",
    "Mizoram": "15", "Nagaland": "13", "Odisha": "21", "Punjab": "03",
    "Rajasthan": "08", "Sikkim": "11", "Tamil Nadu": "33",
    "Telangana": "36", "Tripura": "16", "Uttar Pradesh": "09",
    "Uttarakhand": "05", "West Bengal": "19",
    "Andaman & Nicobar Islands": "35", "Chandigarh": "04",
    "Dadra & Nagar Haveli and Daman & Diu": "26", "Delhi": "07",
    "Jammu & Kashmir": "01", "Ladakh": "38",
    "Lakshadweep": "31", "Puducherry": "34",
}


def get_bridge_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "Share_executable", "ShareBridge.exe")
    return os.path.abspath(os.path.join("Share_executable", "ShareBridge.exe"))
