from __future__ import annotations

from pathlib import Path

from src.data_sources import get_source_label, load_data_source


def test_load_csv_source(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("time,value\n0,1.5\n1,2.5\n2,3.5\n", encoding="utf-8")

    source = load_data_source(str(csv_path))

    assert source.kind == "csv"
    assert source.display_name == "sample.csv"
    assert source.structure["groups"][0]["name"] == "sample"
    assert source.structure["groups"][0]["channels"][1]["max"] == 3.5
    assert get_source_label(source) == "sample.csv [CSV]"


def test_load_unsupported_extension(tmp_path: Path) -> None:
    text_path = tmp_path / "sample.txt"
    text_path.write_text("hello", encoding="utf-8")

    try:
        load_data_source(str(text_path))
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported file type")
