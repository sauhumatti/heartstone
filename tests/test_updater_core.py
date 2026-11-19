"""The app's own update code, run on this machine.

The Android app's updater keeps its rules (UpdateState) and its network and file
work (UpdateFiles) in plain Java with no Android in it. These tests compile those
two files as they are and run them against the real update routes of a live test
server: the same code the phone runs, apart from where it stores a few values.
Skipped when no Java compiler is installed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("GAME_NO_PERSIST", "1")

import requests  # noqa: E402
import uvicorn  # noqa: E402

from server import updates  # noqa: E402
from server.app import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "ai" / "sakualy" / "cardgame" / "update"
PORT = 18794
BASE = f"http://127.0.0.1:{PORT}/api/app/"
TOKEN = "u" * 64


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no Java compiler here")
class TestUpdaterCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="updater-core-test-"))
        cls.classes = cls.tmp / "classes"
        subprocess.run(
            ["javac", "-d", str(cls.classes), str(JAVA_SRC / "UpdateState.java"), str(JAVA_SRC / "UpdateFiles.java"), str(ROOT / "tests" / "java" / "UpdateDriver.java")],
            check=True,
            capture_output=True,
        )
        cls.saved = (updates.UPDATES_DIR, updates.TOKEN_FILE)
        updates.UPDATES_DIR = cls.tmp / "files"
        updates.TOKEN_FILE = cls.tmp / "app-token"
        updates.UPDATES_DIR.mkdir()
        updates.TOKEN_FILE.write_text(TOKEN + "\n")
        (cls.tmp / "wrong-token").write_text("w" * 64 + "\n")
        cls.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(60):
            try:
                if requests.get(f"http://127.0.0.1:{PORT}/api/health", timeout=0.5).ok:
                    break
            except Exception:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.should_exit = True
        cls.thread.join(timeout=3)
        updates.UPDATES_DIR, updates.TOKEN_FILE = cls.saved
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def java(self, *args: str) -> str:
        res = subprocess.run(["java", "-cp", str(self.classes), "UpdateDriver", *args], capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def publish(self, version: str, files: dict[str, bytes]) -> dict:
        data = make_zip(files)
        (updates.UPDATES_DIR / f"bundle-{version}.zip").write_bytes(data)
        bundle = {"version": version, "file": f"bundle-{version}.zip", "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "minShell": 2}
        (updates.UPDATES_DIR / "manifest.json").write_text(json.dumps({"bundle": bundle, "notes": "x"}))
        return bundle

    # --- the rules ---------------------------------------------------------------------

    def steps(self, *ops: str) -> list[dict[str, str]]:
        out = []
        for line in self.java("state", *ops).splitlines():
            fields = dict(part.split("=", 1) for part in line.split(" -> ", 1)[1].split(" "))
            out.append(fields)
        return out

    def test_a_downloaded_bundle_is_shown_at_the_next_start_and_kept_once_confirmed(self) -> None:
        s = self.steps("start=2/0.2.0", "stage=202611170001", "start=2/0.2.0", "confirm", "start=2/0.2.0")
        self.assertEqual(s[0]["shown"], "")  # first start: the built-in bundle
        self.assertEqual(s[1]["pending"], "202611170001")
        self.assertEqual((s[2]["shown"], s[2]["trying"]), ("202611170001", "202611170001"))
        self.assertEqual((s[3]["active"], s[3]["trying"]), ("202611170001", ""))
        self.assertEqual((s[4]["shown"], s[4]["failed"]), ("202611170001", ""))

    def test_a_bundle_that_never_reports_in_is_dropped_for_good(self) -> None:
        s = self.steps("start=2/0.2.0", "stage=202611170001", "start=2/0.2.0", "start=2/0.2.0", "stage=202611170001", "start=2/0.2.0")
        self.assertEqual(s[2]["shown"], "202611170001")
        # started again without a confirm in between: back to the built-in bundle
        self.assertEqual((s[3]["shown"], s[3]["failed"], s[3]["rolledBack"]), ("", "202611170001", "202611170001"))
        # and it is not taken again, even if offered
        self.assertEqual(s[4]["pending"], "")
        self.assertEqual(s[5]["shown"], "")

    def test_rollback_goes_to_the_bundle_before_not_all_the_way_back(self) -> None:
        s = self.steps("start=2/0.2.0", "stage=202611170001", "start=2/0.2.0", "confirm", "stage=202611180001", "start=2/0.2.0", "start=2/0.2.0")
        self.assertEqual(s[5]["shown"], "202611180001")
        self.assertEqual(s[5]["inUse"], "202611180001,202611170001")  # the earlier one is kept while the new one is on trial
        self.assertEqual((s[6]["shown"], s[6]["failed"]), ("202611170001", "202611180001"))

    def test_the_watchdog_and_restart_inside_a_running_app(self) -> None:
        s = self.steps("start=2/0.2.0", "stage=202611170001", "apply", "giveup", "apply")
        self.assertEqual((s[2]["shown"], s[2]["trying"]), ("202611170001", "202611170001"))  # "Restart now"
        self.assertEqual((s[3]["shown"], s[3]["active"], s[3]["failed"]), ("true", "", "202611170001"))
        self.assertEqual(s[4]["shown"], "")

    def test_a_new_app_version_forgets_every_download(self) -> None:
        s = self.steps("start=2/0.2.0", "stage=202611170001", "start=2/0.2.0", "confirm", "stage=202611180001", "start=3/0.3.0")
        self.assertEqual((s[5]["shown"], s[5]["active"], s[5]["pending"], s[5]["fresh"], s[5]["inUse"]), ("", "", "", "true", ""))

    def test_version_order(self) -> None:
        for newer, older, expected in (
            ("202611170001", "202611160001", "true"),
            ("202611160001", "202611160001", "false"),
            ("202611160001", "202611170001", "false"),
            ("1000000000000", "202611160001", "true"),  # longer is later
            ("99", "202611160001", "false"),
            ("abc", "1", "false"),
            ("../x", "1", "false"),
            ("5", "", "true"),
        ):
            self.assertEqual(self.java("newer", newer, older), expected, (newer, older))

    # --- asking the server and fetching ---------------------------------------------------

    def test_manifest_fetch_with_and_without_the_token(self) -> None:
        self.publish("202611170001", {"index.html": b"<html>one</html>"})
        body = json.loads(self.java("get", BASE + "latest", str(updates.TOKEN_FILE)))
        self.assertEqual(body["bundle"]["version"], "202611170001")
        self.assertTrue(self.java("get", BASE + "latest", str(self.tmp / "wrong-token")).startswith("PROBLEM refused"))
        self.assertTrue(self.java("get", BASE + "latest", "").startswith("PROBLEM refused"))
        self.assertTrue(self.java("get", "http://127.0.0.1:9/api/app/latest", str(updates.TOKEN_FILE)).startswith("PROBLEM offline"))

    def test_download_verify_unpack(self) -> None:
        files = {"index.html": b"<html>two</html>", "assets/app.js": b"x" * 400_000, "py/engine.zip": os.urandom(300_000), "bundle.json": b'{"version":"202611170002"}'}
        b = self.publish("202611170002", files)
        dest = self.tmp / "dl.zip"
        out = self.java("download", BASE + f"bundle/{b['version']}.zip", str(updates.TOKEN_FILE), str(dest), str(b["size"]), b["sha256"])
        self.assertTrue(out.startswith("OK"), out)
        self.assertIn(f"last={b['size']}", out)
        self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(), b["sha256"])
        target = self.tmp / "bundles" / b["version"]
        target.parent.mkdir(exist_ok=True)
        self.assertEqual(self.java("unzip", str(dest), str(target)), "OK")
        for name, data in files.items():
            self.assertEqual((target / name).read_bytes(), data, name)
        self.assertFalse((target.parent / (b["version"] + ".part")).exists())

    def test_a_wrong_checksum_size_or_token_leaves_no_file(self) -> None:
        b = self.publish("202611170003", {"index.html": b"<html>three</html>", "a.bin": os.urandom(50_000)})
        url = BASE + f"bundle/{b['version']}.zip"
        dest = self.tmp / "bad.zip"
        cases = (
            ("checksum", (url, str(updates.TOKEN_FILE), str(dest), str(b["size"]), "0" * 64)),
            ("checksum", (url, str(updates.TOKEN_FILE), str(dest), str(b["size"]), "")),
            ("size", (url, str(updates.TOKEN_FILE), str(dest), str(b["size"] - 10), b["sha256"])),
            ("size", (url, str(updates.TOKEN_FILE), str(dest), str(b["size"] + 10), b["sha256"])),
            ("size", (url, str(updates.TOKEN_FILE), str(dest), "0", b["sha256"])),
            ("refused", (url, str(self.tmp / "wrong-token"), str(dest), str(b["size"]), b["sha256"])),
            ("refused", (BASE + "bundle/209912310000.zip", str(updates.TOKEN_FILE), str(dest), str(b["size"]), b["sha256"])),
            ("cancelled", (url, str(updates.TOKEN_FILE), str(dest), str(b["size"]), b["sha256"], "cancel")),
        )
        for kind, args in cases:
            out = self.java("download", *args)
            self.assertTrue(out.startswith(f"PROBLEM {kind}"), (kind, out))
            self.assertFalse(dest.exists(), kind)

    def test_archives_that_are_not_a_game_or_reach_outside_are_refused(self) -> None:
        target = self.tmp / "bundles" / "evil"
        target.parent.mkdir(exist_ok=True)
        outside = self.tmp / "escaped.txt"
        for name, files in (
            ("no index", {"assets/app.js": b"x"}),
            ("dots", {"index.html": b"x", "../escaped.txt": b"got out"}),
            ("deep dots", {"index.html": b"x", "a/../../../escaped.txt": b"got out"}),
            ("absolute", {"index.html": b"x", str(outside): b"got out"}),
        ):
            z = self.tmp / "evil.zip"
            z.write_bytes(make_zip(files))
            out = self.java("unzip", str(z), str(target))
            self.assertTrue(out.startswith("PROBLEM archive"), (name, out))
            self.assertFalse(target.exists(), name)
            self.assertFalse((target.parent / "evil.part").exists(), name)
            self.assertFalse(outside.exists(), name)
        z = self.tmp / "evil.zip"
        z.write_bytes(b"this is not a zip file at all")
        self.assertTrue(self.java("unzip", str(z), str(target)).startswith("PROBLEM archive"))


if __name__ == "__main__":
    unittest.main()
