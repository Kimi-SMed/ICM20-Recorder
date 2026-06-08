classdef ReviewPlotWidget < handle
    % Post-recording CH1 review plot in its OWN separate window.
    % MATLAB port of ui/review_plot_widget.py.
    %
    % Loads a recorded CSV and shows the full CH1 waveform (X = seconds from
    % recording start, Y = mV). Mouse drag pans; the X/Y zoom buttons zoom
    % +/-10% about the centre. Closing the window just hides it so it can be
    % reopened from the main window's "Review" button.

    properties (Constant)
        ZOOM_FACTOR = 0.10;
    end

    properties (Access = private)
        fig
        ax
        infoLabel
        csvPath = '';
    end

    methods
        function obj = ReviewPlotWidget()
            obj.fig = uifigure('Name', 'ECG Review', ...
                'Position', [200 200 920 440], 'Visible', 'off');
            obj.fig.CloseRequestFcn = @(~,~) obj.hide();

            g = uigridlayout(obj.fig, [2 1], ...
                'RowHeight', {34, '1x'}, 'Padding', 6, 'RowSpacing', 6);

            bar = uigridlayout(g, [1 7], ...
                'ColumnWidth', {90, 40, 40, 40, 40, 70, '1x'}, ...
                'Padding', 0, 'ColumnSpacing', 4);

            uibutton(bar, 'Text', 'Load CSV...', 'ButtonPushedFcn', @(~,~) obj.loadDialog());
            uibutton(bar, 'Text', 'X +', 'ButtonPushedFcn', @(~,~) obj.zoomAxis('x', -1));
            uibutton(bar, 'Text', 'X -', 'ButtonPushedFcn', @(~,~) obj.zoomAxis('x', +1));
            uibutton(bar, 'Text', 'Y +', 'ButtonPushedFcn', @(~,~) obj.zoomAxis('y', -1));
            uibutton(bar, 'Text', 'Y -', 'ButtonPushedFcn', @(~,~) obj.zoomAxis('y', +1));
            uibutton(bar, 'Text', 'Reset', 'ButtonPushedFcn', @(~,~) obj.resetView());
            obj.infoLabel = uilabel(bar, 'Text', 'No file loaded', ...
                'HorizontalAlignment', 'right');

            obj.ax = uiaxes(g);
            title(obj.ax, 'Review (CH1)');
            xlabel(obj.ax, 'Time (s)');
            ylabel(obj.ax, 'CH1 (mV)');
            obj.ax.Toolbar.Visible = 'on';
        end

        function show(obj)
            obj.fig.Visible = 'on';
            try
                figure(obj.fig);   % bring to front
            catch
            end
        end

        function hide(obj)
            if ~isempty(obj.fig) && isvalid(obj.fig)
                obj.fig.Visible = 'off';
            end
        end

        function loadCsv(obj, csvPath)
            csvPath = char(csvPath);
            if ~isfile(csvPath)
                obj.infoLabel.Text = 'File not found';
                return;
            end
            obj.csvPath = csvPath;
            try
                T = readtable(csvPath);
            catch e
                obj.infoLabel.Text = sprintf('Read error: %s', e.message);
                obj.show();
                return;
            end
            if ~all(ismember({'timestamp_ms', 'channel_1'}, T.Properties.VariableNames))
                obj.infoLabel.Text = 'Unexpected CSV columns';
                obj.show();
                return;
            end
            t0 = T.timestamp_ms(1);
            tsec = double(T.timestamp_ms - t0) / 1000;
            ch1mv = double(T.channel_1) / icm.Config.AMPLITUDE_DIVISOR;

            cla(obj.ax);
            plot(obj.ax, tsec, ch1mv, 'Color', [0 0.3 0.8]);
            hold(obj.ax, 'on');
            xline(obj.ax, 0, '--', 'Color', [0.5 0.5 0.5]);
            hold(obj.ax, 'off');
            axis(obj.ax, 'tight');
            [~, name, ext] = fileparts(csvPath);
            obj.infoLabel.Text = sprintf('%s%s  (%d samples)', name, ext, height(T));
            obj.show();
        end

        function delete(obj)
            if ~isempty(obj.fig) && isvalid(obj.fig)
                delete(obj.fig);
            end
        end
    end

    methods (Access = private)
        function loadDialog(obj)
            startDir = icm.Config.csvDefaultDir();
            if ~isfolder(startDir), startDir = pwd; end
            [f, p] = uigetfile(fullfile(startDir, '*.csv'), 'Select an ECG CSV recording');
            if isequal(f, 0), return; end
            obj.loadCsv(fullfile(p, f));
        end

        function zoomAxis(obj, which, dir)
            % dir = -1 zoom in, +1 zoom out (+/-10% of half-range about centre).
            if which == 'x'
                lim = obj.ax.XLim;
            else
                lim = obj.ax.YLim;
            end
            c = mean(lim);
            half = (lim(2) - lim(1)) / 2;
            half = half * (1 + dir * obj.ZOOM_FACTOR);
            newLim = [c - half, c + half];
            if which == 'x'
                obj.ax.XLim = newLim;
            else
                obj.ax.YLim = newLim;
            end
        end

        function resetView(obj)
            axis(obj.ax, 'tight');
        end
    end
end
