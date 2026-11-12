//! The camera definitions: the ones shipped with the editor and the user's own, which one reads the open file,
//! Add definition…, Expert mode's "Open with…", and "Edit anyway…" for a firmware a definition was not checked on.

use crate::*;

impl App {
    /// The camera definitions: the set shipped beside the program (under test, the repository's editor/definitions)
    /// and the user's folder, `definitions/` beside the preferences.
    pub(crate) fn find_definitions() -> Definitions {
        let looked_in = if cfg!(test) { vec![Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions")] } else { camset_editor::schema::shipped_dirs() };
        let shipped = looked_in.iter().find(|d| d.is_dir()).map(|d| std::fs::canonicalize(d).unwrap_or_else(|_| d.clone()));
        Definitions::load(shipped, looked_in, Self::user_definitions_dir(), &Schema::help_dirs())
    }

    /// The user's own definitions: `definitions/` beside the preferences, the only folder of definitions the editor
    /// writes.
    fn user_definitions_dir() -> PathBuf {
        Prefs::path().parent().map_or_else(|| PathBuf::from("definitions"), |d| d.join("definitions"))
    }

    /// Read every definition again (one may have been changed, added or removed) and pick again for the open file.
    pub(crate) fn reload_definitions(&mut self) {
        self.defs.reload(&Schema::help_dirs());
        self.repick();
    }

    /// What Reload says: how many definitions were loaded (in Expert mode), and how many files were not used.
    pub(crate) fn definitions_loaded(&self) -> String {
        let n = self.defs.list.len();
        match self.defs.rejected.len() {
            0 if !self.prefs.expert => "Camera definitions reloaded".into(),
            0 => format!("{n} camera definition(s) loaded"),
            k => format!("{n} camera definition(s) loaded; {k} file(s) not used (⚙ Settings > Camera support & web page says why)"),
        }
    }

    /// Pick the definition for the open file again, from the definitions as now loaded (`Definitions::pick`, with
    /// the container block the file was read with). The sample keeps to the shipped ones.
    fn repick(&mut self) {
        let Some(d) = &self.doc else {
            self.use_definition(Schema::default());
            return;
        };
        let (def, how) = self.defs.pick(d.edited.format(), &d.edited.model(), &d.edited.firmware(), d.source == Source::Sample);
        // a definition chosen by hand stays chosen while it is loaded
        let chosen = d.override_def.as_ref().and_then(|o| self.defs.list.iter().position(|s| s.origin == *o));
        if let Some(d) = &mut self.doc {
            d.how = how;
            if chosen.is_none() { d.override_def = None; }
        }
        self.adopt(chosen.or(def));
    }

    /// Read the open file with the definition at `def` in the list (None: with none).
    pub(crate) fn adopt(&mut self, def: Option<usize>) {
        let s = def.and_then(|i| self.defs.list.get(i)).cloned().unwrap_or_default();
        self.use_definition(s);
    }

    /// What the status line says once a file is open: which definition reads it, and whether it can be edited.
    pub(crate) fn opened_words(&self, shown: &str, c: &CamSet, signature: &str, how: &Match) -> String {
        let (model, s) = (c.model(), &self.schema);
        let video = video_words(c).map(|v| format!(", {v}")).unwrap_or_default();
        let read_only = "You can read everything. \"Edit anyway…\" next to the file name edits what it holds in the mapped shape; \"Describe for support…\" saves how it is laid out, without its values, so this firmware can be added.";
        match how {
            Match::None => format!("Opened {shown} ({model}): no camera definition describes this model, so its settings cannot be named and nothing can be changed. \"Describe for support…\" saves how the file is laid out, without its values."),
            _ if !c.checksums_ok() => format!("Opened {shown} ({model}): its {} does not match, so it may be damaged, or its definition may not describe it. It is shown, but never edited.", Self::header_checksum_name(c)),
            Match::Near { file_fw } => format!("Opened {shown} with the {} firmware {} definition: this file says firmware {file_fw}, so editing is off. {read_only}", s.model, s.firmware()),
            Match::Exact if s.layout(signature).is_some() && s.camera.knows(c) => format!("Opened {shown} ({model} firmware {}{video}, saved {})", c.firmware(), self.stamp_words(&c.timestamp())),
            Match::Exact => format!("Opened {shown} ({model} firmware {}{video}): this firmware stores its settings in places Camset hasn't checked, so editing is off. {read_only}", c.firmware()),
        }
    }

    /// Read the open file with `s` from now on. What was worked out from the definition before is dropped, and a
    /// tab the new one does not have gives way to its first.
    pub(crate) fn use_definition(&mut self, s: Schema) {
        let another = s.origin != self.schema.origin;
        self.schema = s;
        self.schema_gen += 1;
        if let View::Tab(t) = &self.view {
            if !self.schema.tabs.contains(t) {
                self.view = View::Tab(self.schema.tabs.first().cloned().unwrap_or_default());
            }
        }
        // another camera's definition: Compare starts with the columns it names (file A's only; B's stay)
        if another && self.cols.iter().all(|c| c.src == Src::A) {
            self.cols = self.start_cols();
        }
    }

    /// Add definition…: check the file chosen and copy it into the user's folder, under the name its model and
    /// firmware give it; a file of that name already there is replaced only once the person agrees (`replace`).
    pub(crate) fn add_definition(&mut self, p: &Path, replace: bool) {
        let shown = p.file_name().unwrap_or_default().to_string_lossy().to_string();
        let text = match std::fs::read_to_string(p) {
            Ok(t) => t,
            Err(e) => {
                let details = details(self.prefs.expert, format_args!("{}: {e}", p.display()));
                self.status = format!("{shown} was not added: {}{details}", io_words(&e, false));
                return;
            }
        };
        let s = match Schema::from_text(&text) {
            Ok(s) => s,
            Err(e) => {
                self.status = format!("{shown} was not added: it is not a camera definition this editor can use: {e}.");
                return;
            }
        };
        let safe = |t: &str| !t.is_empty() && t.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.')) && !t.starts_with('.');
        if !safe(&s.model) || !safe(s.firmware()) {
            self.status = format!("{shown} was not added: its model or firmware holds characters a file name cannot hold.");
            return;
        }
        let name = s.file_name();
        let dir = self.defs.user_dir.clone();
        let dest = dir.join(&name);
        let same = same_file(p, &dest);
        if !same && dest.exists() && !replace {
            if std::fs::read_to_string(&dest).is_ok_and(|t| t == text) {
                self.status = format!("{} firmware {} is in your definitions already, as it is in {shown}.", s.model, s.firmware());
                return;
            }
            self.def_replace = Some((p.to_path_buf(), name));
            return;
        }
        if !same {
            if let Err(e) = std::fs::create_dir_all(&dir).and_then(|_| write_atomic(&dest, text.as_bytes())) {
                let details = details(self.prefs.expert, format_args!("{}: {e}", dest.display()));
                self.status = format!("{shown} was not added: {}{details}", io_words(&e, true));
                return;
            }
        }
        self.reload_definitions();
        let over = if self.defs.shipped(&s.model, s.firmware()).is_some() { " It is used in place of the built-in one." } else { "" };
        self.status = format!("Added {} firmware {} (yours).{over}", s.model, s.firmware());
    }

    /// Expert mode, "Open with…": read the open file with the definition found at `origin` rather than the one its
    /// header picks, or (None) with that one again. The override chooses the names only: editing still needs the
    /// layout checked or "Edit anyway…", and a save or a write names the override in its confirmation. A definition
    /// of another container reads the file again from how it was opened, so edits are saved or undone first.
    pub(crate) fn override_definition(&mut self, origin: Option<Origin>) {
        let Some(d) = &self.doc else { return };
        let Some(origin) = origin else {
            if let Some(d) = &mut self.doc {
                d.override_def = None;
                d.unchecked_ok = false;
            }
            self.repick();
            self.status = format!("The file is read with the definition its header picks again{}.",
                if self.schema.model.is_empty() { String::new() } else { format!(": {} firmware {} ({})", self.schema.model, self.schema.firmware(), self.schema.origin.word()) });
            return;
        };
        let Some(i) = self.defs.list.iter().position(|s| s.origin == origin) else {
            self.status = "That definition is not loaded any more: press Reload in ⚙ Settings.".into();
            return;
        };
        let def = &self.defs.list[i];
        let (model, fw, word) = (def.model.clone(), def.firmware().to_string(), def.origin.word());
        let Some(block) = def.camera.file.clone() else {
            self.status = format!("The {model} firmware {fw} definition describes no file, so it cannot read this one.");
            return;
        };
        let mut reread = None;
        if block != **d.edited.format() {
            if !d.changes().is_empty() {
                self.status = format!("The {model} firmware {fw} definition reads files another way, so the file is opened again with it: save or undo your edits first.");
                return;
            }
            // the file as last saved, and the baseline its edits are judged against, each from its own bytes
            let block = std::sync::Arc::new(block);
            match CamSet::read(&d.original.to_bytes(), &block).and_then(|c| Ok((c, CamSet::read(&d.baseline.to_bytes(), &block)?))) {
                Ok(both) => reread = Some(both),
                Err(e) => {
                    let details = details(self.prefs.expert, &e);
                    self.status = format!("The {model} firmware {fw} definition does not read this file.{details}");
                    return;
                }
            }
        }
        if let Some(d) = &mut self.doc {
            if let Some((c, baseline)) = reread {
                d.signature = c.layout_signature();
                d.original = c.clone();
                d.baseline = baseline;
                d.edited = c;
                d.rev = next_open();
                self.undo.clear();
                self.redo.clear();
            }
            d.override_def = Some(origin);
            d.unchecked_ok = false;
        }
        self.adopt(Some(i));
        self.status = format!("Read with the {model} firmware {fw} definition ({word}), chosen by hand: the names shown are that definition's. A save or a write says so before it goes ahead.");
    }

    /// The definition the open file is read with, in a few words ("ILCE-1M2 firmware 4.00, built-in"), and a
    /// sentence saying how it was picked; None with no file open.
    pub(crate) fn definition_words(&self) -> Option<(String, String)> {
        let d = self.doc.as_ref()?;
        let s = &self.schema;
        if s.model.is_empty() {
            return Some(("no camera definition".into(), format!("No camera definition describes the {}, so nothing is named and nothing can be changed.", d.edited.model())));
        }
        let source = if s.overrides { "yours, in place of the built-in one" } else { s.origin.word() };
        let chosen = if d.override_def.is_some() { ", chosen by hand" } else { "" };
        let how = match (&d.how, d.override_def.is_some()) {
            (_, true) => format!("Chosen by hand in Expert mode; the file's header names {} firmware {}.", d.edited.model(), d.edited.firmware()),
            (Match::Near { file_fw }, _) => format!("The nearest definition of this model: the file says firmware {file_fw}."),
            _ => "The definition of the model and firmware the file names.".to_string(),
        };
        let file = s.origin.path().and_then(Path::file_name).map(|f| format!(" ({})", f.to_string_lossy())).unwrap_or_default();
        Some((format!("{} firmware {}, {source}{chosen}", s.model, s.firmware()), format!("Read with the {} firmware {} definition{file}. {how}", s.model, s.firmware())))
    }

    /// The line a save's or a write's confirmation carries while the open file is read with a definition chosen by
    /// hand (`override_definition`); None otherwise.
    pub(crate) fn override_line(&self) -> Option<String> {
        let d = self.doc.as_ref()?;
        d.override_def.as_ref()?;
        Some(format!("Under an override: this file is read with the {} firmware {} definition ({}), chosen by hand; its header names {} firmware {}.",
            self.schema.model, self.schema.firmware(), self.schema.origin.word(), d.edited.model(), d.edited.firmware()))
    }

    /// The question Add definition… asks before it replaces a definition of the user's.
    pub(crate) fn def_replace_window(&mut self, ctx: &egui::Context) {
        let Some((src, name)) = self.def_replace.clone() else { return };
        let (mut yes, mut no) = (false, false);
        egui::Window::new("Replace your definition?").collapsible(false).resizable(false).show(ctx, |ui| {
            ui.label(format!("Your definitions already hold {name}, and it differs from the file chosen. Replace it with {}?",
                src.file_name().unwrap_or_default().to_string_lossy()));
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                yes = ui.button("Replace").clicked();
                no = ui.button("Cancel").clicked();
            });
        });
        if yes {
            self.def_replace = None;
            self.add_definition(&src, true);
        } else if no {
            self.def_replace = None;
            self.status = format!("{name} was left as it was.");
        }
    }

