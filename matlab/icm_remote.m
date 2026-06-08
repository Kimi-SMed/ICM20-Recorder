classdef icm_remote < handle
    % ICM2 远程录音控制客户端 / ICM2 Remote Recording Control Client (MATLAB port).
    %
    % Controls CSV recording on a running ICM2 ECG Recorder over TCP.
    %
    % Usage:
    %   c = icm_remote('127.0.0.1');     % host, [port], [token]
    %   c.connect();
    %   c.startRecord();
    %   pause(10);
    %   c.stopRecord();
    %   c.disconnect();
    %
    % Protocol (newline-terminated):
    %   AUTH:<token> | START_CSV | STOP_CSV | DISCONNECT

    properties (Access = private)
        host
        port
        token
        sock = [];
    end

    methods
        function obj = icm_remote(host, port, token)
            if nargin < 1, host = '127.0.0.1'; end
            if nargin < 2 || isempty(port), port = 9527; end
            if nargin < 3 || isempty(token), token = 'icm2024'; end
            obj.host  = host;
            obj.port  = port;
            obj.token = token;
        end

        function connect(obj)
            obj.sock = tcpclient(obj.host, obj.port);
            configureTerminator(obj.sock, "LF");
            writeline(obj.sock, sprintf('AUTH:%s', obj.token));
        end

        function startRecord(obj)
            writeline(obj.sock, 'START_CSV');
        end

        function stopRecord(obj)
            writeline(obj.sock, 'STOP_CSV');
        end

        function disconnect(obj)
            if ~isempty(obj.sock)
                try
                    writeline(obj.sock, 'DISCONNECT');
                catch
                end
                obj.sock = [];   % releasing the handle closes the connection
            end
        end
    end

    methods (Static)
        function demo(host)
            % Command-line demo: connect, record 10s, stop, disconnect.
            if nargin < 1, host = '127.0.0.1'; end
            fprintf('连接到 / Connecting to %s:9527...\n', host);
            c = icm_remote(host);
            c.connect();
            fprintf('已连接 / Connected\n');
            fprintf('开始录制 / Starting recording...\n');
            c.startRecord();
            pause(10);
            fprintf('停止录制 / Stopping recording...\n');
            c.stopRecord();
            c.disconnect();
            fprintf('已断开连接 / Disconnected\n');
        end
    end
end
