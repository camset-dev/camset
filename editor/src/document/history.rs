//! The Backups window (every copy the editor keeps) and the Edit history window.

use crate::*;

/// A copy the editor keeps (the Backups window).
pub(crate) struct Backup {
    pub(crate) when: String,
    pub(crate) kind: &'static str,
    pub(crate) path: PathBuf,
}

/// One line of the History window: the section, the record, its name, and its value before and after the step.
pub(crate) struct HistRow {
    pub(crate) si: usize,
    pub(crate) id: u16,
    pub(crate) name: String,
    pub(crate) before: String,
    pub(crate) after: String,
}

/// Which snapshots a History step's lines were worked out from: the step's own snapshot and the one after it
/// (the current file for the last step), by where their records are kept, the number of steps, for the last step the
/// current file's state (`Doc::rev`), and whether the raw numbers are shown. A snapshot is never changed once kept;
/// the current file is, by every edit, a drag joined to its step included, so lines with the same key are still right.
pub(crate) type HistKey = (usize, usize, usize, u64, bool);

impl App {
    /// Every kept copy, newest first: originals, and the camera's settings at each read and around each write.
    pub(crate) fn list_backups() -> Vec<Backup> {
        let mut v = Vec::new();
        for (dir, camera) in [(Self::originals_dir(), false), (Self::camera_dir(), true)] {
            let Ok(rd) = std::fs::read_dir(&dir) else { continue };
            for e in rd.flatten() {
                let path = e.path();
                if !path.extension().is_some_and(|x| x.eq_ignore_ascii_case("dat")) { continue; }
                let name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
                let kind = if !camera { "Original, as first opened" }
                    else if name.starts_with("before_write_") { "Camera, just before a write" }
                    else if name.starts_with("verify_") { "Camera, read back after a write" }
                    else if name.starts_with("SEND_") { "Written to the camera" }
                    else { "Camera, read" };
                let modified = e.metadata().and_then(|m| m.modified()).ok();
                v.push((modified, Backup { when: modified.map(|t| when_words(&stamp_of(t))).unwrap_or_default(), kind, path }));
            }
        }
        v.sort_by_key(|b| std::cmp::Reverse(b.0));
        v.into_iter().map(|(_, b)| b).collect()
    }

    /// The copies the editor keeps: every settings file as first opened, and the camera's settings
    /// at each read and around each write. Any can be opened; Save As and Write to camera then work
    /// as on any file, and the copy itself is never written over.
    pub(crate) fn backups_window(&mut self, ctx: &egui::Context) {
        if !self.show_backups { return; }
        let mut shown = true;
        let mut open = None;
        let mut compare = None;
        let has_doc = self.doc.is_some();
        let mut refresh = false;
        egui::Window::new("Backups").open(&mut shown).resizable(true).default_width(660.0).show(ctx, |ui| {
            ui.label(RichText::new("The editor never writes into a file it opened. It keeps every settings file as first opened (and any file a Save As replaces), and the camera's settings at every read, just before every write and after it. To go back, open a copy and write it to the camera or Save As.").small());
            ui.label(RichText::new(format!("Originals: {}\nCamera: {}", shown_path(&Self::originals_dir()), shown_path(&Self::camera_dir()))).small().color(tone::weak(ui.visuals())));
            if ui.small_button("Refresh").clicked() { refresh = true; }
            ui.add_space(4.0);
            if self.backups.is_empty() { ui.label("Nothing kept yet."); }
            egui::ScrollArea::vertical().max_height(420.0).show(ui, |ui| {
                egui::Grid::new("backups").striped(true).num_columns(4).spacing([14.0, 4.0]).show(ui, |ui| {
                    for b in &self.backups {
                        ui.label(&b.when);
                        ui.label(b.kind);
                        ui.label(RichText::new(b.path.file_name().unwrap_or_default().to_string_lossy()).small()).on_hover_text(b.path.display().to_string());
                        ui.horizontal(|ui| {
                            if ui.small_button("Open").on_hover_text("Open this copy; edits go to a new file with Save As, so the copy stays as it is").clicked() { open = Some(b.path.clone()); }
                            if has_doc && ui.small_button("Compare with the open file").on_hover_text("Open this copy as file B in Compare, beside the file you have open").clicked() { compare = Some(b.path.clone()); }
                        });
                        ui.end_row();
                    }
                });
            });
        });
        if !shown { self.show_backups = false; }
        if refresh { self.backups = Self::list_backups(); }
        if let Some(p) = open { self.open(p); }
        if let Some(p) = compare { self.open_compare(p); self.show_backups = false; }
    }

