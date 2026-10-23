# Forecasting the Budget Seasons · healthcare distributor

Python companion to the Power BI report *Big Tickets, Budget Seasons* (an Indonesian distributor of medical and aesthetic devices, invoice lines Jan 2019 – Mar 2022, IDR).
The dashboard shows that a few large public-hospital orders make up most of the revenue and arrive at year-end. This notebook measures the budget calendar,
tests how far revenue can be forecast, gives a forecast range for the next twelve months, and flags regular customers who are going quiet.

| Question | Method |
|---|---|
| Who buys, and when? | Customer segments from institution names; share of yearly revenue by calendar month |
| How well can revenue be forecast? | Rolling-origin backtest (13 origins, 3-month horizon): naive, seasonal naive, 12-month average, seasonal profile, ETS, SARIMA, LightGBM (global model) · WAPE and bias |
| What range should the plan use? | Monte Carlo: log-normal run-rate + Poisson-Gamma big tickets with the budget calendar · P10 / P50 / P90 and a coverage backtest |
| Which customers are going quiet? | Logistic regression on quarterly customer snapshots, tested on a later snapshot (out of time) · ROC AUC, lift by decile, "overdue regular" flag |

## Headline results
* Public hospitals and health offices: 7% of customers, 57% of revenue, 90% of it in orders of Rp500M+. They spend 0% in Jan–Feb and 59% in Aug, Nov and Dec.
* Monthly revenue cannot be forecast well from history (60% error at best on 3-month totals). The run-rate without big tickets can be (33–34%). LightGBM does not beat a 12-month average.
* Next 12 months: P50 Rp23.4B, 80% range Rp12.1B – Rp44.0B. The run-rate alone is Rp8.2B.
* The repeat-purchase model reaches ROC AUC 0.85 out of time. 59 regular customers are overdue today.

## Run it
```bash
pip install -r requirements.txt
jupyter notebook "Budget Seasons Forecast.ipynb"
```
Put the invoice workbook (.xlsx) in the data folder. It is not included: the data belongs to the company.
Customers and sales reps are anonymised in every output (`Public 001`, `Clinic 005`, `Doctor 014`, `Rep 03`). Every chart is saved to the images folder.

## Files
```
Budget Seasons Forecast/
├── Budget Seasons Forecast.ipynb   the analysis, with outputs
├── Budget Seasons Forecast.html    the same notebook as a static page
├── hdtools.py                      cleaning (same rules as the Power BI model), segments, anonymisation
├── requirements.txt
├── data/                           invoice workbook (not included)
└── images/                         key charts as PNG
```
