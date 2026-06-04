# ICM2 BLE ECG Recorder - Windows Desktop App

## TL;DR

> **Quick Summary**: Build a Windows desktop Python GUI (PyQt5 + PyQtGraph) that connects to an ICM2 medical implant via BLE, performs encrypted handshake, displays real-time dual-channel ECG with markers, and saves to CSV. Package as single .exe via PyInstaller.
> 
> **Deliverables**:
> - Working PyQt5 GUI application with BLE scan/connect/record workflow
> - Real-time 250Hz dual-channel ECG plot with marker overlay
> - CSV export (one row per sample, 8 columns)
> - PyInstaller .exe distributable
> - pytest unit tests for crypto/parser/writer
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 3 → Task 5 → Task 7 → Task 9 → Task 10 → F1-F4

---

## Context

### Original Request
User wanted an Android tablet Python script for BLE ICM communication + ECG CSV saving. After research confirmed bleak doesn't work in Termux (no BlueZ on Android), user pivoted to Windows PC desktop app.

### Interview Summary
**Key Discussions**:
- Platform: Windows PC (dropped Android/Termux)
- Protocol: GEN2 (ICM2), NOT GEN1 — dual-channel ECG with markers
- GUI: PyQt5 + PyQtGraph (rolling 20s window)
- Packaging: PyInstaller single .exe
- Code reuse: Copy+trim from GEN2 reference (`ICM-GEN2-PC-FWIT/ATSPythonBackend/`)
- Recording flow: Multi-stage (scan → connect → handshake → start/stop recording)

**Research Findings**:
- bleak works on Windows via WinRT backend (no BlueZ needed)
- GEN2 ECG payload = 74 int16 (dual-ch + markers + RR + amplitude)
- Handshake is byte-identical between GEN1/GEN2
- `command_encryption.py` uses `cryptography` package (NOT pycryptodome)

### Metis Review
**Identified Gaps** (addressed):
- Threading/async bridge pattern mandated (asyncio thread + queue.Queue + QTimer 50ms)
- Memory growth protection (deque maxlen=5000)
- closeEvent override for CSV integrity
- PyInstaller --collect-all for bleak/winrt/PyQt5/pyqtgraph/cryptography
- CSV save path must avoid UAC-protected directories
- Marker sentinel value confirmed = 0

---

## Work Objectives

### Core Objective
Build a distributable Windows desktop tool that connects to ICM2 via BLE, performs encrypted handshake, captures and displays real-time dual-channel ECG with markers, and saves recordings to CSV.

### Concrete Deliverables
- `main.py` + `icm/` package + `ui/` package + `tests/` directory
- Working GUI: scan → connect → handshake → record → stop → save CSV
- `icm_recorder.spec` for PyInstaller
- `dist/icm_recorder.exe` tested on clean Windows

### Definition of Done
- [ ] `pytest tests/` → all pass (≥6 tests covering crypto, parser, writer)
- [ ] Application launches, displays main window with all panels
- [ ] PyInstaller build succeeds: `pyinstaller icm_recorder.spec` → exit 0
- [ ] `.exe` launches on target machine without Python installed

### Must Have
- BLE scan showing ICM devices by name + RSSI
- Challenge-response handshake (5-step, 20s timeout)
- Dual-channel ECG real-time plot (20s rolling window)
- Marker overlay on plot (text labels from stream_marker_map)
- Heart rate + amplitude display
- CSV export: 8 columns, one row per sample, streaming write
- Multi-recording support (start/stop creates new file each time)
- Graceful error handling (adapter missing, handshake fail, disconnect, disk full)
- closeEvent protection (flush CSV before exit)
- PyInstaller .exe packaging

### Must NOT Have (Guardrails)
- ❌ USB CDC / DMM / power supply code
- ❌ Command channel sending (post-handshake zero commands)
- ❌ Modification of reference directory files
- ❌ GEN1 compatibility
- ❌ Cloud/REST/OTA/remote features
- ❌ Configuration persistence (INI/JSON) beyond runtime state
- ❌ Plot features: zoom/pan/export/FFT/spectrogram
- ❌ CSV metadata header block
- ❌ `pycryptodome` (use `cryptography`)
- ❌ `qasync` library (use threading + queue approach)
- ❌ Unbounded plot buffer (must be fixed-size deque)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (creating from scratch)
- **Automated tests**: YES (tests-after: write module → write tests)
- **Framework**: pytest
- **Real hardware**: OUT OF SCOPE (UAT by user)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **UI verification**: Launch app → take screenshot of window
- **Module verification**: Run pytest → capture stdout
- **Packaging**: Build .exe → check file exists + size
- **CSV verification**: Run writer with synthetic data → validate output with pandas

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - all independent, start immediately):
├── 1. Project scaffolding + requirements.txt + config constants [quick]
├── 2. icm/crypto.py - copy command_encryption.py + adapt [quick]
├── 3. icm/ecg_parser.py - ECG packet parser + marker map [quick]
├── 4. ui/async_bridge.py - asyncio thread + queue + QTimer bridge [quick]
└── 5. tests/ scaffolding + fixtures (synthetic packets) [quick]

