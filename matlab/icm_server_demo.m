function icm_server_demo(port)
% ICM2 Remote Control Server Demo / 调试用服务端 (MATLAB port).
%
% Simulates the ICM2 app's TCP server so a remote client can be debugged.
% Prints all connection events and received commands to the console.
%
% Usage:
%   icm_server_demo            % default port 9527
%   icm_server_demo(9600)
%
% Press Ctrl-C to stop.

    if nargin < 1, port = 9527; end
    token = "icm2024";

    server = tcpserver("0.0.0.0", port);
    configureTerminator(server, "LF");
    state = struct('authed', false, 'token', token);

    % Use a nested-free approach: store state in the server's UserData.
    server.UserData = state;
    configureCallback(server, "terminator", @onLine);
    server.ConnectionChangedFcn = @onConn;

    log(sprintf('Listening on 0.0.0.0:%d (token: %s)', port, char(token)));
    log('Press Ctrl-C to stop.');

    % Keep the function alive so callbacks keep firing.
    cleanup = onCleanup(@() delete(server)); %#ok<NASGU>
    while true
        pause(0.2);
    end
end

function onConn(src, ~)
    if src.Connected
        log('Client connected');
    else
        src.UserData.authed = false;
        log('Client disconnected');
    end
end

function onLine(src, ~)
    line = strtrim(readline(src));
    if line == "", return; end
    if ~src.UserData.authed
        if line == "AUTH:" + string(src.UserData.token)
            src.UserData.authed = true;
            log('Auth OK');
        else
            log(sprintf('Auth FAILED (got %s)', line));
        end
        return;
    end
    log(sprintf('>>> %s', line));
    if line == "DISCONNECT"
        src.UserData.authed = false;
    end
end

function log(msg)
    fprintf('[%s] [SERVER] %s\n', datestr(now, 'HH:MM:SS.FFF'), msg); %#ok<DATST,TNOW1>
end
