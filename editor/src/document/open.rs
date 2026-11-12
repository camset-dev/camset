//! The open file (file A): opening it, from disk, the sample or the camera, the one question before unsaved edits
//! would be lost (`guard`), Save As, and closing it.

use crate::*;

/// Where the open file came from: disk, or a read from the camera at a given time.
#[derive(Clone, PartialEq)]
pub(crate) enum Source { Disk, Sample, Camera { link: String, read_at: String } }

pub(crate) struct Doc {
    pub(crate) path: PathBuf,
    pub(crate) original: CamSet,
    pub(crate) edited: CamSet,
    /// The file as first opened, or as last read from the camera, in this session: what the camera wrote, which Save As
    /// does not move (it moves `original`). The write and save windows judge the edits against it (`acceptance_issues`),
    /// and a copy the camera keeps of a setting's value follows that setting when the two agreed in it (`apply`).
    pub(crate) baseline: CamSet,
    /// Layout fingerprint of the opened file (see CamSet::layout_signature).
    pub(crate) signature: String,
    /// Disk, or read from the camera (with the link and the time of the read).
    pub(crate) source: Source,
    /// Editing turned on for a file of this model from a firmware the schema was not checked on
    /// (only settings it holds in the mapped shape; see unchecked_window).
    pub(crate) unchecked_ok: bool,
    /// How the file found its definition: its own firmware's, the nearest of its model, or none.
    pub(crate) how: Match,
    /// Expert mode: the definition chosen by hand to read the file with (where it was found), in place of the one
    /// its header picks (`App::override_definition`).
    pub(crate) override_def: Option<Origin>,
    /// Which opening of a file this is (`next_open`): what a field typed into but not applied yet belongs to.
    pub(crate) opened: u64,
    /// Which state of the file this is: a new number (`next_open`) at each opening and each change of `edited` or
    /// `original` (an edit, Undo, Redo, a save), so what is worked out from them (the Expert pages' rows, the count of
    /// values the camera may refuse, the page's revision) is kept until it changes.
    pub(crate) rev: u64,
    /// `path` is a file this editor saved (Save As), not the file it opened: saving to it again is allowed.
    pub(crate) saved: bool,
    /// Edits recovered from a journal that kept no copy of the file as opened (`open_recovered`): how many it held.
    /// `original` is then the recovered file itself, so no record shows them as edits, yet they are saved nowhere: they
    /// count as unsaved (`unsaved`) until the file is saved or the camera's read-back takes its place. 0 otherwise.
    pub(crate) recovered: usize,
}

/// A number for each file opened, never the same twice in a run.
pub(crate) fn next_open() -> u64 {
    static OPENS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(1);
    OPENS.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
}

/// Why a settings file could not be read: the disk, or its contents.
#[derive(Debug)]
pub(crate) enum LoadError {
    Io(std::io::Error),
    Parse(camset::CamSetError),
}

impl std::fmt::Display for LoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LoadError::Io(e) => write!(f, "{e}"),
            LoadError::Parse(e) => write!(f, "{e}"),
        }
    }
}

/// What replaces file A, or closes the window, once unsaved edits are dealt with (`guard`).
pub(crate) enum Replace {
    /// Open a file as file A.
    Open(PathBuf),
    /// Open the built-in sample.
    Sample,
    /// Read the camera; the download then opens as file A.
    Read,
    /// A read is done: open its download as file A (edits were made while it ran).
    ReadDone { path: PathBuf, text: String, name: String, at: String },
    /// Close the open files (File > Close file).
    Close,
    /// Close the window.
    Quit,
    /// Open the edits an earlier session left unsaved (its journal, by name: `recovery`).
    Recover(String),
}

impl Doc {
    pub(crate) fn value(&self, section: usize, slot: Slot) -> Option<i64> {
        self.edited.sections.get(section)?.get(slot.0)?.get(slot.1)
    }
    pub(crate) fn original_value(&self, section: usize, slot: Slot) -> Option<i64> {
        self.original.sections.get(section)?.get(slot.0)?.get(slot.1)
    }
    /// The value in the file as first opened or read in this session (`baseline`): what the camera wrote.
    pub(crate) fn baseline_value(&self, section: usize, slot: Slot) -> Option<i64> {
        self.baseline.sections.get(section)?.get(slot.0)?.get(slot.1)
    }
    /// All (section, id) whose bytes differ from the opened file.
    pub(crate) fn changes(&self) -> Vec<(usize, u16)> {
        let mut out = Vec::new();
        for (si, (a, b)) in self.original.sections.iter().zip(&self.edited.sections).enumerate() {
            for (r, q) in a.records.iter().zip(&b.records) {
                if r.value != q.value {
                    out.push((si, r.id));
                }
            }
        }
        out
    }
    /// Edits not saved: the records that differ from `original`, and the recovered edits no record shows (`recovered`).
    pub(crate) fn unsaved(&self) -> usize {
        self.changes().len() + self.recovered
    }
}

