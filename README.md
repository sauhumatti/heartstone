# Hearthstone Classic (2014 Basic + Classic) — Local vs Antigravity

A complete local, offline Hearthstone Classic implementation featuring all **382 collectible cards** from the original Basic + Classic (`VANILLA`) launch set across all 9 hero classes, with **you playing in the browser** and **Antigravity playing against you via CLI or local REST API**.

## Quick Start

1. Start the local server (serves both the Web UI and API on port `8000`):
   ```bash
   ./play.sh
   ```
2. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
3. Create a match in **Antigravity (CLI / API)** mode (or test solo in **Practice Bot** mode).

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
```
