"""Fail if tracked files contain private data (runs in CI and locally).

Checks every file tracked by git (or every file below a folder) for:
* databases, logs, key files, playlists outside tests/fixtures
* stream URLs that embed credentials, unless the host is a reserved example
  host (``*.invalid``, ``example.*``, ``localhost``, ``127.0.0.1``)
* hard-coded API keys

Usage: python tools/check_repo_secrets.py [folder]
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
BINARY_OK = {".png", ".ico", ".jpg"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".log", ".env", ".key", ".db-wal", ".db-shm", ".exe", ".dll", ".pkg", ".pyz"}
URL_RE = re.compile(r"(?i)\b(?:https?|rtmp|rtsp)://[^\s\"'<>()\\]+")
CRED_PATH_RE = re.compile(r"/(live|movie|series)/[^/\s]+/[^/\s]+/")
API_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*[\"']([A-Za-z0-9]{24,})[\"']")
SAFE_HOST_RE = re.compile(r"(?i)(^|\.)(invalid|example\.(com|org|net)|localhost)$|^127\.0\.0\.1$|^example\.")


def tracked_files(folder: Path):
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=folder, text=True)
        return [folder / name for name in output.split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in folder.rglob("*") if p.is_file() and ".git" not in p.parts]


def host_is_safe(host: str) -> bool:
    host = (host or "").split("@")[-1].split(":")[0]
    if host and "." not in host:
        return True  # placeholder like "host" or "h" (real hosts have a domain or are IPs)
    return bool(SAFE_HOST_RE.search(host)) or "{" in host


def check(folder: Path) -> list:
    problems = []
    for path in tracked_files(folder):
        rel = path.relative_to(folder).as_posix()
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES or path.name in ("secret.key", ".env"):
            problems.append(f"{rel}: private or binary file must not be committed")
            continue
        if suffix in (".m3u", ".m3u8") and not rel.startswith("tests/fixtures/"):
            problems.append(f"{rel}: playlists must not be committed (except synthetic test fixtures)")
        if suffix in BINARY_OK or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip(".,;")
            try:
                parts = urlsplit(url)
            except ValueError:
                continue
            query = parse_qs(parts.query)
            risky = bool(CRED_PATH_RE.search(parts.path)) or ("password" in query) or ("username" in query)
            if risky and not host_is_safe(parts.hostname or parts.netloc):
                problems.append(f"{rel}: URL with credentials for a real host: {parts.hostname}")
        for match in API_KEY_RE.finditer(text):
            problems.append(f"{rel}: hard-coded key ({match.group(1)})")
    return problems


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    problems = check(folder)
    for problem in problems:
        print("SECRET-CHECK:", problem)
    print(f"secret check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
