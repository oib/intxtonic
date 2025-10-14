import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["From"] = "test@keisanki.net"
msg["To"] = "oib@bubuit.net"
msg["Subject"] = "Test"
msg.set_content("Hello world")

with smtplib.SMTP("localhost") as smtp:
    smtp.send_message(msg)
