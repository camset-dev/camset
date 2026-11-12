//! Write to camera: the Write window, which reads the camera first and lists what the write changes and the
//! edited values the camera may refuse, and the rule for what may be written at all.

use crate::*;

/// The window shown before a save (Before saving) or a write to the camera (Write to camera): the edited values the
/// camera may refuse, and for a write what it changes on the camera.
#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) enum Review {
    Save,
    Send,
}

/// Why a file the sample was made into is not written (`send_blocked`): it came from the sample however it was opened,
/// as its header says.
pub(crate) const SAMPLE_NOT_WRITTEN: &str = "This file is the editor's sample, or a file saved from it: no camera wrote it as it is (its personal text was taken out), so it is never written to a camera. Read your camera, or open a settings file your camera saved, and make your edits there.";

/// What the window and the page say when the sample, or a file made from it, is saved or downloaded (`is_sample_doc`):
/// saving it is for trying the editor, and a camera must never load it, though its Load menu would list it.
pub(crate) const SAMPLE_NOT_FOR_A_CAMERA: &str = "This is the editor's sample, or a file made from it: no camera wrote it as it is, so never load it into a camera, though a camera's Load menu would list it. Saving it is only for trying the editor.";

/// The Write and Before saving windows' all-clear, the window's and the page's, shown only when every record the
/// session changed was checked on the camera and passed (`acceptance_issues` empty).
pub(crate) const ALL_CLEAR: &str = "✔ Every changed value was checked on the camera and is one it takes.";

/// What to do about the values listed (`acceptance_issues`), the window's and the page's.
pub(crate) const ISSUES_TODO: &str = "What to do: Revert the flagged values, the safe choice. Written anyway, the camera may refuse the whole file or store other values; before writing, save the camera's own copy to its card.";

/// What a changed value is, when the camera is not known to take it (`App::acceptance_issues`): the heading the Write
/// and Before saving windows list it under, in their order.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum IssueKind {
    /// Edits recovered from an earlier session without the file as it was opened (`Doc::recovered`): nothing tells what
    /// they changed, so nothing can be judged.
    Recovered,
    /// The camera refuses it, stores another value instead, or its menus never offer it (`Setting::acceptance`).
    Refused,
    /// A value the menus offer only under another video system than the file was saved under (`Setting::other_system`).
    OtherSystem,
    /// A value the camera keeps in several records, none of which holds it (`Setting::copies`, `App::out_of_step`).
    Copy,
    /// No proof on the camera checked it (`Setting::checked_on_camera`).
    NotChecked,
    /// A text typed in the editor.
    Text,
    /// Bytes changed that no setting the editor changes covers (Expert mode's raw edits, a record no setting covers).
    Raw,
    /// For a write: a record that differs from what the camera holds now but not from the file as opened or read, which
    /// the editor cannot vouch for (`App::write_issues`). Nothing in this session changed it; it is not counted among
    /// the values flagged, though it keeps the all-clear away.
    CameraOnly,
}

impl IssueKind {
    /// The heading, and the line under it that says what such a value is.
    pub(crate) fn heading(self) -> (&'static str, &'static str) {
        match self {
            IssueKind::Recovered => ("Edits the editor cannot check", "Recovered without the file as it was opened, so the editor cannot tell which values they changed, nor whether the camera takes them."),
            IssueKind::Refused => ("The camera may refuse or change these", "Seen on the camera: it refuses a file holding the value, stores another, or its menus never offer it."),
            IssueKind::OtherSystem => ("Another video system's values", "The camera's menus offer these only when it is set to another video system than this file was saved with."),
            IssueKind::Copy => ("Copies out of step", "The camera keeps each of these values in other records too, and every file it writes holds the value in at least one of them; here none does."),
            IssueKind::NotChecked => ("Not checked on the camera", "No proof on the camera chose these values, so nobody knows whether the camera takes them."),
            IssueKind::Text => ("Texts", "Typed here: the camera was not seen to take these texts."),
            IssueKind::Raw => ("Raw edits", "Changed byte by byte, so the editor cannot say what they hold or whether the camera takes them."),
            IssueKind::CameraOnly => ("In the file as opened, not on the camera now", "Nothing in this session changed these: they were in the file as it was opened, they differ from what the camera holds now, and the editor cannot check them."),
        }
    }
}

/// The Write window's sentence for the records only the camera's own copy shows (`IssueKind::CameraOnly`), the
/// window's and the page's: how many, what they are, and what the person can do.
pub(crate) fn camera_only_words(n: usize) -> String {
    let n = if n == 1 { "1 record of this file differs".to_string() } else { format!("{n} records of this file differ") };
    format!("{n} from what the camera holds now, as the file was opened: no edit of this session, but the editor cannot check them, and the camera may refuse the file. To be sure, read the camera and make your edits on that file; write this one only if you know where it came from.")
}

/// The windows' button that puts a value back to what the camera wrote (`Doc::baseline`), where Revert would change
/// nothing (a Save As kept the value): the window's, the detail panel's and the page's word for it.
pub(crate) const REVERT_TO_CAMERA: &str = "Revert to what the camera wrote";

/// The windows' button that puts the copies in step with a setting back at its value, where none of them holds it
/// (`App::issue_fix`): the window's and the page's word for it.
pub(crate) const COPIES_BACK_IN_STEP: &str = "Put its copies back in step";

/// A value the camera is not known to take as written (`App::acceptance_issues`), found before a save or send: where it
/// is (what puts it back, if anything does, is `App::issue_fix`), its name, value and why, and what it is.
#[derive(Clone)]
pub(crate) struct Issue {
    pub(crate) section: usize,
    pub(crate) slot: Slot,
    pub(crate) name: String,
    pub(crate) value: String,
    pub(crate) reason: String,
    pub(crate) kind: IssueKind,
}

impl App {
    /// The line over the values listed (`acceptance_issues`), the window's and the page's.
    pub(crate) fn issues_words(n: usize) -> String {
        let n = if n == 1 { "1 value".to_string() } else { format!("{n} values") };
        format!("{n} the camera is not known to take as written. One the camera refuses makes it reject the whole file.")
    }

    /// Whether file A is the sample, or a file made from it, however it was opened (`Definitions::is_sample`).
    pub(crate) fn is_sample_doc(&self) -> bool {
        self.doc.as_ref().is_some_and(|d| d.source == Source::Sample || self.defs.is_sample(&d.edited))
    }

    /// What the windows' Revert does for an issue, and its words, when there is one: put back what the file held when
    /// last opened or saved ("Revert"); where that holds the value already (a Save As kept it), what the camera wrote
    /// (`REVERT_TO_CAMERA`, `Doc::baseline`); for a setting none of whose copies holds its value, the copies in step with
    /// it put back at its value (`App::back_in_step`). None for what is not put back by itself: recovered edits, what only
    /// the camera's copy shows, a setting out of step with its copies since the file was opened (no copy was in step with
    /// it to put back), a value already where the camera wrote it.
    pub(crate) fn issue_fix(&self, is: &Issue) -> Option<(String, Vec<Action>)> {
        let doc = self.doc.as_ref()?;
        let si = is.section;
        if matches!(is.kind, IssueKind::Recovered | IssueKind::CameraOnly) {
            return None;
        }
        if is.kind == IssueKind::Copy {
            let main = self.schema.settings.iter().find(|s| s.slot() == is.slot && !s.copies.is_empty() && kept_in(s, si))?;
            let acts = self.back_in_step(main, si);
            return (!acts.is_empty()).then(|| (COPIES_BACK_IN_STEP.to_string(), acts));
        }
        let rec = |c: &CamSet, id: u16| c.sections.get(si).and_then(|x| x.get(id)).cloned();
        match is.slot {
            (id, None) => {
                let (now, opened, base) = (rec(&doc.edited, id), rec(&doc.original, id), rec(&doc.baseline, id));
                if now.is_none() {
                    None
                } else if now != opened {
                    Some(("Revert".into(), vec![Action::Revert(si, (id, None))]))
                } else if now != base {
                    base.map(|b| (REVERT_TO_CAMERA.into(), vec![Action::SetRecord(si, b)]))
                } else {
                    None
                }
            }
            slot => {
                let now = doc.value(si, slot)?;
                if Some(now) != doc.original_value(si, slot) {
                    Some(("Revert".into(), vec![Action::Revert(si, slot)]))
                } else {
                    let base = doc.baseline_value(si, slot)?;
                    (base != now).then(|| (REVERT_TO_CAMERA.into(), vec![Action::Set(si, slot, base)]))
                }
            }
        }
    }

    /// What the Before saving window lists (`judge`): the edits against the file as first opened or read in this
    /// session (`Doc::baseline`, which Save As does not move), and the edits recovered without that file.
    pub(crate) fn acceptance_issues(&self) -> Vec<Issue> {
        self.judge(None)
    }

    /// What the Write window lists (`judge`): as `acceptance_issues`, and once the camera has been read for this write
    /// (`before_write`), what differs from what the camera holds now too, under a heading of its own
    /// (`IssueKind::CameraOnly`) when nothing in this session changed it: so a file edited in another session, or saved
    /// and opened again, is judged as well, and a file nobody edited is never said to hold edits.
    pub(crate) fn write_issues(&self) -> Vec<Issue> {
        let camera = self.before_write.as_ref().filter(|b| b.came.elapsed() <= BEFORE_WRITE_FRESH).map(|b| &b.cam);
        self.judge(camera)
    }

