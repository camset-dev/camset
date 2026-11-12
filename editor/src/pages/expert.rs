//! The pages for mapping work (Expert mode): the records without a name yet, the record map, and All edits.

use crate::*;

/// A record of the set shown, as the Record map and the Unmapped page list it, worked out once per state of the
/// file (`RecordsKey`): where it starts, its shape, the setting it holds (an index into the definition's settings),
/// its value in words and raw, and whether it was edited.
pub(crate) struct RecordRow {
    pub(crate) offset: usize,
    pub(crate) id: u16,
    pub(crate) shape: String,
    pub(crate) big: bool,
    pub(crate) setting: Option<usize>,
    pub(crate) value: String,
    pub(crate) raw: String,
    pub(crate) int: Option<i64>,
    pub(crate) edited: bool,
}

/// What the Expert pages' rows were worked out from: the file's state (`Doc::rev`), the set shown and the definition
/// (its generation).
pub(crate) type RecordsKey = (u64, usize, u64);

/// The fields the definition knows inside array records, by record: (byte offset, name, index).
type RecordFields = BTreeMap<u16, Vec<(u16, String, u16)>>;

/// The fields of a definition (its generation) for the live settings or the memory sets.
pub(crate) type FieldsEntry = ((u64, bool), std::rc::Rc<RecordFields>);

/// Each record's setting, by (memory set or not, record number): its index in the definition's settings.
pub(crate) type SettingIndex = std::collections::HashMap<(bool, u16), usize>;

impl App {
    /// A setting the definition has no name for: in words, with its record number in Expert mode.
    pub(crate) fn unnamed(&self, id: u16) -> String {
        if self.prefs.expert { format!("record 0x{id:04x}") } else { "a setting without a name yet (Expert mode shows it)".into() }
    }

