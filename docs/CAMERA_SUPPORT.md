# Which cameras the kit can work with

The kit drives a body through Sony's Camera Remote SDK. What it needs from a body is not a network
port. It needs four SDK features:

- **settings-file download and upload:** every proof and every restore;
- **button presses** (`CameraButtonFunction`): every menu walk and every proof;
- **dial turns** (`CameraDialFunction`);
- **the OSD image** (`GetOSDImage`): the camera's own screen through the SDK, the kit's eyes when there is no HDMI
  capture dongle (QUICKSTART's baseline; a dongle is optional and faster).

Sony lists the models the SDK supports on its public SDK page,
<https://support.d-imaging.sony.co.jp/app/sdk/l/index.php>. Which of these features each model has is in the SDK's
API Reference, which may not be redistributed (`RELEASING.md`), so this page does not say; check your own body
as below. These docs state only what the project observed itself or what Sony publishes openly.

## The short answers

- **Check your own body.** `.venv/bin/python kit/tools/sdk_support.py --json` builds the support table from your own
  copy of the SDK into `private/data/sdk_support.json` (`.cache/` when there is no `private/data/` folder). Then
  `.venv/bin/python kit/tools/body_check.py --model ... --link ... --eyes ...` reads it and answers with what the kit
  can do with that body, and names anything missing (`QUICKSTART.md`, step 1). Run `sdk_support.py` again when a new
  SDK version arrives.
- **What its answers mean:**
  - **Everything** (settings files and button presses): walk, prove and restore.
  - **Settings files only** (no button presses): the editor works (download, edit, upload). Mapping means a person
    pressing the buttons while the kit watches and downloads after each step (`kit/tools/hdmi_watch.py` records the
    screens; `kit/tools/upload_check.py --diff` shows what changed). That is slow but sound.
  - **Nothing** (no settings-file transfer and no button presses): files would have to move on a card, through the
    camera's own Save/Load Settings.
  - **No dial turns:** rows driven by a dial (Var. Shutter speed and the like) stay by hand.
  - **No OSD image:** the kit needs an HDMI capture dongle to see the screen.
- **Ethernet is not needed.** USB carries everything the kit uses (`CAMSET_USB=1`), as the a1 II's
  tests over USB showed ([its page](models/ILCE-1M2_fw4.00.md), "Connection and capture"). Whether a body has an
  Ethernet port, or takes one through a USB-C LAN adapter, `body_check.py` says for yours, from the SDK's own tables.
- **HDMI:** micro-HDMI bodies (a7CR, a7C II and others) work with a micro-to-full HDMI cable into the capture dongle.
  Bodies with the OSD image may not need HDMI at all (below).

## Menu system

The screen readers were built on the a1 II's menu: the 2021-and-later menu, also on the a7S III, a7 IV, a7R V, a7C II,
a7CR, a9 III, FX3 and FX30. Bodies with the older menu (a7R IV/IVA, a7C, a9 II) would need readers of their own. For
the newest bodies (a7 V, a7R VI), check the screens with `kit/tools/selftest.py` and `kit/tools/hdmi_watch.py` before trusting the
readers (playbook, "New model: first day").

## The camera's menus must be in English

The kit's screen readers and menu trees were built on the camera's English menus. The camera's language setting is
changed by the owner's hand ([decision 8](decisions/0008-by-hand-only-usb-language-region-and-network-identity.md)), so
set the camera to English before mapping; the menu tree then records English labels. Other languages are not supported
yet.

## Without an HDMI capture dongle

On a body with the OSD image, the camera can send its own screen through the SDK, so no capture dongle is needed. Set
`"eyes": "osd"` in `private/config.json`, or `CAMSET_EYES=osd` for a single command. Every scan, walk, crawl and proof
then watches the OSD. It was tested on the a1 II in Movie mode on 2026-10-30; the results are on
[its page](models/ILCE-1M2_fw4.00.md), "Connection and capture".

**Things to know:**
- **Scan the menu in OSD mode too.** OSD frames do not match a scan made over HDMI, so a run's eyes and its scan must be
  the same kind.
- **Speed:** the OSD is slower than HDMI (the a1 II's figures are on its page).
- **What HDMI still gives:** speed, and the only view of the screen on bodies without the OSD image, including those
  where a person presses the buttons.
- **Black HDMI frames.** Some settings black out HDMI (Auto Framing, a Framing Stabilizer preview, the rear screen
  folded in). Over HDMI the kit falls back to the OSD for those; in OSD mode the problem doesn't arise.

## SDK limitations seen on the a1 II (Camera Remote SDK 2.02, not camera firmware)

| Date | Behaviour |
|---|---|
| 2026-10-22 | `ExposureProgramMode` cannot be set even with Mode Dial Control Set = Set with Menu; the menu's Shoot Mode item works. `FocusMode` behaves the same way. |
| 2026-10-22 | String properties (`SoftwareVersion`, lens names) report a numeric value of 0; the text is only available through `GetCurrentStr()`. |
| 2026-10-22 | While the camera is connected for Remote Shooting, some menu items refuse to change ("Connected to Remote Shooting. Cannot be executed."): Power Save Start Time, Wi-Fi Frequency Band, Wi-Fi Direct Settings. |
| 2026-10-21 | Settings downloads are refused while the mode dial is on memory positions 1-3. |
| 2026-10-21 | Uploading a settings file restarts the camera. |
