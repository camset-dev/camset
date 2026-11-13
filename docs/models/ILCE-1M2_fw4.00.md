---
render_macros: true
---
# ILCE-1M2 (a1 II), firmware 4.00

The page for this body and firmware: what was measured on it and how it behaves. It is named by its definition,
`editor/definitions/ILCE-1M2_fw4.00.json` (`layouts[].doc`), and by `kit/tools/identify.py`. It states what the camera
does; when, how and from which state each finding was made is the mapper's own evidence, not published
(decision 16). For another body, read it as hints, never as proof.

Camera: ILCE-1M2, body firmware 4.00 (SDK `SoftwareVersion`). A finding that depends on the lens names the lens its
proof was made with.

{{ appendix_measured() }}

## Connection and capture

- **Network:** Wired LAN at 1000BASE-T, with SSH access authentication, from Terminal.app (Local
  Network privacy). Wi-Fi was not used.
- **USB-C:** the same SDK commands work, including download, upload and button presses
  (`CAMSET_USB=1`). The whole Initialize test ran over USB: download, upload and restore. Remote Shooting serves one
  link at a time, so unplug USB to use the LAN (the Network remote and USB row). With the rear screen folded in, HDMI
  goes black and the camera refuses the remote session.
- **HDMI:** a full-size port, through an Elgato Cam Link 4K at 1080p59.94, cropped (150, 0, 1620,
  1080) to 640x480. HDMI follows the movie format in Movie mode; HDMI Resolution set to Auto gives
  2160p29.97, which the capture cannot open.
- **OSD:** the SDK's OSD image is a usable second pair of eyes (about 0.8 s for the first grab).
  It cannot be matched against a scan made over HDMI. As the only eyes, in Movie mode:
  - the page scan makes one full lap, the same pages as over HDMI, about a fifth slower;
  - the page model confirms every label: OCR runs letters together a little more on OSD frames, and the vision
    model's reading settles each one;
  - a crawl walks a row with 0 records changed;
  - proofs match the HDMI proofs and restore to 0 differences;
  - a proved option takes about 14 s against about 8 s over HDMI: roughly 1.8 times slower.

## Screens and readers

- **The 2021-and-later menu system:**
  - tabs Main, Shooting, Exposure/Color, Focus, Playback, Network, Setup;
  - the number of pages differs by mode (stills has more than Movie and S&Q) and by the settings, which show and hide
    rows, so a page number alone names no item (the Menu paging row);
  - Main tile pages that differ by mode.
- **Held vertically,** the shooting screen and dialogs turn; the menus don't. The keys follow the
  turned picture.
- **Screens that needed readers of their own:**
  - assignment tables and pickers;
  - checklists, the White Balance grid, Creative Look panels;
  - scales (AF Transition Speed and the like), two-box screens (S&Q and Time-lapse frame rates);
  - turned dialogs.

## The file

- **Volatile:** of the records ignored as volatile (above), 0x0C46 and 0x1672 change on every save, and 0x04E2 follows the
  camera's position (the Switch V/H AF Area row).
- **Not set by a file:**
  - the fourth slot of 0x18cb (the Recall Custom hold row);
  - 0x1126 (unknown camera state; resets set it to 7: the Setting Reset row);
  - Remote Shooting while it is in use;
  - in every memory set: 0x023c (filled), 0x11ab (stills registration) and 0x11ad (stills exposure mode): the Camera
    Set. Memory and Memory sets rows.
- **First use:** the S&Q and Time-lapse exposure modes (0x13e2, 0x13e3) and Rating Set's second copy of each box
  (0x16bd-0x16c1: the Rating Set(Custom Key) row).
- **The mode dial:** 0x10b6 is the mode in use (P 1, A 2, S 3, M 4). Movie, S&Q Motion and
  Time-lapse each keep their own record (0x13e1, 0x13e2, 0x13e3), numbered P 2, A 3, S 4, M 5.
