#!/bin/sh
# "Camset Editor.app" and a .dmg in target/dist, from a release build, with tools macOS ships
# (sips, iconutil, hdiutil, codesign). Run from editor/:   sh packaging/build_macos_app.sh
#
# The camera definitions (definitions/: one file per model and firmware, and the sample file a definition
# names) go into the app's Resources before it is signed, which seals them: the editor only reads them there,
# and keeps a person's own definitions in its settings folder (docs/decisions/0019). No file types are claimed (.DAT is used by many apps). The camera helper is not included: it is
# built against the Sony Camera Remote SDK, whose files may not be published; someone who has the SDK
# builds it and picks it in Settings. The signature is ad hoc (runs on the Mac that built it);
# another Mac needs a Developer ID signature and notarization, or right-click > Open the first time.
# The app and the disk image carry the project's LICENSE and, when cargo about has written it, the
# third-party licences page (the crates, and the fonts egui builds in). The disk image also holds a shortcut
# to /Applications, so the person installs by dragging Camset Editor onto it, the macOS way.
#
# CAMSET_INTERNAL=1 makes the internal build: the help files in ../private/help (the camera's own help text,
# Sony's, never published; docs/decisions/0018) and, when it is built, the camera helper with the SDK's
# libraries go into the app. It is built into target/dist-internal (never target/dist, where the public
# packages are), the .dmg is named -internal, and it is refused in CI. Never publish it. Without it the app
# carries only the definition's own help.
set -eu
IDENTIFIER="${CAMSET_BUNDLE_ID:-app.camset.editor}"
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)
# the line macOS's About panel shows under the version: the project's licence's copyright holders
COPYRIGHT=$(sed -n 's/^Copyright (c) //p' ../LICENSE | head -1)
# it goes into a sed replacement and the plist's XML as it is: none, or one with & | \ < >, stops the build
case "$COPYRIGHT" in
  ""|*[\&\|\\\<\>]*) echo "LICENSE needs a \"Copyright (c) ...\" line without & | \\ < or >: the app's Info.plist takes its words" >&2; exit 1 ;;
esac
ARCH=$(uname -m)
INTERNAL=""
if [ "${CAMSET_INTERNAL:-}" = 1 ]; then
  if [ -n "${CI:-}" ]; then echo "CAMSET_INTERNAL=1 is refused in CI: the internal build is never published" >&2; exit 1; fi
  ls ../private/help/help_*.json >/dev/null 2>&1 || { echo "CAMSET_INTERNAL=1, but ../private/help has no help file" >&2; exit 1; }
  INTERNAL=1
fi
cargo build --release
OUT=target/dist
STAGE=target/dmg
KIND=""
if [ -n "$INTERNAL" ]; then OUT=target/dist-internal; STAGE=target/dmg-internal; KIND="-internal"; fi
APP="$OUT/Camset Editor.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp target/release/camset_editor "$APP/Contents/MacOS/"
ICONSET=target/AppIcon.iconset
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s assets/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2))
  sips -z $d $d assets/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
# the shipped camera definitions, read-only inside the app: copied before codesign seals Contents/Resources
ls definitions/*.json >/dev/null 2>&1 || { echo "definitions/ holds no camera definition" >&2; exit 1; }
mkdir -p "$APP/Contents/Resources/definitions"
cp definitions/* "$APP/Contents/Resources/definitions/"
if [ -n "$INTERNAL" ]; then
  mkdir -p "$APP/Contents/Resources/help"
  cp ../private/help/help_*.json "$APP/Contents/Resources/help/"
  if [ -f ../kit/probe/build/camset_probe ]; then
    # the camera helper and the SDK core beside the editor; the SDK's adapters (USB, IP) are looked up
    # in the bundle's own Contents/Frameworks/CrAdapter once the helper runs inside the app
    cp ../kit/probe/build/camset_probe "$APP/Contents/MacOS/"
    cp ../kit/probe/build/*.dylib "$APP/Contents/MacOS/" 2>/dev/null || true
    mkdir -p "$APP/Contents/Frameworks"
    cp -R ../kit/probe/build/Contents/Frameworks/CrAdapter "$APP/Contents/Frameworks/" 2>/dev/null || true
  fi
fi
# the project's licence, and the crates' and fonts' licences when cargo about has written them (the release
# workflow does; editor/about.toml, editor/about.hbs): inside the app, and beside it on the disk image
cp ../LICENSE "$APP/Contents/Resources/LICENSE.txt"
LICENSES=target/dist/THIRD_PARTY_LICENSES.html
if [ -f "$LICENSES" ]; then cp "$LICENSES" "$APP/Contents/Resources/"; fi
# the name, version (Cargo.toml's) and copyright line macOS's own About panel shows for the app
sed -e "s/@VERSION@/$VERSION/g" -e "s/@IDENTIFIER@/$IDENTIFIER/g" -e "s|@COPYRIGHT@|$COPYRIGHT|g" packaging/macos/Info.plist > "$APP/Contents/Info.plist"
codesign --force --deep -s - "$APP"
rm -rf "$STAGE"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/Camset Editor.app"
cp ../LICENSE "$STAGE/LICENSE.txt"
if [ -f "$LICENSES" ]; then cp "$LICENSES" "$STAGE/"; fi
# the Applications shortcut the app is dragged onto (in the folder made afresh above)
ln -s /Applications "$STAGE/Applications"
DMG="$OUT/Camset-Editor-$VERSION-macos-$ARCH$KIND.dmg"
rm -f "$DMG"
hdiutil create -volname "Camset Editor" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
echo "$APP"
echo "$DMG"
