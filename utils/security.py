"""Security helpers: SSRF-conscious URL validation, filename sanitisation,
safe path joining, and download extension policy.

The application accepts arbitrary user-supplied URLs, so every outbound
request must pass :func:`validate_url` first.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse, urlunparse

import config


class SecurityError(Exception):
    """Raised when a URL or path fails a safety check."""


# Document types we are willing to download. Executables are never allowed.
ALLOWED_DOWNLOAD_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".txt", ".csv", ".rtf", ".odt", ".ods",
    ".xml", ".json", ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff",
}

# Never download / execute these, regardless of anything else.
BLOCKED_DOWNLOAD_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".dll", ".ps1",
    ".vbs", ".js", ".jse", ".jar", ".sh", ".app", ".apk", ".reg",
    ".lnk", ".pif", ".cpl", ".msc", ".gadget", ".hta", ".wsf",
}

_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

_ALLOWED_SCHEMES = {"http", "https"}


def _ip_is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_url(url: str, *, allow_private: bool | None = None) -> str:
    """Validate an outbound URL for scheme and SSRF safety.

    Returns the normalised URL, or raises :class:`SecurityError`.
    Only ``http``/``https`` are permitted; ``file://`` and others are rejected.
    Hosts resolving to private/loopback/reserved IPs are blocked unless
    ``allow_private`` (defaulting to the ``ALLOW_PRIVATE_HOSTS`` config) is set.
    """
    if allow_private is None:
        allow_private = config.ALLOW_PRIVATE_HOSTS

    if not url or not isinstance(url, str):
        raise SecurityError("Empty URL")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise SecurityError(f"Only http/https URLs are allowed (got '{parsed.scheme}')")

    host = parsed.hostname
    if not host:
        raise SecurityError("URL has no host")

    if allow_private:
        return urlunparse(parsed)

    # If the host is an IP literal, check it directly.
    try:
        ipaddress.ip_address(host)
        if _ip_is_blocked(host):
            raise SecurityError(f"Access to private/reserved address '{host}' is blocked")
        return urlunparse(parsed)
    except ValueError:
        pass  # not an IP literal -> resolve the hostname

    lowered = host.lower()
    if lowered == "localhost" or lowered.endswith(".localhost"):
        raise SecurityError("Access to localhost is blocked")

    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SecurityError(f"Could not resolve host '{host}': {exc}") from exc

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        if _ip_is_blocked(ip_str):
            raise SecurityError(
                f"Host '{host}' resolves to a blocked address ({ip_str})"
            )

    return urlunparse(parsed)


def is_url_allowed(url: str, *, allow_private: bool | None = None) -> bool:
    """Boolean convenience wrapper around :func:`validate_url`."""
    try:
        validate_url(url, allow_private=allow_private)
        return True
    except SecurityError:
        return False


def sanitize_filename(name: str, *, default: str = "file", max_length: int = 180) -> str:
    """Return a safe filename with no path separators or traversal."""
    if not name:
        return default

    # Drop any directory component an attacker may have embedded.
    name = name.replace("\\", "/").split("/")[-1]
    name = name.strip().strip(".")

    # Remove control characters and Windows-illegal characters.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(". ")

    if not name:
        return default

    stem, dot, ext = name.rpartition(".")
    base = stem if dot else name
    if base.lower() in _WINDOWS_RESERVED:
        name = f"_{name}"

    if len(name) > max_length:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 12:
            keep = max_length - len(ext) - 1
            name = f"{stem[:keep]}.{ext}"
        else:
            name = name[:max_length]

    return name or default


def sanitize_path_component(name: str, *, default: str = "unknown") -> str:
    """Sanitise a single directory-name component (e.g. portal or tender id)."""
    return sanitize_filename(name, default=default, max_length=120)


def safe_join(base, *paths) -> str:
    """Join paths under ``base`` and guarantee the result stays within it."""
    base_abs = os.path.abspath(str(base))
    joined = os.path.abspath(os.path.join(base_abs, *[str(p) for p in paths]))
    if not (joined == base_abs or joined.startswith(base_abs + os.sep)):
        raise SecurityError("Path traversal detected")
    return joined


def download_extension_allowed(filename_or_url: str) -> bool:
    """True if the target may be downloaded (allowed type, not executable)."""
    path = urlparse(filename_or_url).path if "://" in filename_or_url else filename_or_url
    _, ext = os.path.splitext(path.lower())
    if not ext:
        # No extension: allow (server Content-Type is checked later), but never
        # treat as executable.
        return True
    if ext in BLOCKED_DOWNLOAD_EXTENSIONS:
        return False
    return ext in ALLOWED_DOWNLOAD_EXTENSIONS
