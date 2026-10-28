# Validation record — v1.1.0-beta.3

Verified on October 28, 2026. All transactions below are fictional simulation inputs; no brokerage account or real order was involved. Published examples contain no personal portfolio data.

## Native Microsoft Excel on Mac

The preceding beta.2 validation covered automatic cached calculation, a user-requested real Yahoo Finance refresh through the button's assigned macro, repeated result imports, invalid-input recovery, historical metrics and the chart marker. The repaired workbook does not retain links to temporary result files. Button/slider bindings were inspected and their target functions executed. Direct coordinate clicking and dragging were not counted as verified because the coordinate service failed; keyboard/paste and AppleScript were used where needed.

The beta.3 cash-display change was tested in the installed local workbook using native Excel and its actual automatic Python calculation path:

| Check | Observed result |
| --- | --- |
| Initial USD 10,000; buy one SPY on October 20 | USD cash 9,230.95; one SPY share; October 27 NAV 10,000.61 |
| Sell that share on October 21 | USD cash/NAV 10,004.04; no SPY position |
| Exchange USD 1,000 for JPY on October 22 | USD 9,004.04 and JPY 158,132; October 27 NAV 10,007.87 |
| Revised layout with two fictional Buy rows and the USD 1,000 exchange | Top Current cash displays USD 7,460.95 and JPY 158,132, matching the existing cash-detail table; starting USD remains 10,000 in B19 |
| Change that exchange from USD 1,000 to USD 500 | Top balances automatically become USD 7,960.95 and JPY 79,066 |
| Restore the USD 1,000 exchange | Prior balances return without an Update click |
| Change initial USD from 10,000 to 11,000 | Automatic calculation increases USD cash and NAV by exactly 1,000; JPY remains unchanged |
| Restore initial USD 10,000, then save | Original inputs and balances restored; current-cash formulas, chart and status visible in native Excel |

ETF and FX cache hashes and modification times stayed unchanged during these local calculations. The user did not need to click Update for trade/initial-cash edits. The new layout was visually checked at normal Excel zoom. Current balances link to cash outputs rather than feeding back into starting inputs.

Example prices and FX amounts refer to the observed cache through October 27, 2026. Later provider revisions may change them.

## Automated and package checks

All 38 Python tests passed locally. The suite covers trade/FX arithmetic, invalid inputs, missing/stale data, independent copies, local-only calculation, backups, locks, concurrent edits, download failures, temporary-file isolation, removal of external links, macro-source consistency and chart/control parts. Cash tests repeat calculation and edit the separate initial amount to guard against applying transactions twice. A fresh-template test checks the new layout before data exists, then recalculates it twice from cached fixture data.

The release package is checked for personal-data exclusion, launcher permissions/line endings, setup without market downloads, repeat setup without resetting a workbook, missing-cache errors, and offline calculation using a separate fixture. Templates are scanned for non-English prompts and local user paths. The public macro template has no entered transactions or downloaded market data; the legacy demo is explicitly identified as a fictional upstream preview.

CI runs setup and Python tests on macOS and Windows. Native Windows Excel UI behavior has **not** been tested. Automated tests do not establish native Excel UI compatibility on an untested platform. See the repository's Actions page for the checks associated with the release commit.
