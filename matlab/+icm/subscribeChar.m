function subscribeChar(c)
    % Robustly enable notifications/indications on a BLE characteristic.
    % Chooses the subscription type from the characteristic's Attributes
    % (Notify vs Indicate), and retries once after a short pause in case the
    % link is still settling.
    %
    %   icm.subscribeChar(c)

    if isempty(c)
        error('icm:subscribe', 'Cannot subscribe: characteristic is empty.');
    end
    if numel(c) > 1
        c = c(1);
    end

    % Inspect supported attributes to pick the right subscription type.
    attrs = "";
    try
        attrs = lower(string(c.Attributes));
    catch
    end
    types = string([]);
    if any(contains(attrs, "notif"))
        types(end+1) = "notification";
    end
    if any(contains(attrs, "indicat"))
        types(end+1) = "indication";
    end
    if isempty(types)
        types = ["notification", "indication"];   % unknown - try both
    end

    fprintf('[HS] subscribe: characteristic attributes = [%s], trying %s\n', ...
            strjoin(attrs, ','), strjoin(types, ','));

    lastErr = [];
    for attempt = 1:2
        for i = 1:numel(types)
            try
                subscribe(c, types(i));
                fprintf('[HS] subscribe OK (%s)\n', types(i));
                return;
            catch e
                lastErr = e;
            end
        end
        pause(0.3);   % brief settle, then retry once
    end

    error('icm:subscribe', ...
          ['Failed to subscribe to characteristic (tried %s). Last error: %s ' ...
           'If the device dropped the link, restart MATLAB to clear stale BLE ' ...
           'handles and move the programmer closer to the device.'], ...
          strjoin(types, ','), lastErr.message);
end
