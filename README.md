# SZEnergy Log Viewer

A powerful, interactive desktop application designed for visualizing and comparing TDMS, XLSX and CSV telemetry logs.
Made by SZEnergy team for Shell Eco-Marathon.

- **Repository**: [https://github.com/varma02/szenergy_log_viewer](https://github.com/varma02/szenergy_log_viewer)
- **Downloads**: Standalone executables for Linux and Windows are available on the [Latest Releases Page](https://github.com/varma02/szenergy_log_viewer/releases/latest).

---

## Key Features

### 📂 Multi-Format Log Loading

- Supports loading National Instruments **TDMS** (`.tdms`), Microsoft **XLSX** (`.xlsx`) and standard **CSV** (`.csv`) files.

### 📊 Advanced Dual-Axis Plotting

- **Independent Scales**: Plot data on the **Left Y-axis** or **Right Y-axis** to compare signals of completely different magnitudes (e.g., vehicle speed in km/h next to motor current in Amperes).
- **Synchronized Zoom & Pan**: Scroll the mouse wheel to zoom, drag with left click to pan or right click to stretch. Both axes scale proportionally and update their tick marks in real-time, while maintaining their relative amplitude bounds.

### 🧭 Interactive Tracking Cursor

- Hover your mouse over the graph to bring up a vertical tracking line.
- A single, color-coded **Consolidated Tooltip Box** follows your cursor, displaying the exact X-axis coordinate alongside the corresponding values of all active curves.

### 📐 Coordinate Calibration (Scale & Offset)

- Align mismatched data manually to perform direct overlays.
- Double-click on any loaded file in the file list to change its coordinates:
  - **X-Axis Multiplier**: How much one unit of the log's selected X-axis corresponds to the actual X-axis on the graph.
  - **X-Axis Offset**: Shift the entire log forward or backward to match the start trigger of another log.
  - **X-Axis Channel**: Select a channel from the log to use as the X-axis instead of the default sample index.

### 🔍 Local Channel Filtering

- Double-click any plotted channel in the lists to apply an equality filter (e.g., plot motor acceleration only when `lap == 1`).
- **Auto Shift to Zero**: When a filter is active, the filtered segment automatically shifts so that the first valid point starts at `X = 0`, allowing you to overlay and compare transient/event phases directly.
- **Batch Filtering**: Select multiple channels in the plotted list and click **Set Filter for Selected** to configure filters for all of them at once.

### 🗂️ Channel Assignment Tabs

- Keep multiple independent plotting views active at the same time.
- Click the **+** button in the top-right to create a new tab.
  - New tabs inherit the parent tab's plotted channels and current zoom/panning coordinates.
- Double-click any tab header to rename it (e.g., "Amps & Acceleration", "Lap 1").
- Switching tabs automatically updates the plot and **restores the exact zoom and pan** coordinates you left that tab in.

---

## How to Use SZEnergy Log Viewer

### 1. Loading Files

1.  Click **Load Files** at the bottom-left corner of the window.
2.  Select one or multiple TDMS, XLSX or CSV files.
3.  Upon loading, a configuration window will pop up prompting you for an initial scale, offset, and custom X-axis channel (defaults to sample index if left blank).

### 2. Plotting Channels

1.  In the **file structure tree**, expand the loaded files and their groups to view individual channels.
2.  Select one or more channels.
3.  Click **Add Selected To Left** or **Add Selected To Right** at the bottom of the tree to plot them on the corresponding Y-axis.

### 3. Managing Plotted Channels

- **Remove Channels**: Select channels in the Left or Right axis lists under **Channel Assignment** and click **Remove Selected**.
- **Clear Graph**: Click **Clear Plot** to remove all plotted series in the active tab.
- **Configure Local Filters**: Double-click any plotted channel in the assignment list to specify a filter channel and value.

### 4. Navigating the Graph

- **Zoom**: Scroll the mouse wheel up or down to zoom in or out.
- **Pan**: Click and hold the left mouse button to drag the graph in any direction.
- **Stretch**: Click and hold the right mouse button to stretch the graph horizontally or vertically.
- **Reset View**: Click the little **A** icon in the bottom right corner to reset to the default view.

### 5. Using Tabs

- Click the **+** button in the top-right to create a new tab.
- Double-click any tab header to rename it.
- Switch between tabs to view different sets of plotted channels or different zoom/pan configurations.
- Use the **x** button in the top-right corner of each tab to close it.

---

This project is licensed under the [MIT License](LICENSE).
