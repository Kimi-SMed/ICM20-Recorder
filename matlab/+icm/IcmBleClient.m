classdef IcmBleClient < handle
    % ICM2 BLE client: scan, connect+handshake, ECG notify, RTC sync, host auth.
    % MATLAB port of icm/ble_client.py (Bluetooth Toolbox `ble` API).
    %
    % Threading note: unlike the Python version (asyncio thread + queue + Qt
    % poll), MATLAB delivers BLE notifications on the main thread via the
    % characteristic DataAvailableFcn, so parsed packets are dispatched
    % directly to the EcgPacketFcn callback - no cross-thread bridge needed.

    properties (Constant)
        CMD_SET_HOST_INFO     = 32;          % 0x20
        HOST_TYPE_FOLLOW_UP   = 2;           % 随访程控
        CMD_PROGRAM_RTC_DELTA = 48;          % 0x30
        ICM_EPOCH_OFFSET      = 1609459200;  % 2021-01-01 00:00:00 UTC
        TIME_ZONE_UTC8        = 32;          % 32/4*3600 = UTC+8
    end

    properties
        % Callback invoked with each parsed ECG packet (set by the UI).
        EcgPacketFcn = [];
        % Callback invoked on unexpected device disconnect.
        DisconnectedFcn = [];
    end

    properties (Access = private)
        bleDev    = [];
        macV      = '';
        connected = false;
        recording = false;
        cryption  = [];
        seq       = 0;
        ecgChar   = [];
        downChar  = [];
    end

    methods
        % ---- scan -----------------------------------------------------
        function results = scan(~, timeout)
            if nargin < 2, timeout = 5.0; end
            results = struct('name', {}, 'address', {}, 'rssi', {});
            try
                list = blelist('Timeout', timeout);
            catch e
                warning('icm:scanFailed', 'BLE scan failed: %s', e.message);
                return;
            end
            prefix = upper(icm.Config.DEVICE_NAME_PREFIX);
            for i = 1:height(list)
                name = string(list.Name(i));
                if name == "" , continue; end
                if startsWith(upper(name), prefix)
                    rssi = -99;
                    if ismember('RSSI', list.Properties.VariableNames)
                        rssi = double(list.RSSI(i));
                    end
                    results(end+1) = struct( ...           %#ok<AGROW>
                        'name', char(name), ...
                        'address', char(string(list.Address(i))), ...
                        'rssi', rssi);
                end
            end
            if ~isempty(results)
                [~, ord] = sort([results.rssi], 'descend');
                results = results(ord);
            end
        end

        % ---- connect + handshake -------------------------------------
        function connect(obj, macAddress)
            if obj.connected
                warning('icm:alreadyConnected', 'Already connected - disconnect first');
                return;
            end
            obj.macV = macAddress;
            try
                fprintf('[ICM] ble() connecting to %s ...\n', macAddress);
                obj.bleDev = ble(macAddress);          % throws on failure
                obj.connected = true;
                fprintf('[ICM] BLE link up; starting handshake\n');

                hs = icm.SecretHandshake(obj.bleDev, macAddress);
                [obj.cryption, obj.seq] = hs.perform();
                fprintf('[ICM] handshake OK (next seq=%d); resolving characteristics\n', obj.seq);

                obj.ecgChar  = icm.findCharacteristic(obj.bleDev, icm.Config.UUID_ECG_DATA);
                obj.downChar = icm.findCharacteristic(obj.bleDev, icm.Config.UUID_DOWN_CMD);
                fprintf('[ICM] ECG + DOWN characteristics resolved; connect complete\n');
            catch err
                % Roll back all state so the user can simply click Connect again.
                fprintf(2, '[ICM] connect failed: %s\n', err.message);
                obj.connected = false;
                obj.cryption  = [];
                obj.seq       = 0;
                obj.ecgChar   = [];
                obj.downChar  = [];
                obj.bleDev    = [];
                rethrow(err);
            end
        end

        % ---- ECG notify ----------------------------------------------
        function startRecording(obj)
            if ~obj.connected || isempty(obj.bleDev)
                error('icm:notConnected', 'Not connected');
            end
            if obj.recording, return; end
            if isempty(obj.ecgChar)
                obj.ecgChar = icm.findCharacteristic(obj.bleDev, icm.Config.UUID_ECG_DATA);
            end
            fprintf('[ICM] ECG_DATA attrs = [%s]; subscribing ...\n', ...
                    strjoin(string(obj.ecgChar.Attributes), ','));
            % Subscribe FIRST (auto-picks notify/indicate), then attach callback,
            % so assigning DataAvailableFcn can't pre-empt with a wrong-type subscribe.
            icm.subscribeChar(obj.ecgChar);
            obj.ecgChar.DataAvailableFcn = @(src, evt) obj.onEcgNotify(src, evt);
            fprintf('[ICM] ECG streaming started\n');
            obj.recording = true;
        end

        function stopRecording(obj)
            if ~obj.recording || isempty(obj.ecgChar), return; end
            try
                obj.ecgChar.DataAvailableFcn = [];
                unsubscribe(obj.ecgChar);
            catch e
                warning('icm:stopNotify', 'stop notify error: %s', e.message);
            end
            obj.recording = false;
        end

        % ---- RTC sync + host permission ------------------------------
        function syncRtc(obj)
            if ~obj.canSendCmd(), return; end
            try
                nowUtc = posixtime(datetime('now', 'TimeZone', 'UTC'));
                ts = uint32(int64(floor(nowUtc)) - obj.ICM_EPOCH_OFFSET);
                payload = [typecast(uint32(ts), 'uint8'), ...
                           uint8([obj.TIME_ZONE_UTC8, 0, 0, 0])];
                obj.sendEncryptedCmd(obj.CMD_PROGRAM_RTC_DELTA, payload);
            catch e
                warning('icm:syncRtc', 'sync_rtc failed: %s', e.message);
            end
        end

        function setHostInfo(obj)
            if ~obj.canSendCmd(), return; end
            try
                payload = obj.buildHostInfoPayload();
                obj.sendEncryptedCmd(obj.CMD_SET_HOST_INFO, payload);
            catch e
                warning('icm:setHostInfo', 'set_host_info failed: %s', e.message);
            end
        end

        % ---- disconnect ----------------------------------------------
        function disconnect(obj)
            if obj.recording
                obj.stopRecording();
            end
            % Releasing all references to the ble object disconnects the device.
            obj.ecgChar  = [];
            obj.downChar = [];
            obj.bleDev   = [];
            obj.connected = false;
            obj.cryption = [];
            obj.seq = 0;
        end

        % ---- state accessors -----------------------------------------
        function tf = isConnected(obj),  tf = obj.connected; end
        function tf = isRecording(obj),  tf = obj.recording; end
        function s  = macAddress(obj),   s  = obj.macV;       end
    end

    methods (Access = private)
        function tf = canSendCmd(obj)
            tf = obj.connected && ~isempty(obj.bleDev) && ~isempty(obj.cryption);
        end

        function sendEncryptedCmd(obj, cmd, payload)
            inner = obj.buildGeneralCmd(obj.seq, cmd, payload);
            obj.seq = mod(obj.seq + 1, 256);
            enc = obj.cryption.encrypt(inner);
            frame = icm.Crypto.appendCRC16([uint8(90), enc]);   % 0x5A prefix + CRC16
            write(obj.downChar, frame);
        end

        function onEcgNotify(obj, src, ~)
            data = uint8(read(src, 'oldest'));
            receivedMs = int64(floor(posixtime(datetime('now', 'TimeZone', 'UTC')) * 1000));
            pkt = icm.parseEcgPacket(data, receivedMs);
            if ~isempty(pkt) && ~isempty(obj.EcgPacketFcn)
                obj.EcgPacketFcn(pkt);
            end
        end

        function p = buildHostInfoPayload(obj)
            n = randi([100000000000, 999999999999]);   % 12-digit serial
            serial = sprintf('%d', n);
            p = uint8([double(serial), obj.HOST_TYPE_FOLLOW_UP, 0, 0, 0]);
        end
    end

    methods (Static, Access = private)
        function s = buildCmdStruct(seq, cmd, data)
            % [len, seq, cmd, <data>, <data_crc32>, <crc8>]  (== create_icm_cmd)
            if isempty(data)
                frame = uint8([4, mod(seq, 256), cmd]);
            else
                data = uint8(data(:).');
                dataCrc32 = typecast(uint32(icm.Crypto.crc32(data)), 'uint8');
                frame = [uint8([numel(data) + 4, mod(seq, 256), cmd]), data, dataCrc32];
            end
            s = [frame, icm.Crypto.crc8(frame)];
        end

        function frame = buildGeneralCmd(seq, cmd, data)
            % Inner frame that gets encrypted (== generate_general_cmd).
            cmdStruct = icm.IcmBleClient.buildCmdStruct(seq, cmd, data);
            if numel(cmdStruct) > 3
                params = cmdStruct(4:end-1);     % cmd_struct[3:-1]
            else
                params = [];
            end
            frame = uint8([4, mod(seq, 256), cmd]);
            if ~isempty(params)
                frame(1) = frame(1) + numel(params) + 4;
                frame = [frame, params];
                crc32 = icm.Crypto.crc32(frame(4:end));
                frame = [frame, typecast(uint32(crc32), 'uint8')];
            end
            frame = [frame, uint8(mod(sum(double(frame)), 256))];
        end
    end
end
