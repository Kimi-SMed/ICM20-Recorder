#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ICM2 远程录音控制客户端 / ICM2 Remote Recording Control Client

本模块提供了一个独立的 Python 客户端，用于远程控制 ICM2 心电图记录仪的 CSV 文件录制。
This module provides a standalone Python client for remote-controlling CSV recording on the ICM2 ECG Recorder.

使用方法 / Usage:
    from icm_remote import ICMRemote
    
    # 连接到服务器 / Connect to server
    client = ICMRemote(host='127.0.0.1', port=9527, token='icm2024')
    client.connect()
    
    # 开始录制 / Start recording
    client.start_record()
    
    # 停止录制 / Stop recording
    client.stop_record()
    
    # 断开连接 / Disconnect
    client.disconnect()

协议 / Protocol:
    - AUTH:<token>\\n     : 认证 / Authentication
    - START_CSV\\n        : 开始CSV录制 / Start CSV recording
    - STOP_CSV\\n         : 停止CSV录制 / Stop CSV recording
    - DISCONNECT\\n       : 断开连接 / Disconnect
"""

import socket
import time
import sys


class ICMRemote:
    """ICM2 远程控制客户端 / ICM2 Remote Control Client"""
    
    def __init__(self, host: str, port: int = 9527, token: str = "icm2024"):
        """
        初始化客户端 / Initialize the client
        
        Args:
            host: 服务器地址 / Server address
            port: 服务器端口 / Server port (default: 9527)
            token: 认证令牌 / Authentication token (default: "icm2024")
        """
        self._host = host
        self._port = port
        self._token = token
        self._socket = None
    
    def connect(self):
        """连接到服务器并认证 / Connect to server and authenticate"""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._host, self._port))
        auth_cmd = f"AUTH:{self._token}\n"
        self._socket.sendall(auth_cmd.encode())
    
    def start_record(self):
        """开始CSV录制 / Start CSV recording"""
        cmd = "START_CSV\n"
        self._socket.sendall(cmd.encode())
    
    def stop_record(self):
        """停止CSV录制 / Stop CSV recording"""
        cmd = "STOP_CSV\n"
        self._socket.sendall(cmd.encode())
    
    def disconnect(self):
        """断开连接 / Disconnect from server"""
        cmd = "DISCONNECT\n"
        self._socket.sendall(cmd.encode())
        self._socket.close()


if __name__ == "__main__":
    # 从命令行参数获取主机地址，默认使用 127.0.0.1
    # Get host from command line argument, default to 127.0.0.1
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    
    print(f"连接到 / Connecting to {host}:9527...")
    
    # 创建客户端并连接 / Create client and connect
    client = ICMRemote(host=host, port=9527, token="icm2024")
    client.connect()
    print("已连接 / Connected")
    
    # 开始录制 / Start recording
    print("开始录制 / Starting recording...")
    client.start_record()
    
    # 录制 5 秒 / Record for 5 seconds
    time.sleep(10)
    
    # 停止录制 / Stop recording
    print("停止录制 / Stopping recording...")
    client.stop_record()
    
    # 断开连接 / Disconnect
    client.disconnect()
    print("已断开连接 / Disconnected")
