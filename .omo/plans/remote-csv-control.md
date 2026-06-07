# Remote CSV Recording Control

## TL;DR

> **Quick Summary**: 在现有 PyQt5 BLE ECG 记录应用中嵌入 TCP Socket 服务端，允许局域网内另一台电脑通过简单 Python 脚本远程控制 CSV 录制的开始/停止，同时保留 GUI 按钮功能不变。
> 
> **Deliverables**:
> - `icm/remote_server.py` — TCP 服务端模块（threading + pyqtSignal）
> - `icm_remote.py` — 提供给对方的极简客户端脚本
> - `ui/main_window.py` 修改 — 集成远程服务器 + 状态显示
> - `ui/device_panel.py` 修改 — 左面板增加远程客户端连接状态标签
> 
> **Estimated Effort**: Short (2-3 hours implementation)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 3 → Task 4 → F1-F4

---

## Context

### Original Request
在不改动现有功能的前提下，增加远程控制 CSV 记录的能力。通过另一台电脑发送自定义指令来开始/停止录制，同时 GUI 按钮保留，并且远程触发时 GUI 同步显示状态。

### Interview Summary
**Key Discussions**:
- 通信方式: TCP Socket，简单文本指令，无需复杂协议
- 反馈: 对方不需要知道执行结果（fire-and-forget）
- GUI 同步: 远程开始→按钮同步更新；已在录制→忽略重复开始
- 单客户端: 只允许一个远程连接
- 认证: 预共享 token（AUTH:icm2024）
- 断线: 录制继续不受影响
- 状态显示: 左面板增加彩色文本标签显示连接状态
- 客户端脚本: connect()/start_record()/stop_record()/disconnect()

### Metis Review
**Identified Gaps** (addressed):
- BLE 未连接时收到 START_CSV → 静默忽略（已确认）
- _on_start_recording() 幂等性 → 通过 self._writer 判断是否已在录制
- 端口占用 → 优雅处理，不崩溃
- 行尾兼容 → .strip() 处理 \r\n 和 \n

---

## Work Objectives

### Core Objective
在现有 PyQt5 应用中嵌入轻量 TCP 服务端，使远程电脑可通过 Python 脚本控制 CSV 录制。

### Concrete Deliverables
- `icm/remote_server.py`: TCP 服务端线程模块
- `icm_remote.py` (项目根目录): 对方使用的客户端脚本
- 修改 `ui/main_window.py`: 集成 RemoteServer
- 修改 `ui/device_panel.py`: 增加远程状态标签

### Definition of Done
- [ ] 远程脚本可连接/认证/开始录制/停止录制/断开
- [ ] GUI 按钮与远程操作双向同步
- [ ] 左面板显示远程连接状态（绿色已连接/灰色未连接）
- [ ] 现有 BLE + GUI 功能完全不受影响

### Must Have
- TCP 服务端在应用启动时自动监听
- 认证失败立即断开连接
- 远程触发录制时 GUI 按钮状态同步
- 已在录制时忽略重复 START_CSV
- BLE 未连接时忽略 START_CSV
- 单客户端限制（拒绝第二个连接）
- 远程断开不影响正在进行的录制
- 应用关闭时优雅关闭 TCP 服务端

### Must NOT Have (Guardrails)
- 不修改 `icm/ecg_writer.py`
- 不修改 BLE 相关代码（ble_client.py, handshake.py, crypto.py）
- 不添加新的 pip 依赖（仅用 stdlib socket + threading）
- 不添加 SSL/TLS 加密
- 不支持多客户端并发
- 不添加重试/重连逻辑到客户端脚本
- 不在 UI 显示 IP 地址、时间戳或连接历史
- 不添加超过必要的 Qt 信号（仅 remote_connected / remote_disconnected）
- 不在 icm_remote.py 中添加 status()/is_recording()/async 变体

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest in requirements.txt, tests/ directory)
- **Automated tests**: NO (user confirmed real scenario verification only)
- **Framework**: N/A

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Network/Server**: Use Bash (Python subprocess) - start server, connect client, verify behavior
- **GUI**: Visual inspection via running app + remote script interaction

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - independent modules):
├── Task 1: TCP Server module (icm/remote_server.py) [unspecified-high]
├── Task 2: Client script (icm_remote.py) [quick]

