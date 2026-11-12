# 9. Credentials are never read or stored

- **Date:** 2026-10 (first kit)
- **Status:** accepted

## Context

The camera's access authentication guards remote control over the network, and every frame the kit sees is kept as evidence.

## Decision

The user name and password live only in ~/.config/camset/network.json (mode 600), written by the owner. The kit never types, reads, OCRs, screenshots or stores a password, and never opens Access Authen. Info.

2026-11-05: the file holds a default pair and, under `"cameras"`, one pair per camera keyed by its MAC address (`{"user", "password", "cameras": {"<MAC>": {"name", "user", "password"}}}`). The camera link and the editor's helper use the camera's own pair, looked up under the MAC address the SDK names for the camera, then the one this computer's network table holds for its address, then `CAMSET_MAC`, else the default; the owner writes it by hand or with the editor's Save, and the kit's Python still never reads it.

2026-11-05: `network.json` must be readable by its owner only: the camera link and the editor's helper refuse one that other users of the computer can read (cause `credentials_file_open`), and the editor's Save writes it private. Beside it, `~/.config/camset/known_cameras.json` (mode 600) holds the cameras this computer trusts: the fingerprint (SSH host key) each camera showed at its first successful connection, under its MAC addresses and its address. A login goes only to a camera whose fingerprint matches; the editor's Forget removes the trust with the login.

## Consequences

Network setup is the owner's, by hand.
