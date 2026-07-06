"""Qt application entry point for TDMS inspection."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QGroupBox,
    QGridLayout,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from src.tdms_reader import read_tdms_file, get_tdms_structure


@dataclass
class LoadedTdmsFile:
    """In-memory representation of the currently loaded TDMS file."""

    path: str
    tdms_file: Any
    structure: Dict[str, Any]


class TdmsBrowserWindow(QMainWindow):
    """Main window for browsing TDMS file structure."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TDMS Graph Explorer")
        self.resize(1200, 800)

        self.loaded_file: Optional[LoadedTdmsFile] = None
        self.series_palette = [
            "#2E86AB",
            "#F18F01",
            "#C73E1D",
            "#6A4C93",
            "#2A9D8F",
            "#E76F51",
        ]
        self.left_axis_series: list[tuple[str, str]] = []
        self.right_axis_series: list[tuple[str, str]] = []

        # Filter state
        self.filter_channel: Optional[tuple[str, str]] = None
        self.filter_value: Optional[float] = None

        self.open_button = QPushButton("Open TDMS File")
        self.open_button.clicked.connect(self.open_file_dialog)

        self.file_label = QLabel("No file loaded")
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.open_button)
        top_layout.addWidget(self.file_label, 1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["TDMS Structure", "Min", "Max"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self.sync_selection_hint)

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

        # Filter UI elements
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
        selection_layout.addWidget(QLabel("Selected channels in tree can be assigned to either axis."), 0, 0, 1, 2)
        selection_layout.addWidget(self.left_series_list, 1, 0)
        selection_layout.addWidget(self.right_series_list, 1, 1)
        selection_layout.addWidget(self.remove_left_button, 2, 0)
        selection_layout.addWidget(self.remove_right_button, 2, 1)
        selection_layout.addWidget(self.clear_plot_button, 3, 0, 1, 2)

        self.placeholder_label = QLabel(
            "Select one or more channels, assign them to the left or right axis, and plot them."
        )
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setWordWrap(True)

        # Filter settings panel
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
        right_layout.addWidget(self.placeholder_label, 1)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
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
        central_layout.addWidget(top_bar)
        central_layout.addWidget(splitter, 1)
        self.setCentralWidget(central_widget)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("Ready")

    def open_file_dialog(self) -> None:
        """Open a TDMS file from disk and populate the browser tree."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open TDMS File",
            os.getcwd(),
            "TDMS Files (*.tdms);;All Files (*)",
        )
        if file_path:
            self.load_tdms_file(file_path)

    def load_tdms_file(self, file_path: str) -> None:
        """Load a TDMS file and refresh the displayed structure."""
        try:
            tdms_file = read_tdms_file(file_path)
            structure = get_tdms_structure(tdms_file)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to Load TDMS File", str(exc))
            return

        self.loaded_file = LoadedTdmsFile(path=file_path, tdms_file=tdms_file, structure=structure)
        self.file_label.setText(file_path)
        self.statusBar().showMessage(f"Loaded {os.path.basename(file_path)}")
        self.populate_tree(structure)
        self.clear_assignments()
        self.clear_filter()
        self.sync_selection_hint()

    def populate_tree(self, structure: Dict[str, Any]) -> None:
        """Fill the tree view with TDMS file content."""
        self.tree.clear()

        for group in structure.get("groups", []):
            group_name = group.get("name", "Unnamed Group")
            group_item = QTreeWidgetItem([group_name, "", ""])
            group_item.setFirstColumnSpanned(True)

            channels = group.get("channels", [])
            for channel in channels:
                channel_name = channel.get("name", "Unnamed Channel")
                min_value = self._format_number(channel.get("min"))
                max_value = self._format_number(channel.get("max"))
                channel_item = QTreeWidgetItem([
                    channel_name,
                    min_value,
                    max_value,
                ])
                channel_item.setData(0, Qt.UserRole, {"group": group_name, "channel": channel_name})
                group_item.addChild(channel_item)

            self.tree.addTopLevelItem(group_item)
            group_item.setExpanded(True)

        self.tree.expandToDepth(1)

    def sync_selection_hint(self) -> None:
        """Keep the placeholder text aligned with the current selection state."""
        selected = self._selected_channel_refs()
        if not selected:
            self.placeholder_label.setText(
                "Select one or more channels in the tree and assign them to the left or right axis."
            )
            return

        self.placeholder_label.setText(
            f"{len(selected)} channel(s) selected in the tree. Use the assignment buttons to plot them."
        )

    def _selected_channel_refs(self) -> list[tuple[str, str]]:
        """Return the selected channel references from the tree."""
        refs: list[tuple[str, str]] = []
        for item in self.tree.selectedItems():
            payload = item.data(0, Qt.UserRole)
            if isinstance(payload, dict) and payload.get("group") and payload.get("channel"):
                refs.append((str(payload["group"]), str(payload["channel"])))
        return refs

    def add_selected_to_left(self) -> None:
        """Add the selected tree channels to the left axis list."""
        self._add_selected_to_axis("left")

    def add_selected_to_right(self) -> None:
        """Add the selected tree channels to the right axis list."""
        self._add_selected_to_axis("right")

    def _add_selected_to_axis(self, axis: str) -> None:
        if self.loaded_file is None:
            return

        selected = self._selected_channel_refs()
        if not selected:
            return

        target_series = self.left_axis_series if axis == "left" else self.right_axis_series
        target_widget = self.left_series_list if axis == "left" else self.right_series_list

        for ref in selected:
            if ref not in target_series:
                target_series.append(ref)

        self._refresh_series_list(axis)
        self._refresh_series_list("left")
        self._refresh_series_list("right")
        self.update_plot()

    def _refresh_series_list(self, axis: str) -> None:
        target_series = self.left_axis_series if axis == "left" else self.right_axis_series
        target_widget = self.left_series_list if axis == "left" else self.right_series_list

        target_widget.clear()
        for index, (group_name, channel_name) in enumerate(target_series):
            color = self._series_color(axis, index, len(self.left_axis_series))
            item = QListWidgetItem(f"{group_name} / {channel_name}")
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
        self._refresh_series_list(axis)
        self.update_plot()

    def clear_assignments(self) -> None:
        """Clear both axis assignments and reset the plot."""
        self.left_axis_series = []
        self.right_axis_series = []
        self.left_series_list.clear()
        self.right_series_list.clear()
        self.update_plot()

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
        group_name, channel_name = self.filter_channel
        self.filter_channel_label.setText(f"Filter Channel: {group_name} / {channel_name}")

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

        self.statusBar().showMessage(f"Filter applied: {self.filter_channel[0]}/{self.filter_channel[1]} == {self.filter_value}")
        self.update_plot()

    def clear_filter(self) -> None:
        """Clear the current filter."""
        self.filter_channel = None
        self.filter_value = None
        self.filter_channel_label.setText("Filter Channel: None")
        self.filter_value_input.clear()
        self.statusBar().showMessage("Filter cleared")
        self.update_plot()

    def update_plot(self) -> None:
        """Render the currently assigned channels on a shared plot with two Y axes."""
        self.plot_item.clear()
        self.right_view_box.clear()

        if self.loaded_file is None:
            return

        tdms_file = self.loaded_file.tdms_file
        left_curves = []
        right_curves = []

        for index, (group_name, channel_name) in enumerate(self.left_axis_series):
            series = self._get_channel_data(tdms_file, group_name, channel_name)
            if series is None:
                continue
            x_values, y_values = series
            color = self._series_color("left", index, len(self.left_axis_series))
            curve = self.plot_item.plot(x_values, y_values, pen=pg.mkPen(color, width=2))
            left_curves.append(curve)

        for index, (group_name, channel_name) in enumerate(self.right_axis_series):
            series = self._get_channel_data(tdms_file, group_name, channel_name)
            if series is None:
                continue
            x_values, y_values = series
            color = self._series_color("right", index, len(self.left_axis_series))
            curve = pg.PlotDataItem(x_values, y_values, pen=pg.mkPen(color, width=2))
            self.right_view_box.addItem(curve)
            right_curves.append(curve)

        if right_curves:
            self._update_right_view()
        else:
            self.plot_item.getAxis("right").setLabel("Right axis")

        if not left_curves and not right_curves:
            self.plot_item.setLabel("left", "Left axis")

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

    def _get_channel_data(self, tdms_file: Any, group_name: str, channel_name: str) -> Optional[tuple[Any, Any]]:
        """Return x and y arrays for the selected channel, applying filter if set."""
        try:
            channel = tdms_file[group_name][channel_name]
            y_values = channel.data
            if y_values is None:
                return None
            
            x_values = np.arange(len(y_values))
            
            # Apply filter if one is set
            if self.filter_channel is not None and self.filter_value is not None:
                filter_group, filter_channel = self.filter_channel
                try:
                    filter_data = tdms_file[filter_group][filter_channel].data
                    if filter_data is not None:
                        # Find indices where filter_data matches filter_value
                        mask = np.isclose(filter_data, self.filter_value)
                        x_values = x_values[mask]
                        y_values = y_values[mask]
                except Exception:
                    # If filter data can't be retrieved, just return unfiltered data
                    pass
            
            return x_values, y_values
        except Exception:
            return None

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


def run_gui(tdms_path: Optional[str] = None) -> int:
    """Start the Qt application and optionally preload a TDMS file."""
    app = QApplication(sys.argv)
    window = TdmsBrowserWindow()
    window.show()

    if tdms_path:
        window.load_tdms_file(tdms_path)

    return app.exec()
