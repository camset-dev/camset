# 8. By hand only: USB, language, region and network identity

- **Date:** 2026-10 (first kit); changed 2026-11-02, 2026-11-11, 2026-11-13 and 2026-11-14
- **Status:** accepted
- **Rule:** USB, language, region and network rows by hand; Auto Power OFF Temp. when a run names it; a dated owner
  decision opens a row it names, look-only by default.

## Context

These settings can take the camera off the link or change what every other setting means (NTSC/PAL re-indexes frame rates).
The screens that show the camera's network addresses (its MAC and IP addresses, its Bluetooth device address) put
them in every frame the kit keeps, in the OCR output and in any reader's request. On 2026-11-13 the owner asked for the
camera's Wi-Fi and Bluetooth items, and then any menu, to be read and mapped ("Let's read and map all the wifi items";
"Yes map as much as we can"; "you have my full permission to open any menu and map items"), which the owner's hand
alone would leave mostly unproved; and then the rest of the never-open list too: "you can also do password/logins,
actions, and display serial number... I have generic sd cards in so you can format, delete, etc", the password
screens' values to be kept ("Read everything"), and the resets that wipe the link possible, restored by hand.

On 2026-11-14 a run under such a decision opened IP Address Setting over the wired LAN link to look at it (Right, then
MENU, nothing chosen). Its screen read as no known kind, and one to two and a half seconds after the MENU the camera
raised a network error and dropped the link the run was on, which did not come back. This record had listed the row
among those whose opening starts or ends nothing, as it had the USB, language, NTSC/PAL and area and date rows, though
nobody had seen any of them opened over the link.

## Decision

