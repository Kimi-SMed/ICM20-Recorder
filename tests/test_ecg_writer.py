"""Unit tests for ICM2 ECG CSV writer."""

import csv
import os
import tempfile
import pytest
from icm.ecg_writer import ECGCsvWriter
from icm.ecg_parser import parse_ecg_packet
from tests.fixtures.sample_packets import (
    make_packet_with_marker, make_empty_packet,
    make_packet_with_ch_data
)


class TestECGCsvWriter:
    """Test ECG CSV writing functionality."""

    def test_csv_header_and_row_count(self):
        """Write empty packet — should have header + 32 data rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            pkt = parse_ecg_packet(make_empty_packet(), received_ms=0)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # First row is header
            assert rows[0][0] == 'timestamp_ms'
            assert len(rows[0]) == 8
            
            # Total: 1 header + 32 data rows
            assert len(rows) == 33

    def test_csv_marker_row(self):
        """Write packet with marker at position 0 — marker_id should appear in row 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            pkt_bytes = make_packet_with_marker(position=0, marker_id=0x0100, rr_ms=800)
            pkt = parse_ecg_packet(pkt_bytes, received_ms=1000)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # Row 1 (index 1) is first data row, position 0 has marker
            marker_row = rows[1]
            assert marker_row[4] == '256'  # 0x0100 = 256
            assert marker_row[5] == 'S'
            assert marker_row[6] == '800'  # rr_ms

    def test_csv_non_marker_rows_empty_marker_fields(self):
        """Write empty packet — non-marker rows should have empty marker fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            pkt = parse_ecg_packet(make_empty_packet(), received_ms=0)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # Row 1 has no marker
            data_row = rows[1]
            assert data_row[4] == ''  # marker_id empty
            assert data_row[5] == ''  # marker_label empty
            assert data_row[6] == ''  # rr_ms empty
            assert data_row[7] == ''  # amplitude_mv empty

    def test_csv_close_idempotent(self):
        """Calling close() multiple times should not raise exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            w.open()
            w.close()
            w.close()  # Should not raise
            w.close()  # Should not raise

    def test_csv_timestamps_monotonic(self):
        """Timestamps should be monotonically increasing by 4ms per sample."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            pkt = parse_ecg_packet(make_empty_packet(), received_ms=0)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            timestamps = [int(r[0]) for r in rows[1:]]
            
            # Should be 0, 4, 8, 12, ..., 124
            expected = list(range(0, 128, 4))
            assert timestamps == expected

    def test_csv_sample_index_increments(self):
        """Sample index should increment globally across packets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            # Write first packet (32 samples)
            pkt1 = parse_ecg_packet(make_empty_packet(), received_ms=0)
            w.write_packet(pkt1)
            
            # Write second packet (32 samples)
            pkt2 = parse_ecg_packet(make_empty_packet(), received_ms=128)
            w.write_packet(pkt2)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # Check sample indices
            sample_indices = [int(r[1]) for r in rows[1:]]
            assert sample_indices == list(range(64))

    def test_csv_channel_values_preserved(self):
        """Channel values from packet should be preserved in CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            pkt_bytes = make_packet_with_ch_data(ch1_val=100, ch2_val=200)
            pkt = parse_ecg_packet(pkt_bytes, received_ms=0)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # All data rows should have ch1=100, ch2=200
            for row in rows[1:]:
                assert int(row[2]) == 100  # channel_1
                assert int(row[3]) == 200  # channel_2

    def test_csv_marker_label(self):
        """Parse marker should have correct label in CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            # P-ON marker (0x1100)
            pkt_bytes = make_packet_with_marker(position=10, marker_id=0x1100, rr_ms=750)
            pkt = parse_ecg_packet(pkt_bytes, received_ms=0)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # Position 10 = row 11 (header at 0, data starts at 1)
            marker_row = rows[11]
            assert marker_row[5] == 'P-ON'

    def test_csv_amplitude_on_marker_row(self):
        """Amplitude should appear on marker rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ECGCsvWriter(tmpdir, "AA:BB:CC:DD:EE:FF")
            path = w.open()
            
            pkt_bytes = make_packet_with_marker(
                position=0, marker_id=0x0100, rr_ms=800, amplitude_raw=880
            )
            pkt = parse_ecg_packet(pkt_bytes, received_ms=0)
            w.write_packet(pkt)
            w.close()
            
            with open(path) as f:
                rows = list(csv.reader(f))
            
            # First data row (position 0)
            marker_row = rows[1]
            # 880 / 1760 = 0.5 mV
            assert float(marker_row[7]) == 0.5
