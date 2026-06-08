function pkt = parseEcgPacket(data, receivedMs)
    % Parse a 148-byte ICM2 GEN2 ECG notify payload (74 little-endian int16).
    % MATLAB port of icm/ecg_parser.py.
    %
    % Layout:
    %   [1:32]   Channel 1 (signed)        [33:64]  Channel 2 (signed)
    %   [65:68]  4 marker slots            [69:72]  4 RR intervals (ms)
    %   [74]     R-wave amplitude (raw, /1760 = mV)
    %
    % Returns a struct with fields:
    %   receivedMs, ch1, ch2, markers (struct array), rrIntervals, amplitudeMv
    % or [] if the packet is too short / malformed.

    if nargin < 2
        receivedMs = 0;
    end

    data = uint8(data(:).');
    if numel(data) < 148
        warning('icm:shortPacket', 'ECG packet too short: %d < 148, skipping', numel(data));
        pkt = [];
        return;
    end

    raw  = data(1:148);
    ecgS = double(typecast(raw, 'int16'));    % signed: samples / amplitude / RR
    ecgU = double(typecast(raw, 'uint16'));   % unsigned: marker bit masks

    pkt = struct();
    pkt.receivedMs = receivedMs;
    pkt.ch1 = ecgS(1:32);
    pkt.ch2 = ecgS(33:64);

    mm = icm.markerMap();
    markers = struct('position', {}, 'id', {}, 'label', {});
    rrIntervals = [];

    for k = 0:3
        md = ecgU(65 + k);             % ecg[64+k]
        if md == 0
            continue;
        end
        position = bitand(md, 255);            % low byte: 0-31
        markerId = bitand(md, 65280);          % high byte: 0xFF00 key
        if isKey(mm, markerId)
            label = mm(markerId);
        else
            label = sprintf('UNK_0x%04x', markerId);
        end
        markers(end+1) = struct('position', position, 'id', markerId, 'label', label); %#ok<AGROW>

        rrVal = ecgS(69 + k);          % ecg[68+k]
        if rrVal > 0
            rrIntervals(end+1) = rrVal; %#ok<AGROW>
        end
    end

    pkt.markers = markers;
    pkt.rrIntervals = rrIntervals;
    pkt.amplitudeMv = ecgS(74) / icm.Config.AMPLITUDE_DIVISOR;
end
