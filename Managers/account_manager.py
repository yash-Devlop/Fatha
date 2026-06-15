import os
import pandas as pd
import json
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from logger import AppLogger


# ── state_code_map ────────────────────────────────────────────────────────────
state_code_map = {
    "Andaman and Nicobar Islands": "35",
    "Andhra Pradesh":              "37",
    "Arunachal Pradesh":           "12",
    "Assam":                       "18",
    "Bihar":                       "10",
    "Chandigarh":                  "04",
    "Chhattisgarh":                "22",
    "Dadra and Nagar Haveli and Daman and Diu": "26",
    "Delhi":                       "07",
    "Goa":                         "30",
    "Gujarat":                     "24",
    "Haryana":                     "06",
    "Himachal Pradesh":            "02",
    "Jammu and Kashmir":           "01",
    "Jharkhand":                   "20",
    "Karnataka":                   "29",
    "Kerala":                      "32",
    "Ladakh":                      "38",
    "Lakshadweep":                 "31",
    "Madhya Pradesh":              "23",
    "Maharashtra":                 "27",
    "Manipur":                     "14",
    "Meghalaya":                   "17",
    "Mizoram":                     "15",
    "Nagaland":                    "13",
    "Odisha":                      "21",
    "Puducherry":                  "34",
    "Punjab":                      "03",
    "Rajasthan":                   "08",
    "Sikkim":                      "11",
    "Tamil Nadu":                  "33",
    "Telangana":                   "36",
    "Tripura":                     "16",
    "Uttar Pradesh":               "09",
    "Uttarakhand":                 "05",
    "West Bengal":                 "19",
}