    /// What the Write and Before saving windows list: every record of file A that differs from the file as first opened
    /// or read in this session (`Doc::baseline`) and is not known to be taken by the camera as written, under what it is
    /// (`IssueKind`); for a write, with `camera` the camera's own copy read just before it, what differs from that copy
    /// alone and cannot be vouched for (`IssueKind::CameraOnly`), the records the camera changes on every load
    /// (`camera.volatile_records`) and the values it keeps for itself (`unproved_reason` "state") left out; every value
    /// of another video system than the file was saved under in its live settings, changed or not; and every setting
    /// the file holds at a value none of its copies holds (`App::out_of_step`), changed or not. A record passes only
    /// when each setting covering its differing bytes was checked on the camera (`Setting::checked_on_camera`) and none
    /// of them refuses, rewrites or never offers its value; a copy the camera keeps of a value (`copy_of`) passes while
    /// it holds its setting's value, and bytes a mirror keeps in step with its copy are judged where that copy is. Edits
    /// recovered without the file as it was opened cannot be judged, and say so. Empty, and only then, when every such
    /// record passed.
    fn judge(&self, camera: Option<&CamSet>) -> Vec<Issue> {
        let mut out = Vec::new();
        let Some(doc) = &self.doc else { return out };
        let cam = &self.schema.camera;
        let named = |s: &Setting, si: usize| format!("{} ({})", s.name, cam.target_name(si));
        let mirrors: Vec<&camset_editor::schema::Mirror> = cam.mirrors.iter().filter(|m| m.stride_in(&doc.edited).is_some()).collect();
        let by_key = |k: &str| self.schema.settings.iter().find(|o| o.key == k);
        let in_step = |si: usize, id: u16, k: usize| mirrors.iter().any(|m| m.in_step(&doc.edited, si, id, k));
        if doc.recovered > 0 {
            out.push(Issue { section: 0, slot: (0, None), name: format!("{} recovered edit(s)", doc.recovered), value: String::new(),
                reason: "recovered from an earlier session without the file as it was opened, so the editor cannot tell which values they changed".into(), kind: IssueKind::Recovered });
        }
        // the bytes of a record that differ from another file's record of the same id (all of them where it has none)
        let differ = |c: &CamSet, si: usize, e: &camset::Record| -> Vec<usize> {
            match c.sections.get(si).and_then(|x| x.get(e.id)) {
                Some(o) if o.value.len() == e.value.len() => (0..e.value.len()).filter(|&k| o.value[k] != e.value[k]).collect(),
                _ => (0..e.value.len()).collect(),
            }
        };
        // every record that differs from the file as opened (edits), or for a write from the camera's copy alone
        let mut records: Vec<(usize, u16, Vec<usize>, Vec<usize>)> = Vec::new();
        for (si, sec) in doc.edited.sections.iter().enumerate() {
            for e in &sec.records {
                let edits = differ(&doc.baseline, si, e);
                let theirs: Vec<usize> = match camera {
                    Some(c) if !(si == 0 && cam.volatile_records.contains(&e.id)) => differ(c, si, e).into_iter().filter(|k| !edits.contains(k)).collect(),
                    _ => Vec::new(),
                };
                if !edits.is_empty() || !theirs.is_empty() {
                    records.push((si, e.id, edits, theirs));
                }
            }
        }
        for (si, id, edits, theirs) in records {
            let Some(e) = doc.edited.sections.get(si).and_then(|x| x.get(id)) else { continue };
            let mut covered = vec![false; e.value.len()];
            for s in self.schema.settings.iter().filter(|s| s.id == id && kept_in(s, si)) {
                // the bytes of the record the setting lives in: the whole record, one element, or a field
                let elem = e.elem_size as usize;
                let (a, b) = match s.index {
                    None => (0, e.value.len()),
                    Some(i) if i & camset::FIELD != 0 => { let at = (i & !camset::FIELD) as usize; (at, at + 2) }
                    Some(i) => (i as usize * elem, (i as usize + 1) * elem),
                };
                for c in covered.iter_mut().take(b).skip(a) {
                    *c = true;
                }
                let inside = |bytes: &[usize]| bytes.iter().copied().filter(|&k| k >= a && k < b).collect::<Vec<usize>>();
                let (mine, only_theirs) = (inside(&edits), inside(&theirs));
                // a value the camera keeps for itself (`unproved_reason` "state") changes as the camera is used: what only
                // the camera's copy shows of it is left out, as the records it changes on every load are
                let state = s.unproved_in(si).map(|u| u.kind.as_str()).or(s.unproved_reason.as_ref().map(|u| u.kind.as_str())) == Some("state");
                if mine.is_empty() && (only_theirs.is_empty() || state) {
                    continue;
                }
                // an edit of this session, under what it is; else what only the camera's copy shows, under its own heading
                let edited_here = !mine.is_empty();
                let issue = |kind: IssueKind, value: String, reason: String| {
                    let kind = if edited_here { kind } else { IssueKind::CameraOnly };
                    Issue { section: si, slot: s.slot(), name: named(s, si), value, reason, kind }
                };
                let bytes = if edited_here { &mine } else { &only_theirs };
                if s.text.is_some() {
                    let reason = if edited_here { "a text typed here; the camera was not seen to take it" } else { "a text the editor cannot check" };
                    out.push(issue(IssueKind::Text, e.text().unwrap_or_default(), reason.into()));
                    continue;
                }
                // a copy holding its setting's value is judged with that setting; one holding another, as the camera keeps
                // a Stills or Movie copy apart, is judged by its own proofs, as any setting is (whether the setting is held
                // by none of its copies is judged below)
                if let Some(main) = s.copy_of.as_deref().and_then(by_key) {
                    if doc.value(si, s.slot()).is_some() && doc.value(si, s.slot()) == doc.value(si, main.slot()) {
                        continue;
                    }
                }
                // a block the editor does not change itself, which a mirror keeps in step with its copy: judged where the
                // copy is, by the setting that changed it
                if !s.scalar && bytes.iter().all(|&k| in_step(si, id, k)) {
                    continue;
                }
                let Some(v) = doc.value(si, s.slot()).filter(|_| s.scalar) else {
                    let reason = if edited_here { "changed byte by byte; the editor does not change this record itself" } else { "a record the editor does not read value by value" };
                    out.push(issue(IssueKind::Raw, e.display_value(), reason.into()));
                    continue;
                };
                let hard = s.refused.contains(&v) || s.rewrite_of(v).is_some() || s.never_offered(v).is_some();
                match s.acceptance(v) {
                    Some(reason) if hard => out.push(issue(IssueKind::Refused, Self::describe(s, Some(v)), reason)),
                    _ if !s.checked_on_camera(v, si) => {
                        let reason = if state { "a value the camera keeps for itself, not a menu setting; the camera may refuse a file where it was changed" } else { "not checked on the camera yet; the camera may refuse a file holding it" };
                        out.push(issue(IssueKind::NotChecked, Self::describe(s, Some(v)), reason.into()));
                    }
                    _ => {}
                }
            }
            // bytes no setting covers: a raw edit, unless a mirror holds them in step with their copy (judged there); and
            // bytes only the camera's copy shows, which no setting covers, under their own heading
            let loose = |bytes: &[usize]| bytes.iter().any(|&k| !covered.get(k).copied().unwrap_or(false) && !in_step(si, id, k));
            let record = |kind, reason: &str| Issue { section: si, slot: (id, None), name: format!("Record 0x{id:04x} ({})", cam.target_name(si)), value: e.display_value(),
                reason: reason.into(), kind };
            if loose(&edits) {
                out.push(record(IssueKind::Raw, "changed byte by byte; no setting the editor knows covers these bytes"));
            } else if loose(&theirs) {
                out.push(record(IssueKind::CameraOnly, "bytes no setting the editor knows covers"));
            }
        }
        // a value of another video system than the file was saved under, changed or not, in the live settings
        // (`system_in`: the camera's own files hold either system's values in their memory sets)
        for s in self.schema.settings.iter().filter(|s| s.video_system_values.is_some()) {
            for si in (0..doc.edited.sections.len()).filter(|&si| kept_in(s, si)) {
                let Some(v) = doc.value(si, s.slot()) else { continue };
                if let Some(why) = self.other_system_words(s, v, si) {
                    out.push(Issue { section: si, slot: s.slot(), name: named(s, si), value: Self::describe(s, Some(v)), reason: why, kind: IssueKind::OtherSystem });
                }
            }
        }
        // a value the camera keeps in other records too that the file holds other than the camera keeps it, changed or
        // not (`out_of_step`): apart from the copy for its set's shooting mode, or where that mode is not known held by
        // none of its copies. No camera writes a file so; a copy for another mode, apart from its setting as the camera
        // keeps it, is never listed
        for o in self.out_of_step() {
            let (si, s) = (o.section, &self.schema.settings[o.setting]);
            let names: Vec<String> = o.copies.iter().map(|&c| self.schema.settings[c].name.clone()).collect();
            let reason = match &o.mode {
                Some(m) => {
                    let todo = if o.as_opened { "it was so when the file was opened or read: put its copy back in step, or read the camera again" } else { "put its copy back in step, or revert what was changed" };
                    format!("in {m} mode the camera keeps this value in {} too, and it holds another, which no camera writes; {todo}", and_list(&names))
                }
                None => {
                    let todo = if o.as_opened {
                        format!("it was so when the file was opened or read: set {} to a value one of them holds, or read the camera again", s.name)
                    } else {
                        "put its copies back in step with it, or revert what was changed".to_string()
                    };
                    format!("the camera keeps this value in {} too, and none of them holds it, which no camera writes; {todo}", and_list(&names))
                }
            };
            out.push(Issue { section: si, slot: s.slot(), name: named(s, si), value: Self::describe(s, doc.value(si, s.slot())), reason, kind: IssueKind::Copy });
        }
        out.sort_by_key(|i| i.kind);
        out
    }

    /// Write the open file to the camera: the Write window opens and reads the camera first (`JobKind::BeforeWrite`),
    /// lists what the write changes against it and the edited values the camera may refuse, and writes only when
    /// asked. A read that fails ends it with the report.
    pub(crate) fn send_to_camera(&mut self) {
        if let Some(why) = self.send_blocked() {
            self.status = why;
            return;
        }
        let issues = self.write_issues();
        self.review_rev = self.revision();
        self.pending = Some((Review::Send, issues));
        self.before_write = None;
        self.run_job(JobKind::BeforeWrite, None, None, None);
        if self.camera_job.is_none() {
            // the link could not start (no camera link program, no address): its report says why
            self.close_write_window();
        }
    }

    /// Write to camera in the Write window, for the file it checked: with the camera's settings it read a moment
    /// ago as the copy from just before; read longer ago than `BEFORE_WRITE_FRESH`, the camera is read again and
    /// the window lists again.
    fn write_confirmed(&mut self) {
        match self.before_write.take() {
            Some(b) if b.came.elapsed() <= BEFORE_WRITE_FRESH => { let _ = self.send_with(Some(b.path)); }
            _ => {
                self.send_to_camera();
                if self.pending.is_some() {
                    self.status = "The camera was read more than five minutes ago: it is read again, so the Write window lists what it holds now.".into();
                }
            }
        }
    }

    /// Why the open file may not be written to the camera now, in plain words; None when it may. The same rule for
    /// the window's Write and the web page's: only a file the editor may edit (its firmware checked, or "Edit
    /// anyway" turned on for it), of the model the camera definition is for, never the sample, one job at a time. The
    /// sample is known by its header however it came (opened from disk, saved and opened again, sent up from the page):
    /// the model and save time of a sample beside a definition (`Definitions::is_sample`).
    pub(crate) fn send_blocked(&self) -> Option<String> {
        let Some(d) = &self.doc else { return Some("No file is open. Read the camera or open a file first.".into()) };
        if d.source == Source::Sample {
            return Some("The sample is not a camera's own file, so it is not written to a camera: read your camera or open your own settings file first.".into());
        }
        if self.defs.is_sample(&d.edited) {
            return Some(SAMPLE_NOT_WRITTEN.into());
        }
        if self.schema.model.is_empty() {
            return Some(format!("This file is from a {}, which no camera definition covers, so it is not written to a camera from here.", d.edited.model()));
        }
        if d.edited.model() != self.schema.model {
            return Some(format!("This file is from a {}, and the camera definition is for the {}, so it is not written to a camera from here.", d.edited.model(), self.schema.model));
        }
        if !self.editable() {
            return Some("This file is view only: its firmware has not been checked yet, so it is not written to a camera. \"Edit anyway…\" next to the file name turns editing on for it.".into());
        }
        if self.camera_job.is_some() {
            return Some("The camera link is busy: wait for the current camera action to finish, then try again.".into());
        }
        None
    }

    /// Which file, with which contents, is open: what the Write window checked must be what is written.
    pub(crate) fn revision(&self) -> Option<u64> {
        let d = self.doc.as_ref()?;
        let mut bytes = d.path.to_string_lossy().as_bytes().to_vec();
        bytes.extend(d.edited.to_bytes());
        Some(fnv1a(&bytes))
    }

    /// Write the open file to the camera, when `send_blocked` lets it, reading the camera first: Err says why not
    /// (the status too). The window and the page write with the read their Write made (`send_with`); the tests
    /// write this way.
    #[cfg(test)]
    fn do_send(&mut self) -> Result<(), String> {
        self.send_with(None)
    }

    /// `do_send`, with `before` the camera's settings the Write window read a moment ago (else the write reads them
    /// first).
    pub(crate) fn send_with(&mut self, before: Option<PathBuf>) -> Result<(), String> {
        if let Some(why) = self.send_blocked() {
            self.status = why.clone();
            return Err(why);
        }
        let Some(doc) = &self.doc else { return Err("No file is open.".into()) };
        let dir = Self::camera_dir();
        let f = dir.join(format!("SEND_{}.DAT", file_stamp()));
        let bytes = doc.edited.to_bytes();
        let parsed = match CamSet::parse(&bytes, doc.edited.format()) {
            Ok(c) => c,
            Err(e) => {
                let details = details(self.prefs.expert, &e);
                let why = format!("Nothing written: the edited file did not read back as a settings file. Undo the last edit, then try again.{details}");
                self.status = why.clone();
                return Err(why);
            }
        };
        if let Err(e) = std::fs::create_dir_all(&dir).and_then(|_| write_atomic(&f, &bytes)) {
            let details = details(self.prefs.expert, format_args!("{}: {e}", f.display()));
            let why = format!("Nothing written: the copy to send could not be kept on this computer, because {}{details}", io_words(&e, true));
            self.status = why.clone();
            return Err(why);
        }
        self.sent = Some((f.clone(), parsed));
        self.run_job(JobKind::Send, Some(f), None, before);
        Ok(())
    }

