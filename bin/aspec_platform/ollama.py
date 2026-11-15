"""Local Ollama discovery shared by retrieval, the Agent Console backend and the dashboard.

Ollama is local by contract: an endpoint is used only when it is loopback, or when this is WSL
and the endpoint is the Windows host at the default gateway (the same machine, reached over the
WSL virtual switch, which is where a Windows Ollama install listens). Anything else needs
AGENT_SPEC_ALLOW_REMOTE_MODELS=1. AGENT_SPEC_OLLAMA_URL pins the endpoint. Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434"
PROBE_TTL_S = 30.0
_LOOPBACK = ("127.0.0.1", "localhost", "::1")
_cache = {"at": 0.0, "key": None, "url": None, "models": []}
_lock = threading.Lock()


def _is_wsl() -> bool:
    try:
        with open("/proc/version", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def wsl_host() -> str | None:
    """The Windows host's address as seen from WSL (the default gateway), or None."""
    if not _is_wsl():
        return None
    try:
        out = subprocess.check_output(["ip", "route"], text=True, timeout=2, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


def is_local(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host in _LOOPBACK:
        return True
    return bool(host) and host == wsl_host()


def allowed(url: str) -> bool:
    return is_local(url) or os.environ.get("AGENT_SPEC_ALLOW_REMOTE_MODELS") == "1"


def candidates() -> list:
    env = (os.environ.get("AGENT_SPEC_OLLAMA_URL") or "").strip().rstrip("/")
    if env:
        return [env]
    urls = [DEFAULT_URL]
    host = wsl_host()
    if host:
        urls.append("http://%s:11434" % host)
    return urls


def _tags(url: str, timeout: float = 2.0) -> list | None:
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=timeout) as resp:  # noqa: S310 — local only
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    out = []
    for m in data.get("models") or []:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        caps = m.get("capabilities")
        details = m.get("details") or {}
        out.append({"name": m["name"], "size": m.get("size"),
                    "parameters": details.get("parameter_size"), "family": details.get("family"),
                    "capabilities": caps if isinstance(caps, list) else None})
    return out


def probe(force: bool = False) -> dict:
    """{"url", "reachable", "models"}; cached for PROBE_TTL_S so request handlers stay cheap."""
    key = tuple(candidates()) + (os.environ.get("AGENT_SPEC_ALLOW_REMOTE_MODELS"),)
    with _lock:
        if not force and _cache["key"] == key and time.time() - _cache["at"] < PROBE_TTL_S:
            return {"url": _cache["url"], "reachable": _cache["url"] is not None, "models": list(_cache["models"])}
    found, models = None, []
    for url in key[:-1]:
        if not allowed(url):
            continue
        tags = _tags(url)
        if tags is not None:
            found, models = url, tags
            break
    with _lock:
        _cache.update(at=time.time(), key=key, url=found, models=models)
    return {"url": found, "reachable": found is not None, "models": models}


def base_url() -> str:
    """A pinned AGENT_SPEC_OLLAMA_URL as given (callers enforce `allowed`); else the reachable
    local endpoint, else the first candidate (callers report the failure)."""
    pinned = (os.environ.get("AGENT_SPEC_OLLAMA_URL") or "").strip().rstrip("/")
    return pinned or probe()["url"] or candidates()[0]


def is_embed_model(m: dict) -> bool:
    caps = m.get("capabilities")
    if isinstance(caps, list) and "embedding" in caps:
        return True
    return "embed" in m["name"].lower()


def chat_models(models: list) -> list:
    """Models that can drive the tool loop: tool-capable first, embedding models excluded,
    cloud-proxied models (`:cloud`) excluded because they leave the machine."""
    usable = [m for m in models if not is_embed_model(m) and not m["name"].endswith(":cloud")]
    return sorted(usable, key=lambda m: (not ("tools" in (m.get("capabilities") or [])), m["name"]))


def supports(models: list, name: str, capability: str) -> bool:
    m = next((m for m in models if m["name"] == name), None)
    return bool(m and capability in (m.get("capabilities") or []))