USB settings, Language, NTSC/PAL, Area/Date, the camera's network identity and its connections are changed by the
owner, with the closed watcher downloading after each. No `--allow` opens one of them, whatever the owner said: the kit
refuses such a label before anything connects and the row however a run named it (`kit/camkit/safety.py`,
`allow_refused` and `never_lifted`). Auto Power OFF Temp. may be changed remotely (the owner: "it causes no issues when
in stills"); it stays on the kit's by-hand list, so a run opens it only when it names the row with `--allow`.

A dated owner decision in the camera's reviewed scope that names the row, `{"date": "YYYY-MM-DD", "lifts": "network",
"rows": [...], "why": "..."}`, opens it for a run given `--network` (`drive.py`, `crawl_run.py`, and `prove_run.py` with
`--rows`); a decision without `"lifts": "network"` opens nothing for such a run (an owner decision, below, is
`drive.py --owner`'s alone), and one dated after the day it is read opens nothing at all. It may name:

- a Wi-Fi or Bluetooth setting (on the a1 II, Wi-Fi Connect, Wi-Fi Frequency Band, Bluetooth Function, Bluetooth Rmt
  Ctrl, Airplane Mode);
- a screen that shows the camera's addresses (Display Wi-Fi Info., Display Wired LAN Info., Disp Device Address),
  opened only by `drive.py`, as the last row of its path;
- an identity or connection row that has been seen to open and close over the link without harm, Right on it
  opening an option list, a submenu or an information screen (on the a1 II, seen on 2026-11-13 and 2026-11-14: Wired
  LAN Connect and Wake On LAN, each a list of two; Remote Shoot Function, a submenu; Cnct. while Power OFF, a notice
  while greyed; Manage Paired Device, a screen; Display FTP Result, an information screen).

A row is liftable only once it has been seen to open and close over the link without harm: `kit/camkit/safety.py`
names beside each such row when it was seen, and a test holds the list to that record. IP Address Setting is never
lifted, since opening and leaving it over the link dropped the link (2026-11-14); USB Connection Mode, USB LUN Setting,
USB Power Supply, Language, NTSC/PAL and Area/Date/Time are not lifted until someone has seen them opened over the
link. They stay by the owner's hand.

A row so named is looked at only: the kit opens it, reads its options with up and down, and leaves it with MENU; it
presses no Enter, no Right or Left and turns no dial there, which could choose or commit an option, until it is back
where it opened the row: until the screen read right after a MENU, or after an Enter on an option the decision
names, is the shooting screen, or the page the row was opened from with its lit bar on the row itself (its label, or
the reading with its page's icon glued on that opened it, that icon read live with at most one letter misread, glued on
or set apart, forming no other label the kit knows). Each MENU or Enter counts for the one read after it, and a
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
the USB rows, Language, NTSC/PAL and Area/Date/Time, and Wi-Fi Frequency Band (a change of band can drop a link that
runs over Wi-Fi); on the a1 II that leaves Bluetooth Function and Wake On LAN as the rows whose options a decision may
name. The kit names these classes only when no other reason
matches the row, so a misread that also looks like credentials or an action keeps that reason.

A run given `--network` asks only local readers, those whose address is this computer's or a private network's,
never a paid service, and marks its run folder so; every tool that reads that folder's frames later
(`pass1_labels.py`, `tiebreak.py`, `page_model.py --vlm`, `help_reads.py`, `tools/reread_proofs.py`,
`tools/reader_census.py`) asks local readers only too, builds no other, and asks none about the frames of an identity
or connection row, and every tool that writes into that folder writes owner-only, as the run left it; and a prover's way back to the shooting screen sends no OK to a notice that refuses MENU during
such a run, nor anywhere to one that names identity or credentials ("Connect to ...?"). A screen met inside such a row that names identity or credentials (a pairing screen, a connecting
notice, an SSID, a keyboard) gets MENU alone, and no reader is asked; so does an address screen. From such a run's
start to its end no screen's text is printed or kept, whatever its kind (`camkit.safety.kept_screen`): what the console,
`drive.jsonl`, `rows.jsonl`, the proofs and `events.jsonl` keep of a screen is its kind, the whole row labels the kit
knows (the definition's, the page model's that are a label alone, the decision's own rows; one of a letter or two only
where it is a row label of the page shown) and the field names, on an
option list the option names the definition gives that row only where the screen shows that whole set, else their
count (never which one is lit, current or saved; never a carousel's, which shows the lit one alone, nor a side
list's, a window centred on it), on a notice what `notice_kept` keeps (a notice the kit knows, and a blocker's row
label where it is one the kit knows, never that row's value, its current state), and the count of lines withheld; the
shooting screen as its kind alone, since its status line is the owner's shooting values; a row label the kit does not
know as "(withheld)", the row a decision names as the run was given it; a text the navigation read as "(the text read
withheld)", never its length; a refusal's or an error's quoted texts withheld, in the closing lines as in the first (a
link command's quoted path holds the home folder); the records that differ at the session's end by
key and count alone, never a value, in the console and in `drive.jsonl` (unless the owner row's decision logs values).
A proof of a network row says nothing of the option it was saved on: the named options are proved in their own order,
each said as "proof i of N", the records they changed said by key, and every such row ends with the session's upload of
the start file; the proofs' diffs against the start file tell it by nature, as do the run's `events.jsonl` (its presses
tell the way the cursor went from the saved option) and its frames, and all stay in the run's owner-only folder. An `--owner` run keeps alike, but for the owner row's own screens where its decision says
`"values": "logged"` (decision 9). Such a run's folder is the owner's alone on macOS and Linux (decision 9). Whatever a network decision says, these stay by hand:
IP Address Setting and the USB, language, NTSC/PAL and area and date rows (above);
credentials and the screens that show them (decision 9), the SSID, WPS, access point and pairing rows, Import Root
Certificate, the copyright and IPTC rows, Display Serial Number, and every action and reset (SSID/PW Reset, Reset
Network Set., Reset Transfer Status); the rows whose opening may itself start or end a connection or act, since
looking only governs the presses after the opening (Smartphone Connection, Cloud Connection, Cloud Information,
Network Streaming, USB Streaming, Tethering Connection, Tethering Disconnection, FTP Function); Server Setting, behind
which the FTP login sits; and Edit Device Name, a keyboard showing the device's name, which no file holds. A network
decision naming one of these, or saying `"confirm"`, `"link_loss"`, `"values"`, `"steps_seen"` or `"unattended"`,
stops the run before anything connects.

A dated owner decision, `{"date": "YYYY-MM-DD", "lifts": "owner", "rows": [...], "why": "..."}`, may name any row of
the never-open list but these, whatever it says: a firmware update and the Version screen; anything that loads a file
or settings from a card or the camera's memory (Save/Load Settings' Load, Recall Camera Setting, Import Root
Certificate, IPTC Information's Register IPTC Info, Manage User LUTs' Import: decision 6); Initialize, an item of Setting Reset's dialog whose Enter nobody has seen (decision 5); and
the rows of sound, light or motion and the Screen Reader (Cleaning Mode, Pixel Mapping, Anti-dust and Preset Focus/Zoom
among them), which keep their own routes (decisions 2 and 3). Only `kit/drive.py --owner` uses it, for the row its
`--path` ends on, one per run; the crawl and the proofs never open such a row. A row whose name the kit knows in more
than one place, or none, and every action's and card's, is named by its path ("Tab > Group > Row [> Row ...]"); the run
goes to it in that tab and group and opens it only where the camera's screen reads that place: the top-level page's
breadcrumb its tab and group; for a deeper row, each parent's lit bar before its Right and the title of the page that
Right opens (after the breadcrumb of the labels above it, joined to the title by a space only right after the tab or
the group), the last of them read again at the opening; whatever cannot be read, and a page that a Right left in the
position it was in, refuses. Between the walk and the opening only Up and Down go out, and from then on no Right or Enter goes out,
in `drive.py` or in the camera's own check, but the opening of that row and the presses inside it, whatever a lit row
reads as; the run's `--confirm` covers only a press those checks judged a step or its armed press. The scope file is
refused when git tracks it, when git cannot say whether it does, or when it writes a key twice in one object. The row opens with Right alone, from a menu page, to look: up,
down and MENU, and Enter only as follows. `"options"` names what may be chosen, never one character, a keyboard's key, a
button's or a go-ahead's word, a never-open name or anything that loads; in a never-choose row only with `"link_loss":
true`, as the last press of a run given `--confirm`; in Language, NTSC/PAL and Area/Date/Time never; in a credentials
row only the row's own listed values, on an option list. An action or a card row opens to look only at a place where
the kit has seen it open a list or a question, judged by the whole place, never the label alone (on the a1 II: Setup >
Reset/Save Settings > Setting Reset, Shooting > Shooting Mode > Camera Set. Memory and Reg. Custom Shoot Set, My Menu >
My Menu Setting > Add Item, Shooting > File > Select REC Folder: `safety.opens_to_look` says where each was seen; not
Format or Delete, whose opening no frame records, decision 4); every other one, and every row that acts as soon as
it opens (WPS Push, Pairing, Access Point Set., Select on Cam & Send, Create New Folder, Forced File Number Reset, the
cloud, streaming, tethering, FTP and Send rows, and IP Address Setting, whose opening and MENU dropped the link on
2026-11-14), opens only as the armed last press of a run given `--confirm`, the row
under `"confirm"`, with `"link_loss"` where the network may change or the link is wiped (Reset Network Set., SSID/PW
Reset: decision 5), and with `"values": "logged"` too where its screens are otherwise blanked (WPS Push, Pairing,
Access Point Set., IP Address Setting and the other identity rows whose opening may change the network: the screen
after the opening must be read to be judged and cancelled), and takes no option; a run that names such a row whose
opening may change the network without `--confirm`, or a decision without it under `"confirm"`, stops before anything
connects. The USB, language, NTSC/PAL and area and date rows stay closed identity rows an owner decision opens to look
at, their frames blacked out; none of them has been seen opened over the link, so an owner's look at one is at the
owner's risk of a dropped link. Before any `--owner` run given `--confirm` connects, whatever
its row (a never-choose option chosen as the last press may drop the link as an action's confirmation may), the person
at the terminal types the row's name after the run has printed its place, what its last press may do and the camera; no
flag or environment variable answers it, it stops a careless agent but not a determined one, so the owner types the
answer themselves, and only `"unattended": true`, said beside `"confirm"` or beside a never-choose row's `"options"`
with `"link_loss"`, waives it (decisions 4 and 5). Inside an action any Enter may be the final one: a step it names goes before
the last press only where `"steps_seen"` marks it seen to lead only to a question, the screen reads as no question and
shows no dialog's two buttons, and another Enter follows (never in a row whose first Enter registers: Camera Set.
Memory, Reg. Custom Shoot Set, My Menu's items); any other Enter there is the run's armed last press, on the action's
question only with a confirm button lit and the whole text that action's question (decision 4). The camera's own check
presses each armed press only when `drive.py` allowed that very press for that row and its own reading agrees. A press
that may drop the link has `RESTORE_BY_HAND.json` written before it goes, naming the start file; no link opens while it
is there until `kit/tools/upload_check.py` has put that file back, and the run takes it away itself only when the press
was refused before it went, or when the row only asked its question, cancelled with MENU (exit status 6), or the link
still answered, and its restore then checked out (decision 5). Screens that take MENU alone stay so whatever is decided of
values: a keyboard or an entry screen, an address or serial number screen, credentials, a connection or a pairing in
the making. Without `"values": "logged"` a credentials, serial number or closed identity row's frames are saved black
from its opening, never read, and its screens kept as nothing but their kind; an action's frames are kept as they are,
read for the checks above, and its screens printed and kept as their field names and whole row labels; with it every
frame is kept, the run keeps the screens' text in its `drive.jsonl`, and the console shows their field names alone
(decision 9). Such a run asks local readers only, and no tool reads its frames with a reader afterwards.

The a1 II's owner, the maintainer, decided all this for their own camera on 2026-11-13; another camera's owner
decides for theirs, and the default stays by hand (the playbook's rule 3).

Before 2026-11-14 IP Address Setting and the region and USB rows (USB Connection Mode, USB LUN Setting, USB Power
Supply, Language, NTSC/PAL, Area/Date/Time) were liftable to look at, listed as rows whose opening starts or ends
nothing though nobody had seen one opened over the link, an owner decision could open IP Address Setting to look
without `--confirm`, a decision could name Wi-Fi Frequency Band's options, and a
`--network` run printed and kept the
text of the screens it did not withhold (a list's lines, a notice's, the page after MENU, the shooting screen's status
line). Before 2026-11-13 no decision opened a row of the never-open list, Wi-Fi Connect, Bluetooth Function and Airplane Mode
were network identity, which no allowance opened, and Bluetooth Rmt Ctrl, Wi-Fi Frequency Band and the address screens
were on no list until a first change that day made them identity rows too; before 2026-11-02 Auto Power OFF Temp. was changed by hand only, as the rest; before 0.2.0
(2026-11-11) a run's `--allow` could name one of the others.

## Consequences

Proofs of these rows come from the owner's hand changes, except the options a decision names, which the kit proves
with `--network`, each proof line carrying the decision as its `allowance`. The frames of the screens opened this way
hold what they show: they stay in `runs/` with every other frame, never in a submission, and go to local readers
alone, then and later, a `--owner` run's to none. For someone else's camera the
playbook's rule 3 keeps Auto Power OFF Temp., the Wi-Fi and Bluetooth rows and the identity rows by hand too, until its
owner decides otherwise.
