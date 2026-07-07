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


def test_load_xlsx_source(tmp_path: Path) -> None:
    import pandas as pd
    from src.data_sources import get_channel_data

    xlsx_path = tmp_path / "sample.xlsx"
    df1 = pd.DataFrame({"time": [0, 1, 2], "temp": [20.5, 21.0, 22.5]})
    df2 = pd.DataFrame({"speed": [10, 20], "power": [100.0, 150.0]})

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df1.to_excel(writer, sheet_name="Sheet1", index=False)
        df2.to_excel(writer, sheet_name="Sheet2", index=False)

    source = load_data_source(str(xlsx_path))

    assert source.kind == "xlsx"
    assert source.display_name == "sample.xlsx"
    assert len(source.structure["groups"]) == 2

    # Verify Sheet1 group and channels
    g1 = source.structure["groups"][0]
    assert g1["name"] == "Sheet1"
    assert g1["channels"][0]["name"] == "time"
    assert g1["channels"][1]["name"] == "temp"
    assert g1["channels"][1]["max"] == 22.5

    # Verify Sheet2 group and channels
    g2 = source.structure["groups"][1]
    assert g2["name"] == "Sheet2"
    assert g2["channels"][0]["name"] == "speed"
    assert g2["channels"][1]["name"] == "power"
    assert g2["channels"][1]["max"] == 150.0

    # Test reading channel data
    data1 = get_channel_data(source, "Sheet1", "temp")
    assert data1 is not None
    x, y = data1
    assert list(x) == [0, 1, 2]
    assert list(y) == [20.5, 21.0, 22.5]