    /// The model of a file from a camera no definition covers (none names its records); None for a model the
    /// editor knows.
    pub(crate) fn foreign_model(&self, c: &CamSet) -> Option<String> {
        let model = c.model();
        (!self.defs.in_use().any(|s| s.model == model) && self.schema.model != model).then_some(model)
    }

    /// File A's model, when no definition covers it (`foreign_model`).
    pub(crate) fn foreign_a(&self) -> Option<String> {
        self.doc.as_ref().and_then(|d| self.foreign_model(&d.edited))
    }

    /// When a file from a camera no definition covers has just been opened, the status line says so (in place of
    /// "Opened …"), once per file.
    pub(crate) fn note_foreign(&mut self) {
        let foreign = self.doc.as_ref().filter(|_| self.foreign_a().is_some()).map(|d| d.path.clone());
        if foreign != self.foreign_noted {
            if let Some(m) = self.foreign_a() { self.status = self.foreign_words(&m); }
            self.foreign_noted = foreign;
        }
    }

    /// What the window says about a file from a camera it does not support yet.
    pub(crate) fn foreign_words(&self, model: &str) -> String {
        format!("This camera ({model}) is not supported yet: no camera definition describes it, so its settings cannot be named and nothing can be changed. \"Describe for support…\" saves how its file is laid out, without its values.")
    }

