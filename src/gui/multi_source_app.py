"""Qt application entry point for multi-source TDMS and CSV comparison."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional
from dataclasses import dataclass
import uuid

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPen, QBrush, QColor
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
    QDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QTabWidget,
    QInputDialog,
    QGraphicsRectItem,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

@dataclass
class ConfiguredStat:
    """Represents a user-defined statistic calculation."""
    stat_id: str
    label: str
    source_id: str
    group: str
    channel: str
    transform: str       # "none", "deriv_raw", "deriv_smooth", "diff"
    aggregation: str     # "min", "max", "avg", "median", "integral", "net_change"
    multiplier: float = 1.0
    last_value: Optional[float] = None


class AssignmentTabState:
    """Manages the state of a single channel assignment tab."""

    def __init__(self, name: str, left_series: list[SeriesRef], right_series: list[SeriesRef]):
        self.name = name
        # Copy SeriesRefs so they are independent
        self.left_axis_series = [
            SeriesRef(
                source_id=s.source_id,
                group=s.group,
                channel=s.channel,
                series_id=s.series_id,
                filter_channel=s.filter_channel,
                filter_value=s.filter_value,
                color=s.color
            ) for s in left_series
        ]
        self.right_axis_series = [
            SeriesRef(
                source_id=s.source_id,
                group=s.group,
                channel=s.channel,
                series_id=s.series_id,
                filter_channel=s.filter_channel,
                filter_value=s.filter_value,
                color=s.color
            ) for s in right_series
        ]
        # Viewport state
        self.x_range = None
        self.left_y_range = None
        self.right_y_range = None


import pyqtgraph as pg

from src.data_sources import LoadedSource, SeriesRef, get_channel_data, get_filter_mask, get_source_label, load_data_source


class FileConfigDialog(QDialog):
    """Modal dialog to configure a source's prescaler, offset, and X-axis channel."""

    def __init__(self, source: LoadedSource, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure Source")
        self.resize(450, 200)

        self.source = source

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.addRow(QLabel(f"File: {source.display_name}"))

        # Prescaler
        self.prescaler_spin = QDoubleSpinBox()
        self.prescaler_spin.setRange(-1000000000.0, 1000000000.0)
        self.prescaler_spin.setDecimals(6)
        self.prescaler_spin.setSingleStep(0.1)
        self.prescaler_spin.setValue(source.prescaler)
        form_layout.addRow("X-Axis Multiplier:", self.prescaler_spin)

        # Offset
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-1000000000.0, 1000000000.0)
        self.offset_spin.setDecimals(6)
        self.offset_spin.setSingleStep(1.0)
        self.offset_spin.setValue(source.offset)
        form_layout.addRow("X-Axis Offset:", self.offset_spin)

        # X-axis combo box
        self.x_combo = QComboBox()
        self.x_combo.addItem("Sample Index (Default)", None)

        # Populate combo box with channels
        current_x_idx = 0
        idx = 1
        for group in source.structure.get("groups", []):
            group_name = group.get("name", "")
            for channel in group.get("channels", []):
                channel_name = channel.get("name", "")
                display_label = f"[{group_name}] {channel_name}" if source.kind != "csv" else channel_name
                role_data = (group_name, channel_name)

                self.x_combo.addItem(display_label, role_data)

                # Check X-channel match
                if source.x_channel == role_data:
                    current_x_idx = idx
                idx += 1

        self.x_combo.setCurrentIndex(current_x_idx)

        form_layout.addRow("X-Axis Channel:", self.x_combo)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def get_settings(self) -> tuple[float, float, Optional[tuple[str, str]]]:
        """Return the configured prescaler, offset, and X-axis channel."""
        return (
            self.prescaler_spin.value(),
            self.offset_spin.value(),
            self.x_combo.currentData()
        )


