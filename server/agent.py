"""An outside agent as the opponent.

The Antigravity CLI (`agy`) is asked what to do, move by move. It never runs
anything itself: it is shown the same fog-of-war table a command-line player
sees and answers with commands in the `./hs` grammar. The server checks each
command against the rules and plays it, so the agent can neither cheat nor
break the match.

Environment:
    AGENT_CMD      path of the CLI (default: `agy` on PATH or ~/.local/bin/agy)
    AGENT_MODEL    default model (default: gemini-4-hydrogen-medium)
    AGENT_TIMEOUT  seconds to wait for one answer (default: 90)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from data.starter_decks import STARTER_DECKS
from engine.cli_format import alias_of, format_state_for_cli, resolve_target
from engine.game import GameEngine, GameError

SEAT = "p2"
DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "gemini-4-hydrogen-medium")
MODELS: dict[str, str] = {
    "gemini-4-hydrogen-low": "Gemini 4 Hydrogen · quick",
    "gemini-4-hydrogen-medium": "Gemini 4 Hydrogen · balanced",
    "gemini-4-hydrogen-high": "Gemini 4 Hydrogen · careful",
    "gemini-4-hydrogen-xhigh": "Gemini 4 Hydrogen · deepest",
}
TIMEOUT = float(os.environ.get("AGENT_TIMEOUT", "90"))
# One turn may take several answers (the agent can ask to see a result first).
MAX_ASKS_PER_TURN = 6
MAX_COMMANDS_PER_ANSWER = 16

ANSWER_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "commands": {"type": "array", "items": {"type": "string"}},
        "say": {"type": "string"},
    },
    "required": ["commands"],
})

Ask = Callable[[str, str], Awaitable[dict[str, Any]]]


class AgentError(RuntimeError):
    pass


def agent_command() -> Optional[str]:
    explicit = os.environ.get("AGENT_CMD")
    if explicit:
        return explicit if Path(explicit).exists() or shutil.which(explicit) else None
    found = shutil.which("agy")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "agy"
    return str(local) if local.exists() else None


def model_label(model: str) -> str:
    return MODELS.get(model, model).split(" · ")[0]


_workdir: Optional[str] = None


def _empty_workdir() -> str:
    """The agent runs in an empty folder: nothing of the game is on disk there."""
    global _workdir
    if _workdir is None or not Path(_workdir).exists():
        _workdir = tempfile.mkdtemp(prefix="agent-seat-")
    return _workdir


async def ask_cli(prompt: str, model: str) -> dict[str, Any]:
    """One question to the CLI, one structured answer back."""
    return parse_answer(await _run_cli(prompt, model, ANSWER_SCHEMA))


async def _run_cli(prompt: str, model: str, schema: str) -> str:
    """Runs the CLI once and returns what it printed."""
    cmd = agent_command()
    if not cmd:
        raise AgentError("The Antigravity CLI (agy) is not installed on this machine.")
    proc = await asyncio.create_subprocess_exec(
        cmd,
        "--model", model,
        "--print-timeout", f"{int(TIMEOUT)}s",
        "--output-format", "json",
        "--json-schema", schema,
        "-p", prompt,
        cwd=_empty_workdir(),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT + 20)
    except asyncio.TimeoutError:
        proc.kill()
        raise AgentError("The agent took too long to answer.")
    text = out.decode("utf-8", "replace").strip()
    if proc.returncode != 0 and not text:
        tail = err.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no output"]
        raise AgentError(f"The agent CLI failed: {tail[0][:200]}")
    return text


def parse_answer(text: str) -> dict[str, Any]:
    """Accepts the CLI's JSON envelope, a bare JSON answer, or plain command lines."""
    data: Any = None
    try:
        data = json.loads(text)
    except ValueError:
        pass
    if isinstance(data, dict):
        if data.get("status") not in (None, "SUCCESS") and not data.get("structured_output"):
            raise AgentError(f"The agent did not finish its answer ({data.get('status')}).")
        answer = data.get("structured_output") or (data if "commands" in data else None)
        if isinstance(answer, dict) and isinstance(answer.get("commands"), list):
            return {
                "commands": [str(c) for c in answer["commands"]][:MAX_COMMANDS_PER_ANSWER],
                "say": str(answer.get("say") or "").strip(),
            }
        text = str(data.get("response") or "")
    lines = [ln.strip(" `") for ln in text.splitlines() if ln.strip(" `")]
    commands = [ln for ln in lines if re.match(r"^(\./)?(hs\s+)?(play|attack|power|pick|end|mulligan|deck|concede)\b", ln, re.I)]
    if not commands:
        raise AgentError("The agent's answer contained no commands.")
    return {"commands": commands[:MAX_COMMANDS_PER_ANSWER], "say": ""}


