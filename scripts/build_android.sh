#!/usr/bin/env bash
# Package a web build of the game as an Android app.
#
#   scripts/build_android.sh <web-build-dir> [--debug]
#
# <web-build-dir> is a finished web build (it must hold index.html), made so that
# it runs from the app's own files: VITE_BUNDLED=1, with the offline engine and
# the sound clips inside it. Card art is added from assets/art if the build has
# no art/ folder. The result is var/android/<name>-<version>.apk, signed for
# installing by hand (sideloading).
#
# --debug makes a build that can be inspected from a computer (chrome://inspect).
# It is signed with the same key, so either kind installs over the other.
#
# Name: frontend/src/branding.ts. Version: mobile/package.json ("version" and
# "android.versionCode": raise both for a new release). Signing key:
# var/android/release.keystore, made on the first run. KEEP THAT FILE: an app
# signed with another key cannot be installed over this one.
#
# Updates: the app is built with the update server's address
# (mobile/package.json, "android.updateUrl") and the token that server asks for
# (var/android/app-token, read by the build itself and never shown). KEEP THAT
# FILE too: installed apps carry the token, and a server with another one turns
# them away. Without the file the app is built without updates. The web build
# should carry its bundle version (bundle.json, written when it is built with
# VITE_BUNDLE_VERSION, as scripts/release.sh does), or the app will take the
# first bundle the server offers as newer than its own.
#
# Needs: JDK 17+, Node, Python 3 with Pillow, and an Android SDK with platform 36
# and build-tools 36 (ANDROID_HOME, default /opt/android-sdk).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE="$ROOT/mobile"
OUT="$ROOT/var/android"
MIN_FREE_MB="${MIN_FREE_MB:-3072}"   # stop rather than fill the disk
VARIANT=release

die() { echo "build_android: $*" >&2; exit 1; }
free_mb() { df --output=avail -BM "$ROOT" | tail -1 | tr -dc '0-9'; }
check_disk() { local f; f="$(free_mb)"; [ "$f" -ge "$MIN_FREE_MB" ] || die "only ${f} MB free on disk (need ${MIN_FREE_MB}); stopping before $1"; }

WEB=""
for arg in "$@"; do
  case "$arg" in
    --debug) VARIANT=debug ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) die "unknown option $arg" ;;
    *) WEB="$arg" ;;
  esac
done
[ -n "$WEB" ] || die "usage: scripts/build_android.sh <web-build-dir> [--debug]"
[ -f "$WEB/index.html" ] || die "$WEB has no index.html: build the web client first"
[ -f "$ROOT/var/android/app-token" ] || echo "!! no var/android/app-token: this app will be built WITHOUT updates"
[ -f "$WEB/bundle.json" ] || echo "!! $WEB has no bundle.json: build it with VITE_BUNDLE_VERSION (scripts/release.sh does) or the app cannot tell how new it is"
WEB="$(cd "$WEB" && pwd)"

export ANDROID_HOME="${ANDROID_HOME:-/opt/android-sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
[ -d "$ANDROID_HOME/platforms" ] || die "no Android SDK at $ANDROID_HOME (set ANDROID_HOME)"
BUILD_TOOLS="$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"

LABEL="$(sed -n "s/^ *title: *'\(.*\)', *$/\1/p" "$ROOT/frontend/src/branding.ts" | head -1)"
[ -n "$LABEL" ] || die "could not read the title from frontend/src/branding.ts"
VERSION="$(node -p "require('$MOBILE/package.json').version")"
SLUG="$(printf '%s' "$LABEL" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\{1,\}/-/g; s/^-//; s/-$//')"
echo "== $LABEL $VERSION ($VARIANT) from $WEB"

check_disk "starting"
mkdir -p "$OUT"

# --- signing key: made once, then kept ---------------------------------------
KEYSTORE="$OUT/release.keystore"
KEYPROPS="$OUT/keystore.properties"
if [ ! -f "$KEYSTORE" ] || [ ! -f "$KEYPROPS" ]; then
  [ ! -f "$KEYSTORE" ] || die "$KEYSTORE exists but $KEYPROPS is missing: not overwriting a key"
  echo "== making a signing key in $OUT (keep it)"
  (
    umask 077
    KS_PASS="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
    export KS_PASS
    keytool -genkeypair -keystore "$KEYSTORE" -storetype PKCS12 -alias cardgame \
      -keyalg RSA -keysize 2048 -validity 10950 -dname "CN=Card Game" \
      -storepass:env KS_PASS -keypass:env KS_PASS >/dev/null
    printf 'storeFile=%s\nstorePassword=%s\nkeyAlias=cardgame\nkeyPassword=%s\n' "$KEYSTORE" "$KS_PASS" "$KS_PASS" > "$KEYPROPS"
  )
  chmod 600 "$KEYSTORE" "$KEYPROPS"
fi

# --- the wrapper's own tools ---------------------------------------------------
if [ ! -d "$MOBILE/node_modules/@capacitor/cli" ]; then
  echo "== installing the wrapper's tools"
  (cd "$MOBILE" && npm install --no-audit --no-fund >/dev/null)
fi

# --- icons, from the same mark as the web icons ----------------------------------
(cd "$ROOT/scripts" && python3 make_android_icons.py)

# --- the web build goes into the app -------------------------------------------
echo "== copying the web build ($(du -sh "$WEB" | cut -f1))"
rm -rf "$MOBILE/www"
mkdir -p "$MOBILE/www"
cp -a "$WEB/." "$MOBILE/www/"
# Card art: online the server hands it out at art/, so a web build may not carry it. The app needs it inside.
if [ ! -d "$MOBILE/www/art" ] && [ -d "$ROOT/assets/art" ]; then
  echo "== the web build has no art/: adding the card art from assets/art ($(du -sh "$ROOT/assets/art" | cut -f1))"
  cp -a "$ROOT/assets/art" "$MOBILE/www/art"
fi
(cd "$MOBILE" && npx cap sync android >/dev/null)
check_disk "compiling"

# --- compile and sign -----------------------------------------------------------
TASK="assemble$(tr '[:lower:]' '[:upper:]' <<< "${VARIANT:0:1}")${VARIANT:1}"
(cd "$MOBILE/android" && ./gradlew --no-daemon --max-workers=2 --console=plain -q \
  -PappLabel="$LABEL" -PkeystoreProps="$KEYPROPS" "$TASK")

BUILT="$MOBILE/android/app/build/outputs/apk/$VARIANT/app-$VARIANT.apk"
[ -f "$BUILT" ] || die "the build finished but $BUILT is missing"
SUFFIX=""; [ "$VARIANT" = release ] || SUFFIX="-debug"
APK="$OUT/$SLUG-$VERSION$SUFFIX.apk"
cp "$BUILT" "$APK"

# --- check what came out ----------------------------------------------------------
"$BUILD_TOOLS/apksigner" verify "$APK" >/dev/null || die "the APK's signature does not verify"
"$BUILD_TOOLS/aapt2" dump badging "$APK" | grep -E "^(package|application-label:|minSdkVersion|targetSdkVersion|uses-permission: name='android)" || true
echo "== $APK ($(du -h "$APK" | cut -f1)), $(free_mb) MB free on disk"