impl App {
    pub(crate) fn remember_session(&mut self) {
        self.prefs.last_a = self.doc.as_ref().filter(|d| d.source != Source::Sample).map(|d| d.path.display().to_string());
        self.prefs.last_b = self.compare.as_ref().map(|(p, _)| p.display().to_string());
        self.prefs.last_base = self.base.as_ref().map(|(p, _)| p.display().to_string());
        self.prefs.compare_mode = self.mode == Mode::Compare;
        self.prefs.target = self.target;
        self.prefs.view = Some(self.view.key().to_string());
        self.prefs.save();
    }

    /// A settings file read from disk; when it cannot be, why in plain words (the technical details in Expert mode).
    pub(crate) fn load(&self, path: &Path) -> Result<CamSet, String> {
        let name = path.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_else(|| path.display().to_string());
        self.read_file(path).map_err(|e| {
            let said = match &e { LoadError::Io(io) => read_problem(io), LoadError::Parse(p) => file_problem(p) };
            let none = if matches!(e, LoadError::Parse(camset::CamSetError::NotCamSet)) { self.no_definitions_note() } else { String::new() };
            let detail = details(self.prefs.expert, format_args!("{}: {e}", path.display()));
            format!("{name}: {said}{none}{detail}")
        })
    }

    /// A settings file read through the definitions' container blocks (`Definitions::open`), with what went wrong
    /// kept apart (`load_words` says it).
    pub(crate) fn read_file(&self, path: &Path) -> Result<CamSet, LoadError> {
        let bytes = std::fs::read(path).map_err(LoadError::Io)?;
        self.defs.open(&bytes, false).map(|o| o.set).map_err(LoadError::Parse)
    }

    /// When no definition is loaded at all, a sentence saying so and where they were looked for; else nothing.
    fn no_definitions_note(&self) -> String {
        if !self.defs.list.is_empty() {
            return String::new();
        }
        // the folders looked in are for Expert mode (Settings > Camera support lists them on hover too)
        let expert = self.prefs.expert;
        let looked: Vec<String> = self.defs.looked_in.iter().chain(std::iter::once(&self.defs.user_dir)).map(|d| d.display().to_string()).collect();
        let details = if expert { format!(" (Looked in {}.)", looked.join(", ")) } else { String::new() };
        format!(" No camera definition was found to read it with: reinstall the editor, or add a definition in ⚙ Settings > Camera support & web page.{details}")
    }

    /// Why a file could not be read, in plain words; the technical details follow in Expert mode only.
    pub(crate) fn load_words(&self, path: &Path, e: &LoadError) -> String {
        let said = match e {
            LoadError::Io(io) => io_words(io, false).to_string(),
            LoadError::Parse(camset::CamSetError::NotCamSet) => format!("no camera definition describes this file.{}", self.no_definitions_note()),
            LoadError::Parse(_) => "the file is damaged, or it was not saved by a camera.".to_string(),
        };
        if self.prefs.expert { format!("{said} (Details: {}: {e})", path.display()) } else { said }
    }

    /// Open a file as file A, after asking when that would throw away unsaved edits (`guard`).
    pub(crate) fn open(&mut self, path: PathBuf) {
        self.guard(Replace::Open(path));
    }

