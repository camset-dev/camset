# 9. Credentials are never read or stored

- **Date:** 2026-10 (first kit); changed 2026-11-05
- **Status:** accepted
- **Rule:** The camera's login lives only in a file the owner writes; the kit never types, reads, OCRs, screenshots or
  stores a password, nor opens Access Authen. Info.

## Context

The camera's access authentication guards remote control over the network, and every frame the kit sees is kept as
evidence. A login sent to the wrong camera, or kept in a file other users can read, gives the camera away.

## Decision

The user name and password live only in `network.json` in `.config/camset/` under the user's home folder
(`~/.config/camset/` on macOS and Linux; on Windows `%USERPROFILE%\.config\camset\`, or under `%HOME%` when that is
set, as both the camera link and the editor look it up), written by the owner by hand or with the editor's Save. The kit never types, reads, OCRs, screenshots or stores a password, and never opens Access
Authen. Info; its Python never reads that file.

The file holds a default pair and, under `"cameras"`, one pair per camera keyed by its MAC address (`{"user",
"password", "cameras": {"<MAC>": {"name", "user", "password"}}}`). The camera link and the editor's helper use the
camera's own pair, looked up under the MAC address the SDK names for the camera, then the one this computer's network
table holds for its address, then `CAMSET_MAC`, else the default. On macOS and Linux they refuse a file other users of
the computer can read (cause `credentials_file_open`), and the editor's Save writes it with mode 600. On Windows
neither is done: the file sits in the user's profile folder (unless HOME points elsewhere), which other standard users
cannot read by default, though administrators can. Beside it, `known_cameras.json` holds the cameras this computer trusts: the fingerprint (SSH host
key) each camera showed at its first successful connection, under its MAC addresses and its address. A login goes only
to a camera whose fingerprint matches; the editor's Forget removes the trust with the login.

Before 2026-11-05 the record named one pair for every camera, with no check that the file is private and no list of
the cameras this computer trusts; it says from 2026-11-13 that no such check is made on Windows, and where the file is
there.

## Consequences

Network setup is the owner's, by hand. Which login a camera gets is said in `kit/common/camera_net.h` and, in words,
in [the editor's guide, "The camera link"](../EDITOR.md#the-camera-link).
