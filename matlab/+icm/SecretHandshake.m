classdef SecretHandshake < handle
    % ICM2 BLE 5-step challenge-response handshake.
    % MATLAB port of icm/handshake.py.
    %
    % Takes a connected `ble` device + MAC. Drives a state machine off the
    % UP_CMD notification callback; perform() blocks (servicing callbacks via
    % pause) until the handshake completes or times out.
    %
    %   hs = icm.SecretHandshake(bleDev, mac);
    %   [cryption, finalSeq] = hs.perform();

    properties (Constant)
        BLE_CMD_ICC_TO_ICM = 49;    % 0x31
        BLE_CMD_ICM_TO_ICC = 50;    % 0x32
        BLE_CMD_ACKNOWLEDGE = 191;  % 0xBF
    end

    properties (Access = private)
        bleDev
        mac
        upChar
        downChar
        seq        = 1;       % matches icm_control.py self.sequence = 1
        sharedKey
        nonce1
        secretKey1
        secretKey2 = [];
        doneFlag   = false;
        errMsg     = '';
    end

    methods
        function obj = SecretHandshake(bleDev, macAddress)
            obj.bleDev = bleDev;
            obj.mac    = macAddress;
            obj.sharedKey = uint8([ ...
                0x00,0xF1,0x7A,0x00,0x33,0x2C, ...
                0x00,0x5B,0x14,0x00,0x55,0x71, ...
                0x00,0x17,0x6B,0x00]);
        end

        function setSharedKey(obj)
            % Derive shared_key positions from the 6 MAC octets (order matches
            % the Python reference: parts[0],[3],[1],[4],[2],[5]).
            o = icm.parseMacOctets(obj.mac);
            obj.sharedKey(1)  = o(1);
            obj.sharedKey(4)  = o(4);
            obj.sharedKey(7)  = o(2);
            obj.sharedKey(10) = o(5);
            obj.sharedKey(13) = o(3);
            obj.sharedKey(16) = o(6);
        end

        function combined = generateChallenge(obj)
            obj.nonce1     = uint8(randi([0 255], 1, 16));
            obj.secretKey1 = uint8(randi([0 255], 1, 16));
            combined = icm.Crypto.encryptCBC(obj.sharedKey, [obj.nonce1, obj.secretKey1]);
        end

        function [cryption, finalSeq] = perform(obj)
            obj.setSharedKey();
            fprintf('[HS] shared_key derived from MAC\n');
            challenge = obj.generateChallenge();
            fprintf('[HS] challenge generated (AES OK)\n');

            obj.upChar   = icm.findCharacteristic(obj.bleDev, icm.Config.UUID_UP_CMD);
            fprintf('[HS] UP_CMD characteristic resolved; attrs = [%s]\n', ...
                    icm.SecretHandshake.attrStr(obj.upChar));
            obj.downChar = icm.findCharacteristic(obj.bleDev, icm.Config.UUID_DOWN_CMD);
            fprintf('[HS] DOWN_CMD characteristic resolved; attrs = [%s]\n', ...
                    icm.SecretHandshake.attrStr(obj.downChar));

            % NOTE: in some MATLAB versions assigning DataAvailableFcn itself
            % triggers a (notification) subscription. Subscribe explicitly with
            % the correct type FIRST, then attach the callback.
            fprintf('[HS] subscribing to UP_CMD ...\n');
            icm.subscribeChar(obj.upChar);
            fprintf('[HS] attaching DataAvailableFcn ...\n');
            obj.upChar.DataAvailableFcn = @(src, evt) obj.notifyHandler(src, evt);
            fprintf('[HS] UP_CMD ready (subscribed + callback attached)\n');

            cleanupObj = onCleanup(@() obj.cleanup());

            % Step 2: send ICC->ICM challenge
            fprintf('[HS] writing challenge to DOWN_CMD ...\n');
            obj.sendCmd(obj.BLE_CMD_ICC_TO_ICM, challenge);
            fprintf('[HS] challenge sent (%d bytes); waiting for device (timeout %.0fs)\n', ...
                    numel(challenge), icm.Config.HANDSHAKE_TIMEOUT_S);

            t0 = tic;
            while ~obj.doneFlag && toc(t0) < icm.Config.HANDSHAKE_TIMEOUT_S
                pause(0.02);    % allow BLE notification callbacks to run
            end

            if ~obj.doneFlag
                error('icm:handshakeTimeout', ...
                      'Handshake timed out after %.0fs', icm.Config.HANDSHAKE_TIMEOUT_S);
            end
            if ~isempty(obj.errMsg)
                error('icm:handshakeError', 'Handshake failed: %s', obj.errMsg);
            end
            if isempty(obj.secretKey2)
                error('icm:handshakeError', 'Handshake ended without secret_key2');
            end

            cryption = icm.CryptionMessage(obj.secretKey1, obj.secretKey2);
            finalSeq = obj.seq;
        end
    end

    methods (Access = private)
        function cleanup(obj)
            try
                obj.upChar.DataAvailableFcn = [];
                unsubscribe(obj.upChar);
            catch
            end
        end

        function frame = buildHandshakeFrame(obj, cmd, params)
            obj.seq = mod(obj.seq, 256);
            inner = uint8([4, obj.seq, cmd]);
            if nargin >= 3 && ~isempty(params)
                params = uint8(params(:).');
                inner(1) = inner(1) + numel(params) + 4;
                inner = [inner, params];
                crc32 = icm.Crypto.crc32(inner(4:end));         % over params
                inner = [inner, typecast(uint32(crc32), 'uint8')]; % LE
            end
            checksum = mod(sum(double(inner)), 256);
            inner = [inner, uint8(checksum)];
            obj.seq = obj.seq + 1;

            frame = icm.Crypto.appendCRC16([uint8(2), inner]);   % outer 0x02 + crc16
        end

        function sendCmd(obj, cmd, params)
            if nargin < 3, params = []; end
            frame = obj.buildHandshakeFrame(cmd, params);
            write(obj.downChar, frame);
        end

        function notifyHandler(obj, src, ~)
            data = uint8(read(src, 'oldest'));
            if numel(data) < 5
                fprintf('[HS] RX short notify (%d bytes), ignoring\n', numel(data));
                return;
            end
            command = data(4);          % 0-based index 3
            message = data(5:end);
            fprintf('[HS] RX %d bytes, cmd=0x%02X\n', numel(data), command);
            try
                switch command
                    case obj.BLE_CMD_ICC_TO_ICM
                        % Step 4: ICM echoed nonce1 encrypted with secret_key1
                        returned = icm.Crypto.decryptCBC(obj.secretKey1, message(1:16));
                        if isequal(returned, obj.nonce1)
                            fprintf('[HS] step 4 OK - nonce1 verified\n');
                            obj.sendCmd(obj.BLE_CMD_ACKNOWLEDGE, ...
                                        uint8([obj.BLE_CMD_ICC_TO_ICM, 0,0,0,0,0,0,0]));
                        else
                            obj.errMsg = 'nonce1 mismatch (check device MAC byte order)';
                            obj.doneFlag = true;
                        end

                    case obj.BLE_CMD_ICM_TO_ICC
                        % Step 6: ICM sends nonce2 + secret_key2 (shared_key encrypted)
                        dec = icm.Crypto.decryptCBC(obj.sharedKey, message(1:32));
                        nonce2 = dec(1:16);
                        obj.secretKey2 = dec(17:32);
                        resp = icm.Crypto.encryptCBC(obj.secretKey2, nonce2);
                        fprintf('[HS] step 6 OK - responding ICM->ICC\n');
                        obj.sendCmd(obj.BLE_CMD_ICM_TO_ICC, resp);

                    case obj.BLE_CMD_ACKNOWLEDGE
                        % Step 8: final ACK
                        if numel(message) >= 2 && message(1) == obj.BLE_CMD_ICM_TO_ICC ...
                                && message(2) == 0
                            fprintf('[HS] step 8 - final ACK, handshake complete\n');
                            obj.doneFlag = true;
                        end
                end
            catch e
                obj.errMsg = e.message;
                obj.doneFlag = true;
            end
        end
    end

    methods (Static, Access = private)
        function s = attrStr(c)
            s = '';
            try
                s = char(strjoin(string(c.Attributes), ','));
            catch
            end
        end
    end
end
