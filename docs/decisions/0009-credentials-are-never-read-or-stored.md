# 9. Credentials are never read or stored

- **Date:** 2026-10 (first kit); changed 2026-11-05, 2026-11-13 and 2026-11-14
- **Status:** accepted
- **Rule:** The login lives only in a file the owner writes; the kit never types a password, and opens a credentials
  screen only where a dated owner decision names it.

## Context

The camera's access authentication guards remote control over the network, and every frame the kit sees is kept as
evidence. A login sent to the wrong camera, or kept in a file other users can read, gives the camera away. On
2026-11-13 the owner asked for their a1 II's login screens to be mapped too ("you can also do password/logins"), and,
asked how their values should be kept, said "Read everything".

## Decision

The user name and password live only in `network.json` in `.config/camset/` under the user's home folder
(`~/.config/camset/` on macOS and Linux; on Windows `%USERPROFILE%\.config\camset\`, or under `%HOME%` when that is
set, as both the camera link and the editor look it up), written by the owner by hand or with the editor's Save. The kit
never types a password or any text: on a keyboard or an entry screen only MENU goes out. Its Python never reads that
file.

By default the kit never reads, OCRs, screenshots or stores a password, and never opens Access Authen. Info or another
credentials screen (Access Authen. Settings, Wi-Fi Direct Info. and Settings); every camera keeps that unless its owner
writes a dated owner decision in its reviewed scope. A dated
owner decision in the reviewed scope that names the screen (`"lifts": "owner"`, decision 8) opens it for `kit/drive.py
--owner` alone, as the last label of its `--path`, to look: inside it only MENU goes out on any screen that is not an
option list, and an option list takes Enter only on an option the decision names that is one of the row's own listed
values, a choice that may change the link (Access Authen., Wi-Fi Direct) only with `"link_loss": true`, as the last
press of a run given `--confirm`. Such a run asks local readers only, and its run folder is marked so that no tool reads
its frames with any reader afterwards (`camkit.vlm.NO_READER_MARKER`). What it keeps:

- with the decision silent on values, every frame from the press that opened the screen until the run leaves it is
  written black in the run's `shots/` by the eyes themselves (`camkit.frames`: no pixel of it is written as it was;
  the OSD eyes poll the camera's own picture into a folder of their own outside the run's folder, made for the run
  with a name no other user can guess and mode 0700, where camlink writes it and the kit removes it, and camlink's
  `.part` beside it, as soon as it is read, and the folder when the row is left and at the run's end, an error's
  included), no OCR text of it is kept, no reader is asked, and the console, `drive.jsonl` and
  `events.jsonl` say only that a screen was there ("screen withheld"), its kind and its frame's name;
- with `"values": "logged"`, every frame is saved as it was in `runs/<model>_fw<fw>/<run>/shots/`, and each screen's
  OCR text, the password among it, in that run's `drive.jsonl`; the console shows each screen's field names, never a
  value: the lines that are whole row labels the kit knows, the name before a value on a line ("Password: ...",
  "User Name  ...") where it is a field name the kit lists (`camkit.safety.ADDRESS_FIELDS`: User Name, Password,
  Fingerprint, Access Authen., SSID, Device Name and the address fields), and always the count of lines not shown,
  then "(values in drive.jsonl)"; `events.jsonl` keeps frame names and keys, never text; and a refusal's or an error's
  quoted texts are withheld in both.

On macOS and Linux the run folder of every `--owner` run, and of every `--network` run (whose frames can hold the
camera's addresses), is the owner's alone: the folder and its subfolders mode 0700, and every file the run writes in it
mode 0600, the frames, `drive.jsonl`, `events.jsonl`, the downloads and the markers among them (`camkit.runs`: the run
sets its process's umask to 0077 before anything is written, so the camera's helper writes so too, whatever the
person's own umask), and the run checks at its end that nothing in its folder can be read by another user, fixes what
can and says so. The eyes' polling target at the top of the folder (`_live.png`, a frame of whatever was polled last)
is taken away when the eyes close and again at that check, and the proof viewer never links it. On Windows the modes
are left as they are: the run folder sits under the user's own profile as a rule, which other standard users cannot
read by default, though administrators can. Every run's `events.jsonl`, an ordinary one's too, holds the camera's
network address and MAC address in its `link_open` entry (the camera link's reply as it opens): mode 0600 in a private
run's folder, and as the person's umask makes it (0644 as a rule) in any other run's, which is never committed or
shared either.

Nothing of it goes into a tracked file: `runs/` is never committed, and `kit/tools/check_public.py` refuses it. The
proof viewer (`kit/tools/proof_viewer.py`) shows no frame and no step of such a run, and its `--pack` copies no frame
of a run marked local-only (a `--network` or `--owner` run's) for another computer.

The file holds a default pair and, under `"cameras"`, one pair per camera keyed by its MAC address (`{"user",
"password", "cameras": {"<MAC>": {"name", "user", "password"}}}`). The camera link and the editor's helper use the
camera's own pair, looked up under the MAC address the SDK names for the camera, then the one this computer's network
table holds for its address, then `CAMSET_MAC`, else the default. On macOS and Linux they refuse a file other users of
the computer can read (cause `credentials_file_open`), and the editor's Save writes it with mode 600. On Windows
neither is done: the file sits in the user's profile folder (unless HOME points elsewhere), which other standard users
cannot read by default, though administrators can. Beside it, `known_cameras.json` holds the cameras this computer
trusts: the fingerprint (SSH host key) each camera showed at its first successful connection, under its MAC addresses
and its address. A login goes only to a camera whose fingerprint matches; the editor's Forget removes the trust with
the login. The maintainer, the a1 II's owner, decided the owner decision's part for their own camera on 2026-11-13.

Before 2026-11-14 such a run folder took the person's umask (folders 0755 and files 0644 as a rule, readable by other
users of the computer), left `_live.png` at its top, and the console showed a logged screen's field names without the
count of lines not shown, and none of a credentials screen's own field names (Password, Fingerprint, Access Authen.).
Before 2026-11-13 no decision opened a credentials screen, and the kit never read one; before 2026-11-05 the record
named one pair for every camera, with no check that the file is private and no list of the cameras this computer
trusts; it says from 2026-11-13 that no such check is made on Windows, and where the file is there.

## Consequences

Network setup is the owner's, by hand. Which login a camera gets is said in `kit/common/camera_net.h` and, in words,
in [the editor's guide, "The camera link"](../EDITOR.md#the-camera-link).