    /// Open a file as file A now, whatever edits are open (the guard asked first). Err: why not, for Expert mode;
    /// the status says it in plain words.
    pub(crate) fn open_now(&mut self, path: PathBuf) -> Result<(), String> {
        let read = std::fs::read(&path).map_err(LoadError::Io).and_then(|b| self.defs.open(&b, false).map(|o| (b, o)).map_err(LoadError::Parse));
        match read {
            Ok((bytes, o)) => {
                Self::keep_original(&path, &bytes);
                let c = o.set;
                let signature = c.layout_signature();
                self.adopt(o.def);
                self.undo.clear();
                self.redo.clear();
                self.prefs.remember(&path);
                self.status = self.opened_words(&path.display().to_string(), &c, &signature, &o.how);
                let note = self.mirror_note(&c);
                self.status += &note;
                self.target = self.target.min(c.sections.len().saturating_sub(1));
                self.fit_cols(c.sections.len());
                self.doc = Some(Doc { path, original: c.clone(), baseline: c.clone(), edited: c, signature, source: Source::Disk, unchecked_ok: false, how: o.how, override_def: None, opened: next_open(), rev: next_open(), saved: false, recovered: 0 });
                self.last_edit = None;
                self.remember_session();
                Ok(())
            }
            Err(e) => {
                let name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
                let saved = self.schema.camera.text.save_load_path.as_deref().filter(|p| !p.is_empty()).map(|p| format!(" ({p})")).unwrap_or_default();
                self.status = format!("Could not open {name}: {} Choose a settings file the camera saved{saved}, or read it from the camera.", self.load_words(&path, &e));
                Err(format!("{}: {e}", path.display()))
            }
        }
    }

    /// Open the sample a definition names, after asking when that would throw away unsaved edits.
    pub(crate) fn open_sample(&mut self) {
        self.guard(Replace::Sample);
    }

    /// Open the sample a definition names (`camera.sample`, a file beside it; the shipped ones first): a place to
    /// look around without a camera or a file. A shipped one is read with the shipped definitions only, so it
    /// behaves the same whatever the user's folder holds. Without one, the welcome page offers none.
    pub(crate) fn open_sample_now(&mut self) {
        let Some((i, path)) = self.defs.samples().into_iter().next() else {
            self.status = format!("There is no sample to explore: no camera definition found names one.{}", self.no_definitions_note());
            return;
        };
        let shipped = self.defs.list[i].origin.is_shipped();
        let read = std::fs::read(&path).map_err(LoadError::Io).and_then(|b| self.defs.open(&b, shipped).map_err(LoadError::Parse));
        match read {
            Ok(o) => {
                let c = o.set;
                let signature = c.layout_signature();
                self.adopt(o.def);
                self.undo.clear();
                self.redo.clear();
                self.status = "Sample camera opened: explore and edit freely; it is not your camera, so it cannot be written to one.".into();
                self.target = self.target.min(c.sections.len().saturating_sub(1));
                self.fit_cols(c.sections.len());
                self.doc = Some(Doc { path: PathBuf::from("Sample camera (built in)"), original: c.clone(), baseline: c.clone(), edited: c, signature, unchecked_ok: false, how: o.how, override_def: None, source: Source::Sample, opened: next_open(), rev: next_open(), saved: false, recovered: 0 });
                self.last_edit = None;
                self.remember_session();
            }
            Err(e) => self.status = format!("The sample could not be read: {}", self.load_words(&path, &e)),
        }
    }

    /// Edits not saved: the records of file A that differ from the file as opened (or as last saved), and recovered
    /// edits whose file as opened was not kept (`Doc::recovered`). What every question before they would be lost reads.
    pub(crate) fn unsaved(&self) -> usize {
        self.doc.as_ref().map_or(0, Doc::unsaved)
    }

    /// The unsaved edits as they stand now (a hash of the edited file); None when there are none.
    pub(crate) fn edits_hash(&self) -> Option<u64> {
        let d = self.doc.as_ref()?;
        (d.unsaved() > 0).then(|| fnv1a(&d.edited.to_bytes()))
    }

    /// File A's edits are the ones the camera confirmed holding (`on_camera`): not saved to the file, but not lost
    /// from the camera either. A further edit, an undo, a save or another write ends it.
    pub(crate) fn edits_on_camera(&self) -> bool {
        match (&self.on_camera, &self.doc, &self.sent) {
            (Some((opened, rev, sent)), Some(d), Some((p, _))) => d.opened == *opened && d.rev == *rev && p == sent && !d.changes().is_empty(),
            _ => false,
        }
    }

    /// The edit counter's words for `n` edits: "N unsaved edit(s)", or, while they are the ones on the camera
    /// (`edits_on_camera`), "N edit(s) on the camera, not saved to CAMSET01.DAT".
    pub(crate) fn unsaved_words(&self, n: usize) -> String {
        match self.doc.as_ref().filter(|_| self.edits_on_camera()) {
            Some(d) => format!("{n} edit(s) on the camera, not saved to {}", d.path.file_name().unwrap_or_default().to_string_lossy()),
            None => format!("{n} unsaved edit(s)"),
        }
    }

