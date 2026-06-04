# Problems - icm-ecg-recorder

## 2026-06-04 Atlas Session Init
No unresolved blockers yet. Session starting.

## 2026-06-04 Hardware Debugging Session

### [RESOLVED] Permission auth failure → device disconnect at 1 min
- See issues.md for full root cause analysis
- Key insight: seq continuity between handshake and post-handshake commands is mandatory

### [OPEN] Real device UAT only partially complete
- Connected, waveform visible, permission holds >1 min ✓
- BPM display working ✓
- CSV recording: untested end-to-end on real hardware
- 14-min permission renewal: untested (requires 14+ min session)
- Marker display on real device: partially tested (ghost bug fixed, needs more observation)

### [OPEN] Log level is DEBUG in production build
- main.py currently has logging.DEBUG — verbose output in terminal
- Should revert to logging.INFO before packaging final .exe
- No functional impact, just noisy
