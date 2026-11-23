"""The friends' door: requests marked X-Friend-Gate (a host without the site's password) reach a
friend match through its invitation and nothing else."""
from __future__ import annotations

import json
import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("GAME_NO_PERSIST", "1")

import requests  # noqa: E402
import uvicorn  # noqa: E402
from websockets.sync.client import connect as ws_connect  # noqa: E402

from data.meta_decks import META_POOLS  # noqa: E402
from server.app import app  # noqa: E402

PORT = 18767
BASE = f"http://127.0.0.1:{PORT}"
SITE = "https://site.example"
FRIEND = "https://friends.example"
DOOR = {"X-Friend-Gate": "1", "Origin": FRIEND}


def _cookie(res: requests.Response) -> str:
    return res.headers["set-cookie"].split(";")[0]


class TestFriendDoor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.env = patch.dict(os.environ, {"CARDGAME_PUBLIC_ORIGIN": SITE, "CARDGAME_FRIEND_ORIGIN": FRIEND})
        cls.env.start()
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
        cls.env.stop()

    def friend_match(self) -> tuple[str, str, str]:
        res = requests.post(BASE + "/api/games", json={"p2_mode": "friend", "p1_deck_id": "starter_mage"},
                            headers={"Origin": SITE}, timeout=10)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        return body["game_id"], body["invite"], _cookie(res)

    def test_invitation_points_at_the_door(self) -> None:
        res = requests.post(BASE + "/api/games", json={"p2_mode": "friend", "p1_deck_id": "starter_mage"},
                            headers={"Origin": SITE}, timeout=10).json()
        self.assertEqual(res["invite_url"], f"{FRIEND}/#invite={res['game_id']}.{res['invite']}")

    def test_expansion_invite_requires_a_deck_from_the_same_pool(self) -> None:
        host, guest = META_POOLS["ungoro"][:2]
        created = requests.post(
            BASE + "/api/games", json={"p2_mode": "friend", "p1_deck_id": host["id"]},
            headers={"Origin": SITE}, timeout=10,
        ).json()
        self.assertEqual(created["invite_url"], f"{FRIEND}/#invite={created['game_id']}.{created['invite']}&era=ungoro")
        url = f"{BASE}/api/games/{created['game_id']}/join"
        rejected = requests.post(url, json={"invite": created["invite"], "deck_id": "starter_mage"}, headers=DOOR, timeout=10)
        self.assertEqual(rejected.status_code, 400)
        joined = requests.post(url, json={"invite": created["invite"], "deck_id": guest["id"]}, headers=DOOR, timeout=10)
        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.json()["state"]["deck_era"], "ungoro")

    def test_friend_joins_and_plays_through_the_door(self) -> None:
        gid, invite, _host = self.friend_match()
        joined = requests.post(f"{BASE}/api/games/{gid}/join", json={"invite": invite, "deck_id": "starter_warrior"},
                               headers=DOOR, timeout=10)
        self.assertEqual(joined.status_code, 200)
        self.assertIn("Path=/;", joined.headers["set-cookie"])
        guest = {**DOOR, "Cookie": _cookie(joined)}
        self.assertEqual(requests.get(f"{BASE}/api/games/{gid}/state?seat=p2", headers=guest, timeout=10).status_code, 200)
        self.assertEqual(requests.get(f"{BASE}/api/games/{gid}/state?seat=p1", headers=guest, timeout=10).status_code, 404)
        listed = requests.get(BASE + "/api/games", headers=guest, timeout=10).json()["games"]
        self.assertEqual([g["game_id"] for g in listed], [gid])
        res = requests.post(f"{BASE}/api/games/{gid}/mulligan", json={"seat": "p2", "replace_indices": []},
                            headers=guest, timeout=10)
        self.assertEqual(res.status_code, 200)
        with ws_connect(f"ws://127.0.0.1:{PORT}/ws/{gid}/p2", additional_headers=guest) as ws:
            self.assertEqual(json.loads(ws.recv(timeout=5))["state"]["viewer_seat"], "p2")

    def test_join_from_the_site_origin_is_refused_at_the_door(self) -> None:
        gid, invite, _host = self.friend_match()
        res = requests.post(f"{BASE}/api/games/{gid}/join", json={"invite": invite, "deck_id": "starter_mage"},
                            headers={"X-Friend-Gate": "1", "Origin": SITE}, timeout=10)
        self.assertEqual(res.status_code, 404)

    def test_everything_else_is_closed(self) -> None:
        legacy = requests.post(BASE + "/api/games", json={"p1_deck_id": "starter_mage", "p2_mode": "bot",
                                                           "p2_deck_choice": "starter_warrior"}, timeout=10).json()["game_id"]
        door = {"X-Friend-Gate": "1", "Origin": FRIEND}
        closed = [
            ("post", "/api/games", {"p2_mode": "friend"}),
            ("post", "/api/games", {"p2_mode": "bot"}),
            ("post", "/api/decks", {"name": "x", "hero_class": "MAGE", "cards": []}),
            ("delete", "/api/decks/anything", None),
            ("get", f"/api/games/{legacy}/state?seat=p1", None),
            ("get", f"/api/games/{legacy}/cli_text", None),
            ("get", f"/api/games/{legacy}/wait", None),
            ("post", f"/api/games/{legacy}/end_turn", {"seat": "p1"}),
            ("post", f"/api/games/{legacy}/p2_deck", {"deck_id": "starter_mage"}),
            ("post", f"/api/games/{legacy}/switch_mode", {"mode": "bot"}),
            ("get", "/api/games/latest/state?seat=p1", None),
            ("get", "/api/app/latest", None),
            ("get", "/lanternfall-0.2.0.apk", None),
        ]
        for method, path, body in closed:
            with self.subTest(f"{method} {path}"):
                res = requests.request(method, BASE + path, json=body, headers=door, timeout=10)
                self.assertEqual(res.status_code, 404)
        listed = requests.get(BASE + "/api/games", headers=door, timeout=10).json()["games"]
        self.assertNotIn(legacy, [g["game_id"] for g in listed])
        with self.assertRaises(Exception):
            with ws_connect(f"ws://127.0.0.1:{PORT}/ws/{legacy}/p1", additional_headers=door) as ws:
                ws.recv(timeout=5)
        # Without the door the same match is still there for the site.
        self.assertEqual(requests.get(f"{BASE}/api/games/{legacy}/state?seat=p1", timeout=10).status_code, 200)

    def test_the_game_itself_opens_at_the_door(self) -> None:
        for path in ("/api/health", "/api/cards", "/api/decks", "/"):
            with self.subTest(path):
                self.assertEqual(requests.get(BASE + path, headers=DOOR, timeout=10).status_code, 200)


if __name__ == "__main__":
    unittest.main()
