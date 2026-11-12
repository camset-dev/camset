//! Why something failed, in plain words: a cause and what to do, the technical details in Expert mode only. One
//! wording for the window and the web page.

use crate::*;

/// The technical words after a sentence in plain words, in Expert mode only: " (Details: …)"; nothing otherwise. The
/// messages that end on an error's own words go through it, so that rule is kept in one place (a camera report's
/// lines and the folders a search looked in have their own forms).
pub(crate) fn details(expert: bool, what: impl std::fmt::Display) -> String {
    if expert { format!(" (Details: {what})") } else { String::new() }
}

/// Why one of the editor's own files (the credentials file, the cameras this computer trusts) could not be read or
/// (`writing`) written, in plain words with what to do, `folder` naming where it is kept in words ("~/.config/camset"):
/// the person picked no folder for it, so "choose another folder" is no help, and its folder is not the editor's own.
pub(crate) fn own_file_words(e: &std::io::Error, writing: bool, folder: &str) -> String {
    use std::io::ErrorKind as K;
    let (verb, may, done) = if writing { ("change", "write to", "written") } else { ("read", "read", "read") };
    match e.kind() {
        K::PermissionDenied | K::ReadOnlyFilesystem => format!("this computer did not let the editor {verb} its file in {folder}: check that your user may {may} that folder, then try again."),
        K::StorageFull if writing => "the disk is full: make room, then try again.".into(),
        _ => format!("its file in {folder} could not be {done}: try again; Expert mode (⚙ Settings) shows the system's own words."),
    }
}

/// The helper's `cause: <token>` line, when it names a cause this editor can explain.
pub(crate) fn probe_cause(text: &str) -> Option<&str> {
    text.lines().find_map(|l| l.trim().strip_prefix("cause:")).map(str::trim).filter(|t| cause_sentence(t).is_some())
}

/// What happened and what to do, for each cause the helper names.
pub(crate) fn cause_sentence(token: &str) -> Option<&'static str> {
    Some(match token {
        "credentials_missing" => "The camera asks for a user name and password, and none is saved on this computer. Enter the pair set on the camera in Connect to the camera and press Save; it is kept in a private file on this computer only.",
        "credentials_rejected" => "The camera refused the user name or password. Check the pair set on the camera and enter it again in Connect to the camera.",
        "camera_not_trusted" => "The camera's identity did not check out while connecting, so the connection was stopped. Try again. If it happens again, check that the camera at this address is yours; if you reset its network settings, forget it in Connect to the camera (Known cameras, Forget) and connect again.",
        "camera_changed" => "The camera at this address is not the one this computer trusted before, so its user name and password were not sent. If you reset the camera's network settings, forget it in Connect to the camera (Known cameras, Forget) and connect again to trust it again. Otherwise check what is at that address.",
        "credentials_file_open" => "The file on this computer that keeps the camera's user name and password could be read by other users of this computer, so it was not used. Enter the pair again in Connect to the camera and press Save, which makes the file private, then try again.",
        "usb_cable_in" => "The camera is also on a USB cable. Unplug the cable from the camera: while it is in, the camera does not answer on the network. Then try again.",
        "no_answer" => "The camera did not answer at that address. If it has just restarted (it does after taking a settings file), wait a few seconds and try again. Otherwise check it is on, on the same network, with network remote control on, and on the shooting screen.",
        "held_by_other_program" => "Another program on this computer is holding the camera. Quit it and try again.",
        "no_usb_camera" => "No camera was found on USB. Check the cable carries data, the camera is on and set to remote control over USB, and it is on the shooting screen.",
        "usb_no_permission" => "The camera is plugged in, but this computer does not let programs open it yet. Run the one-time line `kit/setup.py` prints under camera access, then unplug and replug the camera.",
        "bad_address" => "The camera address is not a valid address: four numbers from 0 to 255 with dots between them, such as 192.168.1.20. Check it in Connect to the camera.",
        "connect_failed" => "The camera did not accept the connection, and the camera link could not tell why. Go through the steps in Connect to the camera, then try again; the link's own messages are shown in Expert mode (⚙ Settings).",
        "download_refused" => "The camera refused to give its settings file. Leave it on the shooting screen, not in a menu or playing back pictures, with a memory card in, and try again.",
        "upload_refused" => "The camera refused the file, so nothing was written to it. Leave it on the shooting screen, not in a menu, and try again.",
        "not_a_settings_file" => "The file to send is not a settings file the camera saved, so nothing was sent. Open one from the camera's card, or read the camera first.",
        _ => return None,
    })
}