# ---------------------------------------------------------------------------
# What the agent is shown
# ---------------------------------------------------------------------------

def _neutral(view: dict[str, Any]) -> dict[str, Any]:
    """The same view with the players' own names left out of what is sent off the machine."""
    human = view["opponent"]["name"]
    mine = view["me"]["name"]
    v = dict(view)
    v["me"] = {**view["me"], "name": "You"}
    v["opponent"] = {**view["opponent"], "name": "Opponent"}
    log = []
    for entry in view.get("log", []):
        text = entry["text"]
        for name, label in ((human, "Opponent"), (mine, "You")):
            if name and len(name) > 1:
                text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", label, text)
        log.append({**entry, "text": text})
    v["log"] = log
    return v


def legal_moves(view: dict[str, Any]) -> list[str]:
    """Every move the rules allow right now, written the way it has to be typed."""
    me = view["me"]
    names = lambda ids: ", ".join(alias_of(view, t) for t in ids)  # noqa: E731
    out: list[str] = []
    for c in me["hand"]:
        if c["choose_options"]:
            for o in c["choose_options"]:
                if not (c["can_play"] and o["playable"]):
                    continue
                need = f" --target <{names(o['valid_targets'])}>" if o["valid_targets"] and o["target_rule"] != "NONE" else ""
                out.append(f"play {c['index']} --choose {o['index']}{need}    ({c['name']}: {o['label']})")
        elif c["can_play"]:
            need = f" --target <{names(c['valid_targets'])}>" if c["target_required"] else ""
            pos = " [--pos <0..%d>]" % len(me["board"]) if c["type"] == "MINION" and me["board"] else ""
            out.append(f"play {c['index']}{need}{pos}    ({c['name']}, {c['cost']} mana)")
    for m in me["board"]:
        if m["can_attack"] and m.get("legal_attack_targets"):
            out.append(f"attack {alias_of(view, m['uid'])} <{names(m['legal_attack_targets'])}>    ({m['name']} {m['attack']}/{m['health']})")
    hero = me["hero"]
    if hero.get("can_attack") and hero.get("legal_attack_targets"):
        out.append(f"attack hero <{names(hero['legal_attack_targets'])}>    (your hero, {hero['attack']} attack)")
    power = hero["hero_power"]
    if power.get("can_use"):
        targets = power.get("valid_targets") or []
        need = f" --target <{names(targets)}>" if power.get("target_rule", "NONE") != "NONE" and targets else ""
        out.append(f"power{need}    ({power['name']}, {power['cost']} mana)")
    out.append("end")
    if concede_allowed(view):
        out.append("concede    (give up the match: only when you see no way to win)")
    return out


# Giving up is offered only when things look dire, so a careless answer cannot throw away a match.
CONCEDE_HEALTH = 10


def concede_allowed(view: dict[str, Any]) -> bool:
    """At 10 health or less, or when the enemy's board alone could finish the agent next turn."""
    if view.get("phase") != "PLAY":
        return False
    hero = view["me"]["hero"]
    health = (hero.get("hp") or 0) + (hero.get("armor") or 0)
    opp = view["opponent"]
    weapon = (opp.get("weapon") or {}).get("attack") or 0
    threat = sum(max(0, m.get("attack") or 0) for m in opp["board"]) + max(weapon, opp["hero"].get("attack") or 0)
    return health <= CONCEDE_HEALTH or threat >= health


PLAY_RULES = """Commands
  play <hand index> [--pos <slot>] [--target <target>] [--choose <0|1>]
  attack <attacker> <target>
  power [--target <target>]
  end
  concede    (only when it is listed as allowed below)
Targets: enemy_hero, hero (your own), e0 e1 ... (enemy minions as listed), m0 m1 ... (your minions as listed).

How your answer is used
- Indices and names mean the table as shown here, even after your earlier commands have changed it.
- Commands run one at a time. If one is rejected, the rest are dropped and you are shown the table again.
- Finish with `end`. Leave it out only when you want to see a result first (a drawn card, a new minion); you are then asked again.
- Mana does not carry over, and a card or attack you leave unused is simply not used.
- "say" is optional: one short remark to your opponent, at most 60 characters. Leave it empty on most turns.
- `concede` gives up the match. It is offered only when things look dire; use it only when you are sure you
  cannot win (for example, the enemy can finish you next turn and nothing you hold can stop it). A gracious
  word in "say" is welcome when you do."""

