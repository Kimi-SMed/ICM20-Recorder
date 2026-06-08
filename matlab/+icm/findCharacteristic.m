function c = findCharacteristic(bleDev, charUuid)
    % Resolve a SCALAR characteristic object on a connected ble device by its
    % characteristic UUID alone (the Python code only tracks characteristic
    % UUIDs; MATLAB's characteristic() also needs the parent service UUID,
    % which we look up from the device's Characteristics table).
    %
    %   c = icm.findCharacteristic(bleDev, "5ac73402-...")

    target = upper(erase(string(charUuid), "-"));
    chars  = bleDev.Characteristics;
    for i = 1:height(chars)
        cu = upper(erase(string(chars.CharacteristicUUID(i)), "-"));
        if cu == target
            svc  = char(string(chars.ServiceUUID(i)));
            cuid = char(string(chars.CharacteristicUUID(i)));
            c = characteristic(bleDev, svc, cuid);
            % characteristic() can return an array if the UUID appears under
            % more than one service - subscribe()/read() need a scalar.
            if numel(c) > 1
                c = c(1);
            end
            if isempty(c)
                error('icm:charEmpty', ...
                      ['Characteristic %s matched in the table but ' ...
                       'characteristic() returned empty (service "%s" may ' ...
                       'not be fully discovered).'], char(charUuid), svc);
            end
            return;
        end
    end
    error('icm:charNotFound', ...
          'Characteristic %s not found on device', char(charUuid));
end
