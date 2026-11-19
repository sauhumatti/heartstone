"""The app's update routes: only for a caller with the app's token, and only the files the manifest names."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

os.environ.setdefault("GAME_NO_PERSIST", "1")

import requests  # noqa: E402
import uvicorn  # noqa: E402

from server import updates  # noqa: E402
from server.app import FRONTEND_DIST, app  # noqa: E402

PORT = 18793
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "t" * 64


def get(path: str, token: str | None = None, **kw) -> requests.Response:
    headers = {"X-App-Token": token} if token is not None else {}
    return requests.get(BASE + path, headers=headers, timeout=10, **kw)


class TestAppUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="app-updates-test-"))
        cls.saved = (updates.UPDATES_DIR, updates.TOKEN_FILE)
        updates.UPDATES_DIR = cls.tmp / "files"
        updates.TOKEN_FILE = cls.tmp / "app-token"
        updates.UPDATES_DIR.mkdir()
        cls.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(60):
            try:
                if requests.get(BASE + "/api/health", timeout=0.5).ok:
                    break
            except Exception:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.should_exit = True
        cls.thread.join(timeout=3)
        updates.UPDATES_DIR, updates.TOKEN_FILE = cls.saved
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self) -> None:
        for f in updates.UPDATES_DIR.iterdir():
            f.unlink()
        updates.TOKEN_FILE.write_text(TOKEN + "\n")
        self.publish("202611160001")

    def publish(self, version: str, code: int = 2) -> None:
        d = updates.UPDATES_DIR
        zip_bytes = f"bundle {version}".encode() * 50
        apk_bytes = f"apk {code}".encode() * 50
        (d / f"bundle-{version}.zip").write_bytes(zip_bytes)
        (d / f"game-0.{code}.0.apk").write_bytes(apk_bytes)
        (d / "other-secret.zip").write_bytes(b"not in the manifest")
        manifest = {
            "bundle": {
                "version": version,
                "file": f"bundle-{version}.zip",
                "sha256": hashlib.sha256(zip_bytes).hexdigest(),
                "size": len(zip_bytes),
                "minShell": 2,
            },
            "shell": {
                "versionCode": code,
                "versionName": f"0.{code}.0",
                "file": f"game-0.{code}.0.apk",
                "sha256": hashlib.sha256(apk_bytes).hexdigest(),
                "size": len(apk_bytes),
            },
            "notes": "A test release.",
            "published": "2026-11-16T00:01:00Z",
        }
        (d / "manifest.json").write_text(json.dumps(manifest))

    # --- who gets in -----------------------------------------------------------

    def test_without_the_token_every_route_is_a_plain_404(self) -> None:
        missing = get("/api/no-such-route")
        self.assertEqual(missing.status_code, 404)
        for path in ("/api/app/latest", "/api/app/bundle/202611160001.zip", "/api/app/shell/2.apk", "/api/app/", "/api/app/manifest.json"):
            for token in (None, "", "wrong", TOKEN[:-1], TOKEN + "x"):
                res = get(path, token)
                self.assertEqual(res.status_code, 404, (path, token))
                self.assertEqual(res.content, missing.content, (path, token))

    def test_the_token_as_a_query_parameter_does_not_work(self) -> None:
        for path in ("/api/app/latest", "/api/app/bundle/202611160001.zip", "/api/app/shell/2.apk"):
            self.assertEqual(get(f"{path}?token={TOKEN}").status_code, 404)
            self.assertEqual(get(f"{path}?x_app_token={TOKEN}").status_code, 404)

    def test_without_a_token_file_the_routes_are_off(self) -> None:
        updates.TOKEN_FILE.unlink()
        self.assertEqual(get("/api/app/latest", TOKEN).status_code, 404)
        self.assertEqual(get("/api/app/latest", "").status_code, 404)
        updates.TOKEN_FILE.write_text("short\n")  # a token too short to be one is no token
        self.assertEqual(get("/api/app/latest", "short").status_code, 404)

    # --- the manifest and the bundle -----------------------------------------------

    def test_manifest_and_bundle_with_the_token(self) -> None:
        res = get("/api/app/latest", TOKEN)
        self.assertEqual(res.status_code, 200)
        m = res.json()
        self.assertEqual(m["bundle"]["version"], "202611160001")
        self.assertEqual(m["bundle"]["url"], "bundle/202611160001.zip")
        self.assertEqual(m["bundle"]["minShell"], 2)
        self.assertEqual(m["shell"]["versionCode"], 2)
        self.assertEqual(m["notes"], "A test release.")
        self.assertNotIn("file", m["bundle"])
        self.assertNotIn(TOKEN, res.text)

        got = get("/api/app/" + m["bundle"]["url"], TOKEN)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(len(got.content), m["bundle"]["size"])
        self.assertEqual(hashlib.sha256(got.content).hexdigest(), m["bundle"]["sha256"])

    def test_only_the_bundle_the_manifest_names_is_served(self) -> None:
        for name in (
            "other-secret.zip",
            "manifest.json",
            "202611160000.zip",
            "bundle-202611160001.zip",
            "..%2f..%2fandroid%2fapp-token",
            "%2e%2e%2f%2e%2e%2fgames",
            "202611160001.zip%00.txt",
        ):
            self.assertEqual(get(f"/api/app/bundle/{name}", TOKEN).status_code, 404, name)

    def test_a_newer_release_replaces_the_old_one(self) -> None:
        self.publish("202611170900", code=3)
        m = get("/api/app/latest", TOKEN).json()
        self.assertEqual(m["bundle"]["version"], "202611170900")
        self.assertEqual(m["shell"]["versionCode"], 3)
        self.assertEqual(get("/api/app/bundle/202611170900.zip", TOKEN).status_code, 200)
        self.assertEqual(get("/api/app/bundle/202611160001.zip", TOKEN).status_code, 404)

    def test_a_manifest_naming_a_file_outside_the_folder_serves_nothing(self) -> None:
        d = updates.UPDATES_DIR
        m = json.loads((d / "manifest.json").read_text())
        for bad in ("../app-token", "/etc/hostname", ".hidden.zip", "sub/dir.zip", ""):
            m["bundle"]["file"] = bad
            (d / "manifest.json").write_text(json.dumps(m))
            self.assertEqual(get("/api/app/latest", TOKEN).status_code, 404, bad)
            self.assertEqual(get("/api/app/bundle/202611160001.zip", TOKEN).status_code, 404, bad)

    def test_no_manifest_or_a_broken_one_is_a_404(self) -> None:
        (updates.UPDATES_DIR / "manifest.json").write_text("{not json")
        self.assertEqual(get("/api/app/latest", TOKEN).status_code, 404)
        (updates.UPDATES_DIR / "manifest.json").unlink()
        self.assertEqual(get("/api/app/latest", TOKEN).status_code, 404)

    # --- the APK link, for a browser --------------------------------------------------

    def test_the_apk_link_works_without_a_header_until_it_expires(self) -> None:
        m = get("/api/app/latest", TOKEN).json()
        url = "/api/app/" + m["shell"]["url"]
        self.assertNotIn(TOKEN, url)
        res = get(url)  # as a browser would: no header
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/vnd.android.package-archive")
        self.assertIn("game-0.2.0.apk", res.headers.get("content-disposition", ""))
        self.assertEqual(hashlib.sha256(res.content).hexdigest(), m["shell"]["sha256"])

    def test_the_apk_link_cannot_be_altered_or_reused_late(self) -> None:
        m = get("/api/app/latest", TOKEN).json()
        path, query = m["shell"]["url"].split("?")
        e = int(query.split("&")[0].split("=")[1])
        s = query.split("&")[1].split("=")[1]
        self.assertTrue(0 < e - time.time() <= updates.LINK_SECONDS + 1)
        for bad in (
            f"{path}",
            f"{path}?e={e}",
            f"{path}?e={e + 3600}&s={s}",
            f"{path}?e={e}&s={s[:-1]}0",
            f"{path}?e=abc&s={s}",
            f"shell/3.apk?e={e}&s={s}",
            f"{path}?token={TOKEN}",
        ):
            self.assertEqual(get("/api/app/" + bad).status_code, 404, bad)
        # a link whose time has passed, even though it was signed properly
        past = int(time.time()) - 5
        self.assertEqual(get(f"/api/app/{path}?e={past}&s={updates._sign(TOKEN, 2, past)}").status_code, 404)
        # and one signed for another version is no use for this one
        self.assertEqual(get(f"/api/app/{path}?e={e}&s={updates._sign(TOKEN, 3, e)}").status_code, 404)

    # --- what comes through the app's door reaches nothing else ---------------------------

    def test_a_request_marked_as_from_the_apps_door_reaches_only_the_update_routes(self) -> None:
        gate = {"X-App-Gate": "1"}
        for path in ("/", "/api/health", "/api/games", "/api/cards", "/sw.js", "/index.html", "/assets/x.js", "/art/x.webp", "/x/../api/app/latest"):
            req = requests.Request("GET", BASE + path, headers=gate).prepare()
            req.url = BASE + path
            res = requests.Session().send(req, timeout=10)
            self.assertEqual(res.status_code, 404, path)
            self.assertEqual(res.content, b'{"detail":"Not found"}', path)
        self.assertEqual(requests.post(BASE + "/api/games", json={}, headers=gate, timeout=10).status_code, 404)
        # the update routes still work through it, and still want the token
        self.assertEqual(requests.get(BASE + "/api/app/latest", headers={**gate, "X-App-Token": TOKEN}, timeout=10).status_code, 200)
        self.assertEqual(requests.get(BASE + "/api/app/latest", headers=gate, timeout=10).status_code, 404)
        # and without the mark the rest of the server is as before
        self.assertEqual(requests.get(BASE + "/api/health", timeout=10).status_code, 200)

    # --- the page fallback must stay inside the build folder ----------------------------

    def test_the_page_fallback_cannot_be_walked_out_of_its_folder(self) -> None:
        index = (FRONTEND_DIST / "index.html").read_bytes() if (FRONTEND_DIST / "index.html").exists() else None
        s = requests.Session()
        for tricky in ("/../../README.md", "/%2e%2e/%2e%2e/README.md", "/..%2f..%2fREADME.md", "/assets/../../../README.md", "/x/../../../server/app.py"):
            req = requests.Request("GET", BASE + tricky).prepare()
            req.url = BASE + tricky  # keep the dots: requests would tidy them away
            res = s.send(req, timeout=10)
            self.assertNotIn(b"## Sound", res.content, tricky)
            self.assertNotIn(b"FastAPI", res.content, tricky)
            if index is not None and res.status_code == 200:
                self.assertEqual(res.content, index, tricky)


if __name__ == "__main__":
    unittest.main()
