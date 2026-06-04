"""Real-time dual-channel ECG plot widget (PyQtGraph).

Rolling 20-second window (5000 samples/channel) using deque(maxlen=5000).
Two stacked plots: CH1 (green) and CH2 (yellow) on black background.
Marker labels shown as TextItem overlays at marker positions on CH1.
No zoom/pan/export/FFT - view is fixed and auto-scrolling.
"""

from collections import deque
from typing import List

import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from icm.config import ROLLING_WINDOW_PTS
from icm.ecg_parser import ParsedPacket


class ECGPlotWidget(QWidget):
    """Dual-channel ECG display with rolling window and marker overlay.

    Use append_packet() only from Qt main thread (QTimer slot).
    Memory is bounded by deque(maxlen=5000) per channel.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ch1_data: deque = deque(maxlen=ROLLING_WINDOW_PTS)
        self._ch2_data: deque = deque(maxlen=ROLLING_WINDOW_PTS)
        self._marker_items: List[pg.TextItem] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._graphics = pg.GraphicsLayoutWidget()
        self._graphics.setBackground("k")
        layout.addWidget(self._graphics)

        # CH1 plot
        self._plot_ch1: pg.PlotItem = self._graphics.addPlot(row=0, col=0)
        self._plot_ch1.setLabel("left", "CH1")
        self._plot_ch1.showGrid(x=False, y=True, alpha=0.3)
        self._plot_ch1.setMouseEnabled(x=False, y=False)
        self._plot_ch1.hideButtons()
        self._curve_ch1 = self._plot_ch1.plot(pen=pg.mkPen("g", width=1))

        # CH2 plot
        self._plot_ch2: pg.PlotItem = self._graphics.addPlot(row=1, col=0)
        self._plot_ch2.setLabel("left", "CH2")
        self._plot_ch2.showGrid(x=False, y=True, alpha=0.3)
        self._plot_ch2.setMouseEnabled(x=False, y=False)
        self._plot_ch2.hideButtons()
        self._curve_ch2 = self._plot_ch2.plot(pen=pg.mkPen("y", width=1))

        # Link X axes for visual alignment
        self._plot_ch2.setXLink(self._plot_ch1)

    def append_packet(self, packet: ParsedPacket) -> None:
        """Append 32 samples from packet to both channels and refresh plot.

        Call only from Qt main thread (QTimer slot).
        """
        self._ch1_data.extend(packet.ch1)
        self._ch2_data.extend(packet.ch2)
        self._add_marker_items(packet)
        self._refresh_curves()

    def _refresh_curves(self) -> None:
        """Redraw both channel curves."""
        ch1 = list(self._ch1_data)
        ch2 = list(self._ch2_data)
        x = list(range(len(ch1)))
        self._curve_ch1.setData(x=x, y=ch1)
        self._curve_ch2.setData(x=x, y=ch2)

    def _add_marker_items(self, packet: ParsedPacket) -> None:
        """Add TextItem labels for markers in this packet."""
        if not packet.markers:
            return

        buf_len = len(self._ch1_data)
        packet_start = max(0, buf_len - len(packet.ch1))
        ch1_list = list(self._ch1_data)

        for position, _marker_id, marker_label in packet.markers:
            idx = packet_start + position
            if idx >= len(ch1_list):
                continue
            y_val = ch1_list[idx]
            item = pg.TextItem(
                text=marker_label,
                color=(255, 140, 0),
                anchor=(0.5, 1.0),
            )
            item.setPos(idx, y_val)
            self._plot_ch1.addItem(item)
            self._marker_items.append(item)

        # Limit stored markers to 20 to prevent unbounded accumulation
        if len(self._marker_items) > 20:
            evict = self._marker_items[:-20]
            for old_item in evict:
                self._plot_ch1.removeItem(old_item)
            self._marker_items = self._marker_items[-20:]

    def clear(self) -> None:
        """Clear all data and markers from the plot."""
        self._ch1_data.clear()
        self._ch2_data.clear()
        for item in self._marker_items:
            self._plot_ch1.removeItem(item)
        self._marker_items.clear()
        self._curve_ch1.setData(x=[], y=[])
        self._curve_ch2.setData(x=[], y=[])