PREAMBLE = (
    "You are playing a two-player card duel and you want to win. Everything you are allowed to know is in "
    "this message: do not use tools or files, just answer through the structured answer. "
    '"commands" is the list of commands to run now, in order.'
)


def build_prompt(view: dict[str, Any], problem: str = "") -> str:
    """The question for the current decision of the agent's seat."""
    phase = view["phase"]
    v = _neutral(view)
    parts = [PREAMBLE]
    if problem:
        parts.append(f"Your previous answer hit a problem: {problem}\nDecide again from the table below.")

    if phase == "WAITING_FOR_P2_DECK":
        decks = "\n".join(
            f"  deck {cls}    ({d['name']}: {d.get('description', '')})" for cls, d in sorted(STARTER_DECKS.items())
        )
        parts.append(
            "The match is about to start. Choose the deck you will play with exactly one command:\n"
            f"{decks}\n"
            f"Your opponent plays {view['opponent']['hero']['card_class'].title()}."
        )
        return "\n\n".join(parts)

    if phase == "MULLIGAN":
        hand = "\n".join(
            f"  [{c['index']}] ({c['cost']} mana) {c['name']} [{c['type']}"
            + (f" {c['attack']}/{c['health']}" if c["type"] == "MINION" else "")
            + f"] - {c['text']}"
            for c in v["me"]["hand"]
        )
        parts.append(
            "Opening hand. You may send cards back and draw replacements, once.\n"
            f"You play {v['me']['hero']['card_class'].title()} against {v['opponent']['hero']['card_class'].title()}.\n"
            f"Your hand:\n{hand}\n\n"
            "Answer with exactly one command: `mulligan <indices to replace>` (for example `mulligan 0 2`) or `mulligan none`."
        )
        return "\n\n".join(parts)

    if view.get("pending_choice"):
        options = "\n".join(
            f"  pick {i}    ({o['cost']} mana) {o['name']} - {o['text']}" for i, o in enumerate(view["pending_choice"]["options"])
        )
        parts.append(f"You must choose one card to keep:\n{options}\nAnswer with exactly one `pick` command.")
        parts.append("The table:\n" + format_state_for_cli(v))
        return "\n\n".join(parts)

    parts.append("It is your turn.")
    parts.append(PLAY_RULES)
    parts.append("The table:\n" + format_state_for_cli(v))
    parts.append("Allowed right now (choose one value where <...> lists several):\n  " + "\n  ".join(legal_moves(view)))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Turning the answer into moves
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """What the agent was looking at when it answered: its indices and aliases mean this."""

    view: dict[str, Any]
    hand: list[str] = field(default_factory=list)

    @classmethod
    def of(cls, view: dict[str, Any]) -> "Snapshot":
        return cls(view=view, hand=[c["uid"] for c in view["me"]["hand"]])

    def target(self, raw: Optional[str]) -> Optional[str]:
        return resolve_target(self.view, raw)


def _tokens(line: str) -> list[str]:
    try:
        toks = shlex.split(line.strip().strip("`"))
    except ValueError:
        toks = line.strip().split()
    while toks and toks[0].lower() in ("./hs", "hs", "$"):
        toks = toks[1:]
    return toks


def _split_options(toks: list[str]) -> tuple[list[str], dict[str, str]]:
    positional: list[str] = []
    opts: dict[str, str] = {}
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("--"):
            key, _, val = t[2:].partition("=")
            if not val and i + 1 < len(toks):
                i += 1
                val = toks[i]
            opts[key.lower()] = val
        else:
            positional.append(t)
        i += 1
    return positional, opts


def _int(raw: Optional[str], what: str) -> int:
    try:
        return int(str(raw).strip("[]"))
    except (TypeError, ValueError):
        raise GameError(f"{what} must be a number.")


