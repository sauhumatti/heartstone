from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GAME_NO_PERSIST", "1")

import requests  # noqa: E402
import uvicorn  # noqa: E402
from websockets.sync.client import connect as ws_connect  # noqa: E402
from websockets.exceptions import InvalidStatus  # noqa: E402

from server.app import app  # noqa: E402
from server.manager import GameManager  # noqa: E402

PORT = 18766
BASE = f"http://127.0.0.1:{PORT}"


class _Client:
    """The few calls the tests need, against the live test server."""

    def post(self, path: str, json: dict) -> requests.Response:
        return requests.post(BASE + path, json=json, timeout=10)

    def get(self, path: str) -> requests.Response:
        return requests.get(BASE + path, timeout=10)


class TestBeatsOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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

    def setUp(self) -> None:
        self.client = _Client()

    def new_bot_game(self) -> dict:
        res = self.client.post(
            "/api/games",
            json={"p1_name": "T", "p1_deck_id": "starter_mage", "p2_mode": "bot", "p2_deck_choice": "starter_warrior"},
        )
        self.assertEqual(res.status_code, 200)
        return res.json()

    def test_action_answers_with_the_beats_since_the_callers_position(self) -> None:
        created = self.new_bot_game()
        gid = created["game_id"]
        self.assertEqual(created["beats"][0]["events"][0]["t"], "game_start")
        since = created["state"]["seq"]

        res = self.client.post(f"/api/games/{gid}/mulligan", json={"seat": "p1", "since": since, "replace_indices": [0]})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        beats = body["beats"]
        self.assertTrue(beats)
        self.assertEqual(beats[0]["prev"], since)
        self.assertEqual(beats[-1]["seq"], body["state"]["seq"])
        kinds = [e["t"] for b in beats for e in b["events"]]
        self.assertIn("mulligan", kinds)
        self.assertIn("turn_start", kinds)
        # The practice bot may already have moved: every one of its actions is its own beat.
        for a, b in zip(beats, beats[1:]):
            self.assertEqual(b["prev"], a["seq"])

    def test_end_turn_carries_the_whole_bot_turn_as_separate_beats(self) -> None:
        created = self.new_bot_game()
        gid = created["game_id"]
        state = self.client.post(
            f"/api/games/{gid}/mulligan", json={"seat": "p1", "since": created["state"]["seq"], "replace_indices": []}
        ).json()["state"]
        if not state["your_turn"]:
            self.skipTest("bot moved first and has not handed the turn over")
        res = self.client.post(f"/api/games/{gid}/end_turn", json={"seat": "p1", "since": state["seq"]}).json()
        beats = res["beats"]
        self.assertGreaterEqual(len(beats), 2)
        self.assertEqual(beats[0]["events"][0]["t"], "turn_end")
        self.assertEqual(beats[-1]["events"][0]["t"], "turn_end")  # the bot handing the turn back
        self.assertTrue(res["state"]["your_turn"])
        # Nothing the bot drew is visible to the player.
        for b in beats:
            for e in b["events"]:
                if e["t"] == "draw" and e["seat"] == "p2":
                    self.assertNotIn("card", e)

    def test_state_without_a_position_asks_the_client_to_jump(self) -> None:
        created = self.new_bot_game()
        gid = created["game_id"]
        res = self.client.get(f"/api/games/{gid}/state?seat=p1").json()
        self.assertIsNone(res["beats"])
        res = self.client.get(f"/api/games/{gid}/state?seat=p1&since={res['state']['seq']}").json()
        self.assertEqual(res["beats"], [])

    def test_websocket_replays_from_the_given_position(self) -> None:
        created = self.new_bot_game()
        gid = created["game_id"]
        with ws_connect(f"ws://127.0.0.1:{PORT}/ws/{gid}/p1?since=0") as ws:
            first = json.loads(ws.recv(timeout=5))
            self.assertEqual(first["type"], "state")
            self.assertEqual(first["beats"][0]["events"][0]["t"], "game_start")
            self.client.post(
                f"/api/games/{gid}/mulligan",
                json={"seat": "p1", "since": first["state"]["seq"], "replace_indices": []},
            )
            pushed = json.loads(ws.recv(timeout=5))
            self.assertTrue(pushed["beats"])
            self.assertEqual(pushed["beats"][0]["prev"], first["state"]["seq"])

    def test_rejected_action_changes_nothing(self) -> None:
        created = self.new_bot_game()
        gid = created["game_id"]
        res = self.client.post(f"/api/games/{gid}/end_turn", json={"seat": "p1", "since": created["state"]["seq"]})
        self.assertEqual(res.status_code, 400)  # still in the opening-hand phase
        after = self.client.get(f"/api/games/{gid}/state?seat=p1&since={created['state']['seq']}").json()
        self.assertEqual(after["beats"], [])

    def test_friend_seats_are_private_and_resume_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder, requests.Session() as host, requests.Session() as guest:
            saves = Path(folder)
            with patch("server.app.manager", GameManager(persist_dir=saves)):
                created = host.post(BASE + "/api/games", json={"p2_mode": "friend"}, timeout=5)
            self.assertEqual(created.status_code, 200)
            self.assertIn("HttpOnly", created.headers["Set-Cookie"])
            self.assertIn("SameSite=strict", created.headers["Set-Cookie"])
            self.assertIn("no-store", created.headers["Cache-Control"])
            gid, invite = (created.json()[key] for key in ("game_id", "invite"))
            game_url = BASE + f"/api/games/{gid}"
            ws_url = f"ws://127.0.0.1:{PORT}/ws/{gid}"
            host_cookie = "; ".join(f"{key}={value}" for key, value in host.cookies.items())
            with patch("server.app.manager", GameManager(persist_dir=saves)):
                self.assertEqual(host.get(game_url + "/state", timeout=5).json()["state"]["phase"], "WAITING_FOR_P2_DECK")
                self.assertEqual(guest.get(BASE + "/api/games", timeout=5).json()["games"], [])
                for path in ("/state?seat=p2", "/cli_text", "/wait"):
                    self.assertEqual(host.get(game_url + path, timeout=5).status_code, 404)
                self.assertEqual(host.get(BASE + "/api/games/latest/state", timeout=5).status_code, 404)
                self.assertEqual(host.post(game_url + "/switch_mode", json={"mode": "bot"}, timeout=5).status_code, 404)
                self.assertEqual(host.post(game_url + "/p2_deck", json={"deck_id": "starter_mage"}, timeout=5).status_code, 404)
                self.assertEqual(host.post(game_url + "/concede", json={"seat": "p2"}, timeout=5).status_code, 404)
                self.assertEqual(host.post(
                    game_url + "/concede", json={"seat": "p1"}, headers={"Origin": "http://another-site.test"}, timeout=5,
                ).status_code, 404)
                self.assertEqual(guest.post(game_url + "/join", json={"invite": invite, "hero_class": "MAGE", "cards": []}, timeout=5).status_code, 400)
                for url, origin in ((f"{ws_url}/p2", BASE), (f"{ws_url}/p1", "http://another-site.test")):
                    with self.assertRaises(InvalidStatus):
                        ws_connect(url, origin=origin, additional_headers={"Cookie": host_cookie})
                with ws_connect(f"{ws_url}/p1", origin=BASE, additional_headers={"Cookie": host_cookie}) as ws:
                    self.assertEqual(json.loads(ws.recv(timeout=5))["state"]["viewer_seat"], "p1")
                    joined = guest.post(
                        game_url + "/join", json={"invite": invite, "deck_id": "starter_warrior", "name": "Guest"}, timeout=5,
                    )
                    self.assertEqual(joined.status_code, 200)
                    self.assertEqual(joined.json()["state"]["viewer_seat"], "p2")
                    self.assertEqual(json.loads(ws.recv(timeout=5))["state"]["phase"], "MULLIGAN")
            with patch("server.app.manager", GameManager(persist_dir=saves)):
                self.assertEqual(guest.get(BASE + "/api/games", timeout=5).json()["games"][0]["viewer_seat"], "p2")
                for seat, player, other in (("p1", host, guest), ("p2", guest, host)):
                    state = player.get(game_url + f"/state?seat={seat}", timeout=5).json()["state"]
                    self.assertTrue(state["me"]["hand"])
                    self.assertNotIn("hand", state["opponent"])
                    self.assertEqual(other.get(game_url + f"/state?seat={seat}", timeout=5).status_code, 404)
                    result = player.post(game_url + "/mulligan", json={"seat": seat}, timeout=5)
                    self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["state"]["phase"], "PLAY")
                self.assertEqual(requests.post(game_url + "/join", json={"invite": invite, "deck_id": "starter_mage"}, timeout=5).status_code, 404)

    def test_only_one_guest_can_claim_an_invitation(self) -> None:
        created = self.client.post("/api/games", json={"p2_mode": "friend"}).json()
        path = f"/api/games/{created['game_id']}/join"
        payload = {"invite": created["invite"], "deck_id": "starter_mage"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: self.client.post(path, payload), range(2)))
        self.assertEqual(sorted(res.status_code for res in replies), [200, 404])


