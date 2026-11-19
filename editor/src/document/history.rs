//! The Backups window (every copy the editor keeps) and the Edit history window.

use crate::*;

/// A copy the editor keeps (the Backups window).
pub(crate) struct Backup {
    pub(crate) when: String,
    pub(crate) kind: &'static str,
    /// The folder it is in, "originals" or "camera" (`originals_dir`, `camera_dir`): a file name is the copy's own
    /// within its folder only.
    pub(crate) folder: &'static str,
    pub(crate) path: PathBuf,
}

/// One changed setting between two states of a file (`App::edit_lines`), as every list of edits shows it (Edit history,
/// All edits, the Write window's summary, the window's and the page's): its set, the record it is about first, the
/// setting (its key, the first of its records; None for bytes no setting covers), the places it covers (the setting's
/// slot and those of its other records that changed with it, `Setting::twin_of`; the whole record for bytes no setting
/// covers), its name as a list names it (`setting_words`) and its value before and after in its own words.
#[derive(Clone, Debug)]
pub(crate) struct EditLine {
    pub(crate) si: usize,
    pub(crate) id: u16,
    pub(crate) key: Option<String>,
    pub(crate) slots: Vec<Slot>,
    pub(crate) name: String,
    pub(crate) before: String,
    pub(crate) after: String,
}

