from __future__ import annotations

import json
import logging
import platform
import zipfile
from datetime import datetime, timezone
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

import requests

from .config import FACTOR_SOURCES, METADATA_DIR, RAW_FF3_DIR
from .utils import atomic_write_json, sha256_file

LOGGER = logging.getLogger(__name__)


def _download_archive(url: str, timeout: int = 60) -> bytes:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "robo-advisor-fyp/0.1"})
    response.raise_for_status()
    if not response.content.startswith(b"PK"):
        raise RuntimeError(f"Expected ZIP content from {url}; received {response.headers.get('content-type')}")
    return response.content


def download_factor_sources(refresh: bool = False) -> dict:
    metadata_path = METADATA_DIR / "factor_snapshot.json"
    all_local = all(
        (RAW_FF3_DIR / f"{model.lower()}.zip").exists()
        and (RAW_FF3_DIR / f"{model.lower()}.csv").exists()
        for model in FACTOR_SOURCES
    )
    if not refresh and all_local and metadata_path.exists():
        LOGGER.info("Using complete local Kenneth French raw snapshot")
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    files: dict[str, dict[str, str]] = {}
    for model, source in FACTOR_SOURCES.items():
        stem = model.lower()
        zip_path = RAW_FF3_DIR / f"{stem}.zip"
        csv_path = RAW_FF3_DIR / f"{stem}.csv"
        if refresh or not (zip_path.exists() and csv_path.exists()):
            LOGGER.info("Downloading Kenneth French monthly factors: %s", model)
            try:
                content = _download_archive(source["url"])
                zip_path.write_bytes(content)
                with zipfile.ZipFile(BytesIO(content)) as archive:
                    candidates = [name for name in archive.namelist() if name.lower().endswith((".csv", ".txt"))]
                    if not candidates:
                        raise RuntimeError(f"No CSV/TXT member found in {source['url']}")
                    raw_text = archive.read(candidates[0])
                csv_path.write_bytes(raw_text)
            except Exception as exc:
                raise RuntimeError(
                    f"Missing required FF3 raw source {model} ({source['url']}): {exc}. "
                    "No factor data were fabricated; downstream processing stopped."
                ) from exc
        else:
            LOGGER.info("Using local Kenneth French raw snapshot: %s", model)
        files[model] = {
            "region": source["region"],
            "source_dataset": source["source_dataset"],
            "url": source["url"],
            "zip_path": str(zip_path),
            "csv_path": str(csv_path),
            "zip_sha256": sha256_file(zip_path),
            "csv_sha256": sha256_file(csv_path),
        }
    metadata = {
        "download_or_reuse_timestamp_utc": datetime.now(timezone.utc),
        "data_source": "Kenneth R. French Data Library",
        "python_version": platform.python_version(),
        "requests_version": version("requests"),
        "sources": files,
    }
    atomic_write_json(metadata, metadata_path)
    return metadata
