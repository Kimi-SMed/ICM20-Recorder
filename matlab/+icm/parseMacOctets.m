function octets = parseMacOctets(mac)
    % Extract the 6 MAC-address octets from a device address string,
    % regardless of separator style. Accepts "AA:BB:CC:DD:EE:FF",
    % "AA-BB-CC-...", "aabbccddeeff", etc. Returns a 1x6 uint8.
    %
    %   octets = icm.parseMacOctets("AA:BB:CC:DD:EE:FF")

    s   = char(string(mac));
    hex = regexprep(s, '[^0-9A-Fa-f]', '');   % keep hex digits only
    if numel(hex) < 12
        error('icm:badMac', ...
              ['Cannot derive a 6-byte MAC from device address "%s". The ' ...
               'shared-key handshake needs the device MAC address (12 hex ' ...
               'digits). MATLAB returned an address without enough hex ' ...
               'digits - try connecting by the device name instead.'], s);
    end
    hex = hex(1:12);
    octets = zeros(1, 6, 'uint8');
    for k = 1:6
        octets(k) = uint8(hex2dec(hex(2*k-1:2*k)));
    end
end
