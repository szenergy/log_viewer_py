"""Shared loading helpers for TDMS and CSV sources."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.tdms_reader import get_tdms_structure, read_tdms_file


@dataclass
class LoadedSource:
    """In-memory representation of a loaded file."""

    source_id: str
    path: str
    kind: str
    display_name: str
    payload: Any
    structure: Dict[str, Any]
    sample_rate: float = 1.0
    x_channel: Optional[tuple[str, str]] = None  # (group_name, channel_name)


@dataclass
class SeriesRef:
    """Reference to a specific channel in a loaded source, representing a plotted series."""

    source_id: str
    group: str
    channel: str
    series_id: str = ""
    filter_channel: Optional[tuple[str, str]] = None  # (group_name, channel_name)
    filter_value: float = 0.0

    def __post_init__(self):
        if not self.series_id:
            self.series_id = uuid.uuid4().hex[:8]


def load_data_source(filepath: str) -> LoadedSource:
    """Load a TDMS, CSV, or Excel file into a normalized source object."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    extension = os.path.splitext(filepath)[1].lower()
    source_id = uuid.uuid4().hex[:10]
    display_name = os.path.basename(filepath)

    if extension == ".tdms":
        tdms_file = read_tdms_file(filepath)
        structure = get_tdms_structure(tdms_file)
        return LoadedSource(
            source_id=source_id,
            path=filepath,
            kind="tdms",
            display_name=display_name,
            payload=tdms_file,
            structure=structure,
        )

    if extension == ".csv":
        frame = pd.read_csv(filepath)
        structure = _build_csv_structure(filepath, frame)
        return LoadedSource(
            source_id=source_id,
            path=filepath,
            kind="csv",
            display_name=display_name,
            payload=frame,
            structure=structure,
        )

    if extension in (".xlsx", ".xls"):
        sheets_dict = pd.read_excel(filepath, sheet_name=None)
        structure = _build_xlsx_structure(filepath, sheets_dict)
        return LoadedSource(
            source_id=source_id,
            path=filepath,
            kind="xlsx",
            display_name=display_name,
            payload=sheets_dict,
            structure=structure,
        )

    raise ValueError(f"Unsupported file type: {filepath}")