    /// The question before edits on the camera would be lost (`edits_on_camera`) starts with this, in place of
    /// "You have N edits that are not saved."
    pub(crate) fn on_camera_words(n: usize) -> String {
        if n == 1 { "Your edit is written to the camera but not saved to a file.".into() } else { format!("Your {n} edits are written to the camera but not saved to a file.") }
    }

    /// A write to the camera, or the read-back check after it, is running.
    pub(crate) fn writing(&self) -> bool {
        self.camera_job.as_ref().is_some_and(|j| matches!(j.kind, JobKind::Send | JobKind::Verify))
    }

    /// The one guard before file A is replaced (a file, the sample or a camera read opened over it) or the window
    /// closes: go ahead when nothing would be lost, else ask first (`unsaved_window`).
    pub(crate) fn guard(&mut self, then: Replace) {
        if self.unsaved() == 0 && !(matches!(then, Replace::Quit) && self.writing()) {
            self.go(then);
        } else {
            self.unsaved_ask = Some(then);
        }
    }

    /// Do what the guard held back: the person agreed, or nothing would be lost.
    pub(crate) fn go(&mut self, then: Replace) {
        match then {
            Replace::Open(p) => { let _ = self.open_now(p); }
            Replace::Sample => self.open_sample_now(),
            Replace::Read => {
                // the edits stay until the read is done; it replaces them only if they are still these
                let agreed = self.edits_hash();
                self.run_job(JobKind::Read, None, agreed, None);
            }
            Replace::ReadDone { path, text, name, at } => self.finish_read(path, text, name, at),
            Replace::Close => self.close_file_now(),
            Replace::Quit => self.close_ok = true,
            Replace::Recover(base) => { let _ = self.open_recovered(&base); }
        }
    }

    /// A camera read opened beside the edits: file A keeps them, the read is file B in Compare (and what the camera
    /// holds now, for the Write window).
    pub(crate) fn compare_with_read(&mut self, path: PathBuf, at: String) {
        if let Ok(c) = self.read_file(&path) { self.last_camera = Some((at, c)); }
        self.open_compare(path);
        if self.compare.is_some() {
            self.status = "Your edits stay open as file A; file B is what the camera holds.".into();
        }
    }

    /// The guard's question was answered with Cancel: nothing is replaced.
    pub(crate) fn keep(&mut self, then: Replace) {
        match then {
            Replace::ReadDone { path, at, .. } => {
                // the camera's settings were read all the same: kept under Backups, and what the Write window compares with
                if let Ok(c) = self.read_file(&path) { self.last_camera = Some((at, c)); }
                self.status = "Your edits stay open. The camera's settings just read are kept under 🗂 Backups.".into();
            }
            Replace::Quit => self.status = "The editor stays open.".into(),
            Replace::Close => self.status = "The file stays open with your edits.".into(),
            _ => self.status = "Nothing was opened: your edits stay open.".into(),
        }
    }