Wave 2 (Core modules - depend on Wave 1):
├── 6. icm/handshake.py - SecretHandshake state machine (depends: 2) [unspecified-high]
├── 7. icm/ecg_writer.py - CSV streaming writer (depends: 3) [unspecified-high]
├── 8. icm/ble_client.py - BLE scan/connect/notify (depends: 2, 4, 6) [deep]
├── 9. ui/plot_widget.py - PyQtGraph dual-ch + markers (depends: 3, 4) [visual-engineering]
└── 10. Unit tests for crypto + parser + writer (depends: 2, 3, 7, 5) [quick]

Wave 3 (Integration + Packaging):
├── 11. ui/device_panel.py - scan list + connect buttons (depends: 8) [visual-engineering]
├── 12. ui/main_window.py - layout + closeEvent + status (depends: 9, 11, 7) [deep]
├── 13. main.py - entry point wiring all together (depends: 12) [quick]
├── 14. PyInstaller .spec + build (depends: 13) [unspecified-high]
└── 15. README.md - install/run/build instructions (depends: 14) [writing]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1. Plan compliance audit (oracle)
├── F2. Code quality review (unspecified-high)
├── F3. Real manual QA (unspecified-high)
└── F4. Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 6,7,8,9,11,12,13,14 | 1 |
| 2 | - | 6, 8, 10 | 1 |
| 3 | - | 7, 9, 10 | 1 |
| 4 | - | 8, 9, 11, 12 | 1 |
| 5 | - | 10 | 1 |
| 6 | 2 | 8 | 2 |
| 7 | 3 | 10, 12 | 2 |
| 8 | 2, 4, 6 | 11, 12 | 2 |
| 9 | 3, 4 | 12 | 2 |
| 10 | 2, 3, 7, 5 | - | 2 |
| 11 | 8 | 12 | 3 |
| 12 | 9, 11, 7 | 13 | 3 |
| 13 | 12 | 14 | 3 |
| 14 | 13 | 15 | 3 |
| 15 | 14 | - | 3 |
| F1-F4 | ALL | - | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **5 tasks** - T1-T5 → `quick`
- **Wave 2**: **5 tasks** - T6 → `unspecified-high`, T7 → `unspecified-high`, T8 → `deep`, T9 → `visual-engineering`, T10 → `quick`
- **Wave 3**: **5 tasks** - T11 → `visual-engineering`, T12 → `deep`, T13 → `quick`, T14 → `unspecified-high`, T15 → `writing`
- **FINAL**: **4 tasks** - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Project scaffolding + requirements.txt + config constants

  **What to do**:
  - Create directory structure: `icm/`, `ui/`, `tests/`, `tests/fixtures/`
  - Create empty `__init__.py` in each package
  - Write `requirements.txt`: `bleak>=0.21`, `cryptography>=41.0`, `crcmod>=1.7`, `PyQt5>=5.15`, `pyqtgraph>=0.13`, `pytest>=7.4`, `pandas>=2.0` (for tests only)
  - Write `icm/config.py`: BLE UUIDs, sample rate (250), packet size (148), handshake timeout (20s), rolling window (5000 pts), CSV default path `os.path.expanduser("~/Documents/ICM_ECG/")`, MAC scan name filter "ICM"
  - Create `.gitignore` with: `dist/`, `build/`, `__pycache__/`, `*.spec` (later un-ignore icm_recorder.spec), `.pytest_cache/`

  **Must NOT do**:
  - Don't install packages (just write requirements.txt)
  - Don't add `pycryptodome` (use `cryptography`)
  - Don't add config persistence (no INI/JSON files)

  **Recommended Agent Profile**:
  - **Category**: `quick` — Trivial scaffolding, no complex logic
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5)
  - **Blocks**: 6, 7, 8, 9, 11, 12, 13, 14
  - **Blocked By**: None

  **References**:
  - Draft: `.omo/drafts/android-icm-ecg-recorder.md` section "Architecture (FINAL)"
  - GEN2 reference: `D:\Singular_Medical\ICM_GEN2\Dvlp\ICM-GEN2-PC-FWIT\ATSPythonBackend\icm_control.py:20-23` for UUID values
  - **WHY**: Foundation for all other tasks. Constants centralized in config.py prevent magic numbers across modules.

  **Acceptance Criteria**:
  - [ ] Files exist: `requirements.txt`, `icm/__init__.py`, `icm/config.py`, `ui/__init__.py`, `tests/__init__.py`, `.gitignore`
  - [ ] `python -c "from icm import config; print(config.UUID_ECG_DATA, config.SAMPLE_RATE_HZ)"` → prints `5ac73503-3787-4203-856a-38199110db09 250`
  - [ ] `requirements.txt` contains `cryptography` and NOT `pycryptodome`

  **QA Scenarios**:
  ```
  Scenario: Verify project structure created correctly
    Tool: Bash
    Preconditions: Empty target directory
    Steps:
      1. ls icm/ ui/ tests/ tests/fixtures/
      2. cat requirements.txt
      3. python -c "from icm import config; assert config.SAMPLE_RATE_HZ == 250; assert 'cryptography' in open('requirements.txt').read(); assert 'pycryptodome' not in open('requirements.txt').read()"
    Expected Result: All directories exist, all files exist, config imports work, requirements.txt has cryptography (not pycryptodome)
    Failure Indicators: ImportError on config, missing directories, wrong package name in requirements
    Evidence: .omo/evidence/task-1-structure.txt (output of tree command)
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-1-structure.txt` (directory tree)

  **Commit**: NO (groups with Wave 1)