/// The limit, in whole seconds, after which the camera job stopped a helper that had not ended (the `HELPER_TIMEOUT`
/// line `run_helper` adds to its output); None when it ended on its own.
pub(crate) fn helper_timeout(text: &str) -> Option<u64> {
    text.lines().find_map(|l| l.trim().strip_prefix(HELPER_TIMEOUT)).and_then(|r| r.split_whitespace().next()).and_then(|n| n.parse().ok())
}

/// A helper the camera job stopped after `secs`, in plain words with what to do.
pub(crate) fn timeout_sentence(secs: u64) -> String {
    format!("The camera helper did not answer within {secs} s: the camera may have lost its link. Check it, then try again.")
}

/// What happened and what to do, when the output says: a helper the camera job stopped (`helper_timeout`), else the
/// helper's own cause (`probe_cause`, `cause_sentence`).
pub(crate) fn cause_words(text: &str) -> Option<String> {
    helper_timeout(text).map(timeout_sentence).or_else(|| probe_cause(text).and_then(cause_sentence).map(str::to_string))
}

/// A failed camera action in plain words: the sentence for what stopped it (`cause_words`, a warning), or, when the
/// output names nothing, what to check for the link, worded by the camera's definition (`hint`) when it has words for
/// it.
pub(crate) fn cause_lines_with(text: &str, network: bool, hint: Option<&str>) -> Vec<(String, bool)> {
    match (cause_words(text), hint) {
        (Some(said), _) => vec![(said, true)],
        (None, Some(h)) => vec![(h.to_string(), false)],
        (None, None) if network => vec![("Check the camera is on, on the same network as this computer, with network remote control on, on the shooting screen, and with no USB cable to a computer. The steps are in Connect to the camera.".to_string(), false)],
        (None, None) => vec![("Check the camera is on, joined by a cable that carries data, set to remote control over USB, and on the shooting screen. The steps are in Connect to the camera.".to_string(), false)],
    }
}

/// A failed action's report lines: the cause first, then the action's own lines; without a cause, the action's own
/// lines, then what to check (worded by the camera's definition, `hint`, when it has words for it).
pub(crate) fn failure_lines_with(text: &str, network: bool, own: Vec<(String, bool)>, hint: Option<&str>) -> Vec<(String, bool)> {
    let lines = cause_lines_with(text, network, hint);
    let (cause, rest) = if cause_words(text).is_some() { (lines, Vec::new()) } else { (Vec::new(), lines) };
    cause.into_iter().chain(own).chain(rest).collect()
}

/// Why a settings file could not be used, in plain words.
pub(crate) fn file_problem(e: &camset::CamSetError) -> &'static str {
    use camset::CamSetError as E;
    match e {
        E::NotCamSet => "this is not a camera settings file any camera definition describes. Choose a settings file the camera saved",
        E::Truncated(_) | E::BadMarker(_) | E::BadChecksum { .. } | E::BadHeaderChecksum { .. } | E::TrailingData(_) =>
            "this settings file is damaged or incomplete; it may have been cut short when it was copied. Copy it from the card again",
        E::NotScalar(_) | E::OutOfRange { .. } => "a value in this file does not fit where it is kept",
    }
}

/// Why a file could not be read from disk, in plain words.
pub(crate) fn read_problem(e: &std::io::Error) -> &'static str {
    match e.kind() {
        std::io::ErrorKind::NotFound => "the file is not there any more (was the card taken out?)",
        std::io::ErrorKind::PermissionDenied => "this computer does not allow reading it",
        std::io::ErrorKind::IsADirectory => "that is a folder, not a settings file",
        _ => "it could not be read",
    }
}