Wave 2 (After Wave 1 - integration):
├── Task 3: Device panel UI modification [quick]
├── Task 4: MainWindow integration + wiring [unspecified-high]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
├── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Blocked By | Blocks |
|------|-----------|--------|
| 1 | None | 3, 4 |
| 2 | None | 4 |
| 3 | 1 | 4 |
| 4 | 1, 2, 3 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: **2 tasks** - T1 → `unspecified-high`, T2 → `quick`
- **Wave 2**: **2 tasks** - T3 → `quick`, T4 → `unspecified-high`
- **FINAL**: **4 tasks** - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. TCP Server Module (icm/remote_server.py)

  **What to do**:
  - 创建 `icm/remote_server.py`，实现 `RemoteControlServer` 类
  - 继承 `QObject`，定义 pyqtSignal: `remote_connected`, `remote_disconnected`, `start_recording_requested`, `stop_recording_requested`
  - 内部启动 `threading.Thread(daemon=True)` 运行 socket accept loop
  - 模块顶部常量: `TCP_PORT = 9527`, `AUTH_TOKEN = "icm2024"`
  - 认证流程: 客户端连接后必须首先发送 `AUTH:<token>\n`，验证通过则 emit `remote_connected`，失败则关闭连接
  - 指令处理: `START_CSV\n` → emit `start_recording_requested`; `STOP_CSV\n` → emit `stop_recording_requested`; `DISCONNECT\n` → 关闭连接 + emit `remote_disconnected`
  - 单客户端: 如果已有连接，拒绝新连接（立即 close）
  - 所有收到的指令先 `.strip()` 处理行尾
  - 格式错误指令: 忽略，不断开连接
  - `start()` 方法: 绑定端口，OSError 时 log warning 不崩溃
  - `stop()` 方法: 关闭 server socket + 客户端 socket，线程结束
  - 客户端断线检测: recv 返回空 bytes 时 emit `remote_disconnected`

  **Must NOT do**:
  - 不使用 QThread，使用 stdlib threading.Thread
  - 不添加任何 pip 依赖
  - 不添加重连/心跳逻辑
  - 不发送任何响应给客户端（fire-and-forget）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 网络编程 + Qt 信号集成，逻辑复杂度中等偏上
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: 非 UI 测试任务

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3, Task 4
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `ui/async_bridge.py:1-45` — threading.Thread daemon 模式 + 跨线程通信模式参考
  - `ui/main_window.py:200-225` — BLE callback → QMetaObject.invokeMethod 跨线程调用模式

  **API/Type References**:
  - `ui/main_window.py:170-198` — `_on_start_recording()` / `_do_stop_recording()` 的签名和行为，是信号最终要触发的方法

  **External References**:
  - Python stdlib `socket` module: TCP server pattern (socket.socket, bind, listen, accept, recv)
  - PyQt5 `pyqtSignal`: 跨线程信号发射（从非 Qt 线程 emit 是安全的）

  **WHY Each Reference Matters**:
  - `async_bridge.py` 展示了项目中如何在 daemon 线程中运行长期循环
  - `main_window.py:200-225` 展示了从非 Qt 线程安全调用 Qt 的模式
  - `main_window.py:170-198` 是信号最终要连接的目标 slot

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Server starts and listens
    Tool: Bash (python subprocess)
    Preconditions: No other process on port 9527
    Steps:
      1. python -c "from icm.remote_server import RemoteControlServer; from PyQt5.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); s=RemoteControlServer(); s.start(); import socket; c=socket.socket(); c.connect(('127.0.0.1',9527)); c.sendall(b'AUTH:icm2024\n'); import time; time.sleep(0.5); c.close(); s.stop(); print('OK')"
      2. Verify output contains 'OK' and no exceptions
    Expected Result: Server accepts connection, no crash
    Evidence: .omo/evidence/task-1-server-starts.txt

  Scenario: Auth failure closes connection
    Tool: Bash (python subprocess)
    Preconditions: Server running
    Steps:
      1. Connect with socket, send "AUTH:wrong_token\n"
      2. Attempt to recv — expect empty bytes (connection closed by server)
    Expected Result: Connection closed after wrong token
    Evidence: .omo/evidence/task-1-auth-failure.txt

  Scenario: Second client rejected
    Tool: Bash (python subprocess)
    Preconditions: Server running, first client already authenticated
    Steps:
      1. Connect second socket to 127.0.0.1:9527
      2. Attempt to recv — expect empty bytes (rejected immediately)
    Expected Result: Second connection refused
    Evidence: .omo/evidence/task-1-second-client-rejected.txt
  ```

  **Commit**: YES (groups with Task 2)
  - Message: `feat(remote): add TCP server module and client script`
  - Files: `icm/remote_server.py`, `icm_remote.py`
  - Pre-commit: `python -c "from icm.remote_server import RemoteControlServer; print('OK')"`

---

- [x] 2. Client Script (icm_remote.py)

  **What to do**:
  - 在项目根目录创建 `icm_remote.py`
  - 实现 `ICMRemote` 类，4 个方法: `connect()`, `start_record()`, `stop_record()`, `disconnect()`
  - `__init__(self, host: str, port: int = 9527, token: str = "icm2024")` — 保存参数
  - `connect()` — 创建 socket，连接，发送 `AUTH:<token>\n`
  - `start_record()` — 发送 `START_CSV\n`
  - `stop_record()` — 发送 `STOP_CSV\n`
  - `disconnect()` — 发送 `DISCONNECT\n`，关闭 socket
  - 底部 `if __name__ == "__main__"` 块: 简单的命令行演示（connect → start → sleep 5s → stop → disconnect）
  - 文件顶部注释说明用法

  **Must NOT do**:
  - 不添加 retry/reconnect 逻辑
  - 不添加 async 变体
  - 不添加 status()/is_recording() 方法
  - 不添加 context manager（__enter__/__exit__）
  - 不添加除 socket 外的依赖

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件、简单 socket 客户端，逻辑直接
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 4
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `icm/remote_server.py` (Task 1 产出) — 协议格式: `AUTH:<token>\n`, `START_CSV\n`, `STOP_CSV\n`, `DISCONNECT\n`

  **External References**:
  - Python stdlib `socket` module: TCP client pattern (connect, sendall, close)

  **WHY Each Reference Matters**:
  - 需要与 server 的协议完全匹配（指令字符串 + \n 结尾）

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Script imports without error
    Tool: Bash
    Preconditions: None
    Steps:
      1. python -c "from icm_remote import ICMRemote; r = ICMRemote('127.0.0.1'); print('OK')"
    Expected Result: Output "OK", exit code 0
    Evidence: .omo/evidence/task-2-import-ok.txt

  Scenario: Full flow with running server
    Tool: Bash (two processes)
    Preconditions: Task 1 server module exists
    Steps:
      1. Start server in background (python script that creates QApp + RemoteControlServer)
      2. Run: python -c "from icm_remote import ICMRemote; r=ICMRemote('127.0.0.1'); r.connect(); r.start_record(); r.stop_record(); r.disconnect(); print('PASS')"
      3. Verify output contains 'PASS'
    Expected Result: Full connect/start/stop/disconnect cycle completes without exception
    Evidence: .omo/evidence/task-2-full-flow.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `feat(remote): add TCP server module and client script`
  - Files: `icm_remote.py`
  - Pre-commit: `python -c "from icm_remote import ICMRemote; print('OK')"`

---

- [x] 3. Device Panel UI — 远程连接状态标签

  **What to do**:
  - 修改 `ui/device_panel.py`
  - 在 QGroupBox "ICM Devices" 下方（按钮行上方）添加新的 QGroupBox 或 QLabel 区域
  - 缩减设备列表（`_device_list`）的最大高度以腾出空间（例如 setMaximumHeight(120)）
  - 添加 `_remote_status_label = QLabel("远程客户端: 未连接")`
  - 默认样式: 灰色文字 `color: #888888`
  - 提供两个 public 方法:
    - `set_remote_connected()`: 标签文字改为 "远程客户端: 已连接"，颜色绿色 `color: #00aa00`
    - `set_remote_disconnected()`: 标签文字改为 "远程客户端: 未连接"，颜色灰色 `color: #888888`

  **Must NOT do**:
  - 不修改现有的 BLE 设备列表逻辑
  - 不修改现有按钮行为
  - 不添加 IP 地址/时间戳/连接历史显示
  - 不使用图标或圆点，仅彩色文本

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单 UI 修改，添加一个 QLabel + 两个方法
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 4
  - **Blocked By**: Task 1 (需要知道信号名称以便 Task 4 连接)

  **References**:

  **Pattern References**:
  - `ui/device_panel.py:35-72` — 现有 _setup_ui 布局结构，新标签应插入到 btn_layout 之前
  - `ui/device_panel.py:118-126` — `set_status()` / `set_connected()` 方法模式，新方法应遵循此风格

  **WHY Each Reference Matters**:
  - 需要在正确的布局位置插入新控件，不破坏现有布局
  - 新 public 方法要和现有 API 风格一致

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Label exists and displays default state
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. python -c "from PyQt5.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); from ui.device_panel import DevicePanel; p=DevicePanel(); p.show(); assert hasattr(p, '_remote_status_label'); assert '未连接' in p._remote_status_label.text(); print('PASS')"
    Expected Result: Output "PASS"
    Evidence: .omo/evidence/task-3-label-exists.txt

  Scenario: set_remote_connected changes label
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. python -c "from PyQt5.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); from ui.device_panel import DevicePanel; p=DevicePanel(); p.set_remote_connected(); assert '已连接' in p._remote_status_label.text(); assert '#00aa00' in p._remote_status_label.styleSheet(); print('PASS')"
    Expected Result: Output "PASS"
    Evidence: .omo/evidence/task-3-connected-label.txt
  ```

  **Commit**: YES (groups with Task 4)
  - Message: `feat(remote): integrate remote control into GUI`
  - Files: `ui/device_panel.py`

---

- [x] 4. MainWindow Integration — 连接 RemoteServer 到 GUI

  **What to do**:
  - 修改 `ui/main_window.py`
  - 在 `__init__` 中创建 `RemoteControlServer` 实例并调用 `start()`
  - 连接信号:
    - `remote_connected` → `self._device_panel.set_remote_connected()`
    - `remote_disconnected` → `self._device_panel.set_remote_disconnected()`
    - `start_recording_requested` → 新 slot `_on_remote_start_recording()`
    - `stop_recording_requested` → `_on_stop_recording()`（复用现有）
  - 实现 `_on_remote_start_recording()`:
    - 如果 `self._writer` 不为 None（已在录制）→ 忽略
    - 如果 `not self._ble.is_connected`（BLE 未连接）→ 忽略
    - 否则 → 调用 `self._on_start_recording()`
  - 在 `closeEvent` 中调用 `self._remote_server.stop()`
  - import `RemoteControlServer` from `icm.remote_server`

  **Must NOT do**:
  - 不修改 `_on_start_recording()` / `_do_stop_recording()` 的内部逻辑
  - 不添加新的 QTimer
  - 不修改 BLE 回调逻辑
  - 不在 status bar 显示远程相关信息

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 集成任务，需要理解信号连接和线程安全
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 3)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 1, Task 2, Task 3

  **References**:

  **Pattern References**:
  - `ui/main_window.py:47-78` — `__init__` 中对象创建和信号连接模式
  - `ui/main_window.py:59-64` — BLE callback 连接模式（on_xxx = self._on_xxx）
  - `ui/main_window.py:170-198` — `_on_start_recording()` 和 `_do_stop_recording()` 的完整实现
  - `ui/main_window.py:318-337` — `closeEvent` 清理顺序

  **API/Type References**:
  - `icm/remote_server.py` (Task 1 产出) — RemoteControlServer 的信号: remote_connected, remote_disconnected, start_recording_requested, stop_recording_requested
  - `ui/device_panel.py` (Task 3 产出) — set_remote_connected() / set_remote_disconnected() 方法

  **WHY Each Reference Matters**:
  - `__init__` 模式确保新对象以一致的方式初始化和连接
  - `_on_start_recording()` 需要理解其前置条件（BLE 连接 + 未在录制）
  - `closeEvent` 需要在正确顺序插入 server.stop()

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: App starts with remote server active
    Tool: Bash
    Preconditions: All previous tasks complete
    Steps:
      1. Start main.py in background
      2. python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1',9527)); s.sendall(b'AUTH:icm2024\n'); import time; time.sleep(0.5); s.close(); print('CONNECTED')"
      3. Verify output "CONNECTED"
    Expected Result: TCP server is listening when app starts
    Evidence: .omo/evidence/task-4-app-server-active.txt

  Scenario: Remote start ignored when BLE not connected
    Tool: Bash
    Preconditions: App running, no BLE device connected
    Steps:
      1. Connect via icm_remote.py, call start_record()
      2. Check ~/Documents/ICM_ECG/ for new CSV files
    Expected Result: No new CSV file created (START_CSV ignored)
    Evidence: .omo/evidence/task-4-ble-not-connected.txt

  Scenario: Remote start with BLE connected creates CSV
    Tool: Bash
    Preconditions: App running, BLE device connected and streaming
    Steps:
      1. Connect via icm_remote.py, call start_record()
      2. Wait 2 seconds
      3. Check ~/Documents/ICM_ECG/ for new CSV file
      4. Call stop_record()
      5. Verify CSV file is closed (non-zero size)
    Expected Result: CSV file created and populated
    Evidence: .omo/evidence/task-4-remote-start-csv.txt

  Scenario: GUI-first guard — double start ignored
    Tool: Bash
    Preconditions: App running, recording already started via GUI button
    Steps:
      1. Connect via icm_remote.py, call start_record()
      2. Count CSV files in output dir — should still be 1
    Expected Result: No additional CSV file, existing recording uninterrupted
    Evidence: .omo/evidence/task-4-double-start-guard.txt
  ```

  **Commit**: YES
  - Message: `feat(remote): integrate remote control into GUI`
  - Files: `ui/main_window.py`, `ui/device_panel.py`
  - Pre-commit: `python -c "from ui.main_window import MainWindow; print('OK')"`

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run linter on changed files. Review for: `as any`/`@ts-ignore` equivalent, empty catches, print() in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start app. Use icm_remote.py to: connect with correct token, connect with wrong token, send START_CSV, send STOP_CSV, disconnect. Verify GUI label updates. Test double-start scenario. Test disconnect-while-recording. Capture terminal output.
  Output: `Scenarios [N/N pass] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(remote): add TCP server module and client script` - icm/remote_server.py, icm_remote.py
- **Wave 2**: `feat(remote): integrate remote control into GUI` - ui/device_panel.py, ui/main_window.py

---

## Success Criteria

### Verification Commands
```bash
python -c "from icm.remote_server import RemoteControlServer; print('import OK')"
python -c "from icm_remote import ICMRemote; print('import OK')"
python main.py  # App starts without crash, TCP server listening
python icm_remote.py  # Client connects and controls recording
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] App starts normally with TCP server active
- [ ] Remote client can control recording
- [ ] GUI sync works bidirectionally
