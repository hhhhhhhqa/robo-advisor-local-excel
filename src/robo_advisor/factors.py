from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .config import FACTOR_SOURCES, RAW_FF3_DIR

MONTH_PATTERN = re.compile(r"^\d{6}$")


def parse_factor_csv_text(
    text: str,
    factor_model: str,
    region: str,
    source_dataset: str = "Fama/French 3 Factors",
) -> pd.DataFrame:
    lines = text.replace("\ufeff", "").splitlines()
    header_index = None
    for index, line in enumerate(lines):
        normalized = line.replace(" ", "").upper()
        if "MKT-RF" in normalized and "SMB" in normalized and "HML" in normalized and "RF" in normalized:
            header_index = index
            break
    if header_index is None:
        raise ValueError(f"Could not locate monthly FF3 header for {factor_model}")

    header = [part.strip().upper().replace(" ", "") for part in lines[header_index].split(",")]
    aliases = {"MKT-RF": "Mkt_RF", "SMB": "SMB", "HML": "HML", "RF": "RF"}
    positions = {}
    for source_name, output_name in aliases.items():
        try:
            positions[output_name] = header.index(source_name)
        except ValueError as exc:
            raise ValueError(f"Missing {source_name} column in {factor_model} header: {header}") from exc

    records = []
    for line in lines[header_index + 1 :]:
        parts = [part.strip() for part in line.split(",")]
        if not parts or not MONTH_PATTERN.fullmatch(parts[0]):
            if records:
                break
            continue
        if len(parts) <= max(positions.values()):
            raise ValueError(f"Malformed monthly FF3 row for {factor_model}: {line!r}")
        try:
            values = [pd.to_numeric(parts[positions[name]], errors="raise") for name in ["Mkt_RF", "SMB", "HML", "RF"]]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid factor value in {factor_model}: {line!r}") from exc
        records.append([parts[0], *values])
    if not records:
        raise ValueError(f"No YYYYMM monthly rows found for {factor_model}")

    frame = pd.DataFrame(records, columns=["source_period", "Mkt_RF", "SMB", "HML", "RF"])
    for column in ["Mkt_RF", "SMB", "HML", "RF"]:
        frame.loc[frame[column].le(-99), column] = np.nan
        frame[column] = frame[column] / 100.0
    period = pd.PeriodIndex(frame["source_period"], freq="M")
    frame.insert(0, "factor_model", factor_model)
    frame.insert(1, "region", region)
    frame.insert(2, "source_dataset", source_dataset)
    frame.insert(3, "month", period.astype(str))
    frame.insert(4, "observation_month_end", period.to_timestamp(how="end").normalize())
    return frame


def process_factor_sources() -> pd.DataFrame:
    processed = []
    for factor_model, source in FACTOR_SOURCES.items():
        csv_path = RAW_FF3_DIR / f"{factor_model.lower()}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Required FF3 raw source is missing: {csv_path}")
        text = csv_path.read_text(encoding="utf-8-sig", errors="replace")
        processed.append(parse_factor_csv_text(text, factor_model, source["region"], source["source_dataset"]))
    factors = pd.concat(processed, ignore_index=True)
    return factors.sort_values(["factor_model", "month"], kind="stable").reset_index(drop=True)
