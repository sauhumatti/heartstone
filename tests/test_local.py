"""The game without a server (engine/local.py): whole matches, the same replies
the server gives, saving and restoring, and nothing leaked about the other hand."""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import unittest
from typing import Any, Optional

os.environ.setdefault("GAME_NO_PERSIST", "1")

from data.starter_decks import ALL_BUILTIN_DECKS, STARTER_DECKS
from engine import local
from engine.game import GameError
from engine.local import LocalHost


class Table:
    """Plays the player's seat the way the page does: every reply and every
    push has to continue exactly where the last one stopped."""

    def __init__(self, host: LocalHost, **create: Any) -> None:
        self.host = host
        self.received: list[dict[str, Any]] = []
        first = host.create_game(**create)
        self.gid = first["game_id"]
        self.seq = 0
        self.view: dict[str, Any] = {}
        self.take(first)

    def take(self, payload: dict[str, Any]) -> None:
        assert payload["beats"] is not None, "the caller's position was lost"
        for beat in payload["beats"]:
            assert beat["prev"] == self.seq, (beat["prev"], self.seq)
            self.seq = beat["seq"]
        assert payload["state"]["seq"] == self.seq
        self.view = payload["state"]
        self.received.append(payload)

    def do(self, method: str, **args: Any) -> None:
        self.take(getattr(self.host, method)(self.gid, since=self.seq, **args))

    def opponent(self) -> int:
        """What the worker does: one decision, then tell the page, until the player is up."""
        n = 0
        while self.host.opponent_step(self.gid):
            self.take(self.host.state(self.gid, self.seq))
            n += 1
            assert n < 500
        return n

    def my_turn(self, limit: int = 30) -> None:
        """A plain player: plays what it can, attacks with everything, ends the turn."""
        for _ in range(limit):
            v = self.view
            if v["phase"] != "PLAY" or not v["your_turn"]:
                return
            if v["pending_choice"]:
                self.do("choose", option_index=0)
                continue
            card = next((c for c in v["me"]["hand"] if c["can_play"] and not c["choose_options"] and (not c["target_required"] or c["valid_targets"])), None)
            if card is not None:
                target = card["valid_targets"][0] if card["valid_targets"] else None
                try:
                    self.do("play", hand_index=card["index"], target_id=target)
                    continue
                except GameError:
                    pass
            attacker = next((m for m in v["me"]["board"] if m["can_attack"] and m.get("legal_attack_targets")), None)
            if attacker is not None:
                targets = attacker["legal_attack_targets"]
                enemy_hero = v["opponent"]["hero"]["id"]
                self.do("attack", attacker_id=attacker["uid"], target_id=enemy_hero if enemy_hero in targets else targets[0])
                continue
            break
        if self.view["phase"] == "PLAY" and self.view["your_turn"] and not self.view["pending_choice"]:
            self.do("end_turn")

    def play_out(self, max_turns: int = 120) -> None:
        if self.view["phase"] == "MULLIGAN":
            self.opponent()
            self.do("mulligan", replace_indices=[0])
        for _ in range(max_turns * 2):
            if self.view["phase"] == "GAME_OVER":
                return
            self.opponent()
            self.my_turn()
        if self.view["phase"] != "GAME_OVER":
            self.do("concede")


def one_action(engine: Any, seat: str, level: str = "normal", budget_ms: int = 0, rng: Any = None) -> bool:
    """A stand-in opponent that keeps the contract of engine.ai.step and is the same every time."""
    st = engine.state
    if st.phase == "MULLIGAN":
        if st.players[seat].mulligan_done:
            return False
        engine.submit_mulligan(seat, [])
        return True
    if st.phase != "PLAY":
        return False
    if st.pending_choice is not None:
        if st.pending_choice.seat != seat:
            return False
        engine.resolve_pending_choice(seat, 0)
        return True
    if st.active_seat != seat:
        return False
    view = engine.serialize_for_seat(seat)
    for m in view["me"]["board"]:
        if m["can_attack"] and m.get("legal_attack_targets"):
            engine.attack(seat, m["uid"], sorted(m["legal_attack_targets"])[0])
            return True
    for c in view["me"]["hand"]:
        if c["can_play"] and c["type"] == "MINION" and not c["choose_options"] and not c["target_required"]:
            engine.play_card(seat, c["index"])
            return True
    engine.end_turn(seat)
    return True


