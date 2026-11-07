"""Redaction for everything the platform stores (S-003, IMPLEMENTATION-GUIDE §10).

`redact(text)` replaces secrets with `«redacted:<kind>»`; kinds: private_key, url_credentials,
aws_key, secret (key=value), bearer, hex, token (high entropy). Deliberately conservative: it
would rather over-redact a code line (`token = tokens.read(path)`) than leak. Prose, file paths,
UUIDs, kebab/camelCase identifiers and git SHAs are left alone.

SHA rule: a hex string of 32/40/64 chars is kept only when `commit`/`sha`/`hash`/`rev`/`digest`/
`checksum`/`md5`/`head` immediately precedes it; any other long hex string is redacted.
"""
from __future__ import annotations

import math
import re

_KEYWORDS = (r"password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization|credentials?|"
             r"private[_-]?key|access[_-]?key")
_KEY_RE = re.compile(_KEYWORDS, re.I)

_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)",
                          re.S)
_URL_CRED = re.compile(r"(://[^/\s:@]+:)([^@\s/]+)(@)")
_AWS = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_KV = re.compile(r"(?<!\w)((?:[\w.-]*?)(?:" + _KEYWORDS + r")[\w.-]*)(['\"]?\s*[:=]\s*)"
                 r"((?:(?:Bearer|Basic|Token)\s+)?(?:\"[^\"\n]*\"|'[^'\n]*'|(?![{\[(])[^\s,;&\"'«$<]{4,}))", re.I)
_BEARER = re.compile(r"\b(Bearer\s+)(?=[A-Za-z0-9._~+/=-]*[\d._~+/=-])[A-Za-z0-9._~+/=-]{8,}", re.I)
_CANDIDATE = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{32,}={0,2}(?![A-Za-z0-9+/_-])")
_HEX = re.compile(r"[0-9a-fA-F]+")
_SHA_CONTEXT = re.compile(r"(?i)(?:commit|sha\d*|rev(?:ision)?|hash|checksum|digest|md5|head)[\s:=#'\"(\-]*$")
_WORD = re.compile(r"[a-z0-9]+|[A-Z0-9]+|[A-Z][a-z0-9]+")  # one part of kebab/snake/path identifiers
_ENTROPY_MIN = 3.3


def _marker(kind: str) -> str:
    return "«redacted:%s»" % kind


def _entropy(token: str) -> float:
    counts = {}
    for ch in token:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum(n / len(token) * math.log2(n / len(token)) for n in counts.values())


def _high_entropy(text: str) -> str:
    def repl(m):
        token = m.group(0)
        bare = token.rstrip("=")
        if _HEX.fullmatch(bare):
            if len(bare) in (32, 40, 64) and _SHA_CONTEXT.search(text[max(0, m.start() - 20):m.start()]):
                return token
            return _marker("hex")
        has_digit = any(c.isdigit() for c in bare)
        has_alpha = any(c.isalpha() for c in bare)
        if has_digit and has_alpha and _entropy(bare) >= _ENTROPY_MIN:
            parts = [p for p in re.split(r"[-_/]", bare) if p]
            if len(parts) > 1 and all(_WORD.fullmatch(p) for p in parts):
                return token  # kebab / snake / path style identifier made of word-shaped parts
            return _marker("token")
        return token
    return _CANDIDATE.sub(repl, text)


def redact(text) -> str:
    """Return `text` with secrets replaced by `«redacted:<kind>»` markers."""
    if text is None:
        return ""
    text = text if isinstance(text, str) else str(text)
    text = _PRIVATE_KEY.sub(_marker("private_key"), text)
    text = _URL_CRED.sub(lambda m: m.group(1) + _marker("url_credentials") + m.group(3), text)
    text = _AWS.sub(_marker("aws_key"), text)
    text = _KV.sub(lambda m: m.group(1) + m.group(2) + _marker("secret"), text)
    text = _BEARER.sub(lambda m: m.group(1) + _marker("bearer"), text)
    return _high_entropy(text)


def redact_obj(obj):
    """Deep copy of dicts/lists/tuples with every string redacted; secret-named keys lose the value."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if isinstance(value, str) and value and _KEY_RE.search(str(key)) and not value.startswith("«"):
                out[key] = _marker("secret")
            else:
                out[key] = redact_obj(value)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj
