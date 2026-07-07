"""Qt application entry point for multi-source TDMS and CSV comparison."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from src.data_sources import LoadedSource, SeriesRef, get_channel_data, get_filter_mask, get_source_label, load_data_source


class FileLoaderThread(QThread):
    """Background worker thread to load files without blocking the GUI."""
    file_loaded = Signal(object)
    finished_loading = Signal()

    def __init__(self, file_paths: list[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file_paths = file_paths
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        for path in self.file_paths:
            if self._is_cancelled:
                break
            try:
                source = load_data_source(path)
                if self._is_cancelled:
                    break
                self.file_loaded.emit(source)
            except Exception as exc:
                if self._is_cancelled:
                    break
                self.file_loaded.emit((path, str(exc)))
        self.finished_loading.emit()


class TdmsBrowserWindow(QMainWindow):
    """Main window for browsing and comparing multiple sources."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TDMS Graph Explorer")
        self.resize(1200, 800)

        self.loaded_sources: dict[str, LoadedSource] = {}
        self.source_order: list[str] = []

        self.series_palette = [
            "#2E86AB",
            "#F18F01",
            "#C73E1D",
            "#6A4C93",
            "#2A9D8F",
            "#E76F51",
        ]
        self.left_axis_series: list[SeriesRef] = []
        self.right_axis_series: list[SeriesRef] = []

        self.filter_channel: Optional[SeriesRef] = None
        self.filter_value: Optional[float] = None
        self.plotted_data_cache = []
        self.cursor_items = []
        self.cursor_items_right = []

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#777777", width=1.5, style=Qt.DashLine))
        self.v_line.hide()

        self.open_button = QPushButton("Load Files")
        self.open_button.clicked.connect(self.open_file_dialog)

        self.loaded_sources_list = QListWidget()
        self.loaded_sources_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.unload_selected_button = QPushButton("Unload Selected")
        self.unload_selected_button.clicked.connect(self.unload_selected_sources)
        self.clear_loaded_button = QPushButton("Clear All")
        self.clear_loaded_button.clicked.connect(self.clear_loaded_sources)

        loaded_box = QGroupBox("Loaded Files")
        loaded_layout = QVBoxLayout(loaded_box)
        loaded_layout.addWidget(self.loaded_sources_list)
        loaded_button_row = QHBoxLayout()
        loaded_button_row.addWidget(self.open_button)
        loaded_button_row.addWidget(self.unload_selected_button)
        loaded_button_row.addWidget(self.clear_loaded_button)
        loaded_layout.addLayout(loaded_button_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["TDMS / CSV Structure", "Min", "Max"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground("w")
        self.plot_item = self.plot_widget.addPlot(row=0, col=0)
        self.plot_item.showGrid(x=True, y=True, alpha=0.25)
        self.plot_item.setLabel("bottom", "Sample index")
        self.plot_item.setLabel("left", "Left axis")

        self.right_view_box = pg.ViewBox()
        self.plot_item.showAxis("right")
        self.plot_item.getAxis("right").linkToView(self.right_view_box)
        self.right_view_box.setXLink(self.plot_item)
        self.plot_item.scene().addItem(self.right_view_box)
        self.plot_item.getAxis("right").setLabel("Right axis")
        self.plot_item.vb.sigResized.connect(self._update_right_view)

        # Cursor line addition and interaction
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.scene().sigMouseMoved.connect(self.mouse_moved)

        self.left_series_list = QListWidget()
        self.right_series_list = QListWidget()
        self.left_series_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.right_series_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.assign_left_button = QPushButton("Add Selected To Left")
        self.assign_left_button.clicked.connect(self.add_selected_to_left)
        self.assign_right_button = QPushButton("Add Selected To Right")
        self.assign_right_button.clicked.connect(self.add_selected_to_right)
        self.remove_left_button = QPushButton("Remove From Left")
        self.remove_left_button.clicked.connect(lambda: self.remove_from_axis("left"))
        self.remove_right_button = QPushButton("Remove From Right")
        self.remove_right_button.clicked.connect(lambda: self.remove_from_axis("right"))
        self.clear_plot_button = QPushButton("Clear Plot")
        self.clear_plot_button.clicked.connect(self.clear_assignments)

        self.use_as_filter_button = QPushButton("Use as Filter")
        self.use_as_filter_button.clicked.connect(self.use_selected_as_filter)
        self.filter_channel_label = QLabel("Filter Channel: None")
        self.filter_value_input = QLineEdit()
        self.filter_value_input.setPlaceholderText("Enter filter value")
        self.apply_filter_button = QPushButton("Apply Filter")
        self.apply_filter_button.clicked.connect(self.apply_filter)
        self.clear_filter_button = QPushButton("Clear Filter")
        self.clear_filter_button.clicked.connect(self.clear_filter)

        selection_box = QGroupBox("Channel Assignment")
        selection_layout = QGridLayout(selection_box)
        selection_layout.addWidget(QLabel("Selected channels in the tree can be assigned to either axis."), 0, 0, 1, 2)
        selection_layout.addWidget(self.left_series_list, 1, 0)
        selection_layout.addWidget(self.right_series_list, 1, 1)
        selection_layout.addWidget(self.remove_left_button, 2, 0)
        selection_layout.addWidget(self.remove_right_button, 2, 1)
        selection_layout.addWidget(self.clear_plot_button, 3, 0, 1, 2)

        filter_box = QGroupBox("Data Filter")
        filter_layout = QGridLayout(filter_box)
        filter_layout.addWidget(self.filter_channel_label, 0, 0, 1, 2)
        filter_layout.addWidget(self.apply_filter_button, 0, 2, 1, 1)
        filter_layout.addWidget(QLabel("Filter Value:"), 1, 0)
        filter_layout.addWidget(self.filter_value_input, 1, 1)
        filter_layout.addWidget(self.clear_filter_button, 1, 2, 1, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.plot_widget, 4)
        right_layout.addWidget(selection_box, 2)
        right_layout.addWidget(filter_box, 1)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.addWidget(loaded_box)
        tree_layout.addWidget(self.tree, 1)
        tree_layout.addWidget(self.assign_left_button)
        tree_layout.addWidget(self.assign_right_button)
        tree_layout.addWidget(self.use_as_filter_button)

        splitter = QSplitter()
        splitter.addWidget(tree_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(splitter, 1)
        self.setCentralWidget(central_widget)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("Ready")

    def open_file_dialog(self) -> None:
        """Open one or more TDMS/CSV/Excel files from disk."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Files",
            os.getcwd(),
            "Data Files (*.tdms *.csv *.xlsx *.xls);;TDMS Files (*.tdms);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)",
        )
        if file_paths:
            self.load_files(file_paths)

    def load_files(self, file_paths: list[str]) -> None:
        """Load multiple files asynchronously in a background thread and show a progress dialog."""
        loaded_count = 0
        skipped_count = 0
        errors: list[str] = []
        existing_paths = {os.path.abspath(source.path) for source in self.loaded_sources.values()}

        paths_to_load = []
        for file_path in file_paths:
            absolute_path = os.path.abspath(file_path)
            if absolute_path in existing_paths:
                skipped_count += 1
                continue
            paths_to_load.append(file_path)

        if not paths_to_load:
            if skipped_count:
                self.statusBar().showMessage("Selected files are already loaded")
            return

        # Setup Progress Dialog
        self.progress_dialog = QProgressDialog("Initializing loader...", "Cancel", 0, len(paths_to_load), self)
        self.progress_dialog.setWindowTitle("Loading Files")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)  # Show immediately

        if len(paths_to_load) == 1:
            # Set to busy indicator (marquee animation) if loading a single file
            self.progress_dialog.setRange(0, 0)
            self.progress_dialog.setLabelText(f"Loading {os.path.basename(paths_to_load[0])}...")
        else:
            self.progress_dialog.setRange(0, len(paths_to_load))
            self.progress_dialog.setLabelText(f"Loading 0 / {len(paths_to_load)} files...")

        # Create worker thread
        self.loader_thread = FileLoaderThread(paths_to_load, self)
        loaded_results = []

        def handle_file_loaded(result):
            if isinstance(result, LoadedSource):
                loaded_results.append(result)
            else:
                errors.append(f"{os.path.basename(result[0])}: {result[1]}")

            completed = len(loaded_results) + len(errors)
            if len(paths_to_load) > 1 and self.progress_dialog:
                self.progress_dialog.setValue(completed)
                self.progress_dialog.setLabelText(f"Loading {completed} / {len(paths_to_load)} files...")

        def handle_finished():
            if self.progress_dialog:
                self.progress_dialog.close()

            # Process all loaded results
            nonlocal loaded_count
            for source in loaded_results:
                self.loaded_sources[source.source_id] = source
                self.source_order.append(source.source_id)
                loaded_count += 1

            if loaded_count:
                self.refresh_loaded_sources_view()
                self.refresh_tree()
                self.statusBar().showMessage(f"Loaded {loaded_count} file(s)")

            if skipped_count and not loaded_count and not errors:
                self.statusBar().showMessage("Selected files are already loaded")

            if errors:
                QMessageBox.warning(
                    self,
                    "Some Files Could Not Be Loaded",
                    "\n".join(errors),
                )

            if loaded_count == 0 and not errors and skipped_count == 0:
                self.statusBar().showMessage("No files loaded")

            # Clean up references
            self.loader_thread = None
            self.progress_dialog = None

        self.progress_dialog.canceled.connect(self.loader_thread.cancel)
        self.loader_thread.file_loaded.connect(handle_file_loaded)
        self.loader_thread.finished_loading.connect(handle_finished)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)

        # Show the modal loader dialog and run background thread
        self.progress_dialog.show()
        self.loader_thread.start()

    def unload_selected_sources(self) -> None:
        """Remove the selected loaded files from the app."""
        selected_items = self.loaded_sources_list.selectedItems()
        if not selected_items:
            return

        source_ids = [str(item.data(Qt.UserRole)) for item in selected_items if item.data(Qt.UserRole)]
        if not source_ids:
            return

        for source_id in source_ids:
            self.loaded_sources.pop(source_id, None)
            if source_id in self.source_order:
                self.source_order.remove(source_id)

        self._prune_plot_state()
        self.refresh_loaded_sources_view()
        self.refresh_tree()
        self._refresh_series_list("left")
        self._refresh_series_list("right")
        self.update_plot()
        self.statusBar().showMessage(f"Unloaded {len(source_ids)} file(s)")

    def clear_loaded_sources(self) -> None:
        """Remove all loaded sources and plotted series."""
        if not self.loaded_sources:
            return

        self.loaded_sources.clear()
        self.source_order.clear()
        self.left_axis_series = []
        self.right_axis_series = []
        self._reset_filter_state()
        self.refresh_loaded_sources_view()
        self.refresh_tree()
        self.left_series_list.clear()
        self.right_series_list.clear()
        self.update_plot()
        self.statusBar().showMessage("All loaded files cleared")

    def refresh_loaded_sources_view(self) -> None:
        """Refresh the loaded-files list and summary label."""
        self.loaded_sources_list.clear()
        for source_id in self.source_order:
            source = self.loaded_sources.get(source_id)
            if source is None:
                continue
            item = QListWidgetItem(get_source_label(source))
            item.setData(Qt.UserRole, source_id)
            item.setToolTip(source.path)
            self.loaded_sources_list.addItem(item)

        count = len(self.source_order)
        self.file_label.setText(f"Loaded files: {count}" if count else "No files loaded")

    def refresh_tree(self) -> None:
        """Rebuild the tree for all loaded files."""
        self.tree.clear()

        for source_id in self.source_order:
            source = self.loaded_sources.get(source_id)
            if source is None:
                continue

            source_item = QTreeWidgetItem([source.display_name, source.kind.upper(), ""])
            source_item.setData(0, Qt.UserRole, {"type": "source", "source_id": source_id})
            source_item.setToolTip(0, source.path)

            for group in source.structure.get("groups", []):
                group_name = group.get("name", "Unnamed Group")
                group_item = QTreeWidgetItem([group_name, "", ""])
                group_item.setData(0, Qt.UserRole, {"type": "group", "source_id": source_id, "group": group_name})

                for channel in group.get("channels", []):
                    channel_name = channel.get("name", "Unnamed Channel")
                    min_value = self._format_number(channel.get("min"))
                    max_value = self._format_number(channel.get("max"))
                    channel_item = QTreeWidgetItem([channel_name, min_value, max_value])
                    channel_item.setData(
                        0,
                        Qt.UserRole,
                        {"source_id": source_id, "group": group_name, "channel": channel_name},
                    )
                    group_item.addChild(channel_item)

                source_item.addChild(group_item)

            self.tree.addTopLevelItem(source_item)
            source_item.setExpanded(True)

        self.tree.expandToDepth(2)

        # Auto-resize columns to fit content
        for col in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(col)

    def _selected_channel_refs(self) -> list[SeriesRef]:
        """Return selected channel references from the tree."""
        refs: list[SeriesRef] = []
        seen: set[SeriesRef] = set()
        for item in self.tree.selectedItems():
            payload = item.data(0, Qt.UserRole)
            if not isinstance(payload, dict):
                continue
            source_id = payload.get("source_id")
            group_name = payload.get("group")
            channel_name = payload.get("channel")
            if source_id and group_name and channel_name:
                ref = SeriesRef(str(source_id), str(group_name), str(channel_name))
                if ref not in seen:
                    refs.append(ref)
                    seen.add(ref)
        return refs

    def add_selected_to_left(self) -> None:
        """Add the selected tree channels to the left axis list."""
        self._add_selected_to_axis("left")

    def add_selected_to_right(self) -> None:
        """Add the selected tree channels to the right axis list."""
        self._add_selected_to_axis("right")

    def _add_selected_to_axis(self, axis: str) -> None:
        selected = self._selected_channel_refs()
        if not selected:
            return

        target_series = self.left_axis_series if axis == "left" else self.right_axis_series
        for ref in selected:
            if ref not in target_series:
                target_series.append(ref)

        self._refresh_series_list(axis)
        self._refresh_series_list("left")
        self._refresh_series_list("right")
        self.update_plot()

        axis_name = "left" if axis == "left" else "right"
        self.statusBar().showMessage(f"Added {len(selected)} channel(s) to {axis_name} axis")

    def _refresh_series_list(self, axis: str) -> None:
        """Refresh the plotted-series list for one axis."""
        target_series = self.left_axis_series if axis == "left" else self.right_axis_series
        target_widget = self.left_series_list if axis == "left" else self.right_series_list

        target_widget.clear()
        for index, ref in enumerate(target_series):
            color = self._series_color(axis, index, len(self.left_axis_series))
            item = QListWidgetItem(self._series_ref_label(ref))
            item.setIcon(self._color_icon(color))
            target_widget.addItem(item)

    def remove_from_axis(self, axis: str) -> None:
        """Remove selected items from one of the axis lists."""
        target_series = self.left_axis_series if axis == "left" else self.right_axis_series
        target_widget = self.left_series_list if axis == "left" else self.right_series_list

        rows = sorted({item.row() for item in target_widget.selectedIndexes()}, reverse=True)
        if not rows:
            return

        for row in rows:
            if 0 <= row < len(target_series):
                del target_series[row]

        self._refresh_series_list("left")
        self._refresh_series_list("right")
        self.update_plot()

        axis_name = "left" if axis == "left" else "right"
        self.statusBar().showMessage(f"Removed {len(rows)} channel(s) from {axis_name} axis")

    def clear_assignments(self) -> None:
        """Clear both axis assignments and reset the plot."""
        self.left_axis_series = []
        self.right_axis_series = []
        self.left_series_list.clear()
        self.right_series_list.clear()
        self.update_plot()
        self.statusBar().showMessage("Plot cleared")

    def use_selected_as_filter(self) -> None:
        """Set the selected channel as the filter channel."""
        selected = self._selected_channel_refs()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a channel to use as filter.")
            return
        if len(selected) > 1:
            QMessageBox.warning(self, "Multiple Selection", "Please select only one channel to use as filter.")
            return

        self.filter_channel = selected[0]
        self.filter_channel_label.setText(f"Filter Channel: {self._series_ref_label(self.filter_channel)}")
        self.statusBar().showMessage(f"Filter channel set to {self._series_ref_label(self.filter_channel)}")

    def apply_filter(self) -> None:
        """Apply the filter with the current channel and value."""
        if self.filter_channel is None:
            QMessageBox.warning(self, "No Filter Channel", "Please select a channel to use as filter.")
            return

        try:
            self.filter_value = float(self.filter_value_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Please enter a valid numeric value for the filter.")
            return

        if self.filter_channel.source_id not in self.loaded_sources:
            QMessageBox.warning(self, "Missing Source", "The selected filter source is no longer loaded.")
            self._reset_filter_state()
            return

        self.statusBar().showMessage(
            f"Filter applied: {self._series_ref_label(self.filter_channel)} == {self.filter_value}"
        )
        self.update_plot()

    def clear_filter(self) -> None:
        """Clear the current filter."""
        self._reset_filter_state()
        self.statusBar().showMessage("Filter cleared")
        self.update_plot()

    def update_plot(self) -> None:
        """Render the currently assigned channels on a shared plot with two Y axes."""
        # Clean up any existing hover dots and texts
        for item in self.cursor_items:
            try:
                self.plot_item.removeItem(item)
            except Exception:
                pass
        self.cursor_items.clear()

        for item in self.cursor_items_right:
            try:
                self.right_view_box.removeItem(item)
            except Exception:
                pass
        self.cursor_items_right.clear()

        self.plot_item.clear()
        self.right_view_box.clear()
        self.plot_item.setLabel("left", "Left axis")
        self.plot_item.getAxis("right").setLabel("Right axis")

        self.plotted_data_cache = []

        left_curves = []
        right_curves = []

        for index, ref in enumerate(self.left_axis_series):
            series = self._get_channel_data(ref)
            if series is None:
                continue
            x_values, y_values = series
            color = self._series_color("left", index, len(self.left_axis_series))
            curve = self.plot_item.plot(x_values, y_values, pen=pg.mkPen(color, width=2))
            left_curves.append(curve)

            # Create interactive cursor indicators
            dot = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(color), pen=pg.mkPen('w', width=1))
            dot.hide()
            text = pg.TextItem(anchor=(-0.15, 0.5), color='k', fill=(255, 255, 255, 200), border=pg.mkPen(color, width=1))
            text.hide()
            self.plot_item.addItem(dot)
            self.plot_item.addItem(text)
            self.cursor_items.append(dot)
            self.cursor_items.append(text)

            self.plotted_data_cache.append({
                "label": self._series_ref_label(ref),
                "x_values": x_values,
                "y_values": y_values,
                "axis": "Left",
                "color": color,
                "dot_item": dot,
                "text_item": text
            })

        for index, ref in enumerate(self.right_axis_series):
            series = self._get_channel_data(ref)
            if series is None:
                continue
            x_values, y_values = series
            color = self._series_color("right", index, len(self.left_axis_series))
            curve = pg.PlotDataItem(x_values, y_values, pen=pg.mkPen(color, width=2))
            self.right_view_box.addItem(curve)
            right_curves.append(curve)

            # Create interactive cursor indicators (Right Y-axis scale)
            dot = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(color), pen=pg.mkPen('w', width=1))
            dot.hide()
            text = pg.TextItem(anchor=(-0.15, 0.5), color='k', fill=(255, 255, 255, 200), border=pg.mkPen(color, width=1))
            text.hide()
            self.right_view_box.addItem(dot)
            self.right_view_box.addItem(text)
            self.cursor_items_right.append(dot)
            self.cursor_items_right.append(text)

            self.plotted_data_cache.append({
                "label": self._series_ref_label(ref),
                "x_values": x_values,
                "y_values": y_values,
                "axis": "Right",
                "color": color,
                "dot_item": dot,
                "text_item": text
            })

        # Add the vertical cursor line back on top of the left-axis curves
        self.plot_item.addItem(self.v_line, ignoreBounds=True)

        if right_curves:
            self._update_right_view()
        else:
            self.plot_item.getAxis("right").setLabel("Right axis")

        if not left_curves and not right_curves:
            self.plot_item.setLabel("left", "Left axis")

    def mouse_moved(self, evt) -> None:
        """Handle mouse movement to update the vertical cursor line and show values next to data points."""
        pos = evt
        if self.plot_item.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.plot_item.vb.mapSceneToView(pos)
            x = mousePoint.x()

            # Position the vertical line
            self.v_line.setValue(x)
            self.v_line.show()

            for item in getattr(self, "plotted_data_cache", []):
                x_vals = item["x_values"]
                y_vals = item["y_values"]
                dot = item.get("dot_item")
                text_item = item.get("text_item")

                if x_vals is None or len(x_vals) == 0:
                    if dot: dot.hide()
                    if text_item: text_item.hide()
                    continue

                # Find nearest x index
                idx = np.argmin(np.abs(x_vals - x))
                nearest_x = x_vals[idx]
                nearest_y = y_vals[idx]

                # Update dot position
                if dot:
                    dot.setData(x=[nearest_x], y=[nearest_y])
                    dot.show()

                # Update text position and content
                if text_item:
                    text_item.setText(f"{nearest_y:.6g}")
                    text_item.setPos(nearest_x, nearest_y)
                    text_item.show()

        else:
            self.v_line.hide()
            for item in getattr(self, "plotted_data_cache", []):
                dot = item.get("dot_item")
                text_item = item.get("text_item")
                if dot: dot.hide()
                if text_item: text_item.hide()

    def _get_channel_data(self, series_ref: SeriesRef) -> Optional[tuple[Any, Any]]:
        """Return x and y arrays for the selected channel, applying a filter if needed."""
        source = self.loaded_sources.get(series_ref.source_id)
        if source is None:
            return None

        series = get_channel_data(source, series_ref.group, series_ref.channel)
        if series is None:
            return None

        x_values, y_values = series
        if self.filter_channel is not None and self.filter_value is not None:
            if self.filter_channel.source_id == series_ref.source_id:
                filter_source = self.loaded_sources.get(self.filter_channel.source_id)
                if filter_source is not None:
                    mask = get_filter_mask(
                        filter_source,
                        self.filter_channel.group,
                        self.filter_channel.channel,
                        self.filter_value,
                    )
                    if mask is not None and len(mask) == len(y_values):
                        x_values = x_values[mask]
                        y_values = y_values[mask]

        return x_values, y_values

    def _series_ref_label(self, series_ref: SeriesRef) -> str:
        """Return a human-friendly label for a plotted series."""
        source = self.loaded_sources.get(series_ref.source_id)
        source_name = source.display_name if source is not None else series_ref.source_id
        return f"{source_name} / {series_ref.group} / {series_ref.channel}"

    def _prune_plot_state(self) -> None:
        """Remove series and filter references that point to unloaded sources."""
        loaded_ids = set(self.loaded_sources)
        self.left_axis_series = [ref for ref in self.left_axis_series if ref.source_id in loaded_ids]
        self.right_axis_series = [ref for ref in self.right_axis_series if ref.source_id in loaded_ids]
        if self.filter_channel is not None and self.filter_channel.source_id not in loaded_ids:
            self._reset_filter_state()

    def _reset_filter_state(self) -> None:
        """Reset filter state without immediately redrawing."""
        self.filter_channel = None
        self.filter_value = None
        self.filter_channel_label.setText("Filter Channel: None")
        self.filter_value_input.clear()

    def _color_icon(self, color: str) -> QIcon:
        """Create a small color swatch for list entries."""
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(pg.mkBrush(color))
        painter.setPen(pg.mkPen(color))
        painter.drawRoundedRect(1, 1, 12, 12, 2, 2)
        painter.end()
        return QIcon(pixmap)

    def _series_color(self, axis: str, index: int, left_count: int) -> str:
        """Return the display color for a series on the given axis."""
        if axis == "right":
            return self.series_palette[(index + left_count) % len(self.series_palette)]
        return self.series_palette[index % len(self.series_palette)]

    def _update_right_view(self) -> None:
        """Keep the secondary view box aligned with the main plot area."""
        self.right_view_box.setGeometry(self.plot_item.vb.sceneBoundingRect())
        self.right_view_box.linkedViewChanged(self.plot_item.vb, self.right_view_box.XAxis)

    def _format_number(self, value: Any) -> str:
        """Format numeric values for display in the tree."""
        if value is None:
            return ""

        try:
            return f"{float(value):.6g}"
        except Exception:
            return str(value)


def run_gui(initial_path: Optional[str] = None) -> int:
    """Start the Qt application and optionally preload a file."""
    app = QApplication(sys.argv)
    window = TdmsBrowserWindow()
    window.show()

    if initial_path:
        window.load_files([initial_path])

    return app.exec()
