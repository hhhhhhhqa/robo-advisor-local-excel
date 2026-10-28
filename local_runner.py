"""Local-only distribution wrapper; portfolio mathematics remain in robo_advisor."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


class LocalError(Exception):
    """An actionable local workflow error."""


@contextmanager
def folder_lock(root: Path):
    """An OS lock is released automatically even after a crash."""
    local = root / "local_data"
    local.mkdir(parents=True, exist_ok=True)
    with (local / "update.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LocalError("This folder is already updating. Wait for the other update to finish.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def prepare(root: Path) -> Path:
    """Create a private working workbook without replacing an existing one."""
    workbook = root / "Portfolio.xlsx"
    template = root / "examples" / "excel" / "robo_advisor_dashboard.xlsx"
    if not workbook.exists():
        if not template.is_file():
            raise LocalError("Excel template not found. Extract the complete download package and try again.")
        try:
            with workbook.open("xb") as destination, template.open("rb") as source:
                shutil.copyfileobj(source, destination)
        except FileExistsError:
            pass
        print("Created Portfolio.xlsx with USD 10,000 starting cash. You can edit the starting amounts.")
    return workbook


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_closed(workbook: Path) -> None:
    if workbook.with_name("~$" + workbook.name).exists():
        raise LocalError(f"Save and close {workbook.name} before running an external update. The in-workbook button works while Excel is open.")


def calculate(root: Path, workbook: Path, output: Path, *, refresh: bool = False) -> list[dict]:
    from robo_advisor.config import load_project_config
    from robo_advisor.excel_frontend import read_inputs, simulate, write_results
    from robo_advisor.market_data import MarketData, load_fx_snapshot, load_price_snapshot

    config = load_project_config(root / "config" / "assets.json")
    inputs = read_inputs(workbook, config["assets"], read_refresh_flags=False)
    local = root / "local_data"
    market_dir = local / "market"
    market_dir.mkdir(parents=True, exist_ok=True)
    price_path = market_dir / "etf_prices.parquet"
    fx_path = market_dir / "fx_rates.parquet"
    if refresh:
        # This branch is reachable only from an explicit user Update action.
        import yfinance as yf
        yf.set_tz_cache_location(str(local / "yfinance"))
        print("Updating asset prices and FX rates at your request...", flush=True)
        with tempfile.TemporaryDirectory(prefix="market-", dir=local) as staging:
            staged_prices = Path(staging) / price_path.name
            staged_fx = Path(staging) / fx_path.name
            for source, target in ((price_path, staged_prices), (fx_path, staged_fx)):
                if source.exists():
                    shutil.copy2(source, target)
            prices = load_price_snapshot(staged_prices, True, list(config["assets"]),
                                         config["requested_start_date"])
            fx = load_fx_snapshot(staged_fx, True, config["requested_start_date"])
            # A failed API call leaves both previous cache files intact.
            for source, target in ((staged_prices, price_path), (staged_fx, fx_path)):
                os.replace(source, target)
    else:
        missing = [name for path, name in ((price_path, "asset prices"), (fx_path, "FX rates"))
                   if not path.is_file()]
        if missing:
            raise LocalError("Missing local " + " and ".join(missing) +
                             ". Click Update to download market data. Automatic calculation never downloads data.")
        print("Calculating from the local cache only. No market data requests.", flush=True)
        prices = load_price_snapshot(price_path, False, list(config["assets"]),
                                     config["requested_start_date"])
        fx = load_fx_snapshot(fx_path, False, config["requested_start_date"])
    market = MarketData(prices, fx)
    ledger, history, cash, holdings = simulate(inputs, market)
    if workbook != output:
        shutil.copy2(workbook, output)
    write_results(output, inputs, market, ledger, history, cash, holdings, config["assets"], local_mode=True)
    return history


def backup_input(root: Path, workbook: Path) -> None:
    backups = root / "local_data" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"Portfolio-{datetime.now():%Y%m%d-%H%M%S-%f}{workbook.suffix}"
    shutil.copy2(workbook, backup)
    for old in sorted(backups.glob("Portfolio-*.xls*"), reverse=True)[5:]:
        try:
            old.unlink()
        except OSError:
            logging.warning("Could not remove old backup %s", old.name)


def update(root: Path, *, refresh: bool = True) -> Path:
    workbook = root / "Portfolio.xlsm"
    if not workbook.exists():
        workbook = prepare(root)
    require_closed(workbook)
    before = fingerprint(workbook)
    local = root / "local_data"
    local.mkdir(exist_ok=True)

    # Never write calculations over the user's input until the entire run succeeds.
    with tempfile.TemporaryDirectory(prefix="update-", dir=local) as staging:
        staged = Path(staging) / "Portfolio.xlsx"
        shutil.copy2(workbook, staged)
        history = calculate(root, staged, staged, refresh=refresh)
        if workbook.suffix == ".xlsm":
            from workbook_button import attach_project
            macro_staged = Path(staging) / "Portfolio.xlsm"
            attach_project(staged, macro_staged, root)
            staged = macro_staged
        require_closed(workbook)
        if fingerprint(workbook) != before:
            raise LocalError("The workbook changed during calculation. Writing was cancelled. Save and close it, then try again.")
        backup_input(root, workbook)
        os.replace(staged, workbook)
    print(f"Completed: valuation date {history[-1]['date']}, portfolio value USD {history[-1]['nav']:,.2f}.")
    print(f"Open {workbook.name} to view the results and use the date slider.")
    print("The previous inputs were saved to local_data/backups. The latest five automatic backups are retained.")
    return workbook


def calculate_for_excel(root: Path, snapshot: Path | None = None, output: Path | None = None,
                        *, refresh: bool = False) -> Path:
    """Calculate a saved input copy while the real Excel workbook stays open."""
    local = root / "local_data"
    snapshot = snapshot or local / "button_input.xlsm"
    output = output or local / "button_result.xlsx"
    if snapshot.resolve() == output.resolve() or output.suffix != ".xlsx":
        raise LocalError("The input snapshot and output must be separate files. The output must use .xlsx format.")
    output.unlink(missing_ok=True)
    output.with_suffix(".error.txt").unlink(missing_ok=True)
    if not snapshot.is_file():
        raise LocalError("Input snapshot not found. Use the Update button in Portfolio.xlsm or edit a trade to calculate locally.")
    with tempfile.TemporaryDirectory(prefix="button-", dir=local) as staging:
        staged = Path(staging) / "result.xlsx"
        calculate(root, snapshot, staged, refresh=refresh)
        backup_input(root, snapshot)
        os.replace(staged, output)
    print("Calculation completed. Excel is importing the results.")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set up or update the local Excel portfolio")
    parser.add_argument("action", choices=("setup", "update", "recalculate", "excel-update", "excel-recalculate", "excel-button"))
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args(argv)
    if bool(args.snapshot) != bool(args.result) or (args.snapshot and not args.action.startswith("excel-")):
        parser.error("--snapshot and --result must be supplied together for an excel action")
    root = ROOT
    (root / "local_data").mkdir(exist_ok=True)
    logging.basicConfig(filename=root / "local_data" / "last_update.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    logging.captureWarnings(True)
    try:
        with folder_lock(root):
            if args.action == "setup":
                from robo_advisor.config import load_project_config
                load_project_config(root / "config" / "assets.json")
                from workbook_button import prepare_button_workbook, install_mac_helper
                prepare_button_workbook(root)
                install_mac_helper(root)
                print("Setup completed. Open Portfolio.xlsm and enable macros for this workbook.")
                print("Click Update yourself to download the initial market data. Trade edits calculate from cached data only.")
            elif args.action.startswith("excel-"):
                calculate_for_excel(root, args.snapshot, args.result,
                                    refresh=args.action in ("excel-update", "excel-button"))
            else:
                update(root, refresh=args.action == "update")
        return 0
    except Exception as exc:
        logging.exception("Local %s failed", args.action)
        if args.result:
            try:
                args.result.with_suffix(".error.txt").write_text(str(exc), encoding="utf-8")
            except OSError:
                logging.exception("Could not write the Excel error detail")
        print(f"\nNot completed: {exc}", file=sys.stderr)
        print("The calculation did not replace your workbook results. Correct the issue and try again.", file=sys.stderr)
        print("See README.md for input instructions and local_data/last_update.log for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