def skeleton(value: Any) -> Any:
    """A value reduced to its shape: key names and kinds, not contents."""
    if isinstance(value, dict):
        # what an event carries depends on its kind; what every event has is checked instead
        return {k: ([{"seq": "number", "t": "str"}] if k == "events" and v else skeleton(v)) for k, v in value.items()}
    if isinstance(value, list):
        merged: Any = None
        for item in value:
            merged = merge(merged, skeleton(item))
        return [merged]
    if value is None:
        return None
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def merge(a: Any, b: Any) -> Any:
    if a is None:
        return b
    if b is None:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: merge(a.get(k), b.get(k)) for k in {*a, *b}}
    if isinstance(a, list) and isinstance(b, list):
        return [merge(a[0], b[0])]
    return a


def differences(a: Any, b: Any, path: str = "") -> list[str]:
    """Where two shapes disagree. An absent value (null, empty list) agrees with anything."""
    if a is None or b is None or a == [None] or b == [None]:
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f"{path}.{k}: only on one side" for k in set(a) ^ set(b)]
        for k in set(a) & set(b):
            out += differences(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        return differences(a[0], b[0], path + "[]")
    return [] if a == b else [f"{path}: {a!r} vs {b!r}"]


class WholeMatches(unittest.TestCase):
    def test_every_starter_deck_plays_to_the_end(self) -> None:
        host = LocalHost()
        for i, cls in enumerate(STARTER_DECKS):
            with self.subTest(deck=cls):
                t = Table(host, p1_deck_id=STARTER_DECKS[cls]["id"], level=local.level_ids()[i % len(local.level_ids())], seed=100 + i)
                self.assertTrue(t.gid.startswith(local.ID_PREFIX))
                self.assertEqual(t.view["mode"], local.MODE)
                t.play_out()
                self.assertEqual(t.view["phase"], "GAME_OVER")
                self.assertIn(t.view["winner"], ("p1", "p2", "draw"))
                last = t.received[-1]
                self.assertFalse(last["agent"]["thinking"])
                self.assertEqual(json.loads(json.dumps(last)), last)  # all of it survives the trip to the page

    def test_the_opponent_moves_one_decision_at_a_time(self) -> None:
        host = LocalHost(think=one_action)
        t = Table(host, p1_deck_id="starter_hunter", p2_deck_choice="starter_warrior", seed=3)
        self.assertEqual(t.opponent(), 1)  # its mulligan
        t.do("mulligan", replace_indices=[])
        turns = 0
        while t.view["phase"] == "PLAY" and turns < 8:
            before = len(t.received)
            steps = t.opponent()
            # every decision reached the page as its own reply, each with something to show
            self.assertEqual(len(t.received) - before, steps)
            for p in t.received[before:]:
                self.assertGreaterEqual(len(p["beats"]), 1)
            t.my_turn()
            turns += 1
        self.assertGreater(turns, 3)

    def test_custom_decks_are_checked(self) -> None:
        host = LocalHost()
        cards = list(STARTER_DECKS["PRIEST"]["cards"])
        ok = host.create_game(p1_class="PRIEST", p1_cards=cards, p1_deck_name="Mine", p2_class="MAGE", p2_cards=list(STARTER_DECKS["MAGE"]["cards"]))
        self.assertEqual(ok["state"]["me"]["deck_name"], "Mine")
        self.assertEqual(ok["state"]["opponent"]["hero"]["card_class"], "MAGE")
        with self.assertRaises(GameError):
            host.create_game(p1_class="PRIEST", p1_cards=cards[:29])
        with self.assertRaises(GameError):
            host.create_game(p1_class="MAGE", p1_cards=cards)
        with self.assertRaises(GameError):
            host.create_game(p1_deck_id="no_such_deck")


class WhenTheOpponentFails(unittest.TestCase):
    def play(self, think: Any) -> Table:
        t = Table(LocalHost(think=think), p1_deck_id="starter_mage", p2_deck_choice="starter_paladin", seed=9)
        with contextlib.redirect_stderr(io.StringIO()):  # the host reports what went wrong; not wanted here
            t.opponent()
            t.do("mulligan", replace_indices=[])
            for _ in range(6):
                if t.view["phase"] != "PLAY":
                    break
                t.opponent()
                self.assertTrue(t.view["your_turn"] or t.view["phase"] == "GAME_OVER")
                t.my_turn()
        return t

    def test_it_raises(self) -> None:
        def broken(*_a: Any, **_k: Any) -> bool:
            raise RuntimeError("boom")

        t = self.play(broken)
        self.assertTrue(any("stopped" in p["agent"]["error"] for p in t.received))

    def test_it_says_it_moved_but_did_not(self) -> None:
        t = self.play(lambda *_a, **_k: True)
        self.assertTrue(any(p["agent"]["error"] for p in t.received))

    def test_it_declines(self) -> None:
        self.play(lambda *_a, **_k: False)

    def test_it_never_ends_its_turn(self) -> None:
        def fidgets(engine: Any, seat: str, **_k: Any) -> bool:
            if engine.state.phase == "MULLIGAN":
                engine.submit_mulligan(seat, [])
            else:
                engine.send_emote(seat, "hm")
                engine.emit("turn_note", seat=seat)  # looks like progress
                engine.checkpoint()
            return True

        self.play(fidgets)

    def test_without_the_opponent_module_the_bot_plays(self) -> None:
        host = LocalHost()
        host._think = None
        self.assertFalse(host.info()["ai"])
        t = Table(host, p1_deck_id="starter_druid", seed=4)
        t.play_out()
        self.assertEqual(t.view["phase"], "GAME_OVER")


class SameRepliesAsTheServer(unittest.TestCase):
    def test_shape_matches_the_server(self) -> None:
        try:
            from server import app as server_app
        except Exception as exc:  # the web server's own packages are not installed here
            self.skipTest(f"server not importable: {exc}")
        manager = server_app.manager

        async def online() -> list[dict[str, Any]]:
            out = []
            mg = await manager.create_game(p1_name="A", p1_deck_id="starter_hunter", p2_mode="bot", p2_deck_choice="starter_warrior")
            eng = mg.engine
            out.append(server_app._payload(mg, "p1", 0))
            since = eng.state.cp_seq
            eng.submit_mulligan("p1", [0])
            await manager.maybe_step_bot(mg)
            out.append(server_app._payload(mg, "p1", since))
            for _ in range(12):
                if eng.state.phase != "PLAY":
                    break
                since = eng.state.cp_seq
                if eng.state.active_seat == "p1":
                    view = eng.serialize_for_seat("p1")
                    card = next((c for c in view["me"]["hand"] if c["can_play"] and not c["target_required"] and not c["choose_options"]), None)
                    if card:
                        eng.play_card("p1", card["index"])
                        out.append(server_app._payload(mg, "p1", since))
                        since = eng.state.cp_seq
                    if eng.state.pending_choice is not None:
                        eng.resolve_pending_choice("p1", 0)
                    eng.end_turn("p1")
                await manager.maybe_step_bot(mg)
                out.append(server_app._payload(mg, "p1", since))
            # the status an opponent that thinks would carry
            eng.state.mode = "agent_vs_human"
            out.append({"agent": manager.agent_status(mg)})
            manager.games.pop(eng.state.game_id, None)
            return out

        server_replies = asyncio.run(online())

        t = Table(LocalHost(), p1_deck_id="starter_hunter", p2_deck_choice="starter_warrior", seed=21)
        t.play_out(max_turns=8)
        local_replies = t.received

        want: Any = None
        for p in server_replies:
            want = merge(want, skeleton(p))
        got: Any = None
        for p in local_replies:
            got = merge(got, skeleton(p))
        self.assertEqual(set(got), {"state", "beats", "agent", "game_id"})
        got.pop("game_id")  # only the reply to "create" carries it, on the server too
        self.assertEqual(differences(want, got), [])
        # and the parts that must be there are there on both sides
        for side in (want, got):
            self.assertIn("me", side["state"])
            self.assertEqual(set(side["beats"][0]), {"seq", "prev", "events", "state"})
            self.assertEqual(set(side["agent"]), {"model", "label", "thinking", "typing", "error", "rev"})

    def test_the_json_door(self) -> None:
        host = LocalHost()
        made = json.loads(host.call("create_game", json.dumps({"p1_deck_id": "starter_rogue", "seed": 2})))["ok"]
        gid = made["game_id"]
        refused = json.loads(host.call("play", json.dumps({"game_id": gid, "hand_index": 0})))
        self.assertIn("error", refused)
        self.assertNotIn("ok", refused)
        self.assertIn("error", json.loads(host.call("state", json.dumps({"game_id": "local_nope"}))))
        self.assertIn("error", json.loads(host.call("save", "{}")))  # bytes do not go through this door
        self.assertIn("error", json.loads(host.call("__init__", "{}")))
        for beat in made["beats"]:
            for ev in beat["events"]:
                self.assertIn("seq", ev)
                self.assertIn("t", ev)
        self.assertTrue(json.loads(host.call("opponent_pending", json.dumps({"game_id": gid})))["ok"])
        self.assertEqual(json.loads(host.call("games"))["ok"]["latest_game_id"], gid)
        cat = json.loads(host.call("catalog"))["ok"]
        self.assertGreater(len(cat["cards"]), 100)
        self.assertEqual(len(json.loads(host.call("decks"))["ok"]["decks"]), len(ALL_BUILTIN_DECKS))


class SavedMatches(unittest.TestCase):
    def test_a_match_survives_being_closed(self) -> None:
        a = Table(LocalHost(think=one_action), p1_deck_id="starter_shaman", p2_deck_choice="starter_priest", seed=11)
        a.opponent()
        a.do("mulligan", replace_indices=[1])
        for _ in range(5):
            a.opponent()
            a.my_turn()
        blob = a.host.save(a.gid)
        self.assertIsInstance(blob, bytes)

        fresh = LocalHost(think=one_action)
        summary = fresh.restore(blob)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["game_id"], a.gid)
        self.assertEqual(summary["turn_number"], a.view["turn_number"])
        self.assertEqual(fresh.games()["latest_game_id"], a.gid)
        # the page picks up exactly where it was: nothing to replay, same table
        again = fresh.state(a.gid, a.seq)
        self.assertEqual(again["beats"], [])
        self.assertEqual(again["state"], a.host.state(a.gid, a.seq)["state"])

        # from here both copies play the same match, card for card
        b = Table.__new__(Table)
        b.host, b.gid, b.seq, b.view, b.received = fresh, a.gid, a.seq, again["state"], []
        for t in (a, b):
            for _ in range(60):
                if t.view["phase"] == "GAME_OVER":
                    break
                t.opponent()
                t.my_turn()
        self.assertEqual(a.view["phase"], "GAME_OVER")
        self.assertEqual(a.view["winner"], b.view["winner"])
        self.assertEqual(a.view["me"]["hero"], b.view["me"]["hero"])
        self.assertEqual(a.seq, b.seq)

    def test_closed_while_the_opponent_was_thinking(self) -> None:
        a = Table(LocalHost(think=one_action), p1_deck_id="starter_warlock", p2_deck_choice="starter_hunter", seed=5)
        a.opponent()
        a.do("mulligan", replace_indices=[])
        a.opponent()
        a.my_turn()
        self.assertTrue(a.host.opponent_step(a.gid))  # one decision into its turn
        fresh = LocalHost(think=one_action)
        self.assertIsNotNone(fresh.restore(a.host.save(a.gid)))
        self.assertTrue(fresh.opponent_pending(a.gid))
        self.assertTrue(fresh.state(a.gid, None)["agent"]["thinking"])
        fresh.run_opponent(a.gid)
        self.assertTrue(fresh.state(a.gid, None)["state"]["your_turn"])

    def test_bad_saves_are_refused(self) -> None:
        host = LocalHost()
        self.assertIsNone(host.restore(b""))
        self.assertIsNone(host.restore(b"not a save"))
        t = Table(LocalHost(), p1_deck_id="starter_mage", seed=1)
        import pickle

        data = pickle.loads(t.host.save(t.gid))
        data["v"] = local.SAVE_VERSION + 1
        self.assertIsNone(host.restore(pickle.dumps(data)))
        self.assertEqual(host.games()["games"], [])
        t.host.forget(t.gid)
        self.assertEqual(t.host.games(), {"games": [], "latest_game_id": None})

    def test_saves_an_update_left_behind_are_dropped_with_a_reason(self) -> None:
        import pickle

        t = Table(LocalHost(think=one_action), p1_deck_id="starter_mage", seed=3)
        t.opponent()
        t.do("mulligan", replace_indices=[])
        good = t.host.save(t.gid)
        data = pickle.loads(good)

        # (what is wrong with the save, the save)
        cases = []
        cases.append(("nothing there", b""))
        cases.append(("not a save", b"not a save"))
        cases.append(("an older save format", pickle.dumps({**data, "v": local.SAVE_VERSION - 1})))
        # the save lacks something this version of the engine keeps for every player
        broken = pickle.loads(good)
        del broken["state"].players["p1"].__dict__["hand"]
        cases.append(("a state that no longer fits", pickle.dumps(broken)))
        # the save names a class this version of the engine no longer has
        cases.append(("a class that is gone", good.replace(b"GameState", b"GameStatf")))
        cases.append(("not a dictionary", pickle.dumps(["v", 1])))
        cases.append(("cut short", good[: len(good) // 2]))

        for what, blob in cases:
            host = LocalHost(think=one_action)
            self.assertIsNone(host.restore(blob), what)
            self.assertEqual(host.games(), {"games": [], "latest_game_id": None}, what)
            notices = host.take_notices()["notices"]
            self.assertEqual(len(notices), 1, what)
            self.assertIn(notices[0], (local.GONE_OLDER, local.GONE_UNREADABLE), what)
            self.assertEqual(host.take_notices(), {"notices": []}, what)  # said once
            # and the host is as usable as before
            fresh = Table(host, p1_deck_id="starter_mage", seed=4)
            self.assertEqual(fresh.view["phase"], "MULLIGAN", what)

        # several bad saves at one start: one sentence each kind, not one per save
        host = LocalHost()
        for _ in range(3):
            host.restore(b"junk")
        self.assertEqual(host.take_notices()["notices"], [local.GONE_UNREADABLE])
        self.assertEqual(json.loads(host.call("take_notices")), {"ok": {"notices": []}})

    def test_a_match_from_before_an_update_that_breaks_in_play_is_let_go(self) -> None:
        import pickle

        t = Table(LocalHost(think=one_action), p1_deck_id="starter_mage", p2_deck_choice="starter_hunter", seed=9)
        t.opponent()
        t.do("mulligan", replace_indices=[])
        t.opponent()
        blob = t.host.save(t.gid)
        self.assertEqual(pickle.loads(blob)["engine"], local.engine_tag())

        # saved under the same rules: a failure in play is reported, and the match stays
        same = LocalHost(think=one_action)
        self.assertIsNotNone(same.restore(blob))
        self.assertFalse(same.matches[t.gid].older)

        def boom(*_a: object, **_k: object) -> None:
            raise AttributeError("'Minion' object has no attribute 'new_field'")

        same.matches[t.gid].engine.end_turn = boom  # type: ignore[method-assign]
        res = json.loads(same.call("end_turn", json.dumps({"game_id": t.gid})))
        self.assertNotIn("gone", res)
        self.assertIn("error", res)
        self.assertIn(t.gid, same.matches)

        # saved under other rules (an update came in between): the same failure lets the match go
        data = pickle.loads(blob)
        data["engine"] = "0000000000000000"
        older = LocalHost(think=one_action)
        self.assertIsNotNone(older.restore(pickle.dumps(data)))
        self.assertTrue(older.matches[t.gid].older)
        self.assertEqual(older.take_notices(), {"notices": []})  # it loaded: nothing to say yet
        # as long as it works it is an ordinary match
        self.assertIn("ok", json.loads(older.call("state", json.dumps({"game_id": t.gid}))))
        older.matches[t.gid].engine.end_turn = boom  # type: ignore[method-assign]
        res = json.loads(older.call("end_turn", json.dumps({"game_id": t.gid})))
        self.assertEqual(res["error"], local.GONE_OLDER)
        self.assertEqual(res["gone"], t.gid)
        self.assertNotIn(t.gid, older.matches)
        self.assertEqual(older.games(), {"games": [], "latest_game_id": None})
        # the page's next request for it is an ordinary refusal, not a crash
        self.assertIn("not found", json.loads(older.call("state", json.dumps({"game_id": t.gid})))["error"])
        # a save written from here on carries today's rules
        again = Table(older, p1_deck_id="starter_mage", seed=10)
        self.assertEqual(pickle.loads(older.save(again.gid))["engine"], local.engine_tag())


class NothingLeaks(unittest.TestCase):
    def test_the_other_hand_stays_hidden(self) -> None:
        host = LocalHost()
        for seed, cls in enumerate(("MAGE", "HUNTER", "PALADIN")):
            with self.subTest(deck=cls):
                t = Table(host, p1_deck_id=STARTER_DECKS[cls]["id"], seed=40 + seed)
                eng = host.matches[t.gid].engine
                t.opponent()
                t.do("mulligan", replace_indices=[0, 1])
                for _ in range(14):
                    if t.view["phase"] != "PLAY":
                        break
                    t.opponent()
                    t.my_turn()
                    # what the opponent holds now, and has never shown
                    shown = set()
                    for cp in eng.state.checkpoints:
                        for ev in cp["events"]:
                            if ev["t"] not in ("draw", "card_added", "mulligan"):
                                shown.update(str(v) for v in ev.values() if isinstance(v, str))
                                card = ev.get("card")
                                if isinstance(card, dict):
                                    shown.add(str(card.get("uid")))
                    hidden = {ci.uid for ci in eng.state.players["p2"].hand} - shown
                    text = json.dumps(t.received)
                    for uid in hidden:
                        self.assertNotIn(f'"{uid}"', text)
                for p in t.received:
                    self.assertNotIn("hand", p["state"]["opponent"])
                    for beat in p["beats"]:
                        self.assertNotIn("hand", beat["state"]["opponent"])
                        for ev in beat["events"]:
                            if ev["t"] in ("draw", "card_added") and ev.get("seat") == "p2":
                                self.assertNotIn("card", ev)
                                self.assertNotIn("uid", ev)
                # the replies are the engine's own view for the player's seat, nothing else
                now = host.state(t.gid, None)
                self.assertEqual(now["state"], eng.serialize_for_seat("p1"))
                self.assertIsNone(now["beats"])


if __name__ == "__main__":
    unittest.main()
