# CUHK CDAS Robo-Advisor

This is a Final Year Project for the Computational Data Science at CUHK, focusing on the development of a robo-advisor for personalized portfolio construction and optimization.

The project aims to construct investment portfolios that achieve lower volatility while maintaining competitive risk-adjusted returns relative to the market benchmark.

The Fama–French Three-Factor Model serves as the baseline asset-pricing model. Building upon this framework, we explore additional factors, modeling techniques, and portfolio optimization methods to improve its ability to capture current market dynamics and enhance portfolio performance.

The final objective is to develop and evaluate a practical portfolio allocation framework that balances return and risk under different market conditions.

The baseline is the Fama-French three-factor model. The data pipeline downloads adjusted ETF prices from Yahoo Finance, downloads regional factor data from the Kenneth French Data Library, calculates daily and monthly returns, aligns observations without look-ahead, validates the result, and writes a monthly Parquet research dataset.

## Asset universe

The configured universe includes US large-cap, small-cap, value, and growth exposures; Europe, Japan, and emerging-market exposures; US aggregate bonds; gold; and 10 US equity sectors represented by the Select Sector SPDR ETFs:

`XLK`, `XLC`, `XLY`, `XLP`, `XLE`, `XLF`, `XLV`, `XLI`, `XLB`, and `XLU`.

The sector ETFs are currently mapped to `US_FF3` for consistent research features. This is a baseline mapping: the Fama-French factors do not capture every sector-specific risk.
The real-estate sector ETF was intentionally excluded because the factor construction universe treats REITs differently.

## Time and information conventions

The current universe consists of US-listed ETFs, so daily prices are normalized to `America/New_York` and returns are measured in USD. Monthly observations use the calendar-month label `YYYY-MM`, while `price_observation_date` records the actual last trading date used for that month.

For an ex-post FF3 regression, an asset's month-t return is matched with the month-t factors. For a portfolio backtest, the default assumption is that month-t factor information is available in month t+1, and decisions and holdings begin in month t+1. Factor release dates are not individually verified, so this is a conservative research convention rather than a claim about the exact publication time.

## Build the dataset

```bash
python scripts/build_data_pipeline.py
```

Use `--refresh` to replace local Yahoo Finance and Kenneth French snapshots. The generated files are intentionally ignored by Git and are written under `data/raw/` and `data/final/`.

## Excel trading and portfolio dashboard

The trading interface uses the same 19 US-listed, USD-quoted ETFs. Install the project, build the local ETF price snapshot once, then run:

```bash
python -m pip install -e .
python scripts/build_data_pipeline.py
PYTHONPATH=src python -m robo_advisor.excel_frontend
```

The command creates one workbook at `data/final/robo_advisor_dashboard.xlsx` on first use, then updates that same workbook on each run. The workbook has one visible **Dashboard** sheet containing starting cash, valuation date, price and FX refresh switches, trade entry, holdings, trade records, daily history, a portfolio value chart and a draggable time slider. The slider is an Excel form control and needs no macro.

The repository also includes a [populated Dashboard example](examples/excel/robo_advisor_dashboard_demo.xlsx) with 14 fictional trades and market data through 2026-09-29. It is a preview of the same one-sheet workflow; the active workbook remains `data/final/robo_advisor_dashboard.xlsx`.

Enter starting cash in USD, JPY, EUR, AUD and/or CNY. The optional valuation date is blank by default and then uses the latest cached ETF close. Set the annual risk-free rate as a decimal, such as `0.04` for 4%. **Update ETF prices** and **Update FX rates** accept Yes or No independently. No uses local snapshots without requesting market data. Yes downloads completed daily Yahoo Finance closes to Excel-specific caches; the first FX refresh is needed before using non-USD cash or trades. The existing research price snapshot seeds the Excel cache and is not modified.

Enter trades in the table on the Dashboard in date order. Same-day entries run from top to bottom:

| Date | Action | ETF | Shares / amount | Cash currency | To currency |
| --- | --- | --- | ---: | --- | --- |
| 2026-08-27 | Buy | SPY | 2 | USD | |
| 2026-08-28 | Sell | SPY | 1 | USD | |
| 2026-08-28 | Exchange | | 500 | USD | JPY |

Buy/Sell quantity is a positive whole number of ETF shares; the cash currency is debited or credited. Exchange quantity is the amount of source-currency cash to convert, and the destination currency must differ. ETFs execute at their USD close. A non-USD cash balance is translated at the daily FX rate for USD valuation. No short sales or negative cash are allowed.

Drag the slider above the chart to move between trading days. The highlighted point on the curve and **Metrics as of** date move with it, and portfolio value, return, annualized Sharpe and drawdown update for that day. Portfolio value includes ETF holdings and all cash translated into USD. Return starts from the first displayed date. Sharpe uses daily USD returns, the configured risk-free rate and 252 trading days; it is unavailable with fewer than two returns or zero volatility. Maximum drawdown is the largest decline from a prior peak. ETF prices must exist on trade dates; FX uses the latest rate on or before the date, at most five calendar days old. This is an end-of-day simulation and excludes dividends, fees and spreads. It does not place orders.
