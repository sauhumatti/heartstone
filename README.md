# Hearthstone Classic (2014 Basic + Classic) — Local vs Antigravity

A complete local, offline Hearthstone Classic implementation featuring all **382 collectible cards** from the original Basic + Classic (`VANILLA`) launch set across all 9 hero classes, with **you playing in the browser** and **Antigravity playing against you via CLI or local REST API**.

## Quick Start

1. Start the local server (serves both the Web UI and API on port `8000`):
   ```bash
   ./play.sh
   ```
2. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
3. Create a match in **Antigravity (CLI / API)** mode (or test solo in **Practice Bot** mode).

## Playing with a friend

Open the hosted game in your browser, then choose **Play → Play a friend**. Pick a deck, create
an invitation, and send the link to your friend. They sign in through the same site gate, open
the link, and choose their own deck. Use separate browsers or browser profiles so each player
has their own seat. Both players can use **Resume match** in the browser they played in.

Friend matches are unrated. Each invitation is good for one guest. If the site sign-in drops the
invite link, sign in first and then open the link again. See [the server rollout guide](docs/friend-match-deploy.md)
for deployment and rollback.

## Playing Against Antigravity via CLI (`./hs`)

Antigravity acts as Player 2 (`p2`) using fair-play Fog of War (only public board state, opponent card counts, and opponent secret classes are visible):

```bash
./hs games                       # List active games
./hs wait                        # Block until it's Player 2's turn / mulligan
./hs status                      # Print current fair-play board & hand
./hs deck MAGE                   # Choose P2 deck (if match awaits CLI deck)
./hs mulligan 0 2                # Replace opening cards (or 'none')
./hs play 0 --pos 1 --target e0  # Play card 0 at slot 1 targeting e0
./hs play 2 --choose 1           # Play Choose One card (0 or 1)
./hs pick 0                      # Pick Tracking discovery option
./hs attack m0 enemy_hero        # Attack with m0 -> enemy_hero (or e0..e6)
./hs power --target e0           # Use Hero Power
./hs emote "Well Played"         # Send an emote bubble to the Web UI
./hs end                         # End turn
./hs concede                     # Concede match
```