impl EditLine {
    /// The actions that put this line's places back as `from` holds them, the rest of their records as `current` holds
    /// them: what a History step's Revert does for one setting (whole records replaced, so a setting view only now
    /// still goes back), never to another setting kept in the same record.
    pub(crate) fn put_back(&self, from: &CamSet, current: &CamSet) -> Vec<Action> {
        let mut recs: Vec<camset_editor::camset::Record> = Vec::new();
        for &(id, index) in &self.slots {
            let Some(old) = from.sections.get(self.si).and_then(|s| s.get(id)) else { continue };
            let at = match recs.iter().position(|r| r.id == id) {
                Some(at) => at,
                None => {
                    let Some(now) = current.sections.get(self.si).and_then(|s| s.get(id)) else { continue };
                    recs.push(now.clone());
                    recs.len() - 1
                }
            };
            let r = &mut recs[at];
            match index.and_then(|i| old.get(Some(i)).map(|v| (i, v))) {
                Some((i, v)) if r.elem_size == old.elem_size && r.count == old.count => { let _ = r.put(Some(i), v); }
                _ => *r = old.clone(),
            }
        }
        recs.into_iter().map(|r| Action::SetRecord(self.si, r)).collect()
    }
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
        for (dir, folder) in [(Self::originals_dir(), "originals"), (Self::camera_dir(), "camera")] {
            let camera = folder == "camera";
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
                v.push((modified, Backup { when: modified.map(|t| when_words(&stamp_of(t))).unwrap_or_default(), kind, folder, path }));
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
                            if ui.add_enabled(self.editable(), egui::Button::new("Revert").small()).on_hover_text("Put this setting back to its value before this edit; later edits stay").on_disabled_hover_text("View only: this file cannot be edited, so nothing is reverted.").clicked() {
                                actions.extend(line.put_back(before, &doc.edited));
                            }
                            ui.end_row();
                        }
                    }
                });
            });
        });
        if !open { self.show_history = false; }
        self.history_revert(actions);
    }

    /// The History window's Reverts (each a record put back as it was before its edit), made as any edit is; one that
    /// changes a switch keeping copies apart waits for the question's answer first (`hold_untick`, `untick_window`).
    pub(crate) fn history_revert(&mut self, actions: Vec<Action>) {
        let actions = self.hold_untick(actions);
        self.apply(actions);
    }

    /// The History window's lines for undo step `i` (`current`: the file as edited now): every setting the step
    /// changed (`edit_lines`), with its value before and after, a memory set's named before it. Worked out once per step
    /// and kept (`HistKey`).
    fn history_lines(&self, i: usize, current: &CamSet) -> std::rc::Rc<Vec<EditLine>> {
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
        let lines: Vec<EditLine> = self.edit_lines(before, after).into_iter().map(|mut l| {
            l.name = self.placed_name(l.si, &l.name);
            l
        }).collect();
        let lines = std::rc::Rc::new(lines);
        if cache.len() <= i { cache.resize_with(i + 1, || ((0, 0, 0, 0, false), Default::default())); }
        cache[i] = (key, lines.clone());
        lines
    }

    /// A line's name with its memory set before it ("Memory 1 · Black Level"), as the History window, the page's and
    /// the Write window's summary name a setting of a memory; the live settings' alone.
    pub(crate) fn placed_name(&self, si: usize, name: &str) -> String {
        if si == 0 { name.to_string() } else { format!("{} · {name}", self.schema.camera.target_name(si)) }
    }

    /// A setting's name where a list names it away from its group (`EditLine`): its family's column before it, as the
    /// family's table names its cells ("PP3 Black Level"); where another setting of the same sets would read the same
    /// and is not one with it (`Setting::twin_of`), its group after it ("Shutter Speed (Recall Custom hold 1)"), or for
    /// a copy beside its setting in one group, "(copy)"; else its name.
    pub(crate) fn setting_words(&self, s: &Setting) -> String {
        let short = |o: &Setting| match self.family_of(std::slice::from_ref(o)) {
            Some(f) => format!("{} {}", f.column_title(&o.group), o.name),
            None => o.name.clone(),
        };
        let mine = short(s);
        let others: Vec<&Setting> = self.schema.settings.iter().filter(|o| o.key != s.key && o.name == s.name && o.area == s.area && !s.twin_of(o) && short(o) == mine).collect();
        if others.is_empty() {
            mine
        } else if s.copy_of.is_some() && others.iter().all(|o| o.group == s.group) {
            format!("{mine} (copy)")
        } else {
            format!("{mine} ({})", s.group)
        }
    }

    /// A setting's value in record `r` in its own words (`describe`; a text as typed), with the number it is stored as
    /// beside its words when the raw numbers are shown (`show_raw`); a record the editor does not read value by value as
    /// its bytes. Nothing where the record is missing.
    fn edit_words(&self, s: Option<&Setting>, r: Option<&camset_editor::camset::Record>) -> String {
        let Some(r) = r else { return String::new() };
        match s {
            Some(s) if s.text.is_some() => r.text().unwrap_or_else(|| r.display_value()),
            Some(s) if s.scalar => match r.get(s.index) {
                Some(v) => {
                    let w = Self::describe(s, Some(v));
                    if self.show_raw && w != v.to_string() { format!("{w} [{v}]") } else { w }
                }
                None => r.display_value(),
            },
            _ => r.display_value(),
        }
    }

    /// Every setting whose value differs between two states of a file, `before` and `after` (header left out), as
    /// every list of edits shows it (`EditLine`): one line per setting, element by element in a record that holds
    /// several, one setting's records together (`Setting::twin_of`), named as a list names it (`setting_words`); bytes
    /// no setting covers a line of their own, by their record. In record order, set by set.
    pub(crate) fn edit_lines(&self, before: &CamSet, after: &CamSet) -> Vec<EditLine> {
        let st = &self.schema.settings;
        let mut by_id: std::collections::HashMap<u16, Vec<usize>> = Default::default();
        for (i, s) in st.iter().enumerate() {
            by_id.entry(s.id).or_default().push(i);
        }
        let mut out = Vec::new();
        let mut folded: std::collections::HashSet<(usize, Slot)> = Default::default();
        for (si, (x, y)) in before.sections.iter().zip(&after.sections).enumerate() {
            for r in &x.records {
                let o = y.get(r.id);
                if o.is_some_and(|o| o.value == r.value && o.elem_size == r.elem_size && o.count == r.count) {
                    continue;
                }
                // the settings this set keeps here, one line per place: in a memory set one of the sets' own first, as
                // `Schema::find` names a record
                let mut here: Vec<&Setting> = by_id.get(&r.id).into_iter().flatten().map(|&i| &st[i]).filter(|s| kept_in(s, si)).collect();
                if si != 0 {
                    here.sort_by_key(|s| s.area != "set");
                }
                let record_line = |s: Option<&Setting>| EditLine { si, id: r.id, key: None, slots: vec![(r.id, None)],
                    name: s.map_or_else(|| self.unnamed(r.id), |s| self.setting_words(s)), before: r.display_value(), after: o.map(|o| o.display_value()).unwrap_or_default() };
                let Some(o) = o.filter(|o| o.elem_size == r.elem_size && o.count == r.count) else {
                    // a record of another shape, or gone: a line of its own, by its setting's name where it has one
                    out.push(record_line(here.first().copied()));
                    continue;
                };
                let differ: Vec<usize> = (0..r.value.len()).filter(|&k| r.value[k] != o.value[k]).collect();
                let mut covered = vec![false; r.value.len()];
                let mut places = std::collections::HashSet::new();
                for s in here {
                    let elem = r.elem_size as usize;
                    let (a, b) = match s.index {
                        None => (0, r.value.len()),
                        Some(i) if i & camset::FIELD != 0 => { let at = (i & !camset::FIELD) as usize; (at, at + 2) }
                        Some(i) => (i as usize * elem, (i as usize + 1) * elem),
                    };
                    for c in covered.iter_mut().take(b).skip(a) {
                        *c = true;
                    }
                    if !places.insert(s.slot()) || folded.contains(&(si, s.slot())) || !differ.iter().any(|&k| k >= a && k < b) {
                        continue;
                    }
                    // the setting's other records that changed too: one line
                    let mut slots = vec![s.slot()];
                    for t in st.iter().filter(|t| t.name == s.name && kept_in(t, si) && s.twin_of(t)) {
                        let value = |c: &CamSet| c.sections.get(si).and_then(|x| x.get(t.id)).and_then(|q| q.get(t.index));
                        if value(before) != value(after) && folded.insert((si, t.slot())) {
                            slots.push(t.slot());
                        }
                    }
                    out.push(EditLine { si, id: r.id, key: Some(s.key.clone()), slots, name: self.setting_words(s), before: self.edit_words(Some(s), Some(r)), after: self.edit_words(Some(s), Some(o)) });
                }
                if differ.iter().any(|&k| !covered[k]) {
                    out.push(record_line(None));
                }
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Two settings kept in one record (PP1's and PP3's Black Level, elements of 0x04e9, each with its stills and movie
    /// copies): every list of edits names each setting by its own name with its value in words, never the record by
    /// its first setting with its array, in the window and on the page; History's Revert of the first edit puts PP1's
    /// back and leaves PP3's, as does All edits' Revert of one line.
    #[test]
    fn edit_lists_name_settings_and_revert_one_alone() {
        use crate::web::tests::answer;
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let get = |app: &App, k: &str| app.schema.settings.iter().find(|s| s.key == k).cloned().unwrap();
        let (pp1, pp3) = (get(&app, "global:0x04e9[0]"), get(&app, "global:0x04e9[2]"));
        let v = |app: &App, s: &Setting| app.doc.as_ref().unwrap().value(0, s.slot()).unwrap();
        let (a0, c0) = (v(&app, &pp1), v(&app, &pp3));
        let (a1, c1) = (if a0 < 15 { a0 + 1 } else { a0 - 1 }, if c0 < 15 { c0 + 1 } else { c0 - 1 });
        app.apply(vec![Action::Set(0, pp1.slot(), a1)]);
        app.last_edit = None;
        app.apply(vec![Action::Set(0, pp3.slot(), c1)]);
        assert_eq!(app.undo.len(), 2);
        let names = |lines: &[EditLine]| lines.iter().map(|l| l.name.clone()).collect::<Vec<_>>();
        let doc = app.doc.as_ref().unwrap();
        let (one, two) = (app.history_lines(0, &doc.edited), app.history_lines(1, &doc.edited));
        assert_eq!(names(&one), ["PP1 Black Level", "PP1 Black Level (stills)", "PP1 Black Level (movie)"]);
        assert_eq!(names(&two), ["PP3 Black Level", "PP3 Black Level (stills)", "PP3 Black Level (movie)"]);
        assert_eq!((one[0].before.as_str(), one[0].after.clone()), (a0.to_string().as_str(), a1.to_string()), "the value in words, not the record's array");
        // the Write window's summary and All edits, setting by setting too
        let all = app.edit_lines(&doc.original, &doc.edited);
        assert_eq!(names(&all), ["PP1 Black Level", "PP3 Black Level", "PP1 Black Level (stills)", "PP3 Black Level (stills)", "PP1 Black Level (movie)", "PP3 Black Level (movie)"]);
        app.last_camera = Some((String::new(), doc.original.clone()));
        let summary: Vec<String> = app.send_summary().into_iter().map(|(t, _)| t).collect();
        assert!(summary.iter().any(|t| t.contains("this changes 6 settings")) && summary.iter().any(|t| t.trim() == format!("PP3 Black Level: {c0} ➡ {c1}")), "{summary:?}");
        // the page's lists
        let body = |b: &[u8]| serde_json::from_slice::<serde_json::Value>(b).unwrap();
        let h = body(&answer(&mut app, "history", serde_json::json!({})).body);
        let page: Vec<(u64, String)> = h["steps"].as_array().unwrap().iter().map(|x| (x["step"].as_u64().unwrap(), x["name"].as_str().unwrap().to_string())).collect();
        assert_eq!(page[0], (0, "PP1 Black Level".to_string()));
        assert_eq!(page[3], (1, "PP3 Black Level".to_string()));
        let c = body(&answer(&mut app, "changes", serde_json::json!({})).body);
        assert_eq!(c["changes"][1]["name"], "PP3 Black Level");
        assert_eq!(c["changes"][1]["key"], pp3.key.as_str());
        // History's Revert of step 1, PP1's line: PP1 and its copies back, PP3's edit stays
        let doc = app.doc.as_ref().unwrap();
        let acts = one[0].put_back(&app.undo[0], &doc.edited);
        app.history_revert(acts);
        assert_eq!((v(&app, &pp1), v(&app, &pp3)), (a0, c1), "PP3's edit stays");
        let doc = app.doc.as_ref().unwrap();
        assert_eq!(names(&app.edit_lines(&doc.original, &doc.edited)), ["PP3 Black Level", "PP3 Black Level (stills)", "PP3 Black Level (movie)"], "PP1's copies went back with it");
        app.undo();
        // the page's History Revert, by the line's key
        let r = answer(&mut app, "revert_history", serde_json::json!({ "step": 0, "section": 0, "id": pp1.id, "key": pp1.key }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!((v(&app, &pp1), v(&app, &pp3)), (a0, c1));
        app.undo();
        // All edits' Revert of PP3's line, in the window (its places' Reverts) and on the page (its key)
        let doc = app.doc.as_ref().unwrap();
        let line = app.edit_lines(&doc.original, &doc.edited).into_iter().find(|l| l.key.as_deref() == Some(pp3.key.as_str())).unwrap();
        app.apply(line.slots.iter().map(|&slot| Action::Revert(0, slot)).collect());
        assert_eq!((v(&app, &pp1), v(&app, &pp3)), (a1, c0), "PP1's edit stays");
        app.undo();
        assert_eq!(answer(&mut app, "revert", serde_json::json!({ "target": 0, "key": pp3.key })).status, 200);
        assert_eq!((v(&app, &pp1), v(&app, &pp3)), (a1, c0));
    }

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
