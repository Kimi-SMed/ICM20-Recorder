"""Synthetic BLE notify payload fixtures for ICM2 ECG unit tests.

All packets are 148 bytes = 74 int16 LE values:
  [0:32]   int16 = CH1 (32 samples)
  [32:64]  int16 = CH2 (32 samples)
  [64:68]  int16 = 4 marker slots (low byte = position, high byte = marker type key >> 8)
  [68:72]  int16 = 4 RR intervals (ms)
  [73]     int16 = R amplitude
"""

import struct


def _pack_int16_le(values: list) -> bytes:
    """Pack a list of int16 values as little-endian bytes."""
    return struct.pack(f"<{len(values)}h", *values)


def make_empty_packet() -> bytes:
    """148-byte packet with all zeros — no markers, no data signal."""
    return bytes(148)


def make_packet_with_ch_data(ch1_val: int = 100, ch2_val: int = 200) -> bytes:
    """Packet with constant channel values, no markers.
    
    Args:
        ch1_val: int16 value for all 32 CH1 samples
        ch2_val: int16 value for all 32 CH2 samples
    """
    ch1 = [ch1_val] * 32
    ch2 = [ch2_val] * 32
    markers = [0, 0, 0, 0]      # no markers
    rr = [0, 0, 0, 0]           # no RR
    amplitude = 1760             # 1.0 mV (1760 / 1760 = 1.0)
    tail = 0                     # padding to reach index 73

    values = ch1 + ch2 + markers + rr + [tail] + [amplitude]
    # Total so far: 32+32+4+4+1+1 = 74 int16s = 148 bytes
    return _pack_int16_le(values)


def make_packet_with_marker(
    position: int = 5,
    marker_id: int = 0x0100,   # S marker
    rr_ms: int = 800,
    amplitude_raw: int = 1760, # 1.0 mV
) -> bytes:
    """Packet with one marker in slot 0.
    
    Args:
        position: sample position within packet (0-31), stored in low byte
        marker_id: marker type key (e.g. 0x0100 = 'S'), stored in high byte
        rr_ms: RR interval in ms
        amplitude_raw: R amplitude raw value (divide by 1760 for mV)
    """
    ch1 = [500] * 32
    ch2 = [300] * 32
    
    # Marker slot 0: low byte = position, high byte = marker_id >> 8
    marker_slot_0 = (position & 0xFF) | (marker_id & 0xFF00)
    markers = [marker_slot_0, 0, 0, 0]
    rr = [rr_ms, 0, 0, 0]
    tail = 0     # index 72
    amplitude = amplitude_raw  # index 73
    
    values = ch1 + ch2 + markers + rr + [tail] + [amplitude]
    return _pack_int16_le(values)


def make_short_packet(length: int = 10) -> bytes:
    """Packet shorter than 148 bytes — should be rejected by parser."""
    return bytes(length)


def make_packet_with_multiple_markers() -> bytes:
    """Packet with 3 markers of different types in slots 0, 1, 2."""
    ch1 = [1000] * 32
    ch2 = [-500] * 32
    
    # Slot 0: S marker (0x0100) at position 0
    # Slot 1: P-ON marker (0x1100) at position 16
    # Slot 2: VT-ON marker (0x3100) at position 31
    # Slot 3: empty
    m0 = (0 & 0xFF) | 0x0100
    m1 = (16 & 0xFF) | 0x1100
    m2 = (31 & 0xFF) | 0x3100
    markers = [m0, m1, m2, 0]
    rr = [800, 750, 820, 0]
    tail = 0
    amplitude = 880  # 0.5 mV
    
    values = ch1 + ch2 + markers + rr + [tail] + [amplitude]
    return _pack_int16_le(values)