/// The settings an edit or a copy left alone, by why: a file holds them in another shape than the editor knows (`shape`,
/// `copy_row`); they are view only outside Expert mode (`locked`, `App::locked_why`: no proof on the camera stands for
/// them); their value is one the menus offer under another video system than file A was saved under (`other_system`,
/// `Setting::other_system`); a copy the camera keeps of a setting that took no value (following its setting, put back,
/// or taken along), its record being of another shape than mapped (`copies_shape`, `App::apply`).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Left {
    pub(crate) shape: usize,
    pub(crate) locked: usize,
    pub(crate) other_system: usize,
    pub(crate) copies_shape: usize,
}

impl Left {
    /// How many, whatever the reason.
    pub(crate) fn total(self) -> usize {
        self.shape + self.locked + self.other_system + self.copies_shape
    }
}

/// What an edit or a copy left alone (`Left`), one sentence per reason, each saying what to do where something can be
/// done; empty when it left none.
pub(crate) fn left_alone(left: Left) -> String {
    let one = |n: usize, it: &str, them: &str| match n {
        0 => None,
        1 => Some(format!("1 setting left alone: {it}")),
        n => Some(format!("{n} settings left alone: {them}")),
    };
    [
        one(left.shape, "a file here holds it in another shape than the editor knows.", "a file here holds them in another shape than the editor knows."),
        one(left.locked, "it is view only outside Expert mode, as no proof on the camera stands for it here. Expert mode (⚙ Settings > Editing & Compare) copies it.",
            "they are view only outside Expert mode, as no proof on the camera stands for them here. Expert mode (⚙ Settings > Editing & Compare) copies them."),
        one(left.other_system, "its value is offered only with the camera set to another video system than file A was saved with.",
            "their values are offered only with the camera set to another video system than file A was saved with."),
        one(left.copies_shape, "a copy the camera keeps of a setting was not changed with it, as the file holds it in another shape than the editor knows; it holds its old value.",
            "copies the camera keeps of settings were not changed with them, as the file holds them in another shape than the editor knows; they hold their old values."),
    ].into_iter().flatten().collect::<Vec<_>>().join(" ")
}

/// A status line with `left_alone`'s sentences after it, when there are some.
pub(crate) fn with_left(said: &str, left: Left) -> String {
    let said = said.trim().trim_end_matches('.');
    match (left.total(), said.is_empty()) {
        (0, _) => said.to_string(),
        (_, true) => left_alone(left),
        _ => format!("{said}. {}", left_alone(left)),
    }
}

/// Where the camera link's own messages are, outside Expert mode.
pub(crate) const EXPERT_LINK_NOTE: &str = "The camera link's own messages are shown in Expert mode (⚙ Settings).";

/// A file error in plain words, for reading (`writing` false) or writing a file.
pub(crate) fn io_words(e: &std::io::Error, writing: bool) -> &'static str {
    use std::io::ErrorKind as K;
    match (e.kind(), writing) {
        (K::NotFound, false) => "the file is not there any more: it was moved or renamed, or its card was taken out.",
        (K::NotFound, true) => "that folder is not there any more: it was moved, or its card was taken out.",
        (K::PermissionDenied, false) => "this computer does not let the editor read that file. Copy it to a folder of your own and open the copy.",
        (K::PermissionDenied, true) | (K::ReadOnlyFilesystem, true) => "this computer does not let the editor write there (the folder, disk or card may be locked). Choose another folder.",
        (K::StorageFull, _) => "the disk or card is full. Make room, or choose another place.",
        (_, false) => "the file could not be read.",
        (_, true) => "the file could not be written there. Choose another folder.",
    }
}

#[cfg(test)]
pub(crate) mod plain_words_tests {
    use super::*;