    pub(crate) fn changes_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let mut actions = Vec::new();
        let Some(doc) = &self.doc else {
            ui.label("No file open.");
            return actions;
        };
        let changes = doc.changes();
        if changes.is_empty() {
            ui.label("No edits yet.");
            return actions;
        }
        egui::Grid::new("changes").striped(true).num_columns(5).spacing([18.0, 6.0]).show(ui, |ui| {
            ui.strong("Where");
            ui.strong("Setting");
            ui.strong("Was");
            ui.strong("Now");
            ui.label("");
            ui.end_row();
            for (si, id) in changes {
                let s = self.schema.find(si != 0, id);
                let name = s.map(|s| s.name.clone()).unwrap_or_else(|| self.unnamed(id));
                let was = doc.original.sections[si].get(id).map(|r| r.display_value()).unwrap_or_default();
                let now = doc.edited.sections[si].get(id).map(|r| r.display_value()).unwrap_or_default();
                let fmt = |raw: &String| s.and_then(|s| raw.parse::<i64>().ok().and_then(|v| s.label_for(v).map(|l| if self.show_raw { format!("{l} [{v}]") } else { l.to_string() }))).unwrap_or(raw.clone());
                ui.label(self.schema.camera.target_name(si));
                ui.label(name);
                ui.label(fmt(&was));
                ui.label(RichText::new(fmt(&now)).color(tone::edit(ui.visuals())));
                if ui.small_button("Revert").clicked() {
                    actions.push(Action::Revert(si, (id, None)));
                }
                ui.end_row();
            }
        });
        actions
    }

    /// The index (into the definition's settings) of the setting a record holds, as `Schema::find` finds it: in a
    /// memory set (`in_set`) one kept in the sets only first, else one the sets keep; in the live settings a live
    /// one. Looked up in a map made once per definition.
    fn setting_index_of(&self, in_set: bool, id: u16) -> Option<usize> {
        let generation = self.schema_gen;
        let mut cache = self.setting_index.borrow_mut();
        if cache.as_ref().map(|c| c.0) != Some(generation) {
            let mut m = std::collections::HashMap::new();
            let settings = || self.schema.settings.iter().enumerate();
            for (i, s) in settings().filter(|(_, s)| s.area == "global") { m.entry((false, s.id)).or_insert(i); }
            for (i, s) in settings().filter(|(_, s)| s.area == "set") { m.entry((true, s.id)).or_insert(i); }
            for (i, s) in settings().filter(|(_, s)| s.in_sets) { m.entry((true, s.id)).or_insert(i); }
            *cache = Some((generation, m));
        }
        cache.as_ref().and_then(|(_, m)| m.get(&(in_set, id)).copied())
    }

    /// The setting a record holds (`setting_index_of`), borrowed.
    pub(crate) fn setting_at(&self, in_set: bool, id: u16) -> Option<&Setting> {
        self.setting_index_of(in_set, id).and_then(|i| self.schema.settings.get(i))
    }

    /// The records of the set shown, as the Expert pages list them, worked out once per state of the file.
    pub(crate) fn record_rows(&self) -> std::rc::Rc<Vec<RecordRow>> {
        let Some(doc) = &self.doc else { return Default::default() };
        let key = (doc.rev, self.target, self.schema_gen);
        if let Some((k, rows)) = self.records_cache.borrow().as_ref() {
            if *k == key { return rows.clone(); }
        }
        let in_set = self.target != 0;
        let offsets = doc.edited.record_offsets(self.target);
        let orig = doc.original.sections.get(self.target);
        let rows: Vec<RecordRow> = doc.edited.sections.get(self.target).map(|sec| sec.records.iter().enumerate().map(|(ri, r)| {
            let setting = self.setting_index_of(in_set, r.id);
            let value = match setting.and_then(|i| self.schema.settings.get(i)) {
                Some(s) if s.text.is_some() => r.text().unwrap_or_default(),
                Some(s) if s.scalar => Self::describe(s, r.as_int()),
                Some(_) => r.display_value(),
                None => String::new(),
            };
            RecordRow {
                offset: offsets.get(ri).copied().unwrap_or_default(), id: r.id, shape: format!("{}×{}", r.elem_size, r.count),
                big: r.value.len() > 8, setting, value, raw: r.display_value(), int: r.as_int(),
                edited: orig.and_then(|o| o.get(r.id)).is_some_and(|o| o.value != r.value),
            }
        }).collect()).unwrap_or_default();
        let rows = std::rc::Rc::new(rows);
        *self.records_cache.borrow_mut() = Some((key, rows.clone()));
        rows
    }

    /// The fields the definition knows inside array records (16-bit fields at byte offsets), for the live settings
    /// or the memory sets (`in_set`), worked out once per definition.
    fn record_fields(&self, in_set: bool) -> std::rc::Rc<RecordFields> {
        let key = (self.schema_gen, in_set);
        if let Some((k, f)) = self.fields_cache.borrow().as_ref() {
            if *k == key { return f.clone(); }
        }
        let mut fields = RecordFields::new();
        for s in &self.schema.settings {
            if let Some(ix) = s.index.filter(|ix| ix & camset_editor::camset::FIELD != 0) {
                if (in_set && s.in_sets) || (!in_set && s.area == "global") {
                    fields.entry(s.id).or_default().push((ix & !camset_editor::camset::FIELD, s.name.clone(), ix));
                }
            }
        }
        let fields = std::rc::Rc::new(fields);
        *self.fields_cache.borrow_mut() = Some((key, fields.clone()));
        fields
    }

    /// How many edited values the camera may not take (`acceptance_issues`), worked out once per state of the file.
    pub(crate) fn issue_count(&self) -> usize {
        let Some(doc) = &self.doc else { return 0 };
        let key = (doc.rev, self.schema_gen);
        match self.issues_count.get() {
            Some((k, n)) if k == key => n,
            _ => {
                let n = self.acceptance_issues().len();
                self.issues_count.set(Some((key, n)));
                n
            }
        }
    }

    pub(crate) fn unmapped_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let mut actions = Vec::new();
        ui.horizontal(|ui| {
            if ui.checkbox(&mut self.allow_raw_edits, "Allow raw edits").changed() {
                self.prefs.allow_raw_edits = self.allow_raw_edits;
                self.prefs.save();
            }
            ui.label(RichText::new("Raw values have unknown meaning. The camera may reject or misread them; test edited files one change at a time.").color(tone::caution(ui.visuals())));
        });
        ui.separator();
        if self.doc.is_none() { return actions };
        let rows = self.record_rows();
        let q = self.search.to_lowercase();
        let editable = self.editable() && self.allow_raw_edits;
        egui::Grid::new("unmapped").striped(true).num_columns(3).spacing([18.0, 4.0]).show(ui, |ui| {
            ui.strong("Record");
            ui.strong("Shape");
            ui.strong("Value");
            ui.end_row();
            for r in rows.iter().filter(|r| r.setting.is_none()) {
                let id = format!("0x{:04x}", r.id);
                if !q.is_empty() && !id.contains(&q) {
                    continue;
                }
                if self.only_changed && !r.edited {
                    continue;
                }
                ui.label(RichText::new(&id).monospace());
                ui.label(&r.shape);
                if let (true, Some(mut v)) = (editable, r.int) {
                    if named(ui.add(egui::DragValue::new(&mut v)), &format!("Record {id}")).changed() {
                        actions.push(Action::Set(self.target, (r.id, None), v));
                    }
                } else {
                    let t = RichText::new(&r.raw).monospace();
                    ui.label(if r.edited { t.color(tone::edit(ui.visuals())) } else { t });
                }
                ui.end_row();
            }
        });
        actions
    }

    /// The record map: every record of the section being edited, in file order, with its byte offset,
    /// shape, the setting it belongs to (if any) and its value. Unmapped records are highlighted so
    /// they can be read in the context of their mapped neighbours.
    pub(crate) fn records_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let actions = Vec::new();
        if self.doc.is_none() {
            ui.label("No file open.");
            return actions;
        }
        let in_set = self.target != 0;
        let only_unmapped = ui.data(|d| d.get_temp::<bool>(egui::Id::new("rm_unmapped"))).unwrap_or(false);
        let only_interesting = ui.data(|d| d.get_temp::<bool>(egui::Id::new("rm_interesting"))).unwrap_or(false);
        let mut expanded: std::collections::HashSet<u16> = ui.data(|d| d.get_temp(egui::Id::new("rm_expanded"))).unwrap_or_default();
        let (mut u, mut i) = (only_unmapped, only_interesting);
        ui.horizontal(|ui| {
            ui.label(RichText::new(format!("{}: records in file order", self.schema.camera.target_name(self.target))).strong());
            ui.separator();
            ui.checkbox(&mut u, "Only unmapped");
            ui.checkbox(&mut i, "Only edited").on_hover_text("Records whose value differs from the file as it was opened");
            ui.label(RichText::new("Search matches record ids (0x1234), setting names and values. Click a setting to open it; click the shape of a multi-byte record for its bytes.").small().color(tone::weak(ui.visuals())));
        });
        ui.data_mut(|d| { d.insert_temp(egui::Id::new("rm_unmapped"), u); d.insert_temp(egui::Id::new("rm_interesting"), i); });
        // fields the schema knows inside array records, and the records as listed: worked out once, not per frame
        let fields = self.record_fields(in_set);
        let rows = self.record_rows();
        ui.separator();
        let section = self.doc.as_ref().and_then(|d| d.edited.sections.get(self.target));
        let q = self.search.to_lowercase();
        let mut jump: Option<Setting> = None;
        let mut shown = 0;
        egui::Grid::new(("record_map", self.target)).striped(true).num_columns(6).spacing([16.0, 3.0]).show(ui, |ui| {
            ui.strong("Offset");
            ui.strong("Record");
            ui.strong("Shape");
            ui.strong("Setting");
            ui.strong("Value");
            ui.strong("Raw");
            ui.end_row();
            for row in rows.iter() {
                let setting = row.setting.and_then(|i| self.schema.settings.get(i));
                let id = format!("0x{:04x}", row.id);
                if u && setting.is_some() { continue; }
                if i && !row.edited { continue; }
                if !q.is_empty() && !id.contains(&q) && !setting.is_some_and(|s| s.name.to_lowercase().contains(&q) || s.group.to_lowercase().contains(&q)) && !row.value.to_lowercase().contains(&q) {
                    continue;
                }
                shown += 1;
                let color = if row.edited { Some(tone::edit(ui.visuals())) } else if setting.is_none() { Some(tone::unnamed(ui.visuals())) } else { None };
                let paint = |t: String| { let t = RichText::new(t).monospace(); if let Some(c) = color { t.color(c) } else { t } };
                ui.label(paint(format!("{:06x}", row.offset)));
                ui.label(paint(id));
                let big = row.big;
                let shape = ui.add(egui::Label::new(paint(format!("{}{}", row.shape, if big { if expanded.contains(&row.id) { " ▾" } else { " ▸" } } else { "" }))).sense(if big { egui::Sense::click() } else { egui::Sense::hover() }));
                if big && shape.on_hover_text("Click to show the bytes").clicked() && !expanded.remove(&row.id) {
                    expanded.insert(row.id);
                }
                match setting {
                    Some(s) => {
                        let title = match fields.get(&row.id) { Some(fs) if fs.len() > 1 => format!("{} known fields ({}, …)", fs.len(), s.name), _ => s.name.clone() };
                        let text = RichText::new(title);
                        let text = if let Some(c) = color { text.color(c) } else { text };
                        if ui.add(egui::Label::new(text).sense(egui::Sense::click())).on_hover_text(format!("{} > {}\n{}", s.tab, s.group, s.note_shown(self.prefs.expert)).trim_end().to_string()).clicked() {
                            jump = Some(s.clone());
                        }
                    }
                    None => { ui.label(RichText::new("— unmapped —").color(tone::unnamed(ui.visuals()))); }
                }
                // the bytes of a record shown open, from the file as it is now
                let r = section.and_then(|sec| sec.get(row.id)).filter(|_| big && expanded.contains(&row.id));
                if let Some(r) = r {
                    // byte dump with the known fields marked, in the value column
                    let mut dump = String::new();
                    for (n, chunk) in r.value.chunks(16).enumerate() {
                        let hex: Vec<String> = chunk.iter().map(|b| format!("{b:02x}")).collect();
                        let asc: String = chunk.iter().map(|&b| if (32..127).contains(&b) { b as char } else { '.' }).collect();
                        dump += &format!("{:04x}  {:<47}  {}\n", n * 16, hex.join(" "), asc);
                    }
                    if let Some(fs) = fields.get(&r.id) {
                        dump += "fields:\n";
                        let mut fs = fs.clone(); fs.sort();
                        for (off, name, ix) in fs {
                            let v = r.get(Some(ix)).map(|v| v.to_string()).unwrap_or_default();
                            dump += &format!("  @{off:<4} {name} = {v}\n");
                        }
                    }
                    ui.label(RichText::new(dump.trim_end().to_string()).monospace().small());
                } else {
                    ui.label(paint(row.value.clone()));
                }
                let raw = &row.raw;
                let raw_short: String = if raw.chars().count() > 24 { format!("{}…", raw.chars().take(24).collect::<String>()) } else { raw.clone() };
                ui.label(paint(raw_short)).on_hover_text(raw);
                ui.end_row();
            }
        });
        if shown == 0 {
            ui.label("No records match.");
        }
        ui.data_mut(|d| d.insert_temp(egui::Id::new("rm_expanded"), expanded));
        if let Some(s) = jump {
            self.view = self.view_of(&s);
            self.group = Some(self.shown_group_of(&s));
            self.item = Some(s.name.clone());
            self.focus = Focus::Items;
        }
        actions
    }
}
