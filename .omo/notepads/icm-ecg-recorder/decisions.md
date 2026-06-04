# Decisions - icm-ecg-recorder

## 2026-06-04 Atlas Session Init

### Architecture Decisions
- Platform: Windows PC, Python 3.10+
- GUI: PyQt5 + PyQtGraph
- BLE: bleak (WinRT backend on Windows)
- Encryption: cryptography package (NOT pycryptodome)
- Packaging: PyInstaller single .exe

### Threading Decision
- asyncio.new_event_loop() + threading.Thread(target=loop.run_forever)
- NO qasync, NO asyncio.run() in Qt slots
- queue.Queue (thread-safe) for asyncio->Qt data bridge
- QTimer(50ms) in Qt thread to drain queue

### CSV Decision
- One file per recording session
- ecg_<MAC>_<YYYYMMDD_HHMMSS>.csv naming
- 8 fixed columns, streaming write, flush every packet
- Path: ~/Documents/ICM_ECG/ (UAC-safe)

### No Command Channel
- After handshake: zero commands sent post-handshake
- ECG channel is plaintext -- no decryption needed after handshake

### Plot Buffer
- deque(maxlen=5000) per channel (20s at 250Hz)

### Test Strategy
- pytest unit tests for crypto, parser, writer
- No real hardware tests in plan scope
- Agent QA for UI + CSV + packaging
