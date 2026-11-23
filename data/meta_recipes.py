"""Expansion deck recipes, ordered by class and archetype.

Each line gives the class, original deck name, role, game plan, and core cards.
An exclamation mark after a card picks one copy even if two are legal.
"""

RECIPES = {
    "gvg": """
DRUID|Wildwood Combo|combo|Ramp early and finish with Force of Nature and Savage Roar.|Wild Growth;Druid of the Claw;Force of Nature;Savage Roar;Ancient of Lore;Shade of Naxxramas
DRUID|Ironroot Ramp|ramp|Accelerate into large Taunts and keep playing threats after they are cleared.|Wild Growth;Innervate;Ancient of War;Ironbark Protector;Cenarius;Sludge Belcher;Ancient of Lore
DRUID|Copper Grove|mech|Discount Mechs, then finish with Savage Roar when they stick.|Mechwarper;Clockwork Gnome;Cogmaster;Spider Tank;Piloted Shredder;Savage Roar
HUNTER|Highmane Midrange|beast|Win trades with Beasts, back them with Houndmaster, and finish with Kill Command.|Webspinner;Haunted Creeper;Animal Companion;Houndmaster;Savannah Highmane;Kill Command;Freezing Trap
HUNTER|Long Road Face|rush|Attack early and close with the bow, hero power, and burn.|Leper Gnome;Wolfrider;Explosive Trap;Eaglehorn Bow;Kill Command;Unleash the Hounds;Leeroy Jenkins
HUNTER|Pack Hunt|beast|Feed Scavenging Hyena through Beast trades and push damage with a Rhino turn.|Scavenging Hyena;Timber Wolf;River Crocolisk;Haunted Creeper;Houndmaster;Tundra Rhino;Savannah Highmane
MAGE|Brasswork Mage|mech|Open with discounted Mechs and let Blastmage and Fireball finish.|Clockwork Gnome;Mechwarper;Snowchugger;Goblin Blastmage;Piloted Shredder;Fireball;Dr. Boom
MAGE|Winterlock|freeze|Freeze the board and buy turns for Alexstrasza followed by burn.|Frostbolt;Ice Lance;Frost Nova;Ice Block;Blizzard;Alexstrasza;Fireball;Pyroblast!
MAGE|Echo Giants|control|Stabilize at low Health and repeat your Giants with Mirror of Embers.|Molten Giant;Sunfury Protector;Ice Block;Doomsayer;Antique Healbot;Faceless Manipulator;Mirror of Embers
PALADIN|Muster Midrange|board|Build Recruits and turn a surviving board into pressure with Banner Captain.|Shielded Minibot;Muster for Battle;Banner Captain;Knife Juggler;Truesilver Champion;Tirion Fordring
PALADIN|Silver Shield Control|control|Clear with Equality, heal, and close with Tirion or a late legendary.|Equality;Wild Pyromancer;Consecration;Guardian of Kings;Lay on Hands;Tirion Fordring;Ragnaros the Firelord
PALADIN|Gilt Edge Aggro|rush|Refill your cheap minion rush with Divine Favor and attack through blockers.|Divine Favor;Blessing of Might;Argent Squire;Shielded Minibot;Leper Gnome;Sword of Justice;Truesilver Champion
PRIEST|Lightbomb Control|control|Clear boards, borrow enemy minions, and win on resources.|Lightbomb;Auchenai Soulpriest;Circle of Healing;Cabal Shadow Priest;Thoughtsteal;Mind Control;Northshire Cleric
PRIEST|Ember Reliquary|death|Build a board that keeps producing bodies when traded or cleared.|Emberglass Cocoon;Haunted Creeper;Harvest Golem;Piloted Shredder;Power Word: Shield;Cairne Bloodhoof;Kel'Thuzad
PRIEST|Shadow Chapel|control|Upgrade your damage Hero Power and grind away threats before turning it on the hero.|Shadowform;Holy Fire;Antique Healbot;Auchenai Soulpriest;Circle of Healing;Doomsayer;Lightbomb
ROGUE|Pitchblade Combo|weapon|Sharpen a weapon with Oil, swing, then cash it in with Blade Flurry.|Pitchblade Oil;Deadly Poison;Blade Flurry;Preparation;Sap;Eviscerate;Sprint;Assassin's Blade!
ROGUE|Backstreet Tempo|board|Take the board with cheap combo cards, then finish with threats that survive trades.|Backstab;Defias Ringleader;Edwin VanCleef;SI:7 Agent;Eviscerate;Sap;Piloted Shredder
ROGUE|Gutter Gears|mech|Accelerate Mechs and grow them with reusable targeted buffs.|Clockwork Gnome;Mechwarper;Cogmaster;Spider Tank;Piloted Shredder;Master of Disguise;Cold Blood
SHAMAN|Thunder Tradewind|board|Trade up with Totems and weapons, then finish with a wide board or Al'Akir.|Flametongue Totem;Feral Spirit;Hex;Lightning Storm;Fire Elemental;Al'Akir the Windlord;Bloodlust!
SHAMAN|Copperbolt|mech|Land discounted Mechs, buff them with Powermace, and close with Crackle.|Mechwarper;Whirling Zap-o-matic;Powermace;Piloted Shredder;Cogmaster;Crackle;Rockbiter Weapon
SHAMAN|Second Thunder|death|Reuse high-value Deathrattles with Ancestral Spirit, then protect the returning board.|Ancestral Spirit;Emberglass Cocoon;Piloted Shredder;Sylvanas Windrunner;Cairne Bloodhoof;Kel'Thuzad;Hex
WARLOCK|Ashgate Demons|death|Sacrifice Lanternbound Herald to bring a heavy Demon into play early.|Lanternbound Herald;Ashgate Regent;Sense Demons;Doomguard;Void Terror;Emberglass Cocoon;Shadowflame
WARLOCK|Giants at the Gate|control|Use Life Tap to discount Giants, then protect them with Taunt.|Mountain Giant;Molten Giant;Twilight Drake;Sunfury Protector;Ancient Watcher;Hellfire;Lord Jaraxxus
WARLOCK|Back Alley Zoo|rush|Trade with cheap minions and keep attacking with a sticky board and Doomguard.|Flame Imp;Voidwalker;Haunted Creeper;Knife Juggler;Power Overwhelming;Doomguard;Imp-losion
WARRIOR|Iron Vault|control|Remove threats and build Armor until late-game threats or Grommash can finish.|Shield Slam;Shield Block;Death's Bite;Brawl;Shieldmaiden;Grommash Hellscream;Gorehowl;Ragnaros the Firelord
WARRIOR|Moonfang Combo|combo|Give Raging Worgen Charge, damage and buff it, then attack twice.|Raging Worgen;Charge;Inner Rage;Rampage;Faceless Manipulator!;Battle Rage;Acolyte of Pain;Fiery War Axe
WARRIOR|Axe Rush|weapon|Attack with weapons and Charge minions, then close with Mortal Strike.|Heroic Strike;Fiery War Axe;Arcanite Reaper;Kor'kron Elite;Mortal Strike;Upgrade!;Wolfrider
""",
    "tgt": """
DRUID|Grove Battlecry|combo|Ramp with Aspirant and finish after midrange chip damage with Force and Roar.|Darnassus Aspirant;Wild Growth;Living Roots;Force of Nature;Savage Roar;Ancient of Lore;Emperor Thaurissan
DRUID|Scrapwood Rush|rush|Pressure with small threats or an early Fel Reaver, then use Roar to finish.|Innervate;Living Roots;Darnassus Aspirant;Fel Reaver;Leper Gnome;Power of the Wild;Savage Roar
DRUID|Roots of Stone|ramp|Use mana acceleration to deploy high-health defenders before opposing threats mature.|Wild Growth;Darnassus Aspirant;Ancient of War;Druid of the Claw;Kel'Thuzad;Dr. Boom;Ironbark Protector
HUNTER|Highland Beastmaster|beast|Curve sticky Beasts into Houndmaster and Highmane, with Quick Shot for the last points.|Webspinner;Haunted Creeper;Houndmaster;Savannah Highmane;Quick Shot;Freezing Trap;Loatheb
HUNTER|Quickshot Pursuit|rush|Race with Charge, Quick Shot, Explosive Trap, and Steady Shot.|Leper Gnome;Wolfrider;Arcane Shot;Quick Shot;Explosive Trap;Eaglehorn Bow
HUNTER|Two-Speed Hunt|beast|Open with cheap threats and finish after Highmane survives early removal.|Gnomish Inventor!;Leper Gnome;Wolfrider;Quick Shot;Mad Scientist;Savannah Highmane;Kill Command;Houndmaster!
MAGE|Flamewake Spells|combo|Chain cheap spells with Flamewaker and use burn once the board has been cleared.|Flamewaker;Mana Wyrm;Arcane Blast;Unstable Portal;Sorcerer's Apprentice;Fireball;Mirror Entity
MAGE|First Snow|freeze|Stall behind Ice Block while drawing into Alexstrasza and discounted burn.|Frost Nova;Ice Block;Frostbolt;Ice Lance;Emperor Thaurissan;Alexstrasza;Fireball;Doomsayer
MAGE|Frost Gears|mech|Get Mechs out early and hold the board with Blastmage until Fireball is lethal.|Mechwarper;Snowchugger;Goblin Blastmage;Spider Tank;Piloted Shredder;Antique Healbot!;Fireball;Loatheb
PALADIN|Oathbox Paladin|secrets|Build a board and pull Secrets into play with Oathbox Marshal.|Oathbox Marshal;Noble Sacrifice;Redemption;Repentance;Eye for an Eye!;Secretkeeper;Shielded Minibot;Muster for Battle
PALADIN|Tournament Muster|board|Use Muster for Battle and Banner Captain to grow a board, backed by Tirion.|Muster for Battle;Banner Captain;Shielded Minibot;Truesilver Champion;Defender of Argus;Tirion Fordring;Consecration
PALADIN|Squire Rush|rush|Flood early, reload with Divine Favor, and finish through attack buffs.|Argent Squire;Divine Favor;Blessing of Might;Blessing of Kings;Shielded Minibot;Leper Gnome;Muster for Battle!
PRIEST|Twilight Dragons|dragon|Activate Dragons from hand and keep efficient bodies alive through combat.|Twilight Whelp;Wyrmrest Agent;Blackwing Technician;Twilight Guardian;Blackwing Corruptor;Azure Drake;Ysera
PRIEST|Justicar Control|control|Survive with bigger healing, exhaust threats with Lightbomb, and win on resources.|Justicar Trueheart;Lightbomb;Auchenai Soulpriest;Circle of Healing;Cabal Shadow Priest;Holy Nova;Deathlord
PRIEST|Cinder Vigil|death|Trade valuable minions and use Vigil of Cinders to return them.|Vigil of Cinders;Emberglass Cocoon;Injured Blademaster;Cairne Bloodhoof;Velen's Chosen;Sylvanas Windrunner;Kel'Thuzad
ROGUE|Tournament Oil|weapon|Clear blockers and turn a buffed blade into burst with the original Blade Flurry.|Pitchblade Oil;Blade Flurry;Deadly Poison;Preparation;Emperor Thaurissan;Sap;Eviscerate;Azure Drake
ROGUE|Spellknife Malygos|combo|Use Thaurissan to discount Malygos and direct damage into one swing turn.|Malygos;Emperor Thaurissan;Sinister Strike;Eviscerate;Preparation;Shiv;Gadgetzan Auctioneer!
ROGUE|Coldlight Mill|mill|Bounce Coldlight Oracle and shuffle copies to drive the opponent into fatigue.|Coldlight Oracle;Gang Up;Shadowstep;Youthful Brewmaster;Vanish;Deathlord;Antique Healbot
SHAMAN|Drumcrest Totems|totem|Keep Totems in play and turn them into win threats with Drumcrest Oracle.|Drumcrest Oracle;Totem Golem;Flametongue Totem;Mana Tide Totem;Feral Spirit;Hex;Bloodlust!
SHAMAN|Powermace Rush|mech|Use Powermace and discounted Mechs to build pressure, then finish with burn.|Powermace;Whirling Zap-o-matic;Mechwarper;Spider Tank;Piloted Shredder;Crackle;Fel Reaver
SHAMAN|Storm Flood|totem|Fill the board with Totems and sticky minions, then land a Bloodlust turn.|Bloodlust;Totem Golem;Feral Spirit;Haunted Creeper;Knife Juggler;Flametongue Totem;Totemic Might!
WARLOCK|Imp Court Zoo|rush|Win cheap trades with Imp Gang Boss and use Doomguard for the final hit.|Imp Gang Boss;Imp-losion;Flame Imp;Voidwalker;Power Overwhelming;Darkbomb;Doomguard
WARLOCK|Deep Hand|control|Tap into Giants and Drakes, defend with Taunts while they grind through answers.|Mountain Giant;Molten Giant;Twilight Drake;Sunfury Protector;Hellfire;Sludge Belcher;Lord Jaraxxus
WARLOCK|Rift Demons|death|Sacrifice a Herald to create an early big Demon; let the bodies that survive finish.|Lanternbound Herald;Sense Demons;Void Terror;Ashgate Regent;Doomguard;Emberglass Cocoon;Imp Gang Boss
WARRIOR|Cinderhall Combo|combo|Damage Brawlers to make bodies and grow Frothing Berserker for burst.|Cinderhall Brawler;Whirlwind;Death's Bite;Frothing Berserker;Warsong Commander;Inner Rage;Battle Rage;Emperor Thaurissan
WARRIOR|Tournament Bulwark|control|Ramp Armor with Justicar, then win with heavy threats or Grommash.|Justicar Trueheart;Shieldmaiden;Bash;Brawl;Death's Bite;Shield Slam;Grommash Hellscream
WARRIOR|Twilight Steel|dragon|Use weapons to establish tempo and follow with durable Dragons.|Hearthscale Vanguard;Fiery War Axe;Death's Bite;Twilight Guardian;Blackwing Corruptor;Azure Drake;Ysera;Grommash Hellscream
""",
    "old_gods": """
DRUID|Grove Swarm|token|Flood the board for Savage Roar or use Wayward Ash Idol after a long chain of spells.|Violet Teacher;Living Roots;Power of the Wild;Savage Roar;Fandral Staghelm;Swipe;Wayward Ash Idol
DRUID|Moonwood Beasts|beast|Build up Beast pressure, protect it with efficient removal, and finish with Roar.|Grovebound Prowler;Druid of the Claw;Jungle Panther;Stranglethorn Tiger;Living Roots;Savage Roar;Feral Rage
DRUID|Sigilwood Ramp|ramp|Accelerate into larger defenders while collecting Sigils for Lantern Colossus.|Wild Growth;Nourish;Sigil Page;Sigil Sworn;Lantern Colossus;Ancient of War;Fandral Staghelm
HUNTER|Beasts of the Wild|beast|Pressure with Highmane and close with Call of the Wild.|Quick Shot;Houndmaster;Savannah Highmane;Call of the Wild;Animal Companion;Kill Command;Freezing Trap
HUNTER|Pursuit and Pack|rush|Start with cheap attacks and follow with Highmane, heavier Beasts, and burn.|Quick Shot;Arcane Shot;Leper Gnome;Wolfrider;Kill Command;Savannah Highmane;Call of the Wild!
HUNTER|Bellkeeper Hunter|death|Trade Deathrattle minions and revive them with Keeper of the Last Bell.|Keeper of the Last Bell;Savannah Highmane;Emberglass Cocoon;Harvest Golem;Cairne Bloodhoof;Sylvanas Windrunner;Explosive Shot
MAGE|Flame Current|combo|Chain spells into Flamewaker and close with remaining burn.|Flamewaker;Arcane Blast;Mana Wyrm;Sorcerer's Apprentice;Arcane Missiles;Fireball;Arcane Intellect
MAGE|Frost Clock|freeze|Stall and draw until Alexstrasza puts the opponent within burn range.|Frostbolt;Ice Block;Frost Nova;Doomsayer;Emperor Thaurissan;Alexstrasza;Fireball;Ice Lance
MAGE|One of Each Frost|singleton|Use Reno to survive long enough to finish with freezes and burn.|Reno Jackson;Ice Block;Frost Nova;Blizzard;Alexstrasza;Fireball;Ice Lance;Pyroblast
PALADIN|Bellkeeper Paladin|death|Heal and clear until the Keeper can return Tirion and other Deathrattles.|Keeper of the Last Bell;Tirion Fordring;Equality;Wild Pyromancer;Lay on Hands;Sylvanas Windrunner;Emberglass Cocoon
PALADIN|Oathbox Survivors|secrets|Grow Secretkeeper and collect board advantage with Oathbox Marshal.|Oathbox Marshal;Noble Sacrifice;Repentance;Redemption;Eye for an Eye!;Secretkeeper;Keeper of Uldaman
PALADIN|Gilded Shields|rush|Use Divine Shields to keep minions alive through combat and push face damage.|Argent Squire;Argent Protector;Scarlet Crusader;Blood Knight;Blessing of Kings;Keeper of Uldaman;Argent Commander
PRIEST|Last Light Control|control|Resolve repeated sweeps and turn sustained healing and stolen threats into a win.|Auchenai Soulpriest;Circle of Healing;Entomb;Cabal Shadow Priest;Justicar Trueheart;Holy Fire;Thoughtsteal
PRIEST|Old Gods Dragons|dragon|Keep early Dragons alive and turn combat tempo into a late Dragon threat.|Twilight Whelp;Wyrmrest Agent;Twilight Guardian;Blackwing Corruptor;Azure Drake;Ysera;Entomb
PRIEST|Sigil Chapel|control|Stabilize with Light Acolytes and build toward Lantern Colossus damage.|Acolyte of Last Light;Sigil Page;Sigil Sworn;Lantern Colossus;Shadow Word: Death;Holy Nova;Entomb
ROGUE|Hidden Miracle|combo|Cycle with Auctioneer and finish with an Edwin, a buffed minion, or Leeroy.|Gadgetzan Auctioneer;Conceal;Cold Blood;Leeroy Jenkins;Edwin VanCleef;Preparation;Tomb Pillager;Eviscerate
ROGUE|Graveglass Bell|death|Copy Deathrattles with Graveglass Mimic, then revive several at once with the Keeper.|Graveglass Mimic;Keeper of the Last Bell;Emberglass Cocoon;Tomb Pillager;Cairne Bloodhoof;Sylvanas Windrunner;Loot Hoarder
ROGUE|Sigil Knives|control|Remove opposing threats with the Cutthroat and turn collected Sigils into burst.|Sigil Cutthroat;Sigil Page;Sigil Sworn;Lantern Colossus;Backstab;Sap;Assassinate
SHAMAN|Groundbreak Rush|rush|Push early Overload threats and finish with Doomhammer or spells.|Tunnel Trogg;Totem Golem;Flamewreathed Faceless;Lightning Bolt;Lava Burst;Doomhammer;Rockbiter Weapon
SHAMAN|Thunderbluff Midrange|totem|Build a durable board with Totems and cheap Taunts, then land Bloodlust.|Totem Golem;Drumcrest Oracle;Thing from Below;Flametongue Totem;Hex;Fire Elemental;Bloodlust
SHAMAN|Bell and Thunder|death|Use removal and healing to survive, then bring back Deathrattles for the finish.|Keeper of the Last Bell;Ancestral Spirit;Sylvanas Windrunner;Cairne Bloodhoof;Lightning Storm;Refreshment Vendor;Earth Elemental
WARLOCK|Swarm Pact|rush|Hold the early board with minions and finish with Doomguard or Leeroy.|Flame Imp;Imp Gang Boss;Dark Peddler;Knife Juggler;Power Overwhelming;Doomguard;Leeroy Jenkins
WARLOCK|Reno Sigils|singleton|Use the single-copy survival package and finish with Lantern Colossus.|Reno Jackson;Sigil Page;Sigil Sworn;Lantern Colossus;Siphon Soul;Hellfire;Refreshment Vendor;Lord Jaraxxus
WARLOCK|Reno Bellkeeper|singleton|Stabilize with Reno, trade Deathrattles, then revive them together.|Reno Jackson;Keeper of the Last Bell;Emberglass Cocoon;Cairne Bloodhoof;Sylvanas Windrunner;Hellfire;Siphon Soul
WARRIOR|Red Dragon Charge|dragon|Pressure with weapons and Charge, then close with larger Dragons.|Hearthscale Vanguard;Fiery War Axe;Blackwing Corruptor;Twilight Guardian;Azure Drake;Kor'kron Elite;Grommash Hellscream;Skyfire Drake
WARRIOR|Stonewatch Sigils|control|Gain Armor while collecting Sigils, then land a large Colossus turn.|Stonewatch Sentinel;Sigil Page;Sigil Sworn;Lantern Colossus;Shield Slam;Shield Block;Brawl
WARRIOR|Iron Resolve|control|Exhaust opposing threats with removal and Armor, then finish with late threats.|Justicar Trueheart;Brawl;Ravaging Ghoul;Shield Slam;Gorehowl;Grommash Hellscream;Ysera
""",
    "gadgetzan": """
DRUID|Greenwake Ramp|jade|Grow Jade Golems and use Jade Idol to keep replenishing threats.|Jade Idol;Jade Blossom;Jade Behemoth;Aya Blackpaw;Gadgetzan Auctioneer;Wild Growth;Fandral Staghelm
DRUID|Moonsong Combo|combo|Accelerate into Malygos, then multiply the damage of cheap spells.|Malygos;Innervate;Moonfire;Living Roots;Emperor Thaurissan;Nourish;Swipe
DRUID|Cocoon Swarm|token|Use Deathrattle tokens to survive clears, then attack with Savage Roar.|Emberglass Cocoon;Living Roots;Power of the Wild;Savage Roar;Soul of the Forest;Violet Teacher;Mark of the Wild
HUNTER|Emberfield Midrange|beast|Build a sticky Beast board and use Houndmaster and Kill Command to convert it.|Emberfield Stalker;Kindly Grandmother;Scavenging Hyena;Houndmaster;Kill Command;Savannah Highmane;Call of the Wild!
HUNTER|Hidden Hunt|secrets|Deploy cheap Secrets and trigger swings with Snarewright, Eaglehorn Bow, and Briar Ambush.|Snarewright;Briar Ambush;Freezing Trap;Snipe!;Explosive Trap;Eaglehorn Bow;Savannah Highmane;Secretkeeper
HUNTER|Dockside Face|rush|Keep the curve low and stack Bow, Steady Shot, and direct damage.|Wolfrider;Arcane Shot;Quick Shot;Eaglehorn Bow;Explosive Trap;Kill Command;Sir Finley Mrrgglton
MAGE|Brewer Reno Mage|singleton|Clear with single-copy tools, heal with Reno, and close with late spells and value.|Reno Jackson;Lantern Brewer;Hearthforge Warden;Firelands Portal;Fireball;Flamestrike;Ice Block;Alexstrasza
MAGE|Portal Tempo|combo|Make early spells count twice with Flamewaker, then use Firelands Portal and Fireball.|Mana Wyrm;Flamewaker;Sorcerer's Apprentice;Arcane Blast;Firelands Portal;Fireball;Arcane Intellect
MAGE|Closed Ice|freeze|Freeze minions until a burn turn becomes possible after Alexstrasza.|Frost Nova;Ice Block;Ice Lance;Frostbolt;Alexstrasza;Emperor Thaurissan;Fireball;Doomsayer;Pyroblast!
PALADIN|Tidal Return|control|Trade your Charge Murlocs and Warleaders, then use Anyfin to bring them back.|Anyfin Can Happen;Bluegill Warrior;Murloc Warleader;Equality;Wild Pyromancer;Solemn Vigil;Lay on Hands
PALADIN|Fast Murloc Paladin|murloc|Snowball tribal buffs and replenish the board with Marshfen Prowler.|Murloc Tidecaller;Murloc Tidehunter;Murloc Warleader;Bluegill Warrior;Marshfen Prowler;Divine Favor;Truesilver Champion
PALADIN|Brasscoat Handbuff|board|Buff cheap minions in hand and play bodies that win subsequent trades.|Brasscoat Outfitter;Argent Squire;Argent Protector;Divine Favor;Keeper of Uldaman;Truesilver Champion;Defender of Argus
PRIEST|Gadgetzan Dragons|dragon|Use efficient Dragon turns and Operative value to stay ahead.|Twilight Whelp;Wyrmrest Agent;Twilight Guardian;Blackwing Corruptor;Azure Drake;Drakonid Operative;Ysera
PRIEST|Reno Dragon Lantern|singleton|Recover with Reno and Brewer, then make the Dragons outlast opposing answers.|Reno Jackson;Lantern Brewer;Twilight Whelp;Wyrmrest Agent;Twilight Guardian;Drakonid Operative;Ysera;Entomb
PRIEST|Reno Velen Burst|singleton|Play a defensive Highlander game until Velen can amplify your remaining burn.|Reno Jackson;Lantern Brewer;Prophet Velen;Mind Blast;Holy Smite;Emperor Thaurissan;Auchenai Soulpriest;Entomb
ROGUE|Coin and Conceal|combo|Cycle cheaply with Auctioneer and conceal a growing threat for lethal next turn.|Gadgetzan Auctioneer;Preparation;Conceal;Questing Adventurer;Tomb Pillager;Edwin VanCleef;Cold Blood;Eviscerate
ROGUE|Dockside Knives|pirate|Get early Pirates and weapon hits through, then finish with damage spells.|Southsea Deckhand;Breakwater Runaway;Bloodsail Raider;Southsea Captain;Deadly Poison;Cold Blood;Eviscerate
ROGUE|Beneath the Docks|murloc|Play a Pirate opening and use the Prowler to replenish the board with Murlocs.|Breakwater Runaway;Southsea Deckhand;Marshfen Prowler;Murloc Warleader;Bluegill Warrior;Cold Blood;Backstab
SHAMAN|Burn the Harbor|rush|Use Overload minions and Pirate pressure, then end with Doomhammer or burn.|Tunnel Trogg;Totem Golem;Breakwater Runaway;Southsea Deckhand;Flamewreathed Faceless;Doomhammer;Lava Burst
SHAMAN|Midrange Greenwake|jade|Use Jade weapons and damage spells to fight for the board while Golems grow.|Greenwake Hatchet;Jade Breaker;Jade Spirit;Aya Blackpaw;Totem Golem;Thing from Below;Flametongue Totem;Maelstrom Portal
SHAMAN|Deep Greenwake|jade|Survive aggressive openings with clears before committing large Jade threats.|Greenwake Hatchet;Jade Breaker;Jade Spirit;Aya Blackpaw;Lightning Storm;Hex;Earth Elemental;Refreshment Vendor
WARLOCK|Reno Giants and Fire|singleton|Heal with Reno, then finish with Jaraxxus or a Leeroy and Faceless burst turn.|Reno Jackson;Lantern Brewer;Lord Jaraxxus;Leeroy Jenkins;Power Overwhelming;Faceless Manipulator;Emperor Thaurissan;Twisting Nether
WARLOCK|City Zoo|rush|Build the early board and use Charge or buffs to finish before Jades get big.|Dark Peddler;Flame Imp;Emberglass Cocoon;Power Overwhelming;Doomguard;Imp Gang Boss;Soulfire;Knife Juggler
WARLOCK|Marsh Zoo|murloc|Refill with Life Tap, then use tribal buffs to punish opponents for leaving a Murloc alive.|Murloc Tidecaller;Murloc Tidehunter;Murloc Warleader;Marshfen Prowler;Sea Giant;Flame Imp;Soulfire
WARRIOR|Pyreclaw Pirates|pirate|Chain weapon buffs and Pirate attacks to close with Charge or Mortal Strike.|Pyreclaw Corsair;Breakwater Runaway;Southsea Deckhand;Bloodsail Raider;Upgrade!;Fiery War Axe;Arcanite Reaper;Kor'kron Elite;Mortal Strike
WARRIOR|Harbor Dragons|dragon|Control tempo with weapons and Dragons, then land a late charge or large body.|Hearthscale Vanguard;Fiery War Axe;Pyreclaw Corsair;Blackwing Corruptor;Twilight Guardian;Azure Drake;Skyfire Drake;Grommash Hellscream
WARRIOR|Forged Fortress|control|Clear early pressure with Armor, then win through durable threats and attrition.|Shield Slam;Shield Block;Ravaging Ghoul;Brawl;Justicar Trueheart;Skyfire Drake;Gorehowl;Grommash Hellscream
""",
    "ungoro": """
DRUID|Mossling Rush|token|Flood with Mosslings and cheap minions, then make the board lethal with Roar.|Mossburst;Power of the Wild;Savage Roar;Argent Squire;Knife Juggler;Soul of the Forest;Violet Teacher
DRUID|Jade Through the Wilds|jade|Build Golems and use Jade Idol to preserve a late-game supply of threats.|Jade Idol;Jade Blossom;Jade Behemoth;Aya Blackpaw;Nourish;Fandral Staghelm;Gadgetzan Auctioneer
DRUID|Farwood Ramp|ramp|Build mana quickly and close with Skyfire Drake and Farwood Titan.|Farwood Titan;Skyfire Drake;Wild Growth;Nourish;Innervate;Ancient of War;Ironbark Protector
HUNTER|Wilds Beastmaster|beast|Curve Beasts into Houndmaster and Highmane to keep pressure after removal.|Emberfield Stalker;Kindly Grandmother;Houndmaster;Animal Companion;Savannah Highmane;Kill Command;Call of the Wild!
HUNTER|Low Trail Hunter|beast|Stay under the top-heavy lists and finish with cheaper Beasts and burn.|Timber Wolf;Scavenging Hyena;Emberfield Stalker;Kindly Grandmother;Unleash the Hounds;Kill Command;Houndmaster
HUNTER|Briar Face Hunter|secrets|Place cheap Secrets with Snarewright and race with a bow and Steady Shot.|Snarewright;Briar Ambush;Explosive Trap;Snipe!;Eaglehorn Bow;Secretkeeper;Arcane Shot;Kill Command
MAGE|Frostforge|freeze|Buy time with Ice Block and freezes until Alexstrasza enables burn.|Ice Block;Frost Nova;Blizzard;Doomsayer;Alexstrasza;Fireball;Frostbolt;Archmage Antonidas
MAGE|Spellvault Secrets|secrets|Use early Secrets and Kirin Tor Mage, then deploy a cheap Spellvault Engine.|Kirin Tor Mage;Spellvault Engine;Counterspell;Mirror Entity;Secretkeeper;Mana Wyrm;Fireball;Ethereal Arcanist!
MAGE|Hearthforge Burn|control|Finish with direct damage, or turn big spells into pressure with the Warden.|Hearthforge Warden;Firelands Portal;Fireball;Pyroblast;Mana Wyrm;Frostbolt;Ice Block;Polymorph
PALADIN|Marsh Midrange|murloc|Build a Murloc board and turn its survivors into lethal with Oathwall Captain.|Murloc Tidecaller;Marshfen Prowler;Murloc Warleader;Brinecrest Elder;Oathwall Captain;Bluegill Warrior;Truesilver Champion
PALADIN|Brinecrest Rush|murloc|Use cheap tribal pressure and make trades one-sided with Brinecrest Elder.|Brinecrest Elder;Murloc Tidecaller;Murloc Tidehunter;Murloc Warleader;Grimscale Oracle;Bluegill Warrior;Divine Favor;Argent Squire
PALADIN|Oathwall Control|control|Clear with Equality, then stabilize behind Taunts and finish with Tirion or big bodies.|Equality;Wild Pyromancer;Consecration;Oathwall Captain;Tirion Fordring;Guardian of Kings;Lay on Hands;Skyfire Drake
PRIEST|Wilds Dragon Chapel|dragon|Keep Dragon synergies active and gain enough board advantage to finish.|Drakonid Operative;Skyfire Drake;Faerie Dragon;Twilight Drake;Ysera;Northshire Cleric;Temple Enforcer
PRIEST|Silent Chamber|combo|Silence a cheap high-Health minion, then turn its Health into lethal Attack.|Chamber Initiate;Ancient Watcher;Silence;Mass Dispel;Divine Spirit;Inner Fire;Power Word: Shield;Northshire Cleric
PRIEST|Hearthforge Control|control|Survive with healing and removal, then create repeated threats from expensive spells.|Hearthforge Warden;Holy Nova;Holy Fire;Mind Control;Auchenai Soulpriest;Circle of Healing;Cabal Shadow Priest;Shadow Word: Death
ROGUE|Understudy Combo|trial|Replay a cheap minion to complete the Trial, then turn smaller bodies into 4/4s.|Understudy's Trial;Shadowstep;Youthful Brewmaster;Novice Engineer;Stonetusk Boar;Wisp;Preparation;Defias Ringleader
ROGUE|Street Miracle|combo|Cycle with Auctioneer and finish via Edwin or buffed minion burst.|Gadgetzan Auctioneer;Preparation;Edwin VanCleef;Cold Blood;Eviscerate;Questing Adventurer;Leeroy Jenkins
ROGUE|Jade Bell|jade|Grow Jades through Deathrattles and use the Keeper to bring back key pieces.|Keeper of the Last Bell;Stonehatch Cutpurse;Jade Spirit;Aya Blackpaw;Emberglass Cocoon;Shadowstep;Loot Hoarder
SHAMAN|Moss and Thunder|token|Finish with Bloodlust or transform the Maskmaker's Crew into three larger minions.|Maskmaker's Crew;Chrysalis Wave;Bloodlust;Maelstrom Portal;Flametongue Totem;Feral Spirit;Knife Juggler;Thing from Below;Mana Tide Totem!
SHAMAN|Wilds Jade Tide|jade|Control the early board and take over as each Jade summon gets larger.|Greenwake Hatchet;Jade Breaker;Jade Spirit;Aya Blackpaw;Thing from Below;Maelstrom Portal;Hex
SHAMAN|Stormcall Elementals|elemental|Chain Elementals over successive turns, then use Stormcall Elder as the finisher.|Spark Courier;Kiln Guard;Stormcall Elder;Fire Elemental;Earth Elemental;Lightning Storm;Feral Spirit
WARLOCK|Wilds Zoo|rush|Take the board with cheap minions and close with Doomguard or Soulfire.|Flame Imp;Voidwalker;Emberglass Cocoon;Knife Juggler;Doomguard;Soulfire;Dire Wolf Alpha
WARLOCK|Silt Murloc Warlock|murloc|Use Life Tap to keep the tribe stocked, then finish with tribal buffs or a Sea Giant.|Murloc Tidecaller;Murloc Tidehunter;Murloc Warleader;Marshfen Prowler;Sea Giant;Soulfire;Doomguard!
WARLOCK|Ashfall Control|control|Use Ashen Reckoning to reset the board and refill, then win with large Demons.|Ashen Reckoning;Lanternbound Herald;Ashgate Regent;Lord Jaraxxus;Siphon Soul;Shadowflame;Sense Demons;Hellfire
WARRIOR|Wilds Pirate Rush|pirate|Upgrade weapons and use Pirates to race, then close with Mortal Strike.|Breakwater Runaway;Pyreclaw Corsair;Southsea Deckhand;Upgrade!;Bloodsail Raider;Fiery War Axe;Mortal Strike;Arcanite Reaper
WARRIOR|Furnace Trial|trial|Survive behind Taunts, then use the Furnace Hammer reward to finish with repeatable damage.|Trial of Iron;Shieldbearer;Sen'jin Shieldmasta;Frostwolf Grunt;Skyfire Drake;Brawl;Shield Block;Sunwalker
WARRIOR|Farwood Bulwark|control|Clear and gain Armor until large threats or fatigue can finish.|Shield Slam;Shield Block;Brawl;Ravaging Ghoul;Skyfire Drake;Farwood Titan;Grommash Hellscream;Gorehowl
""",
}
