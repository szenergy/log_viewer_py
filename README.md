# SZEnergy Log Viewer

A powerful, interactive desktop application designed for visualizing and comparing TDMS, XLSX, and CSV telemetry logs.
Made by SZEnergy team for Shell Eco-Marathon.

- **Repository**: [https://github.com/varma02/szenergy_log_viewer](https://github.com/varma02/szenergy_log_viewer)
- **Downloads**: Standalone executables for Linux and Windows are available on the [Latest Releases Page](https://github.com/varma02/szenergy_log_viewer/releases/latest).

---

## Key Features

### 📂 Multi-Format Log Loading

- Supports loading National Instruments **TDMS** , Microsoft Excel **XLSX**, and standard **CSV** files.

### 📊 Advanced Dual-Axis Plotting

- **Independent Scales**: Plot data on the **Left Y-axis** or **Right Y-axis** to compare signals of completely different magnitudes (e.g., vehicle speed in km/h next to motor current in Amperes).
- **Synchronized Zoom & Pan**: Scroll the mouse wheel to zoom, middle-click and drag to pan, or right-click and drag to stretch. Both axes scale proportionally and update tick marks in real-time.

### 🧭 Interactive Tracking Cursor & Tooltip

- Hover your mouse over the graph to bring up a vertical tracking line.
- A single, color-coded **Consolidated Tooltip Box** follows your cursor, displaying the exact X-axis coordinate alongside the corresponding values of all active curves.

### 📐 Coordinate Calibration (Scale & Offset)

- Align mismatched data manually to perform direct overlays.
- Double-click on any loaded file in the file list to change its coordinate calibration.

### 🔍 Channel Options (Local Offsets & Filters)

- Double-click any plotted channel in the assignment list or select multiple channels and click **Channel Options** to configure: Filter Channel & Value, Local Y-Axis Offset or Local X-Axis Offset
- **Cross-File Compatibility**: Batch-filtering and options configuration work seamlessly across files by dynamically matching channel names.

### 🗂️ Channel Assignment Tabs

- **Surf Mode**: The first tab called **surf** dynamically plots whatever channels are selected in the sidebar tree view. Perfect for rapid data exploration.
- **Custom Assignment Tabs**: Click the **+** button in the top-right to create new custom tabs (inheriting channels from the current tab). Switching tabs even restores the exact pan position and zoom state on the graph.

### 🧮 Visible-Range Global Statistics

- Add, edit, or delete configured statistics in the collapsible right sidebar.
- Computes metrics dynamically for all active channels within the current visible viewport range.
- **Pre-processing Filters**: Specify a min/max value filter and a multiplier to apply to the channel data prior to transformation.
- **Transformation Operations**: Compute first derivative (raw and smoothed), or difference.
- **Aggregation Types**: Minimum, Maximum, Average, Median, Integral, Net Change, Standard Deviation.

### 🌗 Theme-Aware Styles & Collapsible Sidebars

- **Theme-Aware Styles**: Fully responsive Qt stylesheet utilizing native color palette variables. Seamlessly supports light and dark system modes (e.g., Fedora KDE dark mode) without text or background rendering glitches.
- **Collapsible Sidebars**: Slide both the left file tree panel and the right statistics panel open or closed with convenient sidebar toggle buttons.

### 💾 Session Persistence

- The application automatically saves your entire workspace configuration on close and restores it when started again.
- On startup, if a previously loaded log file is missing, the application prompts you to either **Replace/Locate** or **Ignore** it.

---

## How to Use SZEnergy Log Viewer

### 1. Loading Files

1.  Click **Load Files** at the bottom-left corner of the window.
2.  Select one or multiple TDMS, XLSX, or CSV files.
3.  Upon loading, a configuration window will pop up prompting you for an initial X multiplier, X offset, and X-axis channel.

### 2. Quick Exploration (Surf Mode)

1.  Select the **Surf** tab .
2.  Click channels in the **loaded file structure tree** to plot them on the left Y-axis.

### 3. Plotting

1.  Select channels in the file structure tree.
2.  Click **Add Selected To Left** or **Add Selected To Right** to add them to the respective axis.

### 4. Creating Custom Tabs

1.  Click the **+** button in the top-right corner to create a new tab.
2.  The new tab will inherit all channels from the current tab.
3.  Double-click on the tab to rename.

### 4. Customizing Channel Options & Offsets

1.  Double-click any plotted channel in the left or right axis lists, or select multiple channels and click **Channel Options**.
2.  Set local X/Y offsets, or select a filter channel and value.

### 5. Managing Global Statistics

1.  Expand the right sidebar (if collapsed).
2.  Click **Add Stat** to configure a new metric. Double-click any statistic row to edit, or select and click **Delete Stat** to remove.

### 6. Keyboard and Mouse Controls

- **Zoom**: Scroll the mouse wheel up or down.
- **Pan**: Hold **Ctrl** and drag with the left mouse button, or click and drag with the middle mouse button.
- **Stretch**: Hold the right mouse button and drag horizontally or vertically.
- **Fit to selection**: Hold the left mouse button and drag the rectangle around the area to zoom into. Press the **Escape** key to cancel.
- **Reset View**: Click the **A** icon in the bottom-left of the plot to reset zoom.

---

## Configuration Paths

Session states are saved to:

- **Windows**: `%APPDATA%\SZEnergy\Log_viewer\state.json`
- **Linux/macOS**: `~/.config/SZEnergy/Log_viewer/state.json`

---

Created by SZEnergy team for Shell Eco-Marathon.

This project is licensed under the [MIT License](LICENSE).