    /// The guard's question: "You have N edits that are not saved." Save As… (then carry on), Discard edits, or
    /// Cancel. Before closing while the camera is being written, also that closing skips the check that it took
    /// the file.
    pub(crate) fn unsaved_window(&mut self, ctx: &egui::Context) {
        let Some(then) = &self.unsaved_ask else { return };
        let quit = matches!(then, Replace::Quit);
        let n = self.unsaved();
        let writing = quit && self.writing();
        if n == 0 && !quit {
            // saved or undone meanwhile: nothing would be lost any more
            if let Some(then) = self.unsaved_ask.take() { self.go(then); }
            return;
        }
        let what = match then {
            Replace::Open(p) => format!("Opening {} replaces them.", p.file_name().unwrap_or_default().to_string_lossy()),
            Replace::Sample => "Opening the sample replaces them.".into(),
            Replace::Read => "Reading the camera replaces them with the camera's settings.".into(),
            Replace::ReadDone { .. } => "The camera's settings have been read: opening them replaces your edits.".into(),
            Replace::Close => "Closing the file throws them away.".into(),
            Replace::Quit => "Closing the editor throws them away.".into(),
            Replace::Recover(_) => "Opening the recovered edits replaces them.".into(),
        };
        // edits the camera holds but the file does not are said to be so
        let have = if self.edits_on_camera() { Self::on_camera_words(n) } else { format!("You have {n} {} not saved.", if n == 1 { "edit that is" } else { "edits that are" }) };
        // a camera read can sit beside the edits instead: as file B in Compare
        let read = matches!(then, Replace::Read | Replace::ReadDone { .. }) && n > 0;
        // Esc is Cancel here, and taken, so the shortcuts do not also close a window or clear the search with it
        let (mut save, mut discard, mut cancel) = (false, false, ctx.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape)));
        let mut compare = false;
        egui::Window::new(if quit { "Close the editor?" } else { "Unsaved edits" })
            .collapsible(false).resizable(false).anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0]).show(ctx, |ui| {
                if writing {
                    ui.label(RichText::new("The camera is being written. Closing now skips the check that it took the file.").color(tone::caution(ui.visuals())));
                }
                if n > 0 {
                    ui.label(format!("{have} {what}"));
                } else if !writing {
                    // a close asked about while the camera was written, which is done now: its report is worth a look
                    ui.label("The camera write is done and nothing is left unsaved: see its report, or close the editor.");
                }
                ui.add_space(8.0);
                ui.horizontal(|ui| {
                    if n > 0 && ui.button("Save As…").on_hover_text("Save the edits as a new file first, then carry on").clicked() { save = true; }
                    if read && ui.button("Compare with what the camera holds").on_hover_text("Keep your edits open as file A and open the camera's settings as file B beside them, in Compare").clicked() { compare = true; }
                    let label = match (n > 0, quit, writing) { (true, true, _) => "Discard edits and close", (true, false, _) => "Discard edits", (false, _, true) => "Close anyway", _ => "Close" };
                    if ui.button(label).clicked() { discard = true; }
                    if ui.button("Cancel").clicked() { cancel = true; }
                });
            });
        if compare {
            match self.unsaved_ask.take() {
                Some(Replace::ReadDone { path, at, .. }) => self.compare_with_read(path, at),
                Some(_) => {
                    self.read_as_b = true;
                    self.run_job(JobKind::Read, None, None, None);
                    self.read_as_b = false;
                }
                None => {}
            }
        } else if save {
            if self.dialog_open {
                self.status = "A file dialog is already open".into();
            } else {
                self.after_save = self.unsaved_ask.take();
                self.save_as(ctx);
            }
        } else if discard {
            if let Some(then) = self.unsaved_ask.take() { self.go(then); }
        } else if cancel {
            if let Some(then) = self.unsaved_ask.take() { self.keep(then); }
        }
    }

    /// Whether Save As is offered (the top bar's button, the File menu, Cmd/Ctrl+S): editing is on and something is
    /// unsaved, recovered edits no record shows included (`Doc::unsaved`).
    pub(crate) fn can_save_as(&self) -> bool {
        self.editable() && self.doc.as_ref().is_some_and(|d| d.unsaved() > 0)
    }

    /// Save As, after the acceptance check: issues go to a window first.
    pub(crate) fn save_as(&mut self, ctx: &egui::Context) {
        let issues = self.acceptance_issues();
        // a file read with a definition chosen by hand, and the sample or a file made from it: the window says so first
        if !issues.is_empty() || self.override_line().is_some() || self.is_sample_doc() {
            self.pending = Some((Review::Save, issues));
            return;
        }
        self.save_file_dialog(ctx);
    }

    /// The name offered when saving the edited file.
    /// As the camera's definition says (`save_name`: the opened file's name cut short, upper case, and a suffix);
    /// without it, the opened file's own name.
    pub(crate) fn suggested_name(&self, doc: &Doc) -> String {
        let stem = doc.path.file_stem().map(|s| s.to_string_lossy().to_string()).filter(|s| !s.is_empty()).unwrap_or_else(|| "SETTINGS".into());
        match self.schema.camera.save_name.as_ref().filter(|n| n.stem_chars > 0) {
            Some(n) => format!("{}{}", stem.chars().take(n.stem_chars).collect::<String>().to_uppercase(), n.suffix),
            None => doc.path.file_name().map(|f| f.to_string_lossy().to_string()).filter(|f| f.to_ascii_uppercase().ends_with(".DAT")).unwrap_or_else(|| format!("{stem}.DAT")),
        }
    }

    /// Ask where to save the edited file; `save_to` writes it.
    /// It starts in the opened file's folder and offers the next name the camera lists that is free there, and the
    /// status line says how many settings files the camera lists and how many that folder holds.
    pub(crate) fn save_file_dialog(&mut self, ctx: &egui::Context) {
        let Some(doc) = &self.doc else { return };
        let from = doc.path.clone();
        let kind = DialogKind::SaveAs(from);
        let dir = self.start_dir(&kind);
        let suggested = dir.as_deref().and_then(|d| self.free_card_name(d)).unwrap_or_else(|| self.suggested_name(doc));
        let held = dir.as_deref().map_or(0, |d| settings_files_in(d, &self.defs));
        let folder = self.card_folder();
        let (note, title) = match self.schema.camera.text.max_settings_files_on_card {
            Some(limit) if held >= limit => (
                format!("⚠ The camera lists at most {limit} settings files in {folder}, and the folder offered holds {held} already: a new one there would not show in the camera's list. Remove one from the card first, or save it elsewhere."),
                format!("Save As: that folder holds {held} settings files; the camera lists {limit}"),
            ),
            Some(limit) => (
                format!("Save As: the camera lists up to {limit} settings files in {folder}; the folder offered holds {held}."),
                format!("Save As (the camera lists up to {limit} settings files; this folder holds {held})"),
            ),
            None => ("Save As: choose where to save the edited file.".to_string(), "Save As".to_string()),
        };
        self.status = note;
        self.ask_titled(ctx, kind, Some(suggested), Some(title));
    }

    /// The first name the camera gives its settings files (CAMSET01.DAT, CAMSET02.DAT…) that is free in `dir`.
    pub(crate) fn free_card_name(&self, dir: &Path) -> Option<String> {
        let taken: std::collections::HashSet<String> = std::fs::read_dir(dir).ok()?.flatten()
            .map(|e| e.file_name().to_string_lossy().to_uppercase()).collect();
        (1..=99).map(|n| self.card_file_name(n)).find(|name| !taken.contains(&name.to_uppercase()))
    }

    /// Save the edited file as `p`, the name the Save As dialog gave.
    pub(crate) fn save_to(&mut self, p: PathBuf) {
        // what was to follow a save (the guard's Save As…) follows only this one, and only if it succeeds
        let then = self.after_save.take();
        let Some(doc) = &self.doc else { return };
        // the rule Save As is offered by (`can_save_as`), checked here rather than left to whoever asks for the save
        if !self.editable() {
            self.status = "Not saved: this file is view only, as its firmware has not been checked yet (or the file looks damaged). \"Edit anyway…\" next to the file name turns editing on for a firmware not checked.".into();
            return;
        }
        // the file the edits came from, however the dialog names it, is never written over (a file Save As made is)
        if same_file(&p, &doc.path) && !doc.saved {
            self.status = "Refusing to overwrite the opened file; choose a new name".into();
            return;
        }
        if p.parent().is_some_and(Self::is_own_folder) {
            self.status = "Those folders hold the editor's backups; save to another folder".into();
            return;
        }
        // a file this save replaces is kept first, as every opened file is
        if self.prefs.backup_on_save && doc.path.is_file() {
            if let Ok(existing) = std::fs::read(&doc.path) {
                let _ = keep_copy(&Self::originals_dir(), &doc.path, &existing);
            }
        }
        if self.prefs.backup_on_save && p.is_file() {
            if let Ok(existing) = std::fs::read(&p) {
                let _ = keep_copy(&Self::originals_dir(), &p, &existing);
            }
        } else if let Ok(old) = std::fs::read(&p) {
            if self.defs.is_settings_file(&old) { Self::keep_original(&p, &old); }
        }
        let bytes = doc.edited.to_bytes();
        // Verify what we are about to write parses back cleanly.
        match CamSet::parse(&bytes, doc.edited.format()) {
            Ok(written) => match write_atomic(&p, &bytes) {
                Ok(_) => {
                    // the window works on the saved file now: its edits are saved, and Undo still steps back through them
                    if let Some(d) = &mut self.doc {
                        d.path = p.clone();
                        d.original = written;
                        d.rev = next_open();
                        d.saved = true;
                        d.recovered = 0;
                        if d.source != Source::Sample { d.source = Source::Disk; }   // the sample stays one: never written to a camera
                    }
                    self.prefs.remember(&p);
                    self.remember_session();
                    let folder = p.parent().map(|d| d.display().to_string()).unwrap_or_default();
                    self.status = format!("Saved as {} in {folder}", p.file_name().unwrap_or_default().to_string_lossy());
                    if self.is_sample_doc() { self.status += &format!(". {SAMPLE_NOT_FOR_A_CAMERA}"); }
                    // The camera's Load list shows a limited number of settings files; extra ones are silently hidden.
                    let limit = self.schema.camera.text.max_settings_files_on_card;
                    let n = p.parent().map_or(0, |d| settings_files_in(d, &self.defs));
                    if let Some(limit) = limit.filter(|l| n > *l) {
                        self.status += &format!(" (warning: {n} settings files in that folder; the camera lists only {limit})");
                    }
                    if let Some(then) = then { self.go(then); }
                }
                Err(e) => {
                    let details = details(self.prefs.expert, format_args!("{}: {e}", p.display()));
                    self.status = format!("Not saved: {}{details}", io_words(&e, true));
                }
            },
            Err(e) => {
                let details = details(self.prefs.expert, &e);
                self.status = format!("Not saved: the edited file did not read back as a settings file. Undo the last edit, then save again.{details}");
            }
        }
    }

    /// The folder on the card that holds the settings files ("PRIVATE/SONY/CAMSET" unless the camera definition
    /// names another).
    pub(crate) fn card_folder(&self) -> String {
        self.schema.camera.text.card_folder.clone().filter(|f| !f.is_empty()).unwrap_or_else(|| "PRIVATE/SONY/CAMSET".into())
    }

    /// The camera's name for its settings file number `n` ("CAMSETnn.DAT" unless the camera definition names
    /// another pattern).
    fn card_file_name(&self, n: u32) -> String {
        let pattern = self.schema.camera.text.settings_file_name.clone().filter(|p| p.contains("nn")).unwrap_or_else(|| "CAMSETnn.DAT".into());
        pattern.replacen("nn", &format!("{n:02}"), 1)
    }

    /// Where a settings file is and how the camera saves one, for the welcome page's Open card.
    pub(crate) fn open_hint(&self) -> String {
        let save = self.schema.camera.text.save_load_path.as_deref().filter(|p| !p.is_empty()).map(|p| format!(" ({p})")).unwrap_or_default();
        format!("A settings file the camera saved: on the card it is {}/{}{save}.", self.card_folder(), self.card_file_name(1))
    }

    /// Whether `dir` is one of the editor's own folders of copies (the originals, the camera's files) or inside one,
    /// however the path reaches it (a link to the folder, say): they hold copies, never a file to save into or to
    /// keep a copy of again.
    pub(crate) fn is_own_folder(dir: &Path) -> bool {
        let real = |d: &Path| std::fs::canonicalize(d).unwrap_or_else(|_| d.to_path_buf());
        let here = real(dir);
        [Self::originals_dir(), Self::camera_dir()].iter().any(|own| dir.starts_with(own) || here.starts_with(real(own)))
    }

    /// Where every settings file opened is kept once, as it was, so an edit can always go back to it.
    pub(crate) fn originals_dir() -> PathBuf {
        Prefs::path().parent().map(|p| p.join("originals")).unwrap_or_else(|| PathBuf::from("originals"))
    }

    /// Keep a copy of a settings file as opened, once per content. Files in the editor's own
    /// folders are copies already.
    fn keep_original(path: &Path, bytes: &[u8]) {
        if path.parent().is_some_and(Self::is_own_folder) { return; }
        let _ = keep_copy(&Self::originals_dir(), path, bytes);
    }

    /// Close the open files (File > Close file, Cmd/Ctrl+W). It never throws edits away: with edits not saved yet it
    /// asks first, as opening another file does (`guard`: Save As…, Discard edits or Cancel); while the camera is
    /// being read or written it does not close and says why.
    pub(crate) fn close_file(&mut self) {
        if self.doc.is_none() { return; }
        if self.camera_job.is_some() {
            self.status = "Not closed while the camera is being read or written.".into();
            return;
        }
        self.guard(Replace::Close);
    }

    /// Close the open files now (the guard asked first).
    pub(crate) fn close_file_now(&mut self) {
        let Some(d) = &self.doc else { return };
        let name = d.path.file_name().unwrap_or_default().to_string_lossy().to_string();
        self.doc = None;
        self.compare = None;
        self.base = None;
        self.prune_cols();
        self.undo.clear();
        self.redo.clear();
        self.pending = None;
        self.show_history = false;
        self.show_unchecked = false;
        self.remember_session();
        self.status = format!("Closed {name}");
    }
}

