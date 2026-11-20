"""The on-device opponent: it picks its moves by trying them out.

No network, no language model, only the standard library, so it runs wherever
the engine runs (a server, or Python inside a browser or an app).

How it decides
    For every move the rules allow it plays the move on a private copy of the
    game, using the engine's own rules, and scores the position that results.
    It looks ahead over whole sequences of moves within its turn (the order of
    attacks and plays matters), keeps the most promising lines, and takes the
    first move of the best line. It knows nothing about individual cards: a
    card is only what the rules do when it is played.

What it may know (the same as a person in its seat)
    Its own hand, its own secrets, both boards, both heroes and weapons, both
    players' mana, the number of cards in each hand and deck, which cards its
    own deck still holds, and that the opponent has secrets (not which).

What it may not know, and how that is kept from it
    - the order of its own deck: the deck is reshuffled in every imagined game;
    - the opponent's hand and the order of the opponent's deck: both are pooled
      and dealt out again at random, so no imagined game holds the real hand;
    - the opponent's secrets: they are removed from the imagined game;
    - what the dice will do: imagined games roll their own dice, never a copy
      of the real game's.
    The real game is only ever read, then changed by one public action.

The three levels
    easy    looks one move ahead only, overlooks some of the moves open to it, misjudges which of
            the good ones is best, spends its cards freely and does not see danger coming. It
            never makes a move that harms it. A little weaker than the practice bot.
    normal  plans its whole turn and checks how each of its best plans stands when the turn has
            ended, with a small error in that last comparison: now and then it takes the second
            best plan, or leaves a marginal move unmade.
    hard    the same without the error, looking at more lines, trying moves that hang on the dice
            twice, and imagining the opponent's board (and hero power) answering before it chooses.

Use
    while ai.step(engine, seat, level="normal"):
        ...  # one decision was made and applied; show it, then ask again

A plan made at the first decision of a turn is followed for the rest of it for as long as the game
looks the way the plan expected, so most decisions after the first cost next to nothing.
scripts/ai_arena.py plays the levels against each other and the practice bot and prints win rates
and thinking times; tests/test_ai.py holds it to the rules above.
"""
from __future__ import annotations

import copy
import heapq
import math
import random
import time
from typing import Any, Optional

from engine.catalog import get_card
from engine.effects import CHOOSE_ONE_OPTIONS, TARGET_RULES
from engine.game import GameEngine, GameError
from engine.models import GameState

LEVELS = ("easy", "normal", "hard")

# How long a caller may want to give one decision at each level, in milliseconds.
# `step` never needs more than its level's work; a smaller budget just cuts the search short.
SUGGESTED_BUDGET_MS = {"easy": 250, "normal": 700, "hard": 1500}

Move = tuple  # ("play", card uid, target, choose) | ("power", target) | ("attack", attacker, target) | ("pick", index) | ("end",)

# width: lines kept at each step of the look-ahead; extra: lines kept only because they hurt the
# enemy hero most (so a kill that needs setting up is not pruned); depth: moves looked ahead;
# nodes: imagined moves per decision at most; finals: best lines played through to the end of the
# turn before choosing; reply: also imagine the opponent's board hitting back; samples: how many
# times a move left to chance is tried; noise: random error added to each score; threat: how much
# the danger of dying next turn weighs.
# attention: the share of its possible moves it notices at each decision; cards: how much it values
# the cards in its own hand (below 1 it spends them freely).
_LEVELS: dict[str, dict[str, Any]] = {
    "easy": dict(width=1, extra=0, depth=1, nodes=60, finals=0, reply=False, samples=1, noise=4.0, threat=0.0, attention=0.6, cards=0.25),
    "normal": dict(width=4, extra=2, depth=12, nodes=260, finals=3, reply=False, samples=1, noise=1.2, threat=1.0, attention=1.0, cards=1.0),
    "hard": dict(width=8, extra=3, depth=14, nodes=900, finals=5, reply=True, samples=2, noise=0.0, threat=1.0, attention=1.0, cards=1.0),
}

MAX_DECISIONS_PER_TURN = 40
WIN = 10_000.0
CHANCE_CAP = 80.0  # a win or loss that hangs on the dice counts this much, not for everything

