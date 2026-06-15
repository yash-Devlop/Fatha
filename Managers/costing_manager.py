from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")


UNIT_TYPES: dict[str, list[str]] = {
    "count":  ["piece", "pair", "set", "box", "pack", "roll", "sheet", "unit", "lot", "dozen"],
    "length": ["meter", "cm", "mm", "inch", "feet", "yard"],
    "weight": ["kg", "gram", "mg", "ton", "lb"],
    "volume": ["liter", "ml", "gallon", "fl oz"],
}

UNIT_TYPE_LABELS = {
    "count":  "Count / Quantity",
    "length": "Length",
    "weight": "Weight",
    "volume": "Volume",
}

ALL_UNIT_TYPES: list[str] = list(UNIT_TYPES.keys())
ALL_UNITS: list[str]      = [u for us in UNIT_TYPES.values() for u in us]


def _now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _uid(length: int = 6) -> str:
    return uuid.uuid4().hex[:length].upper()


class CostingManager:

    _RM_COLS     = ["MaterialId", "Name", "UnitType", "Unit", "CostPerUnit", "CreatedAt", "UpdatedAt"]
    _RMHIST_COLS = ["HistoryId", "MaterialId", "MaterialName", "OldCost", "NewCost", "ChangedAt", "Notes"]

    _BOM_COLS    = [
        "BOMId", "ProductId", "ProductName", "MaterialId", "MaterialName",
        "QuantityUsed", "Unit", "AddedAt",
        "SourceType",
        "LayerId",
        "LayerName",
    ]

    _CCT_COLS    = ["TypeId", "Name", "Description", "CreatedAt"]
    _PCC_COLS    = ["PCCId", "ProductId", "TypeId", "TypeName", "Rate", "RateUnit", "UpdatedAt"]
    _SNAP_COLS   = [
        "SnapshotId", "ProductId", "ProductName",
        "RawMaterialCost", "CustomCostBreakdown",
        "TotalCustomCost", "TotalCost",
        "WarrantyPct", "WarrantyCost",
        "LabourPct",   "LabourCost",
        "FinalCost",
        "SalePrice", "Margin", "MarginPct",
        "SnapshotAt", "TriggerType", "Notes",
    ]
    _LAYER_COLS  = ["LayerId", "LayerName", "MaterialId", "MaterialName",
                    "QuantityUsed", "Unit", "CreatedAt"]
    _WLC_COLS    = ["WLCId", "ProductId", "WarrantyPct", "LabourPct", "UpdatedAt"]

    def __init__(self, data_dir: str) -> None:
        self._data_dir    = data_dir
        os.makedirs(data_dir, exist_ok=True)

        self._rm_path     = os.path.join(data_dir, "raw_materials.csv")
        self._rmhist_path = os.path.join(data_dir, "raw_material_cost_history.csv")
        self._bom_path    = os.path.join(data_dir, "product_bom.csv")
        self._cct_path    = os.path.join(data_dir, "custom_cost_types.csv")
        self._pcc_path    = os.path.join(data_dir, "product_custom_costs.csv")
        self._snap_path   = os.path.join(data_dir, "product_cost_snapshots.csv")
        self._layer_path  = os.path.join(data_dir, "layers.csv")
        self._wlc_path    = os.path.join(data_dir, "product_warranty_config.csv")

        self._ensure_files()

    def _ensure_files(self) -> None:
        for path, cols in [
            (self._rm_path,     self._RM_COLS),
            (self._rmhist_path, self._RMHIST_COLS),
            (self._bom_path,    self._BOM_COLS),
            (self._cct_path,    self._CCT_COLS),
            (self._pcc_path,    self._PCC_COLS),
            (self._snap_path,   self._SNAP_COLS),
            (self._wlc_path,    self._WLC_COLS),
        ]:
            if not os.path.exists(path):
                pd.DataFrame(columns=cols).to_csv(path, index=False)
            else:
                if path == self._snap_path:
                    self._migrate_snapshot_cols()
                if path == self._bom_path:
                    self._migrate_bom_cols()

    def _migrate_snapshot_cols(self) -> None:
        try:
            df = pd.read_csv(self._snap_path)
            changed = False
            for col, default in [
                ("WarrantyPct", 0.0), ("WarrantyCost", 0.0),
                ("LabourPct",   0.0), ("LabourCost",   0.0),
                ("FinalCost",   None),
            ]:
                if col not in df.columns:
                    df[col] = df.get("TotalCost", 0.0) if col == "FinalCost" else default
                    changed = True
            if changed:
                df.to_csv(self._snap_path, index=False)
        except Exception:
            pass

    def _migrate_bom_cols(self) -> None:
        try:
            df = pd.read_csv(self._bom_path)
            changed = False
            if "SourceType" not in df.columns:
                df["SourceType"] = "direct"
                changed = True
            if "LayerId" not in df.columns:
                df["LayerId"] = ""
                changed = True
            if "LayerName" not in df.columns:
                df["LayerName"] = ""
                changed = True
            df["SourceType"] = df["SourceType"].fillna("direct")
            df["LayerId"]    = df["LayerId"].fillna("")
            df["LayerName"]  = df["LayerName"].fillna("")
            if changed:
                df.to_csv(self._bom_path, index=False)
        except Exception:
            pass


    def _read(self, path: str, dtypes: dict | None = None) -> pd.DataFrame:
        try:
            df = pd.read_csv(path, dtype=dtypes or {})
            if "Name" in df.columns:
                df = df.sort_values(by="Name")
            return df.reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

    def _write(self, path: str, df: pd.DataFrame) -> bool:
        try:
            df.to_csv(path, index=False)
            return True
        except Exception:
            return False


    def get_raw_materials(self) -> pd.DataFrame:
        return self._read(self._rm_path)

    def add_raw_material(self, name: str, unit_type: str,
                         unit: str, cost_per_unit: float | str) -> tuple:
        name = name.strip().upper()
        if not name or not unit_type or not unit:
            return "Error", "All fields are required."
        try:
            cost_per_unit = float(cost_per_unit)
            if cost_per_unit < 0:
                raise ValueError
        except (ValueError, TypeError):
            return "Error", "Cost must be a non-negative number."

        df = self.get_raw_materials()
        if not df.empty and name in df["Name"].values:
            return "Error", f"Material '{name}' already exists."

        row = {
            "MaterialId":  _uid(6),
            "Name":        name,
            "UnitType":    unit_type,
            "Unit":        unit,
            "CostPerUnit": round(cost_per_unit, 4),
            "CreatedAt":   _now(),
            "UpdatedAt":   _now(),
        }
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        if self._write(self._rm_path, df):
            self._log_rm_cost_history("", "", 0.0, cost_per_unit,
                                      row["MaterialId"], name, "Initial entry")
            return "Success", f"Material '{name}' added."
        return "Error", "Could not save material."

    def edit_raw_material(self, material_id: str, name: str,
                          unit_type: str, unit: str) -> tuple:
        df   = self.get_raw_materials()
        mask = df["MaterialId"] == material_id
        if not mask.any():
            return "Error", "Material not found."
        name = name.strip().upper()
        if not name:
            return "Error", "Name is required."
        dup = df[(df["Name"] == name) & (df["MaterialId"] != material_id)]
        if not dup.empty:
            return "Error", "Another material with this name already exists."
        df.loc[mask, "Name"]      = name
        df.loc[mask, "UnitType"]  = unit_type
        df.loc[mask, "Unit"]      = unit
        df.loc[mask, "UpdatedAt"] = _now()
        if self._write(self._rm_path, df):
            return "Success", "Material updated."
        return "Error", "Could not save."

    def update_raw_material_cost(self, material_id: str,
                                 new_cost: float | str,
                                 notes: str = "") -> tuple:
        df   = self.get_raw_materials()
        mask = df["MaterialId"] == material_id
        if not mask.any():
            return "Error", "Material not found."
        try:
            new_cost = float(new_cost)
            if new_cost < 0:
                raise ValueError
        except (ValueError, TypeError):
            return "Error", "Cost must be a non-negative number."

        old_cost = float(df.loc[mask, "CostPerUnit"].iloc[0])
        mat_name = df.loc[mask, "Name"].iloc[0]

        df.loc[mask, "CostPerUnit"] = round(new_cost, 4)
        df.loc[mask, "UpdatedAt"]   = _now()
        self._write(self._rm_path, df)
        self._log_rm_cost_history("", "", old_cost, new_cost, material_id, mat_name, notes)
        return "Success", f"Cost updated: ₹{old_cost:.4f} → ₹{new_cost:.4f}"

    def _log_rm_cost_history(self, _hist_id: str, _unused: str,
                             old_cost: float, new_cost: float,
                             material_id: str, mat_name: str,
                             notes: str) -> None:
        hist = self._read(self._rmhist_path)
        row  = {
            "HistoryId":    _uid(8),
            "MaterialId":   material_id,
            "MaterialName": mat_name,
            "OldCost":      round(old_cost, 4),
            "NewCost":      round(new_cost, 4),
            "ChangedAt":    _now(),
            "Notes":        notes.strip(),
        }
        hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
        self._write(self._rmhist_path, hist)

    def delete_raw_material(self, material_id: str) -> tuple:
        bom = self._read(self._bom_path)
        if not bom.empty and material_id in bom["MaterialId"].values:
            products = bom[bom["MaterialId"] == material_id]["ProductName"].unique().tolist()
            return "Error", f"Used in: {', '.join(products)}. Remove from BOM first."
        df   = self.get_raw_materials()
        mask = df["MaterialId"] == material_id
        if not mask.any():
            return "Error", "Material not found."
        df = df[~mask].reset_index(drop=True)
        if self._write(self._rm_path, df):
            return "Success", "Material deleted."
        return "Error", "Could not save."

    def get_raw_material_cost_history(self, material_id: str | None = None) -> pd.DataFrame:
        df = self._read(self._rmhist_path)
        if material_id and not df.empty:
            df = df[df["MaterialId"] == material_id]
        return (
            df.sort_values("ChangedAt", ascending=False).reset_index(drop=True)
            if not df.empty else df
        )

    def get_product_bom(self, product_id: str) -> pd.DataFrame:
        """Return all BOM rows for a product, sorted by layer then material name."""
        bom = self._read(self._bom_path)
        if bom.empty:
            return pd.DataFrame()
        rows = bom[bom["ProductId"] == product_id].copy()
        if rows.empty:
            return pd.DataFrame()
        for col, default in [("SourceType", "direct"), ("LayerId", ""), ("LayerName", "")]:
            if col not in rows.columns:
                rows[col] = default
            rows[col] = rows[col].fillna(default if default else "")
        return rows.sort_values(
            ["LayerName", "MaterialName"],
            key=lambda s: s.str.lower()
        ).reset_index(drop=True)

    def get_all_bom(self) -> pd.DataFrame:
        return self._read(self._bom_path)

    def add_material_to_product(
        self,
        product_id: str,
        product_name: str,
        material_id: str,
        quantity_used: float | str,
    ) -> tuple:
        try:
            qty = float(quantity_used)
            if qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return "Error", "Quantity must be a positive number."

        rm  = self.get_raw_materials()
        row = rm[rm["MaterialId"] == material_id]
        if row.empty:
            return "Error", "Raw material not found."

        bom = self._read(self._bom_path)
        for col, default in [("SourceType", "direct"), ("LayerId", ""), ("LayerName", "")]:
            if col not in bom.columns:
                bom[col] = default
            bom[col] = bom[col].fillna(default)

        if not bom.empty:
            dup = bom[
                (bom["ProductId"]   == product_id) &
                (bom["MaterialId"]  == material_id) &
                (bom["SourceType"]  == "direct")
            ]
            if not dup.empty:
                return "Error", "Material already added directly to this BOM. Edit its quantity instead."

        new_row = {
            "BOMId":        _uid(8),
            "ProductId":    product_id,
            "ProductName":  product_name,
            "MaterialId":   material_id,
            "MaterialName": row.iloc[0]["Name"],
            "QuantityUsed": qty,
            "Unit":         row.iloc[0]["Unit"],
            "AddedAt":      _now(),
            "SourceType":   "direct",
            "LayerId":      "",
            "LayerName":    "",
        }
        bom = pd.concat([bom, pd.DataFrame([new_row])], ignore_index=True)
        if self._write(self._bom_path, bom):
            return "Success", f"Added {row.iloc[0]['Name']} × {qty} {row.iloc[0]['Unit']} (direct)"
        return "Error", "Could not save."

    def update_bom_quantity(self, bom_id: str, quantity_used: float | str) -> tuple:
        try:
            qty = float(quantity_used)
            if qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return "Error", "Quantity must be a positive number."
        bom  = self._read(self._bom_path)
        mask = bom["BOMId"] == bom_id
        if not mask.any():
            return "Error", "BOM entry not found."
        bom.loc[mask, "QuantityUsed"] = qty
        if self._write(self._bom_path, bom):
            return "Success", f"Quantity updated to {qty}."
        return "Error", "Could not save."

    def remove_material_from_product(self, bom_id: str) -> tuple:
        bom  = self._read(self._bom_path)
        mask = bom["BOMId"] == bom_id
        if not mask.any():
            return "Error", "Entry not found."
        bom = bom[~mask].reset_index(drop=True)
        if self._write(self._bom_path, bom):
            return "Success", "Removed from BOM."
        return "Error", "Could not save."

    def remove_layer_from_product(self, product_id: str, layer_id: str) -> tuple:
        """Remove all BOM rows for a specific layer injection from a product."""
        bom  = self._read(self._bom_path)
        if bom.empty:
            return "Error", "BOM is empty."
        mask = (bom["ProductId"] == product_id) & (bom["LayerId"] == layer_id)
        if not mask.any():
            return "Error", "Layer not found in this product's BOM."
        layer_name = bom.loc[mask, "LayerName"].iloc[0]
        bom = bom[~mask].reset_index(drop=True)
        if self._write(self._bom_path, bom):
            return "Success", f"Layer '{layer_name}' removed from BOM."
        return "Error", "Could not save."


    def get_custom_cost_types(self) -> pd.DataFrame:
        return self._read(self._cct_path)

    def add_custom_cost_type(self, name: str, description: str = "") -> tuple:
        name = name.strip().title()
        if not name:
            return "Error", "Name is required."
        df = self.get_custom_cost_types()
        if not df.empty and name in df["Name"].values:
            return "Error", f"'{name}' already exists."
        row = {
            "TypeId":      _uid(6),
            "Name":        name,
            "Description": description.strip(),
            "CreatedAt":   _now(),
        }
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        if self._write(self._cct_path, df):
            return "Success", f"'{name}' added as cost type."
        return "Error", "Could not save."

    def delete_custom_cost_type(self, type_id: str) -> tuple:
        pcc = self._read(self._pcc_path)
        if not pcc.empty and type_id in pcc["TypeId"].values:
            return "Error", "Still attached to products. Remove from products first."
        df   = self.get_custom_cost_types()
        mask = df["TypeId"] == type_id
        if not mask.any():
            return "Error", "Not found."
        df = df[~mask].reset_index(drop=True)
        if self._write(self._cct_path, df):
            return "Success", "Cost type deleted."
        return "Error", "Could not save."

    def get_product_custom_costs(self, product_id: str) -> pd.DataFrame:
        df = self._read(self._pcc_path)
        if df.empty:
            return pd.DataFrame()
        return df[df["ProductId"] == product_id].reset_index(drop=True)

    def set_product_custom_cost(self, product_id: str, product_name: str,
                                type_id: str, rate: float | str,
                                rate_unit: str = "per unit") -> tuple:
        try:
            rate = float(rate)
            if rate < 0:
                raise ValueError
        except (ValueError, TypeError):
            return "Error", "Rate must be a non-negative number."

        cct  = self.get_custom_cost_types()
        trow = cct[cct["TypeId"] == type_id]
        if trow.empty:
            return "Error", "Cost type not found."
        type_name = trow.iloc[0]["Name"]

        df = self._read(self._pcc_path)
        if df.empty:
            df = pd.DataFrame(columns=self._PCC_COLS)
        mask = (df["ProductId"] == product_id) & (df["TypeId"] == type_id)

        if mask.any():
            df.loc[mask, "Rate"]      = round(rate, 2)
            df.loc[mask, "RateUnit"]  = rate_unit
            df.loc[mask, "UpdatedAt"] = _now()
        else:
            row = {
                "PCCId":     _uid(8),
                "ProductId": product_id,
                "TypeId":    type_id,
                "TypeName":  type_name,
                "Rate":      round(rate, 2),
                "RateUnit":  rate_unit,
                "UpdatedAt": _now(),
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        if self._write(self._pcc_path, df):
            return "Success", f"{type_name} → ₹{rate:.2f} {rate_unit}"
        return "Error", "Could not save."

    def remove_product_custom_cost(self, pcc_id: str) -> tuple:
        df   = self._read(self._pcc_path)
        mask = df["PCCId"] == pcc_id
        if not mask.any():
            return "Error", "Not found."
        df = df[~mask].reset_index(drop=True)
        if self._write(self._pcc_path, df):
            return "Success", "Removed."
        return "Error", "Could not save."


    def get_product_warranty_config(self, product_id: str) -> dict:
        df = self._read(self._wlc_path)
        if df.empty:
            return {"warranty_pct": 0.0, "labour_pct": 0.0}
        row = df[df["ProductId"] == product_id]
        if row.empty:
            return {"warranty_pct": 0.0, "labour_pct": 0.0}
        return {
            "warranty_pct": float(row.iloc[0].get("WarrantyPct", 0.0) or 0.0),
            "labour_pct":   float(row.iloc[0].get("LabourPct",   0.0) or 0.0),
        }

    def set_product_warranty_config(self, product_id: str,
                                    warranty_pct: float | str,
                                    labour_pct:   float | str) -> tuple:
        try:
            warranty_pct = float(warranty_pct)
            labour_pct   = float(labour_pct)
            if warranty_pct < 0 or labour_pct < 0:
                raise ValueError
        except (ValueError, TypeError):
            return "Error", "Percentages must be non-negative numbers."

        df = self._read(self._wlc_path)
        if df.empty:
            df = pd.DataFrame(columns=self._WLC_COLS)
        mask = df["ProductId"] == product_id

        if mask.any():
            df.loc[mask, "WarrantyPct"] = round(warranty_pct, 4)
            df.loc[mask, "LabourPct"]   = round(labour_pct, 4)
            df.loc[mask, "UpdatedAt"]   = _now()
        else:
            row = {
                "WLCId":       _uid(8),
                "ProductId":   product_id,
                "WarrantyPct": round(warranty_pct, 4),
                "LabourPct":   round(labour_pct, 4),
                "UpdatedAt":   _now(),
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        if self._write(self._wlc_path, df):
            return (
                "Success",
                f"Warranty: {warranty_pct:.2f}%  |  Labour: {labour_pct:.2f}%  saved.",
            )
        return "Error", "Could not save warranty config."


    def calculate_product_cost(self, product_id: str) -> dict:
        rm_df = self.get_raw_materials()
        bom   = self.get_product_bom(product_id)
        pcc   = self.get_product_custom_costs(product_id)
        wlc   = self.get_product_warranty_config(product_id)

        rm_lines: list[dict] = []
        raw_cost = 0.0
        for _, row in bom.iterrows():
            m   = rm_df[rm_df["MaterialId"] == row["MaterialId"]]
            cpu = float(m.iloc[0]["CostPerUnit"]) if not m.empty else 0.0
            qty = float(row["QuantityUsed"])
            lc  = round(cpu * qty, 4)
            raw_cost += lc
            rm_lines.append({
                "bom_id":        row["BOMId"],
                "name":          row["MaterialName"],
                "qty":           qty,
                "unit":          row["Unit"],
                "cost_per_unit": cpu,
                "line_cost":     lc,
                "source_type":   str(row.get("SourceType", "direct") or "direct"),
                "layer_id":      str(row.get("LayerId", "") or ""),
                "layer_name":    str(row.get("LayerName", "") or ""),
            })
        raw_cost = round(raw_cost, 2)

        cc_lines: list[dict] = []
        total_cc = 0.0
        for _, row in pcc.iterrows():
            r = float(row["Rate"])
            total_cc += r
            cc_lines.append({
                "pcc_id":    row["PCCId"],
                "type_name": row["TypeName"],
                "rate":      r,
                "rate_unit": row.get("RateUnit", "per unit"),
            })
        total_cc = round(total_cc, 2)

        base_total      = round(raw_cost + total_cc, 2)
        warranty_pct    = wlc["warranty_pct"]
        warranty_cost   = round(base_total * warranty_pct / 100.0, 2)
        after_warranty  = round(base_total + warranty_cost, 2)
        labour_pct      = wlc["labour_pct"]
        labour_cost     = round(after_warranty * labour_pct / 100.0, 2)
        final_total     = round(after_warranty + labour_cost, 2)

        layer_breakdown = self._build_layer_breakdown(rm_lines)

        return {
            "raw_material_cost":  raw_cost,
            "raw_material_lines": rm_lines,
            "custom_cost_lines":  cc_lines,
            "total_custom_cost":  total_cc,
            "base_total":         base_total,
            "warranty_pct":       warranty_pct,
            "warranty_cost":      warranty_cost,
            "after_warranty":     after_warranty,
            "labour_pct":         labour_pct,
            "labour_cost":        labour_cost,
            "final_total_cost":   final_total,
            "total_cost":         final_total,
            "layer_breakdown":    layer_breakdown,
        }

    def _build_layer_breakdown(self, rm_lines: list[dict]) -> list[dict]:
        if not rm_lines:
            return []

        buckets: dict[tuple, list[dict]] = {}
        for m in rm_lines:
            stype = m.get("source_type", "direct")
            lid   = m.get("layer_id", "")   or ""
            lname = m.get("layer_name", "") or ""
            if stype == "layer" and lid:
                key = ("layer", lid, lname)
            else:
                key = ("direct", "", "")
            buckets.setdefault(key, []).append(m)

        result: list[dict] = []
        for key in sorted((k for k in buckets if k[0] == "layer"),
                          key=lambda k: k[2].lower()):
            _, lid, lname = key
            lines = buckets[key]
            result.append({
                "layer_id":   lid,
                "layer_name": lname,
                "is_direct":  False,
                "materials":  lines,
                "subtotal":   round(sum(x["line_cost"] for x in lines), 2),
            })
        direct_key = ("direct", "", "")
        if direct_key in buckets:
            lines = buckets[direct_key]
            result.append({
                "layer_id":   "",
                "layer_name": "Direct / Ad-hoc",
                "is_direct":  True,
                "materials":  lines,
                "subtotal":   round(sum(x["line_cost"] for x in lines), 2),
            })
        return result

    def get_product_layer_breakdown(self, product_id: str) -> list[dict]:
        bom   = self.get_product_bom(product_id)
        if bom.empty:
            return []
        rm_df = self.get_raw_materials()
        rm_lines: list[dict] = []
        for _, row in bom.iterrows():
            m   = rm_df[rm_df["MaterialId"] == row["MaterialId"]]
            cpu = float(m.iloc[0]["CostPerUnit"]) if not m.empty else 0.0
            qty = float(row["QuantityUsed"])
            lc  = round(cpu * qty, 4)
            rm_lines.append({
                "bom_id":        row["BOMId"],
                "name":          row["MaterialName"],
                "qty":           qty,
                "unit":          row["Unit"],
                "cost_per_unit": cpu,
                "line_cost":     lc,
                "source_type":   str(row.get("SourceType", "direct") or "direct"),
                "layer_id":      str(row.get("LayerId", "") or ""),
                "layer_name":    str(row.get("LayerName", "") or ""),
            })
        return self._build_layer_breakdown(rm_lines)


    def take_cost_snapshot(self, product_id: str, product_name: str,
                           sale_price: float | str,
                           notes: str = "",
                           trigger: str = "manual") -> tuple:
        cost  = self.calculate_product_cost(product_id)
        final = cost["final_total_cost"]

        try:
            sale_price = float(sale_price)
        except (ValueError, TypeError):
            sale_price = 0.0

        margin     = round(sale_price - final, 2)
        margin_pct = round((margin / sale_price * 100) if sale_price else 0.0, 2)

        breakdown_json = json.dumps(
            [{"type": l["type_name"], "rate": l["rate"]}
             for l in cost["custom_cost_lines"]],
            ensure_ascii=False,
        )

        snap = self._read(self._snap_path)
        row  = {
            "SnapshotId":          _uid(10),
            "ProductId":           product_id,
            "ProductName":         product_name,
            "RawMaterialCost":     cost["raw_material_cost"],
            "CustomCostBreakdown": breakdown_json,
            "TotalCustomCost":     cost["total_custom_cost"],
            "TotalCost":           cost["base_total"],
            "WarrantyPct":         cost["warranty_pct"],
            "WarrantyCost":        cost["warranty_cost"],
            "LabourPct":           cost["labour_pct"],
            "LabourCost":          cost["labour_cost"],
            "FinalCost":           final,
            "SalePrice":           sale_price,
            "Margin":              margin,
            "MarginPct":           margin_pct,
            "SnapshotAt":          _now(),
            "TriggerType":         trigger,
            "Notes":               notes.strip(),
        }
        snap = pd.concat([snap, pd.DataFrame([row])], ignore_index=True)
        if self._write(self._snap_path, snap):
            return (
                "Success",
                f"Snapshot saved.\n"
                f"Final cost: ₹{final:.2f} | "
                f"Sale: ₹{sale_price:.2f} | "
                f"Margin: ₹{margin:.2f} ({margin_pct:.1f}%)",
            )
        return "Error", "Could not save snapshot."

    def get_product_cost_history(self, product_id: str) -> pd.DataFrame:
        df = self._read(self._snap_path)
        if df.empty:
            return pd.DataFrame()
        return (
            df[df["ProductId"] == product_id]
            .sort_values("SnapshotAt")
            .reset_index(drop=True)
        )

    def get_all_cost_snapshots(self) -> pd.DataFrame:
        return self._read(self._snap_path)

    def delete_snapshot(self, snapshot_id: str) -> tuple:
        df   = self._read(self._snap_path)
        mask = df["SnapshotId"] == snapshot_id
        if not mask.any():
            return "Error", "Snapshot not found."
        df = df[~mask].reset_index(drop=True)
        if self._write(self._snap_path, df):
            return "Success", "Snapshot deleted."
        return "Error", "Could not save."

    def get_cost_vs_price_timeline(self, product_id: str) -> pd.DataFrame:
        df = self.get_product_cost_history(product_id)
        if df.empty:
            return pd.DataFrame()
        if "FinalCost" not in df.columns:
            df["FinalCost"] = df.get("TotalCost", 0.0)
        df = df[[
            "SnapshotAt", "TotalCost", "FinalCost", "SalePrice",
            "Margin", "MarginPct", "RawMaterialCost", "TotalCustomCost",
            "WarrantyCost", "LabourCost",
        ]].copy()
        df["SnapshotAt"] = pd.to_datetime(df["SnapshotAt"], errors="coerce")
        for col in df.columns:
            if col != "SnapshotAt":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df.dropna(subset=["SnapshotAt"]).reset_index(drop=True)

    def get_material_cost_trend(self, material_id: str) -> pd.DataFrame:
        df = self.get_raw_material_cost_history(material_id)
        if df.empty:
            return pd.DataFrame()
        df = df[["ChangedAt", "OldCost", "NewCost"]].copy()
        df["ChangedAt"] = pd.to_datetime(df["ChangedAt"], errors="coerce")
        df["OldCost"]   = pd.to_numeric(df["OldCost"], errors="coerce").fillna(0)
        df["NewCost"]   = pd.to_numeric(df["NewCost"], errors="coerce").fillna(0)
        return df.sort_values("ChangedAt").reset_index(drop=True)

    def summary_stats(self, product_id: str) -> dict:
        cost  = self.calculate_product_cost(product_id)
        snaps = self.get_product_cost_history(product_id)
        last  = {}
        if not snaps.empty:
            r = snaps.iloc[-1]
            last = {
                "last_snapshot":   str(r["SnapshotAt"]),
                "last_sale_price": float(r["SalePrice"] or 0),
                "last_margin":     float(r["Margin"]    or 0),
                "last_margin_pct": float(r["MarginPct"] or 0),
            }
        return {**cost, **last}


    def get_all_layers(self) -> pd.DataFrame:
        return self._read(self._layer_path)

    def get_layer_names(self) -> list[str]:
        df = self.get_all_layers()
        if df.empty:
            return []
        return sorted(df["LayerName"].unique().tolist())

    def save_layer(self, layer_name: str, material_items: list[dict]) -> tuple:
        layer_name = layer_name.strip().upper()
        if not layer_name:
            return "Error", "Layer preset name cannot be blank."
        if not material_items:
            return "Error", "A layer template must contain at least one raw material."

        rm_df = self.get_raw_materials()
        df    = self.get_all_layers()

        if not df.empty:
            df = df[df["LayerName"] != layer_name]

        new_rows          = []
        layer_id          = _uid(6)
        created_timestamp = _now()

        for item in material_items:
            mat_id = item.get("material_id")
            try:
                qty = float(item.get("quantity_used", 0))
                if qty <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return "Error", "All component material quantities must be positive numbers."

            match = rm_df[rm_df["MaterialId"] == mat_id]
            if match.empty:
                return "Error", f"Material identity token '{mat_id}' does not exist in inventory."

            new_rows.append({
                "LayerId":      layer_id,
                "LayerName":    layer_name,
                "MaterialId":   mat_id,
                "MaterialName": match.iloc[0]["Name"],
                "QuantityUsed": qty,
                "Unit":         match.iloc[0]["Unit"],
                "CreatedAt":    created_timestamp,
            })

        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        if self._write(self._layer_path, df):
            return "Success", f"Layer preset profile '{layer_name}' successfully committed."
        return "Error", "Failed to write database updates onto filesystem storage."

    def delete_layer(self, layer_name: str) -> tuple:
        df         = self.get_all_layers()
        layer_name = layer_name.strip().upper()
        mask       = df["LayerName"] == layer_name
        if not mask.any():
            return "Error", "Target custom configuration template layer not found."
        df = df[~mask].reset_index(drop=True)
        if self._write(self._layer_path, df):
            return "Success", f"Preset configuration context layer '{layer_name}' cleared."
        return "Error", "Write execution failure encountered while erasing the template layout row."

    def inject_layer_to_product(
        self, product_id: str, product_name: str, layer_name: str
    ) -> tuple:
        layers_df  = self.get_all_layers()
        layer_name = layer_name.strip().upper()
        target     = layers_df[layers_df["LayerName"] == layer_name]

        if target.empty:
            return "Error", f"Layer '{layer_name}' not found."

        template_layer_id = str(target.iloc[0]["LayerId"])

        bom_df = self._read(self._bom_path)
        for col, default in [("SourceType", "direct"), ("LayerId", ""), ("LayerName", "")]:
            if col not in bom_df.columns:
                bom_df[col] = default
            bom_df[col] = bom_df[col].fillna(default)

        if not bom_df.empty:
            existing_mask = (
                (bom_df["ProductId"] == product_id) &
                (bom_df["LayerId"]   == template_layer_id)
            )
            if existing_mask.any():
                bom_df = bom_df[~existing_mask].reset_index(drop=True)

        new_rows: list[dict] = []
        for _, row in target.iterrows():
            new_rows.append({
                "BOMId":        _uid(8),
                "ProductId":    product_id,
                "ProductName":  product_name,
                "MaterialId":   row["MaterialId"],
                "MaterialName": row["MaterialName"],
                "QuantityUsed": float(row["QuantityUsed"]),
                "Unit":         row["Unit"],
                "AddedAt":      _now(),
                "SourceType":   "layer",
                "LayerId":      template_layer_id,
                "LayerName":    layer_name,
            })

        bom_df = pd.concat([bom_df, pd.DataFrame(new_rows)], ignore_index=True)
        if self._write(self._bom_path, bom_df):
            n = len(new_rows)
            return "Success", f"Layer '{layer_name}' injected: {n} material(s) added to BOM."
        return "Error", "Could not save BOM."

    def get_all_products_cost_summary(self, products_df: pd.DataFrame) -> list[dict]:
        results = []
        if products_df is None or products_df.empty:
            return results

        for _, row in products_df.iterrows():
            pid        = str(row["ProductId"])
            pname      = str(row["Name"])
            try:
                sale_price = float(row.get("Rate", 0) or 0)
            except (ValueError, TypeError):
                sale_price = 0.0

            cost       = self.calculate_product_cost(pid)
            final      = cost["final_total_cost"]
            margin     = round(sale_price - final, 2)
            margin_pct = round((margin / sale_price * 100) if sale_price else 0.0, 2)

            results.append({
                "product_id":        pid,
                "product_name":      pname,
                "sale_price":        sale_price,
                "raw_material_cost": cost["raw_material_cost"],
                "total_custom_cost": cost["total_custom_cost"],
                "base_total":        cost["base_total"],
                "warranty_pct":      cost["warranty_pct"],
                "warranty_cost":     cost["warranty_cost"],
                "after_warranty":    cost["after_warranty"],
                "labour_pct":        cost["labour_pct"],
                "labour_cost":       cost["labour_cost"],
                "final_total_cost":  final,
                "margin":            margin,
                "margin_pct":        margin_pct,
                "raw_material_lines": cost["raw_material_lines"],
                "custom_cost_lines":  cost["custom_cost_lines"],
                "layer_breakdown":    cost["layer_breakdown"],
            })

        return results