- **Not in the file:** the FTP settings (their own file), Copyright Info's on/off and text, Var. Shutter speed, the AF
  point (outside memory registration), the Fn overlay's cursor, and the live aperture and shutter speed. Sony's own list
  is the Save/Load exclusions row.

## Firmware bugs

Entries go here only when the behaviour reproduces on the camera by itself, without our tools. Anything caused by our
testing (automated button presses, OCR misreads, SDK sessions) does not count, and is noted under "Not bugs" so it
isn't mistaken for one later.

None found so far.

## Camera behaviour worth knowing (by design, not bugs)

| Area | Behaviour |
|---|---|
| C4 (the trash button) | On the shooting screen C4 does whatever Custom Key assigns it; it acts as the trash button, deleting, once a picture is displayed. The kit sends C4 on neither screen (decision 7). |
| Header: video system | Header byte 0x38 is the video system, not a firmware digit: 0 on NTSC and 1 on PAL. A file saved right after NTSC/PAL Selector is switched differs from the one before only there, in the save time's digits and in the header checksum (0x39). The firmware is 0x36-0x37 (major, then minor), and the layout fingerprint, which feeds 0x36-0x37 only, is the same on both systems. The container block names the two apart (`video_system`, docs/DATA_CONTRACTS.md); the editor shows the video system beside the firmware and writes a file only to a camera set to the same one. |
| Frame rates under PAL | With NTSC/PAL Selector set to PAL (by hand, decision 8), every frame-rate list offers the PAL rates, and each is stored one code above its NTSC counterpart: the NTSC list shifted by one (50p one above 60p, 25p above 30p, 100p above 120p; S&Q's Frame Rate 100, 50, 25, 12, 6 and 3fps one above 120, 60, 30, 15, 8 and 4fps). Proved in Movie mode, one File Format chosen in the menu at a time: Rec Frame Rate of XAVC HS 4K (0x0204: 50p, 100p), XAVC S 4K (0x0206), XAVC S HD (0x0208: 50p, 25p, 100p), XAVC S-I 4K (0x020a) and XAVC S-I HD (0x020c: 50p, 25p); S&Q's Rec Frame Rate (0x0240) and Frame Rate (0x0248) and Time-lapse's Rec Frame Rate (0x1137: 50p, 25p). A list's own start (the option it opens on) changes nothing when chosen, so each list is proved from another saved rate too, and every PAL rate is proved. XAVC HS 8K offers a single rate under PAL, so its Rec Frame Rate has no choice to prove there. |
| Network remote and USB | While a USB cable to a computer is in, the camera refuses every network remote session, wired and Wi-Fi alike (`Connect_SSH_GetFingerprintFailed`), even with no USB session open. With the cable out both work with the same access authentication. On Wi-Fi the camera takes its own DHCP address, with a MAC of its own. |
| Wi-Fi Connect | Greyed while Wired LAN Connect is On ("not available as follows: Wired LAN On"): Wired LAN Connect Off first. Each writes only its own record. |
| USB Connection Mode | MTP is refused while Remote Shooting is On ("Connected to Remote Shooting. Cannot be executed."), even with no session open. Chosen with Remote Shooting Off, it is kept when Remote Shooting goes back On, but the row then reads Sel. When Connect. Turning Remote Shooting On shows a notice about access authentication (Close lit). |
| Creative Look | One set of looks for every mode: Different Set for Still/Mv lists Aperture, Shutter Speed, ISO, Exposure Comp., Metering Mode, White Balance and Picture Profile, no Creative Look, and a base-look change in Stills, Movie, S&Q or Time-lapse writes the same record. Creative Look is greyed in S&Q Intelligent Auto and while a Picture Profile is on. Choosing a custom look's base gives it that base's parameters; the panel's Reset (the trash button: "Reset the current look? All parameters are reset.", Cancel lit) puts them back and keeps the base. A built-in look's panel has no Look cell, and BW and SE have no saturation. |
| Image Quality Settings, one slot | With Recording Media on one slot the table has one column, saved as each cell is chosen. Its File Format lists RAW, RAW & JPEG and JPEG with JPEG/HEIF Switch on JPEG, and RAW, RAW & HEIF and HEIF with it on HEIF. |
| HDMI Output Settings | `4K Output Set. (HDMI Only)` (record 0x0494) can hold a PAL value (an odd code) while the camera is on NTSC, where the menu offers only 60p/30p/24p. Once changed from the menu, such a value cannot be chosen again; only loading a settings file puts it back. |
| Focus Area | Switching **Switch V/H AF Area** off and back on clears the stored vertical-orientation focus areas and positions (records 0x0e64-0x0ffa). Turning the feature back on does not bring them back. |
| Focus Area Limit | Removing a focus area from Focus Area Limit (e.g. Spot: M) resets every stored focus-area slot that used it (per-orientation / per-mode slots, records 0x0e5c-0x0f84, plus 0x04e0) to defaults. Allowing the area again does not restore those slots. |
| Custom Key | Choosing a Recall Custom hold function assigns it immediately and then opens the set's registration screen; cancelling that screen does not undo the assignment. |
| Camera Set. Memory | Registering a memory slot copies the current settings into its memory set (which set: the Memory sets row). Three records in each set only registration writes, never a settings file: 0x023c (2 empty, 4 registered), 0x11ab (0 once registered in Stills mode; a Movie registration leaves 1) and 0x11ad (the stills exposure mode at registration, M 4, S 3). So after Initialize, a file restores the slots' settings but they still read as empty until registered again by hand. The finder's DISP layout is 0x04e6 and the monitor's 0x04e5; the Fn overlay's cursor is not stored. |
| Memory sets | The file's twelve memory sets are three slots for each family: sets 1-3 are the Stills slots 1-3, 4-6 Movie's, 7-9 S&Q Motion's and 10-12 Time-lapse's. Registering a slot also writes that set's 320-byte block of global record 0x018c (block N for set N). M1-M4 go to the memory card ("Registered. Slot 1") and change nothing in the file. Record 0x11ab reads 0 after a Stills registration and 4 after S&Q or Time-lapse; Movie leaves it. In S&Q and Time-lapse sets, registration also writes 0x0170 = 1. A settings file sets none of 0x023c, 0x11ab, 0x11ad or the sets' 0x0170. Only Stills registrations write the raw stop values. |
| Reg. Custom Shoot Set | A Recall Custom hold stores Exposure Comp. with the opposite sign to the live setting. Both count quarter stops from 20, but the live records (0x0340, 0x0e16, 0x13d6; set through the SDK) go up with plus (+1.0 EV is 24), while a hold's record (0x0bf9) goes up with minus (-1.0 EV is 24, +4.7 EV is 1). The hold's other values use the live codes: ISO AUTO 0 and ISO 125 6 up to ISO 102400 35; Drive Mode Single Shooting 0 and the brackets 6-9; Cnt Shoot Speed Boost Off 0 and 30 to 5 images/s 3-7. Registering a bracket drive mode also rewrites the hidden 0x0e80 and 0x0e84, and every Register rewrites 0x0c09. Whether recalling a hold applies the right sign has not been checked; it would take a press of the custom key. |
| Reg. Custom Shoot Set | A hold's Drive Mode list has no step or image count for its brackets, and a speed per row (Cont. Shooting: Hi+ ... Lo; Right does nothing there). Registering a speed writes it twice: Drive Mode (0x0bed 2-5) and 0x0bf1 (Hi+ 0 ... Lo 3), which other drive modes leave alone. Registering Cont. or Single Bracket copies the camera's live bracket setting at that moment (0x04c6 / 0x04c8) into the hold (0x0e80 / 0x0e84), renumbered by its place in the live list from 0 (the live codes skip 13, 20, 42 and 60). So a hold recalls the step and images that were live when it was registered, which its screen never shows. Every Register also writes a small number into 0x0c09, whose meaning is not known. |
| Picture Profile | PP7-PP9 are missing from the a1 II's menu, though the file keeps all eleven profiles. Their slots hold the first a1's log presets, even after Initialize: PP7 S-Log2 / S-Gamut (Gamma 15, Color Mode 11), PP8 S-Log3 / S-Gamut3.Cine, PP9 S-Log3 / S-Gamut3. The ILCE-1 Help Guide (Ver.2) lists PP1-PP11 with those presets; the ILCE-1M2 Help Guide lists PP1-PP6, PP10, PP11 and PPLUT1-4, and log shooting has its own menu (Log Shooting Setting, with which Picture Profile is fixed to Off). This body's Gamma list skips codes 8-9 and has no 15, and its Color Mode list skips 7 and has no 11; a file putting PP7's 15 / 11 into PP1 is refused (PP1 keeps its values). So the file layout carries the a1's slots and codes, and the a1 II hides the log presets and S-Log2 / S-Gamut. PPLUT1-4 show as User1-4 (Picture Profile 12-15) in Movie mode. |
| Focus frame position | Moving the focus frame on the shooting screen (Zone, Spot) changes no live record: the settings file keeps the old place, and a restored file does not move the frame back. Only registering a memory slot writes it, into the set: the zone as an index on its 3 x 3 grid (0 centre, 1 up, 2 right, 3 left, 4 down, 5 lower right, 6 lower left, 7 upper left, 8 upper right; six records agree), the spot as X / Y on a 640 x 480 grid (a press moves a frame by a step AF Frame Move Amt sets, measured with it set by the menu: under Standard a press moved Spot M's point 30 in X and 20 in Y, Spot XS's 20 and 20, and Custom 1's box 28 and 19; under Large Spot M's point 60 in X and 38 in Y, Spot XS's 36 and 32, and the box 56 and 38, twice Standard's). So a settings file cannot carry where a person last put the frame, except through a memory slot. |
| Drive Mode | A third drive-mode record, 0x13d4, takes the same codes as 0x02b5 when the drive mode is chosen from the menu, on a body Camera Settings Reset has been run on: the reset moves 0x1126 to 7, which a settings file cannot set back, and before it a menu choice does not write 0x13d4. The unmapped 0x0b72 is not the switch (loaded back by a file, 0x13d4 still moves). So two bodies with the same file can differ here: a body never reset may leave 0x13d4 unwritten. |
| Picture Profile | Each profile parameter is stored three times. Stills edits write the first two (the one in use and the stills one). The third is **not** the factory default a profile's own Reset uses: a file's values there are kept, and Reset ("Reset PPn to the default setting?") gives Sony's values whatever it holds. It is Movie mode's copy: in Movie mode every menu change across PP1-PP6, PP10 and PP11 writes the copy in use and this one. Whether a change in one mode writes the other mode's copy too is Different Set for Still/Mv's Picture Profile box, not proved yet. Camera Settings Reset and Initialize leave Picture Profiles alone, except PPLUT1-4 (Sony's guide). |
| Camera Settings Reset | Setting Reset opens two buttons, Camera Settings Reset (lit) above Initialize. The prompt reads "Reset the main camera settings? (After initialization, reboots automatically.)" with Cancel lit, and the camera reboots after Enter. It resets every Creative Look's base look and both of its copies (0x0f9b, 0x0fbb) to Sony's, whatever a file put in each. Sony's default-value lists mark no Setup row (sound, Screen Reader, USB, HDMI, network) as reset by it. |
| Camera Set. Memory | Registering a slot writes its exposure-mode stamp (set 0x11ad: the mode dial's position), which no settings file sets back. Uploading a settings file after a registration restores the slot's contents, not that stamp. |
| White Balance | Custom 1-3's fine-tune grid writes only G-M (0x1006, 0x1008, 0x100a). A-B moves, alone or at the grid's corners, change nothing in the settings file, while every other preset stores both axes. So a file restore cannot carry a Custom white balance's A-B shift. Whether the camera keeps it at all (for example over a restart) has not been checked. The schema's guessed A-B records for them (0x0c65, 0x0c67, 0x0c69) are not in this camera's settings files. |
| ISO AUTO Min. SS | One menu setting, two records. 0x0336 holds the option (1/16000 is 4 up to 30" at 23), and its first option, the automatic one, is 0. That option's speed (Slower, Slow, Standard, Fast, Faster: Left/Right on it) is a separate record, 0x04d2 (0-4), which keeps its value while a fixed speed is chosen. An editor should show 0x04d2 only when 0x0336 is 0. |
| ISO Auto/Manual Set | In Flexible Exp. Mode, switching ISO to Auto sets ISO (0x0334, and the movie copy 0x0df4) to AUTO; switching back to Manual does not restore the manual ISO from before but takes the ISO the camera was using in auto. An editor that flips 0x033c should leave 0x0334 alone. |
| Reg. Custom Shoot Set, Focus Area | A hold's Focus Area (0x0c25) numbers the spot sizes the other way from the live record: S 4, M 5, L 6, XL 7, XS 8 (and Tracking: Spot S 16 ... XL 19, XS 20), where 0x0f46 has XL 3, L 4, M 5, S 6, XS 7. Its list also starts with an option of its own, Regist Focus Area (0), and comes round. |
| Movie Record Setting | Movie mode keeps one Record Setting record per File Format and Rec Frame Rate, in order: XAVC HS 4K 60p 0x0212, 24p 0x0214, 120p 0x0216 (HS 4K offers no 30p); XAVC S 4K 60p 0x0218, 30p 0x021a, 24p 0x021c, 120p 0x021e; XAVC S HD 60p 0x0220, 30p 0x0222, 24p 0x0224, 120p 0x0226; XAVC HS 8K 30p 0x020e, 24p 0x0210. Each has its own option list. The same code can name different bitrates in different records: 29 is 16M in S HD at 30p and 25M in S&Q's S HD. A file that changes only a format's Rec Frame Rate is refused (CameraSettings_Read_Result_NG) when the matching record holds no value valid there. The XAVC S-I formats have no Record Setting choice. |
| S&Q Record Setting | S&Q keeps its own Record Setting records apart from the movie ones. XAVC HS 4K (0x024e) and XAVC S HD (0x025c) keep one record at every S&Q Rec Frame Rate. XAVC S 4K keeps one per rate: 60p 0x0254, 30p 0x0256, 24p 0x0258, 120p 0x025a, each with its own option list. The HS 4K one uses the movie record's codes. The S HD one stores 25M 4:2:0 8bit as 29 where the movie record (0x0220) stores 28, so an editor cannot copy codes between the two. |
| Setting Reset | **Camera Settings Reset** changes only shooting settings. Of 304 menu settings tested, each set to another value by file upload, it puts back 234 and leaves 70 as they were: every Setup-tab setting tested (HDMI Resolution, Output Resolution, REC Control, Control For HDMI, Auto Review, Gamma Display Assist, Display LUT, the display options), and shooting, focus and playback settings such as Shutter Type, Release w/o Lens/Card, Grid Line, Lens Compensation, File Number, Folder Name, Recording Media, Live View Display, the movie markers, Time Code, Zoom Range, ISO Range Limit, Exposure step, Zebra, Priority Set in AF-S/AF-C, Focus Area Color, AF Area Registration, Peaking, Image Order, Display Rotation (list: `data/ILCE-1M2_fw4.00/settings_reset_ILCE-1M2_fw4.00.json`, which tags 17 of the 82 Setup, and tags Setup three rows the reset does put back: S&Q Shoot Mode's second record and Underwater Auto's white balance fine-tune A-B and G-M). It does not go through the first-start setup. **Initialize** resets every memory set and all 316 test settings (12 of the test values are the factory defaults, so they show nothing either way); it also clears the network setup (Wired LAN, access authentication) and the FTP settings, which live in their own file, and goes through language/date/area at the next start. Record 0x1126 (unnamed): Camera Settings Reset sets it to 7, Initialize leaves it at 7, and an uploaded file does not set it. After Initialize, an uploaded file restores the memory sets' contents but not three records per set (0x023c, 0x11ab, 0x11ad in sets 1-3), which stay at their Initialize values: they look like the sets' registration state. |
| Switch V/H AF Area | Held vertically, the camera turns the Focus Area dialog (and the shooting screen) on HDMI as well as on its own screen, and the keys follow the turned picture: grip down, Down steps back through the Focus Area carousel, and grip up, Up does. With AF Point + AF Area on, Focus Area writes only the records of the way the camera is held, with the same codes as level: grip down 0x0e6a, 0x0f4c-0x0f50, 0x0ff0-0x0ff4 (Spot size 0x0e5e, Tracking 0x0e64, Custom area 0x131b-0x131f + 0x1395); grip up 0x0e6c, 0x0f52-0x0f56, 0x0ff6-0x0ffa (0x0e60, 0x0e66, 0x1321-0x1325 + 0x1397). Moving the AF point with the multi-selector during a remote session writes nothing to the settings file. Record 0x04e2 is set by the camera, not by a loaded file: 1 level, 8 held vertically either way (an uploaded 1 downloads as 8). Movie mode writes only the level set. |
| Var. Shutter Set. | The variable shutter speed (Rear Dial R in steps of 0.2) is not stored in the settings file: changing it and leaving with Exit writes nothing, like the live shutter speed. Only Var. Shutter itself (0x02e7, 0 = On) is. |
| Flash Mode | With the mode dial on M, Flash Off and Autoflash are refused ("not available as follows Shoot Mode Manual Exposure"), and a stored Autoflash (0x0357 = 1) shows as Fill-flash: the list opens on Fill-flash, and choosing it writes 2. The stored value cannot be put back through the menu in M mode; a file upload can. |
| Recall Custom hold | Records 0x0bd5, 0x0bd9, 0x0bdd, 0x0be1, 0x0be5, 0x0bed, 0x0c25, 0x0c29, 0x0c2d, 0x1724, 0x1728 and 0x18cb are 4-slot arrays: Recall Custom hold 1-3 and a fourth slot that copies whichever hold's registration screen was last opened (assigning a Recall Custom hold to a key opens it). Uploading a settings file restores the first eleven, but not 0x18cb's fourth slot: the camera keeps it. Opening the other hold's registration and leaving it with MENU puts it back. Opening a hold's registration and cancelling changes only the fourth slot. |
| Rating Set(Custom Key) | Each star box of Rating Set(Custom Key) has two records: 0x0f96-0x0f9a (0 = ticked) and 0x16bd-0x16c1 (1 = ticked). The second series stays 0 in a file until the screen is first saved (or Rating goes on a key), so in a file where only the 1-star box is ticked (as the factory leaves it), the first save writes 0x16bd 0 -> 1 even with every box as it was. Unticking the only ticked box is refused ("Item not selected."). |
| Copyright Info | Photographer and Copyright Holder names are **not** saved in settings files, and neither is the Write Copyright Info switch: the schema has no Copyright record, and the Save/Load exclusions row agrees. The 3-character file-name prefix is saved (record 0x0b5b). |
| Dial/Wheel | Turning **Separate M mode and other modes** off and on again copies the M-mode dial functions over the other-mode ones (records 0x0407-0x040e); the separate other-mode choices are lost. |
| Movie / stills | Most settings share one record in stills and movie mode. Some keep a separate movie copy (SteadyShot 0x02f9, Aspect Marker 0x0326, Subject Recog. Frame Display 0x117c, Initial Focus Mag. 0x03b9). The settings Different Set for Still/Mv splits (ISO, Metering, White Balance, Picture Profile and SteadyShot) each keep a stills record and a movie record beside the record in use, and S&Q uses the movie set; Picture Profile's three copies are the Picture Profile row above. |
| Proxy recording | Proxy Rec. Settings (0x0284) is one record for all proxy formats; switching the proxy file format to XAVC HS forces it to a compatible value and switching back keeps that value (with XAVC S HD the item is fixed at 6M 8bit and greyed out). |
| Framing Stabilizer | Record 0x1188 changes 0 -> 1 once Framing Stabilizer has been switched on and stays 1 (one-time flag). |
| Self-timer Type | Only adjustable with the physical Drive Mode dial on a self-timer position; it is greyed out when the drive dial is set to menu control. Its record is 0x02bd; the dial position itself is not stored in the file. |
| Recall Custom | Registering a Recall Custom hold also rewrites hidden per-hold values (0x0c09; bracket values 0x0e80/0x0e84 when a bracket drive mode is registered). |
| Greyed-out items | Settings that are greyed out keep their stored value (e.g. Face Priority in Multi Metering while Recognition Target = Auto). The value is used again once the blocking setting changes. |
| Shooting modes | P, A, S and M share one set of settings; nothing is stored per mode (aperture, shutter, ISO, exposure comp, WB, metering: last set wins). |
| Interval shooting | The Shooting Interval spinner wraps around (60 -> 1); Number of Shots clamps (0 -> 1); BULB Exposure Time refuses values outside 2-900 s rather than clamping. |
| Confirmation popups | Some changes ask for confirmation with **Cancel** pre-selected (e.g. turning Auto Pixel Mapping off); others pre-select OK. |
| Checklist screens | Drive Mode Limit / Recog Trgt Select Set reopen with the cursor where it was last, not at the top. |
| Record numbering | Recognition target **Airplane** is stored in its own record (0x18c8), not in the array holding the other targets (0x1109). This suggests it was added in a later firmware; it is relevant when supporting other firmware versions. |
| Load settings | After a settings file is loaded, Memory 1's record 0x11ad (a working copy of the memory's exposure mode) is rewritten with the mode dial's current position; Memory 2 and 3 keep the file's value. The mode the camera actually recalls is set record 0x0b8d, which the load keeps: recalling Memory 1 through Shoot Mode (dial under menu control) after loading a file whose 0x11ad says M and 0x0b8d says A recalls A. Registering a memory writes both. |
| Load settings | The network settings in the file are applied like any other: a file saved with Wired LAN Connection off takes a LAN-connected camera off the network when loaded. |
| Lens list | The registered lens list (0x167c name, 0x16a1 serial, 0x1682-0x1732 data, 6 slots) is not updated by mounting a lens and taking a picture; it is copied as-is by Save/Load, so every download echoes the last loaded file. Registering a Preset Focus/Zoom preset writes it (a custom key held down for presets 1-5, a lens's Function Ring for 6; the definition's notes on those records). |
| Header checksum | Header byte 0x39 is a checksum of bytes 0x00-0x38: each byte shifted left by (offset mod 8), summed, low byte kept. The trailer u32 is the plain byte sum from 0x3c. Bytes 0x36-0x37 hold the firmware version (02 00 in a firmware 2.00 file, 03 00 in a 3.00 one, 04 00 here) and 0x38 the video system (the Header: video system row). |
| Menu paging | Menu page numbers depend on the configuration, so a page number alone does not identify an item; the kit looks on neighbouring pages. |
| Live exposure | Live aperture and shutter speed are not stored in settings files (only Recall Custom registrations store them). |
| Save/Load exclusions | Sony's Help Guide page for Save/Load Settings lists what the file never holds: IPTC, Copyright Info, External Flash Set., custom white balances 1-3, Face Memory, Remote Shoot Function's Connect without Pairing and Sync. Release Set., FTP Transfer Func. (own file), Network Streaming, Cloud Connection, WPS Push, Access Point Set., Wi-Fi Frequency Band, IP Address Setting, Edit Device Name, Import Root Certificate, Access Authen. Settings, Language, Area/Date/Time. Our own by-hand checks agree on every item tested (Language, Area/Date, Copyright, Wi-Fi band, flash). NTSC/PAL is not on the list but has no record either: the file says it in its header (byte 0x38, the Header: video system row), and it re-indexes the frame-rate records. |

## Not bugs (caused by our testing; listed so they are not mistaken for bugs later)

| What was seen | Actual cause |
|---|---|
| Menu item read as "Touch Sensitiviy" | OCR misread; the camera shows "Touch Sensitivity". |
| Animal/Bird and Continuous Shooting: Mid became unticked during checklist tests | The mapper backed out of a half-finished step after misreading the highlighted row; it did not happen when the screen was navigated by name. |
| Face Priority in Multi Metering and Auto Power OFF Temp. left changed | Mapper failed to restore them: scrolling long label, and cancelling the camera's own confirmation popup. Restored manually. |
| Number of Shots and Shooting Interval left changed | Range-probe misread single digits by OCR. Restored. |
| "Internal temp. high" shutdown, then camera disappeared from USB | Hours of continuous remote menu work in movie mode (live view, a settings save every few seconds), with Auto Power OFF Temp. switched to Standard by our mapper. Not a bug. |
| Camera stopped accepting connections | Our tool was killed mid-session and left the camera's remote session open; a power cycle cleared it. |
| Interval Shooting turned on, drive mode changed | Automated presses on the shooting screen (direction keys are shortcuts there). Restored. |

## Other firmware (files only)

Two settings files from other a1 II bodies were compared with this layout. They are kept in the maintainers' own
`private/camsets/` (decision 18). Nothing was run on a camera with them, and their values stay out of these docs.

| Header bytes 0x36-0x37 | Firmware | Live records | Each memory set | Fingerprint |
|---|---|---|---|---|
| `02 00` | 2.00 | 1421 | 1052 | `be313beeaac7f58c` |
| `03 00` | 3.00 | 1414 | 1057 | `db2248c140565b14` |
| `04 00` | 4.00 (this layout; byte 0x38 is 0 on NTSC, 1 on PAL) | 1415 | 1057 | `07a5b07a502c68f0` |

- **The first two header bytes are the firmware version, the third the video system.** 0x36 is the
  major version and 0x37 the minor; 0x38 is 0 on NTSC and 1 on PAL, proved on this camera at
  firmware 4.00 (the Header: video system row). That firmware 2.00 and 3.00 write the video system at 0x38 as 4.00
  does is inferred, not proved on such a camera. Every file seen has a minor of 0, so whether a minor of 1 is written
  as 01 (x.01) is not known yet.
- **Records keep their id, order and meaning.** Every record the files share is in the same order, and most of the
  proved records with labelled values hold a code this schema labels; the rest hold codes it has no label for. So an
  editor must read a file by record id, never by offset.
- **2.00 to 3.00:** dropped 30 records the firmware 2 file holds: 0x178d-0x17ee, 0x1814,
  19-slot arrays of 17- and 129-byte strings at 0x1847-0x1880, 0x1894-0x18ae and 0x1925. It added
  23 live records: Bluetooth Function, Airplane Mode, the Shooting / Drive / Focus Mode Dial
  records, Delete Slot1/2, Initial Pos. When Exec, Priority Key Settings, the exposure-mode family
  0x13bf-0x13e3, and 0x1391, 0x13ab, 0x13cb, 0x13cd, 0x13cf. Those last five were also added to
  every memory set.
- **3.00 to 4.00:** added 0x1437 (six slots: Preset Focus/Zoom's slot flag A). Creative Look's
  eleven arrays grew from 16 to 18 slots. The two new slots are FL2 and FL3, appended after the
  six custom looks, so slots 0-15 mean the same in both: slots 0-9 name their own look and the
  custom slots hold 0-9 in every file.
- **Leads for unmapped records:** a record that never changed in this body's downloads but holds
  another value in one of these files is one a camera writes: a place to look. Which records those
  are is not listed here, for a difference may be the other owner's setting.
- **In the editor:** a fingerprint the schema does not list opens read-only, with the meanings
  matched by record id. "Edit anyway…" turns on editing for the settings a file holds in the mapped
  shape: 1,410 of 1,624 in the firmware 2 file and 1,426 in the 3.00 one. Creative Look (its arrays
  changed size) and the records those firmwares lack stay view-only. No write to a camera on these
  firmwares has been tried yet: the read-back after a write is the check.

## Open

- What 0x1126 is.
- Which records the remaining unmapped live records hold.