    /// Values in the file about to be sent that would cut the link the editor is using.
    pub(crate) fn link_warnings(&self) -> Vec<String> {
        let Some(doc) = &self.doc else { return Vec::new() };
        let live = |id: u16| doc.edited.sections.first().and_then(|s| s.get(id)).and_then(|r| r.get(None));
        self.schema.camera.link_warnings(if self.prefs.link == "network" { "network" } else { "usb" }, live)
    }

    /// The acceptance window: issues before a save or a send, with revert, go-ahead and cancel.
    pub(crate) fn pending_window(&mut self, ctx: &egui::Context) {
        let Some((what, issues)) = self.pending.clone() else { return };
        let sending = what == Review::Send;
        let mut actions = Vec::new();
        let mut go = false;
        let mut cancel = false;
        let unchecked = self.doc.as_ref().filter(|d| d.unchecked_ok).map(|d| d.edited.firmware());
        // a write reads the camera first; Write to camera waits for that read
        let reading = sending && self.camera_job.as_ref().is_some_and(|j| j.kind == JobKind::BeforeWrite);
        let wait = (sending && self.before_write.is_none()).then_some("The camera is read first, so the window can list what the write changes");
        egui::Window::new(if sending { "Write to camera" } else { "Before saving" }).collapsible(false).resizable(true).default_width(640.0).show(ctx, |ui| {
            // the sample, or a file made from it, about to be saved: never for a camera
            if !sending && self.is_sample_doc() {
                ui.label(RichText::new(SAMPLE_NOT_FOR_A_CAMERA).color(tone::caution(ui.visuals())).strong());
                ui.add_space(4.0);
            }
            if let Some(fw) = &unchecked {
                ui.label(RichText::new(format!("This file is from firmware {fw}, which the camera definition was not checked on: the camera may refuse the file or change values.{}",
                    if sending { " The editor reads the camera first and reads it back afterwards; ↩ Put the camera back undoes the write." } else { "" }))
                    .color(tone::caution(ui.visuals())));
                ui.add_space(4.0);
            }
            // a write lists it first among what it changes (`send_summary`); a save, and a write still reading, here
            if let Some(line) = self.override_line().filter(|_| !sending || reading) {
                ui.label(RichText::new(line).color(tone::caution(ui.visuals())).strong());
                ui.add_space(4.0);
            }
            if sending && reading {
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label(RichText::new("Reading the camera, to list what this write changes…").strong());
                });
                ui.label(RichText::new(format!("Usually about {}. Nothing is written until you press Write to camera.", self.read_words())).small().color(tone::weak(ui.visuals())));
                ui.add_space(6.0);
            } else if sending {
                for (line, warn) in self.send_summary() {
                    if warn { ui.label(RichText::new(line).color(tone::caution(ui.visuals()))); } else { ui.label(line); }
                }
                ui.add_space(6.0);
            }
            if sending {
                self.write_warning_ui(ui);
                ui.add_space(4.0);
                for w in self.link_warnings() {
                    ui.label(RichText::new(w).color(tone::caution(ui.visuals())).strong());
                }
                ui.add_space(6.0);
            }
            // what only the camera's copy shows is no flagged value, though it keeps the all-clear away
            let flagged = issues.iter().filter(|is| is.kind != IssueKind::CameraOnly).count();
            let theirs = issues.len() - flagged;
            if issues.is_empty() {
                ui.label(RichText::new(ALL_CLEAR).color(tone::ok(ui.visuals())));
            } else {
                if flagged > 0 {
                    ui.label(RichText::new(Self::issues_words(flagged)).color(tone::caution(ui.visuals())));
                    ui.label(RichText::new(ISSUES_TODO).small());
                }
                if theirs > 0 {
                    ui.label(RichText::new(camera_only_words(theirs)).color(tone::caution(ui.visuals())));
                }
                ui.add_space(4.0);
                egui::ScrollArea::vertical().max_height(320.0).show(ui, |ui| {
                    // under what each is, in the order of `IssueKind`
                    let mut last: Option<IssueKind> = None;
                    for (i, is) in issues.iter().enumerate() {
                        if last != Some(is.kind) {
                            let (head, line) = is.kind.heading();
                            ui.add_space(4.0);
                            ui.label(RichText::new(head).strong()).on_hover_text(line);
                            ui.label(RichText::new(line).small().color(tone::weak(ui.visuals())));
                            last = Some(is.kind);
                        }
                        ui.horizontal_wrapped(|ui| {
                            ui.label(&is.name);
                            ui.label(RichText::new(&is.value).strong());
                            ui.label(RichText::new(&is.reason).small());
                            // Revert, back to what the camera wrote where a Save As kept the value, or copies back in step (`issue_fix`)
                            if let Some((words, fix)) = self.issue_fix(is) {
                                if ui.small_button(words).clicked() {
                                    actions.extend(fix);
                                    let mut rest = issues.clone(); rest.remove(i);
                                    self.pending = Some((what, rest));
                                }
                            }
                        });
                    }
                });
            }
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                let fixes: Vec<(usize, Vec<Action>)> = issues.iter().enumerate().filter_map(|(i, is)| self.issue_fix(is).map(|(_, a)| (i, a))).collect();
                if !fixes.is_empty() && ui.button("Revert all flagged").clicked() {
                    let done: Vec<usize> = fixes.iter().map(|(i, _)| *i).collect();
                    actions.extend(fixes.into_iter().flat_map(|(_, a)| a));
                    self.pending = Some((what, issues.iter().enumerate().filter(|(i, _)| !done.contains(i)).map(|(_, is)| is.clone()).collect()));
                }
                // with values listed, the go-ahead says it goes ahead with them
                let label = match (sending, flagged, theirs) {
                    (true, 0, 0) => "⬆ Write to camera".to_string(),
                    (true, 0, _) => "⬆ Write anyway".to_string(),
                    (true, n, _) => format!("⬆ Write anyway, with {n} flagged"),
                    (false, 0, _) => "Save As…".to_string(),
                    (false, n, _) => format!("Save anyway, with {n} flagged"),
                };
                let (g, c) = Self::review_buttons(ui, &label, wait);
                go |= g;
                cancel |= c;
            });
        });
        let reverted = !actions.is_empty();
        self.apply(actions);
        if sending && reverted {
            // the window's own Revert changed the file it checks: that is the file to write now
            self.review_rev = self.revision();
        }
        if cancel {
            self.pending = None;
            self.review_rev = None;
            if !sending && self.after_save.take().is_some() { self.status = "Not saved: your edits stay open.".into(); }
        } else if go {
            self.pending = None;
            if !sending {
                self.save_file_dialog(ctx);
            } else if self.review_rev.take() != self.revision() {
                // another file was opened, or this one edited, while the window was open (from the page, say)
                self.status = "Nothing written: the file changed while the Write window was open. Press Write again to check what will be written.".into();
            } else {
                self.write_confirmed();
            }
        }
    }

    /// The Write window's warning, in normal-size text: what a write replaces, the restart loop an edited file
    /// once caused, the camera's own copy to save on its card first, and to leave the camera on and connected.
    pub(crate) fn write_warning_ui(&self, ui: &mut egui::Ui) {
        let save = self.schema.camera.text.save_load_path.as_deref().filter(|p| !p.is_empty()).map(|p| format!(" ({p})")).unwrap_or_default();
        egui::Frame::new().fill(tone::raised(ui.visuals())).corner_radius(4.0).inner_margin(10.0).show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            ui.label(RichText::new("Writing replaces every setting on the camera, memories and custom keys included, and the camera restarts.").strong());
            ui.add_space(2.0);
            ui.label(format!("An edited file has once made a camera restart over and over. Before you write, save the camera's own copy to its card{save}, so you can load it back on the camera."));
            ui.add_space(2.0);
            ui.label(format!("{}.", check_words(&self.job_timing())));
        });
    }

    /// The buttons at the foot of the Write and Before saving windows: the go-ahead as the main button (off, with
    /// `wait` as the reason, while it must wait), and Cancel, which Esc presses and which holds the keyboard focus,
    /// so Enter never writes by accident. (go, cancel)
    fn review_buttons(ui: &mut egui::Ui, label: &str, wait: Option<&str>) -> (bool, bool) {
        let v = ui.visuals().clone();
        let main = egui::Button::new(RichText::new(label).strong().color(tone::chosen_text(&v))).fill(tone::chosen(&v));
        let go = ui.add_enabled(wait.is_none(), main).on_disabled_hover_text(wait.unwrap_or_default()).clicked();
        let cancel = ui.button("Cancel").on_hover_text("Close this window; nothing is written (Esc)");
        if ui.memory(|m| m.focused().is_none()) { cancel.request_focus(); }
        let esc = ui.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape));
        (go, cancel.clicked() || esc)
    }

    /// Plain words for what a write would change on the camera: against the camera's settings the Write window read
    /// a moment ago (`before_write`), else against its last read (the page's Write), else that it cannot say yet.
    pub(crate) fn send_summary(&self) -> Vec<(String, bool)> {
        let mut out: Vec<(String, bool)> = self.override_line().map(|l| (l, true)).into_iter().collect();
        let Some(doc) = &self.doc else { return out };
        let (cam, when) = match (self.before_write.as_ref().filter(|b| b.came.elapsed() <= BEFORE_WRITE_FRESH), &self.last_camera) {
            (Some(b), _) => (&b.cam, None),
            (None, Some((at, cam))) => (cam, Some(when_words(at))),
            (None, None) => {
                out.push(("The editor has not read this camera since it started, so it cannot list yet what will change: the whole file replaces the camera's settings. When you press Write, it reads the camera first and keeps that copy (↩ Put the camera back writes it again); after the restart it lists every setting that differs from this file.".into(), true));
                return out;
            }
        };
        let diffs = self.record_diff(cam, &doc.edited);
        if diffs.is_empty() {
            out.push((match &when {
                None => "Nothing changes: this file holds what the camera holds now.".to_string(),
                Some(w) => format!("Nothing changes: this file holds what the camera held when it was last read ({w})."),
            }, false));
            return out;
        }
        let named: Vec<&(usize, u16, String)> = diffs.iter().filter(|d| d.2 != "(unmapped)").collect();
        let unmapped = diffs.len() - named.len();
        let compared = match &when { None => "Compared with the camera now".to_string(), Some(w) => format!("Compared with what the camera held when it was last read ({w})") };
        let n = if named.len() == 1 { "1 setting".to_string() } else { format!("{} settings", named.len()) };
        let more = if unmapped > 0 { format!(" and {unmapped} more the editor cannot name yet") } else { String::new() };
        out.push((format!("{compared}, this changes {n}{more}:"), false));
        for (si, id, name) in named.iter().take(10) {
            let s = self.schema.find(*si != 0, *id);
            let fmt = |c: &CamSet| c.sections.get(*si).and_then(|sec| sec.get(*id)).map(|r| {
                let raw = r.display_value();
                s.and_then(|s| raw.parse::<i64>().ok().and_then(|v| s.label_for(v).map(|l| l.to_string()))).unwrap_or(raw)
            }).unwrap_or_default();
            out.push((format!("    {}{}: {} ➡ {}", if *si == 0 { String::new() } else { format!("{} · ", self.schema.camera.target_name(*si)) }, name, fmt(cam), fmt(&doc.edited)), false));
        }
        if named.len() > 10 { out.push((format!("    … and {} more (see All edits for the full list)", named.len() - 10), false)); }
        out
    }
}

/// Safety and data integrity: what is written to the camera or a disk, and edits never lost without a question.
#[cfg(test)]
pub(crate) mod safety_tests {
    use super::*;
    use crate::test_support::camera_file;