#[cfg(test)]
pub(crate) mod file_menu_tests {
    use super::*;

    fn sample_on_disk(app: &mut App, tag: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("file_menu_{tag}_{}.DAT", std::process::id()));
        std::fs::write(&p, include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.open(p.clone());
        p
    }

    /// Save As never writes over the file the edits came from, also when the dialog names it another way: through a
    /// link to it, or (on a disk that does not tell case apart, as macOS's and Windows' do by default) in other case.
    #[test]
    fn save_as_never_writes_over_the_opened_file() {
        let mut app = App::new(vec![], Prefs::default());
        let p = sample_on_disk(&mut app, "overwrite");
        let before = std::fs::read(&p).unwrap();
        app.apply(app.demo_edits());
        assert!(app.unsaved() > 0);
        let refused = |app: &mut App, to: PathBuf| {
            app.save_to(to.clone());
            assert!(app.status.starts_with("Refusing to overwrite the opened file"), "{}: {}", to.display(), app.status);
            assert_eq!(std::fs::read(&p).unwrap(), before, "{} left as it was", to.display());
        };
        refused(&mut app, p.clone());
        #[cfg(unix)]
        {
            let link = p.with_file_name(format!("link_{}", p.file_name().unwrap().to_string_lossy()));
            let _ = std::fs::remove_file(&link);
            std::os::unix::fs::symlink(&p, &link).unwrap();
            refused(&mut app, link.clone());
            let _ = std::fs::remove_file(&link);
        }
        let lower = p.with_file_name(p.file_name().unwrap().to_string_lossy().to_lowercase());
        if lower != p && lower.exists() {
            refused(&mut app, lower);
        }
        let _ = std::fs::remove_file(&p);
    }