- [x] 2. icm/crypto.py - copy command_encryption.py and adapt

  **What to do**:
  - Read `D:\Singular_Medical\ICM_GEN2\Dvlp\ICM-GEN2-PC-FWIT\ATSPythonBackend\command_encryption.py` (140 lines, 5514 bytes)
  - Copy entire content to `icm/crypto.py`
  - Verify imports work without modification: `from cryptography.hazmat.backends import default_backend`, `from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes`, `import crcmod`
  - Add module docstring at top: `"""AES-128 CBC/ECB encryption + CRC16 + CryptionMessage CTR mode for ICM2 BLE handshake. Copied byte-identical from ICM-GEN2-PC-FWIT/ATSPythonBackend/command_encryption.py."""`
  - DO NOT refactor or "improve" - the protocol depends on exact bit-for-bit behavior

  **Must NOT do**:
  - Don't change function signatures
  - Don't replace `cryptography` with `pycryptodome`
  - Don't optimize the XOR loops in `decryptHelper`/`encryptHelper`
  - Don't change the IV (it's intentionally all zeros, matches device firmware)

  **Recommended Agent Profile**:
  - **Category**: `quick` — Pure copy, no logic
  - **Skills**: none

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 6, 8, 10
  - **Blocked By**: None

  **References**:
  - Source: `D:\Singular_Medical\ICM_GEN2\Dvlp\ICM-GEN2-PC-FWIT\ATSPythonBackend\command_encryption.py` (entire file, 140 lines)
  - **WHY**: Bit-identical copy preserves protocol compatibility. Any modification risks breaking handshake.

  **Acceptance Criteria**:
  - [ ] `icm/crypto.py` exists, line count ≈ 142 (140 + 2 docstring lines)
  - [ ] `python -c "from icm.crypto import encrypt_CBC, decrypt_CBC, CryptionMessage, append_crc16"` succeeds
  - [ ] Round-trip test: `encrypt_CBC` then `decrypt_CBC` returns input unchanged

  **QA Scenarios**:
  ```
  Scenario: Verify crypto round-trip works
    Tool: Bash
    Preconditions: Task 2 done, cryptography pip-installed in venv
    Steps:
      1. pip install cryptography crcmod
      2. python -c "from icm.crypto import encrypt_CBC, decrypt_CBC; key=bytes(16); plain=b'1234567891234567'; ct=encrypt_CBC(bytearray(key), bytearray(plain)); pt=decrypt_CBC(bytearray(key), ct); assert pt==bytearray(plain), f'roundtrip failed: {pt!r}'"
    Expected Result: Exit 0, no assertion error
    Failure Indicators: ImportError, AssertionError on roundtrip, cryptography not installed
    Evidence: .omo/evidence/task-2-crypto-roundtrip.txt
  ```

  **Evidence to Capture**:
  - [ ] `.omo/evidence/task-2-crypto-roundtrip.txt`

  **Commit**: NO (groups with Wave 1)

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run linter + `pytest tests/`. Review all files for: `as any`/type hacks, empty excepts, print in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify `cryptography` (not pycryptodome) is used.
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Launch `python main.py`. Verify window opens. Click Scan (expect "no devices" graceful handling since no ICM hardware). Verify CSV writer by calling it directly with synthetic data and validating output. Build .exe and verify it launches. Save evidence.
  Output: `Scenarios [N/N pass] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual code. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Flag unaccounted files.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(scaffold): project structure, crypto, parser, async bridge`
- **Wave 2**: `feat(core): handshake, csv-writer, ble-client, plot-widget, tests`
- **Wave 3**: `feat(ui): device-panel, main-window, entry-point, pyinstaller, readme`

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v                    # Expected: 6+ tests PASS
python main.py                      # Expected: window opens, no crash
pyinstaller icm_recorder.spec       # Expected: exit 0, dist/icm_recorder.exe exists
dist\icm_recorder.exe               # Expected: launches on clean Windows
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] .exe builds and launches
- [ ] CSV output validates with pandas
