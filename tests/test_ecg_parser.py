"""Unit tests for ICM2 ECG packet parser."""

import pytest
from icm.ecg_parser import parse_ecg_packet, ParsedPacket, ICM_STREAM_ECG_MARKER
from tests.fixtures.sample_packets import (
    make_empty_packet, make_short_packet,
    make_packet_with_marker, make_packet_with_ch_data,
    make_packet_with_multiple_markers
)


class TestParseECGPacket:
    """Test ECG packet parsing functionality."""

    def test_parse_empty_packet(self):
        """Parse 148-byte all-zeros packet — should return ParsedPacket with no markers."""
        pkt = parse_ecg_packet(make_empty_packet())
        
        assert pkt is not None
        assert len(pkt.ch1) == 32
        assert len(pkt.ch2) == 32
        assert pkt.markers == []
        assert pkt.rr_intervals == []
        assert pkt.amplitude_mv == 0.0
        assert pkt.received_ms == 0

    def test_short_packet_returns_none(self):
        """Packet shorter than 148 bytes should return None."""
        pkt = parse_ecg_packet(make_short_packet(10))
        assert pkt is None

    def test_parse_packet_with_marker(self):
        """Parse packet with one marker — should extract position, marker_id, label."""
        pkt_bytes = make_packet_with_marker(position=5, marker_id=0x0100, rr_ms=800)
        pkt = parse_ecg_packet(pkt_bytes)
        
        assert pkt is not None
        assert len(pkt.markers) == 1
        
        position, marker_id, label = pkt.markers[0]
        assert position == 5
        assert marker_id == 0x0100
        assert label == 'S'
        assert 800 in pkt.rr_intervals
        assert pkt.amplitude_mv == 1.0  # 1760 / 1760

    def test_parse_packet_channel_data(self):
        """Parse packet with constant channel values — should preserve values."""
        pkt_bytes = make_packet_with_ch_data(ch1_val=100, ch2_val=200)
        pkt = parse_ecg_packet(pkt_bytes)
        
        assert pkt is not None
        assert all(v == 100 for v in pkt.ch1)
        assert all(v == 200 for v in pkt.ch2)

    def test_parse_packet_with_received_ms(self):
        """Parse packet with received_ms timestamp — should be set in ParsedPacket."""
        pkt = parse_ecg_packet(make_empty_packet(), received_ms=12345)
        
        assert pkt is not None
        assert pkt.received_ms == 12345

    def test_parse_packet_amplitude_calculation(self):
        """Parse packet with known amplitude raw value — verify conversion."""
        pkt_bytes = make_packet_with_ch_data(ch1_val=0, ch2_val=0)
        pkt = parse_ecg_packet(pkt_bytes)
        
        # Default amplitude in fixture is 1760, so 1760 / 1760 = 1.0
        assert pkt is not None
        assert abs(pkt.amplitude_mv - 1.0) < 0.01

    def test_parse_multiple_markers(self):
        """Parse packet with 3 markers of different types."""
        pkt_bytes = make_packet_with_multiple_markers()
        pkt = parse_ecg_packet(pkt_bytes)
        
        assert pkt is not None
        assert len(pkt.markers) == 3
        assert len(pkt.rr_intervals) == 3
        
        # Check marker types and positions
        m0_pos, m0_id, m0_label = pkt.markers[0]
        m1_pos, m1_id, m1_label = pkt.markers[1]
        m2_pos, m2_id, m2_label = pkt.markers[2]
        
        assert m0_pos == 0 and m0_id == 0x0100 and m0_label == 'S'
        assert m1_pos == 16 and m1_id == 0x1100 and m1_label == 'P-ON'
        assert m2_pos == 31 and m2_id == 0x3100 and m2_label == 'VT-ON'
        
        assert pkt.rr_intervals == [800, 750, 820]

    def test_parse_negative_channel_values(self):
        """Parse packet with negative int16 channel values."""
        pkt_bytes = make_packet_with_ch_data(ch1_val=-100, ch2_val=-500)
        pkt = parse_ecg_packet(pkt_bytes)
        
        assert pkt is not None
        assert all(v == -100 for v in pkt.ch1)
        assert all(v == -500 for v in pkt.ch2)

    def test_parse_max_channel_values(self):
        """Parse packet with maximum int16 values."""
        pkt_bytes = make_packet_with_ch_data(ch1_val=32767, ch2_val=32767)
        pkt = parse_ecg_packet(pkt_bytes)
        
        assert pkt is not None
        assert all(v == 32767 for v in pkt.ch1)
        assert all(v == 32767 for v in pkt.ch2)
