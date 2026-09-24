"""Logging configuration with redaction of private data.

IPTV URLs usually embed the account name and password
(``http://host/live/<user>/<pass>/123.ts`` or ``get.php?username=..&password=..``).
Such URLs must never end up in log files that users may share when reporting
a problem, so every record passes through :class:`RedactingFilter`.
"""
import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path

_URL_RE = re.compile(r"\b((?:https?|rtmp|rtsp|udp|rtp|mms)://)([^/\s?#\"']+)([^\s\"']*)", re.IGNORECASE)
_CRED_RE = re.compile(r"(?i)\b(username|password|pass|user|token|api_key|apikey)=([^&\s\"']+)")
_USER_PATH_RE = re.compile(r"(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/\s]+")


def redact(text: str) -> str:
    """Remove credentials, URL paths and user names from ``text``."""
    if not text:
        return text

    def _url(match):
        scheme, host, rest = match.group(1), match.group(2), match.group(3)
        host = host.split("@")[-1]  # drop user:pass@
        return f"{scheme}{host}/<redacted>" if rest and rest != "/" else f"{scheme}{host}"

    text = _URL_RE.sub(_url, text)
    text = _CRED_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text)
    text = _USER_PATH_RE.sub(lambda m: f"{m.group(1)}<user>", text)
    home = str(Path.home())
    if len(home) > 3:
        text = text.replace(home, "~")
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        record.msg = redact(message)
        record.args = ()
        if record.exc_info and not record.exc_text:
            # Format the traceback now so it can be redacted too.
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def setup_logging(log_dir: Path, debug: bool = False) -> Path:
    """Configure root logging: rotating file + console, both redacted."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "migecast.log"
    level = logging.DEBUG if (debug or os.environ.get("MIGECAST_DEBUG")) else logging.INFO

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    redactor = RedactingFilter()

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redactor)
    root.addHandler(file_handler)

    if sys.stderr is not None:  # windowed (frozen) builds have no console
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.addFilter(redactor)
        root.addHandler(console)

    # Third-party libraries are chatty and may log full request URLs.
    for noisy in ("urllib3", "requests", "sqlalchemy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_file
