"""SMTP 发信。"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr


def send_mail(host: str, port: int, username: str, password: str,
              from_addr: str, to_addrs: list[str] | str,
              subject: str, body: str, html: bool = False,
              starttls: bool = True, from_name: str = "") -> None:
    if isinstance(to_addrs, str):
        to_addrs = [to_addrs]

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    subtype = "html" if html else "plain"
    msg.attach(MIMEText(body, subtype, "utf-8"))

    if starttls:
        server = smtplib.SMTP(host, port, timeout=30)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    try:
        server.login(username, password)
        server.sendmail(from_addr, to_addrs, msg.as_string())
    finally:
        server.quit()
