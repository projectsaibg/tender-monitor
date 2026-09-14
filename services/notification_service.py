"""Optional email notifications over SMTP.

All credentials come from user-editable settings (never hard-coded, never
logged). Sending is best-effort and never raises into the scan flow.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from services import tender_service as ts
from utils.dates import now_tz
from utils.logging_setup import get_logger

log = get_logger("app")


def _truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def smtp_configured(settings=None):
    s = settings or ts.get_settings()
    return bool(s.get("smtp_host") and s.get("email_from") and s.get("email_to"))


def send_email(subject, body, attachments=None, settings=None):
    """Send an email. Returns a result dict; never raises."""
    s = settings or ts.get_settings()
    if not smtp_configured(s):
        return {"sent": False, "reason": "SMTP not configured"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s["email_from"]
    msg["To"] = s["email_to"]
    msg.set_content(body)

    for path in attachments or []:
        try:
            p = Path(path)
            if not p.exists():
                continue
            data = p.read_bytes()
            msg.add_attachment(
                data, maintype="application",
                subtype="octet-stream", filename=p.name)
        except Exception as exc:
            log.warning("Could not attach %s: %s", path, exc)

    host = s["smtp_host"]
    port = int(s.get("smtp_port") or 587)
    username = s.get("smtp_username") or ""
    password = s.get("smtp_password") or ""
    use_tls = _truthy(s.get("smtp_use_tls", "1"))

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                if username:
                    server.login(username, password)
                server.send_message(msg)
        log.info("Notification email sent to %s (subject=%s)", s["email_to"], subject)
        return {"sent": True, "reason": "ok"}
    except Exception as exc:
        log.warning("Email send failed: %s", exc)  # never log the password
        return {"sent": False, "reason": str(exc)}


def build_daily_summary_text(summary):
    stats = ts.dashboard_stats()
    high = len([t for t in ts.tenders_by_status("new") if t.get("relevance_band") == "HIGH"])
    date_str = now_tz(ts.get_timezone_name()).strftime("%d %B %Y")
    lines = [
        "Tender Monitor Daily Report",
        "Date: %s" % date_str,
        "",
        "Portals scanned: %d" % summary.get("portals", 0),
        "Successful: %d" % summary.get("successful", 0),
        "Attention required: %d" % (summary.get("portals", 0) - summary.get("successful", 0)),
        "New tenders: %d" % summary.get("new", 0),
        "Updated tenders: %d" % summary.get("updated", 0),
        "High-relevance new tenders: %d" % high,
        "Documents downloaded: %d" % summary.get("documents", 0),
        "",
        "Total tenders in database: %d" % stats["total_tenders"],
    ]
    return "\n".join(lines)


def maybe_send_summary(summary, excel_path=None, settings=None):
    """Send a daily summary honouring the notify_* flags. Returns a result dict."""
    s = settings or ts.get_settings()
    if not _truthy(s.get("notify_enabled")):
        return {"sent": False, "reason": "notifications disabled"}
    if not smtp_configured(s):
        return {"sent": False, "reason": "SMTP not configured"}

    had_errors = summary.get("successful", 0) < summary.get("portals", 0)
    high = len([t for t in ts.tenders_by_status("new") if t.get("relevance_band") == "HIGH"])

    if _truthy(s.get("notify_only_errors")) and not had_errors:
        return {"sent": False, "reason": "no errors to report"}
    if _truthy(s.get("notify_only_if_new")) and summary.get("new", 0) == 0 \
            and not (_truthy(s.get("notify_only_errors")) and had_errors):
        return {"sent": False, "reason": "no new tenders"}
    if _truthy(s.get("notify_only_high_relevance")) and high == 0:
        return {"sent": False, "reason": "no high-relevance tenders"}

    body = build_daily_summary_text(summary)
    attachments = [excel_path] if (excel_path and _truthy(s.get("notify_attach_excel"))) else []
    subject = "Tender Monitor: %d new, %d updated" % (summary.get("new", 0), summary.get("updated", 0))
    return send_email(subject, body, attachments=attachments, settings=s)