# ---- what a position is worth (all from the point of view of the seat deciding) ----
W_HERO = 6.0  # times the square root of health + armor: each point matters more the fewer are left
W_ENEMY_HERO = 0.7  # above 1 it races for the enemy hero, below 1 it fights for the board
W_BODY = 0.7  # a piece on the board, whatever its numbers
W_ATTACK = 1.0
W_HEALTH = 1.0
W_ENEMY = 1.12  # the other side's pieces weigh a little more: they strike first
W_CARD = 1.8  # a card in hand ...
W_CARD_COST = 0.45  # ... and more for a dearer one
W_ENEMY_CARD = 2.3
W_WEAPON = 0.55
W_SECRET = 1.2  # one of its own secrets in play ...
W_SECRET_COST = 1.5  # ... and more for a dearer one
W_OVERLOAD = 0.7
W_MANA_LEFT = 0.15
W_THREAT = 1.2
W_DEAD_NEXT_TURN = 30.0
W_AFTER_REPLY = 0.4  # how much of that danger still counts once the opponent's answer has been imagined
W_ABILITY = 0.45  # per point a piece's numbers fall short of its cost: it does something else

_ATOMS = (int, str, bool, float, type(None))
_JOURNAL = ("log", "checkpoints", "pending_events")
# Marks of a piece that keeps doing something while it is on the board.
_STANDING = frozenset(("TRIGGER_VISUAL", "AURA", "DEATHRATTLE", "ADJACENT_BUFF"))

