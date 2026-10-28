"""Excel-driven, end-of-day ETF trading simulation and monitoring."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import os
import shutil

import pandas as pd
from openpyxl import load_workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.axis import DateAxis
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.workbook.properties import CalcProperties
from openpyxl.styles import Alignment, Font, PatternFill

from .config import FINAL_DIR, PROJECT_ROOT, RAW_DIR, load_project_config
from .excel_controls import add_time_slider
from .market_data import FX_CURRENCIES, MarketData, load_fx_snapshot, load_price_snapshot
from .performance import Performance


TEMPLATE_PATH = PROJECT_ROOT / "examples" / "excel" / "robo_advisor_dashboard.xlsx"
DEFAULT_INPUT = FINAL_DIR / "robo_advisor_dashboard.xlsx"
DEFAULT_OUTPUT = DEFAULT_INPUT
DEFAULT_PRICES = RAW_DIR / "excel_etf_prices.parquet"
DEFAULT_PRICE_SEED = RAW_DIR / "etf_prices.parquet"
DEFAULT_FX = RAW_DIR / "fx_rates.parquet"
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Trade:
    row: int
    day: date
    action: str
    ticker: str | None
    quantity: Decimal
    currency: str
    to_currency: str | None = None


@dataclass(frozen=True)
class Inputs:
    cash: dict[str, Decimal]
    as_of: date | None
    risk_free: float
    refresh_prices: bool
    refresh_fx: bool
    trades: list[Trade]


def _money(value: Decimal | float | int, currency: str = "USD") -> Decimal:
    quantum = Decimal("1") if currency == "JPY" else CENT
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)


def _positive_amount(value: object, location: str, *, allow_zero: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{location} must be a numeric amount") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise ValueError(f"{location} must be {'non-negative' if allow_zero else 'positive'}")
    return result


def _date(value: object, location: str) -> date:
    try:
        stamp = pd.Timestamp(value)
        if pd.isna(stamp):
            raise ValueError("missing date")
        return stamp.date()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{location} must be a valid date") from exc


def _yes_no(value: object, location: str) -> bool:
    choice = str(value or "No").strip().lower()
    if choice not in {"yes", "no"}:
        raise ValueError(f"{location} must be Yes or No")
    return choice == "yes"


def read_inputs(path: Path, assets: dict, *, read_refresh_flags: bool = True) -> Inputs:
    book = load_workbook(path, read_only=True, data_only=True)
    if "Dashboard" not in book:
        raise ValueError("Expected one Dashboard sheet; use robo_advisor_dashboard.xlsx")
    settings = book["Dashboard"]
    cash = {}
    for row, currency in enumerate(FX_CURRENCIES, 4):
        amount = _positive_amount(settings.cell(row, 2).value or 0, f"Settings!B{row}", allow_zero=True)
        rounded = _money(amount, currency)
        if amount != rounded:
            raise ValueError(f"Settings!B{row}: {currency} cash has too many decimal places")
        cash[currency] = rounded
    if not any(cash.values()):
        raise ValueError("Enter a positive starting cash balance in Settings!B4:B8")
    as_of = _date(settings["E3"].value, "Dashboard!E3") if settings["E3"].value else None
    risk_free = float(_positive_amount(settings["E4"].value or 0, "Dashboard!E4", allow_zero=True))
    if risk_free >= 1:
        raise ValueError("Dashboard!E4 risk-free rate must be a decimal below 1, e.g. 0.04")
    refresh_prices = _yes_no(settings["E5"].value, "Dashboard!E5") if read_refresh_flags else False
    refresh_fx = _yes_no(settings["E6"].value, "Dashboard!E6") if read_refresh_flags else False

    trades = []
    sheet = book["Dashboard"]
    for row, values in enumerate(sheet.iter_rows(min_row=27, max_row=226, max_col=6, values_only=True), 27):
        if all(value is None or value == "" for value in values):
            continue
        day = _date(values[0], f"Dashboard!A{row}")
        action = str(values[1] or "").strip().title()
        if action not in {"Buy", "Sell", "Exchange"}:
            raise ValueError(f"Dashboard!B{row} must be Buy, Sell or Exchange")
        ticker = str(values[2] or "").strip().upper() or None
        quantity = _positive_amount(values[3], f"Dashboard!D{row}")
        currency = str(values[4] or "").strip().upper()
        to_currency = str(values[5] or "").strip().upper() or None
        if currency not in FX_CURRENCIES:
            raise ValueError(f"Dashboard!E{row} must be one of {FX_CURRENCIES}")
        if action == "Exchange":
            if ticker or to_currency not in FX_CURRENCIES or to_currency == currency:
                raise ValueError(f"Dashboard!C{row}/F{row}: Exchange needs no ETF and a different destination currency")
            if currency == "JPY" and quantity != quantity.to_integral_value():
                raise ValueError(f"Dashboard!D{row}: JPY exchange amount must be whole yen")
        else:
            if ticker not in assets or to_currency:
                raise ValueError(f"Dashboard!C{row}/F{row}: Buy/Sell needs a configured ETF and no destination currency")
            if quantity != quantity.to_integral_value():
                raise ValueError(f"Dashboard!D{row}: ETF shares must be whole numbers")
        trades.append(Trade(row, day, action, ticker, quantity, currency, to_currency))
    if trades != sorted(trades, key=lambda trade: trade.day):
        raise ValueError("Trades must be in date order; same-day rows run top to bottom")
    if as_of and any(trade.day > as_of for trade in trades):
        raise ValueError("A trade date is later than Dashboard!E3 (valuation date)")
    book.close()
    return Inputs(cash, as_of, risk_free, refresh_prices, refresh_fx, trades)


def _valuation(cash: dict[str, Decimal], holdings: dict[str, int], market: MarketData, day: date) -> tuple[float, float, float]:
    cash_usd = sum(float(amount) * market.usd_per_unit(day, currency)[0]
                   for currency, amount in cash.items() if amount)
    assets_usd = sum(shares * market.close(day, ticker) for ticker, shares in holdings.items() if shares)
    return cash_usd + assets_usd, cash_usd, assets_usd


def simulate(inputs: Inputs, market: MarketData) -> tuple[list[dict], list[dict], dict[str, Decimal], dict[str, int]]:
    if not market.price_dates:
        raise ValueError("ETF price cache is empty")
    end = inputs.as_of or market.price_dates[-1]
    if end not in market.price_dates:
        raise ValueError(f"No ETF close on valuation date {end}; select an available US trading date")
    if any(trade.day not in market.price_dates for trade in inputs.trades):
        bad = next(trade for trade in inputs.trades if trade.day not in market.price_dates)
        raise ValueError(f"Trades!A{bad.row}: no ETF close on {bad.day}")
    eligible = [day for day in market.price_dates if day <= end]
    first = inputs.trades[0].day if inputs.trades else eligible[max(0, len(eligible) - 252)]
    start_index = eligible.index(first)
    dates = eligible[max(0, start_index - 1):]
    cash = inputs.cash.copy()
    holdings: dict[str, int] = {}
    ledger: list[dict] = []
    history: list[dict] = []
    pending = iter(inputs.trades)
    trade = next(pending, None)
    baseline, _, _ = _valuation(cash, holdings, market, dates[0])
    if baseline <= 0:
        raise ValueError("Starting portfolio value must be positive")
    performance = Performance(inputs.risk_free)
    for day in dates:
        while trade and trade.day == day:
            source_rate, source_day = market.usd_per_unit(day, trade.currency)
            if trade.action == "Exchange":
                assert trade.to_currency is not None
                destination_rate, destination_day = market.usd_per_unit(day, trade.to_currency)
                debit = _money(trade.quantity, trade.currency)
                credit = _money(debit * Decimal(str(source_rate)) / Decimal(str(destination_rate)), trade.to_currency)
                if cash[trade.currency] < debit:
                    raise ValueError(f"Trades!D{trade.row}: insufficient {trade.currency} cash")
                cash[trade.currency] -= debit
                cash[trade.to_currency] += credit
                price = None
                fx_day = max(source_day, destination_day)
                usd_value = float(debit) * source_rate
            else:
                assert trade.ticker is not None
                price = market.close(day, trade.ticker)
                usd_value = float(trade.quantity) * price
                local_value = _money(Decimal(str(usd_value)) / Decimal(str(source_rate)), trade.currency)
                debit = local_value if trade.action == "Buy" else Decimal(0)
                credit = local_value if trade.action == "Sell" else Decimal(0)
                if trade.action == "Buy":
                    if cash[trade.currency] < debit:
                        raise ValueError(f"Trades!D{trade.row}: insufficient {trade.currency} cash")
                    cash[trade.currency] -= debit
                    holdings[trade.ticker] = holdings.get(trade.ticker, 0) + int(trade.quantity)
                else:
                    if holdings.get(trade.ticker, 0) < int(trade.quantity):
                        raise ValueError(f"Trades!D{trade.row}: insufficient {trade.ticker} shares")
                    cash[trade.currency] += credit
                    holdings[trade.ticker] -= int(trade.quantity)
                fx_day = source_day
            ledger.append({"date": day, "action": trade.action, "ticker": trade.ticker or "",
                           "quantity": float(trade.quantity), "currency": trade.currency,
                           "to_currency": trade.to_currency or "", "close_usd": price,
                           "usd_per_unit": source_rate, "fx_date": fx_day,
                           "usd_value": usd_value, "cash_debit": float(debit),
                           "cash_credit": float(credit),
                           "shares_after": holdings.get(trade.ticker, 0) if trade.ticker else None})
            trade = next(pending, None)
        nav, cash_usd, assets_usd = _valuation(cash, holdings, market, day)
        metrics = performance.add(nav)
        history.append({"date": day, "nav": nav, "cash_usd": cash_usd, "etf_usd": assets_usd,
                        **metrics})
    return ledger, history, cash, holdings


def _header(sheet, row: int, labels: list[str]) -> None:
    for col, label in enumerate(labels, 1):
        cell = sheet.cell(row, col, label)
        cell.fill = PatternFill("solid", fgColor="17324D")
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
    sheet.row_dimensions[row].height = 25


def write_results(input_path: Path, inputs: Inputs, market: MarketData,
                  ledger: list[dict], history: list[dict], cash: dict[str, Decimal],
                  holdings: dict[str, int], assets: dict, *, local_mode: bool = False) -> None:
    book = load_workbook(input_path)
    sheet = book["Dashboard"]
    sheet.sheet_view.showGridLines = False
    sheet.sheet_properties.tabColor = "17324D"
    sheet._charts.clear()
    for row in sheet.iter_rows(min_row=230, max_row=max(sheet.max_row, 230), max_col=max(sheet.max_column, 23)):
        for cell in row:
            cell.value = None
    for row in sheet.iter_rows(min_row=26, max_row=55, min_col=8, max_col=13):
        for cell in row:
            cell.value = None
    sheet["A1"] = "ETF trading and portfolio dashboard (USD)"
    sheet["A1"].font = Font(name="Arial", size=16, bold=True, color="17324D")
    sheet["H5"] = "Drag the slider to inspect each trading day"
    sheet["H5"].font = Font(name="Arial", size=10, color="17324D")
    sheet["D8"] = "Metrics as of"
    sheet["F8"] = len(history)
    sheet["F8"].number_format = ";;;"  # Linked index for the Excel form control.
    sheet["E8"] = f"=INDEX($A$440:$A${439+len(history)},$F$8)"
    sheet["E8"].number_format = "yyyy-mm-dd"
    sheet["E8"].fill = PatternFill("solid", fgColor="FFF2CC")
    metrics = [("Portfolio value (USD)", "B"), ("Return since start", "E"),
               ("Sharpe (daily, annualized)", "F"), ("Maximum drawdown", "G"),
               ("Current drawdown", "H"), ("Cash (USD value)", "C"),
               ("ETF holdings (USD)", "D")]
    for row, (label, column) in enumerate(metrics, 9):
        sheet.cell(row, 4, label)
        result = f"INDEX(${column}${440}:${column}${439+len(history)},MATCH($E$8,$A${440}:$A${439+len(history)},0))"
        sheet.cell(row, 5, f'=IFERROR(IF(ISNUMBER({result}),{result},"n.a."),"n.a.")')
        if row in (10, 12, 13):
            sheet.cell(row, 5).number_format = "0.0%"
        elif row in (9, 14, 15):
            sheet.cell(row, 5).number_format = '"$"#,##0.00'
        else:
            sheet.cell(row, 5).number_format = "0.00"
    sheet["A10"] = "Trade entry"
    sheet["D17"] = "ETF price cache through"
    sheet["E17"] = market.price_dates[-1]
    sheet["E17"].number_format = "yyyy-mm-dd"
    sheet["D18"] = "FX cache through (all four pairs)"
    if all(currency in market.fx for currency in FX_CURRENCIES if currency != "USD"):
        sheet["E18"] = min(market.fx[currency][-1][0] for currency in FX_CURRENCIES if currency != "USD")
        sheet["E18"].number_format = "yyyy-mm-dd"
    else:
        sheet["E18"] = "not loaded"
    sheet["D19"] = "Drag the slider above the chart to review historical metrics."
    sheet["D20"] = "Daily close simulation; fees, spreads and dividends are excluded."
    book.defined_names.add(DefinedName("MonitorDates",
        attr_text=f"'Dashboard'!$A$440:$A${439+len(history)}"))
    for validation in list(sheet.data_validations.dataValidation):
        if str(validation.sqref) == "E8":
            sheet.data_validations.dataValidation.remove(validation)

    chart = LineChart()
    chart.title = "Portfolio value (USD)"
    chart.y_axis.title = "USD"
    chart.x_axis.title = "Trading date"
    chart.style = 13
    chart.height = 6.5
    chart.width = 18
    chart.legend = None
    chart.x_axis = DateAxis(crossAx=100)
    chart.y_axis.crossAx = chart.x_axis.axId
    span_days = (history[-1]["date"] - history[0]["date"]).days
    if span_days <= 90:
        chart.x_axis.number_format = "d-mmm"
        chart.x_axis.majorTimeUnit = "days"
        chart.x_axis.majorUnit = 7
    else:
        chart.x_axis.number_format = "mmm-yy"
        chart.x_axis.majorTimeUnit = "months"
        chart.x_axis.majorUnit = 1 if span_days <= 365 else 3
    nav_values = [item["nav"] for item in history]
    nav_low, nav_high = min(nav_values), max(nav_values)
    padding = max((nav_high - nav_low) * 0.1, nav_high * 0.001)
    chart.y_axis.scaling.min = max(0, nav_low - padding)
    chart.y_axis.scaling.max = nav_high + padding
    chart.y_axis.numFmt = '"$"#,##0'
    chart.add_data(Reference(sheet, min_col=2, min_row=439, max_row=len(history)+439), titles_from_data=True)
    chart.add_data(Reference(sheet, min_col=9, min_row=439, max_row=len(history)+439), titles_from_data=True)
    chart.set_categories(Reference(sheet, min_col=1, min_row=440, max_row=len(history)+439))
    chart.series[0].graphicalProperties.line.solidFill = "17324D"
    chart.series[0].graphicalProperties.line.width = 25400
    chart.series[1].graphicalProperties.line.noFill = True
    chart.series[1].marker.symbol = "circle"
    chart.series[1].marker.size = 9
    chart.series[1].marker.graphicalProperties.solidFill = "E69138"
    chart.series[1].marker.graphicalProperties.line.solidFill = "E69138"
    sheet.add_chart(chart, "G8")

    _header(sheet, 26, ["Date", "Action", "ETF", "Shares / amount", "Cash currency", "To currency"])
    for col, label in enumerate(["ETF", "Name", "Shares", "Close USD", "Value USD", "Weight"], 8):
        sheet.cell(26, col, label)
        sheet.cell(26, col).fill = PatternFill("solid", fgColor="17324D")
        sheet.cell(26, col).font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        sheet.cell(26, col).alignment = Alignment(horizontal="center")
    end = history[-1]["date"]
    total = history[-1]["nav"]
    row = 27
    for ticker in assets:
        shares = holdings.get(ticker, 0)
        if not shares:
            continue
        close = market.close(end, ticker)
        values = [ticker, assets[ticker]["name"], shares, close, shares*close, shares*close/total]
        for col, value in enumerate(values, 8):
            sheet.cell(row, col, value)
        for col in (4, 5):
            sheet.cell(row, col+7).number_format = '"$"#,##0.00'
        sheet.cell(row, 13).number_format = "0.0%"
        row += 1
    for col, label in enumerate(["Currency", "Cash balance", "USD per unit", "USD value", "FX date"], 8):
        cell = sheet.cell(49, col, label)
        cell.fill = PatternFill("solid", fgColor="17324D")
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
    for idx, currency in enumerate(FX_CURRENCIES, 50):
        rate, rate_date = market.usd_per_unit(end, currency) if cash[currency] else (None, None)
        for col, value in enumerate((currency, float(cash[currency]), rate,
                                     float(cash[currency])*rate if rate else None, rate_date), 8):
            sheet.cell(idx, col, value)
        sheet.cell(idx, 9).number_format = "#,##0" if currency == "JPY" else "#,##0.00"
        sheet.cell(idx, 10).number_format = "0.000000"
        sheet.cell(idx, 11).number_format = '"$"#,##0.00'
        sheet.cell(idx, 12).number_format = "yyyy-mm-dd"

    _header(sheet, 230, ["Date", "Action", "ETF", "Shares / amount", "Cash currency",
                         "To currency", "ETF close USD", "USD per cash unit", "FX date",
                         "USD value", "Cash debit", "Cash credit", "Shares after"])
    for row, item in enumerate(ledger, 231):
        for col, key in enumerate(("date", "action", "ticker", "quantity", "currency", "to_currency",
                                   "close_usd", "usd_per_unit", "fx_date", "usd_value",
                                   "cash_debit", "cash_credit", "shares_after"), 1):
            sheet.cell(row, col, item[key])
        for col in (1, 9):
            sheet.cell(row, col).number_format = "yyyy-mm-dd"
        for col in (7, 10):
            sheet.cell(row, col).number_format = '"$"#,##0.00'
        sheet.cell(row, 8).number_format = "0.000000"
        for col, currency in ((11, item["currency"]), (12, item["to_currency"] or item["currency"])):
            sheet.cell(row, col).number_format = "#,##0" if currency == "JPY" else "#,##0.00"
    _header(sheet, 439, ["Date", "Portfolio value USD", "Cash USD", "ETFs USD",
                         "Return", "Sharpe", "Max drawdown", "Drawdown"])
    sheet["I439"] = "Selected value USD"
    for row, item in enumerate(history, 440):
        sheet.cell(row, 1, item["date"]).number_format = "yyyy-mm-dd"
        for col, key in enumerate(("nav", "cash_usd", "etf_usd", "return", "sharpe", "max_drawdown", "drawdown"), 2):
            sheet.cell(row, col, item[key])
            sheet.cell(row, col).number_format = "0.0%" if col in (5, 7, 8) else "#,##0.00"
        sheet.cell(row, 9, f"=IF(ROW()-439=$F$8,$B{row},NA())")
    sheet.freeze_panes = "A26"
    if local_mode:
        for address, text in {
            "D5": "Market data", "E5": "Manual Update", "D6": "Calculations", "E6": "Automatic (local)",
            "A15": "Trade edits calculate automatically using local data.",
            "H5": "Click Update to download prices and FX rates.",
        }.items():
            sheet[address] = text
        for address in ("E5", "E6"):
            sheet[address].fill = PatternFill(fill_type=None)
            sheet[address].font = Font(name="Arial", size=10, color="17324D")
        for validation in list(sheet.data_validations.dataValidation):
            if str(validation.sqref) in ("E5:E6", "E5", "E6"):
                sheet.data_validations.dataValidation.remove(validation)
        sheet.merge_cells("H6:M7")
        sheet["H6"] = "Calculated from local market data. Click Update for new prices / FX."
        sheet["H6"].alignment = Alignment(wrap_text=True, vertical="center")
        sheet["H6"].font = Font(name="Arial", size=10, color="17324D")
    book.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True, forceFullCalc=True)
    temp_path = input_path.with_name(input_path.stem + ".tmp.xlsx")
    book.save(temp_path)
    add_time_slider(temp_path, len(history))
    os.replace(temp_path, input_path)


def run_excel_frontend(input_path: Path = DEFAULT_INPUT, output_path: Path | None = None,
                       prices_path: Path = DEFAULT_PRICES, fx_path: Path = DEFAULT_FX) -> Path:
    if output_path is not None and output_path.resolve() != input_path.resolve():
        raise ValueError("All inputs and results live in the same Dashboard workbook")
    if input_path == DEFAULT_INPUT and not input_path.exists():
        input_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE_PATH, input_path)
    config = load_project_config()
    assets = config["assets"]
    inputs = read_inputs(input_path, assets)
    seed = DEFAULT_PRICE_SEED if prices_path == DEFAULT_PRICES else None
    prices = load_price_snapshot(prices_path, inputs.refresh_prices, list(assets),
                                 config["requested_start_date"], seed_path=seed)
    fx = load_fx_snapshot(fx_path, inputs.refresh_fx, config["requested_start_date"])
    market = MarketData(prices, fx)
    ledger, history, cash, holdings = simulate(inputs, market)
    write_results(input_path, inputs, market, ledger, history, cash, holdings, assets)
    return input_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Excel ETF trading and monitoring dashboard")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    print(run_excel_frontend(args.input))


if __name__ == "__main__":
    main()
