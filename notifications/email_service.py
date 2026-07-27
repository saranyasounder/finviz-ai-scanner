from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from config.settings import EmailSettings


class EmailService:
    """Sends the HTML report by email. Should only be invoked when there are
    meaningful changes to report - the caller decides that, not this class."""

    def __init__(self, settings: EmailSettings):
        self.settings = settings

    def send(self, subject: str, html_body: str) -> bool:
        if not self.settings.to_addrs:
            logger.warning("No EMAIL_TO recipients configured, skipping email send.")
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = f"{self.settings.subject_prefix} {subject}"
        message["From"] = self.settings.from_addr
        message["To"] = ", ".join(self.settings.to_addrs)
        message.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as server:
                server.starttls()
                server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.sendmail(
                    self.settings.from_addr, self.settings.to_addrs, message.as_string()
                )
            logger.success(f"Email sent to {len(self.settings.to_addrs)} recipient(s).")
            return True
        except Exception as exc:
            logger.error(f"Failed to send email: {exc}")
            return False
