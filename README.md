# Local Excel Portfolio Tracker

An Excel portfolio dashboard that runs on your own computer. Download a copy, run Setup once, and record ETF trades and currency exchanges in desktop Microsoft Excel. Each person's workbook, data and calculations are independent.

**Trade edits calculate automatically from local data. Only you decide when to download new asset prices and FX rates by clicking Update.** There are no scheduled market downloads or market requests on workbook open.

**Final release: v1.1.0.** Current cash balances are now at the top: Buy reduces cash, Sell adds cash, and Exchange reduces one currency and increases the other. Initial cash has its own editable section. Application messages and documentation are in English.

[Download the complete ZIP](https://github.com/hhhhhhhqa/robo-advisor-local-excel/releases/download/v1.1.0/robo-advisor-local-excel-v1.1.0.zip) · [Release notes](https://github.com/hhhhhhhqa/robo-advisor-local-excel/releases/tag/v1.1.0) · [Worked tutorial](docs/TUTORIAL.md) · [Every file explained](docs/FILES.md)

## Requirements

- Desktop Microsoft Excel for Windows or Mac, with macros enabled for this workbook. Excel for the web, mobile Excel, Google Sheets and Apple Numbers do not run this integration.
- Internet for the first Setup and whenever **you** choose Update. Once data is cached, entering trades and calculating results can work offline.
- A writable local folder containing the **entire extracted package**. No GitHub account, Git installation or separately installed Python is required for ordinary use.

Native Excel behavior has been tested on Mac. Windows setup and Python workflows are covered by automated CI; Windows native Excel UI behavior has not been tested. See [validation details](VALIDATION.md).

## Download and first setup

1. Download the ZIP above. Alternatively, open the [release page](https://github.com/hhhhhhhqa/robo-advisor-local-excel/releases/tag/v1.1.0) and select `robo-advisor-local-excel-v1.1.0.zip` under **Assets**. GitHub's green **Code > Download ZIP** downloads the current source instead of a numbered release; it also contains the setup files, but the release ZIP is easier to identify and share.
2. Extract the **whole ZIP** into a folder you intend to keep. Do not run files inside the ZIP or copy only an Excel template out of the folder.
3. Mac: double-click `1_Setup.command`. Windows: double-click `1_Setup.cmd`. Wait for **Setup completed**. Setup installs a private Python environment and dependencies, then creates `Portfolio.xlsm`. On Mac it also installs a small Excel-to-Python bridge for your account. **Setup does not download prices or FX rates.**
4. Open the generated **`Portfolio.xlsm` in the main folder** and enable macros for this trusted workbook. Files under `examples/excel` are templates or previews.
5. Enter starting amounts in the yellow **Initial cash** cells, `B19:B23`. USD 10,000 is a starting example; change it before recording your own portfolio. Use non-negative amounts, whole yen for JPY, and at most two decimal places for the other currencies. At least one amount must be positive.
6. Click **Update** yourself to download initial market data. The first historical download may take a few minutes. Wait for the success message at the upper right, then save.

Before the first market download, **Update required** in Current cash and a missing-cache message are expected. Setup completion does not mean market data has been downloaded.

If macOS blocks the setup file, check its source and use that file's **Open Anyway** option in System Settings > Privacy & Security. Do not disable Gatekeeper globally. If a `.command` file lacks execution permission, open Terminal in the extracted folder and run `chmod +x *.command`, then retry. If Windows flags a trusted download, review its file properties and your organization's policy. Do not disable antivirus or Excel's global macro protections. Managed computers may require administrator help.

## Daily use: calculation versus Update

| Action | What happens | Downloads market data? |
| --- | --- | --- |
| Run `1_Setup` | Install or repair the runtime; create a workbook if missing | No; software installation itself needs internet |
| Open Excel or edit initial cash, dates or trades | Calculate holdings, cash, history, metrics and chart from the cache | No |
| Click **Update** in Excel | Download prices and FX rates, calculate, and save | Yes, at your request |
| Run external `2_Update` with Excel closed | Download prices and FX rates, then calculate | Yes, at your request |
| Run external `3_Recalculate` with Excel closed | Calculate from the existing cache | No |
| Move the date slider | Display historical metrics and move the chart marker | No |

Finish editing a row and wait about two seconds. The status reports calculation, followed by success or a specific error. An incomplete row can briefly produce an error while you type; completing it triggers another calculation. Unsaved edits are included, but save Excel as usual to keep your work.

**Update is always a user action.** Automatic calculation never silently fetches missing data. Correct the input or choose Update yourself. One Update can make multiple requests for the configured ETFs and currencies; it is not a single API call. There is no built-in API key or promise of unlimited requests.

## Dashboard reference

| Location | Meaning | How to use it |
| --- | --- | --- |
| `B4:B8` — **Current cash** | Remaining USD, JPY, EUR, AUD and CNY after trades through the valuation date | Automatic output; do not overwrite the formulas |
| `B19:B23` — **Initial cash** | Cash before the first recorded trade | Yellow input cells; set before entering trades |
| `E3` | Valuation date | Blank means latest cached ETF day; a chosen date needs available closing data |
| `E4` | Annual risk-free rate | Enter `0.04` or `4%`, for example |
| `A27:F226` | Trade entry | Up to 200 rows, oldest first; same-day rows execute top to bottom |
| `E8:E15` | Selected date and portfolio metrics | Follow the date slider |
| `E17:E18` | ETF and FX cache coverage | Check these dates rather than assuming today's closing prices are available |
| `H1:M2` | Calculation status | Read this first if results seem unchanged |
| `H26:M...` | ETF holdings | Positions at the valuation date |
| `H49:L54` | Cash detail | Currency balances, FX observations and USD equivalents |
| Row 230 onward | Calculated trade ledger | Execution prices, cash debits/credits and remaining shares |
| Row 439 onward | Daily history | Portfolio values and performance used by the chart |

The input columns are **Date, Action, ETF, Shares / amount, Cash currency, To currency**. Use actual Excel dates covered by the cached US ETF trading calendar. Weekends and holidays without a close are not accepted, including for exchanges in this simulation. The valuation date cannot precede any entered trade.

| Date | Action | ETF | Shares / amount | Cash currency | To currency |
| --- | --- | --- | ---: | --- | --- |
| 2026-10-20 | Buy | SPY | 1 | USD | |
| 2026-10-21 | Sell | SPY | 1 | USD | |
| 2026-10-22 | Exchange | | 1000 | USD | JPY |

For **Buy/Sell**, enter positive whole shares and a payment/receipt currency; leave To currency empty. For **Exchange**, leave ETF empty, enter the amount of source currency to convert, and choose a different destination currency. Negative cash, overselling and fractional shares are rejected. The 19 supported US-listed ETFs are listed in [config/assets.json](config/assets.json).

The [worked tutorial](docs/TUTORIAL.md) explains expected results, corrections, starting your own portfolio and restoring backups.

## Calculation conventions

This is an end-of-day simulation. It does not connect to a broker or place orders. You enter transactions; the application computes history from those records and cached prices/FX. Editing an old transaction recalculates the affected history.

ETFs execute at their USD close. Cash debits/credits use whole yen for JPY and two decimals for other currencies, with half-up rounding. FX uses the most recent observation on or before the relevant date, no more than five calendar days old. Future FX is not used. Dividends, fees and bid/ask spreads are excluded.

Portfolio value includes ETFs and cash translated to USD. Return starts at the first displayed date. Sharpe uses daily USD returns, the entered risk-free rate and 252 trading days; insufficient observations or zero volatility produce `n.a.`. Maximum drawdown is the worst decline from an earlier peak. The slider changes historical metrics and the chart marker; Current cash and holdings remain valuation-date results.

Market data comes from Yahoo Finance through `yfinance`. ETF downloads exclude the unfinished New York trading day; FX excludes the current UTC day. Provider limits, outages and historical coverage apply. The workbook cannot value an ETF before its available trading history.

## Errors, backups and recovery

**RESULTS NOT CURRENT** means the displayed outputs do not reflect the present inputs. The last valid results remain visible, so a visible number does not prove that the new calculation succeeded. Read the reason, correct the input, or deliberately Update if more data is needed.

| Message or symptom | What to check |
| --- | --- |
| `Missing local ... Click Update` | Setup did not download market data. Choose Update when ready. |
| `no ETF close` / `No ETF close` | Weekend/holiday, date outside cache, or ETF without a price on that day. |
| `insufficient ... cash` | Source currency and cash available before this row. |
| `insufficient ... shares` | Earlier purchases and quantity being sold. |
| `FX rate is stale` | FX coverage; decide whether to Update. |
| `Run 1_Setup once` | Run Setup for your operating system to repair the environment. |
| Cash does not change | Complete the row, including Cash currency; check dates, wait, and read the status. |
| Button does nothing | Enable macros for this file. Alternatively, save/close Excel and run `2_Update` or `3_Recalculate`. |

Calculation uses temporary files and imports completed results. Downloads are staged before replacing market caches. Failed calculations do not replace the working workbook with partial results. Automatic input backups are in `local_data/backups` (latest five); diagnostics are in `local_data/last_update.log`. Backups are input snapshots, not a substitute for saved copies.

To restore, close Excel, keep a copy of the current workbook, copy a chosen backup into the main tool folder, and name the restored copy `Portfolio.xlsm`. Reopen and verify its inputs. The tutorial includes the full procedure.

## Sharing and upgrading

Share the **original release ZIP or download link**. Each person extracts and runs Setup once. A lone `Portfolio.xlsm` does not contain the Python functions. Do not share your working folder when you intend to exclude your own transactions, cache, backups and logs.

`Portfolio.xlsm`, `local_data/`, `.venv/`, `.runtime/` and `.tools/` are local-only and excluded from Git and release ZIPs. There is no portfolio-upload feature. Market requests send instrument requests to the data provider.

To move an existing portfolio into this release, extract it into a **new folder** and run Setup. Copy starting amounts into the new Initial cash cells and paste only the six trade-input columns, `A27:F226`, from the old workbook. Do not overwrite the new workbook with an old `.xlsm`, which also restores old macros. Optionally copy `local_data/market` into the new folder and run `3_Recalculate` with Excel closed to reuse data. Keep the old folder as a backup. Setup can import legacy `Portfolio.xlsx`; its old cash layout migrates on the first successful calculation. Rerunning Setup never resets an existing `Portfolio.xlsm`.

After moving the whole folder, rerun Setup at the new location. See [the file reference](docs/FILES.md) for working files, templates, runtime files and developer tools.

## Development and provenance

Based on [winstonFang05/cuhk-cdas-robo-advisor](https://github.com/winstonFang05/cuhk-cdas-robo-advisor), upstream commit `53743116b40cc2638620acded8f4d44cfc725405`. [ATTRIBUTION.md](ATTRIBUTION.md) records the source acknowledgement. This repository contains only the local Excel application and its supporting files. Upstream did not declare a separate license; this distribution does not invent one.

Developers can run `uv sync --extra test` and `uv run pytest -q`. VBA source is in `excel_button/`; tests extract and compare the embedded project with that source. After editing VBA or the fresh-workbook layout, run `python scripts/build_workbook.py`. This developer-only rebuild requires Go and pinned [ovba-writer](https://github.com/kay-ws/ovba-writer); ordinary users need neither. `scripts/package_release.py` packages tracked distribution files and rejects local/private data. CI covers setup and Python behavior on macOS and Windows. See [VALIDATION.md](VALIDATION.md) and [CHANGELOG.md](CHANGELOG.md).
