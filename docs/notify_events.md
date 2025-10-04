---
description: notify events SSE issue investigation
---
# `/notify/events` SSE Connection Issue

- **Summary**
  The admin interfaces (`/admin` and `/admin/i18n`) still report "The connection to https://intxtonic.net/notify/events was interrupted while the page was loading". The Firefox HAR trace captured on 2025-10-03 shows standard asset loads but no long-lived SSE stream entry.

- **Backend state**
  `src/backend/app/api/notify.py` was updated to emit `:ok` immediately and `:keepalive` comments every 30s inside `_event_stream()`. If the Gunicorn process has not been restarted since this change, workers may still be running the previous implementation without keep-alives.

- **Proxy configuration**
  `/etc/nginx/sites-available/intxtonic.net` includes the recommended SSE directives (`proxy_buffering off`, `proxy_cache off`, `proxy_send_timeout 1h`, `add_header X-Accel-Buffering no`). nginx still returns 499 in prior logs, indicating the client closes the socket early because it stops receiving data.

- **Observed symptoms**
  - Firefox console logs the interruption on both admin pages immediately after load.
  - Network panel shows no sustained pending request for `/notify/events`; the stream closes before any payload is delivered.
  - nginx access log entries for `/notify/events` previously showed early disconnects (HTTP 499) despite Gunicorn responding with 200.

- **Outstanding checks**
  1. Restart the backend service: `systemctl --user restart intxtonic.service`, then tail `journalctl --user -fu intxtonic.service` to confirm the new generator is active and no errors are raised when clients connect.
  2. Reload nginx after verifying the config: `sudo nginx -t && sudo systemctl reload nginx`.
  3. Reproduce with Firefox DevTools open, confirm `/notify/events` stays pending, and inspect the response pane for `:ok`/`:keepalive` comments.
  4. Monitor `/var/log/nginx/intxtonic_access.log` to ensure the SSE connection remains open (no immediate 499).
  5. If the stream still interrupts, capture simultaneous browser network details, nginx logs, and Gunicorn logs to determine whether upstream closes the connection or if a proxy timeout persists.