    /// The editor's own folders of copies are known however a path reaches them: Save As never saves into them, and
    /// a file opened from them is not kept again.
    #[test]
    fn the_editors_own_folders_through_a_link() {
        let own = App::originals_dir();
        std::fs::create_dir_all(&own).unwrap();
        assert!(App::is_own_folder(&own) && App::is_own_folder(&own.join("sub")) && App::is_own_folder(&App::camera_dir()));
        assert!(!App::is_own_folder(&std::env::temp_dir()));
        #[cfg(unix)]
        {
            let link = std::env::temp_dir().join(format!("camset_own_link_{}", std::process::id()));
            let _ = std::fs::remove_file(&link);
            std::os::unix::fs::symlink(&own, &link).unwrap();
            assert!(App::is_own_folder(&link), "a link to the folder");
            let mut app = App::new(vec![], Prefs::default());
            let p = sample_on_disk(&mut app, "own_link");
            app.apply(app.demo_edits());
            app.save_to(link.join("CAMSET01.DAT"));
            assert!(app.status.starts_with("Those folders hold the editor's backups"), "{}", app.status);
            let _ = std::fs::remove_file(&link);
            let _ = std::fs::remove_file(&p);
        }
    }

    /// Close never throws edits away: with an edit it stays open and says why; without, it closes.
    #[test]
    fn close_keeps_unsaved_edits() {
        let mut app = App::new(vec![], Prefs::default());
        let p = sample_on_disk(&mut app, "close");
        let edits = app.demo_edits();
        assert!(!edits.is_empty());
        app.apply(edits);
        app.close_file();
        assert!(app.doc.is_some() && matches!(app.unsaved_ask, Some(Replace::Close)), "it asks first, as opening does");
        let then = app.unsaved_ask.take().unwrap();
        app.keep(then);   // Cancel
        assert!(app.doc.is_some(), "{}", app.status);
        while !app.undo.is_empty() { app.undo(); }
        app.close_file();
        assert!(app.doc.is_none(), "{}", app.status);
        let _ = std::fs::remove_file(&p);
    }

    /// F3 in Edit mode goes to each edited setting of the set in turn, in menu order, and round again.
    #[test]
    fn next_edit_steps_through_the_edits() {
        let mut app = App::new(vec![], Prefs::default());
        let p = sample_on_disk(&mut app, "next");
        let edits = app.demo_edits();
        let live = edits.iter().filter(|a| matches!(a, Action::Set(0, _, _))).count();
        app.apply(edits);
        let mut seen = Vec::new();
        for _ in 0..live {
            app.step_edit(1);
            assert!(matches!(app.view, View::Tab(_)));
            seen.push(app.item.clone().unwrap());
        }
        app.step_edit(1);
        assert_eq!(app.item.as_ref(), seen.first(), "round again");
        seen.sort();
        seen.dedup();
        assert_eq!(seen.len(), live, "each edit once");
        let _ = std::fs::remove_file(&p);
    }
}
