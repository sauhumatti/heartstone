from __future__ import annotations

import functools
import random
import time
import uuid
from typing import Any, Callable, Optional

from engine import campaign as campaign_rules
from engine import expansions, meta_effects
from engine.catalog import CARDS, HEROES, CardDef, get_card
from engine.effects import (
    CHOOSE_ONE_OPTIONS,
    COMBO_ONLY_TARGET_CARDS,
    DEATHRATTLE_CARDS,
    DRAGON_ONLY_TARGET_CARDS,
    DREAM_CARDS,
    TARGET_RULES,
    cast_spell,
    trigger_battlecry,
    trigger_deathrattle,
    trigger_hero_power,
    trigger_weapon_deathrattle,
)
from engine.models import (
    CardInstance,
    Enchantment,
    GameState,
    Hero,
    Minion,
    PendingChoice,
    PlayerState,
    SecretInstance,
    Weapon,
)


class GameError(ValueError):
    pass


# How many action snapshots are kept for replay. A client that falls further
# behind than this gets the current state without animation.
MAX_CHECKPOINTS = 80

# Events whose card identity is hidden from the other seat.
_PRIVATE_CARD_EVENTS = ("draw", "card_added", "hand_remove")


def redact_event(ev: dict[str, Any], viewer: str) -> dict[str, Any]:
    """Return the event as `viewer` is allowed to see it (fog of war)."""
    if ev.get("seat") == viewer:
        return ev
    t = ev["t"]
    if t == "hand_buff":
        return {"t": t, "seq": ev["seq"], "seat": ev["seat"]}
    if t in _PRIVATE_CARD_EVENTS:
        return {k: v for k, v in ev.items() if k not in ("card", "uid")}
    if t == "play" and ev.get("secret"):
        out = {k: v for k, v in ev.items() if k not in ("card", "uid", "target")}
        out["card"] = None
        return out
    return ev


