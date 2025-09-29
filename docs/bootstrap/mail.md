# Email Handling in the Application

## Overview
The application uses Python's built-in `smtplib` and `email` modules to handle email functionality. Currently, the implementation is minimal and primarily used for testing purposes.

## Current Implementation

### Test Scripts
There are two test scripts available for email functionality:

1. `/tests/test_mail.py`

Both scripts contain the same basic email sending functionality:

```python
import smtplib
from email.message import EmailMessage

# Create email message
msg = EmailMessage()
msg["From"] = "test@keisanki.net"
msg["To"] = "oib@bubuit.net"
msg["Subject"] = "Test"
msg.set_content("Hello world")

# Send email using local SMTP server
with smtplib.SMTP("localhost") as smtp:
    smtp.send_message(msg)
```

## Configuration

### SMTP Server
- The application is configured to use a local SMTP server running on `localhost`
- No authentication is currently configured for the SMTP connection
- The connection is not using TLS/SSL

### Email Settings
- **From Address**: `test@keisanki.net` (hardcoded in test scripts)
- **To Address**: `oib@bubuit.net` (hardcoded in test scripts)

## Integration Points

Currently, email functionality is not integrated into the main application. The existing implementation is limited to test scripts and would need to be properly integrated with the application's configuration system for production use.

## Future Improvements

1. Move email configuration to environment variables or a configuration file
2. Add support for SMTP authentication
3. Implement TLS/SSL for secure email transmission
4. Create email templates for different types of notifications
5. Add error handling and retry logic for failed email deliveries
6. Integrate with the application's logging system
7. Implement email confirmation flow for new accounts (see below)

## Email Confirmation Flow

### Goals
- Ensure new users verify ownership of the email address used during registration.
- Prevent spam accounts by requiring confirmation before unlocking posting features.

### Backend Steps
1. **Extend schema**: Add `email_confirmed_at TIMESTAMPTZ` and optional `email_confirmation_token` to `app.accounts`.
2. **Generate token**: On registration, create a secure random token (e.g., 32-byte URL-safe) and store hash + expiry.
3. **Send confirmation email**: Queue email with link `https://langsum.example/confirm?token=...`.
4. **Verification endpoint**: Add `POST /auth/confirm-email` to validate token, mark `email_confirmed_at`, clear token.
5. **Resend flow**: Provide `POST /auth/resend-confirmation` with throttling to issue a new token if expired.
6. **Guard actions**: Update middleware to reject posting/voting until `email_confirmed_at` is set.

### Frontend Steps
1. **Registration success screen**: Inform users that a confirmation email was sent and provide a resend button.
2. **Confirmation landing page**: Display success or error messages based on token validation outcome.
3. **UI indicators**: In settings/profile, show confirmation status and allow resending if pending.
4. **Accessibility**: Ensure links and buttons are reachable, provide copy-able URL for manual confirmation.

### Email Template Guidelines
- Subject: "Confirm your LangSum email".
- Body: Include greeting, confirmation link, and note about expiry (e.g., 24h).
- Provide fallback instructions if link expires.
- Add footer with support contact and unsubscribe/legal requirements where applicable.

### Security & Ops Notes
- Store hashed tokens (e.g., SHA256) instead of raw values.
- Rate-limit confirmation attempts and resend requests to prevent abuse.
- Log confirmation events for audit trail.
- Consider background cleanup job to purge expired tokens.

## Testing

To test the email functionality, you can run either of the test scripts:

```bash
# or
python3 tests/test_mail.py
```

Make sure you have a local SMTP server running on `localhost` before testing.
