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


@dataclass(frozen=True)
class SeriesRef:
    """Reference to a specific channel in a loaded source."""

    source_id: str
    group: str
    channel: str


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
    return f"{source.display_name} [{source.kind.upper()}]"


def get_channel_data(source: LoadedSource, group_name: str, channel_name: str) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Return x/y data for the requested channel."""
    if source.kind == "tdms":
        try:
            channel = source.payload[group_name][channel_name]
            y_values = np.asarray(channel.data)
            if y_values.size == 0:
                return None
            x_values = np.arange(len(y_values))
            return x_values, y_values
        except Exception:
            return None

    if source.kind == "csv":
        try:
            series = pd.to_numeric(source.payload[channel_name], errors="coerce")
            values = series.to_numpy(dtype=float)
            mask = np.isfinite(values)
            if not np.any(mask):
                return None
            x_values = np.arange(len(values))[mask]
            y_values = values[mask]
            return x_values, y_values
        except Exception:
            return None

    if source.kind == "xlsx":
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

            series = pd.to_numeric(df[col_key], errors="coerce")
            values = series.to_numpy(dtype=float)
            mask = np.isfinite(values)
            if not np.any(mask):
                return None
            x_values = np.arange(len(values))[mask]
            y_values = values[mask]
            return x_values, y_values
        except Exception:
            return None

    return None


def get_filter_mask(source: LoadedSource, group_name: str, channel_name: str, filter_value: float) -> Optional[np.ndarray]:
    """Return a boolean mask for samples that match the requested filter value."""
    if source.kind == "tdms":
        try:
            values = np.asarray(source.payload[group_name][channel_name].data)
            if values.size == 0:
                return None
            return np.isclose(values, filter_value)
        except Exception:
            return None

    if source.kind == "csv":
        try:
            series = pd.to_numeric(source.payload[channel_name], errors="coerce")
            values = series.to_numpy(dtype=float)
            if values.size == 0:
                return None
            return np.isclose(values, filter_value)
        except Exception:
            return None

    if source.kind == "xlsx":
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

            series = pd.to_numeric(df[col_key], errors="coerce")
            values = series.to_numpy(dtype=float)
            if values.size == 0:
                return None
            return np.isclose(values, filter_value)
        except Exception:
            return None

    return None