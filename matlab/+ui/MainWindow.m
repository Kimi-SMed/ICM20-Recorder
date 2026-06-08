classdef MainWindow < handle
    % ICM2 ECG Recorder main window (programmatic uifigure).
    % MATLAB port of ui/main_window.py + ui/device_panel.py.
    %
    % Owns the BLE client, CSV writer, real-time plot, review plot and the
    % remote-control TCP server, and wires them together. ECG packets arrive
    % on the BLE notification callback and are dispatched straight to the plot
    % + CSV writer (MATLAB is single-threaded, so no asyncio/queue bridge).

    properties (Access = private)
        fig
        ble
        writer = [];
        remote
        permTimer

        % widgets
        deviceList
        statusLabel
        remoteStatusLabel
        scanBtn
        connectBtn
        disconnectBtn
        startBtn
        stopBtn
        reviewBtn
        ampLabel
        sampleLabel
        hrLabel
        fileLabel
        statusBar
        plot
        review

        lastScan = struct('name', {}, 'address', {}, 'rssi', {});
    end

    methods
        function obj = MainWindow()
            obj.ble = icm.IcmBleClient();
            obj.ble.EcgPacketFcn   = @(pkt) obj.onEcgPacket(pkt);
            obj.ble.DisconnectedFcn = @() obj.onDeviceDisconnected();

            obj.buildUi();

            % Permission renewal: sync RTC + SET_HOST_INFO every 14 minutes.
            obj.permTimer = timer( ...
                'ExecutionMode', 'fixedRate', ...
                'Period', 14 * 60, ...
                'TimerFcn', @(~,~) obj.renewPermission());

            % Remote control server.
            obj.remote = icm.RemoteControlServer();
            obj.remote.RemoteConnectedFcn    = @() obj.setRemoteStatus(true);
            obj.remote.RemoteDisconnectedFcn = @() obj.setRemoteStatus(false);
            obj.remote.StartRecordingFcn     = @() obj.onRemoteStart();
            obj.remote.StopRecordingFcn      = @() obj.stopRecording();
            obj.remote.start();
        end
    end

    % ================= UI construction =================
    methods (Access = private)
        function buildUi(obj)
            obj.fig = uifigure('Name', 'ICM2 ECG Recorder', 'Position', [100 100 1200 700]);
            obj.fig.CloseRequestFcn = @(~,~) obj.onClose();

            outer = uigridlayout(obj.fig, [2 1], 'RowHeight', {'1x', 34}, 'Padding', 6);

            top = uigridlayout(outer, [1 2], 'ColumnWidth', {340, '1x'}, ...
                'Padding', 0, 'ColumnSpacing', 6);

            % ----- left: device panel -----
            left = uigridlayout(top, [6 1], ...
                'RowHeight', {'1x', 24, 8, 24, 32, 22}, 'Padding', 0, 'RowSpacing', 4);

            obj.deviceList = uilistbox(left, 'Items', {}, 'Multiselect', 'off');
            obj.deviceList.ValueChangedFcn = @(~,~) []; % selection only

            obj.statusLabel = uilabel(left, 'Text', 'Not connected', ...
                'HorizontalAlignment', 'center');

            uilabel(left, 'Text', '');  % spacer row

            obj.remoteStatusLabel = uilabel(left, 'Text', '远程客户端: 未连接', ...
                'HorizontalAlignment', 'center', 'FontColor', [0.53 0.53 0.53]);

            btnRow = uigridlayout(left, [1 3], 'Padding', 0, 'ColumnSpacing', 4);
            obj.scanBtn = uibutton(btnRow, 'Text', 'Scan', ...
                'ButtonPushedFcn', @(~,~) obj.onScan());
            obj.connectBtn = uibutton(btnRow, 'Text', 'Connect', 'Enable', 'off', ...
                'ButtonPushedFcn', @(~,~) obj.onConnect());
            obj.disconnectBtn = uibutton(btnRow, 'Text', 'Disconnect', 'Enable', 'off', ...
                'ButtonPushedFcn', @(~,~) obj.onDisconnect());

            uilabel(left, 'Text', '');  % filler

            % ----- centre: live plot (full height) -----
            livePanel = uipanel(top, 'BorderType', 'none');
            obj.plot = ui.EcgPlotWidget(livePanel);

            % Review lives in its OWN separate window (hidden until opened).
            obj.review = ui.ReviewPlotWidget();

            % ----- bottom: toolbar / status bar -----
            obj.statusBar = uigridlayout(outer, [1 8], ...
                'ColumnWidth', {120, 120, 80, '1x', 110, 110, 110, 220}, ...
                'Padding', 2, 'ColumnSpacing', 6);

            obj.startBtn = uibutton(obj.statusBar, 'Text', 'Start Recording', ...
                'Enable', 'off', 'ButtonPushedFcn', @(~,~) obj.startRecording());
            obj.stopBtn = uibutton(obj.statusBar, 'Text', 'Stop Recording', ...
                'Enable', 'off', 'ButtonPushedFcn', @(~,~) obj.stopRecording());
            obj.reviewBtn = uibutton(obj.statusBar, 'Text', 'Review', ...
                'ButtonPushedFcn', @(~,~) obj.review.show());  % open review window

            obj.fileLabel = uilabel(obj.statusBar, 'Text', ...
                'Idle - Click Scan to find ICM devices');

            obj.ampLabel = uilabel(obj.statusBar, 'Text', 'Amp: -- mV');
            obj.sampleLabel = uilabel(obj.statusBar, 'Text', 'Samples: 0');
            obj.hrLabel = uilabel(obj.statusBar, 'Text', '-- bpm', ...
                'FontSize', 18, 'FontWeight', 'bold', 'FontColor', [0.8 0.13 0]);
            uilabel(obj.statusBar, 'Text', '');
        end
    end

    % ================= button handlers =================
    methods (Access = private)
        function onScan(obj)
            obj.deviceList.Items = {};
            obj.connectBtn.Enable = 'off';
            obj.setStatus('Scanning for ICM devices...');
            drawnow;
            results = obj.ble.scan();
            obj.lastScan = results;
            items = cell(1, numel(results));
            data  = cell(1, numel(results));
            for i = 1:numel(results)
                items{i} = sprintf('%s  |  %s  |  RSSI: %d dBm', ...
                    results(i).name, results(i).address, results(i).rssi);
                data{i} = results(i).address;
            end
            obj.deviceList.Items = items;
            obj.deviceList.ItemsData = data;
            if ~isempty(items)
                obj.deviceList.Value = data{1};
                obj.connectBtn.Enable = 'on';
            end
            obj.setStatus(sprintf('Found %d ICM device(s)', numel(results)));
        end

        function onConnect(obj)
            addr = obj.deviceList.Value;
            if isempty(addr), return; end
            obj.setStatus(sprintf('Connecting to %s (handshake ~5s)...', addr));
            drawnow;
            try
                obj.ble.connect(addr);
            catch e
                obj.setStatus(sprintf('Handshake failed: %s', e.message));
                uialert(obj.fig, e.message, 'Connection Failed');
                return;
            end
            obj.onHandshakeDone(addr);
        end

        function onHandshakeDone(obj, addr)
            obj.statusLabel.Text = sprintf('Connected: %s', addr);
            obj.scanBtn.Enable = 'off';
            obj.connectBtn.Enable = 'off';
            obj.disconnectBtn.Enable = 'on';
            obj.startBtn.Enable = 'on';
            obj.setStatus('Handshake complete - streaming ECG. Click Start Recording to save CSV.');

            % run_test_4 order: sync RTC -> set host permission -> start ECG
            obj.ble.syncRtc();
            obj.ble.setHostInfo();
            start(obj.permTimer);
            obj.ble.startRecording();
        end

        function onDisconnect(obj)
            obj.safeStopTimer();
            if ~isempty(obj.writer)
                obj.stopRecording();
            end
            obj.ble.disconnect();
            obj.onDeviceDisconnected();
        end

        function onDeviceDisconnected(obj)
            obj.safeStopTimer();
            obj.disconnectBtn.Enable = 'off';
            obj.scanBtn.Enable = 'on';
            obj.startBtn.Enable = 'off';
            obj.stopBtn.Enable = 'off';
            obj.statusLabel.Text = 'Disconnected';
            obj.hrLabel.Text = '-- bpm';
            obj.ampLabel.Text = 'Amp: -- mV';
            obj.plot.clear();
            if ~isempty(obj.writer)
                obj.writer.close();
                obj.writer = [];
            end
            obj.setStatus('Device disconnected');
        end

        function startRecording(obj)
            mac = obj.ble.macAddress();
            if isempty(mac), mac = 'unknown'; end
            obj.writer = icm.EcgCsvWriter(icm.Config.csvDefaultDir(), mac);
            try
                p = obj.writer.open();
            catch e
                uialert(obj.fig, sprintf('Cannot open CSV file:\n%s', e.message), 'File Error');
                obj.writer = [];
                return;
            end
            [~, n, x] = fileparts(p);
            obj.fileLabel.Text = [n x];
            obj.startBtn.Enable = 'off';
            obj.stopBtn.Enable = 'on';
            obj.setStatus('Recording...');
        end

        function stopRecording(obj)
            csvPath = '';
            if ~isempty(obj.writer)
                csvPath = obj.writer.currentPath();
                obj.writer.close();
                obj.writer = [];
            end
            obj.startBtn.Enable = 'on';
            obj.stopBtn.Enable = 'off';
            obj.fileLabel.Text = '';
            obj.setStatus('Recording stopped. Ready to record again.');
            if ~isempty(csvPath) && isfile(csvPath)
                obj.review.loadCsv(csvPath);
            end
        end

        function onRemoteStart(obj)
            if ~isempty(obj.writer)
                return;   % already recording
            end
            if ~obj.ble.isConnected()
                return;   % BLE not connected
            end
            obj.startRecording();
        end

        function renewPermission(obj)
            if obj.ble.isConnected()
                obj.ble.syncRtc();
                obj.ble.setHostInfo();
            end
        end
    end

    % ================= ECG data path =================
    methods (Access = private)
        function onEcgPacket(obj, pkt)
            obj.plot.appendPacket(pkt);

            if ~isempty(obj.writer) && obj.writer.isOpen()
                try
                    obj.writer.writePacket(pkt);
                catch e
                    obj.stopRecording();
                    uialert(obj.fig, sprintf('CSV write failed:\n%s', e.message), 'Disk Error');
                    return;
                end
            end

            if pkt.amplitudeMv ~= 0
                obj.ampLabel.Text = sprintf('Amp: %.2f mV', pkt.amplitudeMv);
            end
            if ~isempty(pkt.rrIntervals)
                rr = pkt.rrIntervals(1);
                if rr > 0
                    obj.hrLabel.Text = sprintf('%d bpm', round(60000 / rr));
                end
            end
            if ~isempty(obj.writer)
                obj.sampleLabel.Text = sprintf('Samples: %d', obj.writer.sampleCount());
            end
        end
    end

    % ================= helpers / teardown =================
    methods (Access = private)
        function setStatus(obj, msg)
            obj.fileLabel.Text = msg;
        end

        function setRemoteStatus(obj, connected)
            if connected
                obj.remoteStatusLabel.Text = '远程客户端: 已连接';
                obj.remoteStatusLabel.FontColor = [0 0.67 0];
            else
                obj.remoteStatusLabel.Text = '远程客户端: 未连接';
                obj.remoteStatusLabel.FontColor = [0.53 0.53 0.53];
            end
        end

        function safeStopTimer(obj)
            try
                if ~isempty(obj.permTimer) && isvalid(obj.permTimer) ...
                        && strcmp(obj.permTimer.Running, 'on')
                    stop(obj.permTimer);
                end
            catch
            end
        end

        function onClose(obj)
            obj.safeStopTimer();
            try
                if ~isempty(obj.permTimer) && isvalid(obj.permTimer)
                    delete(obj.permTimer);
                end
            catch
            end
            if ~isempty(obj.writer)
                obj.writer.close();
                obj.writer = [];
            end
            try
                obj.ble.disconnect();
            catch
            end
            try
                obj.remote.stop();
            catch
            end
            try
                delete(obj.review);   % close the separate review window
            catch
            end
            delete(obj.fig);
        end
    end
end
