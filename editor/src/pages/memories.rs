//! The Memories page: the mode dial's memories beside the live settings, with recall and register.

use crate::*;

impl App {
    /// Heading of the memories page, e.g. "Memories 1, 2, 3": the definition's words (`text.memories_title`), "{list}"
    /// standing for the dial's memories.
    pub(crate) fn memories_title(&self) -> String {
        let list = self.dial_sets().iter().map(|m| m.to_string()).collect::<Vec<_>>().join(", ");
        let title = self.schema.camera.text.memories_title.as_deref().filter(|t| !t.is_empty()).unwrap_or("Memories {list}");
        title.replace("{list}", &list)
    }

    /// What the memories page says the memories are (`text.memories_intro`).
    pub(crate) fn memories_intro(&self) -> String {
        self.schema.camera.text.memories_intro.clone().filter(|t| !t.is_empty())
            .unwrap_or_else(|| "The camera's memories. Each holds a copy of the shooting settings registered into it.".into())
    }

    /// What the Memories page says under its heading, in the window and on the web page: the definition's words, and
    /// how a difference and an edit are shown.
    pub(crate) fn memories_lead(&self) -> String {
        format!("{} Values that differ from the live settings are shaded; your edits are orange with a pencil.", self.memories_intro())
    }

    /// Memories 1-3 beside the live settings: what each holds, recall and register.
    pub(crate) fn memories_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let mut actions = Vec::new();
        if self.doc.is_none() {
            ui.label("Open a settings file to see its memories.");
            return actions;
        }
        let dial = self.dial_sets();
        if dial.is_empty() {
            ui.label("This camera has no mode-dial memories Camset knows of.");
            return actions;
        }
        let editable = self.editable();
        ui.heading(self.memories_title());
        ui.label(RichText::new(self.memories_lead()).small().color(tone::weak(ui.visuals())));
        ui.add_space(6.0);
        // the search and "Only rows that differ" narrow the rows shown; Recall and Register always copy every setting
        // the memories keep
        let all = self.matrix_rows_shared(&self.search, None);
        let kept: Vec<&(String, String, Vec<Setting>)> = all.iter().filter(|r| r.2[0].in_sets).collect();
        let every = self.whole_set_note(!self.search.trim().is_empty());
        ui.horizontal_wrapped(|ui| {
            ui.label(RichText::new("Whole sets:").strong());
            for &m in &dial {
                let (label, hover, said) = self.recall_words(m, &every, "");
                if ui.add_enabled(editable, egui::Button::new(label)).on_hover_text(hover).clicked() {
                    for r in &self.memory_rows() { actions.extend(self.copy_row(&r.2, Col::a(m), Col::a(0))); }
                    self.pin_families(Some(m), 0, &mut actions);
                    self.status = said;
                }
                let (label, hover, said) = self.register_words(m, &every, "");
                if ui.add_enabled(editable, egui::Button::new(label)).on_hover_text(hover).clicked() {
                    for r in &self.memory_rows() { actions.extend(self.copy_row(&r.2, Col::a(0), Col::a(m))); }
                    self.pin_families(Some(0), m, &mut actions);
                    self.status = said;
                }
                ui.separator();
            }
        });
        ui.horizontal_wrapped(|ui| {
            if ui.checkbox(&mut self.prefs.memories_only_diff, "Only rows that differ from Live")
                .on_hover_text("Show only the settings where a memory holds another value than the live settings").changed() {
                self.prefs.save();
            }
            if !self.search.trim().is_empty() {
                ui.label(RichText::new(format!("The settings that match \"{}\".", self.search.trim())).small().color(tone::weak(ui.visuals())));
                if ui.small_button("Show all").on_hover_text("Clear the search").clicked() { self.search.clear(); }
            }
        });
        ui.add_space(6.0);
        let live = Col::a(0);
        let rows: Vec<&(String, String, Vec<Setting>)> = kept.into_iter()
            .filter(|r| !self.prefs.memories_only_diff || dial.iter().any(|&m| self.memory_differs(Col::a(m), &r.2[0])))
            .collect();
        if rows.is_empty() {
            ui.label(if self.prefs.memories_only_diff { "No memory holds another value than the live settings here." } else { "No settings match." });
            return actions;
        }
        let mut last_group = String::new();
        // the columns share the width shown, so every memory fits beside the live settings: the names and values are
        // cut short to their column (in full on hover)
        let gap = 16.0;
        let sp = ui.spacing().clone();
        let arrows = if editable { 3.0 * sp.item_spacing.x + 2.0 * (2.0 * sp.button_padding.x + 18.0) } else { 0.0 };
        let room = ui.available_width() - gap * (1 + dial.len()) as f32 - arrows * dial.len() as f32;
        let name_w = (room * 0.3).clamp(160.0, 320.0);
        let value_w = ((room - name_w) / (1 + dial.len()) as f32).clamp(70.0, 220.0);
        let fixed = |ui: &mut egui::Ui, text: RichText, w: f32| { ui.scope(|ui| { ui.set_width(w); ui.add(egui::Label::new(text).truncate()); }); };
        egui::Grid::new("memories").striped(true).num_columns(2 + dial.len()).spacing([gap, 4.0]).show(ui, |ui| {
            ui.strong("Setting"); ui.strong("Live");
            for &m in &dial { ui.strong(self.schema.camera.target_name(m)); }
            ui.end_row();
            for (tab, group, linked) in rows {
                let g = format!("{tab} > {group}");
                if g != last_group {
                    fixed(ui, RichText::new(&g).strong().color(tab_ink(ui.visuals(), &self.schema.camera, tab)), name_w);
                    for _ in 0..=dial.len() { ui.label(""); }
                    ui.end_row();
                    last_group = g;
                }
                let s = &linked[0];
                let text = |c: Col| -> String {
                    if s.text.is_some() { self.col_text(c, s).unwrap_or_default() } else { Self::describe(s, self.col_value(c, s)) }
                };
                fixed(ui, RichText::new(self.setting_title(s)), name_w);
                let edited = |c: Col| self.doc.as_ref().is_some_and(|d| d.original_value(c.section, s.slot()) != self.col_value(c, s));
                // a number with no name yet says why on hover
                let why = |r: egui::Response, c: Col| if let Some(w) = self.unnamed_why(s, self.col_value(c, s)) { r.on_hover_text(w); };
                why(Self::value_cell_w(ui, text(live), false, edited(live), Some(value_w)), live);
                for &m in &dial {
                    let c = Col::a(m);
                    let differs = self.memory_differs(c, s);
                    ui.horizontal(|ui| {
                        why(Self::value_cell_w(ui, text(c), differs, edited(c), Some(value_w)), c);
                        if editable && differs {
                            let (back, to) = (Self::arrow_words(&self.col_name(c), &self.col_name(live)), Self::arrow_words(&self.col_name(live), &self.col_name(c)));
                            // an arrow only into a set that takes a value of it (not where it is view only: `locked_why`),
                            // saying what the copy changes there where the camera keeps the value in more than one record
                            // (`copy_note`)
                            let say = |words: &str, into: usize| match self.copy_note(s, into) { Some((note, _)) => format!("{words}\n\n{note}"), None => words.to_string() };
                            if !self.locked(s, 0) && named(ui.small_button("⬅"), &back).on_hover_text(say(&back, 0)).clicked() { actions.extend(self.copy_row(linked, c, live)); }
                            if !self.locked(s, m) && named(ui.small_button("➡"), &to).on_hover_text(say(&to, m)).clicked() { actions.extend(self.copy_row(linked, live, c)); }
                        }
                    });
                }
                ui.end_row();
            }
        });
        actions
    }

    /// Whether a memory's column holds another value of `s` than the live settings (its text, for a text setting).
    pub(crate) fn memory_differs(&self, c: Col, s: &Setting) -> bool {
        let live = Col::a(0);
        if s.text.is_some() { self.col_text(c, s) != self.col_text(live, s) } else { self.col_value(c, s) != self.col_value(live, s) }
    }

    /// One wording per memory action, the same in Compare, on the Memories page and on the web page. Recalling a
    /// whole memory into the live settings: the button, its hover (with `every`, `whole_set_note`) and the status
    /// line after it (`from`: " from the web page", or nothing).
    pub(crate) fn recall_words(&self, m: usize, every: &str, from: &str) -> (String, String, String) {
        let name = self.schema.camera.target_name(m);
        let hint = self.schema.camera.text.memory_dial_hint.as_deref().filter(|t| !t.is_empty());
        let hover = match hint {
            Some(h) => format!("Make the live settings what {name} holds (what {} does on the camera).{every}", h.replace("{m}", &m.to_string())),
            None => format!("Make the live settings what {name} holds (what recalling it on the camera does).{every}"),
        };
        (format!("Recall {name} ➡ Live"), hover, format!("{name} recalled into the live settings{from}; save, or write to the camera, to keep it"))
    }

    /// Registering the live settings into a whole memory, as `recall_words`.
    pub(crate) fn register_words(&self, m: usize, every: &str, from: &str) -> (String, String, String) {
        let name = self.schema.camera.target_name(m);
        let menu = self.schema.camera.text.memory_register_menu.as_deref().filter(|t| !t.is_empty());
        let hover = match menu {
            Some(r) => format!("Store the live settings into {name} (what {r} does on the camera).{every}"),
            None => format!("Store the live settings into {name} (what registering it on the camera does).{every}"),
        };
        (format!("Register Live ➡ {name}"), hover, format!("Live settings registered into {name}{from}; save, or write to the camera, to keep it"))
    }

    /// The sentence a whole-set button's hover ends with while a search or a tab narrows the rows shown: every
    /// setting the memories keep is copied all the same.
    pub(crate) fn whole_set_note(&self, narrowed: bool) -> String {
        if !narrowed { return String::new(); }
        format!(" All {} settings the memories keep are copied, not only the rows shown.", self.memory_rows().len())
    }

    /// A copy arrow's hover, in Compare and on the Memories page: "Put the value from Memory 1 into Live settings".
    pub(crate) fn arrow_words(from: &str, to: &str) -> String {
        format!("Put the value from {from} into {to}")
    }

    /// One value in a table of columns: a pale fill where it differs from the column it is compared with, orange
    /// with a pencil where it is your edit (the colour and the mark are kept for edits). A fixed width (`width`), or
    /// as wide as its text up to 300 points; the full text on hover when it is cut short.
    pub(crate) fn value_cell_w(ui: &mut egui::Ui, text: impl Into<RichText>, differs: bool, edited: bool, width: Option<f32>) -> egui::Response {
        let v = ui.visuals().clone();
        let fill = if differs { tone::differs(&v) } else { Color32::TRANSPARENT };
        let stroke = if edited { egui::Stroke::new(1.0_f32, tone::edit(&v)) } else { egui::Stroke::NONE };
        let text: RichText = text.into();
        let full = text.text().to_string();
        let shown = if edited { RichText::new(format!("{EDIT_MARK} {full}")).color(tone::edit(&v)) } else { text };
        let r = egui::Frame::new().fill(fill).stroke(stroke).inner_margin(egui::Margin::symmetric(4, 1)).corner_radius(3.0)
            .show(ui, |ui| {
                match width { Some(w) => ui.set_width(w), None => ui.set_max_width(300.0) }
                ui.add(egui::Label::new(shown).truncate().selectable(false));
            }).response;
        if full.chars().count() > 30 { r.on_hover_text(full) } else { r }
    }

    /// Every setting the memory sets keep, whatever the search and the Compare tab filter show: what recalling or
    /// registering a whole memory copies (the Memories page's buttons, Compare's Whole sets, the page's).
    pub(crate) fn memory_rows(&self) -> Vec<(String, String, Vec<Setting>)> {
        self.matrix_rows_for("", None).into_iter().filter(|r| r.2[0].in_sets).collect()
    }
}