def _build_xlsx_structure(filepath: str, sheets_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Create a GUI-friendly summary for XLSX/XLS files."""
    groups = []

    for sheet_name, frame in sheets_dict.items():
        group_name = str(sheet_name)
        group_entry: Dict[str, Any] = {
            "name": group_name,
            "properties": {
                "source_type": "xlsx",
                "rows": int(frame.shape[0]),
                "columns": [str(c) for c in frame.columns],
            },
            "channels": [],
        }

        for column_name in frame.columns:
            col_str = str(column_name)
            numeric_values = pd.to_numeric(frame[column_name], errors="coerce")
            valid_values = numeric_values.dropna()
            if valid_values.empty:
                min_value = None
                max_value = None
            else:
                min_value = float(valid_values.min())
                max_value = float(valid_values.max())

            group_entry["channels"].append(
                {
                    "name": col_str,
                    "properties": {},
                    "length": int(len(frame[column_name])),
                    "min": min_value,
                    "max": max_value,
                }
            )
        groups.append(group_entry)

    return {
        "file_properties": {
            "source_type": "xlsx",
            "sheets": [str(s) for s in sheets_dict.keys()],
        },
        "groups": groups,
    }



def _build_csv_structure(filepath: str, frame: pd.DataFrame) -> Dict[str, Any]:
    """Create a GUI-friendly summary for CSV files."""
    group_name = os.path.splitext(os.path.basename(filepath))[0] or "CSV Data"
    group_entry: Dict[str, Any] = {
        "name": group_name,
        "properties": {
            "source_type": "csv",
            "rows": int(frame.shape[0]),
            "columns": list(frame.columns),
        },
        "channels": [],
    }

    for column_name in frame.columns:
        numeric_values = pd.to_numeric(frame[column_name], errors="coerce")
        valid_values = numeric_values.dropna()
        if valid_values.empty:
            min_value = None
            max_value = None
        else:
            min_value = valid_values.min()
            max_value = valid_values.max()

        group_entry["channels"].append(
            {
                "name": str(column_name),
                "properties": {},
                "length": int(len(frame[column_name])),
                "min": min_value,
                "max": max_value,
            }
        )

    return {
        "file_properties": {
            "source_type": "csv",
            "rows": int(frame.shape[0]),
            "columns": list(frame.columns),
        },
        "groups": [group_entry],
    }


def get_source_label(source: LoadedSource) -> str:
    """Return a compact label for the loaded-files list."""
    x_desc = "Index" if source.x_channel is None else f"{source.x_channel[0]}/{source.x_channel[1]}"
    return f"{source.display_name} [{source.kind.upper()}] (dt={source.sample_rate:.3g}s, X={x_desc})"


def _get_raw_channel_data(source: LoadedSource, group_name: str, channel_name: str) -> Optional[np.ndarray]:
    """Retrieve raw Y-values for a channel without alignment or filtering."""
    if source.kind == "tdms":
        try:
            channel = source.payload[group_name][channel_name]
            return np.asarray(channel.data)
        except Exception:
            return None
    elif source.kind == "csv":
        try:
            return pd.to_numeric(source.payload[channel_name], errors="coerce").to_numpy(dtype=float)
        except Exception:
            return None
    elif source.kind == "xlsx":
        try:
            df = source.payload.get(group_name)
            if df is None:
                for k, v in source.payload.items():
                    if str(k) == group_name:
                        df = v
                        break
            if df is None:
                return None

            col_key = None
            for col in df.columns:
                if str(col) == channel_name:
                    col_key = col
                    break
            if col_key is None:
                return None

            return pd.to_numeric(df[col_key], errors="coerce").to_numpy(dtype=float)
        except Exception:
            return None
    return None


def get_channel_data(
    source: LoadedSource,
    group_name: str,
    channel_name: str,
    filter_channel: Optional[tuple[str, str]] = None,
    filter_value: float = 0.0
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Return x/y data for the requested channel, aligned and filtered."""
    y_raw = _get_raw_channel_data(source, group_name, channel_name)
    if y_raw is None or len(y_raw) == 0:
        return None

    # Load X-axis raw data
    x_raw = None
    if source.x_channel is not None:
        x_group, x_chan = source.x_channel
        x_raw = _get_raw_channel_data(source, x_group, x_chan)

    # Align X and Y raw data
    if x_raw is None or len(x_raw) == 0:
        x_values = np.arange(len(y_raw)) * getattr(source, "sample_rate", 1.0)
        y_values = y_raw
    else:
        min_len = min(len(x_raw), len(y_raw))
        x_values = x_raw[:min_len]
        y_values = y_raw[:min_len]

    # Apply filter if configured
    if filter_channel is not None:
        f_group, f_chan = filter_channel
        f_raw = _get_raw_channel_data(source, f_group, f_chan)
        if f_raw is not None and len(f_raw) > 0:
            min_len = min(len(x_values), len(f_raw))
            x_values = x_values[:min_len]
            y_values = y_values[:min_len]
            f_aligned = f_raw[:min_len]

            # Generate filter mask (matching the configured filter value)
            f_mask = np.isclose(f_aligned, filter_value)
            x_values = x_values[f_mask]
            y_values = y_values[f_mask]

    # Filter invalid/non-numeric values
    mask = np.isfinite(x_values) & np.isfinite(y_values)
    if not np.any(mask):
        return None

    x_res = x_values[mask]
    y_res = y_values[mask]

    # Shift X axis so the first remaining point starts at X=0
    if filter_channel is not None and len(x_res) > 0:
        x_res = x_res - x_res[0]

    return x_res, y_res


def get_filter_mask(
    source: LoadedSource,
    group_name: str,
    channel_name: str,
    filter_value: float,
    filter_channel: Optional[tuple[str, str]] = None,
    filter_val: float = 0.0
) -> Optional[np.ndarray]:
    """Return a boolean mask for samples that match the requested filter value, aligned with the configured X axis."""
    aligned = get_channel_data(source, group_name, channel_name, filter_channel, filter_val)
    if aligned is None:
        return None
    _, y_values = aligned
    return np.isclose(y_values, filter_value)