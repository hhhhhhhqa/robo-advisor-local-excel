# Step-by-step tutorial

These fictional transactions record a local simulation. They do not place real orders or exchange real money.

## 1. Open your working workbook

Download the [complete release ZIP](https://github.com/hhhhhhhqa/robo-advisor-local-excel/releases/download/v1.1.0-beta.3/robo-advisor-local-excel-v1.1.0-beta.3.zip), extract it, and run `1_Setup.command` on Mac or `1_Setup.cmd` on Windows. Open the generated `Portfolio.xlsm` in the main folder and enable macros for this file.

There is one Dashboard sheet. Current cash at the upper left is automatic. Initial cash below it is the yellow input table. Update, the date slider and chart are on the right. Trade entry starts at row 27.

Setup installs software but not market data. Click **Update** yourself to fetch initial prices/FX, wait for the success message and save. Before that, Update required and missing-cache messages are expected. A network/provider failure may require retrying later; editing transactions does not trigger downloads.

## 2. Set initial cash

Enter these starting amounts in the yellow cells `B19:B23`:

| Currency | Starting amount |
| --- | ---: |
| USD | 10000.00 |
| JPY | 0 |
| EUR | 0.00 |
| AUD | 0.00 |
| CNY | 0.00 |

Leave valuation date `E3` empty to use the latest cached ETF day, and leave `E4` at 0% for this exercise. With no trades, successful calculation should show USD 10,000 in Current cash and zero for other currencies.

Initial cash means amounts **before the first recorded transaction**. Do not replace these with the remaining cash after each trade; that would count transactions again. Read remaining balances from Current cash.

## 3. Buy one SPY share

Fill row 27. The date must be an Excel date, not a plain-text label.

| Cell | Enter | Meaning |
| --- | --- | --- |
| A27 | 2026-10-20 | A US trading day covered by the cache |
| B27 | Buy | Purchase |
| C27 | SPY | Configured ETF symbol |
| D27 | 1 | One whole share |
| E27 | USD | Pay from USD cash |
| F27 | Leave empty | Not used for Buy/Sell |

Finish the row, wait about two seconds and read the status at `H1`. In the market snapshot tested on October 28, 2026, the purchase debits **USD 769.05**, leaves **USD 9,230.95** and creates **one SPY share**. At the October 27 close, the share is worth USD 769.66 and portfolio value is USD 10,000.61. Provider revisions and later downloads can change these illustrative figures; the balance must still reconcile to the trade ledger.

No Update is needed if the relevant data is already cached. You enter the trade; cash, holdings, metrics and chart update automatically.

## 4. Sell the share

Fill row 28:

| Date | Action | ETF | Shares / amount | Cash currency | To currency |
| --- | --- | --- | ---: | --- | --- |
| 2026-10-21 | Sell | SPY | 1 | USD | |

After calculation, the tested sale adds **USD 773.09**, leaving **USD 10,004.04** and zero SPY shares. The holding disappears when its quantity reaches zero, while history retains the period you held it.

Selling two shares would fail because you bought only one. The status would show RESULTS NOT CURRENT and preserve the last valid output. Correcting the quantity to one calculates again automatically.

## 5. Exchange USD into JPY

Fill row 29. ETF must be empty.

| Date | Action | ETF | Shares / amount | Cash currency | To currency |
| --- | --- | --- | ---: | --- | --- |
| 2026-10-22 | Exchange | | 1000 | USD | JPY |

The amount means **USD to give up**, not yen to receive. The program uses the trade-date cached FX observation to calculate the destination amount. In the tested snapshot, Current cash becomes:

| Currency | Balance after all three rows |
| --- | ---: |
| USD | 9004.04 |
| JPY | 158132 |
| EUR | 0.00 |
| AUD | 0.00 |
| CNY | 0.00 |

USD decreases by exactly 1,000 and JPY increases by the calculated whole-yen amount. At the tested October 27 FX rate, total portfolio value is **USD 10,007.87**. It differs from the immediate post-sale value because the yen's USD value changes after conversion. Currency balances are in their own units; the portfolio headline translates everything to USD.

To observe automatic recalculation, change `D29` temporarily from 1000 to 500. The example's balances become **USD 9,504.04 and JPY 79,066**. Change it back to 1000 and confirm the prior balances return. Do not change Initial cash for this exercise.

To exchange back later, add a new dated Exchange row, leave ETF empty, enter the number of **yen** to exchange, choose JPY as Cash currency and USD as To currency. Use whole yen and no more than the available balance before that row.

## 6. Review history and choose when to Update

Move the slider above the chart. Metrics as of, portfolio value, return, Sharpe, drawdown and the highlighted point follow the selected date. Current cash and holdings remain valuation-date results.

Check `E17:E18` for cache coverage. When you want newer prices/FX, click Update yourself, wait for success and save. A successful request does not guarantee today's close exists; holidays, market hours and publication delays matter.

For edits within the cache, finish typing and let local calculation run. If a date has no price, check for a weekend or holiday first. **October 25, 2026 is a Sunday and is unsuitable for this example.**

## 7. Start your own portfolio

Save a separate copy of the exercise if you want it. Clear only the example inputs in `A27:F29`, set your own amounts in Initial cash, and enter transactions oldest first. Keep Current cash formulas and calculated outputs intact. Keep the working workbook inside the tool folder.

Use the action, ETF and currency dropdowns. Buy/Sell needs an ETF, whole shares and a cash currency. Exchange needs an empty ETF cell and both currencies. Optional cells must really be empty; do not type a dash or the words "blank" or "leave empty".

Editing an old transaction rebuilds history from the starting amounts. The application does not discover broker transactions automatically. Save Excel regularly.

## 8. Handle errors and restore backups

RESULTS NOT CURRENT means the visible outputs are from a previous valid calculation. Read the reason, complete the row or fix its date, currency or quantity, and allow the local retry. If data is missing, decide yourself whether to Update.

If macros are unavailable, save and close Excel. Run `2_Update` for an explicit market download and calculation, or `3_Recalculate` to calculate offline. Use `.command` on Mac and `.cmd` on Windows, then reopen `Portfolio.xlsm`.

To restore a backup:

1. Save and close Excel.
2. Make a separate copy of the current `Portfolio.xlsm` so you can undo restoration.
3. Select a timestamped file under `local_data/backups`.
4. Copy it into the main tool folder and rename the copied file `Portfolio.xlsm`.
5. Reopen it, enable its existing macros if prompted, and check Initial cash and transactions. Recalculate from the cache, or choose Update if you need newer data.

Backups are calculation-input snapshots, including unsaved edits at the time; the latest five automatic backups are kept. They belong to your local copy. Diagnostics are in `local_data/last_update.log`.
