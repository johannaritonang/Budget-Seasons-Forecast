"""Helpers for the Healthcare Distributor forecasting notebook.

`load()` cleans the raw invoice-line extract with the same rules as the Power BI model
(majority Durable/Disposable label per item, product groups, orders = customer + invoice date, order-size bands),
so the numbers reconcile with the dashboard. People are anonymised by default: sales reps become "Rep 01",
individual doctors become "Doctor 001", and institutions become "<segment> 001" in every table and chart.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- palette (brand green + neutrals, matches the Power BI report)
GREEN, GREEN_D, GREEN_L, AMBER, RED, PLUM, SLATE, INK, MUTED, LINE = (
    "#37B14A", "#1F7A33", "#BFE5C6", "#E8A33D", "#D9534F", "#8E5A9B", "#64748B", "#1E293B", "#64748B", "#E2E8F0")
SEGMENT_COLORS = {"Public hospitals & health offices": GREEN_D, "Private hospitals": GREEN, "Clinics & aesthetic chains": PLUM,
                  "Companies & resellers": AMBER, "Doctors (personal)": SLATE}
GROUP_COLORS = {"Aesthetic devices": GREEN_D, "Consumables": GREEN, "Pandemic response": AMBER}


def style_charts():
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#CBD5E1",
                         "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": INK, "axes.labelcolor": MUTED,
                         "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": "white", "axes.facecolor": "white"})


def rp(v, unit="B"):
    """Format rupiah: rp(2.5e9) -> 'Rp2.5B'."""
    div = {"B": 1e9, "M": 1e6}[unit]
    return f"Rp{v / div:,.1f}{unit}"


def find_workbook(folders):
    """First .xlsx in the given folders, preferring a name that mentions 'sales' or 'invoice'."""
    for folder in folders:
        folder = Path(folder)
        if folder.exists():
            files = sorted(f for f in folder.glob("*.xlsx") if not f.name.startswith("~$"))
            pref = [f for f in files if any(k in f.name.lower() for k in ("sales", "invoice"))]
            if pref or files:
                return (pref or files)[0]
    return None


# ---------------------------------------------------------------- customer segments (from the institution name)
PUBLIC = r"\bRSUD\b|\bRSUP\b|RUMAH SAKIT UMUM DAERAH|\bDINKES\b|DINAS KESEHATAN|\bBLUD\b|\bRUMKIT\b|\bBEND\b|BENDAHARA|PROVINSI|KABUPATEN|\bKAB\b|POLRI|BPKPB|PUSAT|KEMENTERIAN|DITJEN|RSUD,|, RSUD|\bRSU\b|RUMAH SAKIT KUSTA|PUSKESMAS"
HOSPITAL = r"\bRS\b|RUMAH SAKIT|\bRSIA\b|\bRSU\b|HOSPITAL"
CLINIC = r"KLINIK|CLINIC|GLOW|BEAUTY|SKIN|AESTHETIC|ESTETIK|DERMA|KECANTIKAN|COCOON|ERHA"


def segment(name, cls):
    if cls == "Personal":
        return "Doctors (personal)"
    n = re.sub(r"[.]", " ", str(name).upper())
    if re.search(PUBLIC, n):
        return "Public hospitals & health offices"
    if re.search(HOSPITAL, n):
        return "Private hospitals"
    if re.search(CLINIC, n):
        return "Clinics & aesthetic chains"
    return "Companies & resellers"


SEG_SHORT = {"Public hospitals & health offices": "Public", "Private hospitals": "Private hospital",
             "Clinics & aesthetic chains": "Clinic", "Companies & resellers": "Company", "Doctors (personal)": "Doctor"}

PANDEMIC = {"LEP3", "LV3", "WS3", "TK3", "IS3", "HY3", "APK"}


def load(path, anonymise=True):
    d = pd.read_excel(path, sheet_name=0)
    d.columns = [str(c).strip() for c in d.columns]
    d = d.rename(columns={"Item Category (Dura/Dispo)": "category_raw"})
    d["Invoice Date"] = pd.to_datetime(d["Invoice Date"]).dt.normalize()
    for c in ("Customer ID", "Inventory ID", "Salesman Name", "Customer Name"):
        d[c] = d[c].astype(str).str.strip()
    d["Customer Class"] = d["Customer Class"].astype(str).str.strip().str.title()

    # one Durable/Disposable label per item: the label used on most of its lines (ties -> the later label alphabetically)
    cnt = d.groupby(["Inventory ID", "category_raw"]).size().reset_index(name="n")
    maj = cnt.sort_values(["Inventory ID", "n", "category_raw"], ascending=[True, False, False]).drop_duplicates("Inventory ID")
    d = d.merge(maj[["Inventory ID", "category_raw"]].rename(columns={"category_raw": "category"}), on="Inventory ID", how="left")
    d["product_group"] = np.where(d["Item Brand"].isin(PANDEMIC), "Pandemic response",
                                  np.where(d.category == "Durable", "Aesthetic devices", "Consumables"))

    d["order_key"] = d["Customer ID"] + "|" + d["Invoice Date"].dt.strftime("%Y%m%d")
    d["order_amount"] = d.groupby("order_key")["Invoice Amount"].transform("sum")
    d["big_ticket"] = d.order_amount >= 500_000_000
    d["month"] = d["Invoice Date"].dt.to_period("M").dt.to_timestamp()
    d["segment"] = [segment(n, c) for n, c in zip(d["Customer Name"], d["Customer Class"])]
    # a customer keeps the segment of its first line, so every customer sits in exactly one segment
    d["segment"] = d.groupby("Customer ID").segment.transform("first")

    if anonymise:
        rank = d.groupby("Customer ID")["Invoice Amount"].sum().sort_values(ascending=False)
        seg = d.groupby("Customer ID").segment.first()
        labels, counters = {}, {}
        for cid in rank.index:
            s = SEG_SHORT[seg[cid]]
            counters[s] = counters.get(s, 0) + 1
            labels[cid] = f"{s} {counters[s]:03d}"
        d["customer"] = d["Customer ID"].map(labels)
        reps = d.groupby("Salesman Name")["Invoice Amount"].sum().sort_values(ascending=False)
        d["salesman"] = d["Salesman Name"].map({n: f"Rep {i + 1:02d}" for i, n in enumerate(reps.index)})
        d = d.drop(columns=["Customer Name", "Salesman Name"])
    else:
        d["customer"], d["salesman"] = d["Customer Name"], d["Salesman Name"]
    return d


# ---------------------------------------------------------------- forecasting helpers
def wape(actual, forecast):
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return np.abs(actual - forecast).sum() / np.abs(actual).sum()


def month_index(start, end):
    return pd.date_range(start, end, freq="MS")
