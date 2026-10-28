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
            raise LocalError("这个文件夹正在更新，请等待另一个更新窗口完成。") from exc
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
            raise LocalError("找不到 Excel 模板。请解压整个下载包后重新运行。")
        try:
            with workbook.open("xb") as destination, template.open("rb") as source:
                shutil.copyfileobj(source, destination)
        except FileExistsError:
            pass
        print("已创建 Portfolio.xlsx（初始现金 10,000 USD，可自行修改）。")
    return workbook


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_closed(workbook: Path) -> None:
    if workbook.with_name("~$" + workbook.name).exists():
        raise LocalError("请先保存并关闭 Portfolio.xlsx，再运行更新。")


def update(root: Path) -> Path:
    import yfinance as yf
    from robo_advisor.config import load_project_config
    from robo_advisor.excel_frontend import read_inputs, simulate, write_results
    from robo_advisor.market_data import MarketData, load_fx_snapshot, load_price_snapshot

    workbook = prepare(root)
    require_closed(workbook)
    before = fingerprint(workbook)
    config = load_project_config(root / "config" / "assets.json")
    inputs = read_inputs(workbook, config["assets"])
    local = root / "local_data"
    market_dir = local / "market"
    market_dir.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(local / "yfinance"))
    price_path = market_dir / "etf_prices.parquet"
    fx_path = market_dir / "fx_rates.parquet"
    refresh_prices = inputs.refresh_prices or not price_path.exists()
    refresh_fx = inputs.refresh_fx or not fx_path.exists()
    if refresh_prices:
        print("正在下载 ETF 日收盘价，首次下载历史数据可能需要几分钟……", flush=True)
    else:
        print("使用本文件夹已下载的 ETF 数据。", flush=True)
    prices = load_price_snapshot(price_path, refresh_prices, list(config["assets"]),
                                 config["requested_start_date"])
    if refresh_fx:
        print("正在下载汇率……", flush=True)
    else:
        print("使用本文件夹已下载的汇率数据。", flush=True)
    fx = load_fx_snapshot(fx_path, refresh_fx, config["requested_start_date"])
    market = MarketData(prices, fx)
    ledger, history, cash, holdings = simulate(inputs, market)

    # Never write calculations over the user's input until the entire run succeeds.
    with tempfile.TemporaryDirectory(prefix="update-", dir=local) as staging:
        staged = Path(staging) / "Portfolio.xlsx"
        shutil.copy2(workbook, staged)
        write_results(staged, inputs, market, ledger, history, cash, holdings, config["assets"])
        require_closed(workbook)
        if fingerprint(workbook) != before:
            raise LocalError("更新期间 Excel 内容发生变化，已取消写入。请保存关闭后重新更新。")
        backups = local / "backups"
        backups.mkdir(exist_ok=True)
        backup = backups / f"Portfolio-{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx"
        shutil.copy2(workbook, backup)
        os.replace(staged, workbook)
        for old in sorted(backups.glob("Portfolio-*.xlsx"), reverse=True)[5:]:
            try:
                old.unlink()
            except OSError:
                logging.warning("Could not remove old backup %s", old.name)
    print(f"更新完成：估值日 {history[-1]['date']}，组合价值 USD {history[-1]['nav']:,.2f}。")
    print("现在可以打开 Portfolio.xlsx 查看结果和使用时间滑块。")
    print("本次更新前的 Excel 已备份到 local_data/backups（保留最近 5 份）。")
    return workbook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="初始化或更新本地 Excel 投资组合")
    parser.add_argument("action", choices=("setup", "update"))
    args = parser.parse_args(argv)
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
                prepare(root)
                print("初始化完成。请打开 Portfolio.xlsx 填写资金和交易。")
                print("保存并关闭 Excel 后，双击 2_Update。第一次更新需要联网下载行情和汇率。")
            else:
                update(root)
        return 0
    except Exception as exc:
        logging.exception("Local %s failed", args.action)
        print(f"\n未完成：{exc}", file=sys.stderr)
        print("未将本次计算结果写入 Excel。请修正问题后重试。", file=sys.stderr)
        print("日期、资金和交易填写要求见 README；详细原因见 local_data/last_update.log。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