## Running Tests

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
(cd frontend && npm run test:progress)   # the rules of rating, ranks and packs
```

## Antigravity as the opponent

Pick **Antigravity** in the lobby (or `p2_mode: "agent"` on `POST /api/games`) and the server asks the
Antigravity CLI (`agy`) for every decision of the other seat: its deck if you let it choose, its
opening hand, and each turn. The model is Gemini 4 Hydrogen; the lobby offers its four effort levels.

- The agent never runs anything. It gets the same fog-of-war table `./hs status` prints, plus the list
  of moves that are legal right now, and answers with `./hs`-style commands as structured output
  (`agy --output-format json --json-schema …`). The server checks every command against the rules.
- Indices mean the table as the agent saw it, so `play 0`, `play 1` works although the hand shifts.
  A rejected command is reported back and the agent is asked again; leaving out `end` gets it another look.
- If the CLI is missing, times out or keeps failing, the practice bot makes that one decision and the
  match goes on. The board shows that it happened.
- Only the table is sent out. The players' names are replaced by "You" and "Opponent".
- `AGENT_CMD`, `AGENT_MODEL`, `AGENT_TIMEOUT` change the CLI path, the default model and the wait per answer.

Code: `server/agent.py` (prompt, parsing, playing the answer) and `GameManager.kick_agent` (when it runs).
The old mode, where someone types `./hs` commands, is still there as **Command line**.

## Phones and installing

The match is drawn on a logical table that is scaled to the screen (`frontend/src/ui/layout.ts`):

- **Standard table** (1600×900) for desktops and tablets.
- **Wide table** (1600×740) for phones held sideways and other very wide screens: the heroes move
  beside the rows, nothing is letterboxed, and the hand shows whole cards.
- On a small screen, controls and text are enlarged (`--ui`), independently of the table.
- Touch has no hover: tap a card in your hand to read it large, and rest a finger on any minion,
  weapon or power to read that. A tap never plays a card. While a card is shown large, the next
  touch only puts it away, whatever it lands on; to play, drag the card onto the table (a real
  pull up out of the hand, not a slip of the finger) or press **Play** beside the enlarged card.
  A phone held upright is asked to turn.
- During a match on a touch device the page goes full screen, locks to landscape and keeps the screen
  awake, where the browser allows it. (In the Android app the wrapper does this instead.)

The game is an installable web app: `manifest.json` is written at build time from `branding.ts`,
the icons come from `scripts/make_icons.py`, and `public/sw.js` keeps the app shell, the card art and
the sound clips on the device. A match against the server still needs the server; to play with no
connection at all, see the next section. In Chrome, use **Install as an app** on the menu screen or
the browser's own install button. Installing needs HTTPS or localhost.

## Playing with no server

The game also runs entirely on the device: choose **This device** as the opponent (three levels).
When the game server cannot be reached it is the only choice offered, and the menus, the
collection and the deck builder work without the server too.

- **The same engine.** `engine/` is not ported: it runs unchanged as Python inside the browser
  ([Pyodide](https://pyodide.org), in a worker). The build packs `engine/` and `data/` as they are
  (`frontend/offline.plugin.ts`), so the device and the server cannot play by different rules.
- **`engine/local.py`** does on the device what `server/manager.py` and `server/app.py` do online:
  starts matches, answers every action with the same `{state, beats, agent}` reply, lets the
  opponent (`engine/ai.py`) make one decision at a time so each is shown as it happens, and saves a
  match so it survives closing the app. If the opponent fails, the practice bot finishes the move.
- **The seam** is `frontend/src/api.ts`: every request goes to the server or to the worker
  (`frontend/src/local/`), decided by the match's id (`local_…`). Nothing above it knows which.
- **Offline in the browser:** *Make available offline* on the menu stores the app, the runtime
  (about 14 MB), all card art and the sound clips on the device, about 26 MB in all; the service
  worker then serves them with no connection. Matches on the device are kept in IndexedDB (the
  newest eight). Decks built while the server is away are kept on the device.
- **The packaged app** is the same client built with everything inside it:

  ```bash
  cd frontend && npm run build:app        # -> frontend/dist-app (VITE_BUNDLED=1)
  ```

  It registers no service worker and talks to no server unless one is named at build time
  (`VITE_SERVER_URL=https://… npm run build:app`); a server that does not answer its own
  `api/health` (no connection, a login page in front of it) counts as not there.
- First start of the engine takes a few seconds (the lobby starts it ahead of time and shows how
  far it is); after that an action takes a few milliseconds.
- **The opponent** (`engine/ai.py`) knows no individual cards: it tries each legal move on a private
  copy of the game with the engine's own rules and scores the result. It sees only what a player in
  its seat would see (hidden cards are re-dealt at random in what it imagines). *Easy* looks one move
  ahead and overlooks things, *Normal* plans the whole turn, *Hard* also imagines the reply. How long
  it may think per decision is `ai.SUGGESTED_BUDGET_MS`. `scripts/ai_arena.py` plays the levels and
  the practice bot against each other and prints win rates and decision times.

```bash
PYTHONPATH=. python3 -m unittest tests.test_local   # the on-device host: whole matches, saves, nothing leaked
PYTHONPATH=. python3 -m unittest tests.test_ai      # the opponent: never fails, takes a win, reads nothing hidden
```

## Android

The Android app is the web client packaged with its files inside (a Capacitor wrapper in
`mobile/`), so it opens without a server. One command turns a finished web build into an APK that
can be installed by hand:

```bash
(cd frontend && npm run build:app)                  # the bundled web build -> frontend/dist-app
scripts/build_android.sh frontend/dist-app          # -> var/android/<name>-<version>.apk
scripts/build_android.sh frontend/dist-app --debug  # same, inspectable from chrome://inspect
```

(For a release, use `scripts/release.sh --apk` instead: see **Updates** below.)

- **The web build** must be one made to run from the app's own files (`npm run build:app`: the
  offline engine, the card art and the sound clips are inside it). A build with no `art/` folder
  gets the card art added from `assets/art`.
