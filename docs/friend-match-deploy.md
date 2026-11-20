# Deploy friend matches to Cardgame

This rollout updates the web game at `https://orch.dev.sakualy.ai/cardgame/` and the existing
`cardgame` service. Keep the current HTTPS sign-in gate in front of the page, game API, and
WebSocket route. The proxy should keep forwarding `/cardgame/ws/` with WebSocket upgrades.
Keep the existing Android update exception for `/cardgame/api/app/*`. The game service needs one
Uvicorn worker and should remain bound to loopback. Both players will use the same site access,
which also grants access to the existing legacy games and shared decks.

## Install

1. From the workstation, publish the commit the rollout should use.

   ```bash
   git push origin HEAD:refs/heads/engine-events-and-client
   git rev-parse HEAD
   ```

2. On the server, go to the existing Cardgame checkout. Confirm that it is clean, that it is the
   working directory of the service, and that `/etc/systemd/system/cardgame.service.d/60-friend-matches.conf`
   is available for this rollout. Set `RELEASE` to the full commit hash from step 1. Run this in Bash.

   ```bash
   set -euo pipefail
   : "${RELEASE:?Set RELEASE to the verified commit hash}"
   test -z "$(git status --porcelain)"
   test -f frontend/dist/index.html
   unit=cardgame.service
   test "$(systemctl show -p WorkingDirectory --value "$unit")" = "$PWD"
   dropin=/etc/systemd/system/cardgame.service.d/60-friend-matches.conf
   sudo test ! -e "$dropin"
   git fetch origin
   git merge-base --is-ancestor "$RELEASE" origin/engine-events-and-client

   mkdir -p var
   backup=$(mktemp -d "$PWD/var/friend-rollout.XXXXXXXX")
   git rev-parse HEAD > "$backup/previous-commit"
   git symbolic-ref --quiet --short HEAD > "$backup/previous-branch" || true
   printf 'Rollout backup: %s\n' "$backup"

   git switch --detach "$RELEASE"
   npm --prefix frontend ci
   npm --prefix frontend run build -- --outDir "$backup/dist-new"
   test -f "$backup/dist-new/index.html"
   find frontend/dist -maxdepth 1 -type f -name '*.apk' -exec cp -p -t "$backup/dist-new" -- {} +

   sudo systemctl stop "$unit"
   if [ -d var/games ]; then cp -a var/games "$backup/games-before"; fi
   mv frontend/dist "$backup/dist-before"
   mv "$backup/dist-new" frontend/dist
   sudo install -d "$(dirname "$dropin")"
   sudo tee "$dropin" >/dev/null <<'SYSTEMD'
   [Service]
   Environment=CARDGAME_PUBLIC_ORIGIN=https://orch.dev.sakualy.ai
   Environment=CARDGAME_COOKIE_PATH=/cardgame/
   SYSTEMD
   sudo systemctl daemon-reload
   sudo systemctl start "$unit"
   sudo systemctl is-active "$unit"
   curl --fail --silent --show-error --retry 5 --retry-connrefused \
     http://127.0.0.1:8765/api/health
   ```

   Use the service's configured port if it differs from `8765`. Use the normal web build as
   shown here. `scripts/release.sh` also publishes an Android update.

3. In a private window, confirm that the game still asks you to sign in. After signing in, open
   `https://orch.dev.sakualy.ai/cardgame/api/health` and check for `"status":"ok"`. Then create
   a friend match in one browser profile and join from another. Check that each sees their own
   opening hand and can pass the turn. The browser network panel should show an upgrade on
   `/cardgame/ws/…`. If the upgrade fails, matches can still update through HTTP polling.

## Roll back

From the same checkout, set `backup` to the printed rollout backup directory. These commands
restore the previous build and its pre-rollout saves. They keep the new saves in the backup
because the old server cannot load friend matches. Matches played since the rollout will
therefore be absent while the old release is running.

```bash
set -euo pipefail
: "${backup:?Set backup to the printed rollout backup directory}"
test -d "$backup/dist-before"
test -s "$backup/previous-commit"
sudo systemctl stop cardgame.service
mv frontend/dist "$backup/dist-after"
mv "$backup/dist-before" frontend/dist
if [ -d var/games ]; then mv var/games "$backup/games-after"; fi
if [ -d "$backup/games-before" ]; then cp -a "$backup/games-before" var/games; fi
git switch --detach "$(cat "$backup/previous-commit")"
previous_branch=$(cat "$backup/previous-branch")
if [ -n "$previous_branch" ] &&
   [ "$(git rev-parse "$previous_branch")" = "$(cat "$backup/previous-commit")" ]; then
  git switch "$previous_branch"
fi
dropin=/etc/systemd/system/cardgame.service.d/60-friend-matches.conf
if sudo test -f "$dropin"; then sudo mv "$dropin" "$backup/60-friend-matches.conf"; fi
sudo systemctl daemon-reload
sudo systemctl start cardgame.service
sudo systemctl is-active cardgame.service
```
