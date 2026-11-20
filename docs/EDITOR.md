# Using the editor

Camset Editor opens the settings file a Sony camera saves to its card (`CAMSET*.DAT`), shows every setting by name,
lets you change them, compares two files and writes a file back to the camera. Downloading and installing it, and the
camera helper it needs to talk to a camera directly, are in the README,
[Use the editor](https://github.com/camset-dev/camset#use-the-editor). To only look inside a file, the
[definition viewer](viewer/) does it in a browser, with nothing to install.

Most buttons, settings and messages explain themselves where you meet them: hold the pointer over one (a phone or
tablet shows no hover text). This page says what the app cannot tell you at that point.

!!! warning "At your own risk"

    --8<-- "README.md:warning"

## First run

### From the card and back

The editor needs nothing but the settings file the camera saves to its card. On the ILCE-1M2 (a1 II):

1. **Save on the camera:** MENU > Setup > Reset/Save Settings > Save/Load Settings > Save. The camera writes a
   `CAMSET*.DAT` file into the card's `PRIVATE/SONY/CAMSET` folder. Copy it to your computer and keep it untouched:
   it is your backup, to load back if anything goes wrong.
2. **Open and edit it:** Open… (it starts in a mounted card's `PRIVATE/SONY/CAMSET` folder), make your changes, then
   Save As…. The editor never writes into the file it opened, and Save As… offers the next free name the camera would
   give (`CAMSET02.DAT` after `CAMSET01.DAT`).
3. **Copy the new file to the card,** into the same folder. The a1 II lists at most 10 settings files there, and the
   status line warns when the folder holds more. Keep a name like the camera's own (`CAMSET*.DAT`): whether the camera
   lists a file under another name is not yet tried.
4. **Load it on the camera:** MENU > Setup > Reset/Save Settings > Save/Load Settings > Load, and choose the file.

Loading an edited file from the card is not yet tried: the project's tests sent edited files over the camera link.
Read the warning above, and [If the camera restarts over and over](#if-the-camera-restarts-over-and-over), before you
load or write an edited file. With the camera helper set up, ⬇ Read and ⬆ Write… read and write the camera over USB
or the network ([The camera link](#the-camera-link)). Still do step 1 first: if the camera ever keeps restarting, the
file it saved on its card is what you load back.

### The welcome screen

The editor opens on three ways in: Read from camera, Open a settings file and Explore a sample. The sample is one
camera's file with its personal text taken out, there to try the editor. You may edit and save it, but the editor
never writes it, or a file saved from it, to a camera, and you should never load it on one.

A file from a firmware the editor has not been checked against opens view only ("⚠ firmware 3.00 not checked: view
only"). Describe for support… saves a description of how the file is laid out, without your settings, so that
firmware can be added. Edit anyway… turns editing on for the settings that firmware keeps where the editor expects
them; the camera may then refuse or change a value. A file from a model no definition covers opens view only, its
values greyed.

### Definitions

What the editor knows about a camera comes from its definition, one file per model and firmware. It reads two
folders:

- **Built-in:** the definitions that come with the editor, beside the program (inside the macOS app). Each install
  replaces them.
- **Yours:** `definitions/` in the editor's own folder ([where it is](#what-the-editor-keeps-on-this-computer)). A
  definition here is used instead of a built-in one of the same model and firmware.

A file opens with the definition of the model and firmware its header names. A file from the same model on another
firmware opens view only with the nearest firmware's definition, which the editor says beside the file's name;
Edit anyway… (above) turns on the settings that firmware keeps in the same place.

Settings > Camera support & web page lists every definition, with Add definition… (it checks the file, then copies it
into your folder), Open folder (to remove one) and Reload.

## Seeing and changing settings

A click on a setting shows its details: Camset's description, the shooting modes it applies in, whether the memories
store it, and its values. A value is shown by its name; "7 (no name yet)" means the file holds a value that no choice
on the camera wrote when the project tested this setting, so it has no name yet. An edited value is orange, and Revert
puts it back. The keyboard shortcuts are in Settings > Appearance.

**What you can change.** A setting can be changed only where a test on the camera (a proof) showed that the camera
takes its values. Every other setting is view only and says why under it, for example "View only: this setting has
not been checked on a camera yet, and the camera may refuse a file where it was changed."

**Expert mode** (Settings > Editing & Compare) is for mapping work and support. It shows what a photographer rarely
needs (settings with no name yet, the copies the camera keeps, every memory, record numbers, raw values), lets you
change the view-only settings, and with "Offer values…" lists values not yet checked on the camera, in italics. The
camera may refuse a whole file that holds such a change. The checks before a save or a write still list every one. A
record no setting names is "unmapped": the mapping found no menu row that changes it, so it does not know what the
record holds, and a change to it is not proved on the camera and is at your own risk.

**The camera's menu in each shooting mode.** Where a camera's definition lists the menus of its shooting modes (Still,
Movie and S&Q, say), the Menu shows one at a time, picked under Camera menu: as the camera's switch picks it: its tabs,
groups and rows in that menu's order, each row titled as the camera draws it there (its details give the setting's
full name). It opens on the mode the file was saved in, and picking another changes nothing in the file. The Editing:
row offers that mode's memories, the search looks in every menu, and a jump to a setting opens the menu that shows it.
In the flat list (Settings), and for a definition that lists no menus, every setting is shown as before.

**Settings the camera keeps twice.** The camera keeps some values more than once: on the a1 II, ISO, White Balance
and each Picture Profile parameter have a copy for stills and one for movies. In a camera menu (above) the row of
such a setting shows the value of that menu's mode, and changing it changes the other menus that held the same value
when the file was opened or read, as the camera keeps a value it shares between modes. The row's note names those
menus before you change it, and says how to change one mode's alone; elsewhere, and in Expert mode, each copy is a row of
its own. A copy has a note saying what changing it changes. Outside Expert mode the editor keeps them as the camera does: a copy
that held its setting's value when the file was opened or read changes with it, and an edit that would leave a file
no camera writes is refused, with why and what to do. Some cameras have a switch that keeps a setting apart for stills
and movies (the a1 II's Different Set for Still/Mv). While it is on, the setting says what the switch did on the
camera, but the editor does not follow it. Where turning it off set the setting to a value of the camera's own when it
was tried, the editor asks first: do as the camera does, change the switch only, or cancel.

**Two limits kept in order.** Some settings are the two ends of one range: on the a1 II, ISO Range Limit (lower) and
(upper), and ISO AUTO's Minimum and Maximum. The camera never keeps the lower above the upper: a value chosen past the
other moves the other to it. The editor does the same, in every place the camera keeps that limit and in each memory,
and the status line says what moved; the note under each limit says so beforehand, and where the camera was not seen
to move it that way, that it was not tried. A pair a file holds out of order is marked under the two settings and on
the Exposure page, which shows the two as the file holds them and draws no band for them.

**Frame rates and the video system.** Where a setting's values depend on whether the camera was set to NTSC or PAL,
the editor offers only those of the system the file was saved under, and warns under a setting that holds a value of
the other.

**My Menu** shows your My Menu pages as the camera does: Remove, the arrows, Change… and Add here… edit them, and a
right-click on a setting adds it. **Memories** shows memories 1, 2 and 3 beside the live settings, with arrows to copy
one setting either way, and "Recall Memory 1 ➡ Live" and "Register Live ➡ Memory 1" for a whole memory.

### Before you save or write

A value nobody has seen the camera take may make it refuse the whole file or store another value, and a file edited
outside the camera's menus once made a camera restart over and over. So the Before saving and Write windows list every
changed value the editor cannot vouch for: values the camera was seen to refuse or change or its menus never offer,
values of the other video system, copies out of step, a setting kept in several places that an edit left naming
different values, two limits out of order, values not checked on the camera (which Expert mode lets you set), texts
and raw edits, edits recovered without the file as opened, and, before a write, anything in the file that differs from
the camera now but was not edited in this session. An edit of this session has its Revert, two limits out of order a
button that puts them back in order as the camera would, and Revert all flagged takes every such fix: that is the safe
choice. What the file already held when you opened it has no
Revert: to be sure, read the camera and make your edits on that file. You may still go ahead with "⬆ Write anyway,
with 3 flagged" (or "Save anyway"), but the camera may then refuse the whole file or store other values. "✔ Every
changed value was checked on the camera and is one it takes." shows only when nothing is listed. Some lists are proved
partly on another setting that offers the same list: one key's functions chosen on the camera, the same list lent to
the other keys. Their values are offered as any proved value, but the editor cannot tell which of them were chosen on
the setting itself, so it never calls them checked on the camera: where you changed one, the all-clear reads "✔ Every
changed value is in a list proved on the camera, and none is one it is known to refuse. Some of the settings you
changed had part of their list proved on another setting with the same list (another key, slot or copy of the same
kind), not on the setting itself.", and in Expert mode the setting's proof line says "partly on another setting of the
same kind". Once a Save As has kept an edit, "Revert to what the camera wrote" puts back the value of the file as first
opened or read.

### About, and reporting a problem

Settings > About (or a click on the version at the right end of the status bar) says which version you have.
Copy details copies the version, the system and the cameras, with no file, folder, user name or network address, to
paste into a report; Report a problem opens the project's issue page. The window works with the computer's screen
reader (VoiceOver, Narrator, Orca), though it has not been tried with each yet.

## Compare mode

Compare shows two files side by side, and a third, the base, when both started from it. Open file B with B: Open…
(and the base with Base: Open…), and pick which part of each file, the live settings or a memory, makes a column.
File B and the base must be from file A's camera model, or they are refused; one from another firmware of that model
is compared, with a line saying that a setting the other firmware keeps elsewhere can show a wrong value, and that
only the settings in the same place in both files are copied into A.

Compare has Edit's Menu on its left, with All settings first: a click shows that entry's rows, and each entry counts
the rows that differ. Where the definition lists the camera's menus, Compare follows the one picked: its rows are
grouped as Edit shows them in that menu, each shows that menu's mode's value in every column, so two files saved in
different modes are compared like for like, each menu's button counts its differences, and the column picker offers
that menu's memories.

Only file A is ever changed. An arrow between two columns copies a value into file A, a right-click on a value copies
it into any other column of file A, and a click on a value of file A changes it in place, as in Edit. With a base file
open, a Changes column tags each row changed in A, changed in B, the same change or a conflict, and Merge B into A
takes B's changes that do not conflict. A copy or a merge leaves alone settings that are view only and values of
another video system, and the status line says how many it left. When the files were saved with the camera on
different video systems (NTSC and PAL), a line says so: settings that depend on the frame rate can differ for that
reason alone.

## The camera link

Reading and writing the camera directly needs the camera helper (`camset_probe`), a small program built on Sony's
Camera Remote SDK. The editor's download does not include it: you download the SDK from Sony yourself and build the
helper with `kit/setup.py` (the README, [The camera helper](https://github.com/camset-dev/camset#the-camera-helper)).
Until it is found, the Read card says so and shows how to set it up.

The 📷 camera button opens Connect to the camera. Choose USB cable or Network, press 🔍 Search for cameras (usually 5
to 15 seconds), then Use this one beside your camera. "Set the camera up like this" lists what the camera must be set
to for that link and ticks each step once a search finds it. Leave the camera on the shooting screen; for the network,
take the USB cable out, as the camera does not answer on the network while it is in. You may give the camera a name of
your own (Your name), which the editor then uses wherever it names it.

Over the network the camera asks for the user name and password set on it: type them under Camera login and press
Save. The editor keeps them in `network.json` ([where](#what-the-editor-keeps-on-this-computer)), never in a settings
file. Save keeps the pair under the camera's MAC address when the editor knows it, and also as the default pair, sent
to every camera without a pair of its own, when the MAC address is not known or no default pair is saved yet: the
first login you save becomes the default. A connection uses the camera's own pair when one is saved under the MAC
address the camera gives, the one this computer's network table holds for its address, or the one the editor knows
for the camera you chose, and the default pair otherwise. On macOS and Linux the camera link refuses a `network.json`
that other users of this computer can read; Save makes it private.

A login goes only to a camera this computer trusts. At the first successful connection the helper keeps the camera's
fingerprint (its SSH host key); before every later login it compares it, and a camera whose fingerprint changed gets
no login: the editor says it is not the camera this computer trusted before. A reset of the camera's network settings
changes the fingerprint: then Forget the camera in Known cameras, which also removes its saved login, and connect
again to trust it again.

Every camera action ends in a Camera link window that says what happened and, when something failed, why and what to
do, with Try again.

**Writing.** ⬆ Write… first reads the camera and lists what the write changes compared with the camera now, with the
checks in [Before you save or write](#before-you-save-or-write), and only then offers ⬆ Write to camera; if that read
fails, nothing is written. Writing replaces every setting on the camera, memories and custom keys included, and the
camera restarts. Leave it on and connected: after the restart the editor reads the camera back and lists every record
that differs from the file sent, and a write counts as done only when that check confirms it. "↩ Put the camera back"
writes the copy read just before the write. The editor writes a file only to a camera of the same model and firmware
as the file, only a file it lets you edit, and never the sample or a file saved from it. A file saved with the camera
set to PAL is never written to a camera set to NTSC, or the other way round: the two number their frame rates
differently and nobody has yet tried what a camera does with such a file, so nothing is written and the window says
what to do instead.

## Going back

The editor never writes into a file it opened, and keeps a copy of every settings file as first opened and of any
file a Save As replaces. Every write keeps the camera's settings as read just before it. File > 📂 Backups… lists every
kept copy, newest first, with Open and "Compare with the open file".

Edits not saved yet are kept too: after a crash, a power cut or a forced quit, the next start offers "Open the
recovered edits" or Discard. When the editor stops on an error it writes a short `crash.log` in its folder: when, the
version, where in the program and the error's words, without your home folder or user name. To report the problem,
send it with Settings > About > Copy details and a few words on what you were doing.

## What the editor keeps on this computer

Nothing the editor keeps leaves the computer: it has no account, sends no usage data and looks for no updates. It talks
only to the camera, through the camera helper, and, while the web page is on, to browsers that enter its access code.

Its own folder, `camset_editor`, is `~/.config/camset_editor` on macOS and Linux, readable by you alone, and
`%APPDATA%\camset_editor` on Windows, as private as your user folder (on any system, `$XDG_CONFIG_HOME/camset_editor`
when that is set). The camera link's two files are in `~/.config/camset` (on Windows, `.config\camset` in your user
folder). Deleting the editor's folder starts it afresh. Installing a newer version or uninstalling the editor leaves
this folder as it is, and `~/.config/camset` with the saved passwords too: delete them yourself to remove them.

| What | Where | What it holds |
| --- | --- | --- |
| Preferences | `camset_editor/prefs.json` | Theme, window, switches, recent files, the web page's port, and the known cameras (your name for each, model, serial number, MAC address, address, when last seen). |
| Originals | `camset_editor/originals/` | A copy of every settings file as first opened, and of any file a Save As replaced. Settings files hold everything the camera keeps, the copyright and artist texts among it. |
| Camera copies | `camset_editor/camera/` | The camera's settings at each read, just before each write and after it, and each file sent. Backups lists them with the originals. |
| Camera link log | `camset_editor/camera/probe.log` | The camera helper's output, with the camera's address, serial number, MAC address and fingerprint. |
| Unsaved edits | `camset_editor/recovery/` | While a file has unsaved edits: the edited file and the file as opened; gone once saved or closed ([Going back](#going-back)). |
| Crash log | `camset_editor/crash.log` | Written only when the editor stops on an error. |
| Web page uploads | `camset_editor/camera/web/` | Files sent up from the web page; the latest twenty are kept. |
| Your definitions | `camset_editor/definitions/` | The definitions you added ([Definitions](#definitions)). |
| Help text | `camset_editor/help/` | A help file of the camera's own words, put there by hand, used in place of the definition's help for its camera. |
| Camera logins | `~/.config/camset/network.json` | Each camera's user name and password, under its MAC address, and one default pair ([The camera link](#the-camera-link)). **The passwords are in plain text, not encrypted:** only the file's permissions protect them (readable by you alone on macOS and Linux, as private as your user folder on Windows). |
| Trusted cameras | `~/.config/camset/known_cameras.json` | The fingerprint of each camera this computer trusts. |

## If the camera restarts over and over

The project has one such case on record. On 2026-11-01 a settings file changed by hand, outside the camera's menus,
was sent to an a1 II in Movie mode: it rewrote the Picture Profile settings, among them those of the profile Movie mode
had in use. The camera restarted to load it and then kept restarting in Movie mode.

- **What ended it:** Initialize, run by hand on the camera (MENU > Setup > Reset/Save Settings > Setting Reset >
  Initialize).
- **What Initialize costs:** far more than the shooting settings. In a test it changed every memory and every menu
  setting tested, and it wipes the network setup, the access authentication and the FTP settings. A settings file
  never holds the network's access settings, the language or the area and date
  ([the a1 II's page](models/ILCE-1M2_fw4.00.md), the Save/Load exclusions row), so set those again by hand.
- **Then:** load the camera's own saved file from the card (Save/Load Settings > Load; [From the card and
  back](#from-the-card-and-back)).
<!-- maintainer: confirm whether Stills still started during the loop and whether the camera's own file loaded back after Initialize; neither is recorded in the repository -->

"↩ Put the camera back" cannot help here: it writes over the camera link, and a camera that keeps restarting does
not answer.

## The web page

Settings > Camera support & web page > Web page for a phone or tablet, off until you turn it on, starts a small web
server inside the editor, so a browser on a tablet, a phone or another computer can use the editor as its window is
used: the same pages, windows and warnings, on the file open in the editor, so edits show in both. For a camera far
away, run the editor on a computer on the camera's network and open the page from wherever you are. Open the address
shown and enter the access code beside it. The code is new each time the page is turned on and is kept nowhere; a
browser that entered it stays signed in until 12 hours pass without use, and New code, Sign out or turning the page
off ends that.

What could harm the camera or cut the page off is set in the desktop app only, and the page marks it "(set in the
desktop app)": Expert mode, Edit anyway, the camera's user name and password (the page never sends them), the camera
definitions, a camera address the editor has not met a camera at, and the web page's own switches.

The page is plain HTTP: anyone on the same network, a café's or an event's Wi-Fi included, can read the access code as
it is entered and the settings the page shows, and whoever has the code can change settings and write them to the
camera. On a network you do not trust, or across the internet, choose "this computer only" and reach the page through
an SSH tunnel (`ssh -L 8642:127.0.0.1:8642 that-computer`, then open `http://localhost:8642`; 8642 is the page's port
unless you changed it) or a VPN, and never open its port on a router. The first time the page listens on the network,
macOS or Windows may ask whether to allow incoming connections.
