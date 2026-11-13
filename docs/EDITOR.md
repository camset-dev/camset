# Using the editor

Camset Editor reads, compares and edits Sony camera settings files (`CAMSET*.DAT`). Downloading and installing it
(on Windows the zip and, from the release after 0.2.1, the installer), building it, the camera helper and the
supported cameras are in the repository's README, [Use the editor](https://github.com/camset-dev/camset#use-the-editor).
To only look inside a file, the [definition viewer](viewer/) does it in a browser, with nothing to install: the same
names, read-only.

!!! warning "At your own risk"

    --8<-- "README.md:warning"

## First run

### From the card and back

The editor works on the settings file the camera saves to its card: nothing else is needed to open, edit and save
one. On the ILCE-1M2 (a1 II):

1. **Save on the camera:** MENU > Setup > Reset/Save Settings > Save/Load Settings > Save. The camera writes a
   `CAMSET*.DAT` file into the card's `PRIVATE/SONY/CAMSET` folder ([the file format](formats/index.md)). Copy it to
   your computer and keep it there too: it is the camera's own backup, to load back if anything goes wrong.
2. **Open and edit it:** Open… (or the welcome screen's Open a settings file), edit, then Save As… under a new name.
   The editor never writes into the file it opened. Open… starts in a mounted card's `PRIVATE/SONY/CAMSET` folder
   when there is one, else in the folder of the file last opened; Save As… starts in the opened file's folder and
   offers the next name the camera would give that is free there (`CAMSET02.DAT` after `CAMSET01.DAT`).
3. **Copy the new file to the card,** into the same `PRIVATE/SONY/CAMSET` folder. The a1 II lists at most 10
   settings files there (`max_settings_files_on_card` in its camera file); after a Save As into a folder that holds
   more, the status line warns. Whether the camera lists a file under a name it did not write itself is not yet
   tried, so give it a name like the camera's own (`CAMSET*.DAT`).
4. **Load it on the camera:** MENU > Setup > Reset/Save Settings > Save/Load Settings > Load, and choose the file.
   This is the camera's own function, which Sony's Help Guide describes. The project's tests with an edited file
   sent it over the camera link ([the playbook](REMAPPING_PLAYBOOK.md#13-a-round-trip-at-the-end), section 13);
   loading an edited file from the card is not yet tried.

With the camera helper built (the README, "The camera helper"), ⬇ Read and ⬆ Write… do steps 1 and 4 over USB or the
network instead, and check the camera afterwards ([The camera link](#the-camera-link)). Read the warning above, and
[If the camera restarts over and over](#if-the-camera-restarts-over-and-over), before loading or writing an edited
file.

### The welcome screen

The editor opens on a welcome screen with three cards, Read from camera, Open a settings file and Explore a
sample (the file beside the built-in ILCE-1M2 definition, with personal text removed, made by
`kit/tools/make_sample.py`, which can be edited but never written to a camera, however it is opened), and the recent
files below them.
Under them, "Works with" names each camera a definition covers by its model code and the name photographers know it
by, from its definition (`display_name`): "ILCE-1M2 · α1 II (firmware 4.00)"; the camera link's reports name a camera
the same way. The Open card says where the file is on the card
(`PRIVATE/SONY/CAMSET/CAMSET01.DAT`) and the camera's menu path for saving it. Without the camera link program,
which the editor's download does not include (the README, "The camera helper"), Open a settings file comes first,
the Read card says the program is needed and opens how to set it up, and the top bar offers no ⬇ Read or ⬆ Write….
Controls appear as they become relevant: Open… and the 📷 camera button are there from the start, with ⬇ Read once
the program is found; Save As…, ↺ Undo, ↻ Redo and ⬆ Write… once a file is open, and Save As… and Undo usable once
there is an edit. The setup steps in Connect to the camera tick themselves when the camera is found. A
failed camera action offers Try again where the action can be retried and Change connection (Enter user name and
password when the login was missing or refused), and, when the check after a write over the network fails, Switch
to USB and read. A progress card shows camera jobs with their expected time, and tiles on the Main page edit in
place.

A file from an unchecked firmware opens view only, its badge reading "⚠ firmware 3.00 not checked: view only",
with "Describe for support…", which saves a description of how the file is laid out, without any settings values,
so support for that firmware can be added. For the same model, "Edit anyway…" turns editing on after a window says
what that means: the settings this firmware keeps where the editor expects them can be changed, and the others stay
locked (the badge then reads "editing on"). The save and write windows then warn that the camera may refuse or
change a value. A file from a model no camera definition covers says so instead ("⚠ ILCE-7M4 is not supported yet:
view only"): its values are greyed, since the names shown are the supported camera's and may not match them.

### Definitions

What the editor knows about a camera is its definition, a file per model and firmware
([decision 19](decisions/0019-definitions-are-files-one-per-model-and-firmware.md)); the program itself holds no
camera facts, the file's container included ([decision 20](decisions/0020-the-editor-holds-no-camera-facts.md)). It
reads two folders:

- **Built-in:** the definitions that come with the editor, beside the program (inside the macOS app, next to the
  program on Windows, from the installer or the zip, in the Linux tarball; `editor/definitions/` when it runs from the
  clone). They are only read; the Windows installer replaces them as a set with each version it installs.
- **Yours:** `definitions/` in the editor's own folder (`camset_editor` in `$XDG_CONFIG_HOME`, `%APPDATA%` or
  `~/.config`). A definition there is used in place of a built-in one of the same model and firmware; the sample
  keeps the built-in one.

A file is read with the definition of the model and firmware its header names. The firmware is only the bytes its
definition's container block names as the firmware: where the block also says where the video system the camera was
set to is (NTSC or PAL, in the camera's words), a file saved on PAL is the same firmware as one saved on NTSC and opens
with that definition, checked. The file's badge says the video system after the firmware ("✔ firmware 4.00 · PAL"),
its hover says "Saved with the camera set to PAL.", and the status line on opening names it too; a value the
definition has no name for shows as its number, saying so. A file from the same model on
another firmware opens with the nearest firmware's definition, which the editor says beside the file's name, and
the settings it does not hold in the mapped shape stay view only; a file whose checksums do not hold under its
definition's container is never edited. In Expert mode, "Open with…" beside the file's name reads the file with any
definition found; a save or a write then names that override in its confirmation.

Settings > Camera support & web page lists every definition (model, firmware, built-in or yours, settings, proved),
with Add definition… (a definition file is checked, then copied into your folder under its model and firmware),
Open folder (yours, to remove one) and Reload. A camera mapped with the kit works this way the same day:
`kit/schema_update.py --write` writes its definition, `editor/definitions/<model>_fw<fw>.json` in the clone, and Add
definition… takes it, with no new editor. A definition made for a newer editor is refused with a message saying so,
and so is one the kit wrote before definitions were lean (definition format 1), with what to do: run
`kit/schema_update.py --write` again, which writes the lean form.

## The top bar and the side bar

In Edit mode the top bar has Edit and Compare; the File menu (Open…, Recent, Save As…, Export CSV…, 📂 Backups…,
🕓 Edit history… and Close file); Open… and Save As…; ↺ Undo and ↻ Redo; the camera button, ⬇ Read and ⬆ Write…
(with the number of edits); and ⚙ Settings at the right. Recent names each file's folder too, so two cards'
`CAMSET01.DAT` can be told apart, and the row wraps when the window is narrow. The camera button names the link and
its state in words: "📷 USB · read 17:44", "📷 Network 192.168.1.50 · not reached", "📷 Set up the camera…" before a
link is chosen, or "📷 Not set up" without the camera link program; its colour says the same (green after a read,
red after a failed camera action), and its hover names the camera and the time of the last read. The row below
picks the live settings or a memory to edit, with the search box, Only edited, and the file's name and firmware
badge.

Closing the file (File > Close file) or the window, opening another file, a kept copy or the sample, and reading
the camera ask first while there are unsaved edits: "You have N edits that are not saved", with Save As… (then
carry on), Discard edits and Cancel; closing while the camera is being written also says that it skips the check
that the camera took the file. Before or after a camera read, the question also offers "Compare with what the camera
holds": the edits stay open as file A and the camera's settings open beside them as file B, in Compare.

The status line at the foot shows the last message on up to two lines (all of it on hover); a click opens Messages,
the last messages with their times, and a warning also shows for a while in a corner of the window. The shortcuts
are listed in Settings > Appearance > Keyboard shortcuts: Cmd/Ctrl+O open, +S Save As, +F search, +W close the
file, +R read the camera, +, Settings, +Z and Shift+Cmd/Ctrl+Z undo and redo, F3 and Shift+F3 the next and previous
edit (in Compare, difference), the arrow keys through the menu's columns, and Esc to close the window on top or
clear the search.

With the sample open, ⬆ Write… is off, and its hover says why: the sample is not a camera's own file. The same holds
however the sample comes: opened with Open… from beside its definition, edited and saved under another name and opened
again, or sent up from the web page. The editor knows it by its header, the model and save time of the sample beside a
definition, which no edit changes, and says so where the write is refused: "This file is the editor's sample, or a file
saved from it: no camera wrote it as it is (its personal text was taken out), so it is never written to a camera.
Read your camera, or open a settings file your camera saved, and make your edits there." The sample may still be saved, as it is there to try the editor: Save
As opens the Before saving window to say first, and the status line once saved and the web page's download say again,
"This is the editor's sample, or a file made from it: no camera wrote it as it is, so never load it into a camera,
though a camera's Load menu would list it. Saving it is only for trying the editor." The window
opens where it was closed and at the size it had, unless that place is off the screen it opens on (a second screen no
longer there, say).

Settings > Appearance > Theme is "Follow the system" for a new user: the window is dark or light as the computer is
set, and changes when it does. Dark and Light keep it one way; preferences from before the choice keep the theme they
had.

Settings > About, the last tab, says which editor this is: the version ("0.2.1") and, for a build made from the
repository, the build (its commit, "1a2b3c4"), the system the editor runs on (its name, its version, on Windows
with its build, and the processor the program was built for), the cameras it works with by model and firmware (a definition you
added says so), whether the camera link program is there, the licence and copyright line, and links to the project
page, the documentation and Report a problem. Copy details copies a short block for a message about a problem: the
version and build, the system, the cameras and the camera link program, with no file, folder, user name or network
address. Changes opens what changed, release by release (the project's `CHANGELOG.md`, built into the program), and
Third-party licences opens the licences of the crates and fonts built into the editor in your browser
(`THIRD_PARTY_LICENSES.html`, which the packages carry; a build of your own has it only once `cargo about` has written
it). The foot of Settings says only where the settings are kept.

The version is in sight without Settings too: in the window's title ("Camset Editor 0.2.1") and at the right end of
the status bar, the whole version (with the build) on hover. The status bar's version is the one that can be clicked,
and it opens Settings on the About tab, on every system (Windows and Linux have no menu bar), bringing Settings over
the other windows, unfolded, if it is open already; over Changes, Esc then closes Settings before Changes. The web
page has the same: About is the last tab of its Settings, with the window's lines, links, Changes and Copy details,
from the editor (its Third-party licences is greyed out, as the licences page is on the editor's computer), and the
version at the right end of its status bar opens Settings on it. The page's windows stack by when they were opened or
asked for, the newest at the top (under a question, which stays first), and Esc closes the one at the top. On macOS
the application menu's About Camset Editor is the system's own panel: the packaged app's name, version and copyright
line, from its Info.plist.

The window describes itself to the computer's screen reader (VoiceOver, Narrator, Orca) through egui's AccessKit
support: buttons, check boxes and lists by their words, and the controls that show none by a name of their own (the
search box, the address and login fields, a setting's number and list boxes, the Main page's tiles with their values,
the welcome cards, the copy arrows and the symbol buttons). It has not been tried with each screen reader yet.

Expert mode is in Settings > Editing & Compare > Expert mode. Without it the editor hides unmapped records, derived
working copies and flags, saved sets 4-12, raw values and the values not checked on the camera yet (which ones:
[DATA_CONTRACTS](DATA_CONTRACTS.md#what-the-editor-offers-outside-expert-mode); its "Offer values…" lists them, in
italics in the window and with "(not checked)" on the page, each saying on hover that the camera may refuse a file
holding it; the value the file holds now is shown as the current value, unmarked, in both), record numbers and file
paths, and the mapping team's words: a setting's note (what it is and how it behaves), the records it lives in, how many values not
checked on the camera yet are hidden, the options that have a choice of their own, the count of known settings at the side bar's foot and the Proved
column of Settings' definitions table. In Expert mode
a setting the definition marks `disputed` says "Disputed: left out of the proofs until a mapper decides" in place
of its proof line; the page marks it the same way in Expert mode. How, when and in which run each thing was proved
(the mapping's evidence) is in no definition, so the editor shows none of it
([DATA_CONTRACTS](DATA_CONTRACTS.md#what-a-mapping-delivers)). Outside Expert mode the
detail panel says in words where a setting is kept. A value the definition says the camera's menus never offer (`not_offered`) is
left out of the list, Expert mode's "Offer values…" or not, unless the open file holds it now (then it is listed as the
value held now, with no mark beside it, its hover saying why), and the detail panel says why on one line per reason
("Not on the camera's list: A, B. …", the menu on its hover); a factory value the
camera writes itself although the menu cannot choose it back stays offered, its line saying so ("ISO 64: The camera's
factory value: …"). Compare's in-place choice and the page say the same.

A number the definition shows other than as stored (`shown_as`: divided, with its decimals, before its unit) is
shown so everywhere: the row's value, the detail panel, Compare, the Memories page, the exports and the number box,
whose range and step are in the same terms ("75 – 105 %, in steps of 2.5" for a stored 7500 to 10500 in steps of
250). A typed number is stored multiplied back; a value the decimals would round shows more of them (9250 is "92.5 %"),
so no shown number stands for two stored ones. Expert mode's "number the camera stores" switch adds the stored number
beside it.

Under Main, the side bar has My Menu when the camera's definition has it (`camera.my_menu`), with how many of its
places hold an item. Its page shows My Menu as the camera does: each page (My Menu 1, 2, …) with its items in order,
each by the camera's name for it and with the value of the setting it opens; a click on the name opens that setting
in its menu, and an item that holds several settings says how many more (which, on hover). Remove takes an item out,
⬆ and ⬇ move it up or down its page (past another item only, on a camera that keeps its pages packed), and an edited
place is marked as any edit, with what it held on hover. Every place takes any of the camera's items, not only the
ones a setting the editor knows opens: "Change…" puts another item in a place, where the old one stood, and a page's
"Add here…" adds one after the page's items (on its first empty place, as the camera keeps its pages packed); both
open a list of every item My Menu can hold, with a box to type part of its name or tab, the items already in My Menu
greyed out with where they are, and the camera's own exclusion said (Playback items cannot be added, on the a1 II).
An item no setting carries shows by its name alone. An item is also added from its setting, with a right-click and
Add to My Menu. The raw places ("My Menu 1: item 1" …, 42 on the a1 II) are shown in Expert mode only, as the page edits them.
My Menu is part of the live settings, not of a memory, so the page always shows the live settings and
says so while a memory is the set being edited. Below the pages are the settings of My Menu's own tab (Display From
My Menu on the a1 II), to change as in any group. The settings of a tab the definition does not list are under Other,
so every setting can be reached from the side bar, and next edit (F3) lands on them there.

A value is shown by its name. A setting with a range shows a number and its unit, and one the definition has no names
for at all shows the plain number. Where a setting has named values but the file holds a number none of them names,
it shows as "7 (no name yet)": that value was not chosen on the camera when the setting was mapped (frame rates of
the other TV system, say), so the definition has no name for it. Its hover says so wherever it is shown (the menu,
the Main page, Compare, Memories, the search and the web page), and so does a line in the detail panel, which adds
in Expert mode why (it was not chosen on the camera when mapped) and the record number. Outside Expert mode it says only "The camera holds 7 here, a value Camset has no name for
yet."

The side bar has a Memories page: memories 1, 2, 3 beside the live settings, "Recall Memory 1 ➡ Live" and "Register
Live ➡ Memory 1" for a whole memory (Compare's Whole sets row has the same buttons and words), and per-row copy
arrows. "Only rows that differ from Live", on unless turned off, leaves out the settings every memory holds as the live
settings do, and the search box narrows the page's rows in place. On the other pages the search box lists matches
across every tab. The detail panel's help is Camset's own description of the setting, from the definition; a help
file of the camera's own text on this computer takes its place where it has some, and the help's hover, and each
option's, says whose words it shows. A help file is used only for the model and firmware written inside it, whatever
its name: another camera's is not used, and Settings > Camera support & web page says so. The detail panel shows which shooting modes a
setting applies in (from the Help Guide list) and whether memories store it, and a line
saying whether it was proved
on the camera ("Proved on the camera (3/3)", the values a proof checked of those it lists; "Proved on the camera
(sampled)" for a scale proved by samples; "Not proved on the camera yet"), its hover saying what a proof is, in the
window and on the page, or, for a setting no proof can reach, why
in a few words, the definition's reason in full on hover: "Not on this camera", "Not a menu setting: the camera keeps
it", "Written only by the camera's own saves", "Not proved (needs equipment)", "Not proved (network, by hand only)",
"Not proved (nothing tried moved it)" or "Not proved (skipped)", and "No proof possible" for a kind of reason a newer
definition brings that this editor does not know; a memory set's own says "in this memory set". That line is off
unless turned on in Settings > Editing & Compare, under Expert mode, beside the switches for the record number beside
a setting's name and the stored number beside a value's name; those three switches show only while Expert mode is on, and the proof line
shows in the detail panel, on the Exposure page and on the web page. With Expert mode off none of the three draws
anything, whatever it was left at; they come back as they were with it. With the proof line off, a setting the camera's
menu does not show says "Not on this camera's menu".

Outside Expert mode a setting is changed only where a proof on the camera stands for it; the others are view only,
whatever view would change them (the detail panel, a row's box, the Main page's tiles, My Menu's page, Compare's
picker, arrows and copies, the Memories page's arrows and the web page), each saying why under it in a few words, the
definition's own reason on hover:

- A setting with no proof (`proved` absent), in every set, or in the memory sets its `unproved_sets` names, or one whose
  proofs disagree (`disputed`): "View only: …, and the camera may refuse a file where it was changed. Expert mode
  (⚙ Settings > Editing & Compare) can change it.", the cause in the words of its `unproved_reason`: "this setting is
  not on this camera's menu, so no camera writes it" (Picture Profiles PP7 to PP9 on the a1 II), "this setting needs
  equipment the camera was not proved with…", "no menu choice tried on the camera changed this setting…", "this is a
  value the camera keeps for itself, not a menu setting", or, with no reason given, "this setting has not been checked
  on a camera yet". A copy or a recall leaves it as it is, says how many it left, and that Expert mode copies them.

A value the camera keeps in more than one record (`copies` and `copy_of` in the definition: a Picture Profile
parameter in use and its Stills and Movie copies, the Picture Profile in use, ISO, White Balance, ISO AUTO Max) is
changed as any setting is, and the editor keeps what the camera keeps. A copy is never part of its setting's row, even
where it shares its name and place: it is a row of its own, and its row, tile or cell says beforehand, in a note under
it (on the page too, and on hover in Compare, the Main tiles and the Memories page's arrows), what changing it changes.

- What follows an edit: the copies that held the setting's value in the file as opened or read, decided once per set
  for the session, whatever values the setting passes through. Changing such a copy changes its setting and the other
  copies in step, in one undo step, and outside Expert mode its Revert is its setting's: it never goes back alone
  ("Changing this changes Black Level and Black Level (movie) too, and reverting it reverts them: they held the same
  value when this file was opened or read, so the editor keeps them together. Expert mode (⚙ Settings > Editing &
  Compare) changes this one alone."). A copy that held another value is changed and reverted alone, and stays as it
  is when its setting changes. Whether the camera moves a family's Stills and Movie values together is a setting of
  its own that no proof has read yet, so the shooting mode never decides what follows.
- What is checked: where a set's shooting mode is known (the definition's `camera.live_mode` names the live record
  that says the mode the file was saved in; a memory set's mode is the one `camera.memory_sets.modes` lists it under)
  and the copies say whose mode they are (`copy_for`), the setting must equal the copy for that mode, as in every file
  a camera writes; where it is not known, it must equal at least one of its copies. An edit or a Revert that would
  break that is refused outside Expert mode, with why and what to do ("Not changed: this file was saved in Stills
  mode, and in Stills mode the camera always holds Black Level at the value of Black Level (stills), so a file where
  they differ is one no camera writes. Change or revert Black Level or Black Level (stills) instead: the two change
  together."); one that leaves a file opened so no worse, mends it, or puts it back as opened is made.

In Expert mode a copy changes alone (its setting still takes it along when the setting changes), and a file left
out of step is listed when it is saved or written. A copy whose record has another shape than mapped takes no value
(followed, taken along or put back), and the status line says so. Copying several rows at once (Copy all shown rows,
a merge, a whole memory's recall or register) gives each row the other file's value, a copy too, and leaves every
other record of the same value as it was, even one that held the same value in both files; a copy that would leave
the file other than the camera keeps it is refused, saying to copy the shooting-mode row too or to copy in Expert
mode, and a recall or register across shooting modes says the memory's mode and the file's, that the camera recalls
or registers a mode's memories only in that mode, and that Expert mode copies it all the same. Copying one row is an
edit of it. Where a Save As
kept a copy apart from its setting, "Back in step with …" puts it at its setting's value (its hover says so).
A copy of a setting the definition does not name is view only outside Expert mode, as the editor cannot keep the two
in step.

Where a Save As kept an edit, Revert has nothing to go back to, as the file as last saved holds it too: the detail
panel, Compare's menu, the page's row and the Write and Before saving windows then offer "Revert to what the camera
wrote", which puts back the value of the file as first opened or read. It is offered for view-only settings too, as it
only restores what the camera wrote.

Where the definition lists a setting's values by video system (`video_system_values`) and the file's header says which
one it was saved under, in the live settings the values of the other one are not offered (nor in Expert mode's "Offer
values…"), the page refuses one ("Not changed: 50p is offered only with the camera set to PAL, and this file was saved
with it set to NTSC. Choose one of the values offered."), Compare does not copy one in and says how many it left, and a
file holding one already shows it with a warning under the setting. The memory sets are left out of that rule, as the
camera's own files hold either system's values there. A file whose video system is not known offers every value.

The Write window says in plain words what changes on the camera compared with the last read; when the camera has
not been read since the editor started, it says that the write reads the camera first and lists the differences
after the restart. It says, in normal-size text, that writing replaces every setting on the camera and restarts it,
that an edited file once made a camera restart over and over, to save the camera's own copy to its card first, and
how long to leave the camera on and connected: its restart and then the check, counted from when it takes the file;
"⬆ Write to camera" is the main button, and Cancel holds the keyboard focus (Esc presses it).

The Write and Before saving windows then judge every record that differs from what the camera wrote: the file as
first opened, or as read from the camera, in this session, which a Save As does not move (an edit saved is still
judged); for a write, the camera's own copy read just before it too, the list made again once that read comes back,
so a file edited and saved in another session is judged as well. A record passes only when each setting covering its
changed bytes was proved on the camera with the value it now holds and none of them refuses, rewrites or never offers
that value; a copy passes while it holds its setting's value (one holding another is judged by its own proofs), and
bytes a mirror (`camera.mirrors`) keeps in step are judged where their copy is. Everything else is listed under what it is, in this order: "Edits the editor cannot check"
(edits recovered from an earlier session without the file as it was opened, which never get the all-clear), "The
camera may refuse or change these",
"Another video system's values" (also one the file held as opened, which has no Revert), "Copies out of step" (a
setting apart from the copy for its set's shooting mode, or where the mode is not known held by none of its copies, as
no camera writes a file so; listed whenever the file holds it, edited or not, and never for a copy for another mode
or a Stills copy apart from its Movie copy),
"Not checked on the camera", "Texts" and "Raw edits" (bytes no setting the editor changes covers), each with the Revert
that applies to it (Revert, "Revert to what the camera wrote", or "Put its copies back in step"); then, for a
write, "In the file as opened, not on the camera now": records that differ from the camera's own copy but not from the
file as opened, which the editor cannot check (the records the camera changes on every load, `camera.volatile_records`,
and the values it keeps for itself, `unproved_reason` "state", left out). Those are no edit of this session and have no Revert; they are not counted as flagged, but while any is
listed the all-clear does not show, and a sentence says how many and what to do (read the camera and make the edits on
that file, or write this one only if you know where it came from); with nothing else listed the button reads
"⬆ Write anyway". What the camera wrote unchanged, and what passes the check, is taken as it is. "✔ Every changed value was checked on the camera and is one it takes." shows only
when nothing is listed; with values listed the window says what to do (revert them, the safe choice; written anyway,
the camera may refuse the whole file or store other values), Revert puts back one and "Revert all flagged" all of
them, and the button says it goes ahead with them: "⬆ Write anyway, with 3 flagged", "Save anyway, with 3 flagged".
The web page's Write window lists them the same way, under the same headings.

A group's rows are laid out as on the camera when its definition says where each setting sits (the kit writes it
from the camera's menus and the proofs): the rows in the camera's order, a submenu's rows indented under the row that
opens it, a row of the camera with no setting of its own as a heading that folds what is under it (click it), the rows
the camera's menu has in another shooting mode only after the others, under that mode's name ("In Movie mode"), and
the settings the definition places nowhere last, under "More settings in this group". A whole group with no row on the
camera at all (the settings read through Sony's SDK that the menus do not show, the memories' exposure copies) is
not in its tab: the Menu lists those groups after the tabs, under "Not in the menus", by tab and group; a family's
table and My Menu's own settings stay where they are. A setting is shown in the group
whose page holds its row on the camera, so a screen the definition keeps as a group of its own (Recall Custom hold 1)
is under the row that opens it (Shooting Mode > Reg. Custom Shoot Set), a setting whose row is in another tab in
that tab (the Custom Key cells a definition keeps in Shooting under Setup > Operation Customize > Custom Key/Dial
Set.), and the tab's groups come in the camera's order, a group only the Movie menu has where that menu has it. A choice the camera shows beside one
option of a row, which Right opens on the camera (Drive Mode's continuous shooting speed beside Continuous Shooting,
White Balance's fine-tune beside its preset, a Creative Look's parameters beside the look), is no row of its own as on
the camera: only the row is, and its detail panel shows, under the option list, every choice of the option chosen now
(two, or eight), in the order the definition lists them, each in a box with its own control and Revert, plus any
choice of another option that is edited. An option with a choice of its own has "›" after its name, and one not
chosen says on hover what it opens ("Has a choice of its own: …"); Expert mode names them all above the boxes. The
group's count in the side bar counts the choices too (they are settings), and Only edited keeps a row whose choice is
edited. The search, F3, All edits, Compare and the edit history list a choice by its own name; opening it opens its
row with its box marked and in view. A choice whose row's own setting is not in the group (a search or Only edited
left it out, or another group holds it) is a row under that row's heading, as before. An option whose Right opens a
whole page of rows on the camera (Picture Profile's PP1 to PP11: Black Level, Gamma, Black Gamma > Range, Level,
Knee > Auto Set > …, Color Depth > R … Y, Detail > Adjust > …) has "›" too, but no boxes: while it is chosen, or under
the pointer, a link under it ("Open the PP1 page") opens that page, a group of its own listed after the group of its
row ("› Picture Profile PP1"), laid out as the camera's page, its rows' headings folding what is under them and the
stills and movie copies of a parameter side by side. The search, F3, All edits, Compare and the edit history open a
page's setting on its page; the family's table (Picture Profiles) still holds every profile's settings, and the Menu
counts each setting once. "Flat list", above the rows,
lists the group's settings in the definition's order instead, each setting in its own group and every choice a row
too (the detail panel still shows it beside its option); the editor remembers the choice, the setting chosen stays chosen, and the
arrow keys, F3, the search, Compare's Open in Edit, My Menu's links and the edit counts follow the layout shown, Not in
the menus included (the flat list has no such entry: every setting is in its tab). A
setting's name says, on hover, where it sits on the camera. A definition that places nothing has the flat list only.

Where the camera nests a setting's options (a carousel whose option opens a choice of its own: Focus Area's Spot opens
its sizes, Tracking its start areas), the detail panel lists them as the camera does, from the definition's option
tree: the main options, and under the one chosen, its choices. Choosing a main option keeps its choice when the value
already belongs to it, else takes its first; a choice is chosen as any option is, with the same help, colours, Revert
and "original" mark. The page shows the same as two lists, the choice's under the main one. Everywhere else (the
row's value, Compare, the exports, the search, the Memories page) the value keeps its flat name ("Spot: M"), and a
definition without the tree, or a list the camera shows flat, keeps the flat list.

## The Exposure page

The side bar's Exposure page shows aperture, shutter speed and ISO for the live settings and each memory on
aligned stop scales: who sets each side in that exposure mode, and the limits on what the camera may choose
(ISO AUTO range, ISO Range Limit, ISO AUTO Min. SS). Which records hold what comes from the camera definition
(`camera.exposure` in `data/ILCE-1M2_fw4.00/camera_ILCE-1M2_fw4.00.json`).

## Compare mode

Pick any sections of file A, file B and an optional base file as columns; the first column is the one the others
are compared with, and "Compare the others with this column" over another column makes that one first. A value that
differs from the first column's has a pale amber fill; your edits are orange, with a pencil and an outline, here as
everywhere in the window. Each row is one setting as the Edit page has it: the records the editor writes together
(Exposure Comp.'s three, Drive Mode's, a White Balance fine-tune's) are one row, which an arrow, a copy, the picker and
the Memories page's arrows change together, in the window and on the page alike; each Picture Profile's Black Level is
a row of its own under its profile's group ("Picture Profile PP3"), so copying it changes that profile only; and a
copy the camera keeps of a setting is never in that setting's row. "N of M settings shown" and the headings' counts
count those rows.
Columns are named by their file's letter and section (A · Live, A · Memory 1, B · Live, Base · Live), and the
Compare bar says once which file each letter is; B and Base carry a lock, as they are never changed.
F3 / Shift+F3 (or Alt+Down / Alt+Up) step through the differences, and the strip on the right is a change map
(click to jump). In a row that differs, a small arrow between two columns puts one column's value into the column
it points at (◀ into the left one, ▶ into the right one). Only file A takes values: between B and A the arrow
points into A, between two columns of A there are both, between B and Base there is none. A right-click on a value
puts it into any other shown column of file A, each entry with an arrow toward its column. With a base file open
(the file A and B both started from) a "Changes" column tags every row changed in A / changed in B / same change /
conflict, and B's non-conflicting changes merge into A with one button. An arrow, a copy, a merge or a recall leaves
alone a setting view only outside Expert mode (no arrow goes into it) and a value of another video system than file A
was saved with, and the status line says how many it left and why; a copy the camera keeps of a setting takes it
along as an edit does, and several rows copied at once each keep their own value. Tab and group headings fold, with how many of
their settings differ (Collapse all, Expand all; a jump to a difference opens its group). Only file A is ever
edited, and file B shows only here: Edit mode shows file A alone. When the files open were saved with the camera set
to different video systems, one line under the letters says which ("A on NTSC, B on PAL") and that settings depending
on the frame rates can differ for that reason alone.

A setting's name is a link: a click opens it in Edit, in the first column of file A that keeps it (else the live
settings), and the right-click menu of a value of file A has "Open in Edit: A · Memory 1" for that column's set.
Edit then shows "← Back to Compare", which returns to Compare with that row under the difference cursor; it goes
once you open another setting, group, page or set. The web page's Compare does the same.

A value of file A also changes in place: a click on it (or "Change…" in its right-click menu) opens, under the cell,
the choice Edit's detail panel offers for that setting in that column's set: its values (those no proof on the camera
has established only with Expert mode's "Offer values…", the ones the camera refuses marked), the main option and its choice where
the camera nests them, a number within its range or a text. The value chosen is set as from Edit, every record the
setting lives in together, so it is an edit like any other (orange, "was …" on hover, Revert in the menu and in the
choice, Undo, the write check). The row stays where it was, even once it no longer differs, until "Only rows that
differ" or the three-way filter changes. File B and the base never take a value. The web page's Compare does the
same, with the page's own control for the setting.

## The camera link

The camera button in the top bar (📷 USB, or 📷 Network and the camera's address; 📷 Set up the camera… before a link
is chosen) opens Connect to the camera. It shows the same cards as Settings > Camera link, in the same order, and
adds only "Connect and read from camera" at the bottom. While the camera link program is not found, a first card,
"First: the camera link program", says what it is, how `kit/setup.py` builds it, links to Sony's SDK page and
offers "Choose the program…"; Search and Connect stay off until it is there.

- Connection: USB cable or Network, and "🔍 Search for cameras" (`camset_probe discover` lists every camera the Sony
  SDK can see, USB and network; it usually takes 5 to 15 seconds). The cameras found are listed with "Use this one"
  first in each row to pick one, and a green line says when a camera is found and the setup is complete.
- Set the camera up like this: what the camera must be set to for the chosen link, from the camera definition,
  each step with a box that ticks itself when a search finds a camera. A new user needs these steps a few times,
  not on every connect: the card is open while the editor knows no camera, folds once a camera is found or known,
  and opens again after a search that finds nothing. Otherwise it stays as you left it; a click on its title opens
  or folds it.
- Known cameras: every camera picked after a search or connected to.
- Network address and camera login, only when Network is chosen: the camera's address, and the camera login (the
  user name and password set on the camera) with Save; the note under it says whether one is saved, "on this
  computer only" (the file's path on hover).
- Camera link program (camset_probe), in Expert mode or once one was chosen by hand: where the program is, found on
  its own or chosen.

"⬇ Read" and "⬆ Write…" then run `camset_probe` over that link. Where the editor says how long a read usually takes
(the Read button's hover, the welcome page's Read card, the progress line), it names the median of the last five reads
this computer made over the link in use, in whole seconds; before the first, the time the camera's definition gives
(`link_timing.read_s`).

The found-cameras table shows, after "Use this one" (first, so it shows at any window width without scrolling), each
camera's model (the camera's own name for itself on hover), link, your name for it, serial number and MAC address; it
fits the Connect and Settings windows at their default width, and a narrower window scrolls it sideways. A USB camera sends its serial and a network camera its MAC; the other is learned
the first time the editor connects to it (the helper prints `serial:`, `mac:` and `model:` after every connection), so
the same body is recognised over USB and over the network. Until then the cell says "not yet known", and its hover
says why. In Expert mode the Connection card also shows the helper's whole search output under "Details from the
camera link", below the found table, with the raw id the SDK gave for each camera (`id_hex`); after every connection
the helper says in a `note:` line when the camera did not list its serial number property, or listed it with no text,
and when the serial number was taken from the camera's id instead. A camera the search does not list but which
answers when asked at the address you entered shows "answered at its address" in its Link cell: its MAC address then
comes from this computer's own network table (the card that answered at that address), and its serial number once the
editor connects to it. Sony's API reference says the SDK names either a camera's wired or its wireless LAN card, by
model and not by the connection in use, so the two MAC addresses can differ; such a row is still taken as the camera
last met at that address, and picking it keeps that camera's MAC address. Type a name of your own in "Your name" (for
example "Studio camera"): the editor uses it wherever it names the camera, in the Camera link report ("Connected over
USB to Studio camera (ILCE-1M2)"), the status line, the Connection card's found line and the welcome screen's "Read
from camera". The Known cameras card lists every camera picked after a search or connected to, with name, model,
serial, MAC address, last link and address, and when it was last seen; Forget removes one, with its user name and
password and the trust in it (below).

Each camera's login is kept separately. Save writes the user name and password under the chosen camera's MAC
address in `~/.config/camset/network.json` (mode 600), beside one default pair for cameras without their own; it
writes the default pair when the camera's MAC is not known yet or the file has none. The editor passes the chosen
camera's MAC to the helper (`CAMSET_MAC`). The helper uses the first camera's own pair it finds, saved under the MAC
address the SDK names for the camera at the address, the one this computer's network table holds for the address,
or `CAMSET_MAC`, else the default pair, so a camera's own pair is used even when its search misses the camera.

A login goes only to a camera this computer trusts. At the first successful connection the helper keeps the
camera's fingerprint (its SSH host key) in `~/.config/camset/known_cameras.json` (mode 600), under the MAC addresses
the camera carries and its address; before every later login it compares the fingerprint the camera shows, and a
camera whose fingerprint changed gets no login: the Camera link window says it is not the one this computer trusted
before. After a reset of the camera's network settings, Forget it in Known cameras and connect again to trust it
again. The helpers also refuse a `network.json` that other users of this computer can read; Save makes it private.

Every camera action ends in a "Camera link" window that says what happened. A read names the model the helper found
and checks it against the file, compares the camera's file timestamp with this computer's clock ("The camera's clock and this computer's agree
(17:44)"; a gap is said as a caution, such as "differ by 12 hours", with the read still counting as fresh, since the
helper has just made the download: the camera's clock is what to set), and the file name's hover says
where it came from ("Read over USB at 17:44", or "Opened from disk").

Times are shown in words wherever the editor names one: "17:44" for today, "1 Jan 2026 at 00:00" for another day
("saved 1 Jan 2026 at 00:00", "last read 17:44"), from the stamp in the file's header or this computer's clock;
Expert mode adds the stamp itself ("20260101_000000"). The files the editor keeps are named by this computer's local
time: `camera_2026-11-05_17-44-05.DAT`. A failed read
says so and states that the file on screen is still the one from disk. A failed action says in plain words what
went wrong and what to do (no user name and password saved, or refused; a USB cable still in; no answer at the
address; no camera on USB), from the cause line the helper prints; the helper's own messages appear only in
Expert mode. After a send the editor waits for the camera to restart, reads its settings back and lists every
record that differs from the file sent (only the two load toggle flags are expected to). The camera definition's
`link_timing` sets the wait: the first read starts when the camera is usually back (`restart_s` after the upload;
"Camera restarting…" counts it down), a read that fails is followed by the next once `poll_s` has passed since it
began, and the editor gives up `timeout_s` after the upload. "Try again" on that report reads at once.

When the read-back confirms the write, a file read from the camera starts from that read-back: what is on screen is
what the camera holds, so nothing is left unsaved ("No edits", the edit marks gone, the copy kept in case the editor
stops removed), and the report says so; ↩ Put the camera back undoes the write. Edits made while the check ran stay
edits, and Undo still steps back (a step back is then an edit against what the camera holds). A file from disk is not
changed by a write, so its edits stay edits and stay marked, but while they are the ones the camera confirmed the
counter says "3 edit(s) on the camera, not saved to CAMSET01.DAT" and the question before they would be lost "Your 3
edits are written to the camera but not saved to a file"; a further edit, an undo or a save returns to the usual
words. A read-back that differs, or no answer, changes nothing. Putting the camera back follows the same rules: on a
file read from the camera, the edits the camera no longer holds show as edits again.

⬆ Write… reads the camera before it asks anything: the Write window opens with "Reading the camera, to list what this
write changes…", then shows "Compared with the camera now, this changes N settings:" with each one's value on the
camera and in the file, the warning and the edited values the camera may refuse, and only then offers Write to camera
and Cancel. A read that fails ends there, with the Camera link window saying why; nothing is written. Write to camera
keeps that read as the copy from just before the write; one older than five minutes is read again first. The web
page's Write does the same: its Write window says "Reading the camera, to list what this write changes…" while the
editor reads, then lists what the write changes against the camera now, and only then offers Write to camera; a read
that fails ends there with the Camera link report, and a read older than five minutes asks for Write again.

The window and the web page write by one rule: only a file the editor may edit (its firmware checked, or Edit anyway
turned on) of the model the camera definition is for, never the sample nor a file made from it (known by its header,
however it was opened), one camera action at a time, and only the
file the Write window checked (a file opened or edited meanwhile is refused). The copy read just before a write is
checked first: another model, another record layout or a copy cut short means nothing is written. Where the
definition's container block says where the video system is, the camera must also be set to the one the file was saved
under: the two use different frame rates, a camera numbers its frame-rate settings differently under each
([decision 8](decisions/0008-by-hand-only-usb-language-region-and-network-identity.md)), and nobody has yet tried what a
camera does with a file from the other, so the editor fails closed. Nothing is written, and the Camera link window
says, in the definition's words, "Nothing was written: the camera is set to NTSC, and this file was saved by a camera
set to PAL…", then what to do: read the camera and make the edits on that file, or open a file saved while the camera
was set to NTSC. The rule is one switch, `WRITE_ACROSS_VIDEO_SYSTEMS` beside `write_check` in `editor/src/camera/job.rs`,
for the window and the page alike; the owner may turn it on once a camera has been tried. A write counts as
done only when the camera confirms it; with no confirmation in time the window says the file may have been written,
keeps the copy from just before, offers "↩ Put the camera back" and runs the check.

## Going back

The editor never writes into a file it opened, and Save As writes whole files only (a temporary file, read
back, then renamed). It keeps a copy of every settings file as first opened, and of any file a Save As
replaces. Every write to the camera reads the camera first and keeps that copy; when the read fails, nothing is
written. After a write, "↩ Put the camera back" writes that copy again. File > 📂 Backups… lists every kept copy,
newest first, with Open and, while a file is open, "Compare with the open file", which opens the copy as file B.

Edits not saved yet are kept too, in case the editor stops: a couple of seconds after an edit, it writes the edited
file and the file as opened to its `recovery/` folder, and, when a Save As came between, the file as first opened or
read too, so the recovered edits are judged against it as before. When it closes as usual, or the edits are saved or the file is
closed, that copy goes. After a crash, a power cut or a forced quit, the next start says "The editor closed with 3
unsaved edits to CAMSET01.DAT" and offers "Open the recovered edits", which opens the file under its own name with
the edits on it, not saved yet, or "Discard". When the editor stops on an error it also writes a short `crash.log`
in its folder: when, the version, where in the program and the error's own words, with the home folder and the
user's name taken out. Send it with a few words on what you were doing to report the problem.

## What the editor keeps on this computer

Nothing the editor keeps leaves the computer: it has no account, sends no usage data and looks for no updates. It
talks only to the camera, through the camera link program, and, while the web page is on, to the browsers that
enter its access code. Its own folder is `camset_editor` in `$XDG_CONFIG_HOME`, `%APPDATA%` or `~/.config`; on macOS
and Linux only you can open it (mode 700), and its private files are mode 600. On Windows they are as private as
your user folder. Deleting the folder starts the editor afresh; the two files under `~/.config/camset` are the
camera link's, beside it. The folder is apart from the program's: on Windows the installer puts the program in
`%LOCALAPPDATA%\Programs\Camset Editor`, and neither installing a newer version over it nor uninstalling it removes or
replaces anything in the editor's own folder, nor a file you put beside the program yourself (the camera helper,
say). In the program's `definitions` folder, each install replaces the built-in definitions, the files named as the
shipped ones (`<model>_fw<firmware>.json` and `.DAT`), and nothing else. To start afresh after uninstalling, delete
the editor's own folder by hand.

| What | Where | What it holds |
| --- | --- | --- |
| Preferences | `camset_editor/prefs.json` | Theme, text size, the window's size and place, Expert mode and the other switches, the last files open and the recent files (their paths), the web page's port and switches (its access code is made each time it is turned on and kept in memory only), and the known cameras: your name for each, model, serial number, MAC address, last link and address, and when it was last seen. A damaged one is kept aside as `prefs.json.bad`. |
| Originals | `camset_editor/originals/` | A copy of every settings file as first opened, once per content (named by a hash of it), and of any file a Save As replaced. Settings files hold everything the camera keeps, the copyright and artist texts among it. |
| Camera copies | `camset_editor/camera/` | The camera's settings at each read (`camera_2026-11-05_17-44-05.DAT`), just before each write (`before_write_…`), read back after a write (`verify_…`), and each file sent (`SEND_…`), named by this computer's local time. Backups lists them with the originals. |
| Camera link log | `camset_editor/camera/probe.log` | The camera link program's output for every run, with the camera's address, serial number, MAC address and fingerprint; started again at 2 MB, the one before kept as `probe.log.1`. |
| Unsaved edits | `camset_editor/recovery/` | While a file has edits not saved, the edited file, the file as opened and a short description (the file's path, the definition, the time, how many edits); gone once they are saved, the file is closed or the editor quits as usual ([Going back](#going-back)). |
| Crash log | `camset_editor/crash.log` | Written only when the editor stops on an error: when, the version, where in the program and the error's words, without the home folder or the user's name. The next one replaces it. |
| Web page uploads | `camset_editor/camera/web/` | Each file sent up from the web page, under its own name in a folder named by the time it came; the latest twenty are kept, and one open now. |
| Your definitions | `camset_editor/definitions/` | The camera definitions you added with Add definition… ([Definitions](#definitions)). |
| Help text | `camset_editor/help/` | A help file put there by hand replaces a definition's help text for its camera, setting by setting; where it has none, the definition's own stays. |
| Camera logins | `~/.config/camset/network.json` | Each camera's user name and password, under its MAC address, beside one default pair; written by Save in Connect to the camera, read by the camera link program ([The camera link](#the-camera-link)). Mode 600. |
| Trusted cameras | `~/.config/camset/known_cameras.json` | The fingerprint of each camera this computer trusts, under its MAC addresses and address. Mode 600. |

## If the camera restarts over and over

The project has one such case on record. On 2026-11-01 a settings file changed by hand, outside the camera's menus,
was sent to an a1 II in Movie mode: it rewrote the Picture Profile settings, those of the profile Movie mode had in
use among them. The camera restarted to load it and then kept restarting in Movie mode
([decision 6](decisions/0006-no-hand-made-settings-files.md); `kit/tools/upload_check.py`).

- **What ended it:** Initialize, run by hand on the camera (MENU > Setup > Reset/Save Settings > Setting Reset >
  Initialize).
- **What Initialize costs:** far more than the shooting settings. In a test it changed every memory set and every
  menu setting tested (`data/ILCE-1M2_fw4.00/settings_reset_ILCE-1M2_fw4.00.json`), and it wipes the network setup, the
  access authentication and the FTP settings ([decision 5](decisions/0005-settings-resets-for-proofs-the-narrowest-never-initialize.md);
  [the playbook](REMAPPING_PLAYBOOK.md#9-working-with-the-owner), section 9). A settings file never holds the
  network's access settings, the language or the area and date ([the a1 II's page](models/ILCE-1M2_fw4.00.md), the
  Save/Load exclusions row), so those are set again by hand.
- **Then:** load the camera's own saved file from the card (Save/Load Settings > Load; [From the card and
  back](#from-the-card-and-back)).
<!-- maintainer: confirm whether Stills still started during the loop and whether the camera's own file loaded back after Initialize; neither is recorded in the repository -->

"↩ Put the camera back" cannot help here: it writes over the link, and a camera that keeps restarting does not
answer.

## The web page

Settings > Camera support & web page > Web page for a phone or tablet, off until turned on, starts a small web server
inside the editor, so a browser on another computer, a tablet or a phone can use the editor as its window is used: the
same pages, windows and switches, in the same words. For a camera far away on a network, run the editor on a computer
on that network and open the page from wherever you are. The page works on the file open in the editor, so edits show
in both, and it gives the same warnings before a write, including a file that would turn off the link to the camera.
The page asks once for the access code shown in Settings; the browser then keeps a session (below), and Sign out in
the page's Settings ends it. When the editor quits, the page says so. A request that would replace a file with unsaved
edits in the editor asks on the page first, as the window does.

The page has the window's Menu: Main, My Menu (its pages, Change…, Add here…, Remove and the moves as in the window),
the tabs (Picture Profiles and Creative Looks as one table each), Other and Not in the menus, Memories, Exposure and
All edits, and in Expert mode Unmapped records and the Record map; Compare takes file B and a base file. A click on a
setting's name unfolds what the window's detail panel says about it: its help, the shooting modes it applies in,
where it is kept, its records and My Menu (a right-click offers My Menu too), and for a row like Drive Mode every
choice of the option chosen now (and any edited one), each with its control, as no row of its own as on the camera; a
search lists a choice as a row with "Open beside …", which opens its row's details with the choice marked. A tab's
rows are laid out as the window lays them out, with "As on the camera" and "Flat list" beside the tab's name (the
editor keeps the choice, for its window too), and a link to a setting opens the group that shows it in that layout.
Its windows are the window's: Connect to the camera with the same camera cards, Settings, Backups, Edit history, the
Camera link report with Try again, Change connection and Switch to USB. Edit anyway is not among them: for a file of
a firmware not checked, the page says that it is turned on in the desktop app, beside the file's name, and once it is
there the page edits that file too. A file dialog becomes an upload or a download: Open… and Compare's B and Base
send a file up (kept in the editor's `camera/web` folder under its own name, in a folder named by the time it came,
so Download file offers the name it came with), Download file, Export CSV… and Describe for support… bring one down,
and Backups, Recent and the welcome page's sample open the editor's own files by request.

On the page, Compare works as in the window. File B and the base come from B: Open… and Base: Open…, or from a
file dropped on the page (with no file open it opens; otherwise it is compared as file B), and the window compares
them too. The page has the same column pickers, search, tab list, Only rows that differ, Show raw values and Record
map (these two in Expert mode), the arrows between columns, the menus of a cell or a column header (right-click, or touch and hold on a
phone), the three-way tags with Merge B into A and the two Conflicts buttons, Swap A/B, Collapse all and Expand
all, Previous and Next (F3 / Shift+F3 or Alt+Down / Alt+Up, and the buttons for a phone) and the change map at the
right. Every copy is an edit of file A, so Undo (kept on the top row in Compare), All edits and the edit count
follow it; Save A As is Download A. The page keeps its own columns, filters, folds and cursor: choosing them on
the page does not move the window's, nor the other way round.

Memories shows the mode dial's memories beside the live settings, a memory's value orange where it differs, with
⬅ and ➡ on the row to copy it either way, and "Recall … ➡ Live" and "Register Live ➡ …" for a whole memory, with
the window's hover texts in the camera's own menu names, and "Only rows that differ from Live" as the window has it. They copy the whole memory, whatever the search shows,
unless "Only the rows shown" beside them is ticked (it appears only while a search or a tab narrows the rows); the
message after the copy says what was copied. Each is an edit of the open file: one step to undo, and
listed in All edits. Opened with words in the search box, it lists the settings they match, as the window's does;
"Other memory sets" adds the file's other memory sets as columns (on the a1 II its Movie, S&Q and Time-lapse
memories), starting as the Settings switch "include Movie memories" has it. The Exposure page draws the same stop
scales as inline SVG: one tick per stop, a filled dot for a value you set and a ring for one the camera sets, the
shaded band where the camera may take it, and a bar at a one-sided limit; on a phone the columns stack. "Show in
menu" opens the setting in its tab, and the proof line shows only in Expert mode, while Settings turns it on.

The page's Settings has three kinds of switch. How values are shown (the record number, the proof line and the stored
number, under Expert mode as in the window, the layout, and Compare's two starting choices) are the editor's own: changing one changes the window too. Theme, text size and row spacing are the
page's own, kept in that browser, since a phone wants other sizes than the computer. The rest is shown as it stands
and set in the desktop app, marked "(set in the desktop app)": what opens what can harm the camera (Expert mode and
its two options, Edit anyway, and the copy kept before Save As replaces a file), what lives on the editor's computer
(the camera link program, chosen with a file dialog there, the camera definitions, added there with Add
definition…, reopening the last files, mode and page at start, the window's own theme and zoom), and what would cut the page off (the web page's
port, access code and on/off). The camera cards are the window's, with three limits: an address is picked among
those the editor has met a camera at (a new one is typed in the desktop app, or found with Search), the camera
login is entered in the desktop app only, and Forget takes the camera off the list only, its login and the trust
in it staying until Forget in the desktop app.

It is plain HTTP: anyone on the same network, a café's or an event's Wi-Fi included, can read the access code as it
is entered and the settings the page shows. Whoever has the code can change settings and write them to the camera,
but cannot turn on what can harm it: Expert mode, raw edits, values not checked on the camera yet and Edit anyway are
set in the desktop app only, which also keeps the camera's user name and password (the page's Connect to the camera
says whether a pair is saved, and never sends one across the network), and the page cannot point the camera link at
an address the editor has not met a camera at. The code is new each time the page is turned on and is kept nowhere;
a browser that enters it stays logged in until 12 hours pass without its use, and New code or turning the page off
logs every browser out. Turned on by hand with "from the network", the page listens on this computer's address on
its network; turned on as the editor starts, it is for this computer only. It answers only requests sent to that
address or this computer's name, from its own page, and counts wrong codes per device, so another device cannot
lock you out. On a network you do not trust, or across the internet, choose "this computer only" and use an SSH
tunnel (`ssh -L 8642:127.0.0.1:8642 that-computer`, then open `http://localhost:8642`) or a VPN rather than opening
a port. The first time it listens on the network, macOS or Windows may ask whether to allow incoming connections.
The page itself is `editor/web/`, built into the program.

For tests and screenshots only, `CAMSET_WEB_CODE_FILE=<path>` in the editor's environment makes it write each new
access code to that file (readable by this user only), so a script can sign in to the page. Never set it for real use:
without it the code is kept nowhere but in the editor's memory.
