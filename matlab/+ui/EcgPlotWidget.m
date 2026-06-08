classdef EcgPlotWidget < handle
    % Real-time single-channel (CH1) ECG sweep-line display.
    % MATLAB port of ui/plot_widget.py, modified to:
    %   - show ONLY channel 1 (CH2 display removed)
    %   - divide CH1 raw values by AMPLITUDE_DIVISOR (1760) before plotting
    %     (Y axis in mV)
    %   - drop "S" markers from the display
    %   - support a switchable X-axis time window (5 / 10 / 20 / 40 s)
    %
    % Marker labels are removed as the sweep cursor overwrites their location,
    % so stale markers (e.g. "AS") no longer linger on screen.
    %
    % appendPacket() must be called from the main thread (BLE notify callback).

    properties (Access = private)
        ax
        line1
        cur1
        bufCh1
        xSec
        ptr        = 0;
        eraseWidth
        divisor
        markerTexts = gobjects(0);
        markerPos   = [];          % buffer index (1..n) for each marker text
        windowSec
        windowOptions = [5 10 20 40];
    end

    methods
        function obj = EcgPlotWidget(parent)
            fs = icm.Config.SAMPLE_RATE_HZ;
            obj.divisor    = icm.Config.AMPLITUDE_DIVISOR;   % 1760: raw -> mV
            obj.eraseWidth = max(1, round(fs * 0.15));
            obj.windowSec  = 10;

            n = round(obj.windowSec * fs);
            obj.bufCh1 = nan(1, n);
            obj.xSec   = (0:n-1) / fs;

            panel = uigridlayout(parent, [1 1], 'Padding', 2);
            obj.ax = uiaxes(panel);
            obj.configAxes(obj.ax, 'CH1 (mV)');

            obj.line1 = plot(obj.ax, obj.xSec, obj.bufCh1, 'Color', [0 0.7 0], 'LineWidth', 1);
            obj.cur1  = xline(obj.ax, 0, '--', 'Color', [0.5 0.5 0.5]);
            obj.ax.XLim = [0 obj.windowSec];
        end

        function appendPacket(obj, packet)
            n = numel(obj.bufCh1);
            ch1 = packet.ch1 / obj.divisor;   % scale raw -> mV before plotting
            m = numel(ch1);
            oldPtr = obj.ptr;

            for i = 1:m
                p = mod(obj.ptr, n) + 1;
                obj.bufCh1(p) = ch1(i);
                obj.ptr = obj.ptr + 1;
            end

            % Erase a short gap ahead of the cursor.
            for g = 0:obj.eraseWidth-1
                p = mod(obj.ptr + g, n) + 1;
                obj.bufCh1(p) = NaN;
            end

            % Remove any markers in the region just (over)written so old labels
            % disappear as the sweep passes over them.
            touched = mod(oldPtr:(oldPtr + m + obj.eraseWidth - 1), n) + 1;
            obj.removeMarkersAt(touched);

            obj.line1.YData = obj.bufCh1;
            obj.cur1.Value  = obj.xSec(mod(obj.ptr, n) + 1);

            obj.drawMarkers(packet, n);
            drawnow limitrate;
        end

        function sec = cycleWindow(obj)
            % Advance to the next window size (5 -> 10 -> 20 -> 40 -> 5 ...).
            idx = find(obj.windowOptions == obj.windowSec, 1);
            if isempty(idx), idx = 0; end
            nextIdx = mod(idx, numel(obj.windowOptions)) + 1;
            obj.setWindow(obj.windowOptions(nextIdx));
            sec = obj.windowSec;
        end

        function clear(obj)
            obj.bufCh1(:) = NaN;
            obj.ptr = 0;
            obj.line1.YData = obj.bufCh1;
            obj.clearMarkers();
        end
    end

    methods (Access = private)
        function setWindow(obj, sec)
            fs = icm.Config.SAMPLE_RATE_HZ;
            obj.windowSec = sec;
            n = round(sec * fs);
            obj.bufCh1 = nan(1, n);
            obj.xSec   = (0:n-1) / fs;
            obj.ptr    = 0;
            obj.clearMarkers();
            obj.line1.XData = obj.xSec;
            obj.line1.YData = obj.bufCh1;
            obj.cur1.Value  = 0;
            obj.ax.XLim = [0 sec];
        end

        function configAxes(~, ax, ylab)
            ax.Color = 'k';
            ax.XColor = [0.6 0.6 0.6];
            ax.YColor = [0.6 0.6 0.6];
            ax.YLabel.String = ylab;
            ax.Toolbar.Visible = 'off';
            disableDefaultInteractivity(ax);
            hold(ax, 'on');
        end

        function drawMarkers(obj, packet, n)
            for k = 1:numel(packet.markers)
                if strcmp(packet.markers(k).label, 'S')
                    continue;   % "S" markers are not displayed
                end
                pos = packet.markers(k).position;          % 0-31 within packet
                gIdx = obj.ptr - numel(packet.ch1) + pos;  % global sample index
                bidx = mod(gIdx, n) + 1;
                yv = obj.bufCh1(bidx);
                if isnan(yv), yv = 0; end
                t = text(obj.ax, obj.xSec(bidx), yv, packet.markers(k).label, ...
                         'Color', [1 0.6 0], 'FontSize', 8, ...
                         'HorizontalAlignment', 'center');
                obj.markerTexts(end+1) = t;     %#ok<AGROW>
                obj.markerPos(end+1)   = bidx;  %#ok<AGROW>
            end
        end

        function removeMarkersAt(obj, touched)
            if isempty(obj.markerTexts)
                return;
            end
            keep = true(1, numel(obj.markerTexts));
            for j = 1:numel(obj.markerTexts)
                stale = ~isgraphics(obj.markerTexts(j)) || ismember(obj.markerPos(j), touched);
                if stale
                    if isgraphics(obj.markerTexts(j))
                        delete(obj.markerTexts(j));
                    end
                    keep(j) = false;
                end
            end
            obj.markerTexts = obj.markerTexts(keep);
            obj.markerPos   = obj.markerPos(keep);
        end

        function clearMarkers(obj)
            delete(obj.markerTexts(isgraphics(obj.markerTexts)));
            obj.markerTexts = gobjects(0);
            obj.markerPos   = [];
        end
    end
end
