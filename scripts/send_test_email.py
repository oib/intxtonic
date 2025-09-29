#!/usr/bin/env python3

"""Send a one-off test email using inTxTonic's SMTP settings."""

import asyncio
from datetime import datetime

from src.backend.app.core.email import send_email

DEFAULT_RECIPIENT = "test@intxtonic.net"


async def main() -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    subject = f"inTxTonic SMTP test {timestamp}"
    body = (
        "Hello from inTxTonic!\n\n"
        "This is an automated test message triggered via scripts/send_test_email.py.\n"
        "Timestamp: " + timestamp + "\n"
    )
    await send_email(subject, body, [DEFAULT_RECIPIENT])
    print(f"Sent test email to {DEFAULT_RECIPIENT} with subject '{subject}'.")


if __name__ == "__main__":
    asyncio.run(main())
