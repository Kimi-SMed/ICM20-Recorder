classdef EcgCsvWriter < handle
    % Streaming CSV writer for ICM2 ECG recordings.
    % MATLAB port of icm/ecg_writer.py.
    %
    % 8 columns, one row per sample:
    %   timestamp_ms, sample_index, channel_1, channel_2,
    %   marker_id, marker_label, rr_ms, amplitude_mv
    %
    % File: {baseDir}/ecg_{MAC}_{yyyymmdd_HHMMSS}.csv  (flushed every packet)

    properties (Access = private)
        baseDir
        macStr
        fid          = -1
        sampleIndex  = 0
        isOpenFlag   = false
        currentPathV = '';
    end

    methods
        function obj = EcgCsvWriter(baseDir, macAddress)
            obj.baseDir = baseDir;
            obj.macStr  = upper(strrep(macAddress, ':', '-'));
        end

        function p = open(obj)
            if ~exist(obj.baseDir, 'dir')
                mkdir(obj.baseDir);
            end
            ts = datestr(now, 'yyyymmdd_HHMMSS'); %#ok<DATST,TNOW1>
            fname = sprintf('ecg_%s_%s.csv', obj.macStr, ts);
            obj.currentPathV = fullfile(obj.baseDir, fname);
            obj.fid = fopen(obj.currentPathV, 'w');
            if obj.fid < 0
                error('icm:csvOpen', 'Cannot open CSV file: %s', obj.currentPathV);
            end
            fprintf(obj.fid, ['timestamp_ms,sample_index,channel_1,channel_2,' ...
                              'marker_id,marker_label,rr_ms,amplitude_mv\n']);
            obj.sampleIndex = 0;
            obj.isOpenFlag  = true;
            p = obj.currentPathV;
        end

        function writePacket(obj, packet)
            if ~obj.isOpenFlag || obj.fid < 0
                return;
            end

            % Build position -> (id,label,rr) lookup, pairing markers(i) with
            % rrIntervals(i) positionally (0 if missing) - matches the Python port.
            lookupPos = [packet.markers.position];
            ampMv = round(packet.amplitudeMv, 2);

            for i = 1:numel(packet.ch1)
                sIdx = i - 1;                              % 0-based sample position
                ts   = packet.receivedMs + sIdx * 4;       % 4 ms per sample @250Hz
                ch1  = packet.ch1(i);
                ch2  = packet.ch2(i);

                mi = find(lookupPos == sIdx, 1);
                if ~isempty(mi)
                    mId    = packet.markers(mi).id;
                    mLabel = packet.markers(mi).label;
                    if mi <= numel(packet.rrIntervals)
                        rr = packet.rrIntervals(mi);
                    else
                        rr = 0;
                    end
                    fprintf(obj.fid, '%d,%d,%d,%d,%d,%s,%d,%.2f\n', ...
                            ts, obj.sampleIndex, ch1, ch2, mId, mLabel, rr, ampMv);
                else
                    fprintf(obj.fid, '%d,%d,%d,%d,,,,\n', ...
                            ts, obj.sampleIndex, ch1, ch2);
                end
                obj.sampleIndex = obj.sampleIndex + 1;
            end
            % fprintf to a fid is unbuffered enough for our cadence; no flush API.
        end

        function close(obj)
            if ~obj.isOpenFlag
                return;
            end
            if obj.fid >= 0
                fclose(obj.fid);
            end
            obj.fid = -1;
            obj.isOpenFlag = false;
        end

        function tf = isOpen(obj)
            tf = obj.isOpenFlag;
        end

        function n = sampleCount(obj)
            n = obj.sampleIndex;
        end

        function p = currentPath(obj)
            p = obj.currentPathV;
        end
    end
end