    /// The undo history: every edit of the session with its before and after, each revertable.
    pub(crate) fn history_window(&mut self, ctx: &egui::Context) {
        if !self.show_history { return; }
        let mut open = true;
        let mut actions = Vec::new();
        egui::Window::new("Edit history").open(&mut open).resizable(true).default_width(640.0).show(ctx, |ui| {
            let Some(doc) = &self.doc else { ui.label("No file open."); return; };
            if self.undo.is_empty() {
                ui.label("No edits yet in this session.");
                return;
            }
            ui.label(RichText::new("Oldest first. Revert puts one setting back to what it was before that edit; Undo and Redo in the top bar step through the whole list.").small().color(tone::weak(ui.visuals())));
            ui.add_space(4.0);
            // snapshot i is the file before edit i; the file after edit i is snapshot i+1 (or the current file)
            egui::ScrollArea::vertical().max_height(420.0).show(ui, |ui| {
                egui::Grid::new("history").striped(true).num_columns(5).spacing([16.0, 4.0]).show(ui, |ui| {
                    ui.strong("#"); ui.strong("Setting"); ui.strong("Before"); ui.strong("After"); ui.label(""); ui.end_row();
                    for i in 0..self.undo.len() {
                        let before = &self.undo[i];
                        for line in self.history_lines(i, &doc.edited).iter() {
                            ui.label((i + 1).to_string());
                            ui.label(&line.name);
                            ui.label(&line.before);
                            ui.label(RichText::new(&line.after).color(tone::edit(ui.visuals())));
                            if ui.add_enabled(self.editable(), egui::Button::new("Revert").small()).on_hover_text("Put this record back to its value before this edit").on_disabled_hover_text("View only: this file cannot be edited, so nothing is reverted.").clicked() {
                                if let Some(r) = before.sections.get(line.si).and_then(|sec| sec.get(line.id)) { actions.push(Action::SetRecord(line.si, r.clone())); }
                            }
                            ui.end_row();
                        }
                    }
                });
            });
        });
        if !open { self.show_history = false; }
        self.apply(actions);
    }

    /// The History window's lines for undo step `i` (`current`: the file as edited now): every record the step
    /// changed, named, with its value before and after. Worked out once per step and kept (`HistKey`).
    fn history_lines(&self, i: usize, current: &CamSet) -> std::rc::Rc<Vec<HistRow>> {
        let before = &self.undo[i];
        let after: &CamSet = if i + 1 < self.undo.len() { &self.undo[i + 1] } else { current };
        // the last step's "after" is the file as edited now, which a drag joined to that step changes in place (the same
        // records, the same number of steps): its state (`Doc::rev`) tells one value from the next
        let now = if i + 1 < self.undo.len() { 0 } else { self.doc.as_ref().map_or(0, |d| d.rev) };
        // the raw numbers beside the names (`show_raw`) change the lines too
        let key: HistKey = (before.sections.as_ptr() as usize, after.sections.as_ptr() as usize, self.undo.len(), now, self.show_raw);
        let mut cache = self.history_cache.borrow_mut();
        cache.truncate(self.undo.len());
        if let Some((k, lines)) = cache.get(i) {
            if *k == key { return lines.clone(); }
        }
        let lines: Vec<HistRow> = self.record_diff(before, after).into_iter().map(|(si, id, name)| {
            let s = self.schema.find(si != 0, id);
            let fmt = |c: &CamSet| c.sections.get(si).and_then(|sec| sec.get(id)).map(|r| {
                let raw = r.display_value();
                s.and_then(|s| raw.parse::<i64>().ok().and_then(|v| s.label_for(v).map(|l| if self.show_raw { format!("{l} [{v}]") } else { l.to_string() }))).unwrap_or(raw)
            }).unwrap_or_default();
            let name = if name == "(unmapped)" { self.unnamed(id) } else { name };
            let name = format!("{}{name}", if si == 0 { String::new() } else { format!("{} · ", self.schema.camera.target_name(si)) });
            HistRow { si, id, name, before: fmt(before), after: fmt(after) }
        }).collect();
        let lines = std::rc::Rc::new(lines);
        if cache.len() <= i { cache.resize_with(i + 1, || ((0, 0, 0, 0, false), Default::default())); }
        cache[i] = (key, lines.clone());
        lines
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A value dragged over several frames is one undo step (`apply` joins the frames); the History window's line for
    /// that step follows the drag to its last value, not the value of its first frame.
    #[test]
    fn the_last_step_follows_a_drag() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let cur = |app: &App, s: &Setting| app.col_value(Col::a(0), s);
        let s = app.schema.settings.iter()
            .filter(|s| s.area == "global" && s.scalar && s.index.is_none() && s.text.is_none() && app.shape_ok_in(s, 0))
            .find(|s| s.values.iter().filter(|(v, _)| Some(*v) != cur(&app, s) && s.acceptance(*v).is_none()).count() >= 2)
            .expect("a setting with two other accepted values").clone();
        let was = cur(&app, &s);
        let others: Vec<i64> = s.values.iter().map(|(v, _)| *v).filter(|v| Some(*v) != was && s.acceptance(*v).is_none()).collect();
        let shown = |app: &App| {
            let doc = app.doc.as_ref().unwrap();
            app.history_lines(0, &doc.edited).iter().map(|l| l.after.clone()).collect::<Vec<_>>()
        };
        app.apply(vec![Action::Set(0, s.slot(), others[0])]);
        let first = shown(&app);
        // the next frame of the drag: the same slot at once, joined to the step
        app.apply(vec![Action::Set(0, s.slot(), others[1])]);
        assert_eq!(app.undo.len(), 1, "one step for the whole drag");
        let second = shown(&app);
        app.history_cache.borrow_mut().clear();
        assert_eq!(second, shown(&app), "the lines as worked out afresh");
        assert_ne!(first, second, "the drag's last value, not its first");
        // the raw numbers turned on: the lines carry them at once, not after the next edit
        app.show_raw = true;
        assert!(shown(&app).iter().all(|l| l.ends_with(']')), "{:?}", shown(&app));
    }
}