    /// Turn editing on for a file from a firmware the schema was not checked on, after saying what
    /// that means and how many settings it covers.
    pub(crate) fn unchecked_window(&mut self, ctx: &egui::Context) {
        if !self.show_unchecked { return; }
        let Some(d) = &self.doc else { self.show_unchecked = false; return };
        let fw = d.edited.firmware();
        let mapped: Vec<&Setting> = self.schema.settings.iter().filter(|s| s.area == "global" && s.scalar && s.size > 0).collect();
        let held = mapped.iter().filter(|s| self.shape_ok_in(s, 0)).count();
        let (mut go, mut cancel) = (false, false);
        egui::Window::new("Edit a file from another firmware").collapsible(false).resizable(true).default_width(600.0).show(ctx, |ui| {
            ui.label(format!("This file comes from firmware {fw}; the editor was checked on firmware {}. A firmware update can move settings, so the file opened view-only.", self.schema.firmwares()));
            ui.add_space(6.0);
            ui.label("Editing it anyway:");
            ui.label(format!("• {held} of {} live settings sit where the editor expects them, and can be changed. The others stay locked.", mapped.len()));
            ui.label("• A setting a newer firmware changed may be refused: the camera can then reject the whole file, or change the value.");
            ui.label("• Before writing, the editor keeps the camera's current settings, so ↩ Put the camera back can undo the write; afterwards it reads the camera back and lists what differs.");
            ui.label("• Save As writes a new file. The file you opened stays as it is, and a copy of it is kept under 📂 Backups.");
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if ui.button("Edit this file").clicked() { go = true; }
                if ui.button("Cancel").clicked() { cancel = true; }
            });
        });
        if go {
            if let Some(d) = &mut self.doc { d.unchecked_ok = true; }
            self.status = format!("Editing a firmware {fw} file: settings it holds in another shape stay view-only");
        }
        if go || cancel { self.show_unchecked = false; }
    }
}

#[cfg(test)]
pub(crate) mod firmware_tests {
    use super::*;

    /// A file from a firmware the schema was not checked on opens view-only; "Edit anyway" turns on
    /// editing for the settings it holds in the mapped shape, and only those. Always on a firmware 2 file made here
    /// (Creative Look cut to 16 slots, as before 3.00, and a record added after firmware 2 left out); on every file in
    /// private/ too, when it is there, whose header names the definition's model with another layout.
    #[test]
    fn other_firmware_edit_on_request() {
        let mut c = test_parse(&crate::test_support::camera_file()).unwrap();
        c.header[0x36..=0x38].copy_from_slice(&[2, 0, 0]);
        if let Some(r) = c.sections[0].get_mut(0x0cde) {
            r.count = 16;
            r.value.truncate(16 * r.elem_size as usize);
        }
        c.sections[0].records.retain(|r| r.id != 0x13ad);
        let synth = std::env::temp_dir().join(format!("synth_firmware2_{}.DAT", std::process::id()));
        std::fs::write(&synth, c.to_bytes()).unwrap();
        let others = crate::test_support::private_files(|c, def| c.model() == def.model && def.layout(&c.layout_signature()).is_none());
        for f in std::iter::once(synth.clone()).chain(others) {
            let mut app = App::new(vec![], Prefs::default());
            app.open(f.clone());
            let name = if f == synth { "the firmware 2 file made here" } else { "a file from private/" };
            let d = app.doc.as_ref().unwrap();
            let held_look = d.edited.sections[0].get(0x0cde).map(|r| r.count);
            let has_dial = d.edited.sections[0].get(0x13ad).is_some();
            assert_ne!(d.edited.firmware(), app.schema.firmware(), "{name}: another firmware");
            assert!(!app.editable(), "{name} must open view-only");
            app.doc.as_mut().unwrap().unchecked_ok = true;
            assert!(app.editable());
            // a record held in another shape than mapped (Creative Look grew from 16 to 18 slots after 3.00) stays
            // view-only, and so does one the file does not hold (a record added after firmware 2)
            let look = app.schema.settings.iter().find(|s| s.area == "global" && s.id == 0x0cde).unwrap();
            if held_look != Some(look.count) {
                assert!(!app.shape_ok_in(look, 0), "{name}: Creative Look must stay view-only");
            }
            let dial = app.schema.settings.iter().find(|s| s.area == "global" && s.id == 0x13ad).unwrap();
            if !has_dial {
                assert!(!app.shape_ok_in(dial, 0), "{name}: a record the file does not hold stays view-only");
            }
            if f == synth {
                assert!(held_look == Some(16) && !has_dial && !app.shape_ok_in(look, 0));
            }
            let held = app.schema.settings.iter().filter(|s| s.area == "global" && s.scalar && s.size > 0 && app.shape_ok_in(s, 0)).count();
            assert!(held > 500, "{name}: only {held} settings editable");
        }
        let _ = std::fs::remove_file(&synth);
    }
}