class SeriesConfigDialog(QDialog):
    """Modal dialog to configure a plotted series' local filter."""

    def __init__(self, series_ref: SeriesRef, source: LoadedSource, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure Channel: {series_ref.channel}")
        self.resize(450, 180)

        self.series_ref = series_ref
        self.source = source

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Filter channel combo box
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("None (Disabled)", None)

        # Populate with channels from the same source
        current_f_idx = 0
        idx = 1
        for group in source.structure.get("groups", []):
            group_name = group.get("name", "")
            for channel in group.get("channels", []):
                channel_name = channel.get("name", "")
                display_label = f"[{group_name}] {channel_name}" if source.kind != "csv" else channel_name
                role_data = (group_name, channel_name)

                self.filter_combo.addItem(display_label, role_data)

                # Check Filter-channel match
                if series_ref.filter_channel == role_data:
                    current_f_idx = idx
                idx += 1

        self.filter_combo.setCurrentIndex(current_f_idx)
        form_layout.addRow("Filter Channel:", self.filter_combo)

        # Filter value
        self.filter_val_spin = QDoubleSpinBox()
        self.filter_val_spin.setRange(-1000000000.0, 1000000000.0)
        self.filter_val_spin.setDecimals(5)
        self.filter_val_spin.setSingleStep(1.0)
        self.filter_val_spin.setValue(series_ref.filter_value)
        form_layout.addRow("Filter Value:", self.filter_val_spin)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def get_settings(self) -> tuple[Optional[tuple[str, str]], float]:
        """Return the filter channel and filter value."""
        return (
            self.filter_combo.currentData(),
            self.filter_val_spin.value()
        )


class ChannelLimitDialog(QDialog):
    """Modal dialog to configure a channel's min and max cutoff limits."""

    def __init__(self, display_name: str, current_min: Optional[float], current_max: Optional[float], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Channel Limits")
        self.resize(400, 160)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.addRow(QLabel(f"Channel: {display_name}"))

        # Min cutoff
        self.min_input = QLineEdit()
        self.min_input.setPlaceholderText("No lower limit (None)")
        if current_min is not None:
            self.min_input.setText(str(current_min))
        form_layout.addRow("Min Value Cutoff:", self.min_input)

        # Max cutoff
        self.max_input = QLineEdit()
        self.max_input.setPlaceholderText("No upper limit (None)")
        if current_max is not None:
            self.max_input.setText(str(current_max))
        form_layout.addRow("Max Value Cutoff:", self.max_input)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.validate_and_accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.parsed_min = None
        self.parsed_max = None

    def validate_and_accept(self) -> None:
        min_val = None
        max_val = None

        min_str = self.min_input.text().strip()
        max_str = self.max_input.text().strip()

        if min_str:
            try:
                min_val = float(min_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Value", "Min cutoff must be a number or empty.")
                return

        if max_str:
            try:
                max_val = float(max_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Value", "Max cutoff must be a number or empty.")
                return

        if min_val is not None and max_val is not None and min_val > max_val:
            QMessageBox.warning(self, "Invalid Limits", "Min cutoff cannot be greater than Max cutoff.")
            return

        self.parsed_min = min_val
        self.parsed_max = max_val
        self.accept()

    def get_settings(self) -> tuple[Optional[float], Optional[float]]:
        return self.parsed_min, self.parsed_max


class AddEditStatDialog(QDialog):
    """Dialog to create or edit a global statistic metric."""

    def __init__(
        self,
        plotted_channels: list[tuple[str, str, str, str]],  # [(tab_name, source_id, group, channel)]
        loaded_sources: dict[str, LoadedSource],
        existing_stat: Optional[ConfiguredStat] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.plotted_channels = plotted_channels
        self.loaded_sources = loaded_sources
        self.existing_stat = existing_stat

        title = "Edit Statistic" if existing_stat else "Add Statistic"
        self.setWindowTitle(title)
        self.resize(450, 250)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Label/Name input
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Auto-generate from settings")
        if existing_stat:
            self.label_input.setText(existing_stat.label)
        form_layout.addRow("Custom Label:", self.label_input)

        # Channel Selector
        self.channel_combo = QComboBox()
        # Populating plotted channels
        for tab_name, source_id, group, channel in plotted_channels:
            source = loaded_sources.get(source_id)
            source_name = source.display_name if source else source_id
            display_str = f"[{tab_name}] {source_name} / {group} / {channel}"
            role_data = (source_id, group, channel)
            self.channel_combo.addItem(display_str, role_data)

        # Pre-select if editing
        if existing_stat:
            target_role = (existing_stat.source_id, existing_stat.group, existing_stat.channel)
            for i in range(self.channel_combo.count()):
                if self.channel_combo.itemData(i) == target_role:
                    self.channel_combo.setCurrentIndex(i)
                    break
        form_layout.addRow("Channel:", self.channel_combo)

        # Transformation Selector
        self.transform_combo = QComboBox()
        self.transform_combo.addItem("None (Raw Values)", "none")
        self.transform_combo.addItem("Derivative (dY/dX) - Raw", "deriv_raw")
        self.transform_combo.addItem("Derivative (dY/dX) - Smoothed (5-pt SMA)", "deriv_smooth")
        self.transform_combo.addItem("Difference (dY)", "diff")

        if existing_stat:
            idx = self.transform_combo.findData(existing_stat.transform)
            if idx != -1:
                self.transform_combo.setCurrentIndex(idx)
        form_layout.addRow("Transformation:", self.transform_combo)

        # Aggregation Selector
        self.aggregation_combo = QComboBox()
        self.aggregation_combo.addItem("Minimum (Min)", "min")
        self.aggregation_combo.addItem("Maximum (Max)", "max")
        self.aggregation_combo.addItem("Average (Mean)", "avg")
        self.aggregation_combo.addItem("Median", "median")
        self.aggregation_combo.addItem("Integral (Trapezoidal)", "integral")
        self.aggregation_combo.addItem("Net Change", "net_change")

        if existing_stat:
            idx = self.aggregation_combo.findData(existing_stat.aggregation)
            if idx != -1:
                self.aggregation_combo.setCurrentIndex(idx)
        form_layout.addRow("Aggregation:", self.aggregation_combo)

        # Multiplier
        self.multiplier_spin = QDoubleSpinBox()
        self.multiplier_spin.setRange(-1000000000.0, 1000000000.0)
        self.multiplier_spin.setDecimals(6)
        self.multiplier_spin.setSingleStep(1.0)
        if existing_stat:
            self.multiplier_spin.setValue(existing_stat.multiplier)
        else:
            self.multiplier_spin.setValue(1.0)
        form_layout.addRow("Multiplier:", self.multiplier_spin)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.validate_and_accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.result_stat = None

    def validate_and_accept(self) -> None:
        if self.channel_combo.count() == 0:
            QMessageBox.warning(self, "No Channels Available", "There are no plotted channels to calculate statistics on.")
            return

        source_id, group, channel = self.channel_combo.currentData()
        transform = self.transform_combo.currentData()
        aggregation = self.aggregation_combo.currentData()

        label = self.label_input.text().strip()
        if not label:
            source = self.loaded_sources.get(source_id)
            source_name = source.display_name if source else "Source"
            agg_name = self.aggregation_combo.currentText().split(" ")[0]
            trans_name = ""
            if transform == "deriv_raw":
                trans_name = "d/dx "
            elif transform == "deriv_smooth":
                trans_name = "smoothed d/dx "
            elif transform == "diff":
                trans_name = "diff "
            label = f"{agg_name} of {trans_name}{channel} ({source_name})"

        multiplier = self.multiplier_spin.value()

        import uuid
        stat_id = self.existing_stat.stat_id if self.existing_stat else uuid.uuid4().hex[:8]
        last_val = self.existing_stat.last_value if self.existing_stat else None

        self.result_stat = ConfiguredStat(
            stat_id=stat_id,
            label=label,
            source_id=source_id,
            group=group,
            channel=channel,
            transform=transform,
            aggregation=aggregation,
            multiplier=multiplier,
            last_value=last_val
        )
        self.accept()

    def get_stat(self) -> Optional[ConfiguredStat]:
        return self.result_stat


class CustomTableWidget(QTableWidget):
    """Custom QTableWidget that allows clearing selection when clicking empty space."""
    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item is None:
            self.clearSelection()
        super().mousePressEvent(event)



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


class XZoomViewBox(pg.ViewBox):
    """Custom ViewBox supporting X-axis drag-to-zoom using the left mouse button."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.x_zoom_rect = None

    def mouseDragEvent(self, ev: Any) -> None:
        # Left button drag triggers custom X-axis zoom (holding Shift falls back to standard panning)
        if ev.button() == Qt.LeftButton and not (ev.modifiers() & Qt.ShiftModifier):
            ev.accept()

            if self.x_zoom_rect is None:
                self.x_zoom_rect = QGraphicsRectItem(self)
                # Translucent light blue fill with a dodger blue border
                self.x_zoom_rect.setBrush(QBrush(QColor(135, 206, 250, 80)))
                self.x_zoom_rect.setPen(QPen(QColor(30, 144, 255), 1))
                self.x_zoom_rect.hide()

            if ev.isStart():
                self.x_zoom_rect.show()

            # Map scene points to local coordinate space of this ViewBox
            start_local = self.mapFromScene(ev.buttonDownScenePos())
            current_local = self.mapFromScene(ev.scenePos())

            rect = self.boundingRect()
            x_min = min(start_local.x(), current_local.x())
            x_max = max(start_local.x(), current_local.x())
            y_min = rect.top()
            y_max = rect.bottom()

            self.x_zoom_rect.setRect(x_min, y_min, x_max - x_min, y_max - y_min)

            if ev.isFinish():
                self.x_zoom_rect.hide()
                # Check that the drag distance is meaningful to avoid zooming on clicks
                if abs(current_local.x() - start_local.x()) > 5:
                    start_view = self.mapSceneToView(ev.buttonDownScenePos())
                    current_view = self.mapSceneToView(ev.scenePos())
                    
                    x_start_val = start_view.x()
                    x_finish_val = current_view.x()
                    
                    self.setXRange(min(x_start_val, x_finish_val), max(x_start_val, x_finish_val), padding=0)
        else:
            super().mouseDragEvent(ev)


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
        self.tabs_state: list[AssignmentTabState] = [
            AssignmentTabState("Tab 1", [], [])
        ]
        self.left_axis_series: list[SeriesRef] = self.tabs_state[0].left_axis_series
        self.right_axis_series: list[SeriesRef] = self.tabs_state[0].right_axis_series
        self.active_tab_index = 0

        self.configured_stats: list[ConfiguredStat] = []

        self.plotted_data_cache = []
        self.cursor_items = []
        self.cursor_items_right = []

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#777777", width=1.5, style=Qt.DashLine))
        self.v_line.hide()

        self.L_prev = None
        self.R_prev = None
        self._is_syncing = False

        self.cursor_tooltip = pg.TextItem(
            anchor=(-0.1, 0.1),
            color='k',
            fill=(255, 255, 255, 225),
            border=pg.mkPen('#777777', width=1)
        )
        self.cursor_tooltip.hide()

        self.open_button = QPushButton("Load Files")
        self.open_button.clicked.connect(self.open_file_dialog)

        self.loaded_sources_list = QListWidget()
        self.loaded_sources_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.loaded_sources_list.itemDoubleClicked.connect(self.configure_source_by_item)

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
        self.tree.setHeaderLabels(["Loaded file structure", "Min", "Max"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemDoubleClicked.connect(self.configure_source_by_tree_item)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground("w")
        self.plot_item = self.plot_widget.addPlot(row=0, col=0, viewBox=XZoomViewBox())
        self.plot_item.showGrid(x=True, y=True, alpha=0.25)

        self.right_view_box = pg.ViewBox()
        self.plot_item.showAxis("right")
        self.plot_item.getAxis("right").linkToView(self.right_view_box)
        self.right_view_box.setXLink(self.plot_item)
        self.plot_item.scene().addItem(self.right_view_box)
        self.plot_item.vb.sigResized.connect(self._update_right_view)
        self.plot_item.vb.sigYRangeChanged.connect(self.sync_right_y_zoom)
        self.right_view_box.sigYRangeChanged.connect(self.on_right_y_range_changed)

        # Cursor line addition and interaction
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.scene().sigMouseMoved.connect(self.mouse_moved)
        self.plot_item.sigXRangeChanged.connect(self.recalculate_statistics)

        self.left_series_list = QListWidget()
        self.right_series_list = QListWidget()
        self.left_series_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.right_series_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.left_series_list.itemDoubleClicked.connect(lambda item: self.configure_series_by_item(item, "left"))
        self.right_series_list.itemDoubleClicked.connect(lambda item: self.configure_series_by_item(item, "right"))

        self.assign_left_button = QPushButton("Add Selected To Left")
        self.assign_left_button.clicked.connect(self.add_selected_to_left)
        self.assign_right_button = QPushButton("Add Selected To Right")
        self.assign_right_button.clicked.connect(self.add_selected_to_right)
        self.remove_selected_button = QPushButton("Remove Selected")
        self.remove_selected_button.clicked.connect(self.remove_selected_from_plot)
        self.set_batch_filter_button = QPushButton("Set Filter for Selected")
        self.set_batch_filter_button.clicked.connect(self.set_filter_for_selected)
        self.clear_plot_button = QPushButton("Clear Plot")
        self.clear_plot_button.clicked.connect(self.clear_assignments)

        # Create container widget for the shared assignment lists and buttons
        self.container_widget = QWidget()
        container_layout = QGridLayout(self.container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.left_series_list, 0, 0)
        container_layout.addWidget(self.right_series_list, 0, 1)

        # Button row containing all buttons next to each other
        button_row = QHBoxLayout()
        button_row.addWidget(self.remove_selected_button)
        button_row.addWidget(self.set_batch_filter_button)
        button_row.addWidget(self.clear_plot_button)
        container_layout.addLayout(button_row, 1, 0, 1, 2)

        # Tab widget creation
        self.assignment_tabs = QTabWidget()
        self.assignment_tabs.setTabsClosable(True)
        self.assignment_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: #f1f1f1;
                border: 1px solid #dcdcdc;
                border-bottom: none;
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #555555;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-color: #b8b8b8;
                color: #000000;
            }
            QTabBar::tab:hover {
                background: #e5e5e5;
                color: #000000;
            }
        """)

        # Add '+' button in corner
        self.add_tab_button = QPushButton("+")
        self.add_tab_button.setCursor(Qt.PointingHandCursor)
        self.add_tab_button.setToolTip("Add new tab")
        self.add_tab_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-weight: bold;
                font-size: 16px;
                color: #555555;
                margin-right: 2px;
                margin-top: 1px;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #e2e2e2;
                color: #000000;
                border-radius: 3px;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.add_tab_button.clicked.connect(self.add_assignment_tab)
        self.assignment_tabs.setCornerWidget(self.add_tab_button, Qt.TopRightCorner)

        # Initial Tab Page
        initial_page = QWidget()
        initial_layout = QVBoxLayout(initial_page)
        initial_layout.setContentsMargins(0, 4, 0, 0)
        initial_layout.addWidget(self.container_widget)
        self.assignment_tabs.addTab(initial_page, "Tab 1")

        # Connect signals
        self.assignment_tabs.currentChanged.connect(self.handle_tab_changed)
        self.assignment_tabs.tabCloseRequested.connect(self.handle_tab_close)
        self.assignment_tabs.tabBarDoubleClicked.connect(self.handle_tab_double_clicked)

        selection_box = QGroupBox("Channel Assignment")
        selection_layout = QVBoxLayout(selection_box)
        selection_layout.setContentsMargins(4, 4, 4, 4)
        selection_layout.setSpacing(4)
        selection_layout.addWidget(self.assignment_tabs)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.plot_widget, 4)
        right_layout.addWidget(selection_box, 2)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.addWidget(loaded_box)
        tree_layout.addWidget(self.tree, 1)
        tree_layout.addWidget(self.assign_left_button)
        tree_layout.addWidget(self.assign_right_button)

        # Create collapsible sidebar container (starts collapsed)
        self.sidebar_container = QWidget()
        sidebar_layout = QHBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Toggle button
        self.sidebar_toggle_btn = QPushButton("◀")
        self.sidebar_toggle_btn.setFixedWidth(16)
        self.sidebar_toggle_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.sidebar_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f1f1;
                border: 1px solid #dcdcdc;
                border-top: none;
                border-bottom: none;
                color: #555555;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e5e5e5;
                color: #000000;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.sidebar_toggle_btn)

        # Sidebar content panel
        self.sidebar_content = QWidget()
        self.sidebar_content.setObjectName("sidebar_content_widget")
        self.sidebar_content.setStyleSheet("QWidget#sidebar_content_widget { background-color: #ffffff; border-left: 1px solid #dcdcdc; }")
        sidebar_content_layout = QVBoxLayout(self.sidebar_content)
        sidebar_content_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_content_layout.setSpacing(4)

        # Title
        sidebar_title = QLabel("Statistics")
        sidebar_title.setStyleSheet("font-size: 14px; color: #333333; margin-bottom: 4px;")
        sidebar_content_layout.addWidget(sidebar_title)

        # Stats Table
        self.stats_table = CustomTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.stats_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stats_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setWordWrap(False) # Disable wrapping to prevent word-boundary clipping of hidden lines
        self.stats_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel) # Enable smooth horizontal scrolling
        self.stats_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel) # Enable smooth vertical scrolling
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.horizontalHeader().setHighlightSections(False) # Stop headers from turning bold on selection
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.stats_table.setColumnWidth(0, 180)
        self.stats_table.setColumnWidth(1, 80)
        self.stats_table.setTextElideMode(Qt.ElideNone) # Clip text character-by-character without aggressive ... elision
        self.stats_table.verticalHeader().hide() # Remove the index numbers column
        self.stats_table.itemDoubleClicked.connect(self.edit_selected_stat)
        sidebar_content_layout.addWidget(self.stats_table, 1)

        # Buttons layout
        stats_btn_layout = QHBoxLayout()
        self.add_stat_btn = QPushButton("Add")
        self.add_stat_btn.clicked.connect(self.add_new_stat)
        self.delete_stat_btn = QPushButton("Delete")
        self.delete_stat_btn.clicked.connect(self.delete_selected_stat)

        stats_btn_layout.addWidget(self.add_stat_btn)
        stats_btn_layout.addWidget(self.delete_stat_btn)
        sidebar_content_layout.addLayout(stats_btn_layout)

        sidebar_layout.addWidget(self.sidebar_content)
        self.sidebar_content.hide() # Collapsed by default
        self.sidebar_container.setFixedWidth(16)

        self.main_splitter = QSplitter()
        self.main_splitter.addWidget(tree_panel)
        self.main_splitter.addWidget(right_panel)
        self.main_splitter.addWidget(self.sidebar_container)
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 5)
        self.main_splitter.setStretchFactor(2, 2)
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)
        self.main_splitter.setCollapsible(2, False)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(self.main_splitter, 1)
        self.setCentralWidget(central_widget)

    def _open_native_file_dialog(self) -> Optional[list[str]]:
        """Attempt to open the native OS file picker (zenity/kdialog on Linux)."""
        import subprocess
        import shutil

        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        prefer_kde = "kde" in desktop or "plasma" in desktop

        candidates = ["kdialog", "zenity"] if prefer_kde else ["zenity", "kdialog"]

        for tool in candidates:
            if shutil.which(tool):
                if tool == "zenity":
                    try:
                        cmd = [
                            "zenity",
                            "--file-selection",
                            "--multiple",
                            "--separator=|",
                            "--title=Open Files",
                            "--file-filter=Data Files | *.tdms *.csv *.xlsx *.xls",
                            "--file-filter=All Files | *"
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            paths = result.stdout.strip().split("|")
                            return [p for p in paths if p]
                        elif result.returncode == 1:
                            return []  # User cancelled
                    except Exception:
                        pass
                elif tool == "kdialog":
                    try:
                        cmd = [
                            "kdialog",
                            "--getopenfilename",
                            os.getcwd(),
                            "*.tdms *.csv *.xlsx *.xls|Data Files\n*|All Files",
                            "--multiple",
                            "--separate-output"
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            paths = result.stdout.strip().split("\n")
                            return [p for p in paths if p]
                        elif result.returncode == 1:
                            return []  # User cancelled
                    except Exception:
                        pass
        return None

    def open_file_dialog(self) -> None:
        """Open one or more TDMS/CSV/Excel files from disk, using native picker if possible."""
        
        # Disabled native picker due to performance issues
        # file_paths = self._open_native_file_dialog()
        file_paths = None

        # If native picker was not available or failed to execute, fall back to Qt file dialog
        if file_paths is None:
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
                self.progress_dialog.setLabelText(f"Loading {completed} / {len(paths_to_load)} files...")
                if self.progress_dialog:
                    self.progress_dialog.setValue(completed)

        def handle_finished():
            if self.progress_dialog:
                self.progress_dialog.close()

            # Process all loaded results
            nonlocal loaded_count
            new_sources = []
            for source in loaded_results:
                self.loaded_sources[source.source_id] = source
                self.source_order.append(source.source_id)
                new_sources.append(source)
                loaded_count += 1

            if loaded_count:
                # Open modal configuration dialog for each newly loaded file
                for source in new_sources:
                    dialog = FileConfigDialog(source, self)
                    if dialog.exec() == QDialog.Accepted:
                        prescaler, offset, x_chan = dialog.get_settings()
                        source.prescaler = prescaler
                        source.offset = offset
                        source.x_channel = x_chan

                self.refresh_loaded_sources_view()
                self.refresh_tree()

            if errors:
                QMessageBox.warning(
                    self,
                    "Some Files Could Not Be Loaded",
                    "\n".join(errors),
                )

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

    def configure_source_by_item(self, item: QListWidgetItem) -> None:
        """Open the configuration dialog for a loaded file when double-clicked."""
        source_id = item.data(Qt.UserRole)
        if not source_id:
            return
        source = self.loaded_sources.get(str(source_id))
        if source is None:
            return

        dialog = FileConfigDialog(source, self)
        if dialog.exec() == QDialog.Accepted:
            prescaler, offset, x_chan = dialog.get_settings()
            source.prescaler = prescaler
            source.offset = offset
            source.x_channel = x_chan

            self.refresh_loaded_sources_view()
            self.refresh_tree()
            self.update_plot()

    def configure_source_by_tree_item(self, item: QTreeWidgetItem, column: int) -> None:
        """Open the configuration dialog for a loaded file or channel when double-clicked in the tree."""
        payload = item.data(0, Qt.UserRole)
        if not isinstance(payload, dict):
            return

        if payload.get("type") == "source":
            source_id = payload.get("source_id")
            if not source_id:
                return
            source = self.loaded_sources.get(str(source_id))
            if source is None:
                return

            dialog = FileConfigDialog(source, self)
            if dialog.exec() == QDialog.Accepted:
                prescaler, offset, x_chan = dialog.get_settings()
                source.prescaler = prescaler
                source.offset = offset
                source.x_channel = x_chan

                self.refresh_loaded_sources_view()
                self.refresh_tree()
                self.update_plot()

        elif "source_id" in payload and "group" in payload and "channel" in payload:
            source_id = payload["source_id"]
            group_name = payload["group"]
            channel_name = payload["channel"]

            source = self.loaded_sources.get(str(source_id))
            if source is None:
                return

            # Retrieve current custom limit overrides for this channel
            limits = getattr(source, "channel_limits", {}).get((group_name, channel_name))
            curr_min, curr_max = (None, None) if limits is None else limits

            display_name = f"{source.display_name} / {group_name} / {channel_name}"
            dialog = ChannelLimitDialog(display_name, curr_min, curr_max, self)
            if dialog.exec() == QDialog.Accepted:
                new_min, new_max = dialog.get_settings()
                if new_min is None and new_max is None:
                    # Clear override if both are empty
                    source.channel_limits.pop((group_name, channel_name), None)
                else:
                    source.channel_limits[(group_name, channel_name)] = (new_min, new_max)

                self.refresh_tree()
                self.update_plot()

    def configure_series_by_item(self, item: QListWidgetItem, axis: str) -> None:
        """Open the configuration dialog for a plotted channel when double-clicked."""
        target_list = self.left_series_list if axis == "left" else self.right_series_list
        target_series = self.left_axis_series if axis == "left" else self.right_axis_series

        # Find the index of the clicked item
        row = target_list.row(item)
        if not (0 <= row < len(target_series)):
            return

        ref = target_series[row]
        source = self.loaded_sources.get(ref.source_id)
        if source is None:
            return

        dialog = SeriesConfigDialog(ref, source, self)
        if dialog.exec() == QDialog.Accepted:
            f_chan, f_val = dialog.get_settings()
            ref.filter_channel = f_chan
            ref.filter_value = f_val

            self._refresh_series_list(axis)
            self.update_plot()

    def set_filter_for_selected(self) -> None:
        """Set the same filter settings for all selected channels in the axis lists (must be from the same file)."""
        left_sel = self.left_series_list.selectedItems()
        right_sel = self.right_series_list.selectedItems()

        selected_refs = []
        for item in left_sel:
            row = self.left_series_list.row(item)
            if 0 <= row < len(self.left_axis_series):
                selected_refs.append(self.left_axis_series[row])
        for item in right_sel:
            row = self.right_series_list.row(item)
            if 0 <= row < len(self.right_axis_series):
                selected_refs.append(self.right_axis_series[row])

        if not selected_refs:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select one or more channels in the axis lists to batch-filter."
            )
            return

        # Ensure all selected channels are from the same loaded file
        source_ids = {ref.source_id for ref in selected_refs}
        if len(source_ids) > 1:
            QMessageBox.warning(
                self,
                "Multiple Files Selected",
                "Batch filtering can only be applied to channels from the same file. Please select channels from one file only."
            )
            return

        source_id = list(source_ids)[0]
        source = self.loaded_sources.get(source_id)
        if source is None:
            return

        # Open SeriesConfigDialog using the first selected channel's settings as template
        template_ref = selected_refs[0]
        dialog = SeriesConfigDialog(template_ref, source, self)
        if dialog.exec() == QDialog.Accepted:
            f_chan, f_val = dialog.get_settings()
            for ref in selected_refs:
                ref.filter_channel = f_chan
                ref.filter_value = f_val

            self._refresh_series_list("left")
            self._refresh_series_list("right")
            self.update_plot()

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

    def clear_loaded_sources(self) -> None:
        """Remove all loaded sources and plotted series."""
        if not self.loaded_sources:
            return

        self.loaded_sources.clear()
        self.source_order.clear()
        for state in self.tabs_state:
            state.left_axis_series.clear()
            state.right_axis_series.clear()
        self.refresh_loaded_sources_view()
        self.refresh_tree()
        self.left_series_list.clear()
        self.right_series_list.clear()
        self.update_plot()

    def refresh_loaded_sources_view(self) -> None:
        """Refresh the loaded-files list."""
        self.loaded_sources_list.clear()
        for source_id in self.source_order:
            source = self.loaded_sources.get(source_id)
            if source is None:
                continue
            item = QListWidgetItem(get_source_label(source))
            item.setData(Qt.UserRole, source_id)
            item.setToolTip(source.path)
            self.loaded_sources_list.addItem(item)

    def refresh_tree(self) -> None:
        """Rebuild the tree for all loaded files."""
        self.tree.clear()

        for source_id in self.source_order:
            source = self.loaded_sources.get(source_id)
            if source is None:
                continue

            x_desc = "Index" if source.x_channel is None else f"{source.x_channel[0]}/{source.x_channel[1]}"
            display_text = f"{source.display_name}"
            source_item = QTreeWidgetItem([display_text, "", ""])
            source_item.setData(0, Qt.UserRole, {"type": "source", "source_id": source_id})
            source_item.setToolTip(0, source.path)

            for group in source.structure.get("groups", []):
                group_name = group.get("name", "Unnamed Group")
                group_item = QTreeWidgetItem([group_name, "", ""])
                group_item.setData(0, Qt.UserRole, {"type": "group", "source_id": source_id, "group": group_name})

                for channel in group.get("channels", []):
                    channel_name = channel.get("name", "Unnamed Channel")
                    
                    # Check for limits override
                    limits = getattr(source, "channel_limits", {}).get((group_name, channel_name))
                    if limits is not None:
                        lim_min, lim_max = limits
                        min_val = lim_min if lim_min is not None else channel.get("min")
                        max_val = lim_max if lim_max is not None else channel.get("max")
                    else:
                        min_val = channel.get("min")
                        max_val = channel.get("max")

                    min_value = self._format_number(min_val)
                    max_value = self._format_number(max_val)
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
        seen: set[tuple[str, str, str]] = set()
        for item in self.tree.selectedItems():
            payload = item.data(0, Qt.UserRole)
            if not isinstance(payload, dict):
                continue
            source_id = payload.get("source_id")
            group_name = payload.get("group")
            channel_name = payload.get("channel")
            if source_id and group_name and channel_name:
                key = (str(source_id), str(group_name), str(channel_name))
                if key not in seen:
                    refs.append(SeriesRef(key[0], key[1], key[2]))
                    seen.add(key)
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
            used_colors = {s.color for s in self.left_axis_series + self.right_axis_series if getattr(s, "color", None)}
            chosen_color = None
            for color in self.series_palette:
                if color not in used_colors:
                    chosen_color = color
                    break
            if not chosen_color:
                total_plotted = len(self.left_axis_series) + len(self.right_axis_series)
                chosen_color = self.series_palette[total_plotted % len(self.series_palette)]

            new_ref = SeriesRef(
                source_id=ref.source_id,
                group=ref.group,
                channel=ref.channel,
                color=chosen_color
            )
            target_series.append(new_ref)

        self._refresh_series_list("left")
        self._refresh_series_list("right")
        self.update_plot()

        axis_name = "left" if axis == "left" else "right"

    def _refresh_series_list(self, axis: str) -> None:
        """Refresh the plotted-series list for one axis."""
        target_series = self.left_axis_series if axis == "left" else self.right_axis_series
        target_widget = self.left_series_list if axis == "left" else self.right_series_list

        target_widget.clear()
        for index, ref in enumerate(target_series):
            if not getattr(ref, "color", None):
                ref.color = self._series_color(axis, index, len(self.left_axis_series))
            color = ref.color
            item = QListWidgetItem(self._series_ref_label(ref))
            item.setIcon(self._color_icon(color))
            target_widget.addItem(item)

    def remove_selected_from_plot(self) -> None:
        """Remove all selected items in the Left and Right axis lists from the plot."""
        left_rows = sorted({item.row() for item in self.left_series_list.selectedIndexes()}, reverse=True)
        right_rows = sorted({item.row() for item in self.right_series_list.selectedIndexes()}, reverse=True)

        removed_count = 0
        for row in left_rows:
            if 0 <= row < len(self.left_axis_series):
                del self.left_axis_series[row]
                removed_count += 1

        for row in right_rows:
            if 0 <= row < len(self.right_axis_series):
                del self.right_axis_series[row]
                removed_count += 1

        if removed_count > 0:
            self._refresh_series_list("left")
            self._refresh_series_list("right")
            self.update_plot()

    def clear_assignments(self) -> None:
        """Clear both axis assignments and reset the plot."""
        self.left_axis_series.clear()
        self.right_axis_series.clear()
        self.left_series_list.clear()
        self.right_series_list.clear()
        self.update_plot()

    def update_plot(self) -> None:
        """Render the currently assigned channels on a shared plot with two Y axes."""
        # Clean up any existing hover dots
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
        self.plot_item.addItem(self.cursor_tooltip, ignoreBounds=True)

        self.plotted_data_cache = []

        left_curves = []
        right_curves = []

        for index, ref in enumerate(self.left_axis_series):
            series = self._get_channel_data(ref)
            if series is None:
                continue
            x_values, y_values = series
            if not getattr(ref, "color", None):
                ref.color = self._series_color("left", index, len(self.left_axis_series))
            color = ref.color
            curve = self.plot_item.plot(x_values, y_values, pen=pg.mkPen(color, width=2))
            curve.setDownsampling(auto=True, method='peak')
            if hasattr(curve, 'setSkipFiniteCheck'):
                curve.setSkipFiniteCheck(True)
            left_curves.append(curve)

            # Create interactive cursor indicators
            dot = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(color), pen=pg.mkPen('w', width=1))
            dot.hide()
            self.plot_item.addItem(dot)
            self.cursor_items.append(dot)

            self.plotted_data_cache.append({
                "label": self._series_ref_label(ref),
                "x_values": x_values,
                "y_values": y_values,
                "axis": "Left",
                "color": color,
                "dot_item": dot,
            })

        for index, ref in enumerate(self.right_axis_series):
            series = self._get_channel_data(ref)
            if series is None:
                continue
            x_values, y_values = series
            if not getattr(ref, "color", None):
                ref.color = self._series_color("right", index, len(self.left_axis_series))
            color = ref.color
            curve = pg.PlotDataItem(x_values, y_values, pen=pg.mkPen(color, width=2))
            curve.setDownsampling(auto=True, method='peak')
            if hasattr(curve, 'setSkipFiniteCheck'):
                curve.setSkipFiniteCheck(True)
            self.right_view_box.addItem(curve)
            right_curves.append(curve)

            # Create interactive cursor indicators (Right Y-axis scale)
            dot = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(color), pen=pg.mkPen('w', width=1))
            dot.hide()
            self.right_view_box.addItem(dot)
            self.cursor_items_right.append(dot)

            self.plotted_data_cache.append({
                "label": self._series_ref_label(ref),
                "x_values": x_values,
                "y_values": y_values,
                "axis": "Right",
                "color": color,
                "dot_item": dot,
            })

        # Add the vertical cursor line back on top of the left-axis curves
        self.plot_item.addItem(self.v_line, ignoreBounds=True)

        if left_curves or right_curves:
            self.plot_item.vb.autoRange()

        if right_curves:
            self.right_view_box.autoRange()
            self._update_right_view()

        # Update baseline ranges for synchronized zooming
        self.L_prev = self.plot_item.vb.viewRange()[1]
        self.R_prev = self.right_view_box.viewRange()[1]
        self.recalculate_statistics()
        # else:
        #     self.plot_item.getAxis("right").setLabel("Right axis")

        # if not left_curves and not right_curves:
        #     self.plot_item.setLabel("left", "Left axis")



    def mouse_moved(self, evt) -> None:
        """Handle mouse movement to update the vertical cursor line and show values inside a floating tooltip."""
        pos = evt
        if self.plot_item.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.plot_item.vb.mapSceneToView(pos)
            x = mousePoint.x()

            # Position the vertical line
            self.v_line.setValue(x)
            self.v_line.show()

            html_rows = [f"<b>X:</b> {x:.6g}"]

            for item in getattr(self, "plotted_data_cache", []):
                x_vals = item["x_values"]
                y_vals = item["y_values"]
                dot = item.get("dot_item")
                label_text = item.get("label")
                color = item.get("color")

                if x_vals is None or len(x_vals) == 0:
                    if dot: dot.hide()
                    continue

                # Find nearest x index using fast binary search (fallback to argmin if not sorted)
                if len(x_vals) > 0:
                    idx = np.searchsorted(x_vals, x)
                    idx = np.clip(idx, 0, len(x_vals) - 1)
                    if idx > 0 and abs(x_vals[idx - 1] - x) < abs(x_vals[idx] - x):
                        idx -= 1
                    nearest_x = x_vals[idx]
                    nearest_y = y_vals[idx]
                else:
                    continue

                # Update dot position
                if dot:
                    dot.setData(x=[nearest_x], y=[nearest_y])
                    dot.show()

                # Add row to tooltip
                html_rows.append(
                    f'<span style="color: {color}; font-size: 14px;">●</span> {nearest_y:.6g}'
                )

            # Set tooltip text and position it next to the mouse cursor
            self.cursor_tooltip.setHtml("<br/>".join(html_rows))
            self.cursor_tooltip.setPos(x, mousePoint.y())
            self.cursor_tooltip.show()

        else:
            self.v_line.hide()
            self.cursor_tooltip.hide()
            for item in getattr(self, "plotted_data_cache", []):
                dot = item.get("dot_item")
                if dot: dot.hide()

    def _get_channel_data(self, series_ref: SeriesRef) -> Optional[tuple[Any, Any]]:
        """Return x and y arrays for the selected channel."""
        source = self.loaded_sources.get(series_ref.source_id)
        if source is None:
            return None
        return get_channel_data(
            source,
            series_ref.group,
            series_ref.channel,
            series_ref.filter_channel,
            series_ref.filter_value,
        )

    def _series_ref_label(self, series_ref: SeriesRef) -> str:
        """Return a human-friendly label for a plotted series."""
        source = self.loaded_sources.get(series_ref.source_id)
        source_name = source.display_name if source is not None else series_ref.source_id
        base_label = f"{source_name} / {series_ref.group} / {series_ref.channel}"
        if series_ref.filter_channel is not None:
            f_group, f_chan = series_ref.filter_channel
            base_label += f"\n({f_group} / {f_chan} == {series_ref.filter_value:.3g})"
        return base_label

    def _prune_plot_state(self) -> None:
        """Remove series references that point to unloaded sources across all tabs."""
        loaded_ids = set(self.loaded_sources)
        for state in self.tabs_state:
            state.left_axis_series[:] = [ref for ref in state.left_axis_series if ref.source_id in loaded_ids]
            state.right_axis_series[:] = [ref for ref in state.right_axis_series if ref.source_id in loaded_ids]

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

    def sync_right_y_zoom(self) -> None:
        """Synchronize the right Y-axis zoom/pan with the left Y-axis."""
        if getattr(self, "_is_syncing", False):
            return
        self._is_syncing = True
        try:
            L_curr = self.plot_item.vb.viewRange()[1]
            R_curr = self.right_view_box.viewRange()[1]

            if self.L_prev is not None and self.R_prev is not None:
                L_prev_min, L_prev_max = self.L_prev
                L_curr_min, L_curr_max = L_curr
                R_prev_min, R_prev_max = self.R_prev

                L_width_prev = L_prev_max - L_prev_min
                L_width_curr = L_curr_max - L_curr_min

                if L_width_prev > 0 and L_width_curr > 0:
                    # Calculate scale factor
                    scale = L_width_curr / L_width_prev

                    # Calculate relative pan shift
                    L_center_prev = (L_prev_min + L_prev_max) / 2
                    L_center_curr = (L_curr_min + L_curr_max) / 2
                    shift_left = (L_center_curr - L_center_prev) / L_width_prev

                    # Apply to right axis
                    R_width_prev = R_prev_max - R_prev_min
                    R_width_curr = R_width_prev * scale
                    shift_right = shift_left * R_width_prev

                    R_center_prev = (R_prev_min + R_prev_max) / 2
                    R_center_curr = R_center_prev + shift_right

                    R_new_min = R_center_curr - R_width_curr / 2
                    R_new_max = R_center_curr + R_width_curr / 2

                    self.right_view_box.setYRange(R_new_min, R_new_max, padding=0)
                    R_curr = (R_new_min, R_new_max)

            # Update baselines
            self.L_prev = L_curr
            self.R_prev = R_curr
        finally:
            self._is_syncing = False

    def on_right_y_range_changed(self) -> None:
        """Update R_prev when the right axis range is changed."""
        if not getattr(self, "_is_syncing", False):
            self.R_prev = self.right_view_box.viewRange()[1]

    def toggle_sidebar(self) -> None:
        """Collapse or expand the right statistics sidebar."""
        is_visible = self.sidebar_content.isVisible()
        if is_visible:
            # Save the current width of the sidebar before collapsing so we can restore it
            self._sidebar_last_width = self.sidebar_container.width()
            self.sidebar_content.hide()
            self.sidebar_toggle_btn.setText("◀")
            # Lock the sidebar container width to 16px (collapsed state)
            self.sidebar_container.setFixedWidth(16)
            # Update splitter sizes so the collapsed sidebar is tight (only 16px)
            sizes = self.main_splitter.sizes()
            if len(sizes) == 3:
                # Give the collapsed space back to the middle panel
                sizes[1] += sizes[2] - 16
                sizes[2] = 16
                self.main_splitter.setSizes(sizes)
        else:
            # Unlock the sidebar container width with a minimum size of 166px (150px content + 16px button)
            self.sidebar_container.setMinimumWidth(166)
            self.sidebar_container.setMaximumWidth(16777215) # QWIDGETSIZE_MAX

            self.sidebar_content.show()
            self.sidebar_toggle_btn.setText("▶")
            # Restore to previous width, or default to a reasonable width (similar to tree view)
            sizes = self.main_splitter.sizes()
            if len(sizes) == 3:
                restore_width = getattr(self, "_sidebar_last_width", 250)
                if restore_width < 100:
                    restore_width = 250
                # Take space from the middle panel to expand the sidebar
                sizes[1] = max(200, sizes[1] - (restore_width - 16))
                sizes[2] = restore_width
                self.main_splitter.setSizes(sizes)

    def add_new_stat(self) -> None:
        """Open the dialog to add a new statistic."""
        plotted = self._get_all_plotted_channels()
        if not plotted:
            QMessageBox.information(self, "No Plotted Channels", "Please plot at least one channel in any tab before adding statistics.")
            return

        dialog = AddEditStatDialog(plotted, self.loaded_sources, parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_stat = dialog.get_stat()
            if new_stat:
                self.configured_stats.append(new_stat)
                self.recalculate_statistics()

    def edit_selected_stat(self, item: QTableWidgetItem) -> None:
        """Open the dialog to edit the double-clicked statistic."""
        row = item.row()
        if not (0 <= row < len(self.configured_stats)):
            return

        stat = self.configured_stats[row]
        plotted = self._get_all_plotted_channels()

        dialog = AddEditStatDialog(plotted, self.loaded_sources, existing_stat=stat, parent=self)
        if dialog.exec() == QDialog.Accepted:
            edited_stat = dialog.get_stat()
            if edited_stat:
                self.configured_stats[row] = edited_stat
                self.recalculate_statistics()

    def delete_selected_stat(self) -> None:
        """Delete all currently selected statistics."""
        selected_rows = sorted({item.row() for item in self.stats_table.selectedItems()}, reverse=True)
        if not selected_rows:
            return

        if len(selected_rows) == 1:
            stat = self.configured_stats[selected_rows[0]]
            msg = f"Are you sure you want to delete '{stat.label}'?"
        else:
            msg = f"Are you sure you want to delete the {len(selected_rows)} selected statistics?"

        confirm = QMessageBox.question(
            self,
            "Delete Statistics",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            for row in selected_rows:
                self.configured_stats.pop(row)
            self.recalculate_statistics()

    def _get_all_plotted_channels(self) -> list[tuple[str, str, str, str]]:
        """Return a list of all currently plotted channels across all tabs."""
        plotted = []
        seen = set()
        for state in self.tabs_state:
            tab_name = state.name
            for ref in state.left_axis_series + state.right_axis_series:
                key = (tab_name, ref.source_id, ref.group, ref.channel)
                if key not in seen:
                    plotted.append(key)
                    seen.add(key)
        return plotted

    def recalculate_statistics(self) -> None:
        """Compute statistics for all configured metrics using the active tab's visible viewport range."""
        if not hasattr(self, "configured_stats"):
            return

        try:
            xmin, xmax = self.plot_item.vb.viewRange()[0]
        except Exception:
            xmin, xmax = None, None

        active_channels = {}
        for ref in self.left_axis_series:
            active_channels[(ref.source_id, ref.group, ref.channel)] = ref
        for ref in self.right_axis_series:
            active_channels[(ref.source_id, ref.group, ref.channel)] = ref

        self.stats_table.setRowCount(len(self.configured_stats))

        for idx, stat in enumerate(self.configured_stats):
            key = (stat.source_id, stat.group, stat.channel)
            is_active = key in active_channels

            val_str = "N/A"
            computed_val = None

            if is_active and xmin is not None and xmax is not None:
                ref = active_channels[key]
                series = self._get_channel_data(ref)
                if series is not None:
                    x_full, y_full = series
                    visible_mask = (x_full >= xmin) & (x_full <= xmax)
                    x_vis = x_full[visible_mask]
                    y_vis = y_full[visible_mask]

                    if len(x_vis) > 0:
                        # Apply pre-processing constant multiplier before anything else
                        multiplier = getattr(stat, "multiplier", 1.0)
                        y_vis = y_vis * multiplier

                        x_t, y_t = x_vis, y_vis
                        valid_calc = True

                        if stat.transform == "deriv_raw":
                            if len(x_vis) >= 2:
                                dx = np.diff(x_vis)
                                dx_mask = dx != 0
                                if np.any(dx_mask):
                                    y_t = np.diff(y_vis)[dx_mask] / dx[dx_mask]
                                    x_t = ((x_vis[:-1] + x_vis[1:]) / 2.0)[dx_mask]
                                else:
                                    valid_calc = False
                            else:
                                valid_calc = False

                        elif stat.transform == "deriv_smooth":
                            if len(x_vis) >= 2:
                                dx = np.diff(x_vis)
                                dx_mask = dx != 0
                                if np.any(dx_mask):
                                    y_raw_deriv = np.diff(y_vis)[dx_mask] / dx[dx_mask]
                                    x_raw_deriv = ((x_vis[:-1] + x_vis[1:]) / 2.0)[dx_mask]

                                    window = 5
                                    if len(y_raw_deriv) >= window:
                                        y_t = np.convolve(y_raw_deriv, np.ones(window)/window, mode='valid')
                                        start_idx = (window - 1) // 2
                                        end_idx = start_idx + len(y_t)
                                        x_t = x_raw_deriv[start_idx:end_idx]
                                    else:
                                        y_t = y_raw_deriv
                                        x_t = x_raw_deriv
                                else:
                                    valid_calc = False
                            else:
                                valid_calc = False

                        elif stat.transform == "diff":
                            if len(x_vis) >= 2:
                                y_t = np.diff(y_vis)
                                x_t = x_vis[:-1]
                            else:
                                valid_calc = False

                        if valid_calc and len(y_t) > 0:
                            try:
                                if stat.aggregation == "min":
                                    computed_val = float(np.min(y_t))
                                elif stat.aggregation == "max":
                                    computed_val = float(np.max(y_t))
                                elif stat.aggregation == "avg":
                                    computed_val = float(np.mean(y_t))
                                elif stat.aggregation == "median":
                                    computed_val = float(np.median(y_t))
                                elif stat.aggregation == "integral":
                                    if len(x_t) >= 2:
                                        dx = np.diff(x_t)
                                        avg_y = (y_t[:-1] + y_t[1:]) / 2.0
                                        computed_val = float(np.sum(avg_y * dx))
                                    else:
                                        computed_val = 0.0
                                elif stat.aggregation == "net_change":
                                    computed_val = float(y_t[-1] - y_t[0])
                            except Exception:
                                computed_val = None

            if computed_val is not None:
                stat.last_value = computed_val
                val_str = f"{computed_val:.6g}"
            elif stat.last_value is not None:
                val_str = f"{stat.last_value:.6g}"

            lbl_item = QTableWidgetItem(stat.label)
            val_item = QTableWidgetItem(val_str)

            if not is_active:
                lbl_item.setFlags(lbl_item.flags() & ~Qt.ItemIsEnabled)
                val_item.setFlags(val_item.flags() & ~Qt.ItemIsEnabled)

            self.stats_table.setItem(idx, 0, lbl_item)
            self.stats_table.setItem(idx, 1, val_item)

    def add_assignment_tab(self) -> None:

        """Create a new assignment tab, inheriting the current tab's settings."""
        curr_idx = self.assignment_tabs.currentIndex()
        if 0 <= curr_idx < len(self.tabs_state):
            curr_state = self.tabs_state[curr_idx]
            left_copy = curr_state.left_axis_series
            right_copy = curr_state.right_axis_series
            # Get current viewport range
            try:
                curr_x = self.plot_item.vb.viewRange()[0]
                curr_ly = self.plot_item.vb.viewRange()[1]
                curr_ry = self.right_view_box.viewRange()[1]
            except Exception:
                curr_x = None
                curr_ly = None
                curr_ry = None
        else:
            left_copy = []
            right_copy = []
            curr_x = None
            curr_ly = None
            curr_ry = None

        new_tab_num = 1
        existing_names = {t.name for t in self.tabs_state}
        while f"Tab {new_tab_num}" in existing_names:
            new_tab_num += 1
        new_name = f"Tab {new_tab_num}"

        # Create tab state
        new_state = AssignmentTabState(new_name, left_copy, right_copy)
        new_state.x_range = curr_x
        new_state.left_y_range = curr_ly
        new_state.right_y_range = curr_ry
        self.tabs_state.append(new_state)

        # Create page widget
        new_page = QWidget()
        new_layout = QVBoxLayout(new_page)
        new_layout.setContentsMargins(0, 4, 0, 0)

        # Add page to tab widget
        self.assignment_tabs.addTab(new_page, new_name)
        # Select the newly created tab (triggers handle_tab_changed)
        self.assignment_tabs.setCurrentIndex(self.assignment_tabs.count() - 1)

    def handle_tab_changed(self, index: int) -> None:
        """Handle switching between assignment tabs."""
        if index < 0 or index >= len(self.tabs_state):
            return

        # 1. Save current viewport state to the tab we are switching AWAY from
        prev_idx = getattr(self, "active_tab_index", 0)
        if 0 <= prev_idx < len(self.tabs_state):
            try:
                prev_state = self.tabs_state[prev_idx]
                prev_state.x_range = self.plot_item.vb.viewRange()[0]
                prev_state.left_y_range = self.plot_item.vb.viewRange()[1]
                prev_state.right_y_range = self.right_view_box.viewRange()[1]
            except Exception:
                pass

        # 2. Move the container widget to the active tab's layout
        active_page = self.assignment_tabs.widget(index)
        if active_page and active_page.layout():
            active_page.layout().addWidget(self.container_widget)

        # 3. Update the active lists references
        state = self.tabs_state[index]
        self.left_axis_series = state.left_axis_series
        self.right_axis_series = state.right_axis_series

        # 4. Refresh the UI lists and redraw the plot
        self._refresh_series_list("left")
        self._refresh_series_list("right")
        self.update_plot()

        # 5. Restore viewport state if it exists
        if state.x_range is not None:
            self._is_syncing = True
            try:
                self.plot_item.vb.setXRange(state.x_range[0], state.x_range[1], padding=0)
                self.plot_item.vb.setYRange(state.left_y_range[0], state.left_y_range[1], padding=0)
                self.right_view_box.setYRange(state.right_y_range[0], state.right_y_range[1], padding=0)
                self.L_prev = state.left_y_range
                self.R_prev = state.right_y_range
            finally:
                self._is_syncing = False

        # 6. Set the new active tab index
        self.active_tab_index = index

    def handle_tab_close(self, index: int) -> None:
        """Close the tab at the given index, preserving at least one tab."""
        if self.assignment_tabs.count() <= 1:
            QMessageBox.information(self, "Close Tab", "At least one tab must remain active.")
            return

        confirm = QMessageBox.question(
            self,
            "Close Tab",
            f"Are you sure you want to close '{self.tabs_state[index].name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # Safely disconnect to prevent intermediate range updates
        self.assignment_tabs.currentChanged.disconnect(self.handle_tab_changed)
        try:
            self.assignment_tabs.removeTab(index)
            self.tabs_state.pop(index)
        finally:
            self.assignment_tabs.currentChanged.connect(self.handle_tab_changed)

        # Manually trigger layout shift to the current active tab
        new_active = self.assignment_tabs.currentIndex()
        self.handle_tab_changed(new_active)

    def handle_tab_double_clicked(self, index: int) -> None:
        """Rename the double-clicked tab."""
        if index < 0 or index >= len(self.tabs_state):
            return

        current_name = self.tabs_state[index].name
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Tab",
            "Enter new name for the tab:",
            QLineEdit.Normal,
            current_name
        )
        if ok and new_name.strip():
            new_name = new_name.strip()
            self.tabs_state[index].name = new_name
            self.assignment_tabs.setTabText(index, new_name)



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