_RNG = random.Random()
# Counts for checking the AI itself (scripts/ai_arena.py prints them): plans made, moves imagined,
# planned moves the real game refused, and times it had to fall back on the least it could do.
STATS = {"plans": 0, "imagined": 0, "refused": 0, "errors": 0, "fallbacks": 0}
# What was planned for a game's current turn, so the moves of one plan are not searched for again.
_MEMO: dict[tuple[str, str], dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# An imagined game
# ---------------------------------------------------------------------------


class _Dice(random.Random):
    """Dice for imagined games. They count their rolls, so a move left to chance can be told apart."""

    rolls = 0

    def random(self) -> float:
        self.rolls += 1
        return super().random()

    def getrandbits(self, k: int) -> int:
        self.rolls += 1
        return super().getrandbits(k)


class _Sim(GameEngine):
    """A game being imagined: the same rules, without the journal or the log."""

    def __init__(self, state: GameState, rng: random.Random):
        self.state = state
        self.rng = rng
        self._action_depth = 0
        self.chance = False  # did getting here involve a roll of the dice?

    def emit(self, event_type: str, **data: Any) -> None:
        pass

    def checkpoint(self) -> None:
        pass

    def add_log(self, text: str, seat: Optional[str] = None) -> None:
        pass


def _copy(obj: Any) -> Any:
    """A copy of a piece of the game's state, a good deal faster than copy.deepcopy: the state is
    plain objects, lists, sets and dicts of numbers and strings."""
    t = type(obj)
    if t in _ATOMS:
        return obj
    if t is list:
        return [_copy(x) for x in obj]
    if t is set:
        return set(obj)
    if t is dict:
        return {k: _copy(v) for k, v in obj.items()}
    if t is tuple or t is frozenset:
        return obj
    try:
        fields = obj.__dict__
    except AttributeError:  # something the state did not hold when this was written
        return copy.deepcopy(obj)
    new = object.__new__(t)
    d = new.__dict__
    for k, v in fields.items():
        d[k] = v if type(v) in _ATOMS else _copy(v)
    return new


def _copy_state(st: GameState) -> GameState:
    """The game as it stands, without its history (which is most of its weight)."""
    new = object.__new__(GameState)
    d = new.__dict__
    for k, v in st.__dict__.items():
        if k in _JOURNAL:
            d[k] = []
        elif k == "last_emote":
            d[k] = None
        else:
            d[k] = v if type(v) in _ATOMS else _copy(v)
    return new


def _other(seat: str) -> str:
    return "p2" if seat == "p1" else "p1"


def _uid(card: Any) -> str:
    return card.uid


def _imagine(engine: GameEngine, seat: str, rng: random.Random) -> _Sim:
    """A copy of the game holding only what `seat` knows; the rest is dealt again at random."""
    st = _copy_state(engine.state)
    me = st.players[seat]
    opp = st.players[_other(seat)]
    # Sorting first makes the deal depend on which cards are unseen, not on where they really are.
    me.deck.sort(key=_uid)
    rng.shuffle(me.deck)
    pool = opp.hand + opp.deck
    pool.sort(key=_uid)
    rng.shuffle(pool)
    held = len(opp.hand)
    opp.hand = pool[:held]
    opp.deck = pool[held:]
    opp.secrets = []
    return _Sim(st, _Dice(rng.getrandbits(48)))


def _minion_sig(m: Any) -> tuple:
    return (m.card_id, m.attack, m.max_health - m.damage, m.max_health, m.attacks_this_turn, m.frozen, m.silenced,
            m.summoned_this_turn, len(m.enchantments), tuple(sorted(m.keywords)))


def _board_sig(board: list) -> tuple:
    """A board as a set of pieces: which slot each stands in is not part of how a position looks."""
    if len(board) < 2:
        return tuple([_minion_sig(m) for m in board])
    return tuple(sorted([_minion_sig(m) for m in board]))


def _weapon_sig(w: Any) -> Optional[tuple]:
    return None if w is None else (w.card_id, w.total_attack, w.durability)


def _sig(st: GameState, seat: str) -> tuple:
    """What `seat` can see of a position. Two positions that look alike are the same to the search,
    and a plan is followed only while the real game looks the way the plan expected."""
    me = st.players[seat]
    opp = st.players[_other(seat)]
    mh, oh = me.hero, opp.hero
    pc = st.pending_choice
    return (
        st.phase, st.active_seat, st.winner,
        me.mana, me.max_mana, me.pending_overload, me.jade_counter, me.enemy_spell_cost_mod_this_turn,
        mh.hp, mh.armor, mh.attack, mh.attacks_this_turn, mh.hero_power_id, mh.hero_power_used, mh.frozen,
        oh.hp, oh.armor, oh.frozen,
        tuple([(c.uid, c.card_id, c.cost_mod) for c in me.hand]),
        len(opp.hand), len(me.deck), len(opp.deck),
        _weapon_sig(me.weapon), _weapon_sig(opp.weapon),
        _board_sig(me.board), _board_sig(opp.board),
        tuple([s.card_id for s in me.secrets]),
        (pc.seat, tuple([o.uid for o in pc.options])) if pc is not None else None,
    )


def _look(st: GameState, seat: str) -> tuple:
    """How the game must look for a plan to go on: as `_sig`, and with the very same pieces on the
    board, since the plan's next moves name them."""
    return (_sig(st, seat), tuple([m.uid for s in ("p1", "p2") for m in st.players[s].board]))


# ---------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------


def _shape(m: Any) -> tuple:
    """Pieces with the same shape are interchangeable as targets or attackers."""
    return (m.card_id, m.attack, m.max_health, m.damage, m.frozen, m.silenced, m.attacks_this_turn,
            m.summoned_this_turn, len(m.enchantments), frozenset(m.keywords))


def _distinct(eng: GameEngine, ids: list[str]) -> list[str]:
    """Drop targets that are copies of one already listed."""
    if len(ids) < 2:
        return ids
    out: list[str] = []
    seen: set = set()
    for i in ids:
        if i.startswith("hero_"):
            out.append(i)
            continue
        m = eng.find_minion(i)
        key = (m.owner, _shape(m)) if m is not None else i
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


def _moves(eng: GameEngine, seat: str) -> list[Move]:
    """Every move the rules allow `seat` right now, apart from ending the turn."""
    st = eng.state
    pc = st.pending_choice
    if pc is not None:
        return [("pick", i) for i in range(len(pc.options))] if pc.seat == seat else []
    if st.phase != "PLAY" or st.active_seat != seat:
        return []
    p = st.players[seat]
    out: list[Move] = []

    seen_cards: set = set()
    combo = p.cards_played_this_turn > 0
    for i, ci in enumerate(p.hand):
        key = (ci.card_id, ci.cost_mod)
        if key in seen_cards:
            continue  # a second copy offers nothing the first does not
        seen_cards.add(key)
        if not eng.can_play_card(seat, i)[0]:
            continue
        card = get_card(ci.card_id)
        is_spell = card.type == "SPELL"
        if card.id in CHOOSE_ONE_OPTIONS:
            for k, opt in enumerate(CHOOSE_ONE_OPTIONS[card.id]):
                if opt.target_rule == "NONE":
                    out.append(("play", ci.uid, None, k))
                    continue
                targets = _distinct(eng, eng.get_valid_targets(seat, opt.target_rule, is_spell_or_power=is_spell))
                if targets:
                    out.extend(("play", ci.uid, t, k) for t in targets)
                elif not is_spell:
                    out.append(("play", ci.uid, None, k))
            continue
        rule = eng.get_target_rule(card.id, None, combo, seat=seat, exclude_hand_uid=ci.uid)
        if rule == "NONE":
            out.append(("play", ci.uid, None, None))
            continue
        targets = _distinct(eng, eng.get_valid_targets(seat, rule, is_spell_or_power=is_spell))
        if targets:
            out.extend(("play", ci.uid, t, None) for t in targets)
        elif not is_spell:
            out.append(("play", ci.uid, None, None))

    out.extend(_powers(eng, seat))
    out.extend(_attacks(eng, seat))
    return out


def _powers(eng: GameEngine, seat: str) -> list[Move]:
    if not eng.can_use_hero_power(seat)[0]:
        return []
    rule = TARGET_RULES.get(eng.state.players[seat].hero.hero_power_id, "NONE")
    if rule == "NONE":
        return [("power", None)]
    return [("power", t) for t in _distinct(eng, eng.get_valid_targets(seat, rule, is_spell_or_power=True))]


def _attacks(eng: GameEngine, seat: str) -> list[Move]:
    p = eng.state.players[seat]
    out: list[Move] = []
    seen: set = set()
    for m in p.board:
        if m.attack <= 0 or m.frozen:
            continue
        shape = _shape(m)
        if shape in seen:
            continue
        seen.add(shape)
        for t in _distinct(eng, eng.get_legal_attack_targets(seat, m.uid)):
            out.append(("attack", m.uid, t))
    hero = f"hero_{seat}"
    if p.hero.attack > 0:
        for t in _distinct(eng, eng.get_legal_attack_targets(seat, hero)):
            out.append(("attack", hero, t))
    return out


def _apply(eng: GameEngine, seat: str, move: Move) -> None:
    kind = move[0]
    if kind == "attack":
        eng.attack(seat, move[1], move[2])
    elif kind == "play":
        hand = eng.state.players[seat].hand
        for i, ci in enumerate(hand):
            if ci.uid == move[1]:
                eng.play_card(seat, i, target_id=move[2], choose=move[3])
                return
        raise GameError("That card is no longer in hand.")
    elif kind == "power":
        eng.use_hero_power(seat, target_id=move[1])
    elif kind == "pick":
        eng.resolve_pending_choice(seat, move[1])
    elif kind == "end":
        eng.end_turn(seat)
    else:
        raise GameError(f"Unknown move {kind!r}.")


# ---------------------------------------------------------------------------
# What a position is worth
# ---------------------------------------------------------------------------


def _minion_worth(m: Any) -> tuple[str, float, int]:
    """(whose it will be once the turn is over, its worth, the damage it can deal next turn)."""
    owner = m.owner
    atk = m.attack
    hp = m.max_health - m.damage
    fading = 1.0
    for e in m.enchantments:
        if e.destroy_at_eot:
            return owner, 0.0, 0
        if e.temp_owner_revert:
            owner = e.temp_owner_revert
        if e.temp_until_eot:
            atk -= e.atk
            hp -= max(0, e.hp)
        if e.destroy_at_owner_sot:
            fading = 0.4
    if hp <= 0:
        return owner, 0.0, 0
    if atk < 0:
        atk = 0
    kws = m.keywords
    strike = atk
    if "WINDFURY" in kws:
        strike = atk * 2
    if m.frozen or "CANT_ATTACK" in kws:
        strike = 0
    v = W_BODY + W_ATTACK * atk + W_HEALTH * hp
    if "TAUNT" in kws:
        v += 0.5 + 0.2 * hp
    if "DIVINE_SHIELD" in kws:
        v += 1.0 + 0.5 * atk
    if "WINDFURY" in kws:
        v += 0.5 * atk
    if "STEALTH" in kws:
        v += 0.5 + 0.25 * atk
    if "CANT_ATTACK" in kws:
        v -= 0.7 * atk
    elif m.frozen:
        v -= 0.4 * atk
    v += 1.2 * m.spell_damage
    if not m.silenced:
        card = get_card(m.card_id)
        if not _STANDING.isdisjoint(card.mechanics):
            # numbers below what its cost buys: the rest of its worth is what it keeps doing
            short = (2 * card.cost + 1) - ((card.attack or 0) + (card.health or 0))
            v += W_ABILITY * (6 if short > 6 else short if short > 0 else 0) + 0.4
    return owner, v * fading, strike


def _value(st: GameState, seat: str, threat: float = 1.0, cards: float = 1.0) -> float:
    """How good the position is for `seat`, as if its turn ended here."""
    if st.phase == "GAME_OVER":
        if st.winner == seat:
            return WIN
        return -WIN * (0.5 if st.winner == "draw" else 1.0)
    opp_seat = _other(seat)
    me = st.players[seat]
    opp = st.players[opp_seat]
    my_h = me.hero.hp + me.hero.armor
    op_h = opp.hero.hp + opp.hero.armor
    if my_h <= 0 or op_h <= 0:
        return WIN if my_h > 0 else -WIN
    v = W_HERO * (math.sqrt(my_h) - W_ENEMY_HERO * math.sqrt(op_h))

    my_strike = op_strike = 0
    my_wall = op_wall = 0
    for m in me.board + opp.board:
        owner, worth, strike = _minion_worth(m)
        if worth <= 0.0:
            continue
        guards = "TAUNT" in m.keywords and "STEALTH" not in m.keywords
        if owner == seat:
            v += worth
            my_strike += strike
            if guards:
                my_wall += m.max_health - m.damage
        else:
            v -= W_ENEMY * worth
            op_strike += strike
            if guards:
                op_wall += m.max_health - m.damage

    if me.weapon is not None:
        v += W_WEAPON * me.weapon.total_attack * (me.weapon.durability if me.weapon.durability < 3 else 3)
        if not me.hero.frozen:
            my_strike += me.weapon.total_attack
    if opp.weapon is not None:
        v -= W_WEAPON * opp.weapon.total_attack * (opp.weapon.durability if opp.weapon.durability < 3 else 3)
        if not opp.hero.frozen:
            op_strike += opp.weapon.total_attack

    held = 0.0
    for ci in me.hand:
        cost = get_card(ci.card_id).cost
        held += W_CARD + W_CARD_COST * (cost if cost < 8 else 8)
    v += cards * held
    v -= W_ENEMY_CARD * len(opp.hand)
    for sec in me.secrets:
        v += W_SECRET + W_SECRET_COST * get_card(sec.card_id).cost
    v -= W_OVERLOAD * me.pending_overload
    v -= W_MANA_LEFT * me.mana
    if not me.deck:
        v -= 1.0 + me.fatigue
    if not opp.deck:
        v += 1.0 + opp.fatigue

    if threat > 0.0:
        # What the other side's board can do to this hero next turn, past the pieces that must be hit first.
        through = op_strike - my_wall
        if through > 0:
            if through >= my_h:
                v -= threat * (W_DEAD_NEXT_TURN + 0.5 * (through - my_h))
            else:
                v -= threat * W_THREAT * through * through / my_h
        elif through < 0:
            through = 0
        if opp.hand:
            # and what a hand might add: unknown, so only its size and the mana to spend count
            reach = through + 0.5 * (opp.max_mana + 1 if opp.max_mana < 10 else 10)
            if through < my_h <= reach:
                v -= threat * 6.0
        # The same the other way round, worth less: the opponent moves first.
        mine = my_strike - op_wall
        if mine > 0:
            v += threat * (8.0 if mine >= op_h else 0.35 * W_THREAT * mine * mine / op_h)
    return v


def _promise(eng: GameEngine, seat: str) -> float:
    """What a position can still become this turn: mana that can be spent, pieces yet to strike.
    Only used to decide which lines to keep looking at, never to choose a move."""
    p = eng.state.players[seat]
    mana = p.mana
    spend = 0.0
    costs = sorted(eng.get_card_cost(seat, ci) for ci in p.hand)
    for c in costs:
        if c > mana:
            break
        mana -= c
        spend += c if c > 0 else 0.5
    if mana >= 2 and not p.hero.hero_power_used:
        spend += 1.0
    ready = 0
    for m in p.board:
        if m.attack > 0 and not m.frozen and m.attacks_this_turn < m.max_attacks() and "CANT_ATTACK" not in m.keywords:
            if not m.summoned_this_turn or "CHARGE" in m.keywords:
                ready += m.attack
    if p.hero.attack > 0 and not p.hero.frozen and p.hero.attacks_this_turn == 0:
        ready += p.hero.attack
    return 0.9 * spend + 0.45 * ready


# ---------------------------------------------------------------------------
# Looking ahead
# ---------------------------------------------------------------------------


class _Node:
    __slots__ = ("sim", "parent", "move", "sig", "value", "key", "enemy")

    def __init__(self, sim: _Sim, parent: Optional["_Node"], move: Optional[Move], sig: tuple, value: float, key: float, enemy: int):
        self.sim = sim
        self.parent = parent
        self.move = move
        self.sig = sig
        self.value = value  # what the position is worth if the turn ends here
        self.key = key  # value plus what the turn can still bring: the order lines are kept in
        self.enemy = enemy  # the enemy hero's health and armor

    def line(self, seat: str) -> list[tuple[Move, tuple]]:
        """The moves that lead here, each with what the game should look like after it."""
        out: list[tuple[Move, tuple]] = []
        n: Optional[_Node] = self
        while n is not None and n.move is not None:
            out.append((n.move, _look(n.sim.state, seat)))
            n = n.parent
        out.reverse()
        return out


def _child(parent: _Sim, seat: str, move: Move) -> Optional[_Sim]:
    dice = parent.rng
    sim = _Sim(_copy_state(parent.state), dice)
    rolls = dice.rolls
    try:
        _apply(sim, seat, move)
    except Exception:  # refused, or the rules tripped over an imagined position: not a line to follow
        return None
    sim.chance = parent.chance or dice.rolls != rolls
    return sim


def _capped(value: float) -> float:
    return CHANCE_CAP if value > CHANCE_CAP else -CHANCE_CAP if value < -CHANCE_CAP else value


def _reply(sim: _Sim, seat: str, deadline: float) -> _Sim:
    """The opponent's turn as far as it can be foreseen: the pieces it already has strike back and
    its hero power is used, each where it gains most. Nothing is played from its hand, which is not known."""
    for _ in range(12):
        best: Optional[_Sim] = None
        best_v = _value(sim.state, seat, 0.0) + 0.01
        for move in _attacks(sim, seat) + _powers(sim, seat):
            if time.monotonic() > deadline:
                return sim
            nxt = _child(sim, seat, move)
            if nxt is None:
                continue
            v = _value(nxt.state, seat, 0.0)
            if v > best_v:
                best, best_v = nxt, v
        if best is None:
            return sim
        sim = best
        if sim.state.phase != "PLAY" or sim.state.active_seat != seat:
            return sim
    return sim


def _plan(engine: GameEngine, seat: str, lv: dict[str, Any], budget_ms: float, rng: random.Random) -> tuple[list[tuple[Move, tuple]], bool]:
    """The best line of moves found (empty: end the turn), and whether the turn should end once the
    line is played (False: the line is only the next move, think again after it)."""
    start = time.monotonic()
    span = max(0.005, budget_ms / 1000.0)
    search_until = start + span * (0.6 if lv["finals"] else 0.95)
    deadline = start + span * 0.95
    threat = lv["threat"]
    noise = lv["noise"]
    samples = lv["samples"]
    cards = lv["cards"]
    attention = lv["attention"]
    opp_seat = _other(seat)

    root_sim = _imagine(engine, seat, rng)
    must_move = root_sim.state.pending_choice is not None
    root = _Node(root_sim, None, None, _sig(root_sim.state, seat), _value(root_sim.state, seat, threat, cards), 0.0, 0)
    seen = {root.sig}
    found: list[_Node] = []  # every position reached where the turn could end
    beam = [root]
    sims = 0
    out_of_time = False

    for _depth in range(lv["depth"]):
        children: list[_Node] = []
        for node in beam:
            for move in _moves(node.sim, seat):
                if sims >= lv["nodes"] or time.monotonic() > search_until:
                    out_of_time = True
                    break
                if attention < 1.0 and not must_move and rng.random() > attention:
                    continue  # overlooked
                sim = _child(node.sim, seat, move)
                sims += 1
                if sim is None:
                    continue
                st = sim.state
                sig = _sig(st, seat)
                if sig in seen:
                    continue
                seen.add(sig)
                value = _value(st, seat, threat, cards)
                if sim.chance:
                    # The dice were rolled on the way here: this is one outcome of several. Try the
                    # move again where the level allows, and let no single outcome decide everything.
                    value = _capped(value)
                    if samples > 1 and not node.sim.chance:
                        tries = 1
                        for _ in range(samples - 1):
                            again = _child(node.sim, seat, move)
                            sims += 1
                            if again is not None:
                                value += _capped(_value(again.state, seat, threat, cards))
                                tries += 1
                        value /= tries
                opp = st.players[opp_seat]
                child = _Node(sim, node, move, sig, value, value, opp.hero.hp + opp.hero.armor)
                if st.phase == "GAME_OVER":
                    if st.winner == seat and not sim.chance:
                        STATS["plans"] += 1
                        STATS["imagined"] += sims
                        return child.line(seat), True  # nothing beats winning now
                    found.append(child)
                    continue
                if st.pending_choice is None:
                    found.append(child)
                if st.active_seat != seat:
                    continue  # the move ended the turn
                child.key = value + _promise(sim, seat)
                children.append(child)
            if out_of_time:
                break
        if not children:
            break
        children.sort(key=lambda n: -n.key)
        beam = children[: lv["width"]]
        if lv["extra"] and len(children) > lv["width"]:
            rest = sorted(children[lv["width"]:], key=lambda n: (n.enemy, -n.key))
            beam.extend(rest[: lv["extra"]])
        if out_of_time:
            break

    STATS["plans"] += 1
    STATS["imagined"] += sims
    if not found:
        return [], True
    if not lv["finals"]:
        # The careless player: it sees which moves help, but ranks them with an unsteady eye, so it
        # takes good moves in a poor order or at the wrong target. It never picks a move that harms it.
        helpful = [n for n in found if n.value > root.value + 0.05]
        if not helpful:
            if not must_move:
                return [], False
            helpful = found
        return max(helpful, key=lambda n: n.value + (rng.gauss(0.0, noise) if noise else 0.0)).line(seat), False

    # Play the best few lines through to the end of the turn (and, when the level says so, the
    # opponent's answer), so that what follows is part of the choice.
    finalists = heapq.nlargest(lv["finals"], found, key=lambda n: n.value)
    if not must_move:
        finalists.append(root)
    scored: list[tuple[float, _Node]] = []  # each line as it stands when its turn has ended
    deeper: list[tuple[float, _Node]] = []  # the same lines looked at further
    for node in finalists:
        st = node.sim.state
        if st.phase == "GAME_OVER" or st.active_seat != seat or st.pending_choice is not None:
            scored.append((node.value, node))
            deeper.append((node.value, node))
            continue
        if time.monotonic() > deadline and scored:
            break
        end = _child(node.sim, seat, ("end",))
        if end is None:
            scored.append((node.value, node))
            continue
        ended = _value(end.state, seat, threat, cards)
        if end.chance:
            ended = _capped(ended)
        scored.append((ended, node))
        if not lv["reply"]:
            continue
        if end.state.phase != "PLAY":
            deeper.append((ended, node))  # the game ended with the turn: nothing follows
            continue
        after = _reply(end, opp_seat, deadline)
        if time.monotonic() > deadline:
            continue
        value = _value(after.state, seat, threat * W_AFTER_REPLY, cards)
        deeper.append((_capped(value) if after.chance else value, node))
    # Lines are only compared with lines looked at equally far.
    pool = deeper if len(deeper) >= 2 or (deeper and len(deeper) == len(scored)) else scored
    if noise:
        pool = [(v + rng.gauss(0.0, noise), n) for v, n in pool]
    best_value, best = max(pool, key=lambda s: s[0])
    return best.line(seat), True


# ---------------------------------------------------------------------------
# The opening hand
# ---------------------------------------------------------------------------


def _mulligan(engine: GameEngine, seat: str, level: str, rng: random.Random) -> list[int]:
    """Cards to send back: the ones too dear to play in the first turns."""
    st = engine.state
    hand = st.players[seat].hand
    keep_up_to = 4 if level == "easy" else 3
    costs = [get_card(ci.card_id).cost for ci in hand]
    replace = [i for i, c in enumerate(costs) if c > keep_up_to]
    if level != "easy" and seat != st.first_seat:
        # going second there is one more mana early on: one 4-cost card may stay
        fours = [i for i in replace if costs[i] == 4]
        if fours:
            replace.remove(fours[0])
    if level == "easy" and replace and rng.random() < 0.3:
        replace.pop(rng.randrange(len(replace)))
    return replace


# ---------------------------------------------------------------------------
# Deciding
# ---------------------------------------------------------------------------


def forget(game_id: Optional[str] = None) -> None:
    """Drop what was planned (for one game, or all). Only needed by tests; plans are checked before use."""
    if game_id is None:
        _MEMO.clear()
    else:
        for key in [k for k in _MEMO if k[0] == game_id]:
            del _MEMO[key]


def _memo(st: GameState, seat: str) -> dict[str, Any]:
    key = (st.game_id, seat)
    memo = _MEMO.get(key)
    if memo is None or memo["turn"] != st.turn_number:
        if len(_MEMO) > 32:
            _MEMO.clear()
        memo = _MEMO[key] = {"turn": st.turn_number, "count": 0, "line": [], "expect": None, "final": False, "level": None}
    return memo


def _think(engine: GameEngine, seat: str, level: str, budget_ms: float, rng: random.Random) -> Optional[tuple]:
    """(move, the moves planned after it, how the game should look once it is made, whether the turn
    ends when those are played). None when `seat` has nothing to decide. Changes nothing in the game."""
    st = engine.state
    if st.phase == "MULLIGAN":
        if st.players[seat].mulligan_done:
            return None
        return ("mulligan", _mulligan(engine, seat, level, rng)), [], None, False
    if st.phase != "PLAY":
        return None
    pc = st.pending_choice
    if pc is not None:
        if pc.seat != seat:
            return None
    elif st.active_seat != seat:
        return None

    memo = _memo(st, seat)
    if memo["count"] >= MAX_DECISIONS_PER_TURN and pc is None:
        return ("end",), [], None, False
    if memo["level"] == level and memo["expect"] is not None and memo["expect"] == _look(st, seat):
        # the game looks the way the plan expected: go on with the plan
        if memo["line"]:
            move, expect = memo["line"][0]
            return move, memo["line"][1:], expect, memo["final"]
        if memo["final"] and pc is None:
            return ("end",), [], None, False
    line, final = _plan(engine, seat, _LEVELS[level], budget_ms, rng)
    if not line:
        return (("pick", 0) if pc is not None else ("end",)), [], None, False
    move, expect = line[0]
    return move, line[1:], expect, final


def decide(engine: GameEngine, seat: str, level: str = "normal", budget_ms: float = 700, rng: Optional[random.Random] = None) -> Optional[Move]:
    """The move `step` would make now, without making it: ("mulligan", [hand indices]),
    ("play", card uid, target, choose), ("power", target), ("attack", attacker, target),
    ("pick", option) or ("end",). None when `seat` has nothing to decide."""
    choice = _think(engine, seat, level if level in _LEVELS else "normal", budget_ms, rng or _RNG)
    return None if choice is None else choice[0]


def _fallback(engine: GameEngine, seat: str) -> bool:
    """Something went wrong: do the least that keeps the game moving."""
    try:
        st = engine.state
        if st.phase == "MULLIGAN":
            if st.players[seat].mulligan_done:
                return False
            engine.submit_mulligan(seat, [])
            return True
        if st.phase != "PLAY":
            return False
        pc = st.pending_choice
        if pc is not None:
            if pc.seat != seat:
                return False
            engine.resolve_pending_choice(seat, 0)
            return True
        if st.active_seat != seat:
            return False
        engine.end_turn(seat)
        return True
    except Exception:
        return False


def step(engine: GameEngine, seat: str, level: str = "normal", budget_ms: float = 700, rng: Optional[random.Random] = None) -> bool:
    """Make one decision for `seat` and apply it: the mulligan, a pick, a card, the hero power, an
    attack, or ending the turn. True if it acted (ask again), False if `seat` has nothing to decide
    now: not its move, waiting for the other seat, or the game is over. Never raises."""
    if level not in _LEVELS:
        level = "normal"
    rng = rng or _RNG
    for _attempt in range(2):
        try:
            choice = _think(engine, seat, level, budget_ms, rng)
        except Exception:
            STATS["errors"] += 1
            break
        if choice is None:
            return False
        move, rest, expect, final = choice
        try:
            if move[0] == "mulligan":
                engine.submit_mulligan(seat, move[1])
                return True
            memo = _memo(engine.state, seat)
            _apply(engine, seat, move)
        except GameError:
            # The real game refused a planned move (it had changed in a way that did not show): think afresh once.
            STATS["refused"] += 1
            forget(engine.state.game_id)
            continue
        except Exception:
            STATS["errors"] += 1
            break
        memo["count"] += 1
        memo["line"] = rest
        memo["expect"] = expect
        memo["final"] = final
        memo["level"] = level
        return True
    STATS["fallbacks"] += 1
    try:
        forget(engine.state.game_id)
    except Exception:
        pass
    return _fallback(engine, seat)
