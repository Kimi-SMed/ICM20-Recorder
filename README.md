# ICM2 BLE ECG Recorder

A Windows desktop application for recording ECG data from ICM2 implantable cardiac monitors via BLE.

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10+
- Bluetooth adapter (Windows BLE via WinRT)

## Installation

```bash
# Clone/download the project
cd ICM2-CoDemo-Ultrasonic

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Dependencies installed: `bleak`, `cryptography`, `crcmod`, `PyQt5`, `pyqtgraph`, `pytest`, `pandas`

## Running

```bash
python main.py
```

The application will open. Follow these steps:

1. Click **Scan** to discover ICM devices
2. Select your device from the list
3. Click **Connect** (auto-performs handshake, ~5 seconds)
4. Click **Start Recording** to begin saving ECG to CSV
5. Click **Stop Recording** when done
6. CSV files are saved to `%USERPROFILE%\Documents\ICM_ECG\`

## Building the Executable

```bash
pip install pyinstaller
pyinstaller --noconfirm icm_recorder.spec
```

Output: `dist\icm_recorder.exe` — runs on clean Windows without Python installed.

## CSV Output Format

Each recording produces one file: `ecg_<MAC>_<YYYYMMDD_HHMMSS>.csv`

| Column | Description |
|--------|-------------|
| timestamp_ms | Unix timestamp in milliseconds |
| sample_index | Global sample counter |
| channel_1 | CH1 raw int16 value |
| channel_2 | CH2 raw int16 value |
| marker_id | Marker type ID (empty if no marker) |
| marker_label | Marker label string (e.g. "S", "VT-ON") |
| rr_ms | RR interval in milliseconds |
| amplitude_mv | R-wave amplitude in mV |

Sample rate: 250 Hz (4 ms per sample)

## Running Tests

```bash
pytest tests/ -v
```

Expected: 30+ tests, all pass.

## Project Structure

```
ICM2-CoDemo-Ultrasonic/
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── icm_recorder.spec        # PyInstaller build spec
├── icm/
│   ├── ble_client.py       # BLE scan/connect/notify
│   ├── config.py           # Constants and UUIDs
│   ├── crypto.py           # AES encryption for handshake
│   ├── ecg_parser.py       # ECG packet parser
│   ├── ecg_writer.py       # CSV streaming writer
│   └── handshake.py        # Challenge-response handshake
├── ui/
│   ├── async_bridge.py     # asyncio ↔ Qt bridge
│   ├── device_panel.py     # Scan list + connect buttons
│   ├── main_window.py      # Main application window
│   └── plot_widget.py      # Real-time ECG plot
└── tests/
    ├── test_crypto.py
    ├── test_ecg_parser.py
    ├── test_ecg_writer.py
    └── fixtures/
        └── sample_packets.py
```

## Notes

- Requires BLE connection to an ICM2 device for full operation
- Handshake is mandatory (even for ECG-only recording)
- ECG channel data is transmitted in plaintext after handshake
- Multiple recordings per session: stop then start creates a new CSV file
