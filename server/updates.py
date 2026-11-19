"""Updates for the installed app: what the newest version is, and the files.

The app asks `GET /api/app/latest` and gets a manifest: the newest web bundle
(the game itself: client, engine, art, sound) and the newest shell (the APK).
A bundle is fetched and swapped in by the app on its own; a new shell is
installed by hand from a link the manifest carries.

Everything here is for the app only. A request must carry the app's token in
the `X-App-Token` header. The one exception is the APK link, which the phone's
browser opens and so cannot carry a header: that link is signed with the token
and stops working after a quarter of an hour, so the token itself never
appears in a URL or a log. Anything without a valid token or signature gets
the same 404 as a path that does not exist.

Files live in var/app-updates/, put there by scripts/release.sh together with
manifest.json. Only the two files the manifest names are ever served; nothing
from a request is used as a file name. Without a token file the routes are off.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse

_ROOT = Path(__file__).resolve().parent.parent
# Module attributes, read at each request, so tests can point them elsewhere.
UPDATES_DIR = Path(os.environ.get("APP_UPDATES_DIR") or _ROOT / "var" / "app-updates")
TOKEN_FILE = Path(os.environ.get("APP_TOKEN_FILE") or _ROOT / "var" / "android" / "app-token")
LINK_SECONDS = 15 * 60

router = APIRouter()


def _gone() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found")


def _token() -> Optional[str]:
    try:
        token = TOKEN_FILE.read_text().strip()
    except OSError:
        return None
    return token if len(token) >= 32 else None


def _require(given: Optional[str]) -> str:
    """The app's token, or a 404 if the caller did not send it."""
    token = _token()
    if not token or not given or not hmac.compare_digest(given.encode(), token.encode()):
        raise _gone()
    return token


def _manifest() -> dict[str, Any]:
    try:
        data = json.loads((UPDATES_DIR / "manifest.json").read_text())
    except (OSError, ValueError):
        raise _gone()
    if not isinstance(data, dict):
        raise _gone()
    return data


def _file(entry: Any) -> Path:
    """The file a manifest entry names, which must be a plain file in the updates folder."""
    name = entry.get("file") if isinstance(entry, dict) else None
    if not isinstance(name, str) or not name or name != Path(name).name or name.startswith("."):
        raise _gone()
    path = UPDATES_DIR / name
    if not path.is_file():
        raise _gone()
    return path


def _sign(token: str, version_code: Any, expires: int) -> str:
    return hmac.new(token.encode(), f"shell:{version_code}:{expires}".encode(), hashlib.sha256).hexdigest()


@router.get("/api/app/latest")
def latest(x_app_token: Optional[str] = Header(default=None)) -> dict[str, Any]:
    token = _require(x_app_token)
    manifest = _manifest()
    out: dict[str, Any] = {"notes": str(manifest.get("notes") or ""), "published": manifest.get("published")}
    bundle = manifest.get("bundle")
    if isinstance(bundle, dict) and bundle.get("version"):
        _file(bundle)
        out["bundle"] = {
            "version": str(bundle["version"]),
            "url": f"bundle/{bundle['version']}.zip",
            "sha256": bundle.get("sha256"),
            "size": bundle.get("size"),
            "minShell": int(bundle.get("minShell") or 1),
        }
    shell = manifest.get("shell")
    if isinstance(shell, dict) and shell.get("versionCode"):
        _file(shell)
        expires = int(time.time()) + LINK_SECONDS
        code = int(shell["versionCode"])
        out["shell"] = {
            "versionCode": code,
            "versionName": str(shell.get("versionName") or ""),
            # for the phone's browser: signed, and good for a quarter of an hour
            "url": f"shell/{code}.apk?e={expires}&s={_sign(token, code, expires)}",
            "sha256": shell.get("sha256"),
            "size": shell.get("size"),
        }
    return out


@router.get("/api/app/bundle/{name}")
def bundle_file(name: str, x_app_token: Optional[str] = Header(default=None)) -> FileResponse:
    _require(x_app_token)
    bundle = _manifest().get("bundle")
    if not isinstance(bundle, dict) or name != f"{bundle.get('version')}.zip":
        raise _gone()
    return FileResponse(_file(bundle), media_type="application/zip")


@router.get("/api/app/shell/{name}")
def shell_file(name: str, e: str = Query(default=""), s: str = Query(default="")) -> FileResponse:
    token = _token()
    shell = _manifest().get("shell") if token else None
    if not token or not isinstance(shell, dict) or name != f"{shell.get('versionCode')}.apk":
        raise _gone()
    try:
        expires = int(e)
    except ValueError:
        raise _gone()
    expected = _sign(token, shell.get("versionCode"), expires)
    if expires < time.time() or not hmac.compare_digest(s.encode(), expected.encode()):
        raise _gone()
    path = _file(shell)
    return FileResponse(path, media_type="application/vnd.android.package-archive", filename=path.name)
