"""Journey to Un'Goro (UNG) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from engine.catalog import get_card
from engine.expansions import helpers
from engine.models import CardInstance, ChooseOption, PendingChoice

if TYPE_CHECKING:
    from engine.game import GameEngine
    from engine.models import CardDef, Minion


# ---------------------------------------------------------------------------
# STATIC REGISTRIES
# ---------------------------------------------------------------------------

PURE_KEYWORD_CARDS: set[str] = {
    "UNG_019",  # Air Elemental (Elusive)
    "UNG_071",  # Giant Mastodon (Taunt)
    "UNG_806",  # Ultrasaur (vanilla)
    "UNG_808",  # Stubborn Gastropod (Taunt, Poisonous)
    "UNG_810",  # Stegodon (Taunt)
    "UNG_812",  # Sabretooth Stalker (Stealth)
    "UNG_813",  # Stormwatcher (Windfury)
    "UNG_814",  # Giant Wasp (Stealth, Poisonous)
    "UNG_844",  # Humongous Razorleaf (Can't attack)
    "UNG_852",  # Tyrantus (Taunt, Elusive)
}

TARGET_RULES: dict[str, str] = {
    # Spells
    "UNG_004": "MINION",           # Dinosize
    "UNG_018": "ANY",              # Flame Geyser
    "UNG_030": "MINION",           # Binding Heal
    "UNG_057t1": "ANY",            # Razorpetal (token)
    "UNG_108": "FRIENDLY_MINION",  # Earthen Scales
    "UNG_817": "MINION",           # Tidal Surge
    "UNG_834": "MINION",           # Feeding Time
    "UNG_910": "MINION",           # Grievous Bite
    "UNG_948": "FRIENDLY_MINION",  # Molten Reflection
    "UNG_952": "MINION",           # Spikeridged Steed
    "UNG_955": "MINION",           # Meteor
    "UNG_961": "FRIENDLY_MINION",  # Adaptation
    # Hero Powers
    "UNG_917t1": "BEAST",          # Dinomancy Hero Power
    # Minions
    "UNG_022": "MINION",           # Mirage Caller
    "UNG_047": "FRIENDLY_MINION",  # Ravenous Pterrordax
    "UNG_064": "MINION",           # Vilespine Slayer (Combo only)
    "UNG_073": "FRIENDLY_MURLOC",  # Rockpool Hunter
    "UNG_084": "ANY",              # Fire Plume Phoenix
    "UNG_205": "ENEMY_CHARACTER",  # Glacial Shard
    "UNG_800": "FRIENDLY_DEATHRATTLE",  # Terrorscale Stalker
    "UNG_807": "PIRATE",           # Golakka Crawler
    "UNG_915": "FRIENDLY_BEAST",   # Crackling Razormaw
    "UNG_938": "ANY",              # Hot Spring Guardian
}

COMBO_ONLY_TARGET_CARDS: set[str] = {
    "UNG_064",  # Vilespine Slayer
}

DRAGON_ONLY_TARGET_CARDS: set[str] = set()

CONDITIONAL_TARGET_RULES: dict[str, Callable[..., str]] = {
    "UNG_847": lambda engine, seat, _ex=None: (
        "ANY" if engine.state.players[seat].elemental_last_turn else "NONE"
    ),
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "UNG_101": (  # Shellshifter
        ChooseOption("Raptor Form", "Transform into a 5/3 with Stealth.", "NONE"),
        ChooseOption("Direhorn Form", "Transform into a 3/5 with Taunt.", "NONE"),
    ),
}

DEATHRATTLE_CARDS: set[str] = {
    "UNG_010",    # Sated Threshadon
    "UNG_027",    # Pyros (2/2)
    "UNG_027t2",  # Pyros (6/6)
    "UNG_032",    # Crystalline Oracle
    "UNG_037",    # Tortollan Shellraiser
    "UNG_065",    # Sherazin, Corpse Flower
    "UNG_076",    # Eggnapper
    "UNG_083",    # Devilsaur Egg
    "UNG_086",    # Giant Anaconda
    "UNG_111t1",  # Mana Treant
    "UNG_818",    # Volatile Elemental
    "UNG_830",    # Cruel Dinomancer
    "UNG_845",    # Igneous Elemental
    "UNG_914",    # Raptor Hatchling
    "UNG_953",    # Primalfin Champion
    "UNG_957",    # Direhorn Hatchling
}

SECRET_CARDS: set[str] = {
    "UNG_024",  # Mana Bind
}

AURA_CARDS: set[str] = {
    "UNG_034",  # Radiant Elemental
    "UNG_049",  # Tar Lurker
    "UNG_061",  # Obsidian Shard (cost reduction)
    "UNG_085",  # Emerald Hive Queen
    "UNG_838",  # Tar Lord
    "UNG_928",  # Tar Creeper
}

_DORMANT_TOKENS: frozenset[str] = frozenset({"UNG_065t", "UNG_829t2"})
_KALIMOS_INVOCATIONS: tuple[str, ...] = ("UNG_211a", "UNG_211b", "UNG_211c", "UNG_211d")
_WEAPON_DURABILITY_FIX: frozenset[str] = frozenset({"UNG_061", "UNG_934t1", "UNG_950"})


# ---------------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------------


def _record_non_rogue_class_cards(engine: GameEngine, seat: str) -> set[str]:
    p = engine.state.players[seat]
    seen: set[str] = p.extra_flags.setdefault("obsidian_shard_uids", set())
    for ci in p.hand:
        c = get_card(ci.card_id)
        if c.card_class not in ("NEUTRAL", "ROGUE"):
            seen.add(ci.uid)
    return seen


def _discard_at(engine: GameEngine, seat: str, idx: int) -> None:
    p = engine.state.players[seat]
    if 0 <= idx < len(p.hand):
        ci = helpers.remove_from_hand(engine, seat, idx)
        p.discards_total += 1
        p.discarded_cards.append(ci.card_id)
        engine.add_log(f"{p.name} discarded {get_card(ci.card_id).name}.", seat=seat)
        from engine import expansions
        expansions.on_discard(engine, seat, ci)


def _make_dormant(engine: GameEngine, m: Minion) -> None:
    m.base_keywords.add("DORMANT")
    m.keywords.add("DORMANT")
    engine.recompute_auras()


def _non_quest(c: CardDef) -> bool:
    return not c.has_mechanic("QUEST")


def _draw_specific_from_deck(engine: GameEngine, seat: str, idx: int) -> Optional[CardInstance]:
    ci = helpers.remove_from_deck(engine, seat, idx)
    return engine.give_card_instance_to_hand(seat, ci, origin="deck")


# ---------------------------------------------------------------------------
# PLAYABILITY, COSTS & AURAS
# ---------------------------------------------------------------------------


def can_play_card(engine: GameEngine, seat: str, ci: CardInstance) -> Optional[tuple[bool, str]]:
    p = engine.state.players[seat]
    cid = ci.card_id
    if cid == "UNG_823" and p.weapon is None:  # Envenom Weapon
        return False, "Requires a weapon equipped."
    if cid in ("UNG_829t1", "UNG_948", "UNG_960") and len(p.board) >= 7:
        return False, "Your board is full."
    return None


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    p = engine.state.players[seat]
    card = get_card(ci.card_id)

    # Obsidian Shard: Costs (1) less for each non-Rogue Class card added to your hand this game.
    if card.id == "UNG_061":
        seen = _record_non_rogue_class_cards(engine, seat)
        cost -= len(seen)

    # Radiant Elemental: Your spells cost (1) less (but not less than 1).
    if card.type == "SPELL":
        radiants = sum(1 for m in p.board if not m.silenced and m.card_id == "UNG_034")
        if radiants > 0 and cost > 1:
            cost = max(1, cost - radiants)

    # Emerald Hive Queen: Your minions cost (2) more.
    if card.type == "MINION":
        queens = sum(1 for m in p.board if not m.silenced and m.card_id == "UNG_085")
        cost += 2 * queens

    return cost


def recompute_auras(engine: GameEngine) -> None:
    active = engine.state.active_seat
    for s in ("p1", "p2"):
        pl = engine.state.players[s]
        opp_turn = s != active
        for m in pl.board:
            if m.card_id in _DORMANT_TOKENS:
                m.base_keywords.add("DORMANT")
                m.keywords.add("DORMANT")
                m.attack = 0
                m.max_health = 1
                m.damage = 0
                continue
            if not m.silenced and opp_turn:
                bonus = 0
                if m.card_id == "UNG_049":    # Tar Lurker (+3)
                    bonus = 3
                elif m.card_id == "UNG_838":  # Tar Lord (+4)
                    bonus = 4
                elif m.card_id == "UNG_928":  # Tar Creeper (+2)
                    bonus = 2
                if bonus:
                    m.aura_atk_bonus += bonus
                    m.attack = max(0, m.attack + bonus)


# ---------------------------------------------------------------------------
# SPELLS
# ---------------------------------------------------------------------------


def cast_spell(
    engine: GameEngine,
    seat: str,
    cid: str,
    target_id: Optional[str],
    choose: Optional[int],
    was_combo: bool,
    card_instance: Optional[CardInstance] = None,
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)

    # All 9 Quests
    if cid in helpers.QUEST_DEFS:
        p.trial_card = cid
        p.trial_progress = 0
        p.trial_minions.clear()
        from engine.meta_effects import trial_view
        engine.emit("trial", seat=seat, trial=trial_view(p))
        return True

    if cid == "UNG_004":  # Dinosize: Set a minion's stats to 7/14.
        if target_id:
            engine.add_enchantment(target_id, cid, "Dinosize", set_atk=7, set_hp=14)
        return True

    if cid == "UNG_018":  # Flame Geyser: Deal 2 damage. Add a 1/2 Elemental to your hand.
        if target_id:
            engine.deal_damage(target_id, engine.calc_spell_damage(seat, 2), source_seat=seat, source_name="Flame Geyser")
        engine.add_card_to_hand(seat, "UNG_809t1")
        return True

    if cid == "UNG_025":  # Volcano: Deal 15 damage randomly split among all minions. Overload: (1)
        for _ in range(15):
            cands = [
                m for s in ("p1", "p2") for m in engine.state.players[s].board
                if m.health > 0 and not m.has_keyword("DORMANT")
            ]
            if not cands:
                break
            engine.deal_damage(engine.rng.choice(cands).uid, 1, source_seat=seat, source_name="Volcano")
        return True

    if cid == "UNG_028t":  # Time Warp: Take an extra turn. (Once per game)
        if not p.extra_flags.get("time_warp_used"):
            p.extra_flags["time_warp_used"] = True
            p.extra_turns += 1
            engine.add_log(f"{p.name} will take an extra turn!", seat=seat)
        return True

    if cid == "UNG_029":  # Shadow Visions: Discover a copy of a spell in your deck.
        spells = list(dict.fromkeys(ci.card_id for ci in p.deck if get_card(ci.card_id).type == "SPELL"))
        if spells:
            engine.start_discover(seat, cid, spells)
        return True

    if cid == "UNG_030":  # Binding Heal: Restore 5 Health to a minion and your hero.
        amt = engine.calc_spell_healing(seat, 5)
        if target_id:
            engine.apply_heal(seat, target_id, amt, from_spell_or_power=True)
        engine.apply_heal(seat, f"hero_{seat}", amt, from_spell_or_power=True)
        return True

    if cid == "UNG_057":  # Razorpetal Volley: Add two Razorpetals to your hand.
        for _ in range(2):
            engine.add_card_to_hand(seat, "UNG_057t1")
        return True

    if cid == "UNG_057t1":  # Razorpetal: Deal 2 damage.
        if target_id:
            engine.deal_damage(target_id, engine.calc_spell_damage(seat, 2), source_seat=seat, source_name="Razorpetal")
        return True

    if cid == "UNG_060":  # Mimic Pod: Draw a card, then add a copy of it to your hand.
        drawn = engine.draw_card(seat)
        if drawn:
            engine.add_card_to_hand(seat, drawn.card_id)
        return True

    if cid == "UNG_067t1":  # Crystal Core: For the rest of the game, your minions are 5/5.
        p.crystal_core_active = True
        for m in p.board:
            if not m.has_keyword("DORMANT"):
                m.damage = 0
        engine.recompute_auras()
        engine.add_log(f"{p.name}'s minions are now 5/5 for the rest of the game!", seat=seat)
        return True

    if cid == "UNG_103":  # Evolving Spores: Adapt your minions.
        uids = [m.uid for m in p.board if not m.has_keyword("DORMANT")]
        if uids:
            helpers.start_adapt(engine, seat, uids, cid, remaining=1)
        return True

    if cid == "UNG_108":  # Earthen Scales: Give a friendly minion +1/+1, then gain Armor equal to its Attack.
        if target_id:
            engine.add_enchantment(target_id, cid, "Earthen Scales", atk=1, hp=1)
            m = engine.find_minion(target_id)
            if m:
                p.hero.armor += max(0, m.attack)
        return True

    if cid == "UNG_111":  # Living Mana: Transform your Mana Crystals into 2/2 Treants.
        slots = 7 - len(p.board)
        count = min(p.max_mana, slots)
        if count > 0:
            p.max_mana = max(0, p.max_mana - count)
            p.mana = min(p.mana, p.max_mana)
            for _ in range(count):
                engine.summon_minion(seat, "UNG_111t1")
        return True

    if cid == "UNG_817":  # Tidal Surge: Lifesteal Deal 5 damage to a minion.
        if target_id:
            dealt = engine.deal_damage(target_id, engine.calc_spell_damage(seat, 5), source_seat=seat, source_name="Tidal Surge")
            if dealt > 0:
                engine.apply_heal(seat, f"hero_{seat}", dealt, from_spell_or_power=True)
        return True

    if cid == "UNG_823":  # Envenom Weapon: Give your weapon Poisonous.
        if p.weapon:
            p.weapon.poisonous = True
            engine.add_log(f"{p.name}'s {p.weapon.name} gained Poisonous.", seat=seat)
        return True

    if cid == "UNG_829t1":  # Nether Portal: Open a permanent portal that summons 3/2 Imps.
        portal = engine.summon_minion(seat, "UNG_829t2")
        if portal:
            _make_dormant(engine, portal)
        return True

    if cid == "UNG_831":  # Corrupting Mist: Curse all minions. Destroy them at the start of your next turn.
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if not m.has_keyword("DORMANT"):
                    engine.add_enchantment(m.uid, cid, "Corrupting Mist", destroy_at_owner_sot=seat)
        return True

    if cid == "UNG_832":  # Bloodbloom: The next spell you cast this turn costs Health instead of Mana.
        p.next_spell_costs_health = True
        return True

    if cid == "UNG_834":  # Feeding Time: Deal 3 damage to a minion. Summon three 1/1 Pterrordaxes and Adapt them.
        if target_id:
            engine.deal_damage(target_id, engine.calc_spell_damage(seat, 3), source_seat=seat, source_name="Feeding Time")
        spawned: list[str] = []
        for _ in range(3):
            tok = engine.summon_minion(seat, "UNG_834t1")
            if tok:
                spawned.append(tok.uid)
        if spawned:
            helpers.start_adapt(engine, seat, spawned, cid, remaining=1)
        return True

    if cid == "UNG_851t1":  # Un'Goro Pack: Add 5 Journey to Un'Goro cards to your hand.
        all_ung = helpers.collectible_pool(prefix="UNG_", predicate=_non_quest)
        high_ung = [u for u in all_ung if get_card(u).rarity in ("EPIC", "LEGENDARY")]
        picks: list[str] = []
        if high_ung:
            picks.append(engine.rng.choice(high_ung))
        while len(picks) < 5 and all_ung:
            picks.append(engine.rng.choice(all_ung))
        engine.rng.shuffle(picks)
        for pid in picks:
            engine.add_card_to_hand(seat, pid)
        return True

    if cid == "UNG_854":  # Free From Amber: Discover a minion that costs (8) or more. Summon it.
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="MINION", min_cost=8)
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER_FREE_FROM_AMBER")
        return True

    if cid == "UNG_856":  # Spore Hallucination: Discover a card from your opponent's class.
        opp_class = engine.state.players[opp_seat].hero.card_class
        pool = helpers.collectible_pool(hero_class=opp_class, include_neutral=False, predicate=_non_quest)
        if pool:
            engine.start_discover(seat, cid, pool)
        return True

    if cid == "UNG_910":  # Grievous Bite: Deal 3 damage to a minion and 1 damage to adjacent ones.
        m = engine.find_minion(target_id) if target_id else None
        if m:
            board = engine.state.players[m.owner].board
            idx = board.index(m)
            adj = [board[i].uid for i in (idx - 1, idx + 1) if 0 <= i < len(board)]
            engine.deal_damage(m.uid, engine.calc_spell_damage(seat, 3), source_seat=seat, source_name="Grievous Bite")
            for auid in adj:
                engine.deal_damage(auid, engine.calc_spell_damage(seat, 1), source_seat=seat, source_name="Grievous Bite")
        return True

    if cid == "UNG_916":  # Stampede: Each time you play a Beast this turn, add a random Beast to your hand.
        p.stampede_count += 1
        return True

    if cid == "UNG_917":  # Dinomancy: Replace your Hero Power with 'Give a Beast +3/+3.'
        p.hero.hero_power_id = "UNG_917t1"
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0
        engine.add_log(f"{p.name}'s Hero Power became Dinomancy!", seat=seat)
        return True

    if cid == "UNG_922":  # Explore Un'Goro: Replace your deck with copies of "Discover a card."
        count = len(p.deck)
        for i in range(count - 1, -1, -1):
            helpers.remove_from_deck(engine, seat, i)
        if count > 0:
            engine.shuffle_into_deck(seat, "UNG_922t1", count=count)
        return True

    if cid == "UNG_922t1":  # Choose Your Path: Discover a card.
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, predicate=_non_quest)
        if pool:
            engine.start_discover(seat, cid, pool)
        return True

    if cid == "UNG_923":  # Iron Hide: Gain 5 Armor.
        p.hero.armor += 5
        return True

    if cid == "UNG_927":  # Sudden Genesis: Summon copies of your damaged minions.
        damaged = [m for m in list(p.board) if m.damaged and not m.has_keyword("DORMANT")]
        for src in damaged:
            if len(p.board) >= 7:
                break
            clone = engine.summon_minion(seat, src.card_id)
            if clone:
                engine.copy_minion_into(src, clone)
        return True

    if cid == "UNG_941":  # Primordial Glyph: Discover a spell. Reduce its Cost by (2).
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="SPELL", predicate=_non_quest)
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER_GLYPH")
        return True

    if cid == "UNG_948":  # Molten Reflection: Choose a friendly minion. Summon a copy of it.
        src = engine.find_minion(target_id) if target_id else None
        if src and len(p.board) < 7:
            pos = p.board.index(src) + 1 if src in p.board else None
            clone = engine.summon_minion(seat, src.card_id, pos=pos)
            if clone:
                engine.copy_minion_into(src, clone)
        return True

    if cid == "UNG_952":  # Spikeridged Steed: Give a minion +2/+6 and Taunt. When it dies, summon a Stegodon.
        if target_id:
            engine.add_enchantment(
                target_id,
                cid,
                "Spikeridged Steed",
                atk=2,
                hp=6,
                add_keywords={"TAUNT"},
                extra_deathrattle="SUMMON:UNG_810:1",
            )
        return True

    if cid == "UNG_955":  # Meteor: Deal 15 damage to a minion and 4 damage to adjacent ones.
        m = engine.find_minion(target_id) if target_id else None
        if m:
            board = engine.state.players[m.owner].board
            idx = board.index(m)
            adj = [board[i].uid for i in (idx - 1, idx + 1) if 0 <= i < len(board)]
            engine.deal_damage(m.uid, engine.calc_spell_damage(seat, 15), source_seat=seat, source_name="Meteor")
            for auid in adj:
                engine.deal_damage(auid, engine.calc_spell_damage(seat, 4), source_seat=seat, source_name="Meteor")
        return True

    if cid == "UNG_956":  # Spirit Echo: Give your minions "Deathrattle: Return this to your hand."
        for m in list(p.board):
            if not m.has_keyword("DORMANT"):
                engine.add_enchantment(m.uid, cid, "Spirit Echo", extra_deathrattle=f"ADD_HAND:{m.card_id}")
        return True

    if cid == "UNG_960":  # Lost in the Jungle: Summon two Silver Hand Recruits.
        for _ in range(2):
            engine.summon_minion(seat, "VAN_CS2_101t")
        return True

    if cid == "UNG_961":  # Adaptation: Adapt a friendly minion.
        if target_id and engine.find_minion(target_id):
            helpers.start_adapt(engine, seat, [target_id], cid, remaining=1)
        return True

    return False


# ---------------------------------------------------------------------------
# BATTLECRIES & WEAPON EQUIP EFFECTS
# ---------------------------------------------------------------------------


def trigger_battlecry(
    engine: GameEngine,
    seat: str,
    cid: str,
    minion: Optional[Minion],
    target_id: Optional[str],
    choose: Optional[int],
    was_combo: bool,
    card_instance: Optional[CardInstance] = None,
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    # Fix UNG weapons whose catalog entry stores durability in health (durability=0)
    if cid in _WEAPON_DURABILITY_FIX and p.weapon and p.weapon.card_id == cid:
        cdef = get_card(cid)
        if not cdef.durability and cdef.health:
            p.weapon.durability = cdef.health
            p.weapon.max_durability = cdef.health

    if cid in ("UNG_061", "UNG_929", "UNG_950"):  # Obsidian Shard / Molten Blade / Vinecleaver
        return True

    if cid == "UNG_934t1":  # Sulfuras: Battlecry: Hero Power becomes DIE, INSECT!
        p.hero.hero_power_id = "UNG_934t2"
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0
        engine.add_log(f"{p.name}'s Hero Power became DIE, INSECT!!", seat=seat)
        return True

    if cid == "UNG_001":  # Pterrordax Hatchling: Battlecry: Adapt.
        if minion:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=1)
        return True

    if cid == "UNG_002":  # Volcanosaur: Battlecry: Adapt, then Adapt.
        if minion:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=2)
        return True

    if cid == "UNG_009":  # Ravasaur Runt: If you control at least 2 other minions, Adapt.
        if minion and sum(1 for m in p.board if m.uid != minion.uid) >= 2:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=1)
        return True

    if cid == "UNG_011":  # Hydrologist: Battlecry: Discover and cast a Secret.
        active = {s.card_id for s in p.secrets}
        all_sec = helpers.collectible_pool(
            hero_class=p.hero.card_class, card_type="SPELL", mechanic="SECRET", include_neutral=False
        )
        if not all_sec:
            all_sec = helpers.collectible_pool(
                hero_class="PALADIN", card_type="SPELL", mechanic="SECRET", include_neutral=False
            )
        pool = [s for s in all_sec if s not in active]
        if len(pool) < 3:
            pool = all_sec
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER_HYDROLOGIST")
        return True

    if cid == "UNG_015":  # Sunkeeper Tarim: Set all other minions' Attack and Health to 3.
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if (not minion or m.uid != minion.uid) and not m.has_keyword("DORMANT"):
                    engine.add_enchantment(m.uid, cid, "Sunkeeper Tarim", set_atk=3, set_hp=3)
        return True

    if cid == "UNG_020":  # Arcanologist: Battlecry: Draw a Secret.
        cands = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).has_mechanic("SECRET")]
        if cands:
            _draw_specific_from_deck(engine, seat, engine.rng.choice(cands))
        return True

    if cid == "UNG_021":  # Steam Surger: If you played an Elemental last turn, add a 'Flame Geyser' to your hand.
        if p.elemental_last_turn:
            engine.add_card_to_hand(seat, "UNG_018")
        return True

    if cid == "UNG_022":  # Mirage Caller: Choose a minion. Summon a 1/1 copy of it.
        src = engine.find_minion(target_id) if target_id else None
        if src and len(p.board) < 7:
            pos = p.board.index(minion) + 1 if (minion and minion in p.board) else None
            clone = engine.summon_minion(seat, src.card_id, pos=pos)
            if clone:
                engine.copy_minion_into(src, clone)
                engine.add_enchantment(clone.uid, cid, "Mirage Caller", set_atk=1, set_hp=1)
        return True

    if cid == "UNG_035":  # Curious Glimmerroot: Look at 3 cards. Guess which started in opponent's deck.
        started_ids = list(dict.fromkeys(ci.card_id for ci in opp.deck + opp.hand if ci.started_in_deck))
        if not started_ids:
            started_ids = list(dict.fromkeys(ci.card_id for ci in opp.deck + opp.hand))
        if started_ids:
            correct_id = engine.rng.choice(started_ids)
            started_set = set(started_ids)
            distractors = helpers.collectible_pool(
                hero_class=opp.hero.card_class,
                include_neutral=False,
                predicate=lambda c: c.id not in started_set and _non_quest(c),
            )
            if len(distractors) < 2:
                distractors = helpers.collectible_pool(
                    hero_class=opp.hero.card_class,
                    predicate=lambda c: c.id not in started_set and _non_quest(c),
                )
            option_ids = [correct_id] + engine.rng.sample(distractors, min(2, len(distractors)))
            engine.rng.shuffle(option_ids)
            opts = [CardInstance(uid=engine._new_uid("c"), card_id=oid) for oid in option_ids]
            engine.state.pending_choice = PendingChoice(
                seat=seat,
                choice_type="DISCOVER_GLIMMERROOT",
                source_card_id=cid,
                options=opts,
                meta={"correct_id": correct_id},
            )
        return True

    if cid == "UNG_047":  # Ravenous Pterrordax: Destroy a friendly minion to Adapt twice.
        tm = engine.find_minion(target_id) if target_id else None
        if tm and minion and tm.owner == seat and tm.uid != minion.uid:
            engine.destroy_minion(tm.uid)
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=2)
        return True

    if cid == "UNG_058":  # Razorpetal Lasher: Add a Razorpetal to your hand.
        engine.add_card_to_hand(seat, "UNG_057t1")
        return True

    if cid == "UNG_063":  # Biteweed: Combo: Gain +1/+1 for each other card you've played this turn.
        if was_combo and minion:
            others = max(0, p.cards_played_this_turn - 1)
            if others > 0:
                engine.add_enchantment(minion.uid, cid, "Biteweed", atk=others, hp=others)
        return True

    if cid == "UNG_064":  # Vilespine Slayer: Combo: Destroy a minion.
        if was_combo and target_id:
            engine.destroy_minion(target_id)
        return True

    if cid == "UNG_070":  # Tol'vir Stoneshaper: If you played an Elemental last turn, gain Taunt and Divine Shield.
        if minion and p.elemental_last_turn:
            engine.add_enchantment(minion.uid, cid, "Tol'vir Stoneshaper", add_keywords={"TAUNT", "DIVINE_SHIELD"})
        return True

    if cid == "UNG_072":  # Stonehill Defender: Discover a Taunt minion.
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="MINION", mechanic="TAUNT")
        if pool:
            engine.start_discover(seat, cid, pool)
        return True

    if cid == "UNG_073":  # Rockpool Hunter: Give a friendly Murloc +1/+1.
        if target_id:
            engine.add_enchantment(target_id, cid, "Rockpool Hunter", atk=1, hp=1)
        return True

    if cid == "UNG_078":  # Tortollan Forager: Add a random minion with 5 or more Attack to your hand.
        pool = helpers.collectible_pool(card_type="MINION", predicate=lambda c: (c.attack or 0) >= 5)
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "UNG_082":  # Thunder Lizard: If you played an Elemental last turn, Adapt.
        if minion and p.elemental_last_turn:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=1)
        return True

    if cid == "UNG_084":  # Fire Plume Phoenix: Deal 3 damage.
        if target_id:
            engine.deal_damage(target_id, 3, source_seat=seat, source_name="Fire Plume Phoenix", source_minion=minion)
        return True

    if cid == "UNG_088":  # Tortollan Primalist: Discover a spell and cast it with random targets.
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="SPELL", predicate=_non_quest)
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER_PRIMALIST")
        return True

    if cid == "UNG_089":  # Gentle Megasaur: Adapt your Murlocs.
        uids = [m.uid for m in p.board if m.race == "MURLOC" and not m.has_keyword("DORMANT")]
        if uids:
            helpers.start_adapt(engine, seat, uids, cid, remaining=1)
        return True

    if cid == "UNG_099":  # Charged Devilsaur: Can't attack heroes this turn.
        if minion:
            minion.cant_attack_hero_this_turn = True
        return True

    if cid == "UNG_100":  # Verdant Longneck: Adapt.
        if minion:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=1)
        return True

    if cid == "UNG_101":  # Shellshifter: Choose One - 5/3 Stealth or 3/5 Taunt (5/5 both with Fandral).
        if minion:
            if engine.has_fandral(seat):
                engine.transform_minion(minion.uid, "UNG_101t3")
            elif choose == 0:
                engine.transform_minion(minion.uid, "UNG_101t")
            else:
                engine.transform_minion(minion.uid, "UNG_101t2")
        return True

    if cid == "UNG_109":  # Elder Longneck: If holding a minion with 5+ Attack, Adapt.
        if minion and any(
            (c := get_card(ci.card_id)).type == "MINION" and ((c.attack or 0) + ci.attack_mod) >= 5
            for ci in p.hand
        ):
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=1)
        return True

    if cid == "UNG_113":  # Bright-Eyed Scout: Draw a card. Change its Cost to (5).
        drawn = engine.draw_card(seat)
        if drawn:
            drawn.cost_mod = 5 - get_card(drawn.card_id).cost
        return True

    if cid == "UNG_116t":  # Barnabus the Stomper: Reduce the Cost of minions in your deck to (0).
        for ci in p.deck:
            c = get_card(ci.card_id)
            if c.type == "MINION":
                ci.cost_mod = -c.cost
        engine.add_log(f"{p.name}'s deck minions now cost (0)!", seat=seat)
        return True

    if cid == "UNG_202":  # Fire Plume Harbinger: Reduce the Cost of Elementals in your hand by (1).
        for ci in p.hand:
            if get_card(ci.card_id).race == "ELEMENTAL":
                ci.cost_mod -= 1
        return True

    if cid == "UNG_205":  # Glacial Shard: Freeze an enemy.
        if target_id:
            engine.freeze_character(target_id)
        return True

    if cid == "UNG_208":  # Stone Sentinel: If you played an Elemental last turn, summon two 2/3 Taunts.
        if p.elemental_last_turn:
            pos = p.board.index(minion) + 1 if (minion and minion in p.board) else None
            for _ in range(2):
                engine.summon_minion(seat, "UNG_208t", pos=pos)
        return True

    if cid == "UNG_211":  # Kalimos, Primal Lord: If you played an Elemental last turn, cast an Invocation.
        if p.elemental_last_turn:
            opts = [CardInstance(uid=engine._new_uid("c"), card_id=oid) for oid in _KALIMOS_INVOCATIONS]
            engine.state.pending_choice = PendingChoice(
                seat=seat,
                choice_type="KALIMOS",
                source_card_id=cid,
                options=opts,
            )
        return True

    if cid == "UNG_800":  # Terrorscale Stalker: Trigger a friendly minion's Deathrattle.
        tm = engine.find_minion(target_id) if target_id else None
        if tm and tm.owner == seat:
            helpers.trigger_minion_deathrattle(engine, tm)
        return True

    if cid == "UNG_801":  # Nesting Roc: If you control at least 2 other minions, gain Taunt.
        if minion and sum(1 for m in p.board if m.uid != minion.uid) >= 2:
            engine.add_enchantment(minion.uid, cid, "Nesting Roc", add_keywords={"TAUNT"})
        return True

    if cid == "UNG_803":  # Emerald Reaver: Deal 1 damage to each hero.
        engine.deal_damage(f"hero_{seat}", 1, source_seat=seat, source_name="Emerald Reaver", source_minion=minion)
        engine.deal_damage(f"hero_{opp_seat}", 1, source_seat=seat, source_name="Emerald Reaver", source_minion=minion)
        return True

    if cid == "UNG_807":  # Golakka Crawler: Destroy a Pirate and gain +1/+1.
        tm = engine.find_minion(target_id) if target_id else None
        if tm and tm.race == "PIRATE":
            engine.destroy_minion(tm.uid)
            if minion:
                engine.add_enchantment(minion.uid, cid, "Golakka Crawler", atk=1, hp=1)
        return True

    if cid == "UNG_809":  # Fire Fly: Add a 1/2 Elemental to your hand.
        engine.add_card_to_hand(seat, "UNG_809t1")
        return True

    if cid == "UNG_816":  # Servant of Kalimos: If you played an Elemental last turn, Discover an Elemental.
        if p.elemental_last_turn:
            pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="MINION", race="ELEMENTAL")
            if pool:
                engine.start_discover(seat, cid, pool)
        return True

    if cid == "UNG_833":  # Lakkari Felhound: Discard your two lowest-Cost cards.
        for _ in range(2):
            if not p.hand:
                break
            costs = [engine.get_card_cost(seat, ci) for ci in p.hand]
            low = min(costs)
            low_idxs = [i for i, c in enumerate(costs) if c == low]
            _discard_at(engine, seat, engine.rng.choice(low_idxs))
        return True

    if cid == "UNG_835":  # Chittering Tunneler: Discover a spell. Deal damage to your hero equal to its Cost.
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="SPELL", predicate=_non_quest)
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER_TUNNELER")
        return True

    if cid == "UNG_840":  # Hemet, Jungle Hunter: Destroy all cards in your deck that cost (3) or less.
        destroyed = 0
        for i in range(len(p.deck) - 1, -1, -1):
            if get_card(p.deck[i].card_id).cost <= 3:
                helpers.remove_from_deck(engine, seat, i)
                destroyed += 1
        if destroyed:
            engine.add_log(f"Hemet, Jungle Hunter destroyed {destroyed} card(s) in {p.name}'s deck.", seat=seat)
        return True

    if cid == "UNG_846":  # Shimmering Tempest: Battlecry: Add a random Mage spell to your hand.
        pool = helpers.collectible_pool(
            hero_class="MAGE", card_type="SPELL", include_neutral=False, predicate=_non_quest
        )
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "UNG_847":  # Blazecaller: If you played an Elemental last turn, deal 5 damage.
        if p.elemental_last_turn and target_id:
            engine.deal_damage(target_id, 5, source_seat=seat, source_name="Blazecaller", source_minion=minion)
        return True

    if cid == "UNG_848":  # Primordial Drake: Deal 2 damage to all other minions.
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if not minion or m.uid != minion.uid:
                    engine.deal_damage(m.uid, 2, source_seat=seat, source_name="Primordial Drake", source_minion=minion)
        return True

    if cid == "UNG_851":  # Elise the Trailblazer: Shuffle an Un'Goro Pack; if no duplicates, draw it.
        no_dups = engine.has_no_duplicates_in_deck(seat)
        engine.shuffle_into_deck(seat, "UNG_851t1", count=1)
        if no_dups:
            idx = next((i for i, ci in enumerate(p.deck) if ci.card_id == "UNG_851t1"), None)
            if idx is not None:
                _draw_specific_from_deck(engine, seat, idx)
        return True

    if cid == "UNG_907":  # Ozruk: Gain +5 Health for each Elemental you played last turn.
        cnt = int(p.extra_flags.get("elementals_last_turn_count", 0))
        if cnt == 0 and p.elemental_last_turn:
            cnt = 1
        if minion and cnt > 0:
            engine.add_enchantment(minion.uid, cid, "Ozruk", hp=5 * cnt)
        return True

    if cid == "UNG_912":  # Jeweled Macaw: Add a random Beast to your hand.
        pool = helpers.collectible_pool(card_type="MINION", race="BEAST")
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "UNG_913":  # Tol'vir Warden: Draw two 1-Cost minions from your deck.
        for _ in range(2):
            cands = [
                i for i, ci in enumerate(p.deck)
                if (c := get_card(ci.card_id)).type == "MINION" and c.cost == 1
            ]
            if not cands:
                break
            _draw_specific_from_deck(engine, seat, engine.rng.choice(cands))
        return True

    if cid == "UNG_915":  # Crackling Razormaw: Adapt a friendly Beast.
        tm = engine.find_minion(target_id) if target_id else None
        if tm and tm.owner == seat and tm.race == "BEAST":
            helpers.start_adapt(engine, seat, [tm.uid], cid, remaining=1)
        return True

    if cid == "UNG_920t1":  # Queen Carnassa: Shuffle 20 Raptors into your deck.
        engine.shuffle_into_deck(seat, "UNG_920t2", count=20)
        return True

    if cid == "UNG_920t2":  # Carnassa's Brood: Draw a card.
        engine.draw_card(seat)
        return True

    if cid == "UNG_925":  # Ornery Direhorn: Adapt.
        if minion:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=1)
        return True

    if cid == "UNG_926":  # Cornered Sentry: Summon three 1/1 Raptors for your opponent.
        for _ in range(3):
            engine.summon_minion(opp_seat, "UNG_076t1")
        return True

    if cid == "UNG_933":  # King Mosh: Destroy all damaged minions.
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if m.damaged and not m.has_keyword("DORMANT"):
                    engine.destroy_minion(m.uid)
        return True

    if cid == "UNG_937":  # Primalfin Lookout: If you control another Murloc, Discover a Murloc.
        if any(m.race == "MURLOC" and (not minion or m.uid != minion.uid) for m in p.board):
            pool = helpers.collectible_pool(hero_class=p.hero.card_class, card_type="MINION", race="MURLOC")
            if pool:
                engine.start_discover(seat, cid, pool)
        return True

    if cid == "UNG_938":  # Hot Spring Guardian: Restore 3 Health.
        if target_id:
            engine.apply_heal(seat, target_id, 3)
        return True

    if cid == "UNG_940t8":  # Amara, Warden of Hope: Set your hero's Health to 40.
        p.hero.max_hp = 40
        p.hero.hp = 40
        engine.add_log(f"{p.name}'s hero Health was set to 40!", seat=seat)
        return True

    if cid == "UNG_942t":  # Megafin: Fill your hand with random Murlocs.
        murlocs = helpers.collectible_pool(card_type="MINION", race="MURLOC")
        while len(p.hand) < 10 and murlocs:
            engine.add_card_to_hand(seat, engine.rng.choice(murlocs))
        return True

    if cid == "UNG_946":  # Gluttonous Ooze: Destroy opponent's weapon and gain Armor equal to its Attack.
        if opp.weapon:
            atk = opp.weapon.total_attack
            engine.destroy_weapon(opp_seat)
            p.hero.armor += max(0, atk)
        return True

    if cid == "UNG_954t1":  # Galvadon: Adapt 5 times.
        if minion:
            helpers.start_adapt(engine, seat, [minion.uid], cid, remaining=5)
        return True

    if cid == "UNG_962":  # Lightfused Stegodon: Adapt your Silver Hand Recruits.
        uids = [m.uid for m in p.board if m.card_id == "VAN_CS2_101t" and not m.has_keyword("DORMANT")]
        if uids:
            helpers.start_adapt(engine, seat, uids, cid, remaining=1)
        return True

    return False


# ---------------------------------------------------------------------------
# DEATHRATTLES
# ---------------------------------------------------------------------------


def trigger_deathrattle(
    engine: GameEngine,
    seat: str,
    cid: str,
    orig_pos: int,
    dead_minion: Optional[Minion] = None,
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    if cid == "UNG_010":  # Sated Threshadon: Summon three 1/1 Murlocs.
        for _ in range(3):
            engine.summon_minion(seat, "UNG_201t", pos=orig_pos)
        return True

    if cid == "UNG_027":  # Pyros (2/2) -> 6/6 that costs (4)
        engine.add_card_to_hand(seat, "UNG_027t2")
        return True

    if cid == "UNG_027t2":  # Pyros (6/6) -> 10/10 that costs (8)
        engine.add_card_to_hand(seat, "UNG_027t4")
        return True

    if cid == "UNG_032":  # Crystalline Oracle: Copy a card from opponent's deck to your hand.
        if opp.deck:
            engine.add_card_to_hand(seat, engine.rng.choice(opp.deck).card_id)
        return True

    if cid == "UNG_037":  # Tortollan Shellraiser: Give a random friendly minion +1/+1.
        cands = [m for m in p.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if cands:
            engine.add_enchantment(engine.rng.choice(cands).uid, cid, "Tortollan Shellraiser", atk=1, hp=1)
        return True

    if cid == "UNG_065":  # Sherazin, Corpse Flower: Go Dormant as Sherazin, Seed.
        seed = engine.summon_minion(seat, "UNG_065t", pos=orig_pos)
        if seed:
            seed.extra_data["sherazin_cards"] = 0
            _make_dormant(engine, seed)
        return True

    if cid == "UNG_076":  # Eggnapper: Summon two 1/1 Raptors.
        for _ in range(2):
            engine.summon_minion(seat, "UNG_076t1", pos=orig_pos)
        return True

    if cid == "UNG_083":  # Devilsaur Egg: Summon a 5/5 Devilsaur.
        engine.summon_minion(seat, "UNG_083t1", pos=orig_pos)
        return True

    if cid == "UNG_086":  # Giant Anaconda: Summon a minion from your hand with 5 or more Attack.
        cands = [
            i for i, ci in enumerate(p.hand)
            if (c := get_card(ci.card_id)).type == "MINION" and ((c.attack or 0) + ci.attack_mod) >= 5
        ]
        if cands and len(p.board) < 7:
            engine.summon_minion_from_hand(seat, engine.rng.choice(cands), orig_pos)
        return True

    if cid == "UNG_111t1":  # Mana Treant: Gain an empty Mana Crystal.
        if p.max_mana < 10:
            p.max_mana += 1
        return True

    if cid == "UNG_818":  # Volatile Elemental: Deal 3 damage to a random enemy minion.
        cands = [m for m in opp.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if cands:
            engine.deal_damage(engine.rng.choice(cands).uid, 3, source_seat=seat, source_name="Volatile Elemental")
        return True

    if cid == "UNG_830":  # Cruel Dinomancer: Summon a random minion you discarded this game.
        minions = [dcid for dcid in p.discarded_cards if get_card(dcid).type == "MINION"]
        if minions:
            engine.summon_minion(seat, engine.rng.choice(minions), pos=orig_pos)
        return True

    if cid == "UNG_845":  # Igneous Elemental: Add two 1/2 Flame Elementals to your hand.
        for _ in range(2):
            engine.add_card_to_hand(seat, "UNG_809t1")
        return True

    if cid == "UNG_914":  # Raptor Hatchling: Shuffle a 4/5 Raptor into your deck.
        engine.shuffle_into_deck(seat, "UNG_914t1", count=1)
        return True

    if cid == "UNG_953":  # Primalfin Champion: Return any spells you cast on this minion to your hand.
        if dead_minion:
            for scid in list(dead_minion.extra_data.get("primalfin_spells") or ()):
                engine.add_card_to_hand(seat, scid)
        return True

    if cid == "UNG_957":  # Direhorn Hatchling: Shuffle an 8/12 Direhorn with Taunt into your deck.
        engine.shuffle_into_deck(seat, "UNG_957t1", count=1)
        return True

    return False


# ---------------------------------------------------------------------------
# HERO POWERS
# ---------------------------------------------------------------------------


def trigger_hero_power(engine: GameEngine, seat: str, hp_id: str, target_id: Optional[str]) -> bool:
    if hp_id == "UNG_917t1":  # Dinomancy: Give a Beast +3/+3.
        if target_id:
            engine.add_enchantment(target_id, hp_id, "Dinomancy", atk=3, hp=3)
        return True

    if hp_id == "UNG_934t2":  # DIE, INSECT!: Deal 8 damage to a random enemy.
        cands = engine.living_enemy_characters(seat)
        if cands:
            engine.deal_damage(
                engine.rng.choice(cands),
                8 * engine.velen_multiplier(seat),
                source_seat=seat,
                source_name="DIE, INSECT!",
            )
        return True

    return False


# ---------------------------------------------------------------------------
# PENDING CHOICES
# ---------------------------------------------------------------------------


def resolve_pending_choice(
    engine: GameEngine,
    seat: str,
    pc: PendingChoice,
    picked: CardInstance,
    option_index: int,
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]
    ct = pc.choice_type

    if ct == "DISCOVER_HYDROLOGIST":
        helpers.put_secret_into_play(engine, seat, picked.card_id)
        engine.add_log(f"{p.name} discovered and cast a Secret from Hydrologist.", seat=seat)
        return True

    if ct == "DISCOVER_GLIMMERROOT":
        correct_id = pc.meta.get("correct_id")
        if picked.card_id == correct_id:
            engine.add_card_to_hand(seat, picked.card_id)
            engine.add_log(f"{p.name} guessed correctly with Curious Glimmerroot!", seat=seat)
        else:
            engine.add_log(f"{p.name} guessed wrong with Curious Glimmerroot.", seat=seat)
        return True

    if ct == "DISCOVER_PRIMALIST":
        helpers.cast_random_spell(engine, seat, picked.card_id)
        return True

    if ct == "KALIMOS":
        oid = picked.card_id
        if oid == "UNG_211a":    # Invocation of Earth: Fill board with 1/1 Elementals.
            while len(p.board) < 7:
                if not engine.summon_minion(seat, "UNG_211aa"):
                    break
        elif oid == "UNG_211b":  # Invocation of Water: Restore 12 Health to your hero.
            engine.apply_heal(seat, f"hero_{seat}", 12)
        elif oid == "UNG_211c":  # Invocation of Fire: Deal 6 damage to the enemy hero.
            engine.deal_damage(f"hero_{opp_seat}", 6, source_seat=seat, source_name="Invocation of Fire")
        elif oid == "UNG_211d":  # Invocation of Air: Deal 3 damage to all enemy minions.
            for m in list(opp.board):
                engine.deal_damage(m.uid, 3, source_seat=seat, source_name="Invocation of Air")
        engine.add_log(f"{p.name} cast {get_card(oid).name}!", seat=seat)
        return True

    if ct == "DISCOVER_TUNNELER":
        engine.give_card_instance_to_hand(seat, picked, origin="choice")
        dmg = get_card(picked.card_id).cost
        if dmg > 0:
            engine.deal_damage(f"hero_{seat}", dmg, source_seat=seat, source_name="Chittering Tunneler")
        return True

    if ct == "DISCOVER_FREE_FROM_AMBER":
        engine.summon_minion(seat, picked.card_id)
        engine.add_log(f"{p.name} summoned {get_card(picked.card_id).name} from Free From Amber.", seat=seat)
        return True

    if ct == "DISCOVER_GLYPH":
        picked.cost_mod -= 2
        engine.give_card_instance_to_hand(seat, picked, origin="choice")
        engine.add_log(f"{p.name} discovered a discounted spell with Primordial Glyph.", seat=seat)
        return True

    return False


# ---------------------------------------------------------------------------
# SECRETS
# ---------------------------------------------------------------------------


def trigger_secrets_on_spell(
    engine: GameEngine,
    def_seat: str,
    card: CardDef,
    target_id: Optional[str],
) -> bool:
    p = engine.state.players[def_seat]
    for sec in list(p.secrets):
        if sec.card_id == "UNG_024":  # Mana Bind
            engine._reveal_secret(def_seat, sec)
            engine.add_card_to_hand(def_seat, card.id, cost_mod=-card.cost)
            return True
    return False


# ---------------------------------------------------------------------------
# TURN, CARD, SUMMON, SPELL, DAMAGE, ATTACK & DISCARD TRIGGERS
# ---------------------------------------------------------------------------


def on_start_turn(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    # Shift Ozruk's Elemental counter
    p.extra_flags["elementals_last_turn_count"] = int(p.extra_flags.get("elementals_this_turn_count", 0))
    p.extra_flags["elementals_this_turn_count"] = 0

    # Reset Sherazin Seed's per-turn card counter
    for m in p.board:
        if m.card_id == "UNG_065t":
            m.extra_data["sherazin_cards"] = 0

    # Molten Blade transforms into a random weapon in hand each turn
    weapons = [w for w in helpers.collectible_pool(card_type="WEAPON") if w != "UNG_929"]
    if weapons:
        for ci in p.hand:
            if ci.card_id == "UNG_929" or ci.extra_data.get("is_molten_blade"):
                ci.extra_data["is_molten_blade"] = True
                ci.card_id = engine.rng.choice(weapons)

    # Track non-Rogue class cards in hand for Obsidian Shard
    _record_non_rogue_class_cards(engine, seat)


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    p = engine.state.players[seat]
    cid = minion.card_id
    if cid == "UNG_201":  # Primalfin Totem: Summon a 1/1 Murloc.
        pos = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "UNG_201t", pos=pos)
    elif cid == "UNG_829t2":  # Nether Portal: Summon two 3/2 Imps.
        pos = p.board.index(minion) + 1 if minion in p.board else None
        for _ in range(2):
            engine.summon_minion(seat, "UNG_829t3", pos=pos)


def on_card_played(engine: GameEngine, seat: str, card: CardDef, ci: CardInstance) -> None:
    p = engine.state.players[seat]

    # Track non-Rogue class cards for Obsidian Shard
    if card.card_class not in ("NEUTRAL", "ROGUE"):
        p.extra_flags.setdefault("obsidian_shard_uids", set()).add(ci.uid)

    # Open the Waygate: Cast spells that didn't start in your deck.
    if p.trial_card == "UNG_028" and card.type == "SPELL" and card.id != "UNG_028" and not ci.started_in_deck:
        helpers.advance_quest(engine, seat, "UNG_028", 1)

    # Sherazin, Seed: Play 4 cards in a turn to revive this minion.
    for m in list(p.board):
        if m.card_id == "UNG_065t":
            cnt = int(m.extra_data.get("sherazin_cards", 0)) + 1
            m.extra_data["sherazin_cards"] = cnt
            if cnt >= 4:
                engine.transform_minion(m.uid, "UNG_065")
                engine.add_log(f"Sherazin, Corpse Flower revived for {p.name}!", seat=seat)


def on_minion_played(engine: GameEngine, seat: str, card: CardDef, minion: Optional[Minion]) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    # Count Elementals played this turn for Ozruk
    if card.race == "ELEMENTAL":
        p.extra_flags["elementals_this_turn_count"] = int(p.extra_flags.get("elementals_this_turn_count", 0)) + 1

    # Stampede: Add a random Beast to your hand each time you play a Beast this turn.
    if card.race == "BEAST" and p.stampede_count > 0:
        beasts = helpers.collectible_pool(card_type="MINION", race="BEAST")
        for _ in range(p.stampede_count):
            if beasts:
                engine.add_card_to_hand(seat, engine.rng.choice(beasts))

    # Quest: The Caverns Below (Play 4 minions with the same name)
    if p.trial_card == "UNG_067":
        cnt = p.trial_minions.get(card.name, 0) + 1
        p.trial_minions[card.name] = cnt
        if cnt > p.trial_progress:
            helpers.advance_quest(engine, seat, "UNG_067", delta=cnt - p.trial_progress)

    # Quest: The Marsh Queen (Play seven 1-Cost minions)
    elif p.trial_card == "UNG_920" and card.cost == 1:
        helpers.advance_quest(engine, seat, "UNG_920", 1)

    # Quest: Fire Plume's Heart (Play 7 Taunt minions)
    elif p.trial_card == "UNG_934" and card.has_mechanic("TAUNT"):
        helpers.advance_quest(engine, seat, "UNG_934", 1)

    # Swamp King Dred: After your opponent plays a minion, attack it.
    if minion:
        for dred in list(opp.board):
            if (
                dred in opp.board
                and not dred.silenced
                and dred.card_id == "UNG_919"
                and dred.health > 0
                and dred.attack > 0
                and minion in p.board
                and minion.health > 0
                and not minion.has_keyword("DORMANT")
            ):
                engine.break_stealth(dred)
                engine.emit("attack", seat=opp_seat, attacker=dred.uid, target=minion.uid)
                engine.add_log(f"Swamp King Dred attacked {minion.name}!", seat=opp_seat)
                d_atk = dred.attack
                m_atk = minion.attack
                engine._combat = True
                try:
                    engine.deal_damage(minion.uid, d_atk, source_seat=opp_seat, source_name=dred.name, source_minion=dred)
                    if m_atk > 0:
                        engine.deal_damage(dred.uid, m_atk, source_seat=seat, source_name=minion.name, source_minion=minion)
                finally:
                    engine._combat = False
                engine.resolve_deaths()
                engine.recompute_auras()


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    p = engine.state.players[seat]

    # Quest: Jungle Giants (Summon minions with 5 or more Attack)
    if p.trial_card == "UNG_116" and minion.attack >= 5 and not minion.has_keyword("DORMANT"):
        helpers.advance_quest(engine, seat, "UNG_116", 1)

    # Quest: Awaken the Makers (Summon Deathrattle minions)
    elif p.trial_card == "UNG_940" and not minion.has_keyword("DORMANT"):
        from engine.effects import DEATHRATTLE_CARDS as ALL_DR
        if get_card(minion.card_id).has_mechanic("DEATHRATTLE") or minion.card_id in ALL_DR:
            helpers.advance_quest(engine, seat, "UNG_940", 1)

    # Quest: Unite the Murlocs (Summon Murlocs)
    elif p.trial_card == "UNG_942" and minion.race == "MURLOC":
        helpers.advance_quest(engine, seat, "UNG_942", 1)

    # Spiritsinger Umbra: After you summon a minion, trigger its Deathrattle effect.
    depth = int(p.extra_flags.get("_umbra_depth", 0))
    if depth < 8 and not minion.silenced and not minion.has_keyword("DORMANT"):
        from engine.effects import DEATHRATTLE_CARDS as ALL_DR
        has_dr = minion.card_id in ALL_DR or any(e.extra_deathrattle for e in minion.enchantments)
        if has_dr:
            umbras = [
                bm for bm in list(p.board)
                if not bm.silenced and bm.card_id == "UNG_900" and bm.uid != minion.uid and bm.health > 0
            ]
            if umbras:
                p.extra_flags["_umbra_depth"] = depth + 1
                try:
                    for _ in umbras:
                        if minion in p.board:
                            helpers.trigger_minion_deathrattle(engine, minion)
                finally:
                    p.extra_flags["_umbra_depth"] = depth


def on_spell_cast(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]

    # Lyra the Sunshard: Whenever you cast a spell, add a random Priest spell to your hand.
    lyras = sum(1 for m in p.board if not m.silenced and m.card_id == "UNG_963" and m.health > 0)
    if lyras > 0:
        pool = helpers.collectible_pool(
            hero_class="PRIEST", card_type="SPELL", include_neutral=False, predicate=_non_quest
        )
        for _ in range(lyras):
            if pool:
                engine.add_card_to_hand(seat, engine.rng.choice(pool))

    # Targeted friendly minion triggers (The Last Kaleidosaur + Primalfin Champion)
    if target_id and not target_id.startswith("hero_"):
        tm = engine.find_minion(target_id)
        if tm and tm.owner == seat:
            if p.trial_card == "UNG_954":
                helpers.advance_quest(engine, seat, "UNG_954", 1)
            if not tm.silenced and tm.card_id == "UNG_953":
                tm.extra_data.setdefault("primalfin_spells", []).append(card.id)


def on_after_spell(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]

    # The Voraxx: After you cast a spell on this minion, summon a 1/1 Plant and cast another copy on it.
    if target_id and not target_id.startswith("hero_") and not p.extra_flags.get("_voraxx_active"):
        m = engine.find_minion(target_id)
        if m and m.owner == seat and not m.silenced and m.card_id == "UNG_843" and m.health > 0:
            pos = p.board.index(m) + 1 if m in p.board else None
            plant = engine.summon_minion(seat, "UNG_999t2t1", pos=pos)
            if plant:
                from engine.effects import CHOOSE_ONE_OPTIONS as ALL_CHOOSE
                from engine.effects import cast_spell as engine_cast_spell
                choose = 0 if card.id in ALL_CHOOSE else None
                p.extra_flags["_voraxx_active"] = True
                try:
                    engine_cast_spell(engine, seat, card.id, plant.uid, choose, False)
                finally:
                    p.extra_flags["_voraxx_active"] = False


def on_damage_minion(
    engine: GameEngine,
    m: Minion,
    amount: int,
    source_seat: Optional[str],
    source_minion: Optional[Minion],
) -> None:
    # Bittertide Hydra: Whenever this minion takes damage, deal 3 damage to your hero.
    if not m.silenced and m.card_id == "UNG_087" and amount > 0:
        engine.deal_damage(f"hero_{m.owner}", 3, source_seat=m.owner, source_name="Bittertide Hydra", source_minion=m)


def on_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    p = engine.state.players[seat]
    p.extra_flags["_vinecleaver_swing"] = (
        attacker_id == f"hero_{seat}" and p.weapon is not None and p.weapon.card_id == "UNG_950"
    )
    return target_id, False


def on_after_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> None:
    p = engine.state.players[seat]

    # Vinecleaver: After your hero attacks, summon two Silver Hand Recruits.
    if attacker_id == f"hero_{seat}" and p.extra_flags.pop("_vinecleaver_swing", False):
        for _ in range(2):
            engine.summon_minion(seat, "VAN_CS2_101t")
        return

    if attacker_id.startswith("hero_"):
        return

    m = engine.find_minion(attacker_id)
    if not m or m.silenced or m.health <= 0:
        return

    # Vicious Fledgling: After this minion attacks a hero, Adapt.
    if m.card_id == "UNG_075" and target_id.startswith("hero_"):
        helpers.start_adapt(engine, seat, [m.uid], "UNG_075", remaining=1)

    # Frozen Crusher: After this minion attacks, Freeze it.
    elif m.card_id == "UNG_079":
        engine.freeze_character(m.uid)


def on_discard(engine: GameEngine, seat: str, ci: CardInstance) -> None:
    p = engine.state.players[seat]

    # Quest: Lakkari Sacrifice (Discard 6 cards)
    if p.trial_card == "UNG_829":
        helpers.advance_quest(engine, seat, "UNG_829", 1)

    # Clutchmother Zavas: Whenever you discard this, give it +2/+2 and return it to your hand.
    if ci.card_id == "UNG_836":
        new_ci = CardInstance(
            uid=engine._new_uid("c"),
            card_id="UNG_836",
            cost_mod=ci.cost_mod,
            attack_mod=ci.attack_mod + 2,
            health_mod=ci.health_mod + 2,
        )
        engine.give_card_instance_to_hand(seat, new_ci, origin="created")
        engine.add_log(f"Clutchmother Zavas returned to {p.name}'s hand with +2/+2!", seat=seat)
