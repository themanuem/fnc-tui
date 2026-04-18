"""Read various file formats into pandas DataFrames."""

import csv
import io
import json
import re
from pathlib import Path

import pandas as pd

_SUPPORTED = {".csv", ".json", ".xlsx", ".xls", ".md"}

_MD_TABLE_ROW = re.compile(r"^\|(.+)\|$")
_MD_SEPARATOR = re.compile(r"^[\s|:?-]+$")


def read_file(path: Path) -> pd.DataFrame:
    """Read a file into a DataFrame, dispatching by extension."""
    path = Path(path)
    ext = path.suffix.lower()
    readers = {
        ".csv": _read_csv,
        ".json": _read_json,
        ".xlsx": _read_xlsx,
        ".xls": _read_xlsx,
        ".md": _read_md_table,
    }
    reader = readers.get(ext)
    if reader is None:
        supported = ", ".join(sorted(_SUPPORTED))
        raise ValueError(f"Unsupported file format '{ext}'. Supported: {supported}")
    return reader(path)


def _read_csv(path: Path) -> pd.DataFrame:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(raw[:4096])
        sep = dialect.delimiter
    except csv.Error:
        sep = ","
    return pd.read_csv(io.StringIO(raw), sep=sep, encoding_errors="replace")


def _read_json(path: Path) -> pd.DataFrame:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return pd.json_normalize(data)
        return pd.DataFrame(data)
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return pd.json_normalize(v)
        return pd.json_normalize([data])
    raise ValueError("JSON must be an array of objects or an object with an array field")


def _read_xlsx(path: Path) -> pd.DataFrame:
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise ImportError(
            "openpyxl is required for .xlsx files. "
            "Install it with: uv pip install openpyxl"
        ) from None
    return pd.read_excel(path, engine="openpyxl")


def _read_md_table(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    header: list[str] | None = None
    rows: list[list[str]] = []
    for line in lines:
        m = _MD_TABLE_ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if header is None:
            header = cells
            continue
        if _MD_SEPARATOR.match(m.group(1)):
            continue
        rows.append(cells)
    if header is None:
        raise ValueError("No markdown table found in file")
    return pd.DataFrame(rows, columns=header)
