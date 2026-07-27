from unittest.mock import MagicMock, patch

from config.settings import EmailSettings
from notifications.email_service import EmailService


def _settings(**overrides) -> EmailSettings:
    base = dict(
        smtp_host="smtp.example.invalid",
        smtp_port=587,
        smtp_username="user@example.invalid",
        smtp_password="password",
        from_addr="user@example.invalid",
        to_addrs=["recipient@example.invalid"],
        subject_prefix="[Test]",
        smtp_timeout_seconds=15,
    )
    base.update(overrides)
    return EmailSettings(**base)


def test_no_recipients_skips_send_and_returns_false():
    service = EmailService(_settings(to_addrs=[]))

    with patch("notifications.email_service.smtplib.SMTP") as smtp_cls:
        result = service.send(subject="Test", html_body="<p>hi</p>")

    assert result is False
    smtp_cls.assert_not_called()


def test_successful_send_returns_true_and_uses_configured_timeout():
    service = EmailService(_settings())
    mock_server = MagicMock()

    with patch("notifications.email_service.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = mock_server

        result = service.send(subject="Alert", html_body="<p>hi</p>")

    assert result is True
    smtp_cls.assert_called_once_with("smtp.example.invalid", 587, timeout=15)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.invalid", "password")
    mock_server.sendmail.assert_called_once()


def test_send_failure_is_caught_and_returns_false():
    service = EmailService(_settings())

    with patch("notifications.email_service.smtplib.SMTP") as smtp_cls:
        smtp_cls.side_effect = OSError("connection refused")

        result = service.send(subject="Alert", html_body="<p>hi</p>")

    assert result is False


def test_subject_prefix_is_applied():
    service = EmailService(_settings())
    mock_server = MagicMock()

    with patch("notifications.email_service.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = mock_server
        service.send(subject="3 changes detected", html_body="<p>hi</p>")

    sent_message = mock_server.sendmail.call_args.args[2]
    assert "[Test] 3 changes detected" in sent_message