- **Name** comes from `frontend/src/branding.ts`, **version** from `mobile/package.json`
  (`version` and `android.versionCode`: raise both for a release), **icons** from the same mark as
  the web icons (`scripts/make_android_icons.py`). The app's id is `ai.sakualy.cardgame`.
- **Signing key**: `var/android/release.keystore`, made on the first build and not in git. Keep it:
  a build signed with another key cannot be installed over the app, only after uninstalling it.
- **What the wrapper adds** (`mobile/android/app/src/main/java/.../MainActivity.java`): landscape,
  full screen, drawing around a camera cutout, the screen kept on during a match, and the back
  button (it closes what is open, opens the match menu during a match, and asks before leaving
  from the main menu). The page side of that is `assets/app-shim.js`; the client can take either
  job over by defining `window.onAppBack` or calling `window.AndroidApp.keepAwake(...)` itself.
- **Needs** JDK 17, Node, Python with Pillow, and an Android SDK with platform 36 and build-tools 36
  (`ANDROID_HOME`, default `/opt/android-sdk`). Capacitor asks for Java 21; `mobile/android/build.gradle`
  compiles at 17 instead, which its sources allow. The build stops rather than leave less than 3 GB
  of disk free (`MIN_FREE_MB`).
- Playing online from the app needs the server's address built into the web build
  (`VITE_SERVER_URL=https://… npm run build:app`). The server already accepts requests from any
  origin, so nothing changes there; but a server behind a login page counts as not there, and the
  app then offers only **This device**. Without a named server the app is offline-only.

### Updates

An installed app updates itself. There are two kinds of update, and they are very different in
how often they happen:

- **A new bundle** (nearly every update): the game itself, which is the web build with its engine,
  art and sound. The app asks the server at every start, downloads a newer bundle (at once on Wi-Fi;
  on mobile data it asks first and says the size), checks its length and SHA-256, unpacks it into
  its own storage and shows it from the next start (or at once with **Restart now** on the menu,
  never during a match). A bundle that does not report a successful start within 30 seconds, or
  before the app is next started, is dropped for good and the app goes back to what it showed
  before. Installing a new APK forgets every download, so a new app starts from its own bundle.
- **A new app** (rare: only when something under `mobile/` changes). The menu says so and opens the
  APK's download in the phone's browser; it is installed by hand as before.

**Releasing** is one command, which releases the web version and the bundle together from the
same files, so the server and the devices always play by the same rules:

```bash
scripts/release.sh --notes "what changed"   # web version live + bundle offered to installed apps
scripts/release.sh --apk                    # the same, and a new APK (after raising the version in mobile/package.json)
```

It stamps the bundle with a version (the date and time, always later than the last), writes
`var/app-updates/manifest.json` in one move, keeps the last three bundles, restarts the game
server if the rules on disk are not the ones it is running (matches are kept), and puts the
current APK back at `frontend/dist/` for installing by hand.

