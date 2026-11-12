#!/usr/bin/env bash
# Screenshots of the editor's pages and windows in the dark and the light theme, to check by eye that both read
# well after a change to the window (colours come from editor/src/window/tone.rs; `cargo test` checks their contrast).
#
#   editor/tools/theme_shots.sh OUT_DIR
#
# Builds the release editor, copies it into a scratch folder and runs the copy there with the CAMSET_SCREENSHOT
# hook (one frame saved as a PNG, then the window closes), so:
# - the preferences, kept copies and camera folder are a scratch config (XDG_CONFIG_HOME, HOME and APPDATA point
#   into the scratch folder): your own preferences are never read or changed;
# - the camera link program is /usr/bin/false, which does nothing, and the program search cannot reach a real one
#   (the copy runs outside the repository); the camera address is a documentation address (192.0.2.10); the web
#   page stays off. Nothing talks to a camera.
# The file shown is the sample beside the ILCE-1M2 definition (editor/definitions/ILCE-1M2_fw4.00.DAT), with a few
# edits made by CAMSET_DEMO_EDITS.
# macOS and Linux (a desktop session is needed for the window).
set -euo pipefail
out=${1:?usage: theme_shots.sh OUT_DIR}
here=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$out"
out=$(cd "$out" && pwd)
(cd "$here" && cargo build --release --quiet)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cp "$here/target/release/camset_editor" "$scratch/camset_editor"
cp -R "$here/definitions" "$scratch/definitions"   # the shipped definitions beside the copy, as the packages carry them
cp "$here/definitions/ILCE-1M2_fw4.00.DAT" "$scratch/CAMSET01.DAT"

# name, CAMSET_VIEW, demo edits (1 or empty), file (or empty for the welcome page)
shots=(
  "welcome||| "
  "main|main|1|CAMSET01.DAT"
  "tab|Shooting|1|CAMSET01.DAT"
  "compare|compare|1|CAMSET01.DAT"
  "memories|memories|1|CAMSET01.DAT"
  "exposure|exposure|1|CAMSET01.DAT"
  "settings|settings||CAMSET01.DAT"
  "write|write|1|CAMSET01.DAT"
  "write_reading|write_reading|1|CAMSET01.DAT"
  "history|history|1|CAMSET01.DAT"
)
failed=0
for theme in dark light; do
  light=false; [ "$theme" = light ] && light=true
  for s in "${shots[@]}"; do
    IFS='|' read -r name view demo file <<<"$s"
    cfg="$scratch/cfg_${name}_$theme"
    mkdir -p "$cfg/camset_editor" "$cfg/home"
    printf '{"theme": "%s", "light": %s, "zoom": 1.0, "density": 1, "link": "usb", "probe_path": "/usr/bin/false", "camera_ip": "192.0.2.10", "web_at_start": false, "window": [1280.0, 860.0]}\n' "$theme" "$light" >"$cfg/camset_editor/prefs.json"
    png="$out/${name}_$theme.png"
    rm -f "$png"
    envs=(XDG_CONFIG_HOME="$cfg" HOME="$cfg/home" APPDATA="$cfg" CAMSET_SCREENSHOT="$png")
    [ -n "$view" ] && envs+=(CAMSET_VIEW="$view")
    [ -n "$demo" ] && envs+=(CAMSET_DEMO_EDITS=1)
    args=()
    # named from the scratch folder the copy runs in, so the status line says "Opened CAMSET01.DAT" and no folder of
    # this computer shows in a picture (the README's among them)
    [ -n "${file// /}" ] && args=("$file")
    # ${args[@]+...}: the welcome shot has no file, and bash 3.2 (macOS's own) calls an empty array unbound under set -u
    (cd "$scratch" && env "${envs[@]}" ./camset_editor ${args[@]+"${args[@]}"} >/dev/null 2>&1) || true
    if [ -s "$png" ]; then echo "ok   $png"; else echo "FAIL $png"; failed=1; fi
  done
done
exit $failed
