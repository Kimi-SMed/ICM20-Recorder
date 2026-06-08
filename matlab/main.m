function main()
% ICM2 BLE ECG Recorder - application entry point (MATLAB port).
%
% Usage:
%   >> cd matlab
%   >> main
%
% Requirements:
%   - MATLAB R2022a or later
%   - Bluetooth Toolbox (for real device scan/connect)
%   - A Bluetooth LE adapter + a real ICM2 GEN2 device for full operation
%
% The window owns the BLE client, plot, CSV writer and the remote-control
% TCP server. Close the window to disconnect and clean up.

    % Ensure the +icm / +ui packages on this folder are visible.
    here = fileparts(mfilename('fullpath'));
    addpath(here);

    ui.MainWindow();
end