| Piece | Where |
| --- | --- |
| What the page shows and asks for | `frontend/src/appUpdate.ts`, `frontend/src/ui/AppUpdate.tsx` (the menu's version line) |
| The rules: pending, on trial, rolled back | `mobile/android/app/src/main/java/.../update/UpdateState.java` |
| Asking, downloading, checking, unpacking | `.../update/UpdateFiles.java` |
| The Android side and the page's door to it (`AppUpdater`) | `.../update/Updater.java`, `.../update/UpdaterPlugin.java` |
| The server's routes | `server/updates.py`: `GET /api/app/latest`, `/api/app/bundle/<version>.zip`, `/api/app/shell/<code>.apk` |

- **The token.** The update routes answer only a caller that sends the app's token
  (`X-App-Token`); anyone else gets the same 404 as for a path that does not exist. The token is in
  `var/android/app-token` (made once, not in git) and is built into the app. **Keep that file with
  the signing key**: a server with another token turns every installed app away. The APK link is
  the one request a browser makes, so it carries a signature that is good for fifteen minutes
  instead of the token.
- **The site's login gate** has one exception for this: `/cardgame/api/app/*` (GET only) goes
  straight to the game server without the password, marked with an `X-App-Gate` header. The game
  server answers a request with that mark only on `/api/app/*`.
- **Kept matches and updates.** A match kept on the device remembers which rules it was saved
  under. After an update it is continued if it still loads; if it does not, or if it breaks in
  play, it is removed and the player is told, instead of the app being left stuck.
- The two plain-Java files have no Android in them and are run on this machine by
  `tests/test_updater_core.py` against the real routes of a test server (state rules, download,
  checksum, unpacking, archives that reach outside their folder). What that cannot cover is the
  Android side itself: see below.
- **Never run on a device from here:** storing the few values (`SharedPreferences`), handing the
  folder to Capacitor before the page loads, the reload after **Restart now** or a rollback, the
  metered-connection check, and opening the browser for a new APK.

## Rating, ranks and lanterns

Something to play for. All of it is in `frontend/src/progress/`, knows nothing about the cards,
and changes nothing in a match: it only looks at how matches end.

- **Rating.** Every finished match against an opponent moves the player's rating by the Elo
  rule: start 1000, never below 100, K 40 for the first ten matches and 24 after, a draw is half
  a win. The opponents have fixed ratings, spaced after `scripts/ai_arena.py` (the hard level
  beats the normal one about two times in three, the practice bot is a little stronger than the
  easy level): Easy 800, practice bot 875, Normal 1150, Antigravity 1200, Hard 1300. A match
  against the command line is not rated. If the other seat changes hands during a match (or the
  on-device opponent its level), the match counts as one against the weakest of them. A match is
  counted once, by its id, when its result screen is shown; conceding is a loss; a match that
  ended before the device had a profile is never counted.
- **Ranks.** Eight, by rating: Spark (below 850), Wick 850, Candle 950, Lamp 1050, Lantern 1150,
  Beacon 1250, Lighthouse 1350, Daystar 1450. A new player is in the middle of Candle. The menu
  and the result screen show the rank, the rating and how far the next rank is; the lobby says
  what a win or a loss against the chosen opponent is worth.
- **Lanterns (packs).** Three wins earn one (a win over Hard counts twice; what is left over is
  kept), and so does every rank reached for the first time. Lighting a lantern gives three
  different things to wear, each drawn tier first (Paper 60, Glass 30, Gilded 10 in a hundred),
  and at least one of them is new while anything is missing. A second copy turns into embers
  (5, 10, 25), and embers buy a missing thing of the player's choice (30, 60, 120).
- **Things to wear** are looks only: 11 card backs, 5 tables and 12 titles to find, besides the
  three everyone starts with. Packs never hold cards, and no card is locked. They are chosen on
  the **Rewards** screen (the rank strip on the menu opens it): the card back shows on the
  player's own deck, the table under the match, the title beside the player's name.
- **Where it is kept.** On the device, in the browser's `localStorage` under `lf_progress_v1`
  (the number is the shape of what is stored). Nothing is sent to the server, so a browser and
  an installed app each have their own profile, and clearing the site's data resets it.
- **Pictures.** `scripts/generate_cosmetics.py` asks an image model (OpenRouter's image
  endpoint) for each picture from a plain description, cuts it to shape and writes WebP into
  `frontend/src/progress/art/` (about 0.65 MB in all). They are imported by the build, so they are
  in the web version, in the offline copy and inside the installed app alike. The pictures as the
  model returned them are kept in `var/cosmetics-raw/`; `--pack-only` cuts them again.
- **Checked:** `npm run test:progress` (19 checks of the rules, no browser needed). The screens
  were looked at in a browser at phone and desktop size on a separate test copy; not on a real
  phone, and not inside the installed app.

## Sound

Two kinds of sound. The music and the light, tactile sounds (cards, clicks, bells, the turn) are
made in code when the game runs. Creature voices and the heavier combat and magic effects are short
recorded clips in `frontend/public/sfx/`, generated from written descriptions by a text-to-audio
model. (`assets/audio/` holds the earlier generated clips and is no longer used.)

| File | Job |
| --- | --- |
| `frontend/src/audio/dsp.ts` | the toolkit: noise, filters, struck objects, plucked strings, a sung tone, a room |
| `frontend/src/audio/bank.ts` | the sounds made in code: card and paper, wood, a bronze bell, glass, a frame drum, air |
| `scripts/make_sfx.py` | the recorded clips: each one's description, and the generating, trimming and levelling |
| `frontend/src/audio/creatures.ts` | which voice a piece has, from its type and size |
| `frontend/src/audio/cues.ts` | what each game moment sounds like (an arrangement of sounds and clips) |
| `frontend/src/audio/engine.ts` | the mixing desk: one shared room, separate effect and music levels, a limiter |
| `frontend/src/audio/music.ts` | the score, composed as it plays |
| `frontend/src/sound.ts` | what the rest of the app calls: `sfx.cue(name, opts)`, mood, levels |

- **Creature voices** come in seven kinds (small beast, large beast, dragon, fiend, construct, idol,
  and armored folk for everything else), each with a sound for arriving, attacking and dying, two
  takes of each. Bigger pieces sound louder and lower.
- **Clips load in the background** after the first tap and are kept on the device by the service
  worker. Until a clip has arrived, its cue plays a stand-in made in code, so nothing is ever silent.
- To remake clips: `OPENROUTER_API_KEY=... python3 scripts/make_sfx.py --redo dragon-enter fizzle`
  (edit the description in the script first if the sound should change), then build the frontend.
  The whole set costs about $0.35 to generate.

- **Cues** are placed left to right where they happen on the table, scale with what happened
  (damage dealt, the size of what landed), and never repeat exactly (several takes, slight pitch drift).
- **The score** is in D Dorian: a low string spreads the chords, a higher one plays a two-bar tune
  that comes back varied over each new chord, with a quiet organ-like bed, a bell and a frame drum.
  It follows the match: calmer on the opponent's turn, a pulse and darker colour as a hero nears
  defeat, silence before the victory or defeat cue.
- To hear the raw sounds outside the game: `cd frontend && node scripts/render-sounds.mjs /tmp/sounds`.
- To change a sound, edit its recipe in `bank.ts`; to change when or how loud it plays, `cues.ts`.

## How a move reaches the screen

The engine records every change as a structured event (`engine/game.py`, `emit`). Each public
action (play, attack, hero power, end turn, mulligan, a pick) closes one **beat**: the events it
caused plus a snapshot for each seat. Events are filtered per seat, so the other side's draws and
secrets stay hidden.

- Every action endpoint takes `since` (the last beat the caller has seen) and answers with
  `{state, beats, agent}`. `beats` is `null` when the server cannot replay from that position; the
  client then jumps straight to `state`. `agent` is the other seat's status when something plays it
  (who it is, whether it is thinking, whether it had to be stood in for).
- `GET /api/games/{id}/state?seat=p1&since=N` and the WebSocket `/ws/{id}/{seat}?since=N` work the
  same way. The practice bot's whole turn arrives as one beat per bot action.
- Matches are saved to `var/games/` after every action and reloaded when the server starts
  (`GAME_NO_PERSIST=1` turns this off).

The web client (`frontend/src`) plays beats back in order:

| File | Job |
| --- | --- |
| `api.ts` | where a match lives: the server, or the engine on this device (`local/`) |
| `game/useSession.ts` | follows a match, beat queue, playback loop |
| `game/reduce.ts` | folds one event into the displayed state |
| `game/director.ts` | what each event looks like (lunge, bolt, damage number, death…) |
| `game/fx.ts` | low-level effects and the slide-into-place (FLIP) helper |
| `ui/Board.tsx` | the table, drag to play, drag to attack, overlays |
| `ui/pieces.tsx` | card face, card back, board minion, stat badges |
| `branding.ts` | the game's name (a working title: change it here) |

The table is laid out at 1600×900 and scaled to the window. All URLs are relative, so the build
also works behind a sub-path (a packaged build may name its server with `VITE_SERVER_URL`).

`tests/test_events.py` plays every collectible card and 81 bot matches and checks that replaying a
beat's events on the previous snapshot gives the next one, so a missing event fails the suite.