class AccountManager(AppLogger):
    def __init__(self, client_save_dir, ledger_save_dir, owner_data_dir,
                 products_data_dir, client_rates_data_dir,
                 temp_bill_data, performa_bill_data, permanent_bill_data):
        super().__init__()
        self.client_save_dir        = client_save_dir
        self.ledger_save_dir        = ledger_save_dir
        self.owner_data_dir         = owner_data_dir
        self.products_data_dir      = products_data_dir
        self.client_rates_data_dir  = client_rates_data_dir
        self.temp_bill_data         = temp_bill_data
        self.performa_bill_data = performa_bill_data
        self.permanent_bill_data    = permanent_bill_data

        self._deleted_products_path = os.path.join(
            os.path.dirname(products_data_dir), "deleted_product_ids.json"
        )

        self.owner_exists  = False
        self.owner_data    = {}
        self.client_data   = pd.DataFrame()
        self.products_data = pd.DataFrame()
        self.client_rates_data = pd.DataFrame()

        self.InitializeAccount()
        self.load_data()

    def _load_deleted_product_ids(self) -> set:
        if not os.path.exists(self._deleted_products_path):
            return set()
        try:
            with open(self._deleted_products_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()

    def _save_deleted_product_ids(self, ids: set) -> None:
        try:
            os.makedirs(os.path.dirname(self._deleted_products_path), exist_ok=True)
            with open(self._deleted_products_path, "w", encoding="utf-8") as f:
                json.dump(sorted(ids), f, indent=2)
        except Exception as e:
            self.error(f"Error saving deleted product IDs: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    #  INITIALISATION / LOAD
    # ──────────────────────────────────────────────────────────────────────────

    def load_data(self):
        """Reload all CSV data from disk into memory."""
        if os.path.exists(self.client_save_dir):
            self.client_data = pd.read_csv(
                self.client_save_dir,
                dtype={
                    "Mobile": str, "AltMobile": str, "Pincode": str,
                    "GST": str, "StateCode": str, "Account_no": str,
                }
            )
        else:
            self.client_data = pd.DataFrame()

        if os.path.exists(self.products_data_dir):
            self.products_data = pd.read_csv(
                self.products_data_dir, dtype={"HSN": str, "Rate": str}
            )
        else:
            self.products_data = pd.DataFrame()

        if os.path.exists(self.client_rates_data_dir):
            self.client_rates_data = pd.read_csv(self.client_rates_data_dir)
        else:
            self.client_rates_data = pd.DataFrame()

    def InitializeAccount(self):
        if not os.path.exists(self.owner_data_dir):
            return
        owner_data = pd.read_csv(self.owner_data_dir)
        if len(owner_data) == 1:
            self.owner_data  = {
                k: ("" if pd.isna(v) else v)
                for k, v in owner_data.iloc[0].to_dict().items()
            }
            self.owner_exists = True

    def owner_name(self) -> str:
        return self.owner_data.get("Company", "") if self.owner_data else ""

    def initialize_account_data(self, company, mobile, email, gst, address,
                                state, bank, account, ifsc, cin, pincode):
        try:
            owner_data = {
                "Company": company.upper(), "Mobile": mobile, "Email": email,
                "GST": gst, "Address": address, "State": state,
                "Bank": bank, "Account": account, "IFSC": ifsc,
                "CIN": cin, "Pincode": pincode,
            }
            owner_df = pd.DataFrame([owner_data])
            owner_data_folder = os.path.dirname(self.owner_data_dir)
            os.makedirs(owner_data_folder, exist_ok=True)
            if os.path.exists(self.owner_data_dir):
                return "Error", "Owner Data already exists, Contact Admin."
            owner_df.to_csv(self.owner_data_dir, index=False)
            self.InitializeAccount()
            return "Success", "Owner registered successfully."
        except Exception as e:
            self.error(f"Error saving owner details: {e}")
            return "Error", "Unexpected error. Contact Admin."

    # ──────────────────────────────────────────────────────────────────────────
    #  CLIENTS
    # ──────────────────────────────────────────────────────────────────────────

    def unique_clientId(self, company: str) -> str:
        words  = [w for w in company.strip().upper().split() if w]
        prefix = "".join(w[0] for w in words)[:4]
        if self.client_data.empty:
            return f"{prefix}001"
        matching_ids = self.client_data[
            self.client_data["ClientId"].str.startswith(prefix, na=False)
        ]["ClientId"]
        if matching_ids.empty:
            new_number = 1
        else:
            numbers = [
                int(cid[len(prefix):])
                for cid in matching_ids
                if cid[len(prefix):].isdigit()
            ]
            new_number = max(numbers) + 1 if numbers else 1
        return f"{prefix}{new_number:03d}"

    def save_client_to_csv(self, company: str, client, mobile, alt_mobile,
                           opening_balance, gst, address, pincode,
                           state, state_code, bank, account, ifsc):
        try:
            company_upper = company.strip().upper()
            if company_upper.startswith("M/S"):
                company_upper = company_upper[3:].strip()

            # duplicate checks
            if not self.client_data.empty and gst and gst in self.client_data["GST"].values:
                return "Error", "GST Number already exists."
            if not self.client_data.empty and company_upper in self.client_data["Company"].values:
                return "Error", "Company already exists."

            # ledger
            if not self.save_opening_balance_to_ledger(opening_balance, company_upper):
                return "Error", "Error creating ledger."

            created_at = datetime.now(ZoneInfo("Asia/Kolkata"))

            client_data = {
                "CreatedAT":   created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "ClientId":    self.unique_clientId(company_upper),
                "Company":     company_upper,
                "Client_name": client.title(),
                "Mobile":      str(mobile),
                "AltMobile":   str(alt_mobile),
                "GST":         gst,
                "Address":     address,
                "Pincode":     str(pincode),
                "State":       state,
                "StateCode":   state_code,
                "BankName":    bank,
                "Account_no":  str(account),
                "IFSC":        ifsc,
            }

            new_df      = pd.DataFrame([client_data])
            ordered_cols = list(client_data.keys())

            if os.path.isfile(self.client_save_dir):
                existing_df = pd.read_csv(self.client_save_dir, dtype=str)
                extra_cols  = [c for c in existing_df.columns if c not in ordered_cols]
                all_cols    = ordered_cols + extra_cols
                existing_df = existing_df.reindex(columns=all_cols, fill_value="")
                new_df      = new_df.reindex(columns=all_cols, fill_value="")
                final_df    = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                final_df = new_df.reindex(columns=ordered_cols)

            os.makedirs(os.path.dirname(self.client_save_dir), exist_ok=True)
            final_df.to_csv(self.client_save_dir, index=False)
            self.load_data()
            return "Success", "Client saved successfully!"
        except Exception as e:
            self.error(f"Error creating client: {e}")
            return "Error", "Error creating client."

    def save_opening_balance_to_ledger(self, opening_balance: float, company_name: str) -> bool:
        try:
            company_name = "_".join(company_name.lower().split())
            debit  = abs(opening_balance) if opening_balance > 0 else 0.0
            credit = abs(opening_balance) if opening_balance < 0 else 0.0
            ledger_data = {
                "Date": "", "Vch Type": "Opening Balance", "Vch No.": "",
                "Debit": debit, "Credit": credit, "Balance": float(opening_balance),
            }
            ledger_path = os.path.join(self.ledger_save_dir, f"{company_name}.csv")
            os.makedirs(self.ledger_save_dir, exist_ok=True)
            pd.DataFrame([ledger_data]).to_csv(ledger_path, index=False)
            return True
        except Exception as e:
            self.error(f"Error creating ledger: {e}")
            return False

    def load_clients(self) -> pd.DataFrame:
        self.load_data()
        return self.client_data

    def update_client(self, updated_data: dict):
        try:
            if self.client_data.empty:
                return "Error", "No client data."
            client_id = updated_data.get("ClientId")
            if not client_id:
                return "Error", "Invalid Client ID."
            mask = self.client_data["ClientId"] == client_id
            if not mask.any():
                return "Error", "Client not found."
            protected = {"ClientId", "createdAt", "Company"}
            for col, val in updated_data.items():
                if col in protected:
                    continue
                if col in self.client_data.columns:
                    self.client_data.loc[mask, col] = val
            self.client_data.to_csv(self.client_save_dir, index=False)
            self.load_data()
            return "Success", "Client updated successfully."
        except Exception as e:
            self.error(f"Error updating client: {e}")
            return "Error", "Error updating client."

    def get_company_names(self) -> list:
        self.load_data()
        if not self.client_data.empty:
            return self.client_data["Company"].tolist()
        return []

    def client_details(self, company: str) -> dict:
        if self.client_data.empty:
            return {}
        row = self.client_data[self.client_data["Company"] == company]
        if row.empty:
            return {}
        return {k: ("" if pd.isna(v) else v) for k, v in row.iloc[0].to_dict().items()}

    # ──────────────────────────────────────────────────────────────────────────
    #  LEDGER
    # ──────────────────────────────────────────────────────────────────────────

    def get_financial_year(self, date_obj: datetime) -> str:
        year = date_obj.year
        if date_obj.month >= 4:
            return f"{year}-{str(year + 1)[-2:]}"
        return f"{year - 1}-{str(year)[-2:]}"

    def _ledger_path(self, company_name: str) -> str:
        csv_name = "_".join(company_name.lower().split()) + ".csv"
        return os.path.join(self.ledger_save_dir, csv_name)

    def update_ledger(self, date: str, clientId: str, amount: float,
                      entry_type: str, voucher_type: str,
                      manual_voucher_no: str = "") -> tuple:
        try:
            row = self.client_data[self.client_data["ClientId"] == clientId]
            if row.empty:
                return "Error", "Client not found."
            company_name = row["Company"].item()
            ledger_path  = self._ledger_path(company_name)
            if not os.path.exists(ledger_path):
                return "Error", "Ledger file not found."
            ledger_data = pd.read_csv(ledger_path)
            if ledger_data.empty:
                return "Error", "Ledger corrupted."

            current_date_obj = datetime.strptime(date, "%d/%m/%Y")

            ledger_data["_sort_date"] = pd.to_datetime(
                ledger_data["Date"], errors="coerce", dayfirst=True
            )
            opening_rows = ledger_data[ledger_data["Vch Type"] == "Opening Balance"].copy()
            entry_rows   = ledger_data[ledger_data["Vch Type"] != "Opening Balance"].copy()

            fy         = self.get_financial_year(current_date_obj)
            prefix     = "".join(company_name.split())[:2].upper()
            running_no = len(entry_rows) + 1

            if manual_voucher_no.strip():
                voucher_no_str = manual_voucher_no.strip()
                reference_id   = voucher_no_str
            else:
                reference_id   = f"{prefix}/{fy}/{running_no}"
                voucher_no_str = str(running_no)

            debit  = float(amount) if entry_type == "Debit"  else 0.0
            credit = float(amount) if entry_type == "Credit" else 0.0

            new_entry = pd.DataFrame([{
                "Date":       date,
                "Vch Type":   voucher_type,
                "Vch No.":    f"{voucher_no_str}\nRef #: {reference_id}" if not manual_voucher_no.strip() else f"Ref #: {reference_id}",
                "Debit":      debit  if debit  != 0 else "",
                "Credit":     credit if credit != 0 else "",
                "Balance":    0.0,
                "_sort_date": current_date_obj,
            }])

            combined = pd.concat([entry_rows, new_entry], ignore_index=True)
            combined = combined.sort_values("_sort_date", kind="stable", na_position="last")

            if not opening_rows.empty:
                running_balance = float(opening_rows.iloc[-1]["Balance"])
            else:
                running_balance = 0.0

            for idx in combined.index:
                d = combined.at[idx, "Debit"]
                c = combined.at[idx, "Credit"]
                d = float(d) if str(d).replace(".", "").replace("-", "").isdigit() else 0.0
                c = float(c) if str(c).replace(".", "").replace("-", "").isdigit() else 0.0
                running_balance += d - c
                combined.at[idx, "Balance"] = running_balance

            combined     = combined.drop(columns=["_sort_date"])
            opening_rows = opening_rows.drop(columns=["_sort_date"])
            full = pd.concat([opening_rows, combined], ignore_index=True)
            full.to_csv(ledger_path, index=False)
            return "Success", "Ledger updated successfully."
        except Exception as e:
            self.error(f"Error updating ledger: {e}")
            return "Error", "Error updating ledger."

    def view_ledger(self, company_name: str, start, end):
        try:
            start = pd.to_datetime(start)
            end   = pd.to_datetime(end)
            if start > end:
                return "Error", "Invalid date range.", pd.DataFrame()
            ledger_path = self._ledger_path(company_name)
            if not os.path.exists(ledger_path):
                return "Error", "Ledger not found.", pd.DataFrame()
            ledger_df = pd.read_csv(ledger_path)
            if ledger_df.empty:
                return "Error", "Ledger empty.", pd.DataFrame()

            ledger_df["Debit"]   = pd.to_numeric(ledger_df["Debit"],   errors="coerce").fillna(0)
            ledger_df["Credit"]  = pd.to_numeric(ledger_df["Credit"],  errors="coerce").fillna(0)
            ledger_df["Balance"] = pd.to_numeric(ledger_df["Balance"], errors="coerce").fillna(0)
            ledger_df["Date"]    = pd.to_datetime(
                ledger_df["Date"], errors="coerce", dayfirst=True
            )

            prev_rows = ledger_df[ledger_df["Date"] < start]
            if not prev_rows.empty:
                opening_balance = float(prev_rows.iloc[-1]["Balance"])
            else:
                ob_row = ledger_df[ledger_df["Vch Type"] == "Opening Balance"]
                opening_balance = float(ob_row.iloc[0]["Balance"]) if not ob_row.empty else 0.0

            df = ledger_df[
                (ledger_df["Date"] >= start) & (ledger_df["Date"] <= end)
            ].copy()

            opening_row = pd.DataFrame([{
                "Date": pd.NaT, "Vch Type": "Opening Balance", "Vch No.": "",
                "Debit": 0.0, "Credit": 0.0, "Balance": opening_balance,
            }])
            df = pd.concat([opening_row, df], ignore_index=True)

            total_debit     = df["Debit"].sum()
            total_credit    = df["Credit"].sum()
            closing_balance = float(df.iloc[-1]["Balance"])

            def fmt_amt(x):
                return "" if float(x) == 0 else f"{x:,.2f}"

            def fmt_bal(x):
                if float(x) == 0:
                    return "0.00"
                return f"{abs(x):,.2f} {'Dr' if x > 0 else 'Cr'}"

            df["Debit"]   = df["Debit"].apply(fmt_amt)
            df["Credit"]  = df["Credit"].apply(fmt_amt)
            df["Balance"] = df["Balance"].apply(fmt_bal)
            df["Date"]    = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d %b %y")
            df["Date"]    = df["Date"].fillna("")

            total_row = pd.DataFrame([{
                "Date": "", "Vch Type": "Total", "Vch No.": "",
                "Debit": f"{total_debit:,.2f}",
                "Credit": f"{total_credit:,.2f}", "Balance": "",
            }])
            closing_row = pd.DataFrame([{
                "Date": "", "Vch Type": "Closing Balance", "Vch No.": "",
                "Debit": "", "Credit": "", "Balance": fmt_bal(closing_balance),
            }])
            df = pd.concat([df, total_row, closing_row], ignore_index=True)
            df = df.replace({r"\n": " "}, regex=True).fillna("")
            return None, None, df
        except Exception as e:
            self.error(f"Error loading ledger: {e}")
            return "Error", "Error loading ledger.", pd.DataFrame()

    # ──────────────────────────────────────────────────────────────────────────
    #  PRODUCTS
    # ──────────────────────────────────────────────────────────────────────────

    def save_products(self, product_name, hsn, rate):
        if not product_name or not hsn or not rate:
            return "Error", "Provide full details."
        try:
            product_name    = product_name.strip().upper()
            deleted_ids     = self._load_deleted_product_ids()

            if not self.products_data.empty:
                if product_name in self.products_data["Name"].values:
                    return "Error", "Product already exists."

            # generate unique ID that is not in deleted set or existing set
            existing_ids = (
                set(self.products_data["ProductId"].tolist())
                if not self.products_data.empty else set()
            )
            while True:
                product_id = uuid.uuid4().hex[:4].upper()
                if product_id not in existing_ids and product_id not in deleted_ids:
                    break

            new_product = {
                "ProductId": product_id,
                "Name":      product_name,
                "HSN":       hsn,
                "Rate":      rate,
            }
            new_df = pd.DataFrame([new_product])
            self.products_data = (
                pd.concat([self.products_data, new_df], ignore_index=True)
                if not self.products_data.empty else new_df
            )
            os.makedirs(os.path.dirname(self.products_data_dir), exist_ok=True)
            self.products_data.to_csv(self.products_data_dir, index=False)
            self.load_data()
            return "Success", "Product saved successfully."
        except Exception as e:
            self.error(f"Error adding product: {e}")
            return "Error", "Error adding product."

    def edit_product(self, product_id, product_name, hsn, rate):
        if not all([product_id, product_name, hsn, rate]):
            return "Error", "Provide full details."
        product_name = product_name.strip().upper()
        row_index = self.products_data[
            self.products_data["ProductId"] == product_id
        ].index
        if row_index.empty:
            return "Error", "Product not found."
        dup = self.products_data[
            (self.products_data["Name"]      == product_name) &
            (self.products_data["ProductId"] != product_id)
        ]
        if not dup.empty:
            return "Error", "Another product with this name already exists."
        idx = row_index[0]
        self.products_data.at[idx, "Name"] = product_name
        self.products_data.at[idx, "HSN"]  = hsn
        self.products_data.at[idx, "Rate"] = rate
        self.products_data.to_csv(self.products_data_dir, index=False)
        self.load_data()
        return "Success", "Product updated successfully."

    def delete_product(self, product_id: str) -> tuple:
        """
        Remove a product from the active product list and permanently record its
        ID in the deleted-IDs store so it can never be reused.

        Client-specific rates are intentionally NOT removed from their CSV — the
        rates file retains the row so no rewrite is needed, but the product will
        not appear in any dropdown because it's absent from products_data.
        """
        try:
            if self.products_data.empty:
                return "Error", "No products found."

            mask = self.products_data["ProductId"] == product_id
            if not mask.any():
                return "Error", "Product not found."

            # Record the ID as permanently deleted BEFORE removing from CSV
            deleted_ids = self._load_deleted_product_ids()
            deleted_ids.add(product_id)
            self._save_deleted_product_ids(deleted_ids)

            # Remove from active products
            self.products_data = (
                self.products_data[~mask].reset_index(drop=True)
            )
            self.products_data.to_csv(self.products_data_dir, index=False)
            self.load_data()
            return "Success", "Product deleted successfully."
        except Exception as e:
            self.error(f"Error deleting product: {e}")
            return "Error", "Error deleting product."

    def view_products(self):
        try:
            self.load_data()
            if self.products_data.empty:
                return None, None, pd.DataFrame()
            return None, None, self.products_data.copy()
        except Exception as e:
            self.error(f"Error viewing products: {e}")
            return "Error", "Error viewing products.", pd.DataFrame()

    # ──────────────────────────────────────────────────────────────────────────
    #  CLIENT RATES
    # ──────────────────────────────────────────────────────────────────────────

    def set_client_rates(self, clientId, productId, rate):
        try:
            if self.client_data[self.client_data["ClientId"] == clientId].empty:
                return "Error", "Client not found."
            if self.products_data[self.products_data["ProductId"] == productId].empty:
                return "Error", "Product not found."
            if rate == "":
                return "Error", "Provide Valid Rate."
            if self.client_rates_data.empty:
                self.client_rates_data = pd.DataFrame(
                    [{"ClientId": clientId, "ProductId": productId, "Rate": rate}]
                )
            else:
                row = self.client_rates_data[
                    (self.client_rates_data["ClientId"]  == clientId) &
                    (self.client_rates_data["ProductId"] == productId)
                ]
                if not row.empty:
                    self.client_rates_data.at[row.index[0], "Rate"] = float(rate)
                else:
                    self.client_rates_data = pd.concat(
                        [self.client_rates_data,
                         pd.DataFrame([{
                             "ClientId": clientId, "ProductId": productId, "Rate": rate,
                         }])],
                        ignore_index=True,
                    )
            os.makedirs(os.path.dirname(self.client_rates_data_dir), exist_ok=True)
            self.client_rates_data.to_csv(self.client_rates_data_dir, index=False)
            return "Success", "Client rate saved."
        except Exception as e:
            self.error(f"Error setting client rates: {e}")
            return "Error", "Error setting client rates."

    def get_products_with_client_rates(self, client_id: str) -> pd.DataFrame:
        if self.products_data.empty:
            return pd.DataFrame()
        df = self.products_data.copy()
        if not self.client_rates_data.empty:
            cr = self.client_rates_data[
                self.client_rates_data["ClientId"] == client_id
            ][["ProductId", "Rate"]].rename(columns={"Rate": "ClientRate"})
            df = df.merge(cr, on="ProductId", how="left")
            df["Rate"] = df["ClientRate"].fillna(df["Rate"])
            df = df.drop(columns=["ClientRate"])
        return df.reset_index(drop=True)

    def get_client_rates_for_company(self, client_id: str) -> pd.DataFrame:
        if self.products_data.empty:
            return pd.DataFrame()
        df = self.products_data.copy()
        df = df.rename(columns={"Rate": "DefaultRate"})
        if not self.client_rates_data.empty:
            cr = self.client_rates_data[
                self.client_rates_data["ClientId"] == client_id
            ][["ProductId", "Rate"]].rename(columns={"Rate": "ClientRate"})
            df = df.merge(cr, on="ProductId", how="left")
        else:
            df["ClientRate"] = None
        return df[["ProductId", "Name", "HSN", "DefaultRate", "ClientRate"]].reset_index(drop=True)

    def delete_client_rate(self, client_id: str, product_id: str) -> tuple:
        try:
            if self.client_rates_data.empty:
                return "Error", "No rates found."
            mask = (
                (self.client_rates_data["ClientId"]  == client_id) &
                (self.client_rates_data["ProductId"] == product_id)
            )
            if not mask.any():
                return "Error", "Rate not found."
            self.client_rates_data = self.client_rates_data[~mask].reset_index(drop=True)
            self.client_rates_data.to_csv(self.client_rates_data_dir, index=False)
            return "Success", "Rate deleted."
        except Exception as e:
            self.error(f"Error deleting client rate: {e}")
            return "Error", "Error deleting rate."

    # ──────────────────────────────────────────────────────────────────────────
    #  INVOICE NUMBER GENERATION
    # ──────────────────────────────────────────────────────────────────────────

    def _load_json_bills(self, path: str) -> list:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_json_bills(self, path: str, bills: list) -> bool:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bills, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.error(f"Error saving JSON bills: {e}")
            return False

    def _all_invoice_numbers(self) -> set:
        used: set = set()
        for bill in self._load_json_bills(self.temp_bill_data):
            inv = bill.get("invoice_no")
            if inv:
                used.add(inv)
        for bill in self._load_json_bills(self.permanent_bill_data):
            inv = bill.get("invoice_no")
            if inv:
                used.add(inv)
        return used
    
    def _all_performa_numbers(self):
        used: set = set()
        for bill in self._load_json_bills(self.performa_bill_data):
            inv = bill.get("performa_no")
            if inv:
                used.add(inv)
        return used

    def _current_financial_year_short(self) -> str:
        now  = datetime.now(ZoneInfo("Asia/Kolkata"))
        year = now.year
        if now.month >= 4:
            return f"{str(year)[-2:]}-{str(year + 1)[-2:]}"
        return f"{str(year - 1)[-2:]}-{str(year)[-2:]}"

    def generate_invoice_number(self, company_name: str) -> str:
        owner_company = self.owner_data.get("Company", company_name)
        words  = [w for w in owner_company.strip().upper().split() if w]
        prefix = "".join(w[0] for w in words)[:4]
        fy     = self._current_financial_year_short()

        used    = self._all_invoice_numbers()
        pattern = re.compile(
            rf"^{re.escape(prefix)}/{re.escape(fy)}/(\d+)$"
        )
        max_serial = 0
        for inv in used:
            m = pattern.match(inv)
            if m:
                max_serial = max(max_serial, int(m.group(1)))

        return f"{prefix}/{fy}/{max_serial + 1:03d}"

    def generate_performa_number(self) -> str:

        prefix = "PI"
        fy     = self._current_financial_year_short()

        used    = self._all_performa_numbers()
        pattern = re.compile(
            rf"^{re.escape(prefix)}/{re.escape(fy)}/(\d+)$"
        )
        max_serial = 0
        for inv in used:
            m = pattern.match(inv)
            if m:
                max_serial = max(max_serial, int(m.group(1)))

        return f"{prefix}/{fy}/{max_serial + 1:03d}"

    # ──────────────────────────────────────────────────────────────────────────
    #  TEMP BILLS
    # ──────────────────────────────────────────────────────────────────────────

    def save_temp_bill(self, bill_data: dict) -> tuple:
        try:
            if not bill_data.get("invoice_no"):
                return "Error", "invoice_no is missing."
            bills    = self._load_json_bills(self.temp_bill_data)
            existing = {b.get("invoice_no") for b in bills}
            if bill_data["invoice_no"] in existing:
                return "Error", f"Invoice {bill_data['invoice_no']} already exists."
            bill_data["saved_at"] = datetime.now(
                ZoneInfo("Asia/Kolkata")
            ).strftime("%Y-%m-%d %H:%M:%S")
            bills.append(bill_data)
            if not self._save_json_bills(self.temp_bill_data, bills):
                return "Error", "Could not write to temp bill store."
            return "Success", bill_data["invoice_no"]
        except Exception as e:
            self.error(f"Error saving temp bill: {e}")
            return "Error", "Unexpected error saving bill."

    def save_performa_bill(self, bill_data: dict) -> tuple:
        try:
            if not bill_data.get("performa_no"):
                return "Error", "performa_no is missing."
            bills    = self._load_json_bills(self.performa_bill_data)
            existing = {b.get("performa_no") for b in bills}
            if bill_data["performa_no"] in existing:
                return "Error", f"performa {bill_data['performa_no']} already exists."
            bill_data["saved_at"] = datetime.now(
                ZoneInfo("Asia/Kolkata")
            ).strftime("%Y-%m-%d %H:%M:%S")
            bills.append(bill_data)
            if not self._save_json_bills(self.performa_bill_data, bills):
                return "Error", "Could not write to temp bill store."
            return "Success", bill_data["performa_no"]
        except Exception as e:
            self.error(f"Error saving temp bill: {e}")
            return "Error", "Unexpected error saving bill."

    def load_temp_bills(self) -> list:
        return self._load_json_bills(self.temp_bill_data)

    def load_permanent_bills(self) -> list:
        return self._load_json_bills(self.permanent_bill_data)

    def get_temp_bill_by_invoice(self, invoice_no: str) -> dict | None:
        for bill in self._load_json_bills(self.temp_bill_data):
            if bill.get("invoice_no") == invoice_no:
                return bill
        return None

    def get_performa_bill_by_invoice(self, performa_no: str) -> dict | None:
        for bill in self._load_json_bills(self.performa_bill_data):
            if bill.get("performa_no") == performa_no:
                return bill
        return None

    def get_permanent_bill_by_invoice(self, invoice_no: str) -> dict | None:
        for bill in self._load_json_bills(self.permanent_bill_data):
            if bill.get("invoice_no") == invoice_no:
                return bill
        return None

    def delete_temp_bill(self, invoice_no: str) -> tuple:
        try:
            temp_bills = self._load_json_bills(self.temp_bill_data)
            original   = len(temp_bills)
            temp_bills = [b for b in temp_bills if b.get("invoice_no") != invoice_no]
            if len(temp_bills) == original:
                return "Error", f"Invoice {invoice_no} not found in temp bills."
            if not self._save_json_bills(self.temp_bill_data, temp_bills):
                return "Error", "Could not write to temp bill store."
            return "Success", f"Invoice {invoice_no} deleted from temp bills."
        except Exception as e:
            self.error(f"Error deleting temp bill: {e}")
            return "Error", "Error deleting temp bill."

    def delete_performa_bill(self, performa_no: str) -> tuple:
        try:
            performa_bills = self._load_json_bills(self.performa_bill_data)
            original   = len(performa_bills)
            performa_bills = [b for b in performa_bills if b.get("performa_no") != performa_no]
            if len(performa_bills) == original:
                return "Error", f"Performa {performa_no} not found in temp bills."
            if not self._save_json_bills(self.performa_bill_data, performa_bills):
                return "Error", "Could not write to temp bill store."
            return "Success", f"Performa {performa_no} deleted from temp bills."
        except Exception as e:
            self.error(f"Error deleting Performa: {e}")
            return "Error", "Error deleting Performa."
    def finalize_bill(self, invoice_no: str, eway_no: str = "") -> tuple:
        try:
            temp_bills = self._load_json_bills(self.temp_bill_data)
            bill = next(
                (b for b in temp_bills if b.get("invoice_no") == invoice_no), None
            )
            if not bill:
                return "Error", f"Invoice {invoice_no} not found in temp bills."

            perm_bills    = self._load_json_bills(self.permanent_bill_data)
            perm_existing = {b.get("invoice_no") for b in perm_bills}
            if invoice_no in perm_existing:
                return "Error", f"Invoice {invoice_no} already in permanent records."

            if eway_no:
                bill["eway"] = eway_no.strip()

            bill["finalized_at"] = datetime.now(
                ZoneInfo("Asia/Kolkata")
            ).strftime("%Y-%m-%d %H:%M:%S")
            perm_bills.append(bill)
            if not self._save_json_bills(self.permanent_bill_data, perm_bills):
                return "Error", "Could not write to permanent bill store."

            temp_bills = [b for b in temp_bills if b.get("invoice_no") != invoice_no]
            self._save_json_bills(self.temp_bill_data, temp_bills)

            client_company = (
                bill.get("client_company") or bill.get("client_name", "")
            ).strip().upper()

            bill_date   = bill.get("bill_date") or bill.get("date", "")
            grand_total = bill.get("grand_total", "0").replace(",", "")

            client_row = self.client_data[
                self.client_data["Company"] == client_company
            ]
            if client_row.empty:
                client_row = self.client_data[
                    self.client_data["Client_name"].str.upper() == client_company
                ]

            if not client_row.empty:
                client_id = client_row.iloc[0]["ClientId"]
                try:
                    dt_obj   = datetime.strptime(bill_date, "%d/%m/%Y")
                    date_str = dt_obj.strftime("%d/%m/%Y")
                except Exception:
                    date_str = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d/%m/%Y")
                self.update_ledger(
                    date_str, client_id,
                    float(grand_total), "Debit", "Sales",
                    manual_voucher_no=invoice_no,
                )

            return "Success", f"Invoice {invoice_no} finalized."
        except Exception as e:
            self.error(f"Error finalizing bill: {e}")
            return "Error", "Error finalizing bill."

    def get_all_bill_invoice_numbers(self, store: str = "temp") -> list:
        result = []
        if store in ("temp", "all"):
            for b in self._load_json_bills(self.temp_bill_data):
                inv = b.get("invoice_no")
                if inv:
                    result.append((
                        "temp", inv,
                        b.get("client_name", ""),
                        b.get("saved_at", ""),
                    ))
        if store in ("performa", "all"):
            for b in self._load_json_bills(self.performa_bill_data):
                inv = b.get("performa_no")
                if inv:
                    result.append((
                        "performa", inv,
                        b.get("client_name", ""),
                        b.get("created at", b.get("saved_at", "")),
                    ))
        if store in ("permanent", "all"):
            for b in self._load_json_bills(self.permanent_bill_data):
                inv = b.get("invoice_no")
                if inv:
                    result.append((
                        "permanent", inv,
                        b.get("client_name", ""),
                        b.get("finalized_at", b.get("saved_at", "")),
                    ))
        return result
