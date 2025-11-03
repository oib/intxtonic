---
description: SSE events system status and implementation
---
# Server-Sent Events (`/notify/events`) System

## Overview
inTXTonic implements a Server-Sent Events (SSE) system at `/notify/events` for real-time notifications to connected clients. This is used for features like:
- Live translation job status updates
- Admin debug logging for i18n translations
- Real-time notifications for background processing

## Current Implementation

### Backend (`src/backend/app/api/notify.py`)
- **Endpoint**: `GET /notify/events` returns `StreamingResponse` with `media_type="text/event-stream"`
- **Keep-alive mechanism**: Sends `:ok` on connection, then `:keepalive` every 30 seconds to prevent timeouts
- **Event format**: Uses standard SSE format with `data: {json_payload}\n\n`
- **Error handling**: Gracefully handles client disconnections via `asyncio.CancelledError`

### Core Pub/Sub (`src/backend/app/core/notify.py`)
- **In-memory queue**: Uses `asyncio.Queue` for subscriber management
- **Simple pub/sub**: `subscribe()`, `unsubscribe()`, and `publish()` functions
- **Thread-safe**: Protected by `asyncio.Lock()` for concurrent access
- **Limitations**: Currently in-memory only (not suitable for multi-process deployment)

## Frontend Integration
- **EventSource**: Frontend connects using `new EventSource('/notify/events')`
- **Event types**: Supports different event types like `i18n_debug` for admin translation logging
- **Auto-reconnect**: Browsers typically handle automatic reconnection on dropped connections

## Configuration Requirements
- **Proxy configuration**: nginx should include SSE-friendly directives:
  ```nginx
  proxy_buffering off;
  proxy_cache off;
  proxy_send_timeout 1h;
  add_header X-Accel-Buffering no;
  ```

## Recent Improvements
✅ **Fixed keep-alive issues**: Added 30-second timeout with `:keepalive` comments
✅ **Improved error handling**: Proper cleanup on client disconnection
✅ **Standard SSE format**: Uses correct event-stream format for browser compatibility

## Known Limitations
- **Single-process only**: Current in-memory implementation doesn't work across multiple processes
- **No persistence**: Events are lost if no subscribers are connected
- **Memory usage**: Long-lived connections accumulate in memory

## Production Considerations
For production deployment, consider replacing the in-memory pub/sub with:
- **Redis pub/sub**: For scalable multi-process deployments
- **Postgres LISTEN/NOTIFY**: For database-integrated notifications
- **Message broker**: RabbitMQ or similar for enterprise scenarios

## Troubleshooting
- **Connection interrupts**: Check nginx proxy configuration and keep-alive settings
- **Missing events**: Verify backend service is running and not restarted frequently
- **Memory leaks**: Monitor connection count and implement connection limits if needed

## Example Usage
```javascript
// Frontend SSE connection
const eventSource = new EventSource('/notify/events');
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```