def run_command(engine: GameEngine, snap: Snapshot, line: str) -> str:
    """Play one command for the agent's seat. Returns the command's name; raises GameError if it is refused."""
    toks = _tokens(line)
    if not toks:
        raise GameError("Empty command.")
    name = toks[0].lower()
    args, opts = _split_options(toks[1:])
    phase = engine.state.phase

    if name == "deck":
        if phase != "WAITING_FOR_P2_DECK":
            raise GameError("The deck is already chosen.")
        cls = (args[0] if args else "").upper()
        if cls not in STARTER_DECKS:
            raise GameError(f"Unknown deck '{cls}'. Use one of: {', '.join(sorted(STARTER_DECKS))}.")
        d = STARTER_DECKS[cls]
        engine.set_p2_deck(d["hero_class"], d["cards"], d["name"])
        return name

    if name == "mulligan":
        picks = [a for a in args if a.lower() not in ("none", "keep", "-")]
        engine.submit_mulligan(SEAT, [_int(a, "A hand index") for a in picks])
        return name

    if phase != "PLAY":
        raise GameError("That command is not available right now.")

    if name == "pick":
        engine.resolve_pending_choice(SEAT, _int(args[0] if args else None, "The option"))
        return name

    if name in ("concede", "resign", "forfeit"):
        if not concede_allowed(engine.serialize_for_seat(SEAT)):
            raise GameError(
                f"It is not hopeless yet: you may concede only at {CONCEDE_HEALTH} health or less, "
                "or when the enemy board alone could finish you. Play on."
            )
        engine.concede(SEAT)
        return "concede"

    if name in ("end", "end_turn", "pass"):
        engine.end_turn(SEAT)
        return "end"

    if name == "play":
        shown = _int(args[0] if args else None, "The hand index")
        if not 0 <= shown < len(snap.hand):
            raise GameError(f"There is no card [{shown}] in your hand.")
        uid = snap.hand[shown]
        hand = engine.state.players[SEAT].hand
        current = next((i for i, c in enumerate(hand) if c.uid == uid), None)
        if current is None:
            raise GameError(f"Card [{shown}] is no longer in your hand.")
        pos = _int(opts["pos"], "--pos") if "pos" in opts else None
        choose = _int(opts["choose"], "--choose") if "choose" in opts else None
        engine.play_card(SEAT, current, pos=pos, target_id=snap.target(opts.get("target")), choose=choose)
        return name

    if name == "attack":
        if len(args) < 2:
            raise GameError("attack needs an attacker and a target.")
        engine.attack(SEAT, snap.target(args[0]) or "", snap.target(args[1]) or "")
        return name

    if name == "power":
        raw = opts.get("target") or (args[0] if args else None)
        engine.use_hero_power(SEAT, target_id=snap.target(raw))
        return name

    raise GameError(f"Unknown command '{toks[0]}'.")


def wants_to_act(engine: GameEngine) -> bool:
    """Is the agent's seat the one everybody is waiting for?"""
    st = engine.state
    if st.phase == "WAITING_FOR_P2_DECK":
        return True
    if st.phase == "MULLIGAN":
        return not st.players[SEAT].mulligan_done
    if st.phase == "PLAY":
        if st.pending_choice is not None:
            return st.pending_choice.seat == SEAT
        return st.active_seat == SEAT
    return False


async def take_turn(
    engine: GameEngine,
    model: str,
    after_move: Callable[[], Awaitable[None]],
    ask: Ask = ask_cli,
    still_ours: Callable[[], bool] = lambda: True,
) -> dict[str, Any]:
    """Let the agent act until its seat has nothing left to decide.

    `after_move` runs after every accepted command, so the other side sees
    each move as it happens. Raises AgentError when the agent cannot be
    reached or keeps answering nonsense; the caller decides what happens then.
    """
    asks = 0
    moves = 0
    problem = ""
    failures = 0
    while wants_to_act(engine) and still_ours():
        if asks >= MAX_ASKS_PER_TURN:
            raise AgentError("The agent did not finish its turn.")
        view = engine.serialize_for_seat(SEAT)
        snap = Snapshot.of(view)
        asks += 1
        try:
            answer = await ask(build_prompt(view, problem), model)
        except AgentError:
            failures += 1
            if failures >= 2:
                raise
            continue
        if not still_ours() or not wants_to_act(engine):
            break
        problem = ""
        said = (answer.get("say") or "").strip()
        if said and engine.state.phase == "PLAY":
            engine.send_emote(SEAT, said[:60])
        if not answer["commands"]:
            problem = "You sent no commands."
            continue
        progressed = False
        for line in answer["commands"]:
            if not wants_to_act(engine):
                break
            try:
                run_command(engine, snap, line)
            except GameError as exc:
                problem = f"`{line}` was rejected: {exc}"
                break
            except (IndexError, KeyError, ValueError):
                problem = f"`{line}` could not be understood."
                break
            moves += 1
            progressed = True
            await after_move()
        if not progressed and not problem:
            problem = "None of your commands could be run."
    return {"asks": asks, "moves": moves}


