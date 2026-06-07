#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ICM2 Remote Control Server Demo / 调试用服务端

用于对方客户端调试，模拟 ICM2 应用的服务端行为。
在命令行打印所有连接事件和收到的指令。

用法 / Usage:
    python icm_server_demo.py [port]

    port: 监听端口，默认 9527

示例输出:
    [SERVER] Listening on 0.0.0.0:9527 (token: icm2024)
    [SERVER] Client connected from 192.168.1.101:54321
    [SERVER] Auth OK
    [SERVER] >>> START_CSV
    [SERVER] >>> STOP_CSV
    [SERVER] >>> DISCONNECT
    [SERVER] Client disconnected
"""

import socket
import sys
import time
from datetime import datetime

# ── 配置 ────────────────────────────────────────────────────────────────────
TCP_PORT   = 9527
AUTH_TOKEN = "icm2024"
# ────────────────────────────────────────────────────────────────────────────


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(msg: str) -> None:
    print(f"[{timestamp()}] {msg}", flush=True)


def handle_client(conn: socket.socket, addr: tuple) -> None:
    log(f"Client connected from {addr[0]}:{addr[1]}")
    conn.settimeout(1.0)

    try:
        # ── Auth phase ───────────────────────────────────────────────────────
        buf = b""
        while True:
            try:
                chunk = conn.recv(256)
            except socket.timeout:
                continue
            if not chunk:
                log("Client disconnected before auth")
                return
            buf += chunk
            if b"\n" in buf:
                line, _, buf = buf.partition(b"\n")
                break

        cmd = line.decode("utf-8", errors="replace").strip()

        if cmd != f"AUTH:{AUTH_TOKEN}":
            log(f"Auth FAILED (received: {cmd!r}) — closing connection")
            return

        log("Auth OK")

        # ── Command loop ─────────────────────────────────────────────────────
        while True:
            try:
                chunk = conn.recv(256)
            except socket.timeout:
                continue

            if not chunk:
                log("Client disconnected")
                return

            buf += chunk
            while b"\n" in buf:
                line, _, buf = buf.partition(b"\n")
                cmd = line.decode("utf-8", errors="replace").strip()
                if not cmd:
                    continue

                if cmd == "START_CSV":
                    log(">>> START_CSV  (recording started)")
                elif cmd == "STOP_CSV":
                    log(">>> STOP_CSV   (recording stopped)")
                elif cmd == "DISCONNECT":
                    log(">>> DISCONNECT (client requested disconnect)")
                    log("Client disconnected")
                    return
                else:
                    log(f">>> UNKNOWN: {cmd!r}  (ignored)")

    finally:
        try:
            conn.close()
        except OSError:
            pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else TCP_PORT

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind(("", port))
    except OSError as e:
        print(f"[ERROR] Cannot bind port {port}: {e}")
        sys.exit(1)

    server.listen(1)
    log(f"Listening on 0.0.0.0:{port}  (token: {AUTH_TOKEN})")
    log("Waiting for client... (Ctrl+C to quit)")
    print()

    try:
        while True:
            try:
                server.settimeout(1.0)
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                break

            handle_client(conn, addr)
            print()
            log("Waiting for next client...")

    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        log("Server stopped")


if __name__ == "__main__":
    main()
