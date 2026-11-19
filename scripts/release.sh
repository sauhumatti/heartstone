#!/usr/bin/env bash
# Release the game: the web version on the server and the update for installed
# apps, in one go, from the same files.
#
#   scripts/release.sh [--notes "what changed"] [--apk] [--no-restart]
#
# What it does, in order:
#   1. builds the web version into frontend/dist (what the server hands out);
#   2. builds the same game as a bundle for installed apps (frontend/dist-app),
#      stamps it with a version (date and time, always later than the last one),
#      zips it into var/app-updates/ and writes the manifest the apps ask for.
#      Apps pick it up on their own: no new APK is needed for this;
#   3. with --apk, also builds a new APK (scripts/build_android.sh) and offers
#      it to installed apps as a new app version. Do this only when something
#      under mobile/ changed, and raise "version" and "android.versionCode" in
#      mobile/package.json first. If the bundle needs that new app to run, also
#      set "android.bundleNeedsShell" to its versionCode;
#   4. restarts the game server if the rules on disk (engine/, data/) are not
#      the ones it is running, so the server and the devices play by the same
#      rules. Matches in progress are kept. --no-restart leaves it alone;
#   5. keeps the last three bundles, and puts the current APK back into
#      frontend/dist for installing by hand (the web build empties that folder).
#
# The app's token (var/android/app-token) and signing key
# (var/android/release.keystore) are read where needed and never shown.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPD="$ROOT/var/app-updates"
AND="$ROOT/var/android"
SERVER="${CARDGAME_LOCAL_URL:-http://127.0.0.1:8765}"
SERVICE="${CARDGAME_SERVICE:-cardgame}"
KEEP=3
NOTES=""
WITH_APK=0
RESTART=1

die() { echo "release: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --notes) NOTES="${2:-}"; shift 2 ;;
    --apk) WITH_APK=1; shift ;;
    --no-restart) RESTART=0; shift ;;
    -h|--help) sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option $1" ;;
  esac
done

FREE_MB="$(df --output=avail -BM "$ROOT" | tail -1 | tr -dc '0-9')"
[ "$FREE_MB" -ge 2048 ] || die "only ${FREE_MB} MB free on disk; stopping"
mkdir -p "$UPD"

# --- the bundle's version: now, and never the same or earlier than the last one -------
LAST="$(python3 - "$UPD/manifest.json" <<'PY'
import json, sys
try:
    v = str(json.load(open(sys.argv[1])).get("bundle", {}).get("version", ""))
    print(v if v.isdigit() else "")
except Exception:
    print("")
PY
)"
VERSION="$(date -u +%Y%m%d%H%M)"
if [ -n "$LAST" ] && [ "$VERSION" -le "$LAST" ]; then VERSION="$((LAST + 1))"; fi
echo "== release $VERSION (last: ${LAST:-none})"

# --- 1. the web version -------------------------------------------------------------------
echo "== building the web version"
(cd "$ROOT/frontend" && npm run build >/dev/null)
[ -f "$ROOT/frontend/dist/index.html" ] || die "the web build left no index.html"

# --- 2. the same game as a bundle for installed apps -----------------------------------------
echo "== building the bundle for installed apps"
(cd "$ROOT/frontend" && VITE_BUNDLE_VERSION="$VERSION" npm run build:app >/dev/null)
APP="$ROOT/frontend/dist-app"
grep -q "\"$VERSION\"" "$APP/bundle.json" 2>/dev/null || die "the bundle is not stamped with its version (bundle.json)"

# --- 3. a new APK, when asked for ---------------------------------------------------------------
if [ "$WITH_APK" = 1 ]; then
  echo "== building the APK"
  "$ROOT/scripts/build_android.sh" "$APP"
fi

# --- zip, manifest, prune: all at once, by one program, the manifest last and in one move ------
python3 - "$ROOT" "$VERSION" "$NOTES" "$KEEP" <<'PY'
import hashlib, json, os, re, shutil, sys, time, zipfile
from pathlib import Path

