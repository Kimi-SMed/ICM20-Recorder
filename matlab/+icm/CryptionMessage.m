classdef CryptionMessage < handle
    % AES-CTR style stream cipher used for post-handshake commands.
    % MATLAB port of icm/crypto.py CryptionMessage.
    %
    % NOTE: matching the reference firmware, the send/receive counters are
    % NEVER incremented (the increment lines are commented out in the original),
    % so the keystream block is constant for the session. Kept faithful here.

    properties
        nonce      % uint8 row, 16 bytes (= secret_key1)
        key        % uint8 row, 16 bytes (= secret_key2)
        sendCTR    = 0
        receiveCTR = 0
    end

    methods
        function obj = CryptionMessage(nonce, key)
            obj.nonce = uint8(nonce(:).');
            obj.key   = uint8(key(:).');
        end

        function resetCounter(obj)
            obj.sendCTR = 0;
            obj.receiveCTR = 0;
        end

        function buf = getNonceCtrBuffer(obj, isSending)
            buf = obj.nonce;
            if isSending
                ctr = obj.sendCTR;
            else
                ctr = obj.receiveCTR;
            end
            buf(1:4) = typecast(uint32(ctr), 'uint8');   % little-endian
            buf = icm.Crypto.encryptECB(obj.key, buf);
        end

        function out = encrypt(obj, input)
            out = obj.process(input, true);
        end

        function out = decrypt(obj, input)
            out = obj.process(input, false);
        end
    end

    methods (Access = private)
        function out = process(obj, input, isSending)
            input = uint8(input(:).');
            n = numel(input);
            out = zeros(1, n, 'uint8');
            idx = 1;
            left = n;
            while left >= 16
                ks = obj.getNonceCtrBuffer(isSending);
                out(idx:idx+15) = bitxor(input(idx:idx+15), ks(1:16));
                idx = idx + 16;
                left = left - 16;
            end
            if left > 0
                ks = obj.getNonceCtrBuffer(isSending);
                out(idx:idx+left-1) = bitxor(input(idx:idx+left-1), ks(1:left));
            end
        end
    end
end
