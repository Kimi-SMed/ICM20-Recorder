"""Real-time dual-channel ECG plot widget (PyQtGraph).

Sweep-line (monitor) mode:
  - Fixed 10-second circular buffer (numpy array, NaN-initialised)
  - Write pointer advances left→right, wraps at end back to 0
  - A vertical InfiniteLine marks the current write position
  - A NaN gap (ERASE_WIDTH samples) ahead of the cursor erases stale data,
    giving the classic cardiac-monitor "moving window" appearance
  - X axis shows time in seconds (0–10 s)
  - Two stacked plots: CH1 (green) and CH2 (yellow) on black background
  - Marker TextItems shown on CH1 at their sample position
"""

from typing import List

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from icm.config import ROLLING_WINDOW_PTS, SAMPLE_RATE_HZ
from icm.ecg_parser import ParsedPacket

# Samples erased ahead of the write cursor (≈ 0.15 s blank gap)
ERASE_WIDTH = max(1, int(SAMPLE_RATE_HZ * 0.15))


class ECGPlotWidget(QWidget):
    """Dual-channel ECG display in cardiac-monitor sweep mode.

    Use append_packet() only from Qt main thread (QTimer slot).
    Memory is bounded: two fixed numpy arrays of ROLLING_WINDOW_PTS floats.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Circular buffer — NaN means "no data yet / erased"
        self._buf_ch1 = np.full(ROLLING_WINDOW_PTS, np.nan, dtype=np.float32)
        self._buf_ch2 = np.full(ROLLING_WINDOW_PTS, np.nan, dtype=np.float32)

        # Write pointer: next sample goes here
        self._ptr: int = 0

        # Marker items: list of (sample_index, pg.TextItem)
        self._marker_items: List[tuple] = []

        # Precompute x axis (seconds, fixed for lifetime of widget)
        self._x_sec = np.arange(ROLLING_WINDOW_PTS, dtype=np.float32) / SAMPLE_RATE_HZ

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._graphics = pg.GraphicsLayoutWidget()
        self._graphics.setBackground((220, 220, 220))  # light grey
        layout.addWidget(self._graphics)

        # CH1 plot
        self._plot_ch1 = self._graphics.addPlot(row=0, col=0)
        self._plot_ch1.setLabel("left", "CH1")
        self._plot_ch1.setLabel("bottom", "Time", units="s")
        self._plot_ch1.showGrid(x=True, y=True, alpha=0.25)
        self._plot_ch1.setMouseEnabled(x=False, y=False)
        self._plot_ch1.hideButtons()
        self._plot_ch1.setXRange(0, ROLLING_WINDOW_PTS / SAMPLE_RATE_HZ, padding=0)
        self._curve_ch1 = self._plot_ch1.plot(
            pen=pg.mkPen((30, 100, 200), width=1), connect="finite"  # blue
        )

        # Sweep cursor line for CH1
        self._cursor_ch1 = pg.InfiniteLine(
            angle=90, pen=pg.mkPen((160, 160, 160), width=1, style=Qt.PenStyle.DashLine)
        )
        self._plot_ch1.addItem(self._cursor_ch1)

        # CH2 plot
        self._plot_ch2 = self._graphics.addPlot(row=1, col=0)
        self._plot_ch2.setLabel("left", "CH2")
        self._plot_ch2.setLabel("bottom", "Time", units="s")
        self._plot_ch2.showGrid(x=True, y=True, alpha=0.25)
        self._plot_ch2.setMouseEnabled(x=False, y=False)
        self._plot_ch2.hideButtons()
        self._plot_ch2.setXRange(0, ROLLING_WINDOW_PTS / SAMPLE_RATE_HZ, padding=0)
        self._curve_ch2 = self._plot_ch2.plot(
            pen=pg.mkPen((30, 100, 200), width=1), connect="finite"  # blue
        )

        # Sweep cursor line for CH2
        self._cursor_ch2 = pg.InfiniteLine(
            angle=90, pen=pg.mkPen((160, 160, 160), width=1, style=Qt.PenStyle.DashLine)
        )
        self._plot_ch2.addItem(self._cursor_ch2)

        # Link X axes
        self._plot_ch2.setXLink(self._plot_ch1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_packet(self, packet: ParsedPacket) -> None:
        """Write 32 samples into circular buffer and refresh display.

        Call only from Qt main thread (QTimer slot).
        """
        samples = len(packet.ch1)
        indices = np.arange(self._ptr, self._ptr + samples) % ROLLING_WINDOW_PTS

        # Erase region = new samples + blank gap ahead of new cursor
        new_ptr = int((self._ptr + samples) % ROLLING_WINDOW_PTS)
        erase_idx = np.arange(new_ptr, new_ptr + ERASE_WIDTH) % ROLLING_WINDOW_PTS
        overwrite_set = set(indices.tolist()) | set(erase_idx.tolist())

        # Remove any markers whose buf_idx falls in the overwrite region
        self._evict_markers(overwrite_set)

        self._buf_ch1[indices] = packet.ch1
        self._buf_ch2[indices] = packet.ch2
        self._ptr = new_ptr

        self._buf_ch1[erase_idx] = np.nan
        self._buf_ch2[erase_idx] = np.nan

        self._add_marker_items(packet, indices)
        self._refresh_curves()

    def clear(self) -> None:
        """Clear all data and markers from the plot."""
        self._buf_ch1[:] = np.nan
        self._buf_ch2[:] = np.nan
        self._ptr = 0
        for _idx, item in self._marker_items:
            self._plot_ch1.removeItem(item)
        self._marker_items.clear()
        self._curve_ch1.setData(x=[], y=[])
        self._curve_ch2.setData(x=[], y=[])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evict_markers(self, overwrite_set: set) -> None:
        """Remove markers whose buffer position is about to be overwritten."""
        surviving = []
        for buf_idx, item in self._marker_items:
            if buf_idx in overwrite_set:
                self._plot_ch1.removeItem(item)
            else:
                surviving.append((buf_idx, item))
        self._marker_items = surviving

    def _refresh_curves(self) -> None:
        cursor_sec = self._ptr / SAMPLE_RATE_HZ
        self._curve_ch1.setData(x=self._x_sec, y=self._buf_ch1)
        self._curve_ch2.setData(x=self._x_sec, y=self._buf_ch2)
        self._cursor_ch1.setValue(cursor_sec)
        self._cursor_ch2.setValue(cursor_sec)

    def _add_marker_items(self, packet: ParsedPacket, indices: np.ndarray) -> None:
        if not packet.markers:
            return

        for position, _marker_id, marker_label in packet.markers:
            if position >= len(indices):
                continue
            buf_idx = int(indices[position])
            x_pos = self._x_sec[buf_idx]
            y_val = float(self._buf_ch1[buf_idx])
            if np.isnan(y_val):
                continue
            item = pg.TextItem(
                text=marker_label,
                color=(255, 140, 0),
                anchor=(0.5, 1.0),
            )
            item.setPos(x_pos, y_val)
            self._plot_ch1.addItem(item)
            self._marker_items.append((buf_idx, item))
