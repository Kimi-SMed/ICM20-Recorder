classdef RemoteControlServer < handle
    % LAN TCP server for remote control of CSV recording.
    % MATLAB port of icm/remote_server.py (uses tcpserver).
    %
    % Protocol (newline-terminated text):
    %   AUTH:<token>   -> authenticate (must be first)
    %   START_CSV      -> start CSV recording
    %   STOP_CSV       -> stop CSV recording
    %   DISCONNECT     -> disconnect cleanly
    %
    % Callbacks (set by the UI; all fire on the MATLAB main thread):
    %   RemoteConnectedFcn, RemoteDisconnectedFcn,
    %   StartRecordingFcn, StopRecordingFcn

    properties (Constant)
        TCP_PORT   = 9527;
        AUTH_TOKEN = "icm2024";
    end

    properties
        RemoteConnectedFcn    = [];
        RemoteDisconnectedFcn = [];
        StartRecordingFcn     = [];
        StopRecordingFcn      = [];
    end

    properties (Access = private)
        server = [];
        authed = false;
    end

    methods
        function start(obj)
            if ~isempty(obj.server), return; end
            try
                obj.server = tcpserver("0.0.0.0", obj.TCP_PORT);
            catch e
                warning('icm:remoteBind', ...
                        'RemoteControlServer: cannot bind port %d - %s', ...
                        obj.TCP_PORT, e.message);
                obj.server = [];
                return;
            end
            configureTerminator(obj.server, "LF");
            configureCallback(obj.server, "terminator", @(s, e) obj.onLine(s, e));
            obj.server.ConnectionChangedFcn = @(s, e) obj.onConnectionChanged(s, e);
            fprintf('RemoteControlServer: listening on port %d\n', obj.TCP_PORT);
        end

        function stop(obj)
            if ~isempty(obj.server)
                try, delete(obj.server); catch, end
                obj.server = [];
            end
            obj.authed = false;
        end
    end

    methods (Access = private)
        function onConnectionChanged(obj, s, ~)
            if ~s.Connected
                obj.authed = false;
                obj.fire(obj.RemoteDisconnectedFcn);
            end
        end

        function onLine(obj, s, ~)
            line = strtrim(readline(s));
            if line == ""
                return;
            end

            if ~obj.authed
                if line == "AUTH:" + obj.AUTH_TOKEN
                    obj.authed = true;
                    obj.fire(obj.RemoteConnectedFcn);
                else
                    warning('icm:remoteAuth', 'auth failed (got %s), closing', line);
                    flush(s);
                end
                return;
            end

            switch line
                case "START_CSV"
                    obj.fire(obj.StartRecordingFcn);
                case "STOP_CSV"
                    obj.fire(obj.StopRecordingFcn);
                case "DISCONNECT"
                    obj.authed = false;
                    obj.fire(obj.RemoteDisconnectedFcn);
                otherwise
                    % unknown command - ignore, keep connection
            end
        end

        function fire(~, fcn)
            if ~isempty(fcn)
                fcn();
            end
        end
    end
end
