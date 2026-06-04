"""Streaming CSV writer for ICM2 ECG recordings.

CSV format (8 columns, one row per sample):
  timestamp_ms,sample_index,channel_1,channel_2,marker_id,marker_label,rr_ms,amplitude_mv

  - timestamp_ms: packet_received_ms + (i * 4)  [4ms = 1/250Hz]
  - sample_index: global counter, monotonically increasing
  - channel_1, channel_2: int16 values
  - For non-marker samples: last 4 columns are empty strings
  - For marker samples: marker_id (int), marker_label (str), rr_ms (int), amplitude_mv (float, 2 decimal places)
  - File is flushed every 32 rows (one packet)
  - File path: {base_dir}/ecg_{mac}_{YYYYMMDD_HHMMSS}.csv
"""

import csv
import datetime
import logging
import os
from pathlib import Path
from typing import Optional

from icm.ecg_parser import ParsedPacket

logger = logging.getLogger(__name__)

CSV_HEADER = [
    "timestamp_ms",
    "sample_index",
    "channel_1",
    "channel_2",
    "marker_id",
    "marker_label",
    "rr_ms",
    "amplitude_mv",
]


class ECGCsvWriter:
    """Writes ECG data to CSV file in streaming fashion."""

    def __init__(self, base_dir: str, mac_address: str) -> None:
        """Create writer but do NOT open file yet. Call open() explicitly.

        Args:
            base_dir: Directory to save CSV (e.g. ~/Documents/ICM_ECG/)
            mac_address: BLE MAC address string (colons replaced with dashes in filename)
        """
        self._base_dir = Path(base_dir)
        self._mac_str = mac_address.replace(":", "-").upper()
        self._file = None
        self._writer = None
        self._sample_index: int = 0
        self._is_open: bool = False
        self._current_path: Optional[Path] = None

    def open(self) -> Path:
        """Open a new CSV file for writing. Creates base_dir if needed.

        Returns:
            Path to the newly opened CSV file.

        Raises:
            OSError: If directory cannot be created or file cannot be opened.
        """
        self._base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ecg_{self._mac_str}_{timestamp}.csv"
        self._current_path = self._base_dir / filename
        self._file = open(self._current_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(CSV_HEADER)
        self._sample_index = 0
        self._is_open = True
        logger.info("Opened CSV file: %s", self._current_path)
        return self._current_path

    def write_packet(self, packet: ParsedPacket) -> None:
        """Write all 32 samples from one ECG packet.

        For each sample i (0-31):
          timestamp_ms = packet.received_ms + i * 4

        Marker columns are written only on the sample at the marker's position.
        amplitude_mv is the packet-level R-wave amplitude, written on marker rows.
        rr_ms is paired positionally: markers[i] -> rr_intervals[i] (0 if missing).

        Flushes file after writing all rows.

        Args:
            packet: Parsed ECG packet from parse_ecg_packet()
        """
        if not self._is_open or self._writer is None:
            return

        # Build per-sample marker lookup: sample_position -> (marker_id, marker_label, rr_ms)
        # markers[i] is paired with rr_intervals[i] (positional, 0 if interval not present)
        marker_lookup: dict = {}
        for i, (position, marker_id, marker_label) in enumerate(packet.markers):
            rr_ms = packet.rr_intervals[i] if i < len(packet.rr_intervals) else 0
            marker_lookup[position] = (marker_id, marker_label, rr_ms)

        amp_mv = round(packet.amplitude_mv, 2)
        rows_to_write = []

        for i in range(len(packet.ch1)):
            ts = packet.received_ms + i * 4
            ch1 = packet.ch1[i]
            ch2 = packet.ch2[i]

            if i in marker_lookup:
                m_id, m_label, rr = marker_lookup[i]
                rows_to_write.append([ts, self._sample_index, ch1, ch2, m_id, m_label, rr, amp_mv])
            else:
                rows_to_write.append([ts, self._sample_index, ch1, ch2, "", "", "", ""])

            self._sample_index += 1

        try:
            self._writer.writerows(rows_to_write)
            if self._file:
                self._file.flush()
        except OSError as e:
            logger.error("CSV write failed (disk full?): %s", e)

    def close(self) -> None:
        """Flush and close the CSV file. Idempotent — safe to call multiple times."""
        if not self._is_open:
            return
        try:
            if self._file:
                self._file.flush()
                self._file.close()
        except OSError as e:
            logger.error("CSV close error: %s", e)
        finally:
            self._file = None
            self._writer = None
            self._is_open = False
            logger.info("Closed CSV file: %s", self._current_path)

    @property
    def is_open(self) -> bool:
        """True if a CSV file is currently open for writing."""
        return self._is_open

    @property
    def sample_count(self) -> int:
        """Total number of samples written since open()."""
        return self._sample_index

    @property
    def current_path(self) -> Optional[Path]:
        """Path to the currently open (or last closed) CSV file."""
        return self._current_path
