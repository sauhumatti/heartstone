from __future__ import annotations

import asyncio
import json
import os
import unittest

os.environ.setdefault("GAME_NO_PERSIST", "1")

from engine.catalog import COLLECTIBLE_CARDS  # noqa: E402
from engine.game import GameEngine  # noqa: E402
from engine.models import CardInstance  # noqa: E402
from data.starter_decks import STARTER_DECKS  # noqa: E402
from server import agent  # noqa: E402
from server.manager import GameManager  # noqa: E402


def plain_minions(max_cost: int = 2) -> list[str]:
    """Card ids of cheap minions with no text, so playing them has no side effects."""
    return sorted(
        c.id
        for c in COLLECTIBLE_CARDS.values()
        if c.type == "MINION" and c.cost <= max_cost and not c.mechanics and not c.text
    )


def duel(seed: int = 4, human: str = "Zyxwv") -> GameEngine:
    eng = GameEngine.create_game(
        p1_name=human,
        p1_class="MAGE",
        p1_deck=STARTER_DECKS["MAGE"]["cards"],
        p1_deck_name="Mage",
        p2_name="Antigravity",
        p2_class="WARRIOR",
        p2_deck=STARTER_DECKS["WARRIOR"]["cards"],
        p2_deck_name="Warrior",
        mode="agent_vs_human",
        rng_seed=seed,
    )
    eng.submit_mulligan("p1", [])
    eng.submit_mulligan("p2", [])
    return eng


def give_turn_to_agent(eng: GameEngine) -> None:
    if eng.state.active_seat == "p1":
        eng.end_turn("p1")


