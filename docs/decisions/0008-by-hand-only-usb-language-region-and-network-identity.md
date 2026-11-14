# 8. By hand only: USB, language, region and network identity

- **Date:** 2026-10 (first kit); changed 2026-11-02, 2026-11-11 and 2026-11-13
- **Status:** accepted
- **Rule:** USB, language, region and network rows by hand; Auto Power OFF Temp. when a run names it; a dated owner
  decision opens a row it names, look-only by default.

## Context

These settings can take the camera off the link or change what every other setting means (NTSC/PAL re-indexes frame rates).
The screens that show the camera's network addresses (its MAC and IP addresses, its Bluetooth device address) put
them in every frame the kit keeps, in the OCR output and in any reader's request. On 2026-11-13 the owner asked for the
camera's Wi-Fi and Bluetooth items, and then any menu, to be read and mapped ("Let's read and map all the wifi items";
"Yes map as much as we can"; "you have my full permission to open any menu and map items"), which the owner's hand
alone would leave mostly unproved.

## Decision

USB settings, Language, NTSC/PAL, Area/Date, the camera's network identity and its connections are changed by the
owner, with the closed watcher downloading after each. No `--allow` opens one of them, whatever the owner said: the kit
refuses such a label before anything connects and the row however a run named it (`kit/camkit/safety.py`,
`allow_refused` and `never_lifted`). Auto Power OFF Temp. may be changed remotely (the owner: "it causes no issues when
in stills"); it stays on the kit's by-hand list, so a run opens it only when it names the row with `--allow`.

A dated owner decision in the camera's reviewed scope that names the row, `{"date": "YYYY-MM-DD", "lifts": "network",
"rows": [...], "why": "..."}`, opens it for a run given `--network` (`drive.py`, `crawl_run.py`, and `prove_run.py` with
`--rows`); a decision without `"lifts": "network"`, or dated after the day it is read, opens nothing. It may name:

- a Wi-Fi or Bluetooth setting (on the a1 II, Wi-Fi Connect, Wi-Fi Frequency Band, Bluetooth Function, Bluetooth Rmt
  Ctrl, Airplane Mode);
- a screen that shows the camera's addresses (Display Wi-Fi Info., Display Wired LAN Info., Disp Device Address),
  opened only by `drive.py`, as the last row of its path;
- an identity, connection or region row whose opening starts or ends nothing, Right on it opening an option list, a
  submenu or an information screen (Wired LAN Connect, IP Address Setting, Remote Shoot Function, Cnct. while Power
  OFF, Wake On LAN, Manage Paired Device, Display FTP Result, USB Connection Mode, USB LUN Setting, USB Power Supply,
  Language, NTSC/PAL, Area/Date/Time).

A row so named is looked at only: the kit opens it, reads its options with up and down, and leaves it with MENU; it
presses no Enter, no Right or Left and turns no dial there, which could choose or commit an option, until it is back
where it opened the row: until the screen read right after a MENU, or after an Enter on an option the decision
names, is the shooting screen, or the page the row was opened from with its lit bar on the row itself (its label, or
the reading with its page's icon glued on that opened it). Each MENU or Enter counts for the one read after it, and a
MENU the camera did not take counts for none. What kind of screen the camera seems to show never ends it alone: a
camera slow to draw the row's list still shows the page after the press that opened it, a list or a popup over the
dimmed page can read as that page, and its lit bar then reads an option, never the row. A row's own screen read as
the shooting screen before any MENU (Manage Paired Device's list did, 2026-11-13) is taken as a screen of no known
kind, MENU alone, and from then on a frame read as the shooting screen ends the row only when it is not that screen
and the camera's own picture of its screen reads as the shooting screen too. Choosing an option of these rows needs
the decision to name it, `"options": {"<row>": ["<option>", ...]}`, and then only that option is chosen, its lit text
read as exactly that; an option named by one character, by a button's word (OK, Execute, Cancel, Done) or by a name
the never-open list or identity holds stops the run. No option is ever chosen, whatever a decision names, where the
choice drops a link, starts a connection or a pairing or changes what no file puts back: Wi-Fi Connect (On joins the
access point), Bluetooth Rmt Ctrl (On opens Pairing), Airplane Mode (it drops the Wi-Fi and Bluetooth links), Wired LAN
Connect, Remote Shoot Function, IP Address Setting, Cnct. while Power OFF, Manage Paired Device, Display FTP Result,
the USB rows, Language, NTSC/PAL and Area/Date/Time; on the a1 II that leaves Bluetooth Function, Wi-Fi Frequency Band
and Wake On LAN as the rows whose options a decision may name. The kit names these classes only when no other reason
matches the row, so a misread that also looks like credentials or an action keeps that reason.

A run given `--network` asks only local readers, those whose address is this computer's or a private network's,
never a paid service, and marks its run folder so; every tool that reads that folder's frames later
(`pass1_labels.py`, `tiebreak.py`, `page_model.py --vlm`, `help_reads.py`, `tools/reread_proofs.py`,
`tools/reader_census.py`) asks local readers only too, builds no other, and asks none about the frames of an identity
or connection row; and a prover's way back to the shooting screen sends no OK to a notice that refuses MENU during
such a run, nor anywhere to one that names identity or credentials ("Connect to ...?"). A screen met inside such a row that names identity or credentials (a pairing screen, a connecting
notice, an SSID, a keyboard) gets MENU alone, and no reader is asked; so does an address screen. Inside an identity
row or on an address screen, and on any screen whose text names identity, what the run prints and keeps is the
screen's field names and whole row labels alone, never a value. Whatever is decided, these stay by hand: credentials
and the screens that show them (decision 9), the SSID, WPS, access point and pairing rows, Import Root Certificate,
the copyright and IPTC rows, Display Serial Number, and every action and reset (SSID/PW Reset, Reset Network Set.,
Reset Transfer Status); the rows whose opening may itself start or end a connection or act, until someone has seen
on the camera what Right does there, since looking only governs the presses after the opening (Smartphone
Connection, Cloud Connection, Cloud Information, Network Streaming, USB Streaming, Tethering Connection, Tethering
Disconnection, FTP Function); Server Setting, behind which the FTP login sits; and Edit Device Name, a keyboard
showing the device's name, which no file holds. A decision naming one of these stops the run before anything
connects. The a1 II's owner, the maintainer, decided so for their own camera on 2026-11-13; another camera's owner
decides for theirs, and the default stays by hand (the playbook's rule 3).

Before 2026-11-13 Wi-Fi Connect, Bluetooth Function and Airplane Mode were network identity, which no allowance opened,
and Bluetooth Rmt Ctrl, Wi-Fi Frequency Band and the address screens were on no list until a first change that day made
them identity rows too; before 2026-11-02 Auto Power OFF Temp. was changed by hand only, as the rest; before 0.2.0
(2026-11-11) a run's `--allow` could name one of the others.

## Consequences

Proofs of these rows come from the owner's hand changes, except the options a decision names, which the kit proves
with `--network`, each proof line carrying the decision as its `allowance`. The frames of the screens opened this way
hold what they show: they stay in `runs/` with every other frame, never in a submission, and go to local readers
alone, then and later. For someone else's camera the
playbook's rule 3 keeps Auto Power OFF Temp., the Wi-Fi and Bluetooth rows and the identity rows by hand too, until its
owner decides otherwise.
