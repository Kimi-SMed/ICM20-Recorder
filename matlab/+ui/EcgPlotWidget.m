classdef EcgPlotWidget < handle
    % Real-time single-channel (CH1) ECG sweep-line display.
    % MATLAB port of ui/plot_widget.py, modified to:
    %   - show ONLY channel 1 (CH2 display removed)
    %   - divide CH1 raw values by AMPLITUDE_DIVISOR (1760) before plotting,
    %     so the Y axis is in mV.
    %
    % Fixed-length circular buffer (NaN = no data). A write cursor advances
    % left->right and wraps; a short NaN gap ahead of the cursor erases stale
    % data to give the classic sweeping-monitor look.
    %
    % appendPacket() must be called from the main thread (it is, via the BLE
    % notification callback).

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
    end

    methods
        function obj = EcgPlotWidget(parent)
            n  = icm.Config.ROLLING_WINDOW_PTS;
            fs = icm.Config.SAMPLE_RATE_HZ;
            obj.divisor    = icm.Config.AMPLITUDE_DIVISOR;   % 1760: raw -> mV
            obj.bufCh1     = nan(1, n);
            obj.xSec       = (0:n-1) / fs;
            obj.eraseWidth = max(1, round(fs * 0.15));

            panel = uigridlayout(parent, [1 1], 'Padding', 2);
            obj.ax = uiaxes(panel);
            obj.configAxes(obj.ax, 'CH1 (mV)');

            obj.line1 = plot(obj.ax, obj.xSec, obj.bufCh1, 'Color', [0 0.7 0], 'LineWidth', 1);
            obj.cur1  = xline(obj.ax, 0, '--', 'Color', [0.5 0.5 0.5]);
        end

        function appendPacket(obj, packet)
            n = numel(obj.bufCh1);
            ch1 = packet.ch1 / obj.divisor;   % scale raw -> mV before plotting
            m = numel(ch1);

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

            obj.line1.YData = obj.bufCh1;
            obj.cur1.Value  = obj.xSec(mod(obj.ptr, n) + 1);

            obj.drawMarkers(packet, n);
            drawnow limitrate;
        end

        function clear(obj)
            obj.bufCh1(:) = NaN;
            obj.ptr = 0;
            obj.line1.YData = obj.bufCh1;
            delete(obj.markerTexts(isgraphics(obj.markerTexts)));
            obj.markerTexts = gobjects(0);
        end
    end

    methods (Access = private)
        function configAxes(~, ax, ylab)
            ax.Color = 'k';
            ax.XColor = [0.6 0.6 0.6];
            ax.YColor = [0.6 0.6 0.6];
            ax.XLim = [0 10];
            ax.YLabel.String = ylab;
            ax.Toolbar.Visible = 'off';
            disableDefaultInteractivity(ax);
            hold(ax, 'on');
        end

        function drawMarkers(obj, packet, n)
            % Draw the new markers on CH1; keep only the most recent ones.
            for k = 1:numel(packet.markers)
                if strcmp(packet.markers(k).label, 'S')
                    continue;   % "S" markers are not displayed
                end
                pos = packet.markers(k).position;          % 0-31 within packet
                gIdx = obj.ptr - numel(packet.ch1) + pos;  % global sample index
                xpos = obj.xSec(mod(gIdx, n) + 1);
                yv = obj.bufCh1(mod(gIdx, n) + 1);
                if isnan(yv), yv = 0; end
                t = text(obj.ax, xpos, yv, packet.markers(k).label, ...
                         'Color', [1 0.6 0], 'FontSize', 8, ...
                         'HorizontalAlignment', 'center');
                obj.markerTexts(end+1) = t; %#ok<AGROW>
            end
            obj.markerTexts = obj.markerTexts(isgraphics(obj.markerTexts));
            if numel(obj.markerTexts) > 40
                delete(obj.markerTexts(1:end-40));
                obj.markerTexts = obj.markerTexts(isgraphics(obj.markerTexts));
            end
        end
    end
end
