from __future__ import annotations

import os

os.environ.setdefault("GAME_NO_PERSIST", "1")  # test matches are not written to var/games

import subprocess
import sys
import tempfile
import threading
import time
import unittest

import requests
import uvicorn

from data.starter_decks import STARTER_DECKS
from engine.catalog import COLLECTIBLE_BY_NAME, COLLECTIBLE_CARDS, HEROES
from engine.effects import CHOOSE_ONE_OPTIONS, TARGET_RULES
from engine.game import GameEngine
from engine.models import CardInstance


class TestAll382CardsExecution(unittest.TestCase):
    def test_execute_every_collectible_card_in_engine(self) -> None:
        """Smoke-test playing every single one of the 382 collectible cards cleanly."""
        executed = set()
        for cid, card in sorted(COLLECTIBLE_CARDS.items()):
            eng = GameEngine.create_game(
                p1_name="P1",
                p1_class="MAGE",
                p1_deck=STARTER_DECKS["MAGE"]["cards"],
                p1_deck_name="Mage",
                p2_name="P2",
                p2_class="WARRIOR",
                p2_deck=STARTER_DECKS["WARRIOR"]["cards"],
                p2_deck_name="Warrior",
                rng_seed=99,
            )
            eng.submit_mulligan("p1", [])
            eng.submit_mulligan("p2", [])
            eng.state.active_seat = "p1"
            p1 = eng.state.players["p1"]
            p2 = eng.state.players["p2"]
            p1.mana = 10
            p1.max_mana = 10
            p1.hero.armor = 5
            p1.hero.temp_attack = 2
            eng.equip_weapon("p1", COLLECTIBLE_BY_NAME["Fiery War Axe"].id)
            eng.equip_weapon("p2", COLLECTIBLE_BY_NAME["Arcanite Reaper"].id)

            # Populate diverse minions so any targeting rule has valid candidates
            f1 = eng.summon_minion("p1", COLLECTIBLE_BY_NAME["River Crocolisk"].id)  # Beast 2/3
            f2 = eng.summon_minion("p1", COLLECTIBLE_BY_NAME["Blood Imp"].id)  # Demon 0/1
            f3 = eng.summon_minion("p1", COLLECTIBLE_BY_NAME["Bluegill Warrior"].id)  # Murloc 2/1
            f1.damage = 1  # damaged friendly minion

            e1 = eng.summon_minion("p2", COLLECTIBLE_BY_NAME["Sen'jin Shieldmasta"].id)  # Taunt 3/5
            e1.damage = 1  # damaged enemy minion (atk<=3)
            e2 = eng.summon_minion("p2", COLLECTIBLE_BY_NAME["Core Hound"].id)  # 9/5 Beast (atk>=7)
            e3 = eng.summon_minion("p2", COLLECTIBLE_BY_NAME["Shieldbearer"].id)  # 0/4 Taunt (atk<=2)
            e4 = eng.summon_minion("p2", COLLECTIBLE_BY_NAME["Murloc Raider"].id)  # 2/1 Murloc

            # Put card into hand with cost_mod = -20 so even Molten/Mountain Giant is playable
            ci = CardInstance(uid=eng._new_uid("c"), card_id=cid, cost_mod=-20)
            p1.hand.append(ci)
            h_idx = len(p1.hand) - 1

            if card.id in CHOOSE_ONE_OPTIONS:
                for opt_idx in (0, 1):
                    # Re-test each Choose One branch on fresh copy via fresh hand card
                    if opt_idx == 1:
                        ci2 = CardInstance(uid=eng._new_uid("c"), card_id=cid, cost_mod=-20)
                        p1.hand.append(ci2)
                        h_idx = len(p1.hand) - 1
                        p1.mana = 10
                    opt = CHOOSE_ONE_OPTIONS[card.id][opt_idx]
                    vt = eng.get_valid_targets("p1", opt.target_rule, is_spell_or_power=(card.type == "SPELL"))
                    tgt = vt[0] if vt else None
                    eng.play_card("p1", h_idx, target_id=tgt, choose=opt_idx)
                    if eng.state.pending_choice:
                        eng.resolve_pending_choice("p1", 0)
            else:
                rule = eng.get_target_rule(card.id, None, True)
                vt = eng.get_valid_targets("p1", rule, is_spell_or_power=(card.type == "SPELL"))
                tgt = vt[0] if vt else None
                eng.play_card("p1", h_idx, target_id=tgt)
                if eng.state.pending_choice:
                    eng.resolve_pending_choice("p1", 0)

            executed.add(cid)

        self.assertEqual(len(executed), len(COLLECTIBLE_CARDS))

    def test_all_9_hero_powers_execute(self) -> None:
        for cls in HEROES:
            eng = GameEngine.create_game(
                p1_name="P1",
                p1_class=cls,
                p1_deck=STARTER_DECKS[cls]["cards"],
                p1_deck_name=cls,
                p2_name="P2",
                p2_class="WARRIOR",
                p2_deck=STARTER_DECKS["WARRIOR"]["cards"],
                p2_deck_name="WARRIOR",
                rng_seed=5,
            )
            eng.submit_mulligan("p1", [])
            eng.submit_mulligan("p2", [])
            eng.state.active_seat = "p1"
            p1 = eng.state.players["p1"]
            p1.mana = 10
            p1.max_mana = 10
            p1.hero.hero_power_used = False
            rule = TARGET_RULES.get(p1.hero.hero_power_id, "NONE")
            vt = eng.get_valid_targets("p1", rule, is_spell_or_power=True)
            eng.use_hero_power("p1", target_id=(vt[0] if vt else None))
            self.assertTrue(p1.hero.hero_power_used)