root, version, notes, keep = Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4])
upd, android, app = root / "var" / "app-updates", root / "var" / "android", root / "frontend" / "dist-app"
mobile = json.loads((root / "mobile" / "package.json").read_text())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# the bundle: every file of the build, none hidden, nothing that is not part of the game
name = f"bundle-{version}.zip"
part = upd / (name + ".part")
count = 0
with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for path in sorted(app.rglob("*")):
        rel = path.relative_to(app).as_posix()
        if not path.is_file() or any(piece.startswith(".") for piece in rel.split("/")) or rel.endswith((".apk", ".map")):
            continue
        # art, sound and the runtime are compressed already; storing them as they are keeps unpacking quick
        stored = rel.endswith((".webp", ".mp3", ".png", ".woff2", ".zip"))
        z.write(path, rel, compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
        count += 1
with zipfile.ZipFile(part) as z:
    assert z.testzip() is None and "index.html" in z.namelist() and "bundle.json" in z.namelist()
os.replace(part, upd / name)
bundle = {
    "version": version,
    "file": name,
    "sha256": sha256(upd / name),
    "size": (upd / name).stat().st_size,
    "minShell": int(mobile.get("android", {}).get("bundleNeedsShell") or 1),
}
print(f"== bundle {name}: {count} files, {bundle['size'] / 1e6:.1f} MB")

# the app: the APK of the version mobile/package.json names, if it has been built
title = re.search(r"title:\s*'([^']*)'", (root / "frontend" / "src" / "branding.ts").read_text()).group(1)
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
apk = android / f"{slug}-{mobile['version']}.apk"
old = {}
try:
    old = json.loads((upd / "manifest.json").read_text())
except Exception:
    pass
shell = old.get("shell") if isinstance(old.get("shell"), dict) else None
if apk.is_file():
    shutil.copy2(apk, upd / (apk.name + ".part"))
    os.replace(upd / (apk.name + ".part"), upd / apk.name)
    shell = {
        "versionCode": int(mobile["android"]["versionCode"]),
        "versionName": mobile["version"],
        "file": apk.name,
        "sha256": sha256(upd / apk.name),
        "size": (upd / apk.name).stat().st_size,
    }
    print(f"== app {apk.name}: version code {shell['versionCode']}, {shell['size'] / 1e6:.1f} MB")
else:
    print(f"== no APK for app version {mobile['version']} in var/android: the manifest keeps the app it had")

manifest = {"bundle": bundle, "notes": notes, "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
if shell:
    manifest["shell"] = shell
tmp = upd / "manifest.json.part"
tmp.write_text(json.dumps(manifest, indent=2) + "\n")
os.replace(tmp, upd / "manifest.json")  # from this moment the apps see the new release

# old files: the last few bundles stay, and only the APK the manifest names
bundles = sorted(upd.glob("bundle-*.zip"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
for stale in bundles[:-keep]:
    stale.unlink()
for other in list(upd.glob("*.apk")) + list(upd.glob("*.part")):
    if not shell or other.name != shell["file"]:
        other.unlink()

# for installing by hand (behind the site's password): the web build emptied this folder
if apk.is_file():
    shutil.copy2(apk, root / "frontend" / "dist" / apk.name)
PY

# --- 4. the server must run the rules that were just packed ---------------------------------------
WANT="$(cd "$ROOT" && PYTHONPATH=. python3 -c 'from engine import local; print(local.engine_tag())')"
RUNNING="$(curl -s --max-time 5 "$SERVER/api/health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("engine",""))' 2>/dev/null || true)"
if [ "$WANT" = "$RUNNING" ]; then
  echo "== the server already runs these rules"
elif [ "$RESTART" = 1 ]; then
  echo "== the server runs other rules than the ones on disk: restarting it (matches are kept)"
  systemctl restart "$SERVICE"
  for _ in $(seq 1 30); do
    sleep 1
    RUNNING="$(curl -s --max-time 2 "$SERVER/api/health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("engine",""))' 2>/dev/null || true)"
    [ "$WANT" = "$RUNNING" ] && break
  done
  [ "$WANT" = "$RUNNING" ] || die "the server did not come back with the new rules"
else
  echo "!! the server runs other rules than the ones on disk (--no-restart): restart '$SERVICE' before anyone plays online"
fi

# --- check what the apps will be told ------------------------------------------------------------
if [ -f "$AND/app-token" ]; then
  # asked the way an app asks, with the token read from its file (never put on a command line)
  SERVED="$(python3 - "$SERVER" "$AND/app-token" <<'PY' 2>/dev/null || true
import json, sys, urllib.request
req = urllib.request.Request(sys.argv[1] + "/api/app/latest", headers={"X-App-Token": open(sys.argv[2]).read().strip()})
print(json.load(urllib.request.urlopen(req, timeout=5)).get("bundle", {}).get("version", ""))
PY
)"
  [ "$SERVED" = "$VERSION" ] || die "the server does not offer bundle $VERSION to apps (it says '${SERVED:-nothing}')"
  echo "== released: the web version is live and apps are offered bundle $VERSION"
else
  echo "== released the web version. No var/android/app-token: installed apps are not offered updates"
fi
