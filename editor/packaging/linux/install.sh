#!/bin/sh
# Installs Camset Editor for the current user (no root): the program and its camera definitions together in
# ~/.local/share/camset-editor, linked from ~/.local/bin, and its menu entry and icon under ~/.local/share.
# Run from the unpacked folder:   sh install.sh
# The editor finds its definitions beside the program (the link is followed). Installing again replaces them and
# leaves your own, in ~/.config/camset_editor/definitions, as they are.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
share="$HOME/.local/share/camset-editor"
mkdir -p "$HOME/.local/bin" "$share" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/512x512/apps"
install -m 755 "$here/camset_editor" "$share/camset_editor"
rm -rf "$share/definitions"
cp -R "$here/definitions" "$share/definitions"
# the licences beside the program too: Settings > Third-party licences opens the page from there
for f in LICENSE THIRD_PARTY_LICENSES.html; do
  if [ -f "$here/$f" ]; then install -m 644 "$here/$f" "$share/$f"; fi
done
ln -sf "$share/camset_editor" "$HOME/.local/bin/camset_editor"
install -m 644 "$here/camset-editor.png" "$HOME/.local/share/icons/hicolor/512x512/apps/camset-editor.png"
# the program's full path, quoted as the desktop entry spec wants a path with a space quoted
sed "s|^Exec=camset_editor|Exec=\"$HOME/.local/bin/camset_editor\"|" "$here/camset-editor.desktop" > "$HOME/.local/share/applications/camset-editor.desktop"
echo "Installed. Camset Editor is in your applications menu."