# ---------------------------------------------------------------------------
# Table talk: the human writes, the agent answers
# ---------------------------------------------------------------------------

# Chat answers come from the quickest model: a line of banter needs no deep thought.
CHAT_MODEL = os.environ.get("AGENT_CHAT_MODEL", "gemini-4-hydrogen-low")
CHAT_MAX = 140
CHAT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {"say": {"type": "string"}},
    "required": ["say"],
})
ChatAsk = Callable[[str, str], Awaitable[str]]

_SAID = re.compile(r'says: "(.*)"$', re.S)


def recent_chat(view: dict[str, Any], limit: int = 12) -> list[tuple[str, str]]:
    """What was said at the table lately, as (who, text) with who "You" (the agent) or "Opponent"."""
    out = []
    for entry in _neutral(view).get("log", []):
        m = _SAID.search(entry["text"])
        if m and entry.get("seat"):
            out.append(("You" if entry["seat"] == SEAT else "Opponent", m.group(1)))
    return out[-limit:]


CHAT_PREAMBLE = (
    "You are Antigravity, an AI playing a friendly two-player card duel against a human, who is chatting with "
    "you across the table. Answer their latest message with one line of table talk: witty, playful banter. "
    "Teasing about the match is welcome; keep it good-natured and family-friendly. Write in the language the "
    f"human writes in, at most {CHAT_MAX} characters. Never reveal the cards in your hand or what you plan to "
    "play. Everything you know is in this message: do not use tools or files, just answer through the "
    'structured answer, the line itself in "say".'
)


def build_chat_prompt(view: dict[str, Any]) -> str:
    """The question when the human has said something: the match at a glance and the talk so far."""
    me, opp = view["me"], view["opponent"]

    def hero(p: dict[str, Any]) -> str:
        h = p["hero"]
        armor = f" and {h['armor']} armor" if h.get("armor") else ""
        return f"{h['card_class'].title()} hero at {h['hp']}/{h['max_hp']} health{armor}, {len(p['board'])} minions on the board, {p['hand_count']} cards in hand"

    if view["phase"] == "GAME_OVER":
        state = "The match is over: " + ("you won." if view.get("winner") == SEAT else "you lost." if view.get("winner") else "it ended in a draw.")
    elif view["phase"] == "PLAY":
        state = f"Turn {view['turn_number']}, {'your' if view['active_seat'] == SEAT else 'their'} turn."
    else:
        state = "The match is just starting."
    talk = "\n".join(f"{who}: {text}" for who, text in recent_chat(view)) or "(nothing yet)"
    return "\n\n".join([
        CHAT_PREAMBLE,
        f"{state}\nYou: {hero(me)}.\nOpponent: {hero(opp)}.",
        f"The talk so far, oldest first (\"You\" is you):\n{talk}",
    ])


def parse_chat(text: str) -> str:
    """The line from the CLI's JSON envelope, a bare JSON answer, or plain text, cut to size."""
    said: Any = None
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        if data.get("status") not in (None, "SUCCESS") and not data.get("structured_output"):
            raise AgentError(f"The agent did not finish its answer ({data.get('status')}).")
        answer = data.get("structured_output") if isinstance(data.get("structured_output"), dict) else data
        said = answer.get("say") if "say" in answer else data.get("response")
    elif isinstance(data, str):
        said = data
    else:
        said = text
    line = " ".join(str(said or "").split()).strip("`\"' ")
    if not line:
        raise AgentError("The agent had nothing to say.")
    if len(line) > CHAT_MAX:
        line = line[: CHAT_MAX - 1].rsplit(" ", 1)[0] + "…"
    return line


async def ask_chat_cli(prompt: str, model: str) -> str:
    return parse_chat(await _run_cli(prompt, model, CHAT_SCHEMA))
