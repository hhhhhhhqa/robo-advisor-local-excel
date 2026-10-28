# Changelog

## v1.1.0-beta.3 — 2026-10-28

- Show current cash at the top; Buy, Sell and Exchange automatically update each currency balance.
- Put editable starting amounts in Initial cash, B19:B23. Migrate old cash layouts on successful calculation without replaying trades against a calculated balance.
- Include the revised layout in the fresh template, with Update required before the first calculation.
- Translate prompts, errors and documentation into English; add a worked tutorial and complete file reference.
- Publish a clean package excluding personal workbooks, caches, backups, logs and installed runtimes.

## v1.1.0-beta.2 — 2026-10-28

- Fix temporary result-workbook links that could cause repair prompts on repeated imports.
- Move status messages above the button, show chart axes, use straight line segments and refresh the date marker locally.
- Verify cached calculation, user-requested market updates and error recovery in native Mac Excel.

## v1.1.0-beta.1 — 2026-10-28

- Add the in-workbook Update button and automatic cached calculation after input edits.
- Separate explicit market downloads from ordinary local calculation.

## v1.0.0 — 2026-10-28

- Package the upstream Excel simulation for independent local use with one-time setup and external update/recalculation entry points.
