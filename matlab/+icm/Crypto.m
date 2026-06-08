classdef Crypto
    % AES-128 CBC/ECB + CRC16/CRC8/CRC32 primitives for the ICM2 BLE protocol.
    % MATLAB port of icm/crypto.py. AES is provided by the JVM bundled with
    % MATLAB (javax.crypto), CRC32 by java.util.zip.CRC32 (== zlib.crc32).
    %
    % All data arguments are row vectors of byte values (0-255). All results are
    % returned as uint8 row vectors. DO NOT change the byte layout - the device
    % protocol depends on exact behaviour.

    methods (Static)
        % ---- AES ------------------------------------------------------
        function ct = encryptCBC(key, plaintext)
            ct = icm.Crypto.aesRun(key, plaintext, 'AES/CBC/NoPadding', true);
        end

        function pt = decryptCBC(key, ciphertext)
            pt = icm.Crypto.aesRun(key, ciphertext, 'AES/CBC/NoPadding', false);
        end

        function ct = encryptECB(key, plaintext)
            ct = icm.Crypto.aesRun(key, plaintext, 'AES/ECB/NoPadding', true);
        end

        function pt = decryptECB(key, ciphertext)
            pt = icm.Crypto.aesRun(key, ciphertext, 'AES/ECB/NoPadding', false);
        end

        function out = aesRun(key, data, transform, doEncrypt)
            % Run a one-shot AES operation through the JVM. CBC uses a 16-byte
            % zero IV (matching the Python reference).
            keyBytes  = typecast(uint8(key(:).'),  'int8');
            dataBytes = typecast(uint8(data(:).'), 'int8');

            cipher = javax.crypto.Cipher.getInstance(transform);
            ks = javax.crypto.spec.SecretKeySpec(keyBytes, 'AES');

            if doEncrypt
                mode = javax.crypto.Cipher.ENCRYPT_MODE;
            else
                mode = javax.crypto.Cipher.DECRYPT_MODE;
            end

            if contains(string(transform), "CBC")
                iv = javax.crypto.spec.IvParameterSpec(zeros(16, 1, 'int8'));
                cipher.init(mode, ks, iv);
            else
                cipher.init(mode, ks);
            end

            res = cipher.doFinal(dataBytes);          % Java byte[] -> int8
            out = typecast(int8(res(:).'), 'uint8');
        end

        % ---- CRC ------------------------------------------------------
        function crc = crc16(data)
            % CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflect, xorout 0.
            data = uint16(data(:).');
            crc  = uint16(65535);
            poly = uint16(4129);                      % 0x1021
            for k = 1:numel(data)
                crc = bitxor(crc, bitshift(data(k), 8));
                for b = 1:8
                    if bitand(crc, uint16(32768))     % 0x8000
                        crc = bitand(bitxor(bitshift(crc, 1), poly), uint16(65535));
                    else
                        crc = bitand(bitshift(crc, 1), uint16(65535));
                    end
                end
            end
        end

        function out = appendCRC16(data)
            % Return data with little-endian CRC16 appended.
            data = uint8(data(:).');
            c = icm.Crypto.crc16(data);
            lo = uint8(bitand(c, uint16(255)));
            hi = uint8(bitshift(c, -8));
            out = [data, lo, hi];
        end

        function v = crc32(data)
            % zlib-compatible CRC32 via the JVM.
            c = java.util.zip.CRC32();
            c.update(typecast(uint8(data(:).'), 'int8'));
            v = uint32(c.getValue());
        end

        function r = crc8(data)
            % Table-driven CRC8 matching icm_control.crc8().
            persistent tab
            if isempty(tab)
                tab = uint8([ ...
                    0,49,98,83,196,245,166,151,185,136,219,234,125,76,31,46, ...
                    67,114,33,16,135,182,229,212,250,203,152,169,62,15,92,109, ...
                    134,183,228,213,66,115,32,17,63,14,93,108,251,202,153,168, ...
                    197,244,167,150,1,48,99,82,124,77,30,47,184,137,218,235, ...
                    61,12,95,110,249,200,155,170,132,181,230,215,64,113,34,19, ...
                    126,79,28,45,186,139,216,233,199,246,165,148,3,50,97,80, ...
                    187,138,217,232,127,78,29,44,2,51,96,81,198,247,164,149, ...
                    248,201,154,171,60,13,94,111,65,112,35,18,133,180,231,214, ...
                    122,75,24,41,190,143,220,237,195,242,161,144,7,54,101,84, ...
                    57,8,91,106,253,204,159,174,128,177,226,211,68,117,38,23, ...
                    252,205,158,175,56,9,90,107,69,116,39,22,129,176,227,210, ...
                    191,142,221,236,123,74,25,40,6,55,100,85,194,243,160,145, ...
                    71,118,37,20,131,178,225,208,254,207,156,173,58,11,88,105, ...
                    4,53,102,87,192,241,162,147,189,140,223,238,121,72,27,42, ...
                    193,240,163,146,5,52,103,86,120,73,26,43,188,141,222,239, ...
                    130,179,224,209,70,119,36,21,59,10,89,104,255,206,157,172]);
            end
            data = uint8(data(:).');
            r = uint8(0);
            for i = 1:numel(data)
                r = tab(bitand(bitxor(uint16(r), uint16(data(i))), 255) + 1);
            end
        end
    end
end
