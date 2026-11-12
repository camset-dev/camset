#!/bin/sh
# A tarball in target/dist: the program and its camera definitions, its menu entry, icon, a per-user install
# script, the project's LICENSE and (when cargo about has written it) the third-party licences page.
# Run from editor/ on Linux:   sh packaging/build_linux.sh
set -eu
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)
cargo build --release
NAME="camset-editor-$VERSION-linux-$(uname -m)"
DIR="target/dist/$NAME"
rm -rf "$DIR"
mkdir -p "$DIR"
cp target/release/camset_editor "$DIR/"
# the shipped camera definitions beside the program, so the unpacked folder runs as it is (install.sh keeps them
# beside it)
ls definitions/*.json >/dev/null 2>&1 || { echo "definitions/ holds no camera definition" >&2; exit 1; }
cp -R definitions "$DIR/"
cp packaging/linux/camset-editor.desktop packaging/linux/install.sh "$DIR/"
cp assets/icon.png "$DIR/camset-editor.png"
# the project's licence, and the crates' and fonts' licences when cargo about has written them (the release
# workflow does; editor/about.toml, editor/about.hbs)
cp ../LICENSE "$DIR/LICENSE"
if [ -f target/dist/THIRD_PARTY_LICENSES.html ]; then cp target/dist/THIRD_PARTY_LICENSES.html "$DIR/"; fi
tar -C target/dist -czf "target/dist/$NAME.tar.gz" "$NAME"
echo "target/dist/$NAME.tar.gz"