class Scripted:
    """Stands in for the CLI: answers from a list, remembers what it was asked."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.models: list[str] = []

    async def __call__(self, prompt: str, model: str) -> dict:
        self.prompts.append(prompt)
        self.models.append(model)
        nxt = self.answers.pop(0) if self.answers else ["end"]
        if isinstance(nxt, Exception):
            raise nxt
        if callable(nxt):
            nxt = nxt(prompt)
        return {"commands": list(nxt), "say": ""}


async def noop() -> None:
    return None


class TestAnswerParsing(unittest.TestCase):
    def test_cli_envelope_with_structured_output(self) -> None:
        raw = json.dumps({
            "status": "SUCCESS",
            "response": "play 1\nend",
            "structured_output": {"commands": ["play 1", "end"], "say": "Your move."},
        })
        self.assertEqual(agent.parse_answer(raw), {"commands": ["play 1", "end"], "say": "Your move."})

    def test_plain_lines_are_accepted_too(self) -> None:
        got = agent.parse_answer("I will do this:\n`./hs play 0 --target e1`\nattack m0 enemy_hero\nend\n")
        self.assertEqual(got["commands"], ["./hs play 0 --target e1", "attack m0 enemy_hero", "end"])

    def test_nonsense_is_an_error(self) -> None:
        with self.assertRaises(agent.AgentError):
            agent.parse_answer("I am not sure what to do.")
        with self.assertRaises(agent.AgentError):
            agent.parse_answer(json.dumps({"status": "TIMEOUT", "response": ""}))


class TestWhatTheAgentSees(unittest.TestCase):
    def test_prompt_holds_only_its_own_side_and_no_player_name(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        view = eng.serialize_for_seat("p2")
        prompt = agent.build_prompt(view)
        mine = {c["name"] for c in view["me"]["hand"]}
        for c in view["me"]["hand"]:
            self.assertIn(c["name"], prompt)
        shown = mine | {m["name"] for m in view["me"]["board"] + view["opponent"]["board"]}
        secret = {c["name"] for c in eng.serialize_for_seat("p1")["me"]["hand"]} - shown
        self.assertTrue(secret)
        for name in secret:
            self.assertNotIn(name, prompt)
        self.assertNotIn("Zyxwv", prompt)
        self.assertIn("It is your turn.", prompt)

    def test_legal_moves_are_spelled_out_with_aliases(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        p2 = eng.state.players["p2"]
        p2.mana = p2.max_mana = 10
        m = eng.summon_minion("p2", plain_minions()[0])
        m.summoned_this_turn = False
        eng.summon_minion("p1", plain_minions()[1])
        eng.recompute_auras()
        moves = agent.legal_moves(eng.serialize_for_seat("p2"))
        attack = next(x for x in moves if x.startswith("attack m0"))
        self.assertIn("e0", attack)
        self.assertIn("enemy_hero", attack)
        self.assertEqual(moves[-1], "end")

    def test_opening_questions(self) -> None:
        eng = GameEngine.create_game("P", "MAGE", STARTER_DECKS["MAGE"]["cards"], "Mage", mode="agent_vs_human", rng_seed=1)
        self.assertIn("deck WARRIOR", agent.build_prompt(eng.serialize_for_seat("p2")))
        snap = agent.Snapshot.of(eng.serialize_for_seat("p2"))
        agent.run_command(eng, snap, "deck warrior")
        self.assertEqual(eng.state.phase, "MULLIGAN")
        self.assertIn("mulligan none", agent.build_prompt(eng.serialize_for_seat("p2")))


class TestPlayingAnswers(unittest.TestCase):
    def test_indices_mean_the_table_as_it_was_shown(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        p2 = eng.state.players["p2"]
        p2.mana = p2.max_mana = 10
        a, b = plain_minions()[:2]
        p2.hand = [
            CardInstance(uid="t_a", card_id=a),
            CardInstance(uid="t_b", card_id=b),
            CardInstance(uid="t_c", card_id=a),
        ]
        script = Scripted(["play 0", "play 1", "end"])
        result = asyncio.run(agent.take_turn(eng, "m", noop, ask=script))
        # "play 1" meant the second card shown, although it had moved to index 0 by then.
        self.assertEqual([c.uid for c in p2.hand if c.uid.startswith("t_")], ["t_c"])
        self.assertEqual([m.card_id for m in p2.board], [a, b])
        self.assertEqual(eng.state.active_seat, "p1")
        self.assertEqual(result, {"asks": 1, "moves": 3})

    def test_a_rejected_command_is_reported_and_the_agent_is_asked_again(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        script = Scripted(["attack m3 e5", "end"], ["end"])
        asyncio.run(agent.take_turn(eng, "m", noop, ask=script))
        self.assertEqual(len(script.prompts), 2)
        self.assertIn("`attack m3 e5` was rejected", script.prompts[1])
        self.assertEqual(eng.state.active_seat, "p1")

    def test_leaving_out_end_gets_another_look(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        p2 = eng.state.players["p2"]
        p2.mana = p2.max_mana = 10
        p2.hand = [CardInstance(uid="t_a", card_id=plain_minions()[0])]
        script = Scripted(["play 0"], ["end"])
        asyncio.run(agent.take_turn(eng, "m", noop, ask=script))
        self.assertEqual(len(script.prompts), 2)
        self.assertIn("m0", script.prompts[1])  # the new minion is on the second table
        self.assertEqual(eng.state.active_seat, "p1")

    def test_an_agent_that_never_ends_is_cut_off(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        script = Scripted(*[["power"] for _ in range(20)])
        with self.assertRaises(agent.AgentError):
            asyncio.run(agent.take_turn(eng, "m", noop, ask=script))
        self.assertLessEqual(len(script.prompts), agent.MAX_ASKS_PER_TURN)

    def test_every_move_is_announced_as_it_happens(self) -> None:
        eng = duel()
        give_turn_to_agent(eng)
        seen: list[int] = []

        async def after() -> None:
            seen.append(eng.state.cp_seq)

        asyncio.run(agent.take_turn(eng, "m", after, ask=Scripted(["end"])))
        self.assertEqual(len(seen), 1)


class TestAgentSeatInTheManager(unittest.TestCase):
    def test_a_whole_opening_and_turn_through_the_manager(self) -> None:
        async def run() -> None:
            m = GameManager()
            m.ask_agent = Scripted(["deck HUNTER"], ["mulligan none"], ["end"], ["end"], ["end"])
            mg = await m.create_game(
                p1_deck_id="starter_mage", p2_mode="agent", p2_deck_choice="await_cli",
                p2_agent_model="gemini-4-hydrogen-low",
            )
            self.assertEqual(mg.engine.state.mode, "agent_vs_human")
            self.assertEqual(m.agent_status(mg)["model"], "gemini-4-hydrogen-low")
            await mg.agent_task  # picks a deck, then its opening hand
            eng = mg.engine
            self.assertEqual(eng.state.players["p2"].hero.card_class, "HUNTER")
            self.assertTrue(eng.state.players["p2"].mulligan_done)
            eng.submit_mulligan("p1", [])
            await m.notify(mg)
            m.kick_agent(mg)
            if mg.agent_task and not mg.agent_task.done():
                await mg.agent_task
            if eng.state.active_seat == "p1":
                eng.end_turn("p1")
                m.kick_agent(mg)
                await mg.agent_task
            self.assertEqual(eng.state.active_seat, "p1")
            self.assertFalse(m.agent_status(mg)["thinking"])
            self.assertEqual(m.agent_status(mg)["error"], "")
            self.assertEqual(set(m.ask_agent.models), {"gemini-4-hydrogen-low"})

        asyncio.run(run())

    def test_when_the_agent_fails_the_bot_stands_in(self) -> None:
        async def run() -> None:
            m = GameManager()
            m.ask_agent = Scripted(*[agent.AgentError("no answer") for _ in range(12)])
            mg = await m.create_game(p1_deck_id="starter_mage", p2_mode="agent", p2_deck_choice="starter_warrior")
            await mg.agent_task
            eng = mg.engine
            self.assertTrue(eng.state.players["p2"].mulligan_done)
            self.assertEqual(m.agent_status(mg)["error"], "no answer")
            eng.submit_mulligan("p1", [])
            m.kick_agent(mg)
            if mg.agent_task and not mg.agent_task.done():
                await mg.agent_task
            if eng.state.active_seat == "p1":
                eng.end_turn("p1")
                m.kick_agent(mg)
                await mg.agent_task
            self.assertEqual(eng.state.active_seat, "p1")  # the stand-in finished the turn
            self.assertTrue(any("did not answer" in e["text"] for e in eng.state.log))

        asyncio.run(run())

    def test_switching_away_stops_the_agent_from_acting(self) -> None:
        async def run() -> None:
            m = GameManager()
            started = asyncio.Event()
            release = asyncio.Event()

            async def slow(prompt: str, model: str) -> dict:
                started.set()
                await release.wait()
                return {"commands": ["mulligan 0 1 2"], "say": ""}

            m.ask_agent = slow
            mg = await m.create_game(p1_deck_id="starter_mage", p2_mode="agent", p2_deck_choice="starter_warrior")
            await started.wait()
            self.assertTrue(m.agent_status(mg)["thinking"])
            mg.engine.state.mode = "cli_vs_human"  # the human hands the seat to someone else
            release.set()
            await mg.agent_task
            self.assertFalse(mg.engine.state.players["p2"].mulligan_done)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