    /// A damaged file and a file that is not a settings file are said in plain words; the technical details
    /// only in Expert mode.
    #[test]
    fn file_problems_in_plain_words() {
        let dir = std::env::temp_dir().join(format!("plain_words_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let mut bytes = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT").to_vec();
        bytes[0x100] ^= 0xff;
        let damaged = dir.join("CAMSET07.DAT");
        std::fs::write(&damaged, &bytes).unwrap();
        let other = dir.join("NOTES.DAT");
        std::fs::write(&other, b"not a settings file at all, but long enough to be read as one").unwrap();
        let mut app = App::new(vec![], Prefs::default());
        let e = app.load(&damaged).unwrap_err();
        assert!(e.starts_with("CAMSET07.DAT: ") && e.contains("damaged or incomplete") && !e.contains("0x"), "{e}");
        assert!(app.load(&other).unwrap_err().contains("not a camera settings file any camera definition describes"));
        assert!(app.load(&dir.join("GONE.DAT")).unwrap_err().contains("not there any more"));
        app.prefs.expert = true;
        let e = app.load(&damaged).unwrap_err();
        app.prefs.expert = false;
        assert!(e.contains(" (Details: "), "{e}");
        // with no definition at all, the reason says so and what to do; where they were looked for in Expert mode
        app.defs = Definitions::load(None, vec![dir.join("shipped")], dir.join("mine"), &[]);
        let e = app.load(&other).unwrap_err();
        assert!(e.contains("No camera definition was found to read it with: reinstall the editor") && !e.contains("shipped"), "{e}");
        app.prefs.expert = true;
        let e = app.load(&other).unwrap_err();
        assert!(e.contains("(Looked in ") && e.contains("shipped"), "{e}");
        app.prefs.expert = false;
        // a value the definition has no name for
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let s = app.schema.settings.iter().find(|s| s.range.is_none() && s.values.len() >= 2 && s.text.is_none()).unwrap().clone();
        let unnamed = (0..1000).find(|v| s.label_for(*v).is_none()).unwrap();
        assert_eq!(App::describe(&s, Some(unnamed)), format!("{unnamed} (no name yet)"));
        // why, in plain words; in Expert mode how it was mapped, and the record number
        let why = app.unnamed_why(&s, Some(unnamed)).expect("said why");
        assert_eq!(why, format!("The camera holds {unnamed} here, a value Camset has no name for yet."));
        app.prefs.expert = true;
        let why = app.unnamed_why(&s, Some(unnamed)).expect("said why");
        assert!(why.starts_with(&format!("The camera stores {unnamed} here. This camera's definition has no name for that value yet")), "{why}");
        assert!(!why.contains("have held it before"), "no list of the values camera files held is kept (decision 16)");
        assert!(app.unnamed_why(&s, Some(unnamed)).unwrap().ends_with(&format!("Record 0x{:04x}.", s.id)));
        app.prefs.expert = false;
        // a value with a name, a number in a range, or no value at all: nothing to explain
        assert!(app.unnamed_why(&s, Some(s.values[0].0)).is_none() && app.unnamed_why(&s, None).is_none());
        let ranged = app.schema.settings.iter().find(|s| s.range.is_some()).unwrap();
        assert!(app.unnamed_why(ranged, Some(ranged.range.unwrap().0)).is_none());
        // a setting with no names and no range at all: the plain number, not "(no name yet)"
        let mut plain = s.clone();
        plain.values.clear();
        plain.unit.clear();
        assert_eq!(App::describe(&plain, Some(unnamed)), unnamed.to_string());
        assert!(app.unnamed_why(&plain, Some(unnamed)).is_none());
        plain.unit = "ms".into();
        assert_eq!(App::describe(&plain, Some(unnamed)), format!("{unnamed} ms"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// One of the editor's own files that could not be written (the credentials file, the cameras this computer
    /// trusts): plain words with what to do; the system's own words and the file in Expert mode only.
    #[test]
    fn own_files_in_plain_words() {
        let mut app = App::new(vec![], Prefs::default());
        let e = std::io::Error::from(std::io::ErrorKind::PermissionDenied);
        let p = Path::new("/home/user/.config/camset/network.json");
        // where the file is kept, its folder named (not the editor's own folder); reading said apart from writing
        let folder = shown_path(p.parent().unwrap());
        let said = app.own_file_problem(p, &e, true);
        assert!(said.contains(&format!("did not let the editor change its file in {folder}: check that your user may write to that folder")), "{said}");
        assert!(!said.contains("Details") && !said.contains("network.json") && !said.contains("os error"), "{said}");
        let read = app.own_file_problem(p, &e, false);
        assert!(read.contains(&format!("did not let the editor read its file in {folder}")), "{read}");
        app.prefs.expert = true;
        let said = app.own_file_problem(p, &e, true);
        assert!(said.contains(" (Details: ") && said.contains("network.json"), "{said}");
        assert_eq!((details(false, "x"), details(true, "x")), (String::new(), " (Details: x)".to_string()));
    }
}
