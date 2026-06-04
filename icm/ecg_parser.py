"""ICM2 GEN2 ECG packet parser.

Parses 148-byte BLE notify payload from ECG_DATA characteristic.
Packet format: 74 int16 LE values.
  [0:32]   = Channel 1 (32 samples)
  [32:64]  = Channel 2 (32 samples)
  [64:68]  = 4 marker slots (low byte = position 0-31, high byte identifies marker type via & 0xFF00)
  [68:72]  = 4 RR intervals (ms)
  [73]     = R amplitude (divide by 1760 = mV)
Marker sentinel: marker_data == 0 means empty slot.
"""

import struct
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

PACKET_BYTES = 148  # 74 int16 * 2


# Marker ID -> label map (copied from ICM_STREAM_ECG_MARKER in icm_control.py reference)
ICM_STREAM_ECG_MARKER: dict = {
    0x0000: "None",
    0x0100: "S",
    0x0200: "T",
    0x0300: "AS",
    0x1100: "P-ON",
    0x1200: "P+",
    0x1300: "D-P",
    0x1400: "P-NS",
    0x1500: "P-",
    0x2100: "B-ON",
    0x2200: "B+",
    0x2300: "D-B",
    0x2400: "B-NS",
    0x2500: "B-",
    0x2600: "B-ReON",
    0x3100: "VT-ON",
    0x3200: "VT+",
    0x3300: "D-VT",
    0x3400: "VT-NS",
    0x3500: "VT-",
    0x3600: "VT-ReON",
    0x3700: "VTx",
    0x4100: "AT-ON",
    0x4200: "AT+",
    0x4300: "D-AT",
    0x4400: "AT-NS",
    0x4500: "AT-",
    0x4600: "AT-ReON",
    0x4700: "ATx",
    0x5100: "AF-ON",
    0x5200: "AF+",
    0x5300: "D-AF",
    0x5400: "AF-NS",
    0x5500: "AF-",
    0x5600: "AF-ReON",
    0x6100: "V-P",
    0x6200: "D-V",
    0x6300: "V-J",
    0x7100: "MGT+",
    0x7200: "MGT-",
    0x8100: "MP+",
    0x8200: "MP-",
}


@dataclass
class ParsedPacket:
    """Result of parsing one BLE ECG notify packet."""
    received_ms: int                          # system time when packet arrived (ms since epoch)
    ch1: List[int]                            # 32 int16 samples, channel 1
    ch2: List[int]                            # 32 int16 samples, channel 2
    markers: List[Tuple[int, int, str]]       # list of (position_in_packet, marker_id, marker_label)
    rr_intervals: List[int]                   # RR intervals in ms (up to 4)
    amplitude_mv: float                       # R-wave amplitude in mV


def parse_ecg_packet(data: bytes, received_ms: int = 0) -> Optional[ParsedPacket]:
    """Parse raw BLE notify bytes into ParsedPacket.

    Args:
        data: Raw bytes from ECG_DATA BLE characteristic
        received_ms: Timestamp when packet was received (ms since epoch)

    Returns:
        ParsedPacket if successful, None if packet is too short or malformed.
    """
    if len(data) < PACKET_BYTES:
        logging.warning(f"ECG packet too short: {len(data)} < {PACKET_BYTES}, skipping")
        return None

    try:
        ecg = struct.unpack("<74h", data[:PACKET_BYTES])
    except struct.error as e:
        logging.error(f"ECG packet unpack failed: {e}")
        return None

    ch1 = list(ecg[0:32])
    ch2 = list(ecg[32:64])

    # Parse marker slots [64:68]
    markers = []
    rr_intervals = []
    for idx, marker_data in enumerate(ecg[64:68]):
        if marker_data == 0:
            continue
        position = marker_data & 0x00FF          # position within packet (0-31)
        marker_id = marker_data & 0xFF00         # marker type key for lookup
        marker_label = ICM_STREAM_ECG_MARKER.get(marker_id, f"UNK_{marker_id:#06x}")
        markers.append((position, marker_id, marker_label))

        # RR interval for this marker slot
        rr_val = ecg[68 + idx]
        if rr_val > 0:
            rr_intervals.append(rr_val)

    # R-wave amplitude [73]
    amplitude_mv = ecg[73] / 1760.0 if len(ecg) > 73 else 0.0

    return ParsedPacket(
        received_ms=received_ms,
        ch1=ch1,
        ch2=ch2,
        markers=markers,
        rr_intervals=rr_intervals,
        amplitude_mv=amplitude_mv,
    )
