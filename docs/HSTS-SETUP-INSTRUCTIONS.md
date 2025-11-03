# HSTS Setup Instructions

## What HSTS Does
- Forces browsers to use HTTPS for your domain from the very first request
- Eliminates Firefox HTTPS-Only Mode upgrade messages
- Prevents mixed content attacks
- Includes your domain in browser preload lists

## Updated Configuration
The new HSTS header has been added to your Nginx configuration:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

## How to Apply

### 1. Backup Current Configuration
```bash
sudo cp /etc/nginx/sites-available/intxtonic.net /etc/nginx/sites-available/intxtonic.net.backup
```

### 2. Update Configuration
```bash
sudo nano /etc/nginx/sites-available/intxtonic.net
```

Add this line inside the first `server {` block (after the `server_name` line):
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### 3. Test Configuration
```bash
sudo nginx -t
```

### 4. Reload Nginx
```bash
sudo systemctl reload nginx
```

## HSTS Header Breakdown
- `max-age=31536000` - Force HTTPS for 1 year (in seconds)
- `includeSubDomains` - Apply to all subdomains
- `preload` - Submit to browser preload lists
- `always` - Include on all responses (including errors)

## Security Benefits
- Prevents protocol downgrade attacks
- Eliminates mixed content warnings
- Improves SEO (HTTPS is a ranking factor)
- Protects user data in transit

## Important Notes
⚠️ **Once enabled, this cannot be easily disabled for 1 year**
- Browsers will remember this setting
- Test thoroughly before deploying to production
- Ensure all your resources are available over HTTPS

## Verification
After applying, you can verify HSTS is working:
```bash
curl -I https://intxtonic.net
```

Look for this header in the response:
```
strict-transport-security: max-age=31536000; includeSubDomains; preload
```

## Expected Results
- Firefox HTTPS-Only Mode messages will disappear
- All requests will use HTTPS automatically
- Better security for all users
- Improved browser security warnings
