function run_tests()
% Basic self-tests for the MATLAB port of the ICM2 ECG Recorder.
% Covers the hardware-independent logic: crypto, CRC, packet parsing, CSV.
%
% Usage:
%   >> cd matlab
%   >> tests/run_tests        (or)   run('tests/run_tests.m')

    here = fileparts(mfilename('fullpath'));
    addpath(fileparts(here));   % put the matlab/ folder (with +icm) on path

    np = 0; nf = 0;
    [np, nf] = check('AES ECB roundtrip',      @t_aes_ecb,      np, nf);
    [np, nf] = check('AES CBC roundtrip',      @t_aes_cbc,      np, nf);
    [np, nf] = check('CRC16/CCITT-FALSE',      @t_crc16,        np, nf);
    [np, nf] = check('CRC32 == zlib',          @t_crc32,        np, nf);
    [np, nf] = check('CRC8 self-consistency',  @t_crc8,         np, nf);
    [np, nf] = check('appendCRC16 layout',     @t_append_crc16, np, nf);
    [np, nf] = check('CryptionMessage roundtrip', @t_cryption,  np, nf);
    [np, nf] = check('ECG parser - plain',     @t_parser_plain, np, nf);
    [np, nf] = check('ECG parser - markers',   @t_parser_marker,np, nf);
    [np, nf] = check('CSV writer',             @t_csv,          np, nf);

    fprintf('\n%d passed, %d failed (%d total)\n', np, nf, np + nf);
    if nf > 0
        error('run_tests:failed', '%d test(s) failed', nf);
    end
end

% ---------------------------------------------------------------- helpers
function [np, nf] = check(name, fn, np, nf)
    try
        fn();
        fprintf('  PASS  %s\n', name);
        np = np + 1;
    catch e
        fprintf('  FAIL  %s : %s\n', name, e.message);
        nf = nf + 1;
    end
end

function assertTrue(cond, msg)
    if ~cond
        error('assert:false', msg);
    end
end

function pkt = makePacket(ch1, ch2, markerSlots, rrSlots, amp)
    % Build a 148-byte ECG packet (74 int16 LE).
    vals = zeros(1, 74, 'int16');
    vals(1:32)  = int16(ch1);
    vals(33:64) = int16(ch2);
    vals(65:68) = int16(markerSlots);
    vals(69:72) = int16(rrSlots);
    vals(74)    = int16(amp);
    pkt = typecast(vals, 'uint8');
end

% ---------------------------------------------------------------- tests
function t_aes_ecb()
    key = uint8(1:16);
    pt  = uint8(mod(0:15, 251));
    ct  = icm.Crypto.encryptECB(key, pt);
    rt  = icm.Crypto.decryptECB(key, ct);
    assertTrue(isequal(rt, pt), 'ECB roundtrip mismatch');
end

function t_aes_cbc()
    key = uint8(16:31);
    pt  = uint8([1:16, 17:32]);
    ct  = icm.Crypto.encryptCBC(key, pt);
    rt  = icm.Crypto.decryptCBC(key, ct);
    assertTrue(isequal(rt, pt), 'CBC roundtrip mismatch');
end

function t_crc16()
    c = icm.Crypto.crc16(uint8('123456789'));
    assertTrue(c == hex2dec('29B1'), sprintf('got 0x%04X, want 0x29B1', c));
end

function t_crc32()
    c = icm.Crypto.crc32(uint8('123456789'));
    assertTrue(c == uint32(hex2dec('CBF43926')), sprintf('got 0x%08X', c));
end

function t_crc8()
    a = icm.Crypto.crc8(uint8([1 2 3 4]));
    b = icm.Crypto.crc8(uint8([1 2 3 4]));
    assertTrue(a == b, 'crc8 not deterministic');
    assertTrue(icm.Crypto.crc8(uint8([])) == 0, 'crc8 of empty should be 0');
end

function t_append_crc16()
    data = uint8([1 2 3]);
    out  = icm.Crypto.appendCRC16(data);
    assertTrue(numel(out) == numel(data) + 2, 'appendCRC16 length wrong');
    c = icm.Crypto.crc16(data);
    assertTrue(out(end-1) == bitand(c, uint16(255)), 'low byte wrong');
    assertTrue(out(end)   == bitshift(c, -8),        'high byte wrong');
end

function t_cryption()
    cm = icm.CryptionMessage(uint8(1:16), uint8(101:116));
    pt = uint8(mod(0:39, 251));
    ct = cm.encrypt(pt);
    rt = cm.decrypt(ct);   % symmetric XOR stream (constant counter)
    assertTrue(isequal(rt, pt), 'CryptionMessage roundtrip mismatch');
    assertTrue(~isequal(ct, pt), 'ciphertext should differ from plaintext');
end

function t_parser_plain()
    ch1 = (1:32) * 10;
    ch2 = -(1:32) * 5;
    pkt = makePacket(ch1, ch2, [0 0 0 0], [0 0 0 0], 1760);
    p = icm.parseEcgPacket(pkt, 1000);
    assertTrue(isequal(p.ch1, ch1), 'ch1 mismatch');
    assertTrue(isequal(p.ch2, ch2), 'ch2 mismatch');
    assertTrue(isempty(p.markers), 'should have no markers');
    assertTrue(abs(p.amplitudeMv - 1.0) < 1e-9, 'amplitude mismatch');
    assertTrue(p.receivedMs == 1000, 'receivedMs mismatch');
end

function t_parser_marker()
    % Slot value: high byte = marker id (0x3100 = VT-ON), low byte = position 5.
    slot = hex2dec('3105');
    pkt = makePacket(zeros(1,32), zeros(1,32), [slot 0 0 0], [800 0 0 0], 1760);
    p = icm.parseEcgPacket(pkt, 0);
    assertTrue(numel(p.markers) == 1, 'expected 1 marker');
    assertTrue(p.markers(1).position == 5, 'position wrong');
    assertTrue(strcmp(p.markers(1).label, 'VT-ON'), ...
               sprintf('label wrong: %s', p.markers(1).label));
    assertTrue(isequal(p.rrIntervals, 800), 'rr wrong');
end

function t_csv()
    tmp = tempname;
    w = icm.EcgCsvWriter(tmp, 'AA:BB:CC:DD:EE:FF');
    p = w.open();
    slot = hex2dec('3105');
    pkt = makePacket((1:32), (1:32), [slot 0 0 0], [800 0 0 0], 1760);
    parsed = icm.parseEcgPacket(pkt, 0);
    w.writePacket(parsed);
    assertTrue(w.sampleCount() == 32, 'sample count wrong');
    w.close();

    T = readtable(p);
    assertTrue(height(T) == 32, 'row count wrong');
    assertTrue(any(strcmp(string(T.marker_label), 'VT-ON')), 'marker not written');
    delete(p);
    rmdir(tmp, 's');
end