class TestPersistence(unittest.TestCase):
    def test_a_match_survives_a_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "games"

            async def play() -> tuple[str, int, dict]:
                m = GameManager(persist_dir=folder)
                mg = await m.create_game(p1_deck_id="starter_mage", p2_mode="bot", p2_deck_choice="starter_hunter")
                mg.engine.submit_mulligan("p1", [])
                await m.maybe_step_bot(mg)
                await m.notify(mg)
                return mg.engine.state.game_id, mg.engine.state.cp_seq, mg.engine.serialize_for_seat("p1")

            gid, seq, view = asyncio.run(play())
            self.assertTrue((folder / f"{gid}.pkl").exists())

            revived = GameManager(persist_dir=folder)
            self.assertIn(gid, revived.games)
            self.assertEqual(revived.latest_game_id, gid)
            engine = revived.games[gid].engine
            self.assertEqual(engine.state.cp_seq, seq)
            again = engine.serialize_for_seat("p1")
            self.assertEqual(again["me"]["hand"], view["me"]["hand"])
            self.assertEqual(again["opponent"]["board"], view["opponent"]["board"])
            # The revived match can be played on, and a client can still replay recent beats.
            self.assertEqual(engine.beats_for_seat("p1", seq), [])
            if engine.state.active_seat == "p1":
                engine.end_turn("p1")
                self.assertGreater(engine.state.cp_seq, seq)

    def test_unreadable_saves_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "broken.pkl").write_bytes(b"not a save")
            m = GameManager(persist_dir=folder)
            self.assertEqual(m.games, {})


if __name__ == "__main__":
    unittest.main()
