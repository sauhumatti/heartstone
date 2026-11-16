from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Enchantment:
    uid: str
    source_card_id: str
    source_name: str
    atk: int = 0
    hp: int = 0
    set_atk: Optional[int] = None
    set_hp: Optional[int] = None
    add_keywords: set[str] = field(default_factory=set)
    remove_keywords: set[str] = field(default_factory=set)
    spell_damage: int = 0
    temp_until_eot: bool = False
    temp_owner_revert: Optional[str] = None
    destroy_at_eot: bool = False
    destroy_at_owner_sot: Optional[str] = None
    extra_deathrattle: Optional[str] = None  # "TREANT" | "RESUMMON"
    blessing_of_wisdom_owner: Optional[str] = None

    def clone(self) -> "Enchantment":
        return Enchantment(
            uid=self.uid,
            source_card_id=self.source_card_id,
            source_name=self.source_name,
            atk=self.atk,
            hp=self.hp,
            set_atk=self.set_atk,
            set_hp=self.set_hp,
            add_keywords=set(self.add_keywords),
            remove_keywords=set(self.remove_keywords),
            spell_damage=self.spell_damage,
            temp_until_eot=self.temp_until_eot,
            temp_owner_revert=self.temp_owner_revert,
            destroy_at_eot=self.destroy_at_eot,
            destroy_at_owner_sot=self.destroy_at_owner_sot,
            extra_deathrattle=self.extra_deathrattle,
            blessing_of_wisdom_owner=self.blessing_of_wisdom_owner,
        )


@dataclass
class Minion:
    uid: str
    card_id: str
    owner: str
    name: str
    base_attack: int
    base_health: int
    damage: int = 0
    race: Optional[str] = None
    base_keywords: set[str] = field(default_factory=set)
    base_spell_damage: int = 0
    silenced: bool = False
    frozen: bool = False
    freeze_until_eot_of: Optional[str] = None
    immune_this_turn: bool = False
    stealth_until_sot_of: Optional[str] = None
    summoned_this_turn: bool = True
    attacks_this_turn: int = 0
    enchantments: list[Enchantment] = field(default_factory=list)
    # Recomputed dynamically by recompute_auras()
    attack: int = 0
    max_health: int = 0
    keywords: set[str] = field(default_factory=set)
    spell_damage: int = 0
    aura_atk_bonus: int = 0
    aura_hp_bonus: int = 0

    @property
    def health(self) -> int:
        return self.max_health - self.damage

    @property
    def damaged(self) -> bool:
        return self.damage > 0

    @property
    def enraged(self) -> bool:
        return self.damage > 0 and not self.silenced

    def has_keyword(self, kw: str) -> bool:
        return kw in self.keywords

    def max_attacks(self) -> int:
        return 2 if "WINDFURY" in self.keywords else 1


@dataclass
class Weapon:
    uid: str
    card_id: str
    name: str
    base_attack: int
    durability: int
    max_durability: int
    attack_bonus: int = 0
    aura_attack_bonus: int = 0
    windfury: bool = False

    @property
    def total_attack(self) -> int:
        return max(0, self.base_attack + self.attack_bonus + self.aura_attack_bonus)


@dataclass
class CardInstance:
    uid: str
    card_id: str
    cost_mod: int = 0


@dataclass
class SecretInstance:
    uid: str
    card_id: str
    card_class: str
    name: str


@dataclass
class Hero:
    card_class: str
    name: str
    hp: int = 30
    max_hp: int = 30
    armor: int = 0
    temp_attack: int = 0
    attack: int = 0
    attacks_this_turn: int = 0
    frozen: bool = False
    freeze_until_eot_of: Optional[str] = None
    immune_this_turn: bool = False
    hero_power_id: str = ""
    hero_power_used: bool = False
    shadowform_level: int = 0
    is_jaraxxus: bool = False


@dataclass
class PlayerState:
    seat: str
    name: str
    hero: Hero
    deck: list[CardInstance] = field(default_factory=list)
    hand: list[CardInstance] = field(default_factory=list)
    board: list[Minion] = field(default_factory=list)
    weapon: Optional[Weapon] = None
    secrets: list[SecretInstance] = field(default_factory=list)
    mana: int = 0
    max_mana: int = 0
    overloaded: int = 0
    pending_overload: int = 0
    fatigue: int = 0
    cards_played_this_turn: int = 0
    minions_played_this_turn: int = 0
    mulligan_done: bool = False
    next_secret_free: bool = False
    next_spell_cost_mod: int = 0
    enemy_spells_free_this_turn: bool = False
    enemy_spells_free_next_turn: bool = False
    commanding_shout_active: bool = False
    headcrack_return_eot: bool = False
    deck_name: str = ""


@dataclass
class PendingChoice:
    seat: str
    choice_type: str  # "TRACKING"
    source_card_id: str
    options: list[CardInstance] = field(default_factory=list)
    discard_others: list[CardInstance] = field(default_factory=list)


@dataclass
class GameState:
    game_id: str
    mode: str  # "cli_vs_human" | "bot_vs_human"
    phase: str  # "WAITING_FOR_P2_DECK" | "MULLIGAN" | "PLAY" | "GAME_OVER"
    turn_number: int = 0
    active_seat: str = "p1"
    first_seat: str = "p1"
    winner: Optional[str] = None
    players: dict[str, PlayerState] = field(default_factory=dict)
    pending_choice: Optional[PendingChoice] = None
    log: list[dict[str, Any]] = field(default_factory=list)
    last_emote: Optional[dict[str, Any]] = None
    turn_started_at: float = 0.0
    created_at: float = 0.0
    next_uid: int = 1
    rng_seed: Optional[int] = None
