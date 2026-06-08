classdef Config
    % ICM2 BLE ECG Recorder - configuration constants.
    % MATLAB port of icm/config.py. Access as icm.Config.<NAME>.

    properties (Constant)
        % BLE UUIDs (GEN2 reference)
        UUID_UP_CMD   = "5ac73403-3787-4203-856a-38199110db09";
        UUID_DOWN_CMD = "5ac73402-3787-4203-856a-38199110db09";
        UUID_ECG_DATA = "5ac73503-3787-4203-856a-38199110db09";

        % ECG parameters
        SAMPLE_RATE_HZ    = 250;
        PACKET_SAMPLES    = 32;     % samples per BLE notify
        PACKET_BYTES      = 148;    % 74 int16 * 2
        ROLLING_WINDOW_PTS = 2500;  % 10s * 250Hz per channel

        % Handshake
        HANDSHAKE_TIMEOUT_S = 20.0;

        % Device scan filter
        DEVICE_NAME_PREFIX = "SM";

        % Amplitude conversion (raw -> mV)
        AMPLITUDE_DIVISOR = 1760;
    end

    methods (Static)
        function d = csvDefaultDir()
            % UAC-safe default CSV directory: ~/Documents/ICM_ECG/
            home = char(java.lang.System.getProperty('user.home'));
            d = fullfile(home, 'Documents', 'ICM_ECG');
        end
    end
end
