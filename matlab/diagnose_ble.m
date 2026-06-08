function diagnose_ble(address)
% BLE diagnostic helper. Scans (or connects directly to ADDRESS), then prints
% the device's Characteristics table - UUIDs and Attributes (notify/indicate/
% read/write). Use this to confirm how the ECG / command characteristics must
% be subscribed if startRecording still errors.
%
% Usage:
%   diagnose_ble                 % scan for SM* devices, connect to the first
%   diagnose_ble("AA:BB:..")     % connect directly to a known address

    here = fileparts(mfilename('fullpath'));
    addpath(here);

    if nargin < 1 || isempty(address)
        fprintf('Scanning for ICM (SM*) devices...\n');
        list = blelist('Timeout', 5);
        disp(list);
        sel = list(startsWith(upper(string(list.Name)), "SM"), :);
        if isempty(sel)
            error('No SM* device found. Pass an address: diagnose_ble("AA:BB:..").');
        end
        address = char(string(sel.Address(1)));
        fprintf('Connecting to %s (%s)...\n', char(string(sel.Name(1))), address);
    else
        address = char(address);
        fprintf('Connecting to %s...\n', address);
    end

    b = ble(address);
    fprintf('\nConnected. Characteristics table:\n');
    disp(b.Characteristics);

    fprintf('\nFull Attributes per characteristic:\n');
    chars = b.Characteristics;
    for i = 1:height(chars)
        cu = char(string(chars.CharacteristicUUID(i)));
        attr = chars.Attributes(i);
        if iscell(attr), attr = attr{1}; end
        fprintf('  %-40s  Service=%-40s  Attr=%s\n', cu, ...
                char(string(chars.ServiceUUID(i))), strjoin(string(attr), ','));
    end

    clear b;   % disconnect
    fprintf('\nDone (disconnected).\n');
end
