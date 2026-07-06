# TDMS Graph Explorer

TDMS Graph Explorer is a desktop tool for working with TDMS test data.

## Features

- Multi-file browser with group/channel tree and channel min/max preview
- Multi-channel plotting with separate left/right axis assignment
- Series management (add/remove/clear plotted channels)
- Load and compare multiple TDMS and CSV files in one session
- Unload individual loaded files or clear all sources at once
- Value-based data filter:
  - choose one channel as filter source,
  - set a numeric value,
  - plot only samples where filter channel equals that value
- Status bar messages for user actions
- CLI conversion of TDMS to Excel (one sheet per TDMS group)

## Requirements

- Python 3.10+
- Linux/Windows/macOS

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The App

Start the GUI:

```bash
python main.py --gui
```

Start GUI and open a file immediately:

```bash
python main.py --gui test_data/Test_17_06_2026_05_46_54.tdms
```

## How To Use (GUI)

1. Click Load Files and select one or more .tdms or .csv files.
2. In the left tree, expand the file and group nodes, then select one or more channels.
3. Click Add Selected To Left or Add Selected To Right.
4. Remove channels with Remove From Left/Right, unload individual files from the Loaded Files list, or reset with Clear Plot / Clear All.

### Apply a filter

1. In the tree, select exactly one channel to use as the filter channel.
2. Click Use as Filter.
3. In Data Filter, enter a numeric value.
4. Click Apply Filter.

Only samples where the selected filter channel equals the entered value are plotted for that source.

To remove filtering, click Clear Filter.

## Convert TDMS To Excel (CLI)

Basic conversion:

```bash
python main.py test_data/Test_17_06_2026_05_46_54.tdms
```

Set output path:

```bash
python main.py test_data/Test_17_06_2026_05_46_54.tdms -o output/converted.xlsx
```

Verbose conversion output:

```bash
python main.py test_data/Test_17_06_2026_05_46_54.tdms -v
```

If -o is not provided, the output file is created under output/ with the TDMS base filename.