def _action(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Public game action: everything it emits becomes one replayable beat."""

    @functools.wraps(fn)
    def wrapper(self: "GameEngine", *args: Any, **kwargs: Any) -> Any:
        self._action_depth += 1
        try:
            return fn(self, *args, **kwargs)
        finally:
            self._action_depth -= 1
            if self._action_depth == 0:
                self.checkpoint()

    return wrapper


class GameEngine:
    def __init__(self, state: GameState):
        self.state = state
        # Older saves need defaults for the new mutable expansion state.
        if not hasattr(state, "feugen_died"):
            state.feugen_died = False
            state.stalagg_died = False
            state.dead_minions_all = []
        for player in state.players.values():
            if not hasattr(player, "fallen_minions"):
                player.fallen_minions = []
                player.fallen_deathrattles = []
                player.trial_minions = {}
            if not hasattr(player, "cthun_atk"):
                player.cthun_atk = 6
                player.cthun_hp = 6
                player.cthun_taunt = False
                player.cthun_dead = False
                player.extra_turns = 0
                player.crystal_core_active = False
                player.raza_active = False
                player.next_hero_power_cost_mod = 0
                player.enemy_hero_power_cost_mod_this_turn = 0
                player.enemy_hero_power_cost_mod_next_turn = 0
                player.hero_power_uses_total = 0
                player.spells_cast_by_id = []
                player.discards_total = 0
                player.discarded_cards = []
                player.embrace_shadow_this_turn = False
                player.lock_and_load_count = 0
                player.stampede_count = 0
                player.next_spell_costs_health = False
                player.next_dragon_cost_mod = 0
                player.next_murloc_costs_health = False
                player.extra_flags = {}
            if not hasattr(player.hero, "hero_power_uses_this_turn"):
                player.hero.hero_power_uses_this_turn = 0
                player.hero.is_ragnaros = False
                player.hero.immune_aura = False
        self.rng = random.Random(state.rng_seed) if state.rng_seed is not None else random.Random()
        self._action_depth = 0
        # True while the two sides of an attack trade blows: those are logged as the attack itself.
        self._combat = False

    # -----------------------------------------------------------------------
    # EVENT JOURNAL
    # -----------------------------------------------------------------------

    def emit(self, event_type: str, **data: Any) -> None:
        self.state.seq += 1
        self.state.pending_events.append({"seq": self.state.seq, "t": event_type, **data})

    def checkpoint(self) -> None:
        """Close the current beat: pending events plus a snapshot for each seat."""
        st = self.state
        if st.phase == "GAME_OVER" and not st.over_emitted:
            st.over_emitted = True
            self.emit("game_over", winner=st.winner)
        if not st.pending_events:
            return
        prev = st.cp_seq
        st.cp_seq = st.seq
        events = st.pending_events
        st.pending_events = []
        st.checkpoints.append({
            "seq": st.cp_seq,
            "prev": prev,
            "events": events,
            "views": {seat: self.serialize_for_seat(seat) for seat in ("p1", "p2")},
        })
        if len(st.checkpoints) > MAX_CHECKPOINTS:
            st.checkpoints = st.checkpoints[-MAX_CHECKPOINTS:]

    def beats_for_seat(self, seat: str, since: Optional[int]) -> Optional[list[dict[str, Any]]]:
        """Beats after `since` as `seat` may see them. None means the caller is
        too far behind (or unknown) and must jump to the current state."""
        st = self.state
        if since is None:
            return None
        if since >= st.cp_seq:
            return []
        start = next((i for i, c in enumerate(st.checkpoints) if c["prev"] == since), None)
        if start is None:
            return None
        return [
            {
                "seq": c["seq"],
                "prev": c["prev"],
                "events": [redact_event(e, seat) for e in c["events"]],
                "state": c["views"][seat],
            }
            for c in st.checkpoints[start:]
        ]

    @classmethod
    def create_game(
        cls,
        p1_name: str,
        p1_class: str,
        p1_deck: list[str],
        p1_deck_name: str,
        p2_name: str = "Antigravity",
        p2_class: Optional[str] = None,
        p2_deck: Optional[list[str]] = None,
        p2_deck_name: str = "",
        mode: str = "cli_vs_human",
        game_id: Optional[str] = None,
        rng_seed: Optional[int] = None,
        deck_era: str = "",
        p2_hero_name: Optional[str] = None,
        p2_intro_quote: str = "",
        p2_mid_quote: str = "",
    ) -> "GameEngine":
        rng = random.Random(rng_seed)
        gid = game_id or uuid.uuid4().hex[:8]
        first = rng.choice(["p1", "p2"])
        now = time.time()

        p1_hero_def = HEROES[p1_class]
        p1_hero = Hero(
            card_class=p1_class,
            name=p1_hero_def.name,
            hero_power_id=p1_hero_def.hero_power_id,
        )
        p1_state = PlayerState(
            seat="p1",
            name=p1_name,
            hero=p1_hero,
            deck_name=p1_deck_name,
        )

        if p2_class and p2_deck:
            p2_hero_def = HEROES[p2_class]
            p2_hero = Hero(
                card_class=p2_class,
                name=p2_hero_name or p2_hero_def.name,
                hero_power_id=p2_hero_def.hero_power_id,
            )
            p2_state = PlayerState(
                seat="p2",
                name=p2_name,
                hero=p2_hero,
                deck_name=p2_deck_name,
            )
            phase = "MULLIGAN"
        else:
            p2_hero = Hero(card_class="MAGE", name="Awaiting Opponent", hero_power_id="VAN_HERO_08bp")
            p2_state = PlayerState(seat="p2", name=p2_name, hero=p2_hero, deck_name="")
            phase = "WAITING_FOR_P2_DECK"

        state = GameState(
            game_id=gid,
            mode=mode,
            deck_era=deck_era,
            phase=phase,
            active_seat=first,
            first_seat=first,
            players={"p1": p1_state, "p2": p2_state},
            turn_started_at=now,
            created_at=now,
            rng_seed=rng_seed,
        )
        engine = cls(state)
        engine.rng = rng

        engine._init_deck("p1", p1_deck)
        if phase == "MULLIGAN":
            engine._init_deck("p2", p2_deck or [])
            engine._deal_opening_hands()
            if deck_era == "campaign":
                campaign_rules.setup_campaign(
                    engine,
                    p2_intro_quote=p2_intro_quote,
                    p2_mid_quote=p2_mid_quote,
                )
        engine.checkpoint()
        return engine

    @_action
    def set_p2_deck(self, p2_class: str, p2_deck: list[str], p2_deck_name: str = "") -> None:
        if self.state.phase != "WAITING_FOR_P2_DECK":
            raise GameError("Opponent deck is already set.")
        hdef = HEROES[p2_class]
        p2 = self.state.players["p2"]
        p2.hero = Hero(card_class=p2_class, name=hdef.name, hero_power_id=hdef.hero_power_id)
        p2.deck_name = p2_deck_name
        self._init_deck("p2", p2_deck)
        self.state.phase = "MULLIGAN"
        self._deal_opening_hands()

    def _new_uid(self, prefix: str = "e") -> str:
        uid = f"{prefix}_{self.state.next_uid}"
        self.state.next_uid += 1
        return uid

    def _init_deck(self, seat: str, card_ids: list[str]) -> None:
        p = self.state.players[seat]
        p.deck = [CardInstance(uid=self._new_uid("c"), card_id=cid, started_in_deck=True) for cid in card_ids]
        self.rng.shuffle(p.deck)

    def _deal_opening_hands(self) -> None:
        from engine.expansions.helpers import QUEST_DEFS
        first = self.state.first_seat
        second = self.other_seat(first)
        for seat, size in ((first, 3), (second, 4)):
            p = self.state.players[seat]
            trial = next(
                (i for i, c in enumerate(p.deck) if c.card_id in meta_effects.TRIALS or c.card_id in QUEST_DEFS),
                None,
            )
            if trial is not None:
                p.hand.append(p.deck.pop(trial))
            while len(p.hand) < size and p.deck:
                p.hand.append(p.deck.pop(0))
        self.add_log(
            f"Match started! {self.state.players[first].name} ({self.state.players[first].hero.card_class}) goes first."
        )
        self.emit("game_start", first=first)

    @staticmethod
    def other_seat(seat: str) -> str:
        return "p2" if seat == "p1" else "p1"

    def add_log(self, text: str, seat: Optional[str] = None) -> None:
        self.state.log.append({
            "id": len(self.state.log) + 1,
            "turn": self.state.turn_number,
            "seat": seat,
            "text": text,
        })
        if len(self.state.log) > 250:
            self.state.log = self.state.log[-250:]

    # -----------------------------------------------------------------------
    # MULLIGAN
    # -----------------------------------------------------------------------

    @_action
    def submit_mulligan(self, seat: str, replace_indices: list[int]) -> None:
        if self.state.phase != "MULLIGAN":
            raise GameError("Not in mulligan phase.")
        p = self.state.players[seat]
        if p.mulligan_done:
            raise GameError("Mulligan already submitted.")
        unique_idxs = sorted(set(replace_indices))
        for idx in unique_idxs:
            if idx < 0 or idx >= len(p.hand):
                raise GameError(f"Invalid mulligan card index: {idx}")

        replaced_cards = []
        for idx in reversed(unique_idxs):
            replaced_cards.append(p.hand.pop(idx))
        for _ in replaced_cards:
            if p.deck:
                p.hand.append(p.deck.pop(0))
        p.deck.extend(replaced_cards)
        self.rng.shuffle(p.deck)
        p.mulligan_done = True
        self.add_log(f"{p.name} replaced {len(replaced_cards)} card(s) in mulligan.", seat=seat)
        self.emit("mulligan", seat=seat, count=len(replaced_cards))

        if self.state.players["p1"].mulligan_done and self.state.players["p2"].mulligan_done:
            second = self.other_seat(self.state.first_seat)
            self.add_card_to_hand(second, "GAME_005")
            self.add_log(f"{self.state.players[second].name} received The Coin.", seat=second)
            self.state.phase = "PLAY"
            self.state.active_seat = self.state.first_seat
            self._start_turn(self.state.active_seat)

    # -----------------------------------------------------------------------
    # TURN LIFECYCLE
    # -----------------------------------------------------------------------

    def _start_turn(self, seat: str) -> None:
        if self.state.phase == "GAME_OVER":
            return
        self.state.active_seat = seat
        self.state.turn_number += 1
        self.state.turn_started_at = time.time()

        p = self.state.players[seat]
        p.cards_played_this_turn = 0
        p.minions_played_this_turn = 0
        p.elemental_last_turn = p.elemental_this_turn
        p.elemental_this_turn = False
        p.next_secret_free = False
        p.next_spell_cost_mod = 0
        p.commanding_shout_active = False
        p.headcrack_return_eot = False
        p.enemy_spells_free_this_turn = p.enemy_spells_free_next_turn
        p.enemy_spells_free_next_turn = False
        p.enemy_spell_cost_mod_this_turn = p.enemy_spell_cost_mod_next_turn
        p.enemy_spell_cost_mod_next_turn = 0
        p.enemy_hero_power_cost_mod_this_turn = p.enemy_hero_power_cost_mod_next_turn
        p.enemy_hero_power_cost_mod_next_turn = 0
        p.embrace_shadow_this_turn = False
        p.lock_and_load_count = 0
        p.stampede_count = 0
        p.next_spell_costs_health = False
        p.next_murloc_costs_health = False
        for pl in self.state.players.values():
            pl.dead_minions_this_turn.clear()

        p.hero.attacks_this_turn = 0
        p.hero.temp_attack = 0
        p.hero.immune_this_turn = False
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0

        if p.max_mana < 10:
            p.max_mana += 1
        p.overloaded = min(10, p.pending_overload)
        p.pending_overload = 0
        p.mana = max(0, p.max_mana - p.overloaded)
        self.emit(
            "turn_start",
            seat=seat,
            turn=self.state.turn_number,
            mana=p.mana,
            max_mana=p.max_mana,
            overloaded=p.overloaded,
        )

        for m in p.board:
            m.summoned_this_turn = False
            m.attacks_this_turn = 0
            m.immune_this_turn = False
            m.cant_attack_hero_this_turn = False
            if m.stealth_until_sot_of == seat:
                m.stealth_until_sot_of = None
                m.base_keywords.discard("STEALTH")
                for e in m.enchantments:
                    e.add_keywords.discard("STEALTH")

        # Start-of-turn minion triggers & enchantments (Nightmare / Corruption) & expansion SOT
        self.recompute_auras()
        expansions.trigger_secrets_on_sot(self, seat)
        expansions.on_start_turn(self, seat)
        campaign_rules.on_turn_start(self, seat)
        for m in list(p.board):
            if m not in p.board:
                continue
            self._process_sot_minion(seat, m)
            expansions.on_sot_minion(self, seat, m)
        # Also check opponent minions for Corruption/Nightmare cast by `seat`
        opp = self.state.players[self.other_seat(seat)]
        for m in list(opp.board):
            for e in list(m.enchantments):
                if e.destroy_at_owner_sot == seat:
                    self.destroy_minion(m.uid)
                    break
        for m in list(p.board):
            for e in list(m.enchantments):
                if e.destroy_at_owner_sot == seat:
                    self.destroy_minion(m.uid)
                    break

        self.resolve_deaths()
        if self.state.phase == "GAME_OVER":
            return

        self.draw_card(seat)
        self.recompute_auras()
        self.add_log(f"--- Turn {self.state.turn_number}: {p.name} ({p.mana}/{p.max_mana} Mana) ---", seat=seat)

    def _process_sot_minion(self, seat: str, m: Minion) -> None:
        if m.silenced:
            return
        cid = m.card_id
        if cid == "VAN_EX1_341":  # Lightwell
            p = self.state.players[seat]
            cands = []
            if p.hero.hp < p.hero.max_hp:
                cands.append(f"hero_{seat}")
            cands.extend(fm.uid for fm in p.board if fm.damaged)
            if cands:
                self.apply_heal(seat, self.rng.choice(cands), 3)
        elif cid == "VAN_NEW1_021":  # Doomsayer
            self.add_log("Doomsayer destroys ALL minions!", seat=seat)
            for s in ("p1", "p2"):
                for bm in list(self.state.players[s].board):
                    self.destroy_minion(bm.uid)
        elif cid == "VAN_EX1_557":  # Nat Pagle
            if self.rng.random() < 0.5:
                self.draw_card(seat)
        elif cid == "VAN_EX1_006":  # Alarm-o-Bot
            p = self.state.players[seat]
            minions_in_hand = [i for i, ci in enumerate(p.hand) if get_card(ci.card_id).type == "MINION"]
            if minions_in_hand and m in p.board:
                pick_idx = self.rng.choice(minions_in_hand)
                ci = p.hand.pop(pick_idx)
                b_idx = p.board.index(m)
                p.board.pop(b_idx)
                p.hand.append(CardInstance(uid=self._new_uid("c"), card_id=m.card_id))
                self.summon_minion(seat, ci.card_id, pos=b_idx)
        elif cid == "VAN_EX1_102":  # Demolisher
            cands = self.living_enemy_characters(seat)
            if cands:
                self.deal_damage(self.rng.choice(cands), 2, source_seat=seat, source_name="Demolisher", source_minion=m)
        elif cid == "Mekka1":  # Homing Chicken
            self.destroy_minion(m.uid)
            for _ in range(3):
                self.draw_card(seat)
        elif cid == "Mekka4":  # Poultryizer
            all_m = [bm for s in ("p1", "p2") for bm in self.state.players[s].board]
            if all_m:
                self.transform_minion(self.rng.choice(all_m).uid, "Mekka4t")
        elif cid == "FP1_005":  # Shade of Naxxramas
            self.add_enchantment(m.uid, cid, "Shade of Naxxramas", atk=1, hp=1)

    @_action
    def end_turn(self, seat: str) -> None:
        if self.state.phase != "PLAY":
            raise GameError("Game is not in play phase.")
        if self.state.active_seat != seat:
            raise GameError("Not your turn.")
        if self.state.pending_choice is not None:
            raise GameError("Resolve pending choice before ending turn.")

        self.emit("turn_end", seat=seat)
        p = self.state.players[seat]
        opp_seat = self.other_seat(seat)
        opp = self.state.players[opp_seat]

        # End-of-turn minion triggers
        for m in list(p.board):
            if m in p.board and not m.silenced:
                self._process_eot_minion(seat, m)
                expansions.on_eot_minion(self, seat, m)
                meta_effects.end_minion_turn(self, seat, m)

        # Gruul & Kel'Thuzad trigger at end of EACH turn on BOTH boards
        expansions.on_eot_both(self, seat)
        for s in ("p1", "p2"):
            pl = self.state.players[s]
            for m in list(pl.board):
                if not m.silenced and m.card_id == "VAN_NEW1_038":  # Gruul
                    self.add_enchantment(m.uid, m.card_id, "Gruul", atk=1, hp=1)
                elif not m.silenced and m.card_id == "FP1_013":  # Kel'Thuzad
                    for dead_cid in list(pl.dead_minions_this_turn):
                        if len(pl.board) >= 7:
                            break
                        self.summon_minion(s, dead_cid)

        # Destroy-at-EOT enchantments (Power Overwhelming, Force of Nature)
        for s in ("p1", "p2"):
            for m in list(self.state.players[s].board):
                if any(e.destroy_at_eot for e in m.enchantments):
                    self.destroy_minion(m.uid)

        # Revert Shadow Madness & expire temp-until-EOT buffs
        for s in ("p1", "p2"):
            for m in list(self.state.players[s].board):
                revert_to = None
                for e in m.enchantments:
                    if e.temp_owner_revert:
                        revert_to = e.temp_owner_revert
                m.enchantments = [e for e in m.enchantments if not e.temp_until_eot]
                if revert_to and revert_to != m.owner:
                    if len(self.state.players[revert_to].board) < 7:
                        self.steal_minion(m.uid, revert_to)
                    else:
                        self.destroy_minion(m.uid)

        # Clear Freeze for active player's characters that missed an attack this turn
        hero_max_attacks = 2 if (p.weapon and p.weapon.windfury) else 1
        if p.hero.frozen and p.hero.freeze_until_eot_of == seat:
            if p.hero.attacks_this_turn < hero_max_attacks:
                p.hero.frozen = False
                p.hero.freeze_until_eot_of = None
        for m in p.board:
            if m.frozen and m.freeze_until_eot_of == seat:
                summoning_sick = m.summoned_this_turn and not m.has_keyword("CHARGE")
                if not summoning_sick and m.attacks_this_turn < m.max_attacks():
                    m.frozen = False
                    m.freeze_until_eot_of = None

        # Headcrack combo return
        if p.headcrack_return_eot:
            p.headcrack_return_eot = False
            self.add_card_to_hand(seat, "VAN_EX1_137")

        # Reset turn-scoped hero attack & immune. "Immune this turn" ends with the turn
        # for minions too (on both sides), not when their owner's next turn starts.
        p.hero.temp_attack = 0
        p.hero.immune_this_turn = False
        opp.hero.immune_this_turn = False
        for side in (p, opp):
            for m in side.board:
                m.immune_this_turn = False
        p.commanding_shout_active = False

        self.resolve_deaths()
        self.recompute_auras()
        if self.state.phase == "GAME_OVER":
            return
        if p.extra_turns > 0:
            p.extra_turns -= 1
            self._start_turn(seat)
        else:
            self._start_turn(opp_seat)

    def _process_eot_minion(self, seat: str, m: Minion) -> None:
        p = self.state.players[seat]
        cid = m.card_id
        if cid == "VAN_EX1_274":  # Ethereal Arcanist
            if p.secrets:
                self.add_enchantment(m.uid, cid, "Ethereal Arcanist", atk=2, hp=2)
        elif cid == "VAN_EX1_575":  # Mana Tide Totem
            self.draw_card(seat)
        elif cid == "VAN_NEW1_009":  # Healing Totem
            for fm in list(p.board):
                self.apply_heal(seat, fm.uid, 1)
        elif cid in ("VAN_CS2_059", "VAN_EX1_004"):  # Blood Imp / Young Priestess
            others = [fm for fm in p.board if fm.uid != m.uid]
            if others:
                self.add_enchantment(self.rng.choice(others).uid, cid, m.name, hp=1)
        elif cid == "VAN_NEW1_037":  # Master Swordsmith
            others = [fm for fm in p.board if fm.uid != m.uid]
            if others:
                self.add_enchantment(self.rng.choice(others).uid, cid, m.name, atk=1)
        elif cid == "VAN_EX1_597":  # Imp Master
            self.deal_damage(m.uid, 1, source_seat=seat, source_name="Imp Master", source_minion=m)
            self.summon_minion(seat, "VAN_EX1_598")
        elif cid == "VAN_NEW1_040":  # Hogger
            self.summon_minion(seat, "NEW1_040t")
        elif cid == "VAN_EX1_249":  # Baron Geddon
            for tid in ["hero_p1", "hero_p2"] + [
                bm.uid for s in ("p1", "p2") for bm in self.state.players[s].board if bm.uid != m.uid
            ]:
                self.deal_damage(tid, 2, source_seat=seat, source_name="Baron Geddon", source_minion=m)
        elif cid == "VAN_EX1_298":  # Ragnaros the Firelord
            cands = self.living_enemy_characters(seat)
            if cands:
                self.deal_damage(self.rng.choice(cands), 8, source_seat=seat, source_name="Ragnaros the Firelord", source_minion=m)
        elif cid == "VAN_EX1_572":  # Ysera
            self.add_card_to_hand(seat, self.rng.choice(DREAM_CARDS))
        elif cid == "Mekka2":  # Repair Bot
            damaged = []
            for s in ("p1", "p2"):
                pl = self.state.players[s]
                if pl.hero.hp < pl.hero.max_hp:
                    damaged.append(f"hero_{s}")
                damaged.extend(bm.uid for bm in pl.board if bm.damaged)
            if damaged:
                self.apply_heal(seat, self.rng.choice(damaged), 6)
        elif cid == "Mekka3":  # Emboldener 3000
            all_m = [bm for s in ("p1", "p2") for bm in self.state.players[s].board]
            if all_m:
                self.add_enchantment(self.rng.choice(all_m).uid, cid, "Emboldener 3000", atk=1, hp=1)
        elif cid == "BRM_028":  # Emperor Thaurissan
            for ci in p.hand:
                ci.cost_mod -= 1
            if p.hand:
                self.add_log(f"Emperor Thaurissan reduces the Cost of {p.name}'s hand by (1).", seat=seat)

    # -----------------------------------------------------------------------
    # GOLDEN ERA HELPERS
    # -----------------------------------------------------------------------

    def has_dragon_in_hand(self, seat: str, exclude_uid: Optional[str] = None) -> bool:
        return any(
            ci.uid != exclude_uid and get_card(ci.card_id).race == "DRAGON"
            for ci in self.state.players[seat].hand
        )

    def has_mech_on_board(self, seat: str, exclude_uid: Optional[str] = None) -> bool:
        return any(
            m.uid != exclude_uid and m.race == "MECHANICAL"
            for m in self.state.players[seat].board
        )

    def has_no_duplicates_in_deck(self, seat: str) -> bool:
        deck = self.state.players[seat].deck
        return len({ci.card_id for ci in deck}) == len(deck)

    def has_fandral(self, seat: str) -> bool:
        return any(
            not m.silenced and m.card_id == "OG_044"
            for m in self.state.players[seat].board
        )

    def shuffle_into_deck(self, seat: str, card_id: str, count: int = 1) -> None:
        p = self.state.players[seat]
        for _ in range(count):
            ci = CardInstance(uid=self._new_uid("c"), card_id=card_id)
            idx = self.rng.randint(0, len(p.deck))
            p.deck.insert(idx, ci)
        cname = get_card(card_id).name
        self.add_log(f"Shuffled {count}x {cname} into {p.name}'s deck.", seat=seat)

    def summon_jade_golem(self, seat: str, pos: Optional[int] = None) -> Optional[Minion]:
        p = self.state.players[seat]
        p.jade_counter = min(30, p.jade_counter + 1)
        return self.summon_minion(seat, f"CFM_712_t{p.jade_counter:02d}", pos=pos)

    def start_discover(
        self,
        seat: str,
        source_card_id: str,
        pool_ids: list[str],
        choice_type: str = "DISCOVER",
        count: int = 3,
    ) -> None:
        if not pool_ids:
            return
        k = min(count, len(pool_ids))
        picked = self.rng.sample(pool_ids, k)
        opts = [CardInstance(uid=self._new_uid("c"), card_id=cid) for cid in picked]
        self.state.pending_choice = PendingChoice(
            seat=seat,
            choice_type=choice_type,
            source_card_id=source_card_id,
            options=opts,
        )

    # -----------------------------------------------------------------------
    # AURAS, COSTS & TARGET VALIDATION
    # -----------------------------------------------------------------------

    def get_card_cost(self, seat: str, ci: CardInstance) -> int:
        card = get_card(ci.card_id)
        p = self.state.players[seat]
        opp = self.state.players[self.other_seat(seat)]
        cost = card.cost + ci.cost_mod

        # Card-specific self reductions
        if card.id == "VAN_EX1_586":  # Sea Giant
            total_minions = len(p.board) + len(opp.board)
            cost -= total_minions
        elif card.id == "VAN_EX1_105":  # Mountain Giant
            in_hand = any(h.uid == ci.uid for h in p.hand)
            others = len(p.hand) - 1 if in_hand else len(p.hand)
            cost -= max(0, others)
        elif card.id == "VAN_EX1_620":  # Molten Giant
            dmg_taken = max(0, p.hero.max_hp - p.hero.hp)
            cost -= dmg_taken
        elif card.id == "VAN_NEW1_022":  # Dread Corsair
            if p.weapon:
                cost -= p.weapon.total_attack
        elif card.id == "BRM_001":  # Solemn Vigil
            died = sum(len(pl.dead_minions_this_turn) for pl in self.state.players.values())
            cost -= died
        elif card.id == "OG_028":  # Thing from Below
            cost -= p.totems_summoned
        elif card.id == "LF_M31":
            cost -= p.secrets_played

        # Board & turn auras
        if card.type == "SPELL":
            if p.enemy_spells_free_this_turn:
                return 0
            if card.has_mechanic("SECRET") and p.next_secret_free:
                return 0
            if card.has_mechanic("SECRET"):
                cost -= sum(1 for m in p.board if not m.silenced and m.card_id == "LF_001")
            apprentices = sum(1 for m in p.board if not m.silenced and m.card_id == "VAN_EX1_608")
            cost -= apprentices
            cost -= p.next_spell_cost_mod
            cost += p.enemy_spell_cost_mod_this_turn
        elif card.type == "MINION":
            portals = sum(1 for m in p.board if not m.silenced and m.card_id == "VAN_EX1_315")
            if portals > 0 and cost > 0:
                cost = max(1, cost - 2 * portals)
            if card.race == "MECHANICAL":
                warpers = sum(1 for m in p.board if not m.silenced and m.card_id == "GVG_006")
                cost -= warpers
            if p.minions_played_this_turn == 0:
                pints = sum(1 for m in p.board if not m.silenced and m.card_id == "VAN_EX1_076")
                cost -= pints
            wraiths = sum(
                1 for s in ("p1", "p2") for m in self.state.players[s].board
                if not m.silenced and m.card_id == "VAN_EX1_616"
            )
            cost += wraiths
            ventures = sum(1 for m in p.board if not m.silenced and m.card_id == "VAN_CS2_227")
            cost += 3 * ventures

        cost = expansions.get_card_cost(self, seat, ci, cost)
        return max(0, cost)

    def get_hero_power_cost(self, seat: str) -> int:
        p = self.state.players[seat]
        if p.raza_active:
            return 0
        cost = 2 + p.next_hero_power_cost_mod + p.enemy_hero_power_cost_mod_this_turn
        cost = expansions.get_hero_power_cost(self, seat, cost)
        return max(0, cost)

    def recompute_auras(self) -> None:
        all_minions = [m for s in ("p1", "p2") for m in self.state.players[s].board]
        old_max = {m.uid: m.max_health for m in all_minions}
        old_hp = {m.uid: (old_max[m.uid] - m.damage) for m in all_minions}

        for m in all_minions:
            m.aura_atk_bonus = 0
            m.aura_hp_bonus = 0
            atk = m.base_attack
            hp = m.base_health
            kws = set() if m.silenced else set(m.base_keywords)
            sd = 0 if m.silenced else m.base_spell_damage

            # Enchantments applied after Silence still take effect (Silence clears prior enchantments)
            for e in m.enchantments:
                if e.set_atk is not None:
                    atk = e.set_atk
                atk += e.atk
                if e.set_hp is not None:
                    hp = e.set_hp
                hp += e.hp
                kws |= e.add_keywords
                kws -= e.remove_keywords
                sd += e.spell_damage

            if not m.silenced:
                # Enrage
                if m.damage > 0:
                    if m.card_id == "VAN_EX1_009":  # Angry Chicken
                        atk += 5
                    elif m.card_id == "VAN_EX1_393":  # Amani Berserker
                        atk += 3
                    elif m.card_id == "VAN_EX1_412":  # Raging Worgen
                        atk += 1
                        kws.add("WINDFURY")
                    elif m.card_id == "VAN_EX1_390":  # Tauren Warrior
                        atk += 3
                    elif m.card_id == "VAN_EX1_414":  # Grommash Hellscream
                        atk += 6

            m.attack = max(0, atk)
            m.max_health = max(1, hp)
            m.keywords = kws
            m.spell_damage = sd

        # Apply board auras
        for s in ("p1", "p2"):
            board = self.state.players[s].board
            opp_board = self.state.players[self.other_seat(s)].board
            for idx, src in enumerate(board):
                if src.silenced:
                    continue
                cid = src.card_id
                if cid == "VAN_CS2_222":  # Stormwind Champion
                    for t in board:
                        if t.uid != src.uid:
                            t.aura_atk_bonus += 1
                            t.aura_hp_bonus += 1
                elif cid in ("VAN_CS2_122", "VAN_NEW1_033"):  # Raid Leader / Leokk
                    for t in board:
                        if t.uid != src.uid:
                            t.aura_atk_bonus += 1
                elif cid in ("VAN_DS1_175", "LF_006"):  # Timber Wolf / Ashgate Regent
                    race = "BEAST" if cid == "VAN_DS1_175" else "DEMON"
                    for t in board:
                        if t.uid != src.uid and t.race == race:
                            t.aura_atk_bonus += 1
                elif cid == "VAN_EX1_508":  # Grimscale Oracle
                    for t in board + opp_board:
                        if t.uid != src.uid and t.race == "MURLOC":
                            t.aura_atk_bonus += 1
                elif cid == "VAN_EX1_507":  # Murloc Warleader
                    for t in board + opp_board:
                        if t.uid != src.uid and t.race == "MURLOC":
                            t.aura_atk_bonus += 2
                            t.aura_hp_bonus += 1
                elif cid == "VAN_NEW1_027":  # Southsea Captain
                    for t in board:
                        if t.uid != src.uid and t.race == "PIRATE":
                            t.aura_atk_bonus += 1
                            t.aura_hp_bonus += 1
                elif cid == "VAN_EX1_162":  # Dire Wolf Alpha
                    for ni in (idx - 1, idx + 1):
                        if 0 <= ni < len(board):
                            board[ni].aura_atk_bonus += 1
                elif cid == "VAN_EX1_565":  # Flametongue Totem
                    for ni in (idx - 1, idx + 1):
                        if 0 <= ni < len(board):
                            board[ni].aura_atk_bonus += 2
                elif cid == "VAN_DS1_178":  # Tundra Rhino
                    for t in board:
                        if t.race == "BEAST":
                            t.keywords.add("CHARGE")

        # Self dynamic auras + clamp damage if aura health decreased
        murloc_count = sum(1 for m in all_minions if m.race == "MURLOC")
        for s in ("p1", "p2"):
            pl = self.state.players[s]
            for m in pl.board:
                if not m.silenced:
                    if m.card_id == "VAN_EX1_062":  # Old Murk-Eye
                        m.aura_atk_bonus += max(0, murloc_count - 1)
                    elif m.card_id == "VAN_CS2_146" and pl.weapon is not None:  # Southsea Deckhand
                        m.keywords.add("CHARGE")
                    elif m.card_id == "GVG_013" and any(bm.race == "MECHANICAL" for bm in pl.board):  # Cogmaster
                        m.aura_atk_bonus += 2

                m.attack = max(0, m.attack + m.aura_atk_bonus)
                new_max = max(1, m.max_health + m.aura_hp_bonus)
                if pl.crystal_core_active and not m.has_keyword("DORMANT"):
                    m.attack = max(0, 5 + m.aura_atk_bonus)
                    new_max = max(1, 5 + m.aura_hp_bonus)
                if old_max[m.uid] > 0 and new_max < old_max[m.uid]:
                    clamped_hp = min(old_hp[m.uid], new_max)
                    m.damage = max(0, new_max - clamped_hp)
                m.max_health = new_max

                if not m.silenced and m.card_id == "VAN_EX1_335":  # Lightspawn
                    m.attack = max(0, m.health)

        # Reset dynamic hero immune aura before recomputing
        for s in ("p1", "p2"):
            self.state.players[s].hero.immune_aura = False

        # Expansion dynamic board/weapon/hero auras
        expansions.recompute_auras(self)

        # Weapon aura (Spiteful Smith, Spirit Claws) & Hero attack
        for s in ("p1", "p2"):
            pl = self.state.players[s]
            if pl.weapon:
                smiths = sum(1 for m in pl.board if not m.silenced and m.card_id == "VAN_CS2_221" and m.damage > 0)
                wep_bonus = 2 * smiths
                if pl.weapon.card_id == "KAR_063":  # Spirit Claws
                    if any(m.spell_damage > 0 for m in pl.board):
                        wep_bonus += 2
                pl.weapon.aura_attack_bonus = wep_bonus
            wep_atk = pl.weapon.total_attack if (pl.weapon and s == self.state.active_seat) else 0
            pl.hero.attack = max(0, pl.hero.temp_attack + wep_atk)

    def calc_spell_damage(self, seat: str, base: int) -> int:
        p = self.state.players[seat]
        bonus = sum(m.spell_damage for m in p.board)
        mult = self.velen_multiplier(seat)
        return (base + bonus) * mult

    def calc_spell_healing(self, seat: str, base: int) -> int:
        return base * self.velen_multiplier(seat)

    def velen_multiplier(self, seat: str) -> int:
        p = self.state.players[seat]
        velens = sum(1 for m in p.board if not m.silenced and m.card_id == "VAN_EX1_350")
        return 2 ** velens

    def has_auchenai(self, seat: str) -> bool:
        p = self.state.players[seat]
        if p.embrace_shadow_this_turn:
            return True
        return any(not m.silenced and m.card_id == "VAN_EX1_591" for m in p.board)

    # -----------------------------------------------------------------------
    # VALID TARGETING & PLAYABILITY
    # -----------------------------------------------------------------------

    def get_target_rule(
        self,
        card_id: str,
        choose: Optional[int],
        was_combo: bool,
        seat: Optional[str] = None,
        exclude_hand_uid: Optional[str] = None,
    ) -> str:
        if card_id in CHOOSE_ONE_OPTIONS:
            if choose is None:
                return "NONE"
            opts = CHOOSE_ONE_OPTIONS[card_id]
            return opts[choose].target_rule
        if card_id in COMBO_ONLY_TARGET_CARDS and not was_combo:
            return "NONE"
        if card_id in DRAGON_ONLY_TARGET_CARDS:
            if seat is None or not self.has_dragon_in_hand(seat, exclude_uid=exclude_hand_uid):
                return "NONE"
        cond_fn = expansions.CONDITIONAL_TARGET_RULES.get(card_id)
        if cond_fn is not None:
            if seat is None:
                return "NONE"
            return cond_fn(self, seat, exclude_hand_uid)
        return TARGET_RULES.get(card_id, "NONE")

    def get_valid_targets(
        self,
        seat: str,
        rule: str,
        is_spell_or_power: bool = False,
        exclude_uid: Optional[str] = None,
    ) -> list[str]:
        if rule == "NONE":
            return []
        opp_seat = self.other_seat(seat)
        p = self.state.players[seat]
        opp = self.state.players[opp_seat]
        targets: list[str] = []

        def minion_targetable(m: Minion) -> bool:
            if m.uid == exclude_uid:
                return False
            if m.has_keyword("DORMANT"):
                return False
            if m.owner != seat and m.has_keyword("STEALTH"):
                return False
            if m.owner != seat and m.immune_this_turn:
                return False
            if is_spell_or_power and m.has_keyword("ELUSIVE"):
                return False
            return True

        def add_hero(s: str) -> None:
            pl = self.state.players[s]
            if s != seat and (pl.hero.immune_this_turn or pl.hero.immune_aura):
                return
            targets.append(f"hero_{s}")

        if rule == "ANY":
            add_hero(seat)
            add_hero(opp_seat)
            for m in p.board + opp.board:
                if minion_targetable(m):
                    targets.append(m.uid)
        elif rule == "HERO":
            add_hero(seat)
            add_hero(opp_seat)
        elif rule == "ENEMY_HERO":
            add_hero(opp_seat)
        elif rule == "FRIENDLY_CHARACTER":
            add_hero(seat)
            for m in p.board:
                if minion_targetable(m):
                    targets.append(m.uid)
        elif rule == "ENEMY_CHARACTER":
            add_hero(opp_seat)
            for m in opp.board:
                if minion_targetable(m):
                    targets.append(m.uid)
        elif rule == "MINION":
            for m in p.board + opp.board:
                if minion_targetable(m):
                    targets.append(m.uid)
        elif rule == "FRIENDLY_MINION":
            for m in p.board:
                if minion_targetable(m):
                    targets.append(m.uid)
        elif rule == "FRIENDLY_PRINTED_DEATHRATTLE":
            for m in p.board:
                if minion_targetable(m) and not m.silenced and m.card_id in DEATHRATTLE_CARDS:
                    targets.append(m.uid)
        elif rule == "ENEMY_MINION":
            for m in opp.board:
                if minion_targetable(m):
                    targets.append(m.uid)
        elif rule == "FRIENDLY_BEAST":
            for m in p.board:
                if minion_targetable(m) and m.race == "BEAST":
                    targets.append(m.uid)
        elif rule == "UNDAMAGED_MINION":
            for m in p.board + opp.board:
                if minion_targetable(m) and not m.damaged:
                    targets.append(m.uid)
        elif rule == "DAMAGED_MINION":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.damaged:
                    targets.append(m.uid)
        elif rule == "DAMAGED_ENEMY_MINION":
            for m in opp.board:
                if minion_targetable(m) and m.damaged:
                    targets.append(m.uid)
        elif rule == "MINION_ATK_LE_3":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.attack <= 3:
                    targets.append(m.uid)
        elif rule == "MINION_ATK_GE_5":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.attack >= 5:
                    targets.append(m.uid)
        elif rule == "MINION_ATK_GE_7":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.attack >= 7:
                    targets.append(m.uid)
        elif rule == "ENEMY_MINION_ATK_LE_2":
            for m in opp.board:
                if minion_targetable(m) and m.attack <= 2:
                    targets.append(m.uid)
        elif rule == "ENEMY_MINION_ATK_LE_3":
            for m in opp.board:
                if minion_targetable(m) and m.attack <= 3:
                    targets.append(m.uid)
        elif rule == "ENEMY_TAUNT":
            for m in opp.board:
                if minion_targetable(m) and m.has_keyword("TAUNT"):
                    targets.append(m.uid)
        elif rule == "MURLOC":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race == "MURLOC":
                    targets.append(m.uid)
        elif rule == "DEMON":
            for s in ("p1", "p2"):
                if self.state.players[s].hero.is_jaraxxus:
                    add_hero(s)
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race == "DEMON":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_DEMON":
            for m in p.board:
                if minion_targetable(m) and m.race == "DEMON":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_MECH":
            for m in p.board:
                if minion_targetable(m) and m.race == "MECHANICAL":
                    targets.append(m.uid)
        elif rule == "MECH":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race == "MECHANICAL":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_MURLOC":
            for m in p.board:
                if minion_targetable(m) and m.race == "MURLOC":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_PIRATE":
            for m in p.board:
                if minion_targetable(m) and m.race == "PIRATE":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_DRAGON":
            for m in p.board:
                if minion_targetable(m) and m.race == "DRAGON":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_TOTEM":
            for m in p.board:
                if minion_targetable(m) and m.race == "TOTEM":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_ELEMENTAL":
            for m in p.board:
                if minion_targetable(m) and m.race == "ELEMENTAL":
                    targets.append(m.uid)
        elif rule == "BEAST":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race == "BEAST":
                    targets.append(m.uid)
        elif rule == "PIRATE":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race == "PIRATE":
                    targets.append(m.uid)
        elif rule == "DRAGON":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race == "DRAGON":
                    targets.append(m.uid)
        elif rule == "LEGENDARY_MINION":
            for m in p.board + opp.board:
                if minion_targetable(m) and get_card(m.card_id).rarity == "LEGENDARY":
                    targets.append(m.uid)
        elif rule == "FRIENDLY_DEATHRATTLE":
            for m in p.board:
                if minion_targetable(m) and not m.silenced and (
                    m.card_id in DEATHRATTLE_CARDS or any(e.extra_deathrattle for e in m.enchantments)
                ):
                    targets.append(m.uid)
        elif rule == "NON_DEMON_MINION":
            for m in p.board + opp.board:
                if minion_targetable(m) and m.race != "DEMON":
                    targets.append(m.uid)
        return targets

    def can_play_card(self, seat: str, hand_index: int) -> tuple[bool, str]:
        if self.state.phase != "PLAY" or self.state.active_seat != seat:
            return False, "Not your turn."
        if self.state.pending_choice is not None:
            return False, "Resolve pending choice first."
        p = self.state.players[seat]
        opp = self.state.players[self.other_seat(seat)]
        if hand_index < 0 or hand_index >= len(p.hand):
            return False, "Invalid card index."
        ci = p.hand[hand_index]
        card = get_card(ci.card_id)
        cost = self.get_card_cost(seat, ci)
        pays_health = (
            (card.type == "SPELL" and p.next_spell_costs_health)
            or (card.type == "MINION" and card.race == "MURLOC" and p.next_murloc_costs_health)
            or (card.type == "SPELL" and any(not bm.silenced and bm.card_id == "OG_121" for bm in p.board))
        )
        if pays_health:
            if p.hero.hp <= cost and not p.hero.immune_this_turn and not p.hero.immune_aura:
                return False, "Not enough Health."
        elif p.mana < cost:
            return False, "Not enough mana."

        exp_check = expansions.can_play_card(self, seat, ci)
        if exp_check is not None:
            return exp_check

        if card.type == "MINION":
            if len(p.board) >= 7:
                return False, "Board is full (max 7 minions)."
            return True, "ok"

        if card.type == "WEAPON":
            return True, "ok"

        # SPELL checks
        if card.has_mechanic("SECRET"):
            if len(p.secrets) >= 5:
                return False, "Max 5 Secrets active."
            if any(s.card_id == card.id for s in p.secrets):
                return False, f"Already have {card.name} active."
            return True, "ok"

        if card.id in ("VAN_CS2_074", "VAN_CS2_233", "LF_M01") and p.weapon is None:
            return False, "Requires a weapon equipped."
        if card.id == "LF_M05" and (not p.fallen_minions or len(p.board) >= 7):
            return False, "Requires a fallen minion and a free board slot."
        if card.id in meta_effects.TRIALS and p.trial_card is not None:
            return False, "You already have an active Trial."
        from engine.expansions.helpers import QUEST_DEFS
        if card.id in QUEST_DEFS and p.trial_card is not None:
            return False, "You already have an active Quest."
        if card.id in ("VAN_CS2_114", "VAN_DS1_183", "VAN_EX1_251") and len(opp.board) < 2:
            return False, "Requires at least 2 enemy minions."
        if card.id == "VAN_EX1_617" and len(opp.board) < 1:
            return False, "Requires an enemy minion."
        if card.id == "VAN_EX1_407" and (len(p.board) + len(opp.board)) < 2:
            return False, "Requires at least 2 minions on the battlefield."
        if card.id in ("VAN_EX1_334", "VAN_CS1_113") and len(p.board) >= 7:
            return False, "Your board is full."
        if card.id in ("VAN_CS2_027", "VAN_EX1_248", "VAN_EX1_571", "VAN_NEW1_031", "VAN_EX1_345") and len(p.board) >= 7:
            return False, "Your board is full."
        if card.id == "VAN_DS1_184" and len(p.deck) == 0:
            return False, "No cards left in deck."

        if card.id in CHOOSE_ONE_OPTIONS:
            # At least one option must be valid
            opts = CHOOSE_ONE_OPTIONS[card.id]
            for opt in opts:
                if opt.target_rule == "NONE":
                    return True, "ok"
                if len(self.get_valid_targets(seat, opt.target_rule, is_spell_or_power=True)) > 0:
                    return True, "ok"
            return False, "No valid targets for either Choose One option."

        rule = self.get_target_rule(card.id, None, p.cards_played_this_turn > 0, seat=seat, exclude_hand_uid=ci.uid)
        if rule != "NONE":
            if len(self.get_valid_targets(seat, rule, is_spell_or_power=True)) == 0:
                return False, "No valid targets."
        return True, "ok"

    def can_use_hero_power(self, seat: str) -> tuple[bool, str]:
        if self.state.phase != "PLAY" or self.state.active_seat != seat:
            return False, "Not your turn."
        if self.state.pending_choice is not None:
            return False, "Resolve pending choice first."
        p = self.state.players[seat]
        max_uses = expansions.get_hero_power_max_uses(self, seat)
        if p.hero.hero_power_uses_this_turn >= max_uses:
            return False, "Hero Power already used this turn."
        hp_cost = self.get_hero_power_cost(seat)
        if p.mana < hp_cost:
            return False, "Not enough mana."
        hp_id = p.hero.hero_power_id
        if hp_id in ("VAN_HERO_04bp", "VAN_EX1_tk33", "AT_132_PALADIN", "AT_132_SHAMAN") and len(p.board) >= 7:
            return False, "Your board is full."
        if hp_id == "VAN_HERO_02bp":
            if len(p.board) >= 7:
                return False, "Your board is full."
            existing = {m.card_id for m in p.board}
            if len(existing.intersection({"VAN_CS2_050", "VAN_CS2_051", "VAN_CS2_052", "VAN_NEW1_009"})) >= 4:
                return False, "All 4 basic Totems are already on the battlefield."
        hp_rule = self.get_hero_power_target_rule(seat)
        if hp_rule != "NONE":
            if not self.get_valid_targets(seat, hp_rule, is_spell_or_power=True):
                return False, "No valid Hero Power targets."
        return True, "ok"

    def get_hero_power_target_rule(self, seat: str) -> str:
        p = self.state.players[seat]
        hp_id = p.hero.hero_power_id
        # Steamwheedle Sniper lets Hunter Hero Power target minions
        if hp_id in ("VAN_HERO_05bp", "AT_132_HUNTER") and any(
            not m.silenced and m.card_id == "GVG_087" for m in p.board
        ):
            return "ANY"
        return TARGET_RULES.get(hp_id, "NONE")

    def get_legal_attack_targets(self, seat: str, attacker_id: str) -> list[str]:
        if self.state.phase != "PLAY" or self.state.active_seat != seat or self.state.pending_choice is not None:
            return []
        p = self.state.players[seat]
        opp_seat = self.other_seat(seat)
        opp = self.state.players[opp_seat]

        cant_hit_hero = False
        if attacker_id == f"hero_{seat}":
            if p.hero.frozen or p.hero.attack <= 0:
                return []
            max_atk = 2 if (p.weapon and p.weapon.windfury) else 1
            if p.hero.attacks_this_turn >= max_atk:
                return []
            if p.weapon and p.weapon.card_id == "KAR_028":  # Fool's Bane
                cant_hit_hero = True
        else:
            m = self.find_minion(attacker_id)
            if not m or m.owner != seat:
                return []
            if m.frozen or m.has_keyword("CANT_ATTACK") or m.has_keyword("DORMANT") or m.attack <= 0:
                return []
            if m.summoned_this_turn and not m.has_keyword("CHARGE"):
                if m.has_keyword("RUSH"):
                    cant_hit_hero = True
                else:
                    return []
            if m.attacks_this_turn >= m.max_attacks():
                return []
            if (
                m.cant_attack_hero_this_turn
                or m.has_keyword("CANT_ATTACK_HERO")
                or any(e.cant_attack_hero for e in m.enchantments)
                or (not m.silenced and m.card_id == "AT_125")  # Icehowl
            ):
                cant_hit_hero = True

        taunts = [
            em.uid for em in opp.board
            if em.has_keyword("TAUNT") and not em.has_keyword("STEALTH") and not em.has_keyword("DORMANT") and not em.immune_this_turn
        ]
        if taunts:
            return taunts
        targets = []
        if not cant_hit_hero and not opp.hero.immune_this_turn and not opp.hero.immune_aura:
            targets.append(f"hero_{opp_seat}")
        for em in opp.board:
            if not em.has_keyword("STEALTH") and not em.has_keyword("DORMANT") and not em.immune_this_turn:
                targets.append(em.uid)
        return targets

    # -----------------------------------------------------------------------
    # PLAY CARD, HERO POWER, CHOICE, ATTACK
    # -----------------------------------------------------------------------

    @_action
    def play_card(
        self,
        seat: str,
        hand_index: int,
        pos: Optional[int] = None,
        target_id: Optional[str] = None,
        choose: Optional[int] = None,
    ) -> None:
        ok, msg = self.can_play_card(seat, hand_index)
        if not ok:
            raise GameError(msg)
        p = self.state.players[seat]
        opp_seat = self.other_seat(seat)
        opp = self.state.players[opp_seat]
        ci = p.hand[hand_index]
        card = get_card(ci.card_id)
        was_combo = p.cards_played_this_turn > 0

        if card.id in CHOOSE_ONE_OPTIONS:
            opts = CHOOSE_ONE_OPTIONS[card.id]
            if choose is None:
                if self.has_fandral(seat):
                    choose = 0
                else:
                    raise GameError(f"{card.name} requires choosing option 0 or 1.")
            if choose not in (0, 1):
                raise GameError(f"{card.name} requires choosing option 0 or 1.")
            opt = opts[choose]
            rule = opt.target_rule
        else:
            rule = self.get_target_rule(card.id, choose, was_combo, seat=seat, exclude_hand_uid=ci.uid)

        valid_targets = self.get_valid_targets(
            seat, rule, is_spell_or_power=(card.type == "SPELL")
        )
        if rule != "NONE":
            if card.type == "SPELL":
                if target_id not in valid_targets:
                    raise GameError(f"Invalid target for {card.name}.")
            else:
                # Battlecry minion / weapon: target required ONLY if valid_targets is non-empty!
                if valid_targets:
                    if target_id not in valid_targets:
                        raise GameError(f"Invalid Battlecry target for {card.name}.")
                else:
                    target_id = None

        cost = self.get_card_cost(seat, ci)
        pays_health = (
            (card.type == "SPELL" and p.next_spell_costs_health)
            or (card.type == "MINION" and card.race == "MURLOC" and p.next_murloc_costs_health)
            or (card.type == "SPELL" and any(not bm.silenced and bm.card_id == "OG_121" for bm in p.board))
        )
        if pays_health:
            if card.type == "SPELL":
                p.next_spell_costs_health = False
            elif card.race == "MURLOC":
                p.next_murloc_costs_health = False
            if cost > 0:
                self.deal_damage(f"hero_{seat}", cost, source_seat=seat, source_name=card.name)
        else:
            p.mana -= cost
        p.hand.pop(hand_index)
        p.cards_played_this_turn += 1
        self.emit(
            "play",
            seat=seat,
            uid=ci.uid,
            hand_index=hand_index,
            card=card.to_dict(),
            card_class=card.card_class,
            card_type=card.type,
            cost=cost,
            mana=p.mana,
            target=target_id,
            pos=pos,
            secret=card.has_mechanic("SECRET"),
        )

        # Consume cost-mod turn flags
        if card.type == "SPELL":
            if card.has_mechanic("SECRET") and p.next_secret_free:
                p.next_secret_free = False
            elif not p.enemy_spells_free_this_turn:
                p.next_spell_cost_mod = 0
        elif card.type == "MINION":
            p.minions_played_this_turn += 1
            if card.race == "DRAGON" and p.next_dragon_cost_mod:
                p.next_dragon_cost_mod = 0

        # Apply Overload
        if card.overload > 0:
            p.pending_overload += card.overload

        expansions.on_card_played(self, seat, card, ci)

        # Card played triggers (Questing Adventurer, Illidan Stormrage, Unbound Elemental, Tunnel Trogg)
        for m in list(p.board):
            if not m.silenced:
                if m.card_id == "VAN_EX1_044":  # Questing Adventurer
                    self.add_enchantment(m.uid, m.card_id, "Questing Adventurer", atk=1, hp=1)
                elif m.card_id == "VAN_EX1_614":  # Illidan Stormrage
                    idx = p.board.index(m) + 1 if m in p.board else None
                    self.summon_minion(seat, "VAN_TU4e_002t", pos=idx)
                elif m.card_id == "VAN_EX1_258" and card.overload > 0:  # Unbound Elemental
                    self.add_enchantment(m.uid, m.card_id, "Unbound Elemental", atk=1, hp=1)
                elif m.card_id == "LOE_018" and card.overload > 0:  # Tunnel Trogg
                    self.add_enchantment(m.uid, m.card_id, "Tunnel Trogg", atk=card.overload)

        # Opponent card-played triggers (Fel Reaver)
        for m in list(opp.board):
            if not m.silenced and m.card_id == "GVG_016":
                removed = 0
                for _ in range(3):
                    if opp.deck:
                        burned = opp.deck.pop(0)
                        removed += 1
                        self.emit("burn", seat=opp_seat, card=get_card(burned.card_id).to_dict(), origin="fel_reaver")
                if removed:
                    self.add_log(f"Fel Reaver discarded {removed} cards from {opp.name}'s deck.", seat=opp_seat)

        if card.type == "MINION":
            self.add_log(f"{p.name} played {card.name}.", seat=seat)
            summoned = self.summon_minion(seat, card.id, pos=pos, from_hand=True, hand_card=ci)
            if summoned:
                has_brann = any(not bm.silenced and bm.card_id == "LOE_077" for bm in p.board)
                trigger_battlecry(self, seat, card.id, summoned, target_id, choose, was_combo, card_instance=ci)
                if has_brann and card.has_mechanic("BATTLECRY") and self.state.pending_choice is None:
                    self.recompute_auras()
                    trigger_battlecry(self, seat, card.id, summoned, target_id, choose, was_combo, card_instance=ci)
                self.recompute_auras()
                # Opponent Secrets on minion played (Mirror Entity, Snipe, Repentance, Potion of Polymorph, Sacred Trial, Frozen Clone...)
                self._trigger_secrets_on_minion_played(opp_seat, summoned)
                expansions.on_minion_played(self, seat, card, summoned)
                meta_effects.on_minion_played(self, seat, card)

        elif card.type == "WEAPON":
            self.add_log(f"{p.name} equipped {card.name}.", seat=seat)
            self.equip_weapon(seat, card.id)
            trigger_battlecry(self, seat, card.id, None, target_id, choose, was_combo, card_instance=ci)

        elif card.type == "SPELL":
            if card.has_mechanic("SECRET"):
                self.add_log(f"{p.name} played a {card.card_class.title()} Secret.", seat=seat)
            else:
                self.add_log(f"{p.name} cast {card.name}.", seat=seat)

            # On-spell-cast triggers (Mana Wyrm, Mana Addict, Gadgetzan Auctioneer, Violet Teacher, Antonidas, Secretkeeper, Lorewalker Cho)
            self._on_spell_cast(seat, card, target_id)
            p.spells_cast_by_id.append(card.id)

            # Check Counterspell first
            countered = self._trigger_counterspell(opp_seat, card)
            if not countered:
                if card.has_mechanic("SECRET"):
                    sec_inst = SecretInstance(
                        uid=self._new_uid("sec"),
                        card_id=card.id,
                        card_class=card.card_class,
                        name=card.name,
                    )
                    p.secrets.append(sec_inst)
                    self.emit("secret_add", seat=seat, uid=sec_inst.uid, card_class=card.card_class)
                else:
                    # Check Spellbender if targeting a minion
                    if target_id and not target_id.startswith("hero_"):
                        target_id = self._trigger_spellbender(opp_seat, target_id)
                    cast_spell(self, seat, card.id, target_id, choose, was_combo, card_instance=ci)

                # After-spell triggers (Wild Pyromancer, Flamewaker, expansion after-spell)
                for m in list(p.board):
                    if m in p.board and not m.silenced and m.health > 0:
                        if m.card_id == "VAN_NEW1_020":  # Wild Pyromancer
                            for s in ("p1", "p2"):
                                for bm in list(self.state.players[s].board):
                                    self.deal_damage(bm.uid, 1, source_seat=seat, source_name="Wild Pyromancer", source_minion=m)
                        elif m.card_id == "BRM_002":  # Flamewaker
                            for _ in range(2):
                                cands = self.living_enemy_characters(seat)
                                if not cands:
                                    break
                                self.deal_damage(self.rng.choice(cands), 1, source_seat=seat, source_name="Flamewaker", source_minion=m)
                expansions.on_after_spell(self, seat, card, target_id)
                meta_effects.on_spell_resolved(self, seat, card)

        self.resolve_deaths()
        if card.type == "SPELL" and not countered and self.state.phase == "PLAY":
            if self._trigger_briar_ambush(opp_seat) or expansions.trigger_secrets_on_spell(self, opp_seat, card, target_id):
                self.resolve_deaths()
        self.recompute_auras()

    @_action
    def resolve_pending_choice(self, seat: str, option_index: int) -> None:
        pc = self.state.pending_choice
        if not pc or pc.seat != seat:
            raise GameError("No pending choice for you.")
        if option_index < 0 or option_index >= len(pc.options):
            raise GameError("Invalid choice option.")
        picked = pc.options[option_index]
        choice_type = pc.choice_type
        self.state.pending_choice = None
        p = self.state.players[seat]
        if choice_type == "DISCOVER_HERO_POWER":
            p.hero.hero_power_id = picked.card_id
            p.hero.hero_power_used = False
            p.hero.hero_power_uses_this_turn = 0
            self.add_log(f"{p.name} discovered {get_card(picked.card_id).name}.", seat=seat)
        elif choice_type == "TOTEM":
            self.summon_minion(seat, picked.card_id)
            self.add_log(f"{p.name} summoned {get_card(picked.card_id).name}.", seat=seat)
            self.resolve_deaths()
        elif expansions.resolve_pending_choice(self, seat, pc, picked, option_index):
            self.resolve_deaths()
        else:
            self.give_card_instance_to_hand(seat, picked, origin="choice")
            label = "Tracking" if choice_type == "TRACKING" else "Discover"
            self.add_log(f"{p.name} chose a card from {label}.", seat=seat)
        self.recompute_auras()

    @_action
    def use_hero_power(self, seat: str, target_id: Optional[str] = None) -> None:
        ok, msg = self.can_use_hero_power(seat)
        if not ok:
            raise GameError(msg)
        p = self.state.players[seat]
        opp_seat = self.other_seat(seat)
        hp_id = p.hero.hero_power_id
        rule = self.get_hero_power_target_rule(seat)
        if rule != "NONE":
            valid = self.get_valid_targets(seat, rule, is_spell_or_power=True)
            if target_id not in valid:
                raise GameError("Invalid Hero Power target.")
        hp_cost = self.get_hero_power_cost(seat)
        p.mana -= hp_cost
        p.next_hero_power_cost_mod = 0
        p.hero.hero_power_uses_this_turn += 1
        p.hero_power_uses_total += 1
        max_uses = expansions.get_hero_power_max_uses(self, seat)
        p.hero.hero_power_used = p.hero.hero_power_uses_this_turn >= max_uses
        hp_card = get_card(hp_id)
        self.add_log(f"{p.name} used Hero Power ({hp_card.name}).", seat=seat)
        self.emit("hero_power", seat=seat, id=hp_id, name=hp_card.name, target=target_id, mana=p.mana)
        # Steamwheedle Sniper targeted Hunter Hero Power
        if hp_id in ("VAN_HERO_05bp", "AT_132_HUNTER") and target_id:
            dmg = (3 if hp_id == "AT_132_HUNTER" else 2) + sum(
                1 for m in p.board if not m.silenced and m.card_id == "AT_003"
            )
            self.deal_damage(target_id, dmg * self.velen_multiplier(seat), source_seat=seat, source_name=hp_card.name)
        else:
            trigger_hero_power(self, seat, hp_id, target_id)
        expansions.on_inspire(self, seat)
        meta_effects.on_hero_power(self, seat)
        expansions.trigger_secrets_on_hero_power(self, opp_seat)
        self.resolve_deaths()
        self.recompute_auras()

    @_action
    def attack(self, seat: str, attacker_id: str, target_id: str) -> None:
        valid = self.get_legal_attack_targets(seat, attacker_id)
        if target_id not in valid:
            raise GameError("Illegal attack target.")

        p = self.state.players[seat]
        opp_seat = self.other_seat(seat)
        opp = self.state.players[opp_seat]
        is_hero_atk = attacker_id == f"hero_{seat}"
        atk_minion = None if is_hero_atk else self.find_minion(attacker_id)

        if is_hero_atk:
            p.hero.attacks_this_turn += 1
            if p.weapon and p.weapon.card_id == "VAN_CS2_097":  # Truesilver Champion
                self.apply_heal(seat, f"hero_{seat}", 2)
            if p.weapon and p.weapon.card_id == "VAN_DS1_188":  # Gladiator's Longbow
                p.hero.immune_this_turn = True
        else:
            assert atk_minion is not None
            atk_minion.attacks_this_turn += 1
            self.break_stealth(atk_minion)
            # Blessing of Wisdom triggers on attack declaration
            for ench in atk_minion.enchantments:
                if ench.blessing_of_wisdom_owner:
                    self.draw_card(ench.blessing_of_wisdom_owner)

        # Trigger attack secrets (defender is opp_seat) & expansion attack hooks (Forgetful / Mogor / etc.)
        target_id, aborted = self._trigger_secrets_on_attack(opp_seat, attacker_id, target_id)
        if not aborted:
            target_id, aborted = expansions.on_attack(self, seat, attacker_id, target_id)
        if not aborted:
            # 50% wrong enemy for FORGETFUL minions or Mogor the Ogre on either board
            has_mogor = any(
                not bm.silenced and bm.card_id == "GVG_112"
                for s in ("p1", "p2")
                for bm in self.state.players[s].board
            )
            is_forgetful = (atk_minion is not None and not atk_minion.silenced and atk_minion.has_keyword("FORGETFUL")) or has_mogor
            if is_forgetful and self.rng.random() < 0.5:
                other_enemies = [
                    eid for eid in ([f"hero_{opp_seat}"] + [em.uid for em in opp.board if not em.has_keyword("DORMANT")])
                    if eid != target_id
                ]
                if other_enemies:
                    target_id = self.rng.choice(other_enemies)
        self.resolve_deaths()
        self.recompute_auras()
        if aborted or self.state.phase == "GAME_OVER":
            if is_hero_atk and p.weapon and p.weapon.card_id == "VAN_DS1_188":
                p.hero.immune_this_turn = False
            return

        # Re-verify attacker still alive and on board
        if not is_hero_atk:
            if not atk_minion or atk_minion not in p.board:
                return

        atk_power = p.hero.attack if is_hero_atk else atk_minion.attack
        atk_name = p.hero.name if is_hero_atk else atk_minion.name
        self.emit("attack", seat=seat, attacker=attacker_id, target=target_id)

        self._combat = True
        try:
            if target_id.startswith("hero_"):
                tseat = target_id.split("_")[1]
                t_hero = self.state.players[tseat].hero
                self.add_log(f"{atk_name} attacked {t_hero.name} for {atk_power}.", seat=seat)
                self.deal_damage(target_id, atk_power, source_seat=seat, source_name=atk_name, source_minion=atk_minion)
                if t_hero.attack > 0:
                    self.deal_damage(attacker_id, t_hero.attack, source_seat=tseat, source_name=t_hero.name)
                # Consume weapon durability on hero attack
                if is_hero_atk and p.weapon:
                    self._consume_weapon_swing(seat, hit_minion=False)
            else:
                def_m = self.find_minion(target_id)
                if def_m:
                    def_atk = def_m.attack
                    self.add_log(f"{atk_name} attacked {def_m.name}.", seat=seat)
                    self.deal_damage(def_m.uid, atk_power, source_seat=seat, source_name=atk_name, source_minion=atk_minion)
                    if def_atk > 0:
                        self.deal_damage(attacker_id, def_atk, source_seat=def_m.owner, source_name=def_m.name, source_minion=def_m)
                    if is_hero_atk and p.weapon:
                        self._consume_weapon_swing(seat, hit_minion=True)
        finally:
            self._combat = False

        if is_hero_atk and p.weapon and p.weapon.card_id == "VAN_DS1_188":
            p.hero.immune_this_turn = False

        expansions.on_after_attack(self, seat, attacker_id, target_id)
        self.resolve_deaths()
        self.recompute_auras()

    def _consume_weapon_swing(self, seat: str, hit_minion: bool) -> None:
        p = self.state.players[seat]
        if not p.weapon:
            return
        if p.weapon.card_id == "VAN_EX1_411" and hit_minion:  # Gorehowl
            p.weapon.attack_bonus -= 1
            if p.weapon.total_attack <= 0:
                self.destroy_weapon(seat)
        else:
            p.weapon.durability -= 1
            if p.weapon.durability <= 0:
                self.destroy_weapon(seat)

    @_action
    def concede(self, seat: str) -> None:
        if self.state.phase == "GAME_OVER":
            return
        self.emit("concede", seat=seat)
        self.state.phase = "GAME_OVER"
        self.state.winner = self.other_seat(seat)
        self.add_log(f"{self.state.players[seat].name} conceded!", seat=seat)

    def send_emote(self, seat: str, message: str) -> None:
        self.state.last_emote = {
            "id": int(time.time() * 1000),
            "seat": seat,
            "name": self.state.players[seat].name,
            "text": message[:160],
        }
        self.add_log(f"{self.state.players[seat].name} says: \"{message[:160]}\"", seat=seat)

    # -----------------------------------------------------------------------
    # PRIMITIVE ENGINE OPERATIONS (DAMAGE, HEAL, SUMMON, DEATHS, SECRETS)
    # -----------------------------------------------------------------------

    def find_minion(self, uid: Optional[str]) -> Optional[Minion]:
        if not uid:
            return None
        for s in ("p1", "p2"):
            for m in self.state.players[s].board:
                if m.uid == uid:
                    return m
        return None

    def living_enemy_characters(self, seat: str) -> list[str]:
        opp_seat = self.other_seat(seat)
        opp = self.state.players[opp_seat]
        out = []
        if opp.hero.hp > 0:
            out.append(f"hero_{opp_seat}")
        for m in opp.board:
            if m.health > 0:
                out.append(m.uid)
        return out

    def is_frozen(self, target_id: Optional[str]) -> bool:
        if not target_id:
            return False
        if target_id.startswith("hero_"):
            return self.state.players[target_id.split("_")[1]].hero.frozen
        m = self.find_minion(target_id)
        return bool(m and m.frozen)

    def freeze_character(self, target_id: Optional[str]) -> None:
        if not target_id:
            return
        if target_id.startswith("hero_"):
            tseat = target_id.split("_")[1]
            h = self.state.players[tseat].hero
            h.frozen = True
            h.freeze_until_eot_of = tseat
            self.emit("freeze", target=target_id)
        else:
            m = self.find_minion(target_id)
            if m:
                m.frozen = True
                m.freeze_until_eot_of = m.owner
                self.emit("freeze", target=target_id)

    def break_stealth(self, m: Minion) -> None:
        m.base_keywords.discard("STEALTH")
        for e in m.enchantments:
            e.add_keywords.discard("STEALTH")
        m.keywords.discard("STEALTH")
        m.stealth_until_sot_of = None

    def strip_divine_shield(self, m: Minion) -> None:
        m.base_keywords.discard("DIVINE_SHIELD")
        for e in m.enchantments:
            e.add_keywords.discard("DIVINE_SHIELD")
        m.keywords.discard("DIVINE_SHIELD")

    def _log_hit(self, source_name: str, target_name: str, amount: int, source_seat: Optional[str]) -> None:
        """Damage from an effect (a spell, a deathrattle, a trigger) is written to the log with its
        amount; the blows of an attack are already there as the attack."""
        if source_name and not getattr(self, "_combat", False):
            self.add_log(f"{source_name} hit {target_name} for {amount}.", seat=source_seat)

    def deal_damage(
        self,
        target_id: Optional[str],
        amount: int,
        source_seat: Optional[str] = None,
        source_name: str = "",
        source_minion: Optional[Minion] = None,
    ) -> int:
        if not target_id or amount <= 0:
            return 0

        if source_minion is not None and source_minion.has_keyword("STEALTH"):
            self.break_stealth(source_minion)

        if target_id.startswith("hero_"):
            tseat = target_id.split("_")[1]
            hero = self.state.players[tseat].hero
            if hero.immune_this_turn or hero.immune_aura:
                self.emit("immune", target=target_id)
                return 0
            # Check Ice Block (only on opponent's turn!)
            if amount >= hero.hp + hero.armor and tseat != self.state.active_seat:
                if self._trigger_ice_block(tseat):
                    self.emit("immune", target=target_id)
                    return 0

            rem = amount
            if hero.armor > 0:
                absorbed = min(hero.armor, rem)
                hero.armor -= absorbed
                rem -= absorbed
            if rem > 0:
                hero.hp -= rem
            self.emit(
                "damage",
                target=target_id,
                amount=amount,
                hp=hero.hp,
                armor=hero.armor,
                source=source_minion.uid if source_minion else None,
                source_seat=source_seat,
            )
            self._log_hit(source_name, hero.name, amount, source_seat)
            # Lifesteal on minion or weapon hitting hero
            if source_seat and amount > 0:
                if source_minion and source_minion.has_keyword("LIFESTEAL"):
                    self.apply_heal(source_seat, f"hero_{source_seat}", amount)
                elif source_minion is None and getattr(self, "_combat", False) and self.state.players[source_seat].weapon and self.state.players[source_seat].weapon.lifesteal:
                    self.apply_heal(source_seat, f"hero_{source_seat}", amount)
            expansions.on_damage_hero(self, tseat, amount, source_seat, source_minion)
            if hero.hp <= 0:
                self._check_hero_deaths()
            else:
                if tseat == "p2" and rem > 0:
                    campaign_rules.on_rival_damaged(self)
                # Eye for an Eye (only on opponent's turn!)
                if amount > 0 and tseat != self.state.active_seat:
                    self._trigger_eye_for_eye(tseat, amount)

            # Water Elemental / Snowchugger freeze
            if source_minion and not source_minion.silenced and source_minion.card_id in ("VAN_CS2_033", "GVG_002"):
                self.freeze_character(target_id)
            return amount

        m = self.find_minion(target_id)
        if not m or m.has_keyword("DORMANT"):
            return 0
        if m.immune_this_turn:
            self.emit("immune", target=target_id)
            return 0
        if m.has_keyword("DIVINE_SHIELD"):
            self.strip_divine_shield(m)
            self.emit("shield_break", target=target_id)
            expansions.on_divine_shield_lost(self, m)
            return 0

        owner_p = self.state.players[m.owner]
        m.damage += amount
        if owner_p.commanding_shout_active and m.health < 1:
            m.damage = max(0, m.max_health - 1)
        self.emit(
            "damage",
            target=target_id,
            amount=amount,
            health=m.health,
            source=source_minion.uid if source_minion else None,
            source_seat=source_seat,
        )
        self._log_hit(source_name, m.name, amount, source_seat)

        # On-damage minion triggers
        if not m.silenced:
            if m.card_id == "VAN_EX1_007":  # Acolyte of Pain
                self.draw_card(m.owner)
            elif m.card_id == "VAN_EX1_399":  # Gurubashi Berserker
                self.add_enchantment(m.uid, m.card_id, "Gurubashi Berserker", atk=3)
            elif m.card_id == "BRM_006":  # Imp Gang Boss
                idx = owner_p.board.index(m) + 1 if m in owner_p.board else None
                self.summon_minion(m.owner, "BRM_006t", pos=idx)
            elif m.card_id == "LF_M02" and m.health > 0:
                self.summon_minion(m.owner, "LF_M02t", pos=owner_p.board.index(m) + 1)

        for bm in list(owner_p.board):
            if not bm.silenced and bm.card_id == "VAN_EX1_402":  # Armorsmith
                owner_p.hero.armor += 1

        for s in ("p1", "p2"):
            for bm in list(self.state.players[s].board):
                if not bm.silenced and bm.card_id == "VAN_EX1_604":  # Frothing Berserker
                    self.add_enchantment(bm.uid, bm.card_id, "Frothing Berserker", atk=1)

        # Poisonous / Lifesteal / Water Elemental / Snowchugger
        if source_minion:
            if (not source_minion.silenced and source_minion.card_id in ("VAN_EX1_170", "VAN_EX1_522")) or source_minion.has_keyword("POISONOUS"):
                if not owner_p.commanding_shout_active:
                    m.damage = max(m.damage, m.max_health)
            if source_minion.has_keyword("LIFESTEAL") and source_seat:
                self.apply_heal(source_seat, f"hero_{source_seat}", amount)
            if not source_minion.silenced and source_minion.card_id in ("VAN_CS2_033", "GVG_002"):
                self.freeze_character(m.uid)
        elif source_seat and getattr(self, "_combat", False) and self.state.players[source_seat].weapon:
            wep = self.state.players[source_seat].weapon
            if wep.poisonous and not owner_p.commanding_shout_active:
                m.damage = max(m.damage, m.max_health)
            if wep.lifesteal:
                self.apply_heal(source_seat, f"hero_{source_seat}", amount)

        expansions.on_damage_minion(self, m, amount, source_seat, source_minion)
        return amount

    def apply_heal(
        self,
        caster_seat: str,
        target_id: Optional[str],
        amount: int,
        from_spell_or_power: bool = False,
    ) -> int:
        if not target_id or amount <= 0:
            return 0
        if from_spell_or_power and self.has_auchenai(caster_seat):
            return self.deal_damage(target_id, amount, source_seat=caster_seat, source_name="Auchenai Soulpriest")

        healed = 0
        healed_minion = False
        if target_id.startswith("hero_"):
            tseat = target_id.split("_")[1]
            hero = self.state.players[tseat].hero
            if hero.hp < hero.max_hp:
                healed = min(amount, hero.max_hp - hero.hp)
                hero.hp += healed
                self.emit("heal", target=target_id, amount=healed, hp=hero.hp, source_seat=caster_seat)
        else:
            m = self.find_minion(target_id)
            if m and m.damage > 0:
                healed = min(amount, m.damage)
                m.damage -= healed
                healed_minion = healed > 0
                self.emit("heal", target=target_id, amount=healed, health=m.health, source_seat=caster_seat)

        if healed > 0:
            for s in ("p1", "p2"):
                for bm in list(self.state.players[s].board):
                    if not bm.silenced:
                        if bm.card_id == "VAN_EX1_001":  # Lightwarden
                            self.add_enchantment(bm.uid, bm.card_id, "Lightwarden", atk=2)
                        elif healed_minion and bm.card_id == "VAN_CS2_235":  # Northshire Cleric
                            self.draw_card(bm.owner)
            expansions.on_heal(self, caster_seat, target_id, healed, healed_minion)
        return healed

    def add_enchantment(
        self,
        target_uid: Optional[str],
        source_card_id: str,
        source_name: str,
        atk: int = 0,
        hp: int = 0,
        set_atk: Optional[int] = None,
        set_hp: Optional[int] = None,
        add_keywords: Optional[set[str]] = None,
        remove_keywords: Optional[set[str]] = None,
        spell_damage: int = 0,
        temp_until_eot: bool = False,
        temp_owner_revert: Optional[str] = None,
        destroy_at_eot: bool = False,
        destroy_at_owner_sot: Optional[str] = None,
        extra_deathrattle: Optional[str] = None,
        blessing_of_wisdom_owner: Optional[str] = None,
    ) -> None:
        m = self.find_minion(target_uid)
        if not m:
            return
        if set_hp is not None:
            m.damage = 0
            m.max_health = 0
        m.enchantments.append(
            Enchantment(
                uid=self._new_uid("ench"),
                source_card_id=source_card_id,
                source_name=source_name,
                atk=atk,
                hp=hp,
                set_atk=set_atk,
                set_hp=set_hp,
                add_keywords=set(add_keywords or ()),
                remove_keywords=set(remove_keywords or ()),
                spell_damage=spell_damage,
                temp_until_eot=temp_until_eot,
                temp_owner_revert=temp_owner_revert,
                destroy_at_eot=destroy_at_eot,
                destroy_at_owner_sot=destroy_at_owner_sot,
                extra_deathrattle=extra_deathrattle,
                blessing_of_wisdom_owner=blessing_of_wisdom_owner,
            )
        )
        self.recompute_auras()
        self.emit(
            "buff",
            target=m.uid,
            source=source_name,
            atk=atk,
            hp=hp,
            set_atk=set_atk,
            set_hp=set_hp,
            keywords=sorted(add_keywords or ()),
            minion=self._serialize_minion(m, is_owner=False),
        )

    def silence_minion(self, target_uid: Optional[str]) -> None:
        m = self.find_minion(target_uid)
        if not m or m.has_keyword("DORMANT"):
            return
        old_hp = m.health
        m.silenced = True
        m.frozen = False
        m.freeze_until_eot_of = None
        m.stealth_until_sot_of = None
        m.enchantments.clear()
        m.base_keywords.clear()
        m.base_spell_damage = 0
        new_max = m.base_health
        if new_max < old_hp:
            m.damage = 0
        else:
            m.damage = max(0, new_max - old_hp)
        m.max_health = 0
        self.recompute_auras()
        self.emit("silence", target=m.uid, minion=self._serialize_minion(m, is_owner=False))

    def destroy_minion(self, target_uid: Optional[str]) -> None:
        m = self.find_minion(target_uid)
        if m and not m.has_keyword("DORMANT"):
            m.damage = max(m.damage, m.max_health + 999)
            self.emit("destroy", target=m.uid)

    def remove_minion(self, m: Minion) -> None:
        """Take a minion off the board without it dying (no death triggers)."""
        board = self.state.players[m.owner].board
        if m in board:
            board.remove(m)
            self.emit("remove", target=m.uid, seat=m.owner)
            self.recompute_auras()

    def transform_minion(self, target_uid: Optional[str], new_card_id: str) -> Optional[Minion]:
        m = self.find_minion(target_uid)
        if not m:
            return None
        board = self.state.players[m.owner].board
        idx = board.index(m)
        board.pop(idx)
        return self.summon_minion(m.owner, new_card_id, pos=idx, trigger_summon=True, replaces=m.uid)

    def copy_minion_into(self, src: Minion, dst: Minion) -> None:
        dst.card_id = src.card_id
        dst.name = src.name
        dst.base_attack = src.base_attack
        dst.base_health = src.base_health
        dst.damage = src.damage
        dst.race = src.race
        dst.base_keywords = set(src.base_keywords)
        dst.base_spell_damage = src.base_spell_damage
        dst.silenced = src.silenced
        dst.frozen = src.frozen
        dst.freeze_until_eot_of = src.freeze_until_eot_of
        dst.enchantments = [e.clone() for e in src.enchantments]
        self.recompute_auras()
        self.emit("morph", target=dst.uid, minion=self._serialize_minion(dst, is_owner=False))

    def steal_minion(self, target_uid: Optional[str], new_owner: str) -> None:
        m = self.find_minion(target_uid)
        if not m or m.owner == new_owner:
            return
        dst_board = self.state.players[new_owner].board
        if len(dst_board) >= 7:
            return
        src_board = self.state.players[m.owner].board
        src_board.remove(m)
        old_owner = m.owner
        m.owner = new_owner
        m.summoned_this_turn = True
        m.attacks_this_turn = 0
        dst_board.append(m)
        self.recompute_auras()
        self.emit(
            "steal",
            target=m.uid,
            seat=new_owner,
            from_seat=old_owner,
            minion=self._serialize_minion(m, is_owner=False),
        )

    def bounce_minion(self, m: Minion, cost_mod_delta: int = 0) -> None:
        owner_p = self.state.players[m.owner]
        if m in owner_p.board:
            owner_p.board.remove(m)
        if len(owner_p.hand) >= 10:
            # Hand full -> destroyed (triggers deathrattle)
            self.add_log(f"{m.name} could not return to a full hand and was destroyed!", seat=m.owner)
            self.emit("death", target=m.uid, seat=m.owner)
            trigger_deathrattle(self, m, len(owner_p.board))
        else:
            ci = CardInstance(uid=self._new_uid("c"), card_id=m.card_id, cost_mod=cost_mod_delta)
            owner_p.hand.append(ci)
            self.emit("bounce", target=m.uid, seat=m.owner, uid=ci.uid, card=get_card(m.card_id).to_dict())
        self.recompute_auras()

    def summon_minion(
        self,
        seat: str,
        card_id: str,
        pos: Optional[int] = None,
        from_hand: bool = False,
        trigger_summon: bool = True,
        replaces: Optional[str] = None,
        hand_card: Optional[CardInstance] = None,
    ) -> Optional[Minion]:
        p = self.state.players[seat]
        if len(p.board) >= 7:
            if replaces:
                self.emit("remove", target=replaces, seat=seat)
            return None
        cdef = get_card(card_id)
        m = Minion(
            uid=self._new_uid("m"),
            card_id=cdef.id,
            owner=seat,
            name=cdef.name,
            base_attack=cdef.attack or 0,
            base_health=cdef.health or 1,
            race=cdef.race,
            base_keywords=set(cdef.mechanics),
            base_spell_damage=cdef.spell_damage,
            summoned_this_turn=True,
        )
        if p.echo_sigil and m.base_attack <= 3:
            m.base_attack = m.base_health = 4
        if cdef.id == "OG_280" and (p.cthun_atk != 6 or p.cthun_hp != 6 or p.cthun_taunt):
            extra_kws = {"TAUNT"} if p.cthun_taunt else set()
            m.enchantments.append(Enchantment(
                self._new_uid("ench"), "OG_280", "C'Thun",
                atk=p.cthun_atk - 6, hp=p.cthun_hp - 6, add_keywords=extra_kws,
            ))
        if hand_card and (hand_card.attack_mod or hand_card.health_mod):
            # Avoid double-counting C'Thun hand buff since C'Thun gets player's cthun_atk/hp
            if cdef.id != "OG_280":
                m.enchantments.append(Enchantment(
                    self._new_uid("ench"), "LF_M18", "Hand buff", atk=hand_card.attack_mod, hp=hand_card.health_mod,
                ))
        if pos is None or pos < 0 or pos > len(p.board):
            p.board.append(m)
        else:
            p.board.insert(pos, m)

        if m.race == "TOTEM":
            p.totems_summoned += 1

        self.recompute_auras()
        self.emit(
            "transform" if replaces else "summon",
            seat=seat,
            target=replaces,
            pos=p.board.index(m),
            from_hand=from_hand,
            minion=self._serialize_minion(m, is_owner=False),
        )
        if trigger_summon:
            self._on_minion_summoned(seat, m)
        return m

    def summon_minion_from_hand(self, seat: str, hand_index: int, pos: int) -> None:
        p = self.state.players[seat]
        if len(p.board) >= 7:
            return
        ci = p.hand.pop(hand_index)
        self.emit("hand_remove", seat=seat, uid=ci.uid, hand_index=hand_index)
        self.summon_minion(seat, ci.card_id, pos=pos, hand_card=ci)

    def equip_weapon(self, seat: str, card_id: str) -> None:
        p = self.state.players[seat]
        if p.weapon is not None:
            self.destroy_weapon(seat)
        cdef = get_card(card_id)
        dur = cdef.durability or 1
        p.weapon = Weapon(
            uid=self._new_uid("w"),
            card_id=cdef.id,
            name=cdef.name,
            base_attack=cdef.attack or 0,
            durability=dur,
            max_durability=dur,
            windfury=cdef.has_mechanic("WINDFURY"),
            lifesteal=cdef.has_mechanic("LIFESTEAL"),
            poisonous=cdef.has_mechanic("POISONOUS"),
        )
        self.recompute_auras()
        self.emit("weapon_equip", seat=seat, weapon=self._serialize_weapon(p.weapon))

    def destroy_weapon(self, seat: str) -> None:
        p = self.state.players[seat]
        if p.weapon is not None:
            old_cid = p.weapon.card_id
            p.weapon = None
            self.recompute_auras()
            self.emit("weapon_destroy", seat=seat)
            trigger_weapon_deathrattle(self, seat, old_cid)

    def draw_card(self, seat: str) -> Optional[CardInstance]:
        p = self.state.players[seat]
        if not p.deck:
            p.fatigue += 1
            self.add_log(f"{p.name} suffers {p.fatigue} Fatigue damage!", seat=seat)
            self.emit("fatigue", seat=seat, amount=p.fatigue)
            self.deal_damage(f"hero_{seat}", p.fatigue, source_seat=seat, source_name="Fatigue")
            return None
        ci = p.deck.pop(0)
        if expansions.on_draw(self, seat, ci):
            self.emit("deck_remove", seat=seat)
            self.resolve_deaths()
            self.recompute_auras()
            if self.state.phase == "PLAY":
                return self.draw_card(seat)
            return None
        return self.give_card_instance_to_hand(seat, ci)

    def add_card_to_hand(self, seat: str, card_id: str, cost_mod: int = 0) -> Optional[CardInstance]:
        ci = CardInstance(uid=self._new_uid("c"), card_id=card_id, cost_mod=cost_mod)
        return self.give_card_instance_to_hand(seat, ci, origin="created")

    def give_card_instance_to_hand(
        self, seat: str, ci: CardInstance, origin: str = "deck"
    ) -> Optional[CardInstance]:
        """origin: "deck" (drawn), "created" (made from nothing) or "choice" (picked)."""
        p = self.state.players[seat]
        cdef = get_card(ci.card_id)
        if len(p.hand) >= 10:
            self.add_log(f"{p.name}'s hand is full! {cdef.name} was burned.", seat=seat)
            self.emit("burn", seat=seat, card=cdef.to_dict(), origin=origin)
            return None
        p.hand.append(ci)
        self.emit(
            "draw" if origin == "deck" else "card_added",
            seat=seat,
            uid=ci.uid,
            card=cdef.to_dict(),
            origin=origin,
        )
        return ci

    def discard_random(self, seat: str) -> None:
        p = self.state.players[seat]
        if p.hand:
            idx = self.rng.randrange(len(p.hand))
            ci = p.hand.pop(idx)
            p.discards_total += 1
            p.discarded_cards.append(ci.card_id)
            self.add_log(f"{p.name} discarded {get_card(ci.card_id).name}.", seat=seat)
            self.emit("discard", seat=seat, uid=ci.uid, hand_index=idx, card=get_card(ci.card_id).to_dict())
            expansions.on_discard(self, seat, ci)

    def discard_hand(self, seat: str) -> None:
        p = self.state.players[seat]
        while p.hand:
            ci = p.hand.pop()
            p.discards_total += 1
            p.discarded_cards.append(ci.card_id)
            self.emit("discard", seat=seat, uid=ci.uid, hand_index=len(p.hand), card=get_card(ci.card_id).to_dict())
            expansions.on_discard(self, seat, ci)

    def destroy_secrets(self, seat: str) -> None:
        p = self.state.players[seat]
        for sec in p.secrets:
            self.emit("secret_destroy", seat=seat, uid=sec.uid)
        p.secrets.clear()

    # -----------------------------------------------------------------------
    # TRIGGER DISPATCHERS & DEATH RESOLUTION
    # -----------------------------------------------------------------------

    def _on_minion_summoned(self, seat: str, m: Minion) -> None:
        p = self.state.players[seat]
        # Sword of Justice
        if p.weapon and p.weapon.card_id == "VAN_EX1_366" and m in p.board:
            self.add_enchantment(m.uid, "VAN_EX1_366", "Sword of Justice", atk=1, hp=1)
            p.weapon.durability -= 1
            if p.weapon.durability <= 0:
                self.destroy_weapon(seat)

        # Warsong Commander (check attack <= 3)
        if any(not bm.silenced and bm.card_id == "VAN_EX1_084" and bm.uid != m.uid for bm in p.board):
            if m.attack <= 3:
                self.add_enchantment(m.uid, "VAN_EX1_084", "Warsong Commander", add_keywords={"CHARGE"})

        # Starving Buzzard
        if m.race == "BEAST":
            buzzards = sum(1 for bm in p.board if not bm.silenced and bm.card_id == "VAN_CS2_237" and bm.uid != m.uid)
            for _ in range(buzzards):
                self.draw_card(seat)

        # Murloc Tidecaller (either player summons a Murloc)
        if m.race == "MURLOC":
            for s in ("p1", "p2"):
                for bm in list(self.state.players[s].board):
                    if not bm.silenced and bm.card_id == "VAN_EX1_509" and bm.uid != m.uid:
                        self.add_enchantment(bm.uid, bm.card_id, "Murloc Tidecaller", atk=1)

        # Knife Juggler
        for bm in list(p.board):
            if not bm.silenced and bm.card_id == "VAN_NEW1_019" and bm.uid != m.uid:
                cands = self.living_enemy_characters(seat)
                if cands:
                    self.deal_damage(self.rng.choice(cands), 1, source_seat=seat, source_name="Knife Juggler", source_minion=bm)

        expansions.on_minion_summoned(self, seat, m)

    def _on_spell_cast(self, seat: str, card: CardDef, target_id: Optional[str] = None) -> None:
        p = self.state.players[seat]
        opp_seat = self.other_seat(seat)

        for bm in list(p.board):
            if bm.silenced:
                continue
            if bm.card_id == "VAN_NEW1_012":  # Mana Wyrm
                self.add_enchantment(bm.uid, bm.card_id, "Mana Wyrm", atk=1)
            elif bm.card_id == "VAN_EX1_055":  # Mana Addict
                self.add_enchantment(bm.uid, bm.card_id, "Mana Addict", atk=2, temp_until_eot=True)
            elif bm.card_id == "VAN_EX1_095":  # Gadgetzan Auctioneer
                self.draw_card(seat)
            elif bm.card_id == "VAN_NEW1_026":  # Violet Teacher
                idx = p.board.index(bm) + 1 if bm in p.board else None
                self.summon_minion(seat, "VAN_NEW1_026t", pos=idx)
            elif bm.card_id == "VAN_EX1_559":  # Archmage Antonidas
                self.add_card_to_hand(seat, "VAN_CS2_029")

        # Secretkeeper (any secret played)
        if card.has_mechanic("SECRET"):
            for s in ("p1", "p2"):
                for bm in list(self.state.players[s].board):
                    if not bm.silenced and bm.card_id == "VAN_EX1_080":
                        self.add_enchantment(bm.uid, bm.card_id, "Secretkeeper", atk=1, hp=1)

        # Lorewalker Cho (any spell cast)
        for s in ("p1", "p2"):
            for bm in list(self.state.players[s].board):
                if not bm.silenced and bm.card_id == "VAN_EX1_100":
                    self.add_card_to_hand(opp_seat, card.id)

        expansions.on_spell_cast(self, seat, card, target_id)

    def resolve_deaths(self) -> None:
        for _ in range(16):
            dead_list: list[tuple[Minion, int]] = []
            for s in ("p1", "p2"):
                board = self.state.players[s].board
                for idx, m in enumerate(board):
                    if m.health <= 0:
                        dead_list.append((m, idx))
            if not dead_list:
                break

            # Remove all dead from boards first
            dead_uids = {m.uid for m, _ in dead_list}
            for s in ("p1", "p2"):
                self.state.players[s].board = [m for m in self.state.players[s].board if m.uid not in dead_uids]
            for dead_m, _ in dead_list:
                self.emit("death", target=dead_m.uid, seat=dead_m.owner)
                owner = self.state.players[dead_m.owner]
                owner.dead_minions_this_turn.append(dead_m.card_id)
                owner.fallen_minions.append(dead_m.card_id)
                if not dead_m.silenced and dead_m.card_id in DEATHRATTLE_CARDS:
                    owner.fallen_deathrattles.append(dead_m.card_id)
                if dead_m.race == "MURLOC":
                    self.state.dead_murlocs.append(dead_m.card_id)
                self.state.dead_minions_all.append((dead_m.owner, dead_m.card_id))
                if dead_m.card_id == "OG_280":
                    owner.cthun_dead = True
                if dead_m.card_id == "FP1_015":
                    self.state.feugen_died = True
                if dead_m.card_id == "FP1_014":
                    self.state.stalagg_died = True

            # Death triggers (Flesheating Ghoul, Cult Master, Scavenging Hyena, expansions)
            for dead_m, orig_pos in dead_list:
                for s in ("p1", "p2"):
                    for bm in list(self.state.players[s].board):
                        if bm.silenced:
                            continue
                        if bm.card_id == "VAN_tt_004":  # Flesheating Ghoul
                            self.add_enchantment(bm.uid, bm.card_id, "Flesheating Ghoul", atk=1)
                        elif bm.card_id == "VAN_EX1_595" and bm.owner == dead_m.owner:  # Cult Master
                            self.draw_card(bm.owner)
                        elif bm.card_id == "VAN_EX1_531" and bm.owner == dead_m.owner and dead_m.race == "BEAST":
                            self.add_enchantment(bm.uid, bm.card_id, "Scavenging Hyena", atk=2, hp=1)
                expansions.on_death(self, dead_m, orig_pos)

            # Deathrattles & Redemption & expansion death secrets
            for dead_m, orig_pos in dead_list:
                trigger_deathrattle(self, dead_m, orig_pos)
                if dead_m.owner != self.state.active_seat:
                    self._trigger_redemption(dead_m.owner, dead_m, orig_pos)
                    expansions.trigger_secrets_on_death(self, dead_m.owner, dead_m, orig_pos)

            self.recompute_auras()
        self._check_hero_deaths()

    def _check_hero_deaths(self) -> None:
        p1_dead = self.state.players["p1"].hero.hp <= 0
        p2_dead = self.state.players["p2"].hero.hp <= 0
        if p1_dead or p2_dead:
            winner = "draw" if p1_dead and p2_dead else "p2" if p1_dead else "p1"
            if self.state.phase == "GAME_OVER" and self.state.winner == winner:
                return  # already recorded; this runs again as later effects resolve
            self.state.phase = "GAME_OVER"
            self.state.winner = winner
            if winner == "draw":
                self.add_log("Both heroes fell! The game ends in a Draw.")
            else:
                self.add_log(f"{self.state.players[winner].name} wins!")

    # -----------------------------------------------------------------------
    # SECRET TRIGGERS
    # -----------------------------------------------------------------------

    def _reveal_secret(self, owner_seat: str, sec: SecretInstance) -> None:
        self.state.players[owner_seat].secrets.remove(sec)
        self.add_log(f"Secret revealed: {sec.name}!", seat=owner_seat)
        self.emit("secret_reveal", seat=owner_seat, uid=sec.uid, card=get_card(sec.card_id).to_dict())
        # Eaglehorn Bow gains +1 Durability whenever a Secret is revealed
        for s in ("p1", "p2"):
            pl = self.state.players[s]
            if pl.weapon and pl.weapon.card_id == "VAN_EX1_536":
                pl.weapon.durability += 1
                pl.weapon.max_durability += 1
        expansions.on_secret_revealed(self, owner_seat, sec)

    def _trigger_counterspell(self, def_seat: str, spell_card: CardDef) -> bool:
        p = self.state.players[def_seat]
        for sec in list(p.secrets):
            if sec.card_id == "VAN_EX1_287":
                self._reveal_secret(def_seat, sec)
                self.add_log(f"Counterspell countered {spell_card.name}!", seat=def_seat)
                self.emit("countered", seat=self.other_seat(def_seat), card=spell_card.to_dict())
                return True
        return False

    def _trigger_briar_ambush(self, def_seat: str) -> bool:
        p = self.state.players[def_seat]
        if len(p.board) >= 7:
            return False
        for sec in p.secrets:
            if sec.card_id == "LF_002":
                self._reveal_secret(def_seat, sec)
                self.summon_minion(def_seat, "LF_002t")
                return True
        return False

    def _trigger_spellbender(self, def_seat: str, target_id: str) -> str:
        p = self.state.players[def_seat]
        if len(p.board) >= 7:
            return target_id
        for sec in list(p.secrets):
            if sec.card_id == "VAN_tt_010":
                self._reveal_secret(def_seat, sec)
                sb = self.summon_minion(def_seat, "VAN_tt_010a")
                if sb:
                    return sb.uid
        return target_id

    def _trigger_ice_block(self, def_seat: str) -> bool:
        p = self.state.players[def_seat]
        for sec in list(p.secrets):
            if sec.card_id == "VAN_EX1_295":
                self._reveal_secret(def_seat, sec)
                p.hero.immune_this_turn = True
                return True
        return False

    def _trigger_eye_for_eye(self, def_seat: str, dmg: int) -> None:
        p = self.state.players[def_seat]
        opp_seat = self.other_seat(def_seat)
        for sec in list(p.secrets):
            if sec.card_id == "VAN_EX1_132":
                self._reveal_secret(def_seat, sec)
                self.deal_damage(f"hero_{opp_seat}", dmg, source_seat=def_seat, source_name="Eye for an Eye")
                break

    def _trigger_redemption(self, def_seat: str, dead_m: Minion, orig_pos: int) -> None:
        p = self.state.players[def_seat]
        if len(p.board) >= 7:
            return
        for sec in list(p.secrets):
            if sec.card_id == "VAN_EX1_136":
                self._reveal_secret(def_seat, sec)
                resummoned = self.summon_minion(def_seat, dead_m.card_id, pos=orig_pos)
                if resummoned and resummoned.max_health > 1:
                    resummoned.damage = resummoned.max_health - 1
                break

    def _trigger_secrets_on_minion_played(self, def_seat: str, summoned: Minion) -> None:
        p = self.state.players[def_seat]
        for sec in list(p.secrets):
            if sec.card_id == "VAN_EX1_609":  # Snipe
                self._reveal_secret(def_seat, sec)
                if summoned in self.state.players[summoned.owner].board:
                    self.deal_damage(summoned.uid, 4, source_seat=def_seat, source_name="Snipe")
            elif sec.card_id == "VAN_EX1_379":  # Repentance
                self._reveal_secret(def_seat, sec)
                if summoned in self.state.players[summoned.owner].board:
                    self.add_enchantment(summoned.uid, sec.card_id, "Repentance", set_hp=1)
            elif sec.card_id == "VAN_EX1_294":  # Mirror Entity
                if len(p.board) < 7:
                    self._reveal_secret(def_seat, sec)
                    clone = self.summon_minion(def_seat, summoned.card_id)
                    if clone:
                        self.copy_minion_into(summoned, clone)
                        clone.owner = def_seat
                        clone.summoned_this_turn = True
                        clone.attacks_this_turn = 0
        expansions.trigger_secrets_on_minion_played(self, def_seat, summoned)

    def _trigger_secrets_on_attack(self, def_seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
        p = self.state.players[def_seat]
        atk_seat = self.other_seat(def_seat)
        atk_minion = None if attacker_id.startswith("hero_") else self.find_minion(attacker_id)

        for sec in list(p.secrets):
            is_hero_target = target_id == f"hero_{def_seat}"
            if sec.card_id == "VAN_EX1_130":  # Noble Sacrifice
                if len(p.board) < 7:
                    self._reveal_secret(def_seat, sec)
                    defender = self.summon_minion(def_seat, "VAN_EX1_130a")
                    if defender:
                        target_id = defender.uid
                        continue
            elif sec.card_id == "VAN_EX1_533" and is_hero_target:  # Misdirection
                cands = [f"hero_{atk_seat}"]
                for s in ("p1", "p2"):
                    for bm in self.state.players[s].board:
                        if bm.uid != attacker_id:
                            cands.append(bm.uid)
                if cands:
                    self._reveal_secret(def_seat, sec)
                    target_id = self.rng.choice(cands)
                    continue
            elif sec.card_id == "VAN_EX1_610" and is_hero_target:  # Explosive Trap
                self._reveal_secret(def_seat, sec)
                opp = self.state.players[atk_seat]
                for tid in [f"hero_{atk_seat}"] + [m.uid for m in opp.board]:
                    self.deal_damage(tid, 2, source_seat=def_seat, source_name="Explosive Trap")
                self.resolve_deaths()
                if atk_minion and atk_minion not in opp.board:
                    return target_id, True
            elif sec.card_id == "VAN_EX1_289" and is_hero_target:  # Ice Barrier
                self._reveal_secret(def_seat, sec)
                p.hero.armor += 8
            elif sec.card_id == "VAN_EX1_594" and is_hero_target and atk_minion is not None:  # Vaporize
                self._reveal_secret(def_seat, sec)
                self.destroy_minion(atk_minion.uid)
                return target_id, True
            elif sec.card_id == "VAN_EX1_554" and not is_hero_target and len(p.board) < 7:  # Snake Trap
                self._reveal_secret(def_seat, sec)
                for _ in range(3):
                    self.summon_minion(def_seat, "VAN_EX1_554t")
            elif sec.card_id == "VAN_EX1_611" and atk_minion is not None:  # Freezing Trap
                self._reveal_secret(def_seat, sec)
                self.bounce_minion(atk_minion, cost_mod_delta=2)
                return target_id, True

        return expansions.trigger_secrets_on_attack(self, def_seat, attacker_id, target_id)

    # -----------------------------------------------------------------------
    # FAIR-PLAY SERIALIZATION & CLI FORMATTING
    # -----------------------------------------------------------------------

    def _serialize_minion(self, m: Minion, is_owner: bool) -> dict[str, Any]:
        cdef = get_card(m.card_id)
        can_atk = False
        if is_owner and self.state.active_seat == m.owner and self.state.phase == "PLAY":
            can_atk = len(self.get_legal_attack_targets(m.owner, m.uid)) > 0
        return {
            "uid": m.uid,
            "card_id": m.card_id,
            "name": m.name,
            "owner": m.owner,
            "card_class": cdef.card_class,
            "cost": cdef.cost,
            "attack": m.attack,
            "health": m.health,
            "max_health": m.max_health,
            "base_attack": m.base_attack,
            "base_health": m.base_health,
            "race": m.race,
            "rarity": cdef.rarity,
            "text": "" if m.silenced else cdef.text,
            "keywords": sorted(m.keywords),
            "silenced": m.silenced,
            "frozen": m.frozen,
            "damaged": m.damaged,
            "immune": m.immune_this_turn,
            "spell_damage": m.spell_damage,
            "can_attack": can_atk,
            "summoned_this_turn": m.summoned_this_turn,
            "attacks_this_turn": m.attacks_this_turn,
            "enchantments": [e.source_name for e in m.enchantments],
        }

    def _serialize_weapon(self, w: Optional[Weapon]) -> Optional[dict[str, Any]]:
        if not w:
            return None
        cdef = get_card(w.card_id)
        return {
            "uid": w.uid,
            "card_id": w.card_id,
            "name": w.name,
            "card_class": cdef.card_class,
            "cost": cdef.cost,
            "rarity": cdef.rarity,
            "mechanics": list(cdef.mechanics),
            "attack": w.total_attack,
            "durability": w.durability,
            "max_durability": w.max_durability,
            "windfury": w.windfury,
            "text": cdef.text,
        }

    def serialize_for_seat(self, seat: str) -> dict[str, Any]:
        opp_seat = self.other_seat(seat)
        me = self.state.players[seat]
        opp = self.state.players[opp_seat]
        combo_active = me.cards_played_this_turn > 0

        my_hand = []
        for idx, ci in enumerate(me.hand):
            cdef = get_card(ci.card_id)
            can_play, reason = (
                self.can_play_card(seat, idx)
                if self.state.phase == "PLAY" and self.state.active_seat == seat
                else (False, "")
            )
            choose_opts = []
            if cdef.id in CHOOSE_ONE_OPTIONS:
                for o_idx, opt in enumerate(CHOOSE_ONE_OPTIONS[cdef.id]):
                    vt = self.get_valid_targets(seat, opt.target_rule, is_spell_or_power=True)
                    choose_opts.append({
                        "index": o_idx,
                        "label": opt.label,
                        "description": opt.description,
                        "target_rule": opt.target_rule,
                        "valid_targets": vt,
                        "playable": opt.target_rule == "NONE" or len(vt) > 0,
                    })
                rule = "NONE"
                valid_targets = []
            else:
                rule = self.get_target_rule(cdef.id, None, combo_active, seat=seat, exclude_hand_uid=ci.uid)
                valid_targets = (
                    self.get_valid_targets(seat, rule, is_spell_or_power=(cdef.type == "SPELL"))
                    if can_play
                    else []
                )

            bonus_glow = cdef.has_mechanic("COMBO") and combo_active
            if cdef.id == "LOE_011" and self.has_no_duplicates_in_deck(seat):  # Reno Jackson
                bonus_glow = True
            elif cdef.id in ("BRM_004", "AT_116", "BRM_033", "AT_017", "BRM_034", "CFM_605") and self.has_dragon_in_hand(seat, exclude_uid=ci.uid):
                bonus_glow = True
            elif cdef.id == "GVG_004" and self.has_mech_on_board(seat):  # Goblin Blastmage
                bonus_glow = True
            elif cdef.id == "BRM_015" and me.hero.hp <= 12:  # Revenge
                bonus_glow = True

            my_hand.append({
                "index": idx,
                "uid": ci.uid,
                "card_id": cdef.id,
                "name": cdef.name,
                "card_class": cdef.card_class,
                "type": cdef.type,
                "rarity": cdef.rarity,
                "race": cdef.race,
                "base_cost": cdef.cost,
                "cost": self.get_card_cost(seat, ci),
                "attack": cdef.attack + ci.attack_mod if cdef.attack is not None else None,
                "health": cdef.health + ci.health_mod if cdef.health is not None else None,
                "durability": cdef.durability,
                "text": cdef.text,
                "mechanics": list(cdef.mechanics),
                "overload": cdef.overload,
                "can_play": can_play,
                "unplayable_reason": "" if can_play else reason,
                "target_rule": rule,
                "target_required": bool(valid_targets) and rule != "NONE",
                "valid_targets": valid_targets,
                "choose_options": choose_opts,
                "combo_glow": bonus_glow,
            })

        hp_card = get_card(me.hero.hero_power_id)
        opp_hp_card = get_card(opp.hero.hero_power_id)
        hp_ok, _ = self.can_use_hero_power(seat)
        hp_rule = self.get_hero_power_target_rule(seat)
        hp_targets = self.get_valid_targets(seat, hp_rule, is_spell_or_power=True) if hp_ok else []
        hp_cost = self.get_hero_power_cost(seat)
        opp_hp_cost = self.get_hero_power_cost(opp_seat)

        ser_weapon = self._serialize_weapon

        pending = None
        if self.state.pending_choice and self.state.pending_choice.seat == seat:
            pending = {
                "choice_type": self.state.pending_choice.choice_type,
                "source_card_id": self.state.pending_choice.source_card_id,
                "options": [
                    get_card(ci.card_id).to_dict() | {"uid": ci.uid}
                    for ci in self.state.pending_choice.options
                ],
            }

        nozdormu_active = any(
            not m.silenced and m.card_id == "VAN_EX1_560"
            for s in ("p1", "p2")
            for m in self.state.players[s].board
        )

        return {
            "game_id": self.state.game_id,
            "seq": self.state.cp_seq,
            "mode": self.state.mode,
            "deck_era": self.state.deck_era,
            "phase": self.state.phase,
            "viewer_seat": seat,
            "active_seat": self.state.active_seat,
            "your_turn": self.state.phase == "PLAY" and self.state.active_seat == seat,
            "turn_number": self.state.turn_number,
            "winner": self.state.winner,
            "nozdormu_active": nozdormu_active,
            "turn_started_at": self.state.turn_started_at,
            "pending_choice": pending,
            "waiting_for_opponent_choice": bool(
                self.state.pending_choice and self.state.pending_choice.seat != seat
            ),
            "last_emote": self.state.last_emote,
            "me": {
                "seat": seat,
                "name": me.name,
                "deck_name": me.deck_name,
                "trial": meta_effects.trial_view(me),
                "mulligan_done": me.mulligan_done,
                "mana": me.mana,
                "max_mana": me.max_mana,
                "overloaded": me.overloaded,
                "pending_overload": me.pending_overload,
                "deck_count": len(me.deck),
                "hand_count": len(me.hand),
                "fatigue": me.fatigue,
                "combo_active": combo_active,
                "cards_played_this_turn": me.cards_played_this_turn,
                "spell_damage": sum(m.spell_damage for m in me.board),
                "hero": {
                    "id": f"hero_{seat}",
                    "card_class": me.hero.card_class,
                    "name": me.hero.name,
                    "hp": me.hero.hp,
                    "max_hp": me.hero.max_hp,
                    "armor": me.hero.armor,
                    "attack": me.hero.attack,
                    "frozen": me.hero.frozen,
                    "immune": me.hero.immune_this_turn,
                    "is_jaraxxus": me.hero.is_jaraxxus,
                    "can_attack": len(self.get_legal_attack_targets(seat, f"hero_{seat}")) > 0,
                    "legal_attack_targets": self.get_legal_attack_targets(seat, f"hero_{seat}"),
                    "hero_power": {
                        "id": me.hero.hero_power_id,
                        "name": hp_card.name,
                        "cost": hp_cost,
                        "text": hp_card.text,
                        "used": me.hero.hero_power_used,
                        "can_use": hp_ok,
                        "target_rule": hp_rule,
                        "valid_targets": hp_targets,
                    },
                },
                "weapon": ser_weapon(me.weapon),
                "secrets": [{"uid": s.uid, "card_id": s.card_id, "name": s.name, "card_class": s.card_class} for s in me.secrets],
                "board": [
                    self._serialize_minion(m, is_owner=True) | {
                        "legal_attack_targets": self.get_legal_attack_targets(seat, m.uid)
                    }
                    for m in me.board
                ],
                "hand": my_hand,
            },
            # Opponent Fair-Play Fog of War: NEVER expose opp.hand cards, opp.deck order, or opp.secrets identities!
            "opponent": {
                "seat": opp_seat,
                "name": opp.name,
                "deck_name": opp.deck_name,
                "trial": meta_effects.trial_view(opp),
                "mulligan_done": opp.mulligan_done,
                "mana": opp.mana,
                "max_mana": opp.max_mana,
                "overloaded": opp.overloaded,
                "pending_overload": opp.pending_overload,
                "deck_count": len(opp.deck),
                "hand_count": len(opp.hand),
                "fatigue": opp.fatigue,
                "spell_damage": sum(m.spell_damage for m in opp.board),
                "hero": {
                    "id": f"hero_{opp_seat}",
                    "card_class": opp.hero.card_class,
                    "name": opp.hero.name,
                    "hp": opp.hero.hp,
                    "max_hp": opp.hero.max_hp,
                    "armor": opp.hero.armor,
                    "attack": opp.hero.attack,
                    "frozen": opp.hero.frozen,
                    "immune": opp.hero.immune_this_turn,
                    "is_jaraxxus": opp.hero.is_jaraxxus,
                    "hero_power": {
                        "id": opp.hero.hero_power_id,
                        "name": opp_hp_card.name,
                        "cost": opp_hp_cost,
                        "text": opp_hp_card.text,
                        "used": opp.hero.hero_power_used,
                    },
                },
                "weapon": ser_weapon(opp.weapon),
                "secrets": [{"uid": s.uid, "card_class": s.card_class} for s in opp.secrets],
                "board": [self._serialize_minion(m, is_owner=False) for m in opp.board],
            },
            "log": self.state.log[-40:],
        }