    const SAMPLE: &[u8] = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");

    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("camset_safety_test_{name}_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    /// A camera's own file (`camera_file`) with its header saying firmware 2.00, its Creative Look record (0x0cde) cut
    /// from 18 slots to 16 in the live settings and a later record left out: a file from another firmware, as
    /// `firmware_tests` makes it.
    pub(crate) fn other_firmware() -> CamSet {
        let mut c = test_parse(&camera_file()).unwrap();
        c.header[0x36..=0x38].copy_from_slice(&[2, 0, 0]);
        let r = c.sections[0].get_mut(0x0cde).unwrap();
        r.count = 16;
        r.value.truncate(16 * r.elem_size as usize);
        c.sections[0].records.retain(|r| r.id != 0x13ad);
        c
    }

    /// A camera's own file (`camera_file`) with its video system byte at `v`, where the shipped block says it is (0 is
    /// NTSC and 1 PAL in its names), as if saved with the camera set to that one; the same firmware and layout.
    pub(crate) fn with_video_system(v: u8) -> CamSet {
        let mut c = test_parse(&camera_file()).unwrap();
        let at = test_block().video_system.as_ref().and_then(|f| f.at.at(SAMPLE.len())).expect("the shipped block says where the video system is");
        c.header[at] = v;
        c
    }

    /// The sample saved under another model's name (a made-up one).
    pub(crate) fn other_model() -> CamSet {
        let mut c = test_parse(SAMPLE).unwrap();
        let name = b"ILCE-0TEST";
        c.header[5..0x15].fill(0);
        c.header[5..5 + name.len()].copy_from_slice(name);
        c
    }

    /// An app with `bytes` opened from a file of its own (a file on disk, not the sample).
    fn opened(dir: &Path, name: &str, bytes: &[u8]) -> App {
        let f = dir.join(name);
        std::fs::write(&f, bytes).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        app.open(f.clone());
        assert_eq!(app.doc.as_ref().map(|d| d.path.clone()), Some(f));
        app
    }

    /// A setting the live settings hold as one number, and a value it can take other than the one it holds.
    pub(crate) fn changeable(app: &App) -> (Setting, i64) {
        app.schema.settings.iter().filter(|s| s.area == "global" && s.scalar && s.text.is_none() && s.values.len() >= 2 && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none())
            .find_map(|s| {
                let cur = app.col_value(Col::a(0), s)?;
                s.values.iter().map(|(v, _)| *v).find(|v| *v != cur && s.acceptance(*v).is_none()).map(|v| (s.clone(), v))
            })
            .expect("a setting with another accepted value")
    }

    /// An edit of file A, as the window makes one.
    fn edit(app: &mut App) -> (Setting, i64) {
        let (s, v) = changeable(app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert_eq!(app.unsaved(), 1);
        (s, v)
    }

    /// E-05: arrow keys on a tab that shows no groups (Only edited with no edits), or with no tabs at all, do not
    /// crash the editor.
    #[test]
    fn empty_tab_and_an_arrow_key_do_not_panic() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let tab = app.schema.tabs[0].clone();
        (app.mode, app.view, app.only_changed, app.focus) = (Mode::Edit, View::Tab(tab.clone()), true, Focus::Groups);
        assert!(app.tab_groups(&tab).is_empty(), "no edits: the tab shows no groups");
        let down = || egui::RawInput {
            events: vec![egui::Event::Key { key: egui::Key::ArrowDown, physical_key: None, pressed: true, repeat: false, modifiers: Default::default() }],
            ..Default::default()
        };
        let ctx = egui::Context::default();
        let _ = ctx.run(down(), |ctx| {
            app.keyboard_nav(ctx);
            egui::CentralPanel::default().show(ctx, |ui| { app.menu_view(ui, &tab); });
        });
        app.schema.tabs.clear();
        app.focus = Focus::Tabs;
        let _ = ctx.run(down(), |ctx| app.keyboard_nav(ctx));
        assert_eq!(step_in(0, 0, 1), None);
        assert_eq!(step_in(3, 2, 1), Some(2));
        assert_eq!(step_in(3, 0, -1), Some(0));
    }

    /// E-03: before a write, the camera's copy must be the same model with the same record layout as the file.
    #[test]
    fn write_check_wants_the_same_model_and_layout() {
        let sample = SAMPLE.to_vec();
        assert_eq!(write_check(&sample, &sample, Some(&test_block())), Ok(()));
        let older = other_firmware().to_bytes();
        match write_check(&older, &sample, Some(&test_block())) {
            Err(Wrote::Mismatch(why)) => assert!(why.contains("firmware 2.00") && why.contains("Nothing was written"), "{why}"),
            other => panic!("another firmware: {other:?}"),
        }
        match write_check(&other_model().to_bytes(), &sample, Some(&test_block())) {
            Err(Wrote::Mismatch(why)) => assert!(why.contains("ILCE-0TEST"), "{why}"),
            other => panic!("another model: {other:?}"),
        }
        assert_eq!(write_check(&sample[..sample.len() / 2], &sample, Some(&test_block())), Err(Wrote::NotRead), "a copy cut short");
        assert!(matches!(write_check(&sample, b"not a file", Some(&test_block())), Err(Wrote::Mismatch(_))));
    }

    /// Before a write, where the block says where the video system is: a file saved under another one than the camera
    /// is set to is not written (`WRITE_ACROSS_VIDEO_SYSTEMS`, off), and the reason names both in the block's words and
    /// says what to do; the same one is written. A block that does not say where it is checks nothing of it, as before.
    /// Turning the rule on is what this test then fails for, on purpose.
    #[test]
    fn write_check_wants_the_same_video_system() {
        let (ntsc, pal) = (with_video_system(0).to_bytes(), with_video_system(1).to_bytes());
        assert_eq!(test_parse(&pal).unwrap().layout_signature(), test_parse(&ntsc).unwrap().layout_signature(), "one firmware, one layout");
        let refused = |cam: &[u8], file: &[u8]| match write_check(cam, file, Some(&test_block())) {
            Err(Wrote::Mismatch(why)) => why,
            other => panic!("another video system: {other:?}"),
        };
        let why = refused(&ntsc, &pal);
        assert!(why.starts_with("Nothing was written: the camera is set to NTSC, and this file was saved by a camera set to PAL."), "{why}");
        assert!(why.contains("different frame rates") && why.contains("Read the camera and make your edits on that file, or open a file saved while the camera was set to NTSC."), "{why}");
        assert!(refused(&pal, &ntsc).starts_with("Nothing was written: the camera is set to PAL, and this file was saved by a camera set to NTSC."));
        assert_eq!(write_check(&pal, &pal, Some(&test_block())), Ok(()));
        assert_eq!(write_check(&ntsc, &ntsc, Some(&test_block())), Ok(()));
        // a value the block names nothing for: its number, and what is odd about it
        let why = refused(&with_video_system(7).to_bytes(), &ntsc);
        assert!(why.contains("the camera is set to video system 7, which the camera definition has no name for, and this file was saved by a camera set to NTSC"), "{why}");
        // a block that does not say where the video system is (the reading before 2026-11-06): nothing of it is checked
        let p = Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.json");
        let mut v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
        v["camera"]["file"].as_object_mut().unwrap().remove("video_system");
        let without: std::sync::Arc<FileFormat> = std::sync::Arc::new(serde_json::from_value(v["camera"]["file"].clone()).unwrap());
        assert_eq!(write_check(&ntsc, &pal, Some(&without)), Ok(()));
    }

    /// E-04: a write is confirmed only by "Upload accepted." and a clean exit; an error exit is a refusal; anything
    /// else may have been written.
    #[test]
    fn upload_outcomes() {
        assert_eq!(upload_outcome(Some(0), "Uploading x. The camera will reboot.\nUpload accepted.\n"), Wrote::Confirmed);
        assert_eq!(upload_outcome(Some(1), "upload error CrError_Generic\n"), Wrote::Refused);
        assert_eq!(upload_outcome(Some(NOT_RUN), "could not run camset_probe"), Wrote::Refused);
        assert_eq!(upload_outcome(Some(0), "No confirmation received; check the camera.\n"), Wrote::Unconfirmed);
        assert_eq!(upload_outcome(Some(0), "x = 3  NOT accepted\n"), Wrote::Unconfirmed, "\"accepted\" alone is no confirmation");
        assert_eq!(upload_outcome(None, "Upload accepted.\n"), Wrote::Unconfirmed, "stopped by a signal");
        assert_eq!(upload_outcome(Some(1), "Upload accepted.\n"), Wrote::Refused);
    }

    /// E-03, the review's test 5: the write job sends nothing unless the camera's copy read just before fits the file.
    #[test]
    fn send_job_uploads_only_over_a_fitting_copy() {
        let dir = scratch("send_job");
        let file = dir.join("SEND_test.DAT");
        std::fs::write(&file, SAMPLE).unwrap();
        let before = dir.join("before_write_test.DAT");
        let cases: [(Option<Vec<u8>>, &str); 5] = [
            (Some(SAMPLE.to_vec()), "Upload accepted.\n"),
            (Some(SAMPLE.to_vec()), "No confirmation received; check the camera.\n"),
            (Some(other_firmware().to_bytes()), ""),
            (Some(other_model().to_bytes()), ""),
            (Some(SAMPLE[..1000].to_vec()), ""),
        ];
        let mut outcomes = Vec::new();
        for (copy, said) in cases.iter().cloned().chain([(None, "")]) {
            let _ = std::fs::remove_file(&before);
            let mut uploads = 0;
            let mut run = |args: Vec<std::ffi::OsString>| -> (Option<i32>, String) {
                match args[0].to_str() {
                    Some("download") => {
                        if let Some(c) = &copy { std::fs::write(&before, c).unwrap(); }
                        (Some(0), "Camera: USB\n".into())
                    }
                    Some("upload") => { uploads += 1; (Some(0), said.to_string()) }
                    _ => (Some(2), String::new()),
                }
            };
            let done = send_job(&mut run, &dir, &before, true, &file, Some(&test_block()));
            outcomes.push((done.wrote.clone(), uploads, done.res.is_ok()));
        }
        assert_eq!(outcomes[0], (Some(Wrote::Confirmed), 1, true));
        assert_eq!(outcomes[1], (Some(Wrote::Unconfirmed), 1, false));
        assert!(matches!(outcomes[2], (Some(Wrote::Mismatch(_)), 0, false)), "another firmware: {:?}", outcomes[2]);
        assert!(matches!(outcomes[3], (Some(Wrote::Mismatch(_)), 0, false)), "another model: {:?}", outcomes[3]);
        assert_eq!(outcomes[4], (Some(Wrote::NotRead), 0, false), "a copy cut short");
        assert_eq!(outcomes[5], (Some(Wrote::NotRead), 0, false), "no copy at all");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-07, the review's test 4: a read whose file does not open leaves file A as it was (from disk), takes nothing
    /// as the camera's settings, and says so.
    #[test]
    fn a_read_that_does_not_open_changes_nothing() {
        let dir = scratch("bad_read");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        let bad = dir.join("camera_cut.DAT");
        std::fs::write(&bad, &SAMPLE[..SAMPLE.len() - 100]).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Ok((bad, "Camera: USB\n".into())), None));
        app.poll_camera_job();
        let d = app.doc.as_ref().unwrap();
        assert_eq!(d.path, dir.join("CAMSET01.DAT"));
        assert!(d.source == Source::Disk, "still the file from disk");
        assert!(app.last_camera.is_none(), "nothing taken as the camera's settings");
        let r = app.camera_report.as_ref().unwrap();
        assert!(!r.ok && r.title.contains("could not be opened"), "{}", r.title);
        assert!(r.lines.iter().all(|(l, _)| !l.contains("0x")), "no technical details outside Expert mode");
        // a read that opens is the camera's settings
        let good = dir.join("camera_good.DAT");
        std::fs::write(&good, SAMPLE).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Ok((good.clone(), "Camera: USB\n".into())), None));
        app.poll_camera_job();
        assert_eq!(app.doc.as_ref().map(|d| d.path.clone()), Some(good));
        assert!(matches!(app.doc.as_ref().unwrap().source, Source::Camera { .. }));
        assert!(app.last_camera.is_some());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-04, the review's test 4: a write the camera did not confirm keeps the copy from just before, offers to put it
    /// back, says it may have been written and checks what the camera holds.
    #[test]
    fn an_unconfirmed_write_keeps_the_copy_and_checks() {
        let dir = scratch("unconfirmed");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        // a stand-in for the camera link program that cannot run: the check started below talks to no camera
        app.prefs.probe_path = Some(dir.join("CAMSET01.DAT").display().to_string());
        let before = dir.join("before_write_test.DAT");
        std::fs::write(&before, SAMPLE).unwrap();
        app.sent = Some((dir.join("SEND_test.DAT"), test_parse(SAMPLE).unwrap()));
        let mut job = CameraJob::finished(JobKind::Send, Err("No confirmation received; check the camera.\n".into()), Some(Wrote::Unconfirmed));
        job.backup = Some(before.clone());
        app.camera_job = Some(job);
        app.poll_camera_job();
        assert_eq!(app.camera_backup.as_ref().map(|(_, p)| p.clone()), Some(before));
        let r = app.camera_report.as_ref().unwrap();
        assert!(r.title.contains("may have been written") && r.put_back, "{}", r.title);
        assert_eq!(app.camera_job.as_ref().map(|j| j.kind), Some(JobKind::Verify), "the read-back check runs");
        // a write refused before anything was sent keeps nothing and offers no put-back
        app.camera_job = None;
        app.camera_backup = None;
        app.camera_job = Some(CameraJob::finished(JobKind::Send, Err(String::new()), Some(Wrote::Mismatch("Nothing was written: the camera has firmware 2.00.".into()))));
        app.poll_camera_job();
        let r = app.camera_report.as_ref().unwrap();
        assert!(r.title.contains("Nothing written") && !r.put_back && r.retry.is_none(), "{}", r.title);
        assert!(r.lines[0].0.contains("firmware 2.00"));
        assert!(app.camera_backup.is_none() && app.camera_job.is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The read-back check after a write, for `sent` (a file `name` with `back` in it, the camera's answer).
    fn read_back(app: &mut App, dir: &Path, name: &str, sent: (&str, CamSet), back: &CamSet) {
        app.sent = Some((dir.join(sent.0), sent.1));
        let p = dir.join(name);
        std::fs::write(&p, back.to_bytes()).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::Verify, Ok((p, "Camera: USB\n".into())), None));
        app.poll_camera_job();
    }

    /// A second setting to edit, another record than `not`'s, and a value it can take.
    fn other_edit(app: &App, not: u16) -> (Setting, i64) {
        app.schema.settings.iter().filter(|s| s.area == "global" && s.scalar && s.text.is_none() && s.values.len() >= 2 && s.id != not && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none())
            .find_map(|s| {
                let cur = app.col_value(Col::a(0), s)?;
                s.values.iter().map(|(v, _)| *v).find(|v| *v != cur && s.acceptance(*v).is_none()).map(|v| (s.clone(), v))
            })
            .expect("a second setting with another accepted value")
    }

    /// A write the camera confirmed: file A read from the camera starts from the read-back (no edits left, the report
    /// says so, the journal of unsaved edits goes, Undo stays with the records the camera changes on every load
    /// carried into its steps); an edit made while the check ran stays an edit; putting the camera back follows the
    /// same rule, so the edits it took back show as edits again.
    #[test]
    fn a_confirmed_write_is_where_a_camera_read_starts() {
        let dir = scratch("confirmed_camera");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        let vol = app.schema.camera.volatile_records[0];
        app.doc.as_mut().unwrap().source = Source::Camera { link: "USB".into(), read_at: "20261106_100000".into() };
        let before = app.doc.as_ref().unwrap().original.clone();
        let (s, v) = edit(&mut app);
        let now = std::time::Instant::now();
        app.journal_at(now);
        app.journal_at(now + recovery::WAIT);
        app.journal.finish();
        let base = app.journal.base().expect("the edit is journalled").to_string();
        // the camera holds the file written, its every-load record changed
        let sent = app.doc.as_ref().unwrap().edited.clone();
        let mut back = sent.clone();
        back.sections[0].get_mut(vol).unwrap().value[0] ^= 1;
        read_back(&mut app, &dir, "verify_1.DAT", ("SEND_1.DAT", sent), &back);
        let r = app.camera_report.as_ref().unwrap();
        assert!(r.ok && r.put_back, "{}", r.title);
        assert!(r.lines.iter().any(|(l, _)| l.contains("Your edits are on the camera now, so none are left unsaved") && l.ends_with("↩ Put the camera back undoes the write.")), "{:?}", r.lines);
        let d = app.doc.as_ref().unwrap();
        assert_eq!((app.unsaved(), d.path.clone(), d.saved), (0, dir.join("verify_1.DAT"), false));
        assert!(matches!(&d.source, Source::Camera { link, .. } if link == "USB"));
        assert!(App::same_records(&d.original, &back) && App::same_records(&d.edited, &back));
        assert_eq!(d.value(0, s.slot()), Some(v));
        assert!(!app.edits_on_camera(), "nothing unsaved to speak of");
        // the journal of unsaved edits goes
        app.journal_at(std::time::Instant::now());
        app.journal.finish();
        assert!(app.journal.base().is_none() && recovery::paths(&App::recovery_dir(), &base).iter().all(|f| !f.exists()));
        // Undo stays: its step has the camera's every-load record, so a step back is the one edit against the camera
        assert_eq!(app.undo.len(), 1);
        assert_eq!(app.undo[0].sections[0].get(vol), back.sections[0].get(vol));
        app.undo();
        assert_eq!(app.unsaved(), 1);
        app.redo();
        assert_eq!(app.unsaved(), 0);

        // written again, and another edit made while the check runs: that one stays an edit, the every-load record is none
        let sent = app.doc.as_ref().unwrap().edited.clone();
        let (s2, v2) = other_edit(&app, s.id);
        app.apply(vec![Action::Set(0, s2.slot(), v2)]);
        let mut back2 = sent.clone();
        back2.sections[0].get_mut(vol).unwrap().value[0] ^= 1;
        read_back(&mut app, &dir, "verify_2.DAT", ("SEND_2.DAT", sent), &back2);
        let r = app.camera_report.as_ref().unwrap();
        assert!(r.lines.iter().any(|(l, _)| l.contains("1 edit on screen differs from it: it is not on the camera")), "{:?}", r.lines);
        let d = app.doc.as_ref().unwrap();
        assert_eq!(d.changes(), vec![(0, s2.id)]);
        assert_eq!((d.value(0, s2.slot()), d.edited.sections[0].get(vol)), (Some(v2), back2.sections[0].get(vol)));

        // put back as it was before the first write: the edits the camera no longer holds are edits again
        read_back(&mut app, &dir, "verify_3.DAT", ("before_write_1.DAT", before.clone()), &before);
        let d = app.doc.as_ref().unwrap();
        assert!(App::same_records(&d.original, &before));
        let mut ids: Vec<u16> = d.changes().into_iter().map(|(_, id)| id).collect();
        ids.sort();
        let mut want = vec![s.id, s2.id];
        want.sort();
        assert_eq!(ids, want);
        assert!(app.camera_report.as_ref().unwrap().lines.iter().any(|(l, _)| l.contains("2 edits on screen differ from it")));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// A write the camera confirmed, of a file from disk: the file is unchanged, so its edits stay edits, said to be
    /// on the camera but not saved to the file (the counter, the report, the page) until a further edit or an undo;
    /// a read-back that differs changes nothing.
    #[test]
    fn a_confirmed_write_of_a_file_keeps_its_edits() {
        let dir = scratch("confirmed_disk");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        let vol = app.schema.camera.volatile_records[0];
        let (s, v) = edit(&mut app);
        let sent = app.doc.as_ref().unwrap().edited.clone();
        // a read-back that differs: as before
        let mut wrong = sent.clone();
        wrong.sections[0].get_mut(s.id).unwrap().value = app.doc.as_ref().unwrap().original.sections[0].get(s.id).unwrap().value.clone();
        read_back(&mut app, &dir, "verify_0.DAT", ("SEND_0.DAT", sent.clone()), &wrong);
        assert!(!app.camera_report.as_ref().unwrap().ok);
        assert!(!app.edits_on_camera() && app.unsaved() == 1);
        assert_eq!(app.unsaved_words(1), "1 unsaved edit(s)");
        // confirmed: the edit stays, on the camera but not in the file
        let mut back = sent.clone();
        back.sections[0].get_mut(vol).unwrap().value[0] ^= 1;
        read_back(&mut app, &dir, "verify_1.DAT", ("SEND_1.DAT", sent), &back);
        let d = app.doc.as_ref().unwrap();
        assert_eq!((app.unsaved(), d.path.clone(), d.source == Source::Disk), (1, dir.join("CAMSET01.DAT"), true));
        assert_eq!(d.value(0, s.slot()), Some(v));
        assert!(app.edits_on_camera());
        assert_eq!(app.unsaved_words(1), "1 edit(s) on the camera, not saved to CAMSET01.DAT");
        assert_eq!(App::on_camera_words(1), "Your edit is written to the camera but not saved to a file.");
        assert_eq!(App::on_camera_words(3), "Your 3 edits are written to the camera but not saved to a file.");
        let r = app.camera_report.as_ref().unwrap();
        assert!(r.ok && r.lines.iter().any(|(l, _)| l.starts_with("Your edit is on the camera now, but not saved to CAMSET01.DAT") && l.contains("↩ Put the camera back")), "{:?}", r.lines);
        // the page says the same
        let st = app.web_state(0);
        assert_eq!(st["edits_text"], "1 edit(s) on the camera, not saved to CAMSET01.DAT");
        assert_eq!(st["file"]["on_camera"], "Your edit is written to the camera but not saved to a file.");
        // a further edit, or an undo, returns to the usual words
        let (s2, v2) = other_edit(&app, s.id);
        app.apply(vec![Action::Set(0, s2.slot(), v2)]);
        assert!(!app.edits_on_camera());
        app.undo();
        assert!(!app.edits_on_camera() && app.unsaved() == 1, "back to what the camera holds, but by an undo");
        assert!(app.web_state(0)["file"]["on_camera"].is_null());
        assert_eq!(app.unsaved_words(1), "1 unsaved edit(s)");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// U-14: Write reads the camera before it asks: the window lists what the write changes against the camera now,
    /// and Write to camera keeps that read as the copy from just before (the write does not read again). A read that
    /// fails, or a camera that holds another firmware's layout, ends the write with the report; a read that has grown
    /// old is made again.
    #[test]
    fn write_reads_the_camera_before_it_asks() {
        let dir = scratch("before_write");
        let mut app = opened(&dir, "CAMSET01.DAT", &camera_file());
        // without the camera link program the window does not open: the report says why
        app.send_to_camera();
        assert!(app.pending.is_none() && app.camera_job.is_none());
        assert!(app.camera_report.take().is_some_and(|r| r.title.contains("not found")));
        // a stand-in for the camera link program that cannot run: the jobs started below talk to no camera
        app.prefs.probe_path = Some(dir.join("CAMSET01.DAT").display().to_string());
        app.prefs.link = "usb".into();
        let (s, _) = edit(&mut app);
        app.send_to_camera();
        assert!(app.pending.as_ref().is_some_and(|(w, _)| *w == Review::Send), "the Write window opens");
        assert_eq!(app.camera_job.as_ref().map(|j| j.kind), Some(JobKind::BeforeWrite), "and reads the camera first");
        assert!(app.before_write.is_none());
        // the read comes back: the window lists what changes against it
        let copy = dir.join("before_write_test.DAT");
        std::fs::write(&copy, SAMPLE).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Ok((copy.clone(), "Camera: USB\n".into())), None));
        app.poll_camera_job();
        assert!(app.pending.is_some() && app.camera_report.is_none() && app.last_camera.is_some());
        let lines = app.send_summary();
        assert!(lines[0].0.starts_with("Compared with the camera now, this changes 1 setting:"), "{lines:?}");
        assert!(lines.iter().any(|(l, _)| l.contains(&s.name)), "{lines:?}");
        // Write to camera: the read is the copy from just before, and the write does not read the camera again
        app.pending = None;
        app.write_confirmed();
        let job = app.camera_job.as_ref().unwrap();
        assert_eq!((job.kind, job.backup.clone()), (JobKind::Send, Some(copy.clone())));
        assert!(app.status.starts_with("Writing to the camera"), "{}", app.status);
        assert!(app.sent.is_some() && app.before_write.is_none());
        // a read that fails ends the write, and Try again opens the Write window again
        app.camera_job = None;
        app.send_to_camera();
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Err("could not run camset_probe\n".into()), None));
        app.poll_camera_job();
        assert!(app.pending.is_none(), "a failed read ends the write");
        let r = app.camera_report.take().unwrap();
        assert!(r.title.contains("Nothing written") && r.lines[0].0.contains("could not be read first"), "{}", r.title);
        assert_eq!(r.retry.as_ref().map(|(k, _)| *k), Some(JobKind::BeforeWrite));
        app.camera_job = None;
        app.retry_job(JobKind::BeforeWrite, None);
        assert!(app.pending.is_some() && app.camera_job.as_ref().is_some_and(|j| j.kind == JobKind::BeforeWrite));
        // the camera holds another firmware's layout: nothing is written, and the report says why
        let older = dir.join("before_write_older.DAT");
        std::fs::write(&older, other_firmware().to_bytes()).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Ok((older, "Camera: USB\n".into())), None));
        app.poll_camera_job();
        assert!(app.pending.is_none() && app.before_write.is_none());
        let r = app.camera_report.take().unwrap();
        assert!(r.lines[0].0.contains("firmware 2.00") && r.retry.is_none(), "{:?}", r.lines);
        // a read older than BEFORE_WRITE_FRESH no longer stands for the camera now: Write to camera reads it again
        if let Some(came) = std::time::Instant::now().checked_sub(BEFORE_WRITE_FRESH + std::time::Duration::from_secs(1)) {
            app.camera_job = None;
            app.before_write = Some(BeforeWrite { came, path: copy, cam: test_parse(SAMPLE).unwrap() });
            app.write_confirmed();
            assert_eq!(app.camera_job.as_ref().map(|j| j.kind), Some(JobKind::BeforeWrite), "read again");
            assert!(app.pending.is_some() && app.status.contains("more than five minutes"), "{}", app.status);
        }
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// U-20: a camera read that would replace unsaved edits can open beside them instead, as file B in Compare, both
    /// when the read is done (edits made while it ran) and when it is asked for before it starts.
    #[test]
    fn a_read_can_sit_beside_the_edits() {
        let dir = scratch("read_as_b");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        let a = dir.join("CAMSET01.DAT");
        edit(&mut app);
        let read = dir.join("camera_test.DAT");
        std::fs::write(&read, SAMPLE).unwrap();
        // a read that came back over edits made while it ran asks first; Compare keeps the edits as file A
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Ok((read.clone(), "Camera: USB\n".into())), None));
        app.poll_camera_job();
        let Some(Replace::ReadDone { path, at, .. }) = app.unsaved_ask.take() else { panic!("the question is asked") };
        app.compare_with_read(path, at);
        assert_eq!(app.doc.as_ref().map(|d| d.path.clone()), Some(a.clone()));
        assert_eq!(app.unsaved(), 1, "the edits stay");
        assert_eq!(app.compare.as_ref().map(|(p, _)| p.clone()), Some(read.clone()));
        assert!(app.mode == Mode::Compare && app.last_camera.is_some());
        // asked before the read starts: the read is marked to open as file B, and does when it comes back
        app.compare = None;
        app.prefs.probe_path = Some(a.display().to_string());   // cannot run: no camera is reached
        app.prefs.link = "usb".into();
        app.read_as_b = true;
        app.run_job(JobKind::Read, None, None, None);
        assert!(app.camera_job.as_ref().is_some_and(|j| j.as_b) && !app.read_as_b);
        let mut job = CameraJob::finished(JobKind::Read, Ok((read.clone(), "Camera: USB\n".into())), None);
        job.as_b = true;
        app.camera_job = Some(job);
        app.poll_camera_job();
        assert!(app.unsaved_ask.is_none(), "no question: nothing is replaced");
        assert_eq!(app.doc.as_ref().map(|d| d.path.clone()), Some(a));
        assert_eq!(app.compare.as_ref().map(|(p, _)| p.clone()), Some(read));
        assert_eq!(app.unsaved(), 1);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-30: Swap A/B checks that both files can still be read: with the sample as A, or B gone from the disk, nothing
    /// moves, so A and B never end up the same file.
    #[test]
    fn swap_checks_both_files() {
        let dir = scratch("swap");
        let b = dir.join("B.DAT");
        std::fs::write(&b, SAMPLE).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        app.open_compare(b.clone());
        assert!(app.swap_ab().is_err_and(|w| w.contains("sample")));
        assert!(app.doc.as_ref().is_some_and(|d| d.source == Source::Sample));
        assert_eq!(app.compare.as_ref().map(|(p, _)| p.clone()), Some(b.clone()));
        let mut app = opened(&dir, "A.DAT", SAMPLE);
        let a = dir.join("A.DAT");
        app.open_compare(b.clone());
        std::fs::remove_file(&b).unwrap();
        assert!(app.swap_ab().is_err_and(|w| w.starts_with("File B cannot be read again")));
        assert_eq!((app.doc.as_ref().map(|d| d.path.clone()), app.compare.as_ref().map(|(p, _)| p.clone())), (Some(a.clone()), Some(b.clone())));
        std::fs::write(&b, SAMPLE).unwrap();
        edit(&mut app);
        assert!(app.swap_ab().is_err_and(|w| w.contains("edits")), "edits first");
        app.undo();
        assert_eq!(app.swap_ab(), Ok(()));
        assert_eq!((app.doc.as_ref().map(|d| d.path.clone()), app.compare.as_ref().map(|(p, _)| p.clone())), (Some(b), Some(a)));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-12: one camera job at a time; a second is refused with a word, not started next to the first.
    #[test]
    fn one_camera_job_at_a_time() {
        let dir = scratch("one_job");
        let mut app = opened(&dir, "CAMSET01.DAT", &camera_file());
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Err(String::new()), None));
        let started = app.camera_job.as_ref().unwrap().started;
        for kind in [JobKind::Read, JobKind::Send, JobKind::Discover] {
            app.start_job(kind, None);
            assert!(app.status.contains("busy"), "{}", app.status);
            assert_eq!(app.camera_job.as_ref().map(|j| j.started), Some(started), "the running job is kept");
        }
        assert!(app.send_blocked().is_some_and(|w| w.contains("busy")));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-01: the window's and the page's Write refuse what the Write button would: the sample, a file from a firmware
    /// not checked (until "Edit anyway"), another model. The sample is known by its header however it comes: opened
    /// from disk, edited and saved under another name, then opened again (the editor never changes a header); a camera's
    /// own file of the same model is written.
    #[test]
    fn only_an_editable_file_is_written() {
        let dir = scratch("send_rule");
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert!(app.send_blocked().is_some_and(|w| w.contains("sample")));
        assert!(app.do_send().is_err() && app.sent.is_none());
        // the shipped sample opened from disk, under a camera's file name
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        assert!(app.doc.as_ref().is_some_and(|d| d.source == Source::Disk) && app.editable(), "a file on disk, which can be edited");
        assert_eq!(app.send_blocked().as_deref(), Some(SAMPLE_NOT_WRITTEN));
        assert!(app.do_send().is_err() && app.sent.is_none());
        // edited, saved and opened again: still the sample
        edit(&mut app);
        let saved = dir.join("CAMSET02.DAT");
        app.save_to(saved.clone());
        assert!(app.status.starts_with("Saved as"), "{}", app.status);
        let mut app = App::new(vec![], Prefs::default());
        app.open(saved);
        assert_eq!(app.send_blocked().as_deref(), Some(SAMPLE_NOT_WRITTEN), "a file made from the sample");
        assert!(app.do_send().is_err() && app.sent.is_none());
        // the refusal says the cause, then what to do
        assert!(SAMPLE_NOT_WRITTEN.contains("no camera wrote it as it is") && SAMPLE_NOT_WRITTEN.contains("Read your camera, or open a settings file your camera saved"));
        assert!(SAMPLE_NOT_FOR_A_CAMERA.contains("no camera wrote it as it is"), "the two say alike what the sample is");
        let mut app = opened(&dir, "OLD.DAT", &other_firmware().to_bytes());
        assert!(!app.editable());
        assert!(app.send_blocked().is_some_and(|w| w.contains("view only")));
        assert!(app.do_send().is_err() && app.sent.is_none());
        app.doc.as_mut().unwrap().unchecked_ok = true;
        assert_eq!(app.send_blocked(), None, "Edit anyway turns writing on as it turns editing on");
        let mut app = opened(&dir, "OTHER.DAT", &other_model().to_bytes());
        app.doc.as_mut().unwrap().unchecked_ok = true;
        assert!(app.send_blocked().is_some_and(|w| w.contains("ILCE-0TEST")), "another model, whatever else is on");
        assert!(app.do_send().is_err() && app.sent.is_none());
        let app = opened(&dir, "CAMSET03.DAT", &camera_file());
        assert_eq!(app.send_blocked(), None);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Save As and the page's revert of one edit from the history keep the rule every edit keeps, themselves: a file
    /// view only (a firmware not checked) is neither saved nor changed, whoever asks.
    #[test]
    fn a_view_only_file_is_not_saved_or_changed_from_the_history() {
        let dir = scratch("view_only_save");
        let mut app = opened(&dir, "OLD.DAT", &other_firmware().to_bytes());
        // an edit made while "Edit anyway" was on, which is off again
        app.doc.as_mut().unwrap().unchecked_ok = true;
        let (s, v) = changeable(&app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        app.doc.as_mut().unwrap().unchecked_ok = false;
        assert!(!app.editable() && app.undo.len() == 1);
        let to = dir.join("CAMSET05.DAT");
        app.save_to(to.clone());
        assert!(!to.exists() && app.status.starts_with("Not saved: this file is view only"), "{}", app.status);
        let r = crate::web::tests::answer(&mut app, "revert_history", serde_json::json!({ "step": 0, "section": 0, "id": s.id }));
        assert_eq!(r.status, 409);
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), Some(v), "nothing changed");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The windows judge against what the camera wrote, which Save As does not move: an edit no proof checked stays
    /// listed after the file is saved; edits recovered without the file as opened are never given the all-clear; and a
    /// write judges every record that differs from the camera's own copy read just before it, the list made again when
    /// that read comes back, so a file edited and saved in another session is judged too.
    #[test]
    fn the_windows_judge_against_what_the_camera_wrote() {
        let dir = scratch("baseline");
        let mut app = opened(&dir, "CAMSET01.DAT", &camera_file());
        app.prefs.expert = true;
        let (u, w) = app.schema.settings.iter().filter(|s| s.area == "global" && s.scalar && s.text.is_none() && s.copies.is_empty() && s.copy_of.is_none() && s.proved.is_none() && s.values.len() >= 2 && app.shape_ok_in(s, 0))
            .find_map(|s| { let cur = app.col_value(Col::a(0), s)?; s.values.iter().map(|(x, _)| *x).find(|x| *x != cur && s.acceptance(*x).is_none()).map(|x| (s.clone(), x)) })
            .expect("a setting with no proof");
        app.apply(vec![Action::Set(0, u.slot(), w)]);
        let listed = |app: &App| app.acceptance_issues().iter().any(|i| i.slot == u.slot() && i.kind == IssueKind::NotChecked);
        assert!(listed(&app));
        let saved = dir.join("CAMSET02.DAT");
        app.save_to(saved.clone());
        assert!(app.status.starts_with("Saved as") && app.unsaved() == 0, "{}", app.status);
        assert!(listed(&app), "saved, and still judged against the file as opened");
        // nothing to revert to, as the saved file holds it: the window, the detail panel and the page offer to put back
        // what the camera wrote instead
        let issue = app.acceptance_issues().into_iter().find(|i| i.slot == u.slot()).unwrap();
        let (words, fix) = app.issue_fix(&issue).expect("a way back");
        assert_eq!(words, REVERT_TO_CAMERA);
        let linked = app.web_linked(0, &u.key).unwrap();
        assert_eq!(app.put_back_choice(&linked, 0).map(|(w, _)| w).as_deref(), Some(REVERT_TO_CAMERA), "the detail panel's button");
        assert_eq!(app.web_row(0, &linked)["put_back"], REVERT_TO_CAMERA, "the page's");
        let was = app.doc.as_ref().unwrap().baseline_value(0, u.slot());
        app.apply(fix);
        assert_eq!(app.doc.as_ref().unwrap().value(0, u.slot()), was, "back to what the camera wrote");
        assert!(!listed(&app));
        app.undo();
        assert!(listed(&app));
        // the same from the page (outside Expert mode too: putting back what the camera wrote is always allowed)
        app.prefs.expert = false;
        assert_eq!(crate::web::tests::answer(&mut app, "restore", serde_json::json!({ "target": 0, "key": u.key })).status, 200);
        assert_eq!(app.doc.as_ref().unwrap().value(0, u.slot()), was);
        app.undo();
        app.prefs.expert = true;
        // the saved file opened again in another session: its own baseline, so a save judges nothing ...
        let mut again = App::new(vec![], Prefs::default());
        again.open(saved.clone());
        assert!(again.acceptance_issues().is_empty() && again.write_issues().is_empty());
        // ... but a write judges it against what the camera holds, read just before it, and lists it again
        again.prefs.probe_path = Some(saved.display().to_string());   // a stand-in that cannot run: no camera is reached
        again.prefs.link = "usb".into();
        again.send_to_camera();
        assert!(again.pending.as_ref().is_some_and(|(_, i)| i.is_empty()), "before the read, nothing to judge it against");
        let copy = dir.join("before_write_camera.DAT");
        std::fs::write(&copy, camera_file()).unwrap();
        again.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Ok((copy, "Camera: USB\n".into())), None));
        again.poll_camera_job();
        let (_, issues) = again.pending.clone().expect("the Write window stays open");
        // listed as what only the camera's copy shows: in the file as opened, not on the camera now; no edit of this
        // session, so no flagged value and nothing to revert, but no all-clear either
        let one = issues.iter().find(|i| i.slot == u.slot()).expect("made again once the camera was read");
        assert!(one.kind == IssueKind::CameraOnly && again.issue_fix(one).is_none(), "{:?}", one.kind);
        assert!(issues.iter().all(|i| i.kind == IssueKind::CameraOnly), "nothing else: no edit of this session");
        let drawn = window_texts(&mut again);
        assert!(drawn.iter().any(|t| *t == camera_only_words(issues.len())) && drawn.iter().any(|t| t == "⬆ Write anyway"), "{drawn:?}");
        assert!(!drawn.iter().any(|t| t == ALL_CLEAR || t.contains("flagged") || t == IssueKind::Raw.heading().0 || t == IssueKind::NotChecked.heading().0), "{drawn:?}");
        // the records the camera changes on every load are no difference
        let vol = again.schema.camera.volatile_records.first().copied().expect("the a1 II's every-load record");
        let mut cam = again.before_write.as_ref().unwrap().cam.clone();
        for b in cam.sections[0].get_mut(vol).unwrap().value.iter_mut() { *b = b.wrapping_add(1); }
        again.before_write.as_mut().unwrap().cam = cam;
        assert!(again.write_issues().iter().all(|i| i.slot.0 != vol));
        // nor is a value the camera keeps for itself (`unproved_reason` "state"), which changes as the camera is used:
        // never said to be "not checked on the camera yet" for a file nobody edited
        assert!(again.write_issues().iter().any(|i| i.slot == u.slot()));
        for s in again.schema.settings.iter_mut().filter(|s| s.key == u.key) {
            s.unproved_reason = Some(camset_editor::schema::UnprovedReason { kind: "state".into(), why: String::new() });
        }
        again.schema_gen += 1;
        assert!(again.write_issues().iter().all(|i| i.slot != u.slot()), "{:?}", again.write_issues().iter().map(|i| (&i.name, &i.reason)).collect::<Vec<_>>());
        // edits recovered without the file as opened: never the all-clear
        let mut app = opened(&dir, "CAMSET03.DAT", &camera_file());
        assert!(app.acceptance_issues().is_empty());
        app.doc.as_mut().unwrap().recovered = 2;
        let issues = app.acceptance_issues();
        assert!(issues.len() == 1 && issues[0].kind == IssueKind::Recovered && app.issue_fix(&issues[0]).is_none(), "{:?}", issues.iter().map(|i| &i.name).collect::<Vec<_>>());
        app.pending = Some((Review::Save, issues));
        let drawn = window_texts(&mut app);
        assert!(!drawn.iter().any(|t| t == ALL_CLEAR) && drawn.iter().any(|t| t == IssueKind::Recovered.heading().0), "{drawn:?}");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The sample, or a file made from it, may be saved (it is for trying the editor), but the window and the page say
    /// plainly then that it must never be loaded into a camera: Save As opens the Before saving window to say it, the
    /// status says it once saved, and the page's download says it.
    #[test]
    fn the_sample_says_so_when_it_leaves() {
        let dir = scratch("sample_leaves");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        assert!(app.is_sample_doc());
        let ctx = egui::Context::default();
        let _ = ctx.run(egui::RawInput::default(), |ctx| app.save_as(ctx));
        assert!(matches!(app.pending, Some((Review::Save, _))), "the window opens, with nothing listed, to say it");
        let drawn = window_texts(&mut app);
        assert!(drawn.iter().any(|t| t == SAMPLE_NOT_FOR_A_CAMERA), "{drawn:?}");
        app.pending = None;
        app.save_to(dir.join("CAMSET02.DAT"));
        assert!(app.status.starts_with("Saved as") && app.status.ends_with(SAMPLE_NOT_FOR_A_CAMERA), "{}", app.status);
        assert_eq!(app.web_state(0)["file"]["sample_words"], SAMPLE_NOT_FOR_A_CAMERA);
        assert_eq!(crate::web::tests::answer(&mut app, "file", serde_json::json!({})).status, 200);
        assert!(app.status.ends_with(SAMPLE_NOT_FOR_A_CAMERA), "{}", app.status);
        // a camera's own file says nothing of the kind
        let app = opened(&dir, "CAMSET03.DAT", &camera_file());
        assert!(!app.is_sample_doc() && app.web_state(0)["file"]["sample_words"].is_null());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The texts the Write or Before saving window draws for the issues `pending` holds (on its second frame: a new
    /// window only measures itself on its first).
    fn window_texts(app: &mut App) -> Vec<String> {
        let ctx = egui::Context::default();
        let pending = app.pending.clone();
        let _ = ctx.run(egui::RawInput::default(), |ctx| app.pending_window(ctx));
        app.pending = pending;
        let out = ctx.run(egui::RawInput::default(), |ctx| app.pending_window(ctx));
        crate::test_support::texts(&out.shapes)
    }

    /// The Write and Before saving windows' verdict is true: every record the session changed was checked on the camera
    /// and passed, or it is listed under what it is (a value no proof checked, a text, a raw edit); the all-clear shows
    /// only when nothing is listed. With values listed the button says it goes ahead with them, and the words no longer
    /// invite keeping them; a mirror's copy kept in step is no raw edit.
    #[test]
    fn the_write_window_lists_every_change_not_checked() {
        let dir = scratch("verdict");
        let mut app = opened(&dir, "CAMSET01.DAT", &camera_file());
        let plain = |app: &App, s: &Setting| s.area == "global" && s.scalar && s.text.is_none() && s.copies.is_empty() && s.copy_of.is_none()
            && s.video_system_values.is_none() && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none();
        // a value a proof on the camera established: checked, and passed
        let (s, v) = app.schema.settings.iter().filter(|s| plain(&app, s) && s.proved.is_some())
            .find_map(|s| { let cur = app.col_value(Col::a(0), s)?; s.values.iter().map(|(x, _)| *x).find(|x| *x != cur && s.checked_on_camera(*x, 0) && s.acceptance(*x).is_none()).map(|x| (s.clone(), x)) })
            .expect("a proved value");
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert!(app.acceptance_issues().is_empty(), "{:?}", app.acceptance_issues().iter().map(|i| &i.name).collect::<Vec<_>>());
        app.pending = Some((Review::Save, app.acceptance_issues()));
        let drawn = window_texts(&mut app);
        assert!(drawn.iter().any(|t| t == ALL_CLEAR) && drawn.iter().any(|t| t == "Save As…"), "{drawn:?}");
        // a setting no proof reached: view only outside Expert mode, changed in it, and listed as not checked
        app.prefs.expert = true;
        let (u, w) = app.schema.settings.iter().filter(|s| plain(&app, s) && s.proved.is_none() && s.values.len() >= 2)
            .find_map(|s| { let cur = app.col_value(Col::a(0), s)?; s.values.iter().map(|(x, _)| *x).find(|x| *x != cur && s.acceptance(*x).is_none()).map(|x| (s.clone(), x)) })
            .expect("a setting with no proof");
        assert!(u.established(w), "every value of it offered");
        app.apply(vec![Action::Set(0, u.slot(), w)]);
        // a text typed here
        let t = app.schema.settings.iter().find(|s| s.area == "global" && s.text.is_some() && app.shape_ok_in(s, 0)).cloned().expect("a text setting");
        let rule = t.text.clone().unwrap();
        let held = app.doc.as_ref().unwrap().edited.sections[0].get(t.id).and_then(|r| r.text()).unwrap_or_default();
        let typed: String = rule.charset.chars().filter(|c| !c.is_lowercase()).cycle().skip(1).take(rule.min_len.max(1)).collect();
        assert!(rule.check(&typed).is_ok() && typed != held);
        app.apply(vec![Action::SetText(0, t.id, typed)]);
        // a raw edit in Expert mode, of a record no setting covers
        app.prefs.expert = true;
        app.allow_raw_edits = true;
        let raw = app.doc.as_ref().unwrap().edited.sections[0].records.iter()
            .find(|r| app.schema.find(false, r.id).is_none() && r.elem_size == 1 && r.as_int().is_some()).map(|r| (r.id, r.as_int().unwrap())).expect("an unmapped one-byte record");
        app.apply(vec![Action::Set(0, (raw.0, None), raw.1 ^ 1)]);
        let issues = app.acceptance_issues();
        let kind = |slot: Slot| issues.iter().find(|i| i.slot == slot).map(|i| i.kind);
        assert_eq!((kind(u.slot()), kind(t.slot()), kind((raw.0, None)), kind(s.slot())), (Some(IssueKind::NotChecked), Some(IssueKind::Text), Some(IssueKind::Raw), None));
        assert!(issues.windows(2).all(|w| w[0].kind <= w[1].kind), "listed under what each is");
        // the windows say so: under headings, no all-clear, and a button that says it goes ahead with them
        app.pending = Some((Review::Save, issues.clone()));
        let drawn = window_texts(&mut app);
        for k in [IssueKind::NotChecked, IssueKind::Text, IssueKind::Raw] {
            assert!(drawn.iter().any(|t| t == k.heading().0), "{k:?}: {drawn:?}");
        }
        assert!(!drawn.iter().any(|t| t == ALL_CLEAR) && drawn.iter().any(|t| *t == format!("Save anyway, with {} flagged", issues.len())), "{drawn:?}");
        assert!(drawn.iter().any(|t| t == ISSUES_TODO) && !drawn.iter().any(|t| t.contains("experiment")));
        app.pending = Some((Review::Send, issues.clone()));
        assert!(window_texts(&mut app).iter().any(|t| *t == format!("⬆ Write anyway, with {} flagged", issues.len())));
        // Revert all flagged: nothing left to list
        app.apply(issues.iter().filter_map(|i| app.issue_fix(i).map(|(_, a)| a)).flatten().collect());
        assert!(app.acceptance_issues().is_empty());
        // a memory's exposure block, which a mirror keeps in the live settings too: a field of the live copy made one the
        // editor changes here (the shipped definition changes none), its memory's block, which the editor does not
        // change itself, is no raw edit
        let m = app.schema.camera.mirrors.first().cloned().expect("the a1 II's mirror");
        let key = app.schema.settings.iter().find(|x| x.area == "global" && x.id == m.live_record && x.values.len() >= 2 && app.shape_ok_in(x, 0)).map(|x| x.key.clone()).expect("a field of the exposure block's live copy");
        for x in app.schema.settings.iter_mut().filter(|x| x.key == key) {
            x.scalar = true;
        }
        app.schema_gen += 1;
        let f = app.schema.settings.iter().find(|x| x.key == key).cloned().unwrap();
        let cur = app.col_value(Col::a(0), &f).unwrap();
        let other = f.values.iter().map(|(x, _)| *x).find(|x| *x != cur).unwrap();
        app.apply(vec![Action::Set(0, f.slot(), other)]);
        assert!(app.doc.as_ref().unwrap().changes().iter().any(|(si, id)| *si != 0 && *id == m.set_record), "the mirror wrote the memory's block");
        assert!(app.acceptance_issues().iter().all(|i| i.kind != IssueKind::Raw), "{:?}", app.acceptance_issues().iter().map(|i| &i.name).collect::<Vec<_>>());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-02, the review's test 2: under "Edit anyway", recalling a memory, copying rows from file B and merging leave
    /// every record the file holds in another shape byte for byte as it was, and say how many settings they left.
    #[test]
    fn copies_leave_other_shapes_alone() {
        let dir = scratch("shapes");
        let mut older = other_firmware();
        // Memory 1's Creative Look differs from the live one, so a recall would have copied it
        for b in older.sections[1].get_mut(0x0cde).unwrap().value.iter_mut() { *b = b.wrapping_add(1); }
        let mut app = opened(&dir, "OLD.DAT", &older.to_bytes());
        app.doc.as_mut().unwrap().unchecked_ok = true;
        let look = || -> Vec<u8> { test_parse(SAMPLE).unwrap().sections[0].get(0x0cde).unwrap().value.clone() };
        let a_look = |app: &App| app.doc.as_ref().unwrap().edited.sections[0].get(0x0cde).unwrap().value.clone();
        let before = a_look(&app);
        assert_ne!(before.len(), look().len(), "the live Creative Look has another shape here");
        let m = app.dial_sets()[0];
        let rows = app.memory_rows();
        let acts: Vec<Action> = rows.iter().flat_map(|r| app.copy_row(&r.2, Col::a(m), Col::a(0))).collect();
        assert!(app.copy_skipped.get().shape > 0, "the Creative Look rows are counted");
        assert!(!acts.is_empty(), "the rest is copied");
        app.status = "Memory 1 recalled into the live settings".into();
        app.apply(acts);
        assert_eq!(a_look(&app), before, "Memory 1 ➡ Live left the Creative Look alone");
        assert!(app.status.contains("left alone"), "{}", app.status);
        assert_eq!(app.copy_skipped.get(), Left::default(), "said once");
        // file B from a checked firmware: its rows go into A's live settings, the Creative Look stays as it was
        let b = dir.join("NEW.DAT");
        std::fs::write(&b, SAMPLE).unwrap();
        app.open_compare(b.clone());
        let acts: Vec<Action> = app.matrix_rows_for("", None).iter().flat_map(|r| app.copy_row(&r.2, Col::b(0), Col::a(0))).collect();
        app.apply(acts);
        assert_eq!(a_look(&app), before, "copying file B's rows left the Creative Look alone");
        // three-way: Merge B into A takes B's changes the same way
        app.open_base(dir.join("OLD.DAT"));
        let tc = (Col::base(0), Col::a(0), Col::b(0));
        let acts: Vec<Action> = app.matrix_rows_for("", None).iter().filter(|r| app.three_way(tc, &r.2[0]) == Three::BOnly).flat_map(|r| app.copy_row(&r.2, tc.2, tc.1)).collect();
        app.apply(acts);
        assert_eq!(a_look(&app), before, "Merge B into A left the Creative Look alone");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-08: recalling or registering a memory copies every setting the memories keep, whatever the search and the
    /// Compare tab filter show.
    #[test]
    fn recall_copies_the_whole_memory() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let all = app.memory_rows();
        let tab = all[0].0.clone();
        (app.search, app.compare_tab) = ("a".into(), Some(tab));
        assert!(app.matrix_rows().len() < all.len(), "the filters narrow what is shown");
        assert_eq!(app.memory_rows().len(), all.len(), "but not what a recall copies");
        let m = app.dial_sets()[0];
        let acts: Vec<Action> = app.memory_rows().iter().flat_map(|r| app.copy_row(&r.2, Col::a(m), Col::a(0))).collect();
        app.apply(acts);
        for (_, _, linked) in &all {
            // (a setting view only outside Expert mode is not copied: a copy follows its setting, and no menu writes the others)
            for l in linked.iter().filter(|l| app.shape_ok_in(l, 0) && app.shape_ok_in(l, m) && app.locked_why(l, 0).is_none()) {
                assert_eq!(app.col_value(Col::a(0), l), app.col_value(Col::a(m), l), "{} not recalled", l.name);
            }
        }
    }

    /// E-06 / U-01: a file, the sample or a camera read never replaces unsaved edits without the question; Discard
    /// goes ahead, Cancel keeps them; a read agreed to opens only over the edits that were agreed to.
    #[test]
    fn unsaved_edits_are_asked_about() {
        let dir = scratch("unsaved");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        let other = dir.join("CAMSET02.DAT");
        std::fs::write(&other, SAMPLE).unwrap();
        edit(&mut app);
        app.open(other.clone());
        assert!(matches!(app.unsaved_ask, Some(Replace::Open(_))), "asked first");
        assert_eq!(app.doc.as_ref().unwrap().path, dir.join("CAMSET01.DAT"));
        let then = app.unsaved_ask.take().unwrap();
        app.keep(then);
        assert_eq!(app.unsaved(), 1, "Cancel keeps the edits");
        app.open_sample();
        assert!(matches!(app.unsaved_ask, Some(Replace::Sample)));
        app.unsaved_ask = None;
        app.start_job(JobKind::Read, None);
        assert!(matches!(app.unsaved_ask, Some(Replace::Read)) && app.camera_job.is_none(), "a read asks before it starts");
        app.unsaved_ask = None;
        app.open(other.clone());
        let then = app.unsaved_ask.take().unwrap();
        app.go(then);
        assert_eq!(app.doc.as_ref().unwrap().path, other, "Discard edits opens the file");
        assert_eq!(app.unsaved(), 0);
        // a read done while there are edits nobody agreed to replace: asked about, and Cancel keeps them
        edit(&mut app);
        let read = dir.join("camera_read.DAT");
        std::fs::write(&read, SAMPLE).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Ok((read.clone(), "Camera: USB\n".into())), None));
        app.poll_camera_job();
        assert!(matches!(app.unsaved_ask, Some(Replace::ReadDone { .. })));
        assert_eq!(app.doc.as_ref().unwrap().path, other);
        let then = app.unsaved_ask.take().unwrap();
        app.keep(then);
        assert_eq!(app.unsaved(), 1);
        assert!(app.last_camera.is_some(), "what the camera holds is known all the same");
        // a read agreed to over these very edits opens without another question
        let mut job = CameraJob::finished(JobKind::Read, Ok((read.clone(), "Camera: USB\n".into())), None);
        job.agreed = app.edits_hash();
        app.camera_job = Some(job);
        app.poll_camera_job();
        assert!(app.unsaved_ask.is_none());
        assert_eq!(app.doc.as_ref().unwrap().path, read);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// U-04 / E-18: after Save As the window works on the saved file (no unsaved edits, Undo kept), says "Saved as",
    /// may save to it again, and still never overwrites the file it opened.
    #[test]
    fn save_as_works_on_the_saved_file() {
        let dir = scratch("save_as");
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        edit(&mut app);
        let to = dir.join("CAMSET02.DAT");
        app.save_to(to.clone());
        let d = app.doc.as_ref().unwrap();
        assert_eq!(d.path, to);
        assert_eq!(app.unsaved(), 0, "nothing unsaved after a save");
        assert_eq!(app.undo.len(), 1, "Undo kept");
        assert!(app.status.starts_with("Saved as CAMSET02.DAT"), "{}", app.status);
        assert_eq!(std::fs::read(&to).unwrap(), d.edited.to_bytes());
        assert_eq!(app.prefs.last_a.as_deref(), Some(to.display().to_string().as_str()), "reopened at the next start");
        assert_eq!(std::fs::read(dir.join("CAMSET01.DAT")).unwrap(), SAMPLE, "the opened file untouched");
        // the saved file may be saved again, the opened one never
        edit(&mut app);
        app.save_to(to.clone());
        assert!(app.status.starts_with("Saved as"), "{}", app.status);
        let mut app = opened(&dir, "CAMSET01.DAT", SAMPLE);
        edit(&mut app);
        app.save_to(dir.join("CAMSET01.DAT"));
        assert!(app.status.starts_with("Refusing"), "{}", app.status);
        assert_eq!(std::fs::read(dir.join("CAMSET01.DAT")).unwrap(), SAMPLE);
        // a save asked for by the question before replacing: what was asked follows the save
        let other = dir.join("CAMSET03.DAT");
        std::fs::write(&other, SAMPLE).unwrap();
        app.after_save = Some(Replace::Open(other.clone()));
        app.save_to(dir.join("CAMSET04.DAT"));
        assert_eq!(app.doc.as_ref().unwrap().path, other);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-10: a value dragged (one Set a frame on the same slot) is one undo step, not one per frame.
    #[test]
    fn a_drag_is_one_undo_step() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (s, v) = changeable(&app);
        let was = app.col_value(Col::a(0), &s);
        let others: Vec<i64> = s.values.iter().map(|(x, _)| *x).filter(|x| Some(*x) != was).collect();
        for x in others.iter().chain([&v]) {
            app.apply(vec![Action::Set(0, s.slot(), *x)]);
        }
        assert_eq!(app.undo.len(), 1, "one step for the whole drag");
        app.undo();
        assert_eq!(app.col_value(Col::a(0), &s), was, "Undo goes back to before the drag");
        app.redo();
        // another setting is a step of its own
        let t = app.schema.settings.iter().filter(|t| t.area == "global" && t.scalar && t.text.is_none() && t.slot() != s.slot() && t.values.len() >= 2 && app.shape_ok_in(t, 0) && app.locked_why(t, 0).is_none())
            .find_map(|t| { let cur = app.col_value(Col::a(0), t)?; t.values.iter().map(|(x, _)| *x).find(|x| *x != cur).map(|x| (t.clone(), x)) }).unwrap();
        app.apply(vec![Action::Set(0, t.0.slot(), t.1)]);
        assert_eq!(app.undo.len(), 2);
    }

    /// E-14: damaged preferences are kept aside, not written over; preferences are written readable by this user only.
    #[test]
    fn damaged_preferences_are_kept() {
        let dir = scratch("prefs");
        let p = dir.join("prefs.json");
        std::fs::write(&p, "{ not json").unwrap();
        let prefs = Prefs::read_from(&p);
        assert!(prefs.recent.is_empty());
        assert_eq!(std::fs::read_to_string(dir.join("prefs.json.bad")).unwrap(), "{ not json");
        assert!(!p.exists());
        write_private(&p, serde_json::to_string(&prefs).unwrap()).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&p).unwrap().permissions().mode() & 0o777, 0o600);
        }
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-17: a file that is not a settings file is refused in plain words, with the technical cause in Expert mode only.
    #[test]
    fn open_errors_in_plain_words() {
        let dir = scratch("plain");
        let bad = dir.join("BROKEN.DAT");
        let mut cut = SAMPLE.to_vec();
        cut[0x100] ^= 0xff;
        std::fs::write(&bad, &cut).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        assert!(app.open_now(bad.clone()).is_err());
        assert!(app.status.contains("damaged") && !app.status.contains("0x"), "{}", app.status);
        app.prefs.expert = true;
        let _ = app.open_now(bad);
        assert!(app.status.contains("checksum"), "{}", app.status);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
