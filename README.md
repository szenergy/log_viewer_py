# TDMS viewer and converter

This repository contains a small Python utility that can convert TDMS files into Excel sheets and also view and plot TDMS data.

## Current State

- Implemented: reading TDMS files with `nptdms`.
- Implemented: extracting all groups and channels.
- Implemented: writing each TDMS group to its own Excel sheet (one sheet per group).
- Implemented: column headers using channel names.
- Implemented: verbose progress indicators for extraction and write phases.
- Implemented: Qt GUI shell for browsing and plotting TDMS data.

## Files of interest

- [src/tdms_reader.py](src/tdms_reader.py) — TDMS reading and data extraction
- [src/excel_writer.py](src/excel_writer.py) — Excel workbook creation and writing
- [src/converter.py](src/converter.py) — Conversion orchestration and progress
- [main.py](main.py) — CLI entry point

## Dependencies

Use a Python virtual environment and install dependencies from:

```bash
python3 -m venv .venv
source .venv/bin/activate.fish   # or `.venv/bin/activate` for bash/zsh
pip install -r requirements.txt
```

## Usage

Basic conversion:

```bash
python main.py test_data/Test_17_06_2026_05_46_54.tdms
```

Verbose mode (shows progress bars):

```bash y
python main.py test_data/Test_17_06_2026_05_46_54.tdms -v
```

Launch the Qt GUI browser:

```bash
python main.py --gui
```

You can also preload a file in the GUI:

```bash
python main.py --gui test_data/Test_17_06_2026_05_46_54.tdms
```

By default the output Excel file is written to the `output/` directory with the same base filename.