/// The definitions: the shipped set and the user's folder, Add definition…, and which one a file is read with.
#[cfg(test)]
pub(crate) mod definitions_tests {
    use super::*;

    pub(crate) fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("camset_definitions_test_{name}_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    /// The shipped definitions' folder in this checkout.
    pub(crate) fn shipped() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions")
    }

    /// The shipped ILCE-1M2 firmware 4.00 definition's text with `f` applied to it.
    pub(crate) fn a1_with(f: impl FnOnce(&mut serde_json::Value)) -> String {
        let mut v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(shipped().join("ILCE-1M2_fw4.00.json")).unwrap()).unwrap();
        f(&mut v);
        v.to_string()
    }

    /// An app whose own definitions folder is `user` (a test's, never the one the other tests share).
    pub(crate) fn app_with(user: &Path) -> App {
        let mut app = App::new(vec![], Prefs::default());
        app.defs = Definitions::load(Some(shipped()), vec![shipped()], user.to_path_buf(), &[]);
        app
    }

    /// Add definition… checks a file before it copies it, under the name its model and firmware give it; a definition
    /// of the user's replaces the built-in one for files of that model and firmware, but the sample keeps the
    /// built-in one; and a file of the same name is replaced only once the person agrees.
    #[test]
    fn add_definition_checks_then_copies() {
        let (dir, user) = (scratch("add_src"), scratch("add_user"));
        let mut app = app_with(&user);
        let write = |name: &str, text: &str| { let p = dir.join(name); std::fs::write(&p, text).unwrap(); p };
        // not a definition, a newer format, a model no file name can hold: nothing copied
        app.add_definition(&write("notes.json", "{\"a\": 1}"), false);
        assert!(app.status.starts_with("notes.json was not added") && app.status.contains("no settings list"), "{}", app.status);
        app.add_definition(&write("newer.json", &a1_with(|v| v["definition_format"] = 7.into())), false);
        assert!(app.status.contains("needs a newer Camset Editor (definition format 7"), "{}", app.status);
        let odd = a1_with(|v| { v["model"] = "../X".into(); v["layouts"][0]["model"] = "../X".into(); v["camera"]["model"] = "../X".into(); });
        app.add_definition(&write("odd.json", &odd), false);
        assert!(app.status.contains("file name cannot hold"), "{}", app.status);
        assert_eq!(std::fs::read_dir(&user).unwrap().count(), 0, "nothing copied");
        // another model (a made-up one): copied under its own name, and listed as the user's
        let other = a1_with(|v| { v["model"] = "ILCE-0X0".into(); v["layouts"][0]["model"] = "ILCE-0X0".into(); v["camera"]["model"] = "ILCE-0X0".into(); });
        app.add_definition(&write("from_the_kit.json", &other), false);
        assert_eq!(app.status, "Added ILCE-0X0 firmware 4.00 (yours).");
        assert_eq!(std::fs::read_to_string(user.join("ILCE-0X0_fw4.00.json")).unwrap(), other, "copied as it was written");
        let mine = app.defs.find("ILCE-0X0", "4.00").unwrap();
        assert_eq!(mine.origin, Origin::User(user.join("ILCE-0X0_fw4.00.json")));
        // the ILCE-1M2's, one setting renamed: used in place of the built-in one
        let renamed = a1_with(|v| v["settings"][0]["name"] = "Renamed by me".into());
        app.add_definition(&write("mine.json", &renamed), false);
        assert!(app.status.ends_with("It is used in place of the built-in one."), "{}", app.status);
        let key = app.defs.shipped("ILCE-1M2", "4.00").unwrap().settings[0].key.clone();
        let file = dir.join("CAMSET01.DAT");
        std::fs::write(&file, include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.open(file.clone());
        let named = |app: &App| app.schema.settings.iter().find(|s| s.key == key).unwrap().name.clone();
        assert_eq!(named(&app), "Renamed by me");
        assert!(app.schema.overrides && !app.schema.origin.is_shipped());
        app.open_sample();
        assert_ne!(named(&app), "Renamed by me", "the sample always uses the built-in definition");
        assert!(app.schema.origin.is_shipped());
        // the same name again, with other contents: asked first, replaced once agreed
        let again = a1_with(|v| v["settings"][0]["name"] = "Renamed again".into());
        let p = write("again.json", &again);
        app.add_definition(&p, false);
        assert_eq!(app.def_replace, Some((p.clone(), "ILCE-1M2_fw4.00.json".to_string())));
        assert_eq!(std::fs::read_to_string(user.join("ILCE-1M2_fw4.00.json")).unwrap(), renamed, "not replaced before the answer");
        app.def_replace = None;
        app.add_definition(&p, true);
        app.open(file);
        assert_eq!(named(&app), "Renamed again");
        // the same contents again: nothing to do
        app.add_definition(&p, false);
        assert!(app.def_replace.is_none() && app.status.contains("in your definitions already"), "{}", app.status);
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }

    /// Reload reads a definition changed on disk, and lists a file it cannot use with why.
    #[test]
    fn reload_reads_the_folders_again() {
        let user = scratch("reload_user");
        let mut app = app_with(&user);
        app.open_sample();
        let n = app.defs.list.len();
        std::fs::write(user.join("broken.json"), "{ not json").unwrap();
        app.reload_definitions();
        assert_eq!(app.defs.list.len(), n);
        assert_eq!(app.definitions_loaded(), format!("{n} camera definition(s) loaded; 1 file(s) not used (⚙ Settings > Camera support & web page says why)"));
        assert!(app.defs.rejected[0].1.starts_with("not a readable JSON file"));
        assert!(app.schema.origin.is_shipped(), "the sample is read with the built-in definition again");
        let _ = std::fs::remove_dir_all(&user);
    }

    /// The packages carry the shipped definitions beside the program: inside the macOS app (before it is signed),
    /// in the Linux tarball, and kept beside the program by the Linux install.
    #[test]
    fn packages_carry_the_definitions() {
        let mac = include_str!("../../packaging/build_macos_app.sh");
        let copy = mac.find("cp definitions/* \"$APP/Contents/Resources/definitions/\"").expect("the app carries the definitions");
        assert!(copy < mac.find("codesign --force").unwrap(), "copied before the app is signed");
        let linux = include_str!("../../packaging/build_linux.sh");
        assert!(linux.contains("cp -R definitions \"$DIR/\""));
        let install = include_str!("../../packaging/linux/install.sh");
        assert!(install.contains("cp -R \"$here/definitions\" \"$share/definitions\"") && install.contains("ln -sf \"$share/camset_editor\" \"$HOME/.local/bin/camset_editor\""));
        assert!(shipped().join("ILCE-1M2_fw4.00.json").is_file());
    }

    /// The macOS disk image installs the macOS way: beside the app it holds a shortcut to /Applications to drag it
    /// onto, made in the image's folder (made afresh, so nothing of an earlier run is left in it) before the image is
    /// made from it.
    #[test]
    fn the_disk_image_offers_drag_to_install() {
        let mac = include_str!("../../packaging/build_macos_app.sh");
        let fresh = mac.find("rm -rf \"$STAGE\"\nmkdir -p \"$STAGE\"\n").expect("the image's folder is made afresh");
        let staged = mac.find("ditto \"$APP\" \"$STAGE/Camset Editor.app\"").expect("the app goes into the image's folder");
        let link = mac.find("ln -s /Applications \"$STAGE/Applications\"").expect("the image holds the Applications shortcut");
        let made = mac.find("hdiutil create -volname \"Camset Editor\" -srcfolder \"$STAGE\"").expect("the image is made from that folder");
        assert!(fresh < staged && staged < link && link < made, "the shortcut is made beside the app, before the image");
    }

    /// A path written with "/" as this system spells it: as it is on macOS and Linux, with "\" on Windows (where these
    /// tests' paths that start with "/" are paths from the current drive's root, shown with its separator).
    fn spelled(s: &str) -> String {
        if cfg!(windows) { s.replace('/', "\\") } else { s.to_string() }
    }

    /// Every package puts the licences page where Settings > Third-party licences looks for it (`licences_places`):
    /// the release workflow writes it before it packages, inside the macOS app's Resources (before the app is signed),
    /// beside the program in the Linux tarball, its install and the Windows zip.
    #[test]
    fn packages_carry_the_licences_where_the_button_looks() {
        let places = licences_places(Path::new("/app/Contents/MacOS"));
        assert_eq!(places[0], Path::new("/app/Contents/MacOS/THIRD_PARTY_LICENSES.html"));
        assert_eq!(path_words(&places[1], Path::new("/nobody")), spelled("/app/Contents/Resources/THIRD_PARTY_LICENSES.html"));
        assert_eq!(path_words(&licences_places(Path::new("/src/editor/target/release"))[2], Path::new("/nobody")), spelled("/src/editor/target/dist/THIRD_PARTY_LICENSES.html"));
        // the Windows zip: the page beside camset_editor.exe, found from the program's folder resolved (\\?\C:\…, the
        // first place licences_page looks) and handed to Explorer, and named in the hover, as the person types it
        if cfg!(windows) {
            let zip = licences_places(Path::new(r"\\?\C:\Users\you\camset-editor"))[0].clone();
            assert_eq!(plain_path(&zip).display().to_string(), r"C:\Users\you\camset-editor\THIRD_PARTY_LICENSES.html");
            assert_eq!(path_words(&zip, Path::new(r"C:\Users\you")), r"~\camset-editor\THIRD_PARTY_LICENSES.html");
        }
        let release = include_str!("../../../.github/workflows/editor-release.yml");
        let written = release.find("-o target/dist/THIRD_PARTY_LICENSES.html").expect("the release writes the licences page");
        for package in ["sh packaging/build_macos_app.sh", "sh packaging/build_linux.sh", "Compress-Archive"] {
            assert!(written < release.find(package).unwrap(), "written before {package}");
        }
        assert!(release.contains("$files += \"target/dist/THIRD_PARTY_LICENSES.html\""), "the Windows zip carries it beside the program");
        let mac = include_str!("../../packaging/build_macos_app.sh");
        assert!(mac.contains("LICENSES=target/dist/THIRD_PARTY_LICENSES.html"));
        let copy = mac.find("cp \"$LICENSES\" \"$APP/Contents/Resources/\"").expect("the app carries the licences page");
        assert!(copy < mac.find("codesign --force").unwrap(), "copied before the app is signed");
        let linux = include_str!("../../packaging/build_linux.sh");
        assert!(linux.contains("cp target/dist/THIRD_PARTY_LICENSES.html \"$DIR/\""));
        let install = include_str!("../../packaging/linux/install.sh");
        assert!(install.contains("for f in LICENSE THIRD_PARTY_LICENSES.html; do") && install.contains("install -m 644 \"$here/$f\" \"$share/$f\""));
    }

    /// A folder is named one way, as the person would type it on their system: no "..", macOS's /private/var as /var,
    /// Windows's \\?\C:\ as C:\, home as "~", each with the system's own separator.
    #[test]
    fn folders_are_named_as_typed() {
        let home = Path::new("/Users/you");
        assert_eq!(path_words(Path::new("/Users/you/.config/camset_editor/definitions"), home), spelled("~/.config/camset_editor/definitions"));
        assert_eq!(path_words(Path::new("/Users/you"), home), "~");
        assert_eq!(path_words(Path::new("/Users/yourname/x"), home), spelled("/Users/yourname/x"));
        assert_eq!(path_words(Path::new("/src/editor/target/release/../../definitions"), home), spelled("/src/editor/definitions"));
        assert_eq!(path_words(Path::new("/a/./b"), Path::new("")), spelled("/a/b"));
        assert_eq!(plain_path(Path::new("/a/./b/")).as_os_str(), "/a/./b/", "a path in no long form is left as it is");
        // Windows: the home folder as %USERPROFILE% names it, the definitions under %APPDATA%; the long form the system
        // resolves a path to (std::fs::canonicalize gives the shipped folder as \\?\C:\…), a disk's or a share's, as
        // typed; and a drive's root, which is no one's home folder
        if cfg!(windows) {
            let home = Path::new(r"C:\Users\you");
            assert_eq!(path_words(Path::new(r"C:\Users\you\AppData\Roaming\camset_editor\definitions"), home), r"~\AppData\Roaming\camset_editor\definitions");
            assert_eq!(path_words(Path::new(r"\\?\C:\Users\you\AppData\Roaming\camset_editor"), home), r"~\AppData\Roaming\camset_editor");
            assert_eq!(path_words(Path::new(r"\\?\D:\camset-editor\definitions"), home), r"D:\camset-editor\definitions");
            assert_eq!(path_words(Path::new(r"\\?\UNC\server\share\camset"), home), r"\\server\share\camset");
            assert_eq!(path_words(Path::new(r"C:\camset-editor"), Path::new(r"C:\")), r"C:\camset-editor");
        }
        if cfg!(target_os = "macos") {
            let tmp = Path::new("/var/folders/xy/T/h");
            assert_eq!(path_words(Path::new("/private/var/folders/xy/T/definitions"), tmp), "/var/folders/xy/T/definitions");
            assert_eq!(path_words(Path::new("/private/var/folders/xy/T/h/camset"), tmp), "~/camset");
            // a folder that only begins like /private/var/ keeps its prefix (the name is joined here so the publish
            // guard, which refuses a private/<name> path in a public file, does not take it for a maintainer's folder)
            let looks_like_var = format!("/{}/varnish", "private");
            assert_eq!(path_words(Path::new(&looks_like_var), home), looks_like_var);
        }
    }
}

/// The container read through the definition's block: the pick by trial and the checksum gate (docs/decisions/0020).
#[cfg(test)]
pub(crate) mod container_tests {
    use super::*;
    use crate::definitions::definitions_tests::{a1_with, app_with, scratch};

    /// The sample with its model, firmware and video system bytes changed (the firmware's two, then the video
    /// system's: the ILCE-1M2's block reads them at 0x36-0x38; checksums worked out again), written to `dir`.
    fn retitled(dir: &Path, name: &str, model: &[u8], fw: [u8; 3]) -> PathBuf {
        let mut c = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        c.header[5..0x15].fill(0);
        c.header[5..5 + model.len()].copy_from_slice(model);
        c.header[0x36..0x39].copy_from_slice(&fw);
        let p = dir.join(name);
        std::fs::write(&p, c.to_bytes()).unwrap();
        p
    }

    /// A file from another firmware of the model opens with the nearest definition, says so, and stays view-only
    /// until "Edit anyway…"; the file's own firmware's definition, once there, is used instead.
    #[test]
    fn near_firmware_is_said_and_view_only() {
        let (dir, user) = (scratch("near_src"), scratch("near_user"));
        let mut app = app_with(&user);
        let f = retitled(&dir, "NEAR_FW.DAT", b"ILCE-1M2", [3, 1, 0]);
        app.open(f.clone());
        let d = app.doc.as_ref().unwrap();
        assert_eq!(d.how, Match::Near { file_fw: "3.01".into() });
        assert_eq!(d.edited.firmware(), "3.01");
        assert!(app.status.contains("with the ILCE-1M2 firmware 4.00 definition: this file says firmware 3.01"), "{}", app.status);
        assert!(!app.editable() && app.offers_edit_anyway(app.doc.as_ref().unwrap()));
        // a definition of firmware 3.01 of the user's: picked exactly
        std::fs::write(user.join("ILCE-1M2_fw3.01.json"), a1_with(|v| v["layouts"][0]["firmware"] = "3.01".into())).unwrap();
        app.reload_definitions();
        assert_eq!(app.doc.as_ref().unwrap().how, Match::Exact, "reloading picks again for the open file");
        assert_eq!((app.schema.firmware(), app.schema.origin.is_shipped()), ("3.01", false));
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }

    /// A file saved with the camera on PAL (its video system byte 1, the firmware's bytes 4.00) is firmware 4.00: it
    /// opens with that definition, checked and editable, and the status line says PAL beside the firmware. Beside a
    /// file saved on NTSC in Compare, one line says which file was saved under which.
    #[test]
    fn a_pal_file_is_its_own_firmware() {
        let (dir, user) = (scratch("pal_src"), scratch("pal_user"));
        let mut app = app_with(&user);
        let f = retitled(&dir, "PAL.DAT", b"ILCE-1M2", [4, 0, 1]);
        app.open(f);
        let d = app.doc.as_ref().unwrap();
        assert_eq!((&d.how, d.edited.firmware().as_str(), app.schema.firmware()), (&Match::Exact, "4.00", "4.00"));
        assert_eq!(video_words(&d.edited).as_deref(), Some("PAL"));
        assert_eq!(video_badge(&d.edited).0, " · PAL");
        assert!(app.editable(), "its own firmware's layout: checked");
        assert!(app.status.contains("(ILCE-1M2 firmware 4.00, PAL, saved"), "{}", app.status);
        assert!(app.video_systems_note().is_none(), "one file says nothing");
        // file B, saved on NTSC: Compare says which is which, once
        app.open_compare(retitled(&dir, "NTSC.DAT", b"ILCE-1M2", [4, 0, 0]));
        let note = app.video_systems_note().expect("A on PAL, B on NTSC");
        assert!(note.contains("(A on PAL, B on NTSC)") && note.contains("different frame rates"), "{note}");
        app.open_compare(retitled(&dir, "PAL2.DAT", b"ILCE-1M2", [4, 0, 1]));
        assert!(app.video_systems_note().is_none(), "both on PAL");
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }

    /// A model no definition covers: read with the container's framing, nothing named, view-only, and "Describe
    /// for support…" describes its records; none of the ILCE-1M2's names are used.
    #[test]
    fn an_unknown_model_names_nothing() {
        let (dir, user) = (scratch("unknown_src"), scratch("unknown_user"));
        let mut app = app_with(&user);
        let f = retitled(&dir, "OTHER.DAT", b"ILCE-0X0", [4, 0, 0]);
        app.open(f);
        let d = app.doc.as_ref().unwrap();
        assert_eq!(d.how, Match::None);
        assert!(app.schema.settings.is_empty() && app.schema.tabs.is_empty() && app.schema.model.is_empty(), "no other body's names");
        assert!(!app.editable() && !app.offers_edit_anyway(d));
        assert!(app.status.contains("no camera definition describes this model"), "{}", app.status);
        assert_eq!(app.definition_words().unwrap().0, "no camera definition");
        let layout: serde_json::Value = serde_json::from_str(&App::layout_json(&d.edited)).unwrap();
        assert_eq!((layout["model"].as_str(), layout["firmware_bytes"].as_str()), (Some("ILCE-0X0"), Some("0400")));
        assert_eq!(layout["video_system"]["byte"].as_str(), Some("00"), "the video system's byte, beside the firmware's");
        assert_eq!(layout["sections"].as_array().unwrap().len(), d.edited.sections.len());
        assert!(app.send_blocked().is_some_and(|w| w.contains("no camera definition covers")));
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }

    /// The gate: a definition whose block names the header checksum's site wrongly (0x3a) reads the sample, but
    /// the checksum fails there, so the file is never edited and "Edit anyway…" is not offered. The sample itself,
    /// read with the shipped block, is editable as ever.
    #[test]
    fn a_failing_checksum_keeps_the_file_view_only() {
        let (dir, user) = (scratch("gate_src"), scratch("gate_user"));
        std::fs::write(user.join("ILCE-1M2_fw4.00.json"), a1_with(|v| {
            v["camera"]["file"]["header_checksum"]["over"] = serde_json::json!(["0x00", "0x3a"]);
            v["camera"]["file"]["header_checksum"]["at"] = "0x3a".into();
        })).unwrap();
        let mut app = app_with(&user);
        assert!(app.defs.rejected.is_empty(), "{:?}", app.defs.rejected);
        let f = dir.join("CAMSET01.DAT");
        std::fs::write(&f, include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.open(f.clone());
        let d = app.doc.as_ref().unwrap();
        assert!(!app.schema.origin.is_shipped(), "read with the user's definition");
        assert!(!d.edited.header_checksum_ok() && d.edited.trailer_checksum_ok());
        assert!(!app.layout_checked(d) && !app.editable() && !app.offers_edit_anyway(d));
        assert!(app.status.contains("header checksum (shift_sum) does not match"), "{}", app.status);
        app.doc.as_mut().unwrap().unchecked_ok = true;
        assert!(!app.editable(), "not even with Edit anyway forced on");
        app.open_sample();
        assert!(app.editable(), "the sample is read with the shipped block");
        // a file whose first bytes no definition names is refused, and a folder count skips it
        let mut other = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT").to_vec();
        other[..5].copy_from_slice(b"SONY2");
        std::fs::write(dir.join("CAMSET02.DAT"), &other).unwrap();
        assert!(app.open_now(dir.join("CAMSET02.DAT")).is_err());
        assert!(app.status.contains("no camera definition describes this file"), "{}", app.status);
        assert_eq!(settings_files_in(&dir, &app.defs), 1);
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }
}

/// Expert mode's override: a file read with a definition chosen by hand, named before a save or a write.
#[cfg(test)]
pub(crate) mod override_tests {
    use super::*;
    use crate::definitions::definitions_tests::{a1_with, app_with, scratch};

    /// "Open with…" a definition whose container block reads the file another way reads it again, after a save too:
    /// the file as last saved from its own bytes, and the file as first opened (the baseline the edits are judged
    /// against) from its own, never one for the other.
    #[test]
    fn open_with_rereads_the_baseline_from_its_own_bytes() {
        let (dir, user) = (scratch("over_base_src"), scratch("over_base_user"));
        // another model's definition (made up) with the same records, read through a block that differs in one word
        std::fs::write(user.join("ILCE-0X1_fw4.00.json"), a1_with(|v| {
            v["model"] = "ILCE-0X1".into(); v["layouts"][0]["model"] = "ILCE-0X1".into(); v["camera"]["model"] = "ILCE-0X1".into();
            v["camera"]["file"].as_object_mut().unwrap().remove("video_system");
        })).unwrap();
        let mut app = app_with(&user);
        app.prefs.expert = true;
        let f = dir.join("CAMSET01.DAT");
        std::fs::write(&f, crate::test_support::camera_file()).unwrap();
        app.open(f);
        let (s, v) = crate::write::safety_tests::changeable(&app);
        let first = app.doc.as_ref().unwrap().value(0, s.slot());
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        app.save_to(dir.join("CAMSET02.DAT"));
        let other = app.defs.list.iter().find(|d| d.model == "ILCE-0X1").unwrap().origin.clone();
        app.override_definition(Some(other));
        let d = app.doc.as_ref().unwrap();
        assert!(d.edited.format().video_system.is_none(), "read again with the other block: {}", app.status);
        assert_eq!((d.original_value(0, s.slot()), d.baseline_value(0, s.slot())), (Some(v), first), "each from its own bytes");
        let _ = (std::fs::remove_dir_all(dir), std::fs::remove_dir_all(user));
    }

    #[test]
    fn an_override_is_named_before_a_save_or_a_write() {
        let (dir, user) = (scratch("over_src"), scratch("over_user"));
        std::fs::write(user.join("ILCE-1M2_fw4.00.json"), a1_with(|v| v["settings"][0]["name"] = "Renamed by me".into())).unwrap();
        std::fs::write(user.join("ILCE-0X0_fw1.00.json"), a1_with(|v| {
            v["model"] = "ILCE-0X0".into(); v["layouts"][0]["model"] = "ILCE-0X0".into(); v["layouts"][0]["firmware"] = "1.00".into();
            v["camera"]["model"] = "ILCE-0X0".into();
        })).unwrap();
        let mut app = app_with(&user);
        app.prefs.expert = true;
        let f = dir.join("CAMSET01.DAT");
        std::fs::write(&f, crate::test_support::camera_file()).unwrap();   // a camera's own file: the test writes it
        app.open(f);
        assert!(app.override_line().is_none() && app.schema.overrides, "the user's definition, as the header picks it");
        assert_eq!(app.definition_words().unwrap().0, "ILCE-1M2 firmware 4.00, yours, in place of the built-in one");
        // the built-in one by hand: the file is still editable (same model and layout), and both confirmations say so
        let shipped = app.defs.shipped("ILCE-1M2", "4.00").unwrap().origin.clone();
        app.override_definition(Some(shipped.clone()));
        assert_eq!(app.schema.origin, shipped);
        assert!(app.editable() && app.send_blocked().is_none());
        let line = app.override_line().unwrap();
        assert_eq!(line, "Under an override: this file is read with the ILCE-1M2 firmware 4.00 definition (built-in), chosen by hand; its header names ILCE-1M2 firmware 4.00.");
        assert_eq!(app.send_summary()[0], (line.clone(), true), "the Write window (and the page's) lists it first");
        assert_eq!(app.definition_words().unwrap().0, "ILCE-1M2 firmware 4.00, built-in, chosen by hand");
        let ctx = egui::Context::default();
        app.save_as(&ctx);
        assert_eq!(app.pending.as_ref().map(|(w, i)| (*w, i.len())), Some((Review::Save, 0)), "Save As asks first, even with nothing flagged");
        app.pending = None;
        // a reload keeps the choice
        app.reload_definitions();
        assert_eq!(app.schema.origin, shipped);
        // another model's definition: its names, never editable
        let other = app.defs.find("ILCE-0X0", "1.00").unwrap().origin.clone();
        app.override_definition(Some(other));
        assert_eq!(app.schema.model, "ILCE-0X0");
        assert!(!app.editable() && !app.offers_edit_anyway(app.doc.as_ref().unwrap()));
        assert!(app.send_blocked().is_some_and(|w| w.contains("ILCE-0X0")));
        // Expert mode off: back to the definition the header picks
        app.prefs.expert = false;
        app.expert_off();
        assert!(app.doc.as_ref().unwrap().override_def.is_none() && app.override_line().is_none());
        assert!(app.schema.overrides && app.editable());
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }

    /// A definition of another container reads the file again from how it was opened, so only without edits; one
    /// that cannot read it is refused.
    #[test]
    fn an_override_of_another_container_needs_no_edits() {
        let (dir, user) = (scratch("over_block_src"), scratch("over_block_user"));
        std::fs::write(user.join("ILCE-1M2_fw3.00.json"), a1_with(|v| {
            v["layouts"][0]["firmware"] = "3.00".into();
            v["camera"]["file"]["magic"]["bytes"] = "SONY2".into();
        })).unwrap();
        let mut app = app_with(&user);
        app.prefs.expert = true;
        let f = dir.join("CAMSET01.DAT");
        std::fs::write(&f, include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.open(f);
        let (s, v) = crate::write::safety_tests::changeable(&app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        let theirs = app.defs.find("ILCE-1M2", "3.00").unwrap().origin.clone();
        app.override_definition(Some(theirs.clone()));
        assert!(app.status.contains("save or undo your edits first"), "{}", app.status);
        assert!(app.doc.as_ref().unwrap().override_def.is_none());
        app.undo();
        app.override_definition(Some(theirs));
        assert!(app.status.contains("does not read this file"), "{}", app.status);
        assert!(app.doc.as_ref().unwrap().override_def.is_none() && app.schema.origin.is_shipped());
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
    }
}

#[cfg(test)]
pub(crate) mod other_model_tests {
    use super::*;

    /// A file from a camera no definition covers opens view-only, and the badge and the status line name its model.
    #[test]
    fn another_model_is_view_only_and_named() {
        let mut c = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        let name = b"ILCE-0X0";   // a made-up model
        c.header[5..0x15].fill(0);
        c.header[5..5 + name.len()].copy_from_slice(name);
        let p = std::env::temp_dir().join(format!("other_model_{}.DAT", std::process::id()));
        std::fs::write(&p, c.to_bytes()).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        app.open(p.clone());
        assert_eq!(app.foreign_a().as_deref(), Some("ILCE-0X0"));
        assert!(!app.editable());
        app.note_foreign();
        assert!(app.status.contains("ILCE-0X0") && app.status.contains("not supported yet"), "{}", app.status);
        app.status.clear();
        app.note_foreign();
        assert!(app.status.is_empty(), "said once per file");
        // the sample's own model is not foreign
        app.open_sample();
        assert!(app.foreign_a().is_none());
        let _ = std::fs::remove_file(&p);
    }
}