class TestLiveServerAndCliE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from server.app import app

        cls.port = 18765
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        config = uvicorn.Config(app, host="127.0.0.1", port=cls.port, log_level="warning")
        cls.server = uvicorn.Server(config)
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        for _ in range(50):
            try:
                r = requests.get(f"{cls.base_url}/api/health", timeout=0.5)
                if r.ok:
                    break
            except Exception:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.should_exit = True
        cls.thread.join(timeout=3)

    def _run_cli(self, *args: str) -> str:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cmd = [os.path.join(root, "hs"), "--url", self.base_url, *args]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout

    def test_frontend_and_catalog_and_deck_crud(self) -> None:
        r_html = requests.get(self.base_url + "/", timeout=5)
        self.assertEqual(r_html.status_code, 200)
        self.assertIn('<div id="root">', r_html.text)

        r_art = requests.get(f"{self.base_url}/art/hero_MAGE.webp", timeout=5)
        self.assertEqual(r_art.status_code, 200)
        self.assertGreater(len(r_art.content), 1000)

        r_aud = requests.get(f"{self.base_url}/audio/tavern_theme.mp3", timeout=5)
        self.assertEqual(r_aud.status_code, 200)
        self.assertGreater(len(r_aud.content), 10000)

        r_cat = requests.get(f"{self.base_url}/api/cards", timeout=5).json()
        self.assertEqual(len(r_cat["cards"]), len(COLLECTIBLE_CARDS))
        self.assertEqual(len(r_cat["heroes"]), 9)

        # Save & delete custom deck
        cards30 = STARTER_DECKS["MAGE"]["cards"]
        r_save = requests.post(
            f"{self.base_url}/api/decks",
            json={"name": "E2E Mage", "hero_class": "MAGE", "cards": cards30},
            timeout=5,
        )
        self.assertEqual(r_save.status_code, 200)
        did = r_save.json()["deck"]["id"]

        r_del = requests.delete(f"{self.base_url}/api/decks/{did}", timeout=5)
        self.assertEqual(r_del.status_code, 200)

    def test_human_web_vs_antigravity_cli_match(self) -> None:
        # 1. Human creates game awaiting Antigravity deck via CLI
        r_create = requests.post(
            f"{self.base_url}/api/games",
            json={
                "p1_name": "HumanTester",
                "p1_deck_id": "starter_mage",
                "p2_mode": "cli",
                "p2_deck_choice": "await_cli",
            },
            timeout=5,
        )
        self.assertEqual(r_create.status_code, 200)
        gid = r_create.json()["game_id"]
        self.assertEqual(r_create.json()["state"]["phase"], "WAITING_FOR_P2_DECK")

        # 2. Antigravity picks deck via ./hs CLI
        out = self._run_cli("--game", gid, "deck", "HUNTER")
        self.assertIn("Phase: MULLIGAN", out)

        # 3. Both submit mulligan (P1 via API, P2 via ./hs CLI)
        requests.post(
            f"{self.base_url}/api/games/{gid}/mulligan",
            json={"seat": "p1", "replace_indices": [0]},
            timeout=5,
        ).raise_for_status()
        out = self._run_cli("--game", gid, "mulligan", "none")
        self.assertIn("Phase: PLAY", out)

        # 4. Check fair-play API state for P2 does not expose P1 hand
        p2_state = requests.get(f"{self.base_url}/api/games/{gid}/state?seat=p2", timeout=5).json()["state"]
        self.assertNotIn("hand", p2_state["opponent"])
        self.assertNotIn("deck", p2_state["opponent"])

        # 5. If P1 is active, P1 ends turn -> P2 waits and becomes active
        if p2_state["active_seat"] == "p1":
            requests.post(f"{self.base_url}/api/games/{gid}/end_turn", json={"seat": "p1"}, timeout=5).raise_for_status()

        wait_out = self._run_cli("--game", gid, "wait", "--timeout", "2")
        self.assertIn("[ready=True]", wait_out)
        self.assertIn("YOUR TURN", wait_out)

        # 6. P2 sends emote and ends turn via CLI
        emote_out = self._run_cli("--game", gid, "emote", "Greetings, traveler!")
        self.assertIn("Greetings", emote_out)

        end_out = self._run_cli("--game", gid, "end")
        self.assertIn("OPPONENT TURN", end_out)

        # 7. Check P1 received emote & Turn advanced
        p1_state = requests.get(f"{self.base_url}/api/games/{gid}/state?seat=p1", timeout=5).json()["state"]
        self.assertEqual(p1_state["last_emote"]["text"], "Greetings, traveler!")
        self.assertEqual(p1_state["active_seat"], "p1")


if __name__ == "__main__":
    unittest.main()
