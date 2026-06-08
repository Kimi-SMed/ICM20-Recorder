"""Post-recording CH1 review plot with pan and button-based zoom.

After stopping a recording, this widget loads the CSV and displays the full
CH1 waveform with:
  - X axis: seconds from recording start (converted from timestamp_ms)
  - Mouse left-drag to pan (scroll wheel zoom DISABLED)
  - Button-based X/Y zoom (±10% per click, centered on cursor position)
  - A draggable vertical cursor line for time alignment with the live sweep
  - Close button to dismiss the review panel
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
)

from icm.config import AMPLITUDE_DIVISOR, CSV_DEFAULT_DIR

logger = logging.getLogger(__name__)

# Zoom factor per click (10%)
ZOOM_FACTOR = 0.10


class ReviewPlotWidget(QWidget):
    """Zoomable/pannable CH1 review plot shown after recording stops."""

    # Emitted when user clicks the close button
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._csv_path: Optional[Path] = None
        self._timestamps: Optional[np.ndarray] = None
        self._ch1_data: Optional[np.ndarray] = None
        self._setup_ui()
        self.hide()  # hidden until a recording is loaded

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Top toolbar: title + zoom buttons + close
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)

        self._title_label = QLabel("Recording Review")
        self._title_label.setStyleSheet(
            "font-weight: bold; padding: 2px 6px;"
        )
        toolbar.addWidget(self._title_label)

        # Live cursor readout (updated as cursor is dragged)
        self._cursor_readout = QLabel("t = -- s,  y = -- mV")
        self._cursor_readout.setStyleSheet(
            "padding: 2px 8px; color: #cc2200; font-family: monospace;"
        )
        toolbar.addWidget(self._cursor_readout)

        toolbar.addStretch()

        # X axis zoom buttons
        self._x_zoom_in_btn = QPushButton("X+")
        self._x_zoom_in_btn.setFixedWidth(36)
        self._x_zoom_in_btn.setToolTip("X axis zoom in (show less time)")
        self._x_zoom_in_btn.clicked.connect(self._on_x_zoom_in)
        toolbar.addWidget(self._x_zoom_in_btn)

        self._x_zoom_out_btn = QPushButton("X-")
        self._x_zoom_out_btn.setFixedWidth(36)
        self._x_zoom_out_btn.setToolTip("X axis zoom out (show more time)")
        self._x_zoom_out_btn.clicked.connect(self._on_x_zoom_out)
        toolbar.addWidget(self._x_zoom_out_btn)

        # Y axis zoom buttons
        self._y_zoom_in_btn = QPushButton("Y+")
        self._y_zoom_in_btn.setFixedWidth(36)
        self._y_zoom_in_btn.setToolTip("Y axis zoom in")
        self._y_zoom_in_btn.clicked.connect(self._on_y_zoom_in)
        toolbar.addWidget(self._y_zoom_in_btn)

        self._y_zoom_out_btn = QPushButton("Y-")
        self._y_zoom_out_btn.setFixedWidth(36)
        self._y_zoom_out_btn.setToolTip("Y axis zoom out")
        self._y_zoom_out_btn.clicked.connect(self._on_y_zoom_out)
        toolbar.addWidget(self._y_zoom_out_btn)

        # Load button: open any CSV file
        self._load_btn = QPushButton("Load CSV")
        self._load_btn.setToolTip("Load any recorded CSV file")
        self._load_btn.clicked.connect(self._on_load_clicked)
        toolbar.addWidget(self._load_btn)

        # Close button
        self._close_btn = QPushButton("Close")
        self._close_btn.setToolTip("Close review panel")
        self._close_btn.clicked.connect(self._on_close)
        toolbar.addWidget(self._close_btn)

        layout.addLayout(toolbar)

        # Plot area
        self._graphics = pg.GraphicsLayoutWidget()
        self._graphics.setBackground((245, 245, 245))
        layout.addWidget(self._graphics)

        self._plot = self._graphics.addPlot(row=0, col=0)
        self._plot.setLabel("left", "CH1 (mV)")
        self._plot.setLabel("bottom", "Time (s from start)")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        # Allow left-drag pan only; disable scroll wheel zoom
        self._plot.setMouseEnabled(x=True, y=False)
        self._plot.setMenuEnabled(False)
        vb = self._plot.getViewBox()
        vb.setMouseMode(3)  # PanMode = 3 in pyqtgraph
        # Disable wheel zoom
        vb.wheelEvent = lambda ev: None

        # CH1 curve
        self._curve = self._plot.plot(
            pen=pg.mkPen((30, 100, 200), width=1), connect="finite"
        )

        # Draggable vertical cursor line (no label text)
        self._cursor = pg.InfiniteLine(
            angle=90,
            movable=True,
            pen=pg.mkPen((200, 50, 50), width=2, style=Qt.PenStyle.DashLine),
        )
        self._plot.addItem(self._cursor)
        # Update readout whenever cursor is moved
        self._cursor.sigPositionChanged.connect(self._on_cursor_moved)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_csv(self, csv_path: Path) -> bool:
        """Load a recorded CSV and display CH1.

        Returns True if loaded successfully, False otherwise.
        """
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error("Failed to load CSV for review: %s", e)
            return False

        if df.empty or "timestamp_ms" not in df.columns or "channel_1" not in df.columns:
            logger.warning("CSV is empty or missing required columns")
            return False

        self._csv_path = csv_path
        ts_ms = df["timestamp_ms"].to_numpy(dtype=np.float64)
        timestamps = (ts_ms - ts_ms[0]) / 1000.0
        # Convert raw CH1 to mV by dividing by AMPLITUDE_DIVISOR (1760)
        ch1_data = df["channel_1"].to_numpy(dtype=np.float32) / AMPLITUDE_DIVISOR
        self._timestamps = timestamps
        self._ch1_data = ch1_data

        self._curve.setData(x=timestamps, y=ch1_data)
        x_end = float(timestamps[-1])
        self._plot.setXRange(0, min(10.0, x_end), padding=0)
        self._plot.enableAutoRange(axis="y")
        self._cursor.setValue(0)
        self._on_cursor_moved()  # initialize readout

        self._title_label.setText(f"Recording Review — {csv_path.name}")
        self.show()
        return True

    def clear_review(self) -> None:
        """Clear the review plot and hide the widget."""
        self._curve.setData(x=[], y=[])
        self._csv_path = None
        self._timestamps = None
        self._ch1_data = None
        self._cursor_readout.setText("t = -- s,  y = -- mV")
        self.hide()

    # ------------------------------------------------------------------
    # Zoom / Close slots
    # ------------------------------------------------------------------

    def _on_x_zoom_in(self) -> None:
        """Shrink visible X range by 10%, centered on cursor."""
        self._zoom_axis("x", zoom_in=True)

    def _on_x_zoom_out(self) -> None:
        """Expand visible X range by 10%, centered on cursor."""
        self._zoom_axis("x", zoom_in=False)

    def _on_y_zoom_in(self) -> None:
        """Shrink visible Y range by 10%, centered on current view center."""
        self._zoom_axis("y", zoom_in=True)

    def _on_y_zoom_out(self) -> None:
        """Expand visible Y range by 10%, centered on current view center."""
        self._zoom_axis("y", zoom_in=False)

    def _zoom_axis(self, axis: str, zoom_in: bool) -> None:
        """Zoom an axis by ±10%, centered on cursor (X) or view center (Y)."""
        vb = self._plot.getViewBox()
        x_range, y_range = vb.viewRange()  # type: ignore[misc]
        if axis == "x":
            lo = float(x_range[0])  # type: ignore[arg-type]
            hi = float(x_range[1])  # type: ignore[arg-type]
            center = float(self._cursor.value())  # pyright: ignore[reportArgumentType]
        else:
            lo = float(y_range[0])  # type: ignore[arg-type]
            hi = float(y_range[1])  # type: ignore[arg-type]
            center = (lo + hi) / 2.0

        span = hi - lo
        if zoom_in:
            new_span = span * (1.0 - ZOOM_FACTOR)
        else:
            new_span = span * (1.0 + ZOOM_FACTOR)

        # Minimum span guard
        if new_span < 0.1:
            return

        new_lo = center - new_span / 2.0
        new_hi = center + new_span / 2.0

        if axis == "x":
            self._plot.setXRange(new_lo, new_hi, padding=0)
        else:
            self._plot.setYRange(new_lo, new_hi, padding=0)

    def _on_close(self) -> None:
        """Hide the review panel."""
        self.hide()
        self.closed.emit()

    def _on_load_clicked(self) -> None:
        """Open file dialog to load any CSV file from the default save directory."""
        # Default to the CSV save directory; fall back to home if it doesn't exist
        default_dir = CSV_DEFAULT_DIR
        if not Path(default_dir).exists():
            default_dir = str(Path.home())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load ECG CSV",
            default_dir,
            "CSV files (*.csv);;All files (*.*)",
        )
        if file_path:
            self.load_csv(Path(file_path))

    def _on_cursor_moved(self) -> None:
        """Update the readout label with current cursor (t, y) values."""
        if self._timestamps is None or self._ch1_data is None or len(self._timestamps) == 0:
            self._cursor_readout.setText("t = -- s,  y = -- mV")
            return

        t = float(self._cursor.value())  # pyright: ignore[reportArgumentType]
        # Find nearest sample by time using binary search
        idx = int(np.searchsorted(self._timestamps, t))
        if idx >= len(self._timestamps):
            idx = len(self._timestamps) - 1
        elif idx > 0:
            # Pick the closer of idx-1 and idx
            if abs(self._timestamps[idx - 1] - t) < abs(self._timestamps[idx] - t):
                idx = idx - 1

        y = float(self._ch1_data[idx])
        self._cursor_readout.setText(f"t = {t:7.3f} s,  y = {y:+7.3f} mV")
