//! Edit mode's columns: the Menu on the left, a tab's groups and rows, and the search's results.

use crate::*;

/// How far a submenu's rows are indented under the row that opens it, per level, in the "As on the camera" layout.
const ROW_INDENT: f32 = 14.0;

impl App {
    /// A small count of edits in a pill, like the badges on the camera's menu tabs: the edit's orange.
    pub(crate) fn badge(ui: &mut egui::Ui, text: String, hover: &str) {
        let (fill, ink) = (tone::edit(ui.visuals()), tone::on_edit(ui.visuals()));
        let r = egui::Frame::new().fill(fill).corner_radius(8.0).inner_margin(egui::Margin::symmetric(6, 1))
            .show(ui, |ui| { ui.label(RichText::new(text).small().strong().color(ink)); }).response;
        r.on_hover_text(hover);
    }

    pub(crate) fn side_bar(&mut self, ui: &mut egui::Ui) {
        ui.heading("Menu");
        ui.add_space(4.0);
        // the camera's Main page, when its definition has one (`main_tiles`), by its name (`text.main_title`)
        if self.schema.camera.main_tiles.as_ref().is_some_and(|t| !t.0.is_empty()) {
            let title = self.schema.camera.text.main_title().to_string();
            ui.horizontal(|ui| {
                let (rect, _) = ui.allocate_exact_size(egui::vec2(6.0, 20.0), egui::Sense::hover());
                ui.painter().rect_filled(rect, 2.0, ui.visuals().strong_text_color());
                if ui.selectable_label(self.view == View::Main, title).clicked() {
                    self.view = View::Main;
                }
            });
        }
        // My Menu, a tab of its own on the camera, when the definition has it (`camera.my_menu`), by its name
        // (`text.my_menu_name`), with how many places hold an item and the edits to it
        if self.has_mymenu_page() {
            let name = self.schema.camera.text.my_menu_name().to_string();
            let ((text, hover), edited) = (self.mymenu_entry_words(), self.mymenu_edits());
            ui.horizontal(|ui| {
                let (rect, _) = ui.allocate_exact_size(egui::vec2(6.0, 20.0), egui::Sense::hover());
                ui.painter().rect_filled(rect, 2.0, tab_color(&self.schema.camera, &name));
                if ui.selectable_label(self.view == View::MyMenu, text).on_hover_text(hover).clicked() {
                    self.view = View::MyMenu;
                }
                if edited > 0 {
                    Self::badge(ui, edited.to_string(), &format!("places and settings edited in {name}"));
                }
            });
        }
        let tabs = self.menu_tabs();
        let focused = self.focus == Focus::Tabs && matches!(self.view, View::Tab(_));
        let off = self.schema.camera.text.off_menu_name().to_string();
        for tab in &tabs {
            let n = self.visible_count(Some(tab));
            if n == 0 && (tab == OTHER_TAB || *tab == off) {
                continue;
            }
            let edited = self.counts(Some(tab));
            let selected = self.view == View::Tab(tab.clone());
            ui.horizontal(|ui| {
                let (rect, _) = ui.allocate_exact_size(egui::vec2(6.0, 20.0), egui::Sense::hover());
                ui.painter().rect_filled(rect, 2.0, tab_color(&self.schema.camera, tab));
                let mut text = RichText::new(format!("{tab}  ({n})"));
                if selected && focused {
                    text = text.underline();
                }
                let r = ui.selectable_label(selected, text);
                let r = if *tab == off { r.on_hover_text(Self::off_menu_hover()) } else { r };
                if r.clicked() {
                    self.view = View::Tab(tab.clone());
                    self.focus = Focus::Groups;
                }
                if edited > 0 {
                    Self::badge(ui, edited.to_string(), "settings edited in this tab");
                }
            });
        }
        ui.separator();
        if !self.search.trim().is_empty() {
            let n = self.search_hits().len();
            if ui.selectable_label(self.view == View::Search, format!("🔍 Search results ({n})")).clicked() {
                self.view = View::Search;
            }
        }
        if !self.dial_sets().is_empty() && ui.selectable_label(self.view == View::Memories, self.memories_title()).on_hover_text("The memories on the mode dial beside the live settings: recall one into the live settings, or register the live settings into one").clicked() {
            self.view = View::Memories;
        }
        if let Some(ex) = &self.schema.camera.exposure {
            let title = if ex.title.is_empty() { "Exposure".to_string() } else { ex.title.clone() };
            if ui.selectable_label(self.view == View::Exposure, title).on_hover_text("Aperture, shutter speed and ISO for the live settings and each memory: who sets each in that exposure mode, and the limits on what the camera may choose").clicked() {
                self.view = View::Exposure;
            }
        }
        let n_changes = self.doc.as_ref().map(|d| d.changes().len()).unwrap_or(0);
        if ui.selectable_label(self.view == View::Changes, format!("All edits ({n_changes})")).clicked() {
            self.view = View::Changes;
        }
        if self.prefs.expert {
            if ui.selectable_label(self.view == View::Unmapped, "Unmapped records").clicked() {
                self.view = View::Unmapped;
            }
            if ui.selectable_label(self.view == View::Records, "Record map").on_hover_text("Every record of the set in file order, mapped or not, so an unmapped record can be read next to its neighbours").clicked() {
                self.view = View::Records;
            }
        }
        if self.prefs.expert {
            ui.separator();
            ui.label(RichText::new(format!("{} known settings", self.schema.settings.len())).small().color(tone::weak(ui.visuals())))
                .on_hover_text("The settings the editor can name for this camera. Where they come from: ⚙ Settings > Camera support & web page");
        }
    }

    pub(crate) fn changed(&self, s: &Setting) -> bool {
        self.doc.as_ref().is_some_and(|d| d.value(self.target, s.slot()) != d.original_value(self.target, s.slot()))
    }

    /// Value of a row as the camera would show it (text settings show their text).
    pub(crate) fn row_value(&self, s: &Setting) -> String {
        self.row_value_in(self.target, s)
    }

    /// Value of a row in the set `target` (`row_value`), as the My Menu page shows the live settings whatever set is
    /// being edited.
    pub(crate) fn row_value_in(&self, target: usize, s: &Setting) -> String {
        let Some(doc) = &self.doc else { return String::new() };
        if s.text.is_some() {
            return doc.edited.sections.get(target).and_then(|sec| sec.get(s.id)).and_then(|r| r.text()).unwrap_or_default();
        }
        let v = doc.value(target, s.slot());
        // a number shown other than as stored (`shown_as`) with the number the camera stores, when Expert mode asks
        match v.filter(|v| self.show_raw && s.shown_as.is_some() && s.label_for(*v).is_none()) {
            Some(raw) => format!("{}  [{raw}]", Self::describe(s, v)),
            None => Self::describe(s, v),
        }
    }

    /// Setting name, optionally badged with its record ID (e.g. "0x01d8" or "0x05db[0]") when show_record_ids is on.
    pub(crate) fn setting_title(&self, s: &Setting) -> String {
        if self.prefs.expert && self.prefs.show_record_ids {
            format!("{}  {}", s.name, s.record_id_hex())
        } else {
            s.name.clone()
        }
    }

    /// The camera-menu layout: groups of the tab | items of the group | the selected item.
    pub(crate) fn menu_view(&mut self, ui: &mut egui::Ui, tab: &str) -> Vec<Action> {
        let mut actions = Vec::new();
        let groups = self.tab_groups(tab);
        if groups.is_empty() {
            ui.label("No settings match.");
            return actions;
        }
        // keep the selection valid after a tab switch, a search or a filter
        if !self.group.as_ref().is_some_and(|g| groups.iter().any(|(n, _, _)| n == g)) {
            self.group = Some(groups[0].0.clone());
            self.item = None;
        }
        let gi = groups.iter().position(|(n, _, _)| Some(n) == self.group.as_ref()).unwrap_or(0);
        let (gname, family, rows) = &groups[gi];
        // the group's rows as drawn (as on the camera, or the flat list), and the rows a folded row of the camera hides
        let lines = if *family { Vec::new() } else { self.group_lines(rows) };
        let fold_key = |path: &[String]| Self::fold_key(tab, gname, path);
        if !*family {
            // a sub-choice shown beside its owner's option, opened from elsewhere, opens its owner's row, its box marked
            if let Some(i) = Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref()).filter(|i| !menu_rows::order(&lines).contains(i)) {
                if let Some(o) = menu_rows::beside_owner(rows.iter().map(|r| &r[0]), &rows[i][0]) {
                    self.sub_focus = Some(rows[i][0].key.clone());
                    self.sub_scroll.set(true);
                    self.item = Some(o.name.clone());
                    self.item_key = Some(o.key.clone());
                }
            }
            match Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref()) {
                None => {
                    self.item = menu_rows::order(&lines).first().map(|&i| rows[i][0].name.clone());
                    self.item_key = None;
                }
                // a jump to a row a folded row of the camera hides unfolds it
                Some(i) => {
                    if let Some(at) = lines.iter().position(|l| matches!(l, Line::Row { index, .. } if *index == i)) {
                        for p in menu_rows::headings_above(&lines, at) {
                            self.folded.remove(&fold_key(&p));
                        }
                    }
                }
            }
        }
        let hidden = menu_rows::hidden(&lines, |p| self.folded.contains(&fold_key(p)));
        let shown: Vec<usize> = lines.iter().zip(&hidden).filter_map(|(l, h)| match l { Line::Row { index, .. } if !h => Some(*index), _ => None }).collect();
        // Up/Down move through the items as drawn, like the camera's menu (Left/Right pick the column: see keyboard_nav)
        let mut moved = false;
        if !*family && self.focus == Focus::Items && !ui.ctx().wants_keyboard_input() {
            let cur = Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref());
            let pos = shown.iter().position(|&i| Some(i) == cur).unwrap_or(0);
            let (up, down) = ui.input(|i| (i.key_pressed(egui::Key::ArrowUp), i.key_pressed(egui::Key::ArrowDown)));
            let to = if down && pos + 1 < shown.len() { Some(shown[pos + 1]) } else if up && pos > 0 { Some(shown[pos - 1]) } else { None };
            if let Some(i) = to {
                self.item = Some(rows[i][0].name.clone());
                self.item_key = Some(rows[i][0].key.clone());
                self.sub_focus = None;
                moved = true;
            }
        }
        let current = if *family { None } else { Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref()) };
        let editable = self.editable();
        let foreign = self.foreign_a().is_some();

        // column 2: groups
        let mut pick_group = None;
        let group_focused = self.focus == Focus::Groups;
        egui::SidePanel::left("groups").resizable(true).default_width(220.0).show_inside(ui, |ui| {
            ui.label(RichText::new(tab).strong().color(tab_ink(ui.visuals(), &self.schema.camera, tab)));
            ui.separator();
            egui::ScrollArea::vertical().id_salt("groups_scroll").auto_shrink([false, false]).show(ui, |ui| {
                for (name, family, rows) in &groups {
                    let all: Vec<&Setting> = if *family { rows[0].iter().collect() } else { rows.iter().flatten().collect() };
                    let n = if *family { rows[0].len() } else { rows.len() };
                    let edited = if *family { all.iter().filter(|s| self.changed(s)).count() } else { rows.iter().filter(|r| r.iter().any(|s| self.changed(s))).count() };
                    let selected = Some(name) == self.group.as_ref();
                    // the page an option opens, under the group of its owner's row, as Right opens it on the camera
                    let page = !*family && self.camera_layout() && all.iter().any(|s| s.on_page());
                    let mut text = RichText::new(if page { format!("› {name}  ({n})") } else { format!("{name}  ({n})") });
                    if selected && group_focused {
                        text = text.underline();
                    }
                    ui.horizontal(|ui| {
                        if page {
                            ui.add_space(12.0);
                        }
                        let resp = ui.selectable_label(selected, text);
                        let resp = if page { resp.on_hover_text("A page of settings an option opens on the camera (Right on it)") } else { resp };
                        if resp.clicked() {
                            pick_group = Some(name.clone());
                        }
                        if edited > 0 {
                            Self::badge(ui, edited.to_string(), "settings edited in this group");
                        }
                    });
                }
            });
        });

        if *family {
            egui::CentralPanel::default().show_inside(ui, |ui| {
                egui::ScrollArea::both().id_salt("family_scroll").auto_shrink([false, false]).show(ui, |ui| {
                    self.pp_table(ui, gname, &rows[0], editable, &mut actions);
                });
            });
        } else {
            // column 4: the selected item
            egui::SidePanel::right("detail").resizable(true).default_width(330.0).show_inside(ui, |ui| {
                egui::ScrollArea::vertical().id_salt("detail_scroll").auto_shrink([false, false]).show(ui, |ui| {
                    if let Some(row) = current.map(|i| &rows[i]) {
                        self.detail_panel(ui, tab, gname, row, editable, &mut actions);
                    }
                });
            });
            // column 3: items and their values
            let mut pick_item = None;
            let mut fold = None;
            let mut set_flat = None;
            egui::CentralPanel::default().show_inside(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(gname).strong());
                    // the layout switch, when the definition says where its settings sit on the camera
                    if self.places() {
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            let flat = self.prefs.flat_list;
                            if ui.selectable_label(flat, "Flat list").on_hover_text("Every setting of the group in one list").clicked() {
                                set_flat = Some(true);
                            }
                            if ui.selectable_label(!flat, "As on the camera").on_hover_text("The rows in the camera's order, each submenu's rows indented under it, as the camera's menu lists them").clicked() {
                                set_flat = Some(false);
                            }
                        });
                    }
                });
                ui.separator();
                egui::ScrollArea::vertical().id_salt("items_scroll").auto_shrink([false, false]).show(ui, |ui| {
                    egui::Grid::new(("items", tab, gname, self.target)).num_columns(2).spacing([16.0, 4.0]).show(ui, |ui| {
                        for (li, line) in lines.iter().enumerate() {
                            if hidden[li] {
                                continue;
                            }
                            let (index, depth) = match line {
                                Line::Mode(mode) => {
                                    ui.label(RichText::new(menu_rows::mode_words(mode)).strong().color(tone::weak(ui.visuals())))
                                        .on_hover_text(format!("The rows below are in the camera's menu in {mode} mode only"));
                                    ui.label("");
                                    ui.end_row();
                                    continue;
                                }
                                Line::More => {
                                    ui.label(RichText::new(menu_rows::MORE).strong().color(tone::weak(ui.visuals())))
                                        .on_hover_text("Camset doesn't know which menu row shows these.");
                                    ui.label("");
                                    ui.end_row();
                                    continue;
                                }
                                Line::Heading { label, depth, path } => {
                                    let closed = self.folded.contains(&fold_key(path));
                                    // the edited settings under it, shown while it is folded
                                    let under = lines[li + 1..].iter().take_while(|l| matches!(l, Line::Row { depth: d, .. } | Line::Heading { depth: d, .. } if d > depth));
                                    let edited = under.filter(|l| matches!(l, Line::Row { index, .. } if rows[*index].iter().any(|s| self.changed(s)))).count();
                                    ui.horizontal(|ui| {
                                        ui.add_space(ROW_INDENT * *depth as f32);
                                        let head = RichText::new(format!("{} {label}", if closed { "⏵" } else { "⏷" })).strong();
                                        let r = ui.add(egui::Label::new(head).sense(egui::Sense::click()))
                                            .on_hover_text(if closed { "A row of the camera's menu: click to show the settings under it" } else { "A row of the camera's menu: click to fold the settings under it" });
                                        if r.clicked() {
                                            fold = Some(path.clone());
                                        }
                                        if closed && edited > 0 {
                                            Self::badge(ui, edited.to_string(), "settings edited under this row");
                                        }
                                    });
                                    ui.label("");
                                    ui.end_row();
                                    continue;
                                }
                                Line::Row { index, depth } => (*index, *depth),
                            };
                            let row = &rows[index];
                            let s = &row[0];
                            let selected = Some(index) == current;
                            let edited = row.iter().any(|l| self.changed(l));
                            let inactive = self.doc.as_ref().is_some_and(|d| {
                                s.inactive_when.as_ref().is_some_and(|r| r.inactive(d.value(self.target, (r.record, None))))
                            });
                            let mut name = RichText::new(self.setting_title(s));
                            let mut value = RichText::new(if edited { format!("{EDIT_MARK} {}", self.row_value(s)) } else { self.row_value(s) });
                            if foreign { value = value.weak(); }
                            if edited {
                                let c = tone::edit(ui.visuals());
                                name = name.color(c).strong();
                                value = value.color(c).strong();
                            } else if inactive {
                                name = name.weak();
                                value = value.weak();
                            }
                            let r1 = if depth == 0 {
                                ui.selectable_label(selected, name)
                            } else {
                                ui.horizontal(|ui| {
                                    ui.add_space(ROW_INDENT * depth as f32);
                                    ui.selectable_label(selected, name)
                                }).inner
                            };
                            // where it sits on the camera ("On the camera: Pre-Capture Settings > Pre-Captr. Start Trigger")
                            let r1 = match menu_rows::place_words(s) {
                                Some(w) => r1.on_hover_text(w),
                                None => r1,
                            };
                            // the value is cut short at the panel's edge (in full on hover), never under the detail panel
                            let full = value.text().to_string();
                            let room = ui.available_width() - 2.0 * ui.spacing().button_padding.x;
                            let wide = ui.fonts(|f| f.layout_no_wrap(full.clone(), egui::TextStyle::Button.resolve(ui.style()), Color32::WHITE).size().x) > room + 0.5;
                            let r2 = ui.scope(|ui| {
                                ui.style_mut().wrap_mode = Some(egui::TextWrapMode::Truncate);
                                ui.selectable_label(selected, value)
                            }).inner;
                            // a number with no name yet says why on hover, after the full text when that is cut short
                            let why = self.doc.as_ref().and_then(|d| self.unnamed_why(s, d.value(self.target, s.slot())));
                            let r2 = match (wide, why) {
                                (true, Some(w)) => r2.on_hover_text(format!("{full}\n\n{w}")),
                                (true, None) => r2.on_hover_text(full),
                                (false, Some(w)) => r2.on_hover_text(w),
                                (false, None) => r2,
                            };
                            self.mymenu_context(&r1, s, &mut actions);
                            self.mymenu_context(&r2, s, &mut actions);
                            if r1.clicked() || r2.clicked() {
                                pick_item = Some((s.name.clone(), s.key.clone()));
                                self.focus = Focus::Items;
                            }
                            if selected && moved {
                                r1.scroll_to_me(None);
                            }
                            ui.end_row();
                        }
                    });
                });
            });
            if let Some((name, key)) = pick_item {
                self.item = Some(name);
                self.item_key = Some(key);
                self.sub_focus = None;
            }
            if let Some(path) = fold {
                let key = fold_key(&path);
                if !self.folded.remove(&key) {
                    self.folded.insert(key);
                    // the row chosen goes out of sight with it: the nearest row still shown is chosen instead
                    let hidden = menu_rows::hidden(&lines, |p| self.folded.contains(&fold_key(p)));
                    let shown: Vec<(usize, usize)> = lines.iter().enumerate().zip(&hidden).filter_map(|((at, l), h)| match l { Line::Row { index, .. } if !h => Some((at, *index)), _ => None }).collect();
                    let at = lines.iter().position(|l| matches!(l, Line::Row { index, .. } if Some(*index) == current));
                    if let Some(at) = at.filter(|&a| hidden[a]) {
                        let near = shown.iter().find(|(a, _)| *a > at).or(shown.iter().rev().find(|(a, _)| *a < at));
                        if let Some(&(_, i)) = near {
                            self.item = Some(rows[i][0].name.clone());
                            self.item_key = Some(rows[i][0].key.clone());
                        }
                    }
                }
            }
            if let Some(flat) = set_flat {
                self.set_flat_list(flat);
            }
        }
        if let Some(g) = pick_group {
            self.group = Some(g);
            self.item = None;
            self.item_key = None;
            self.sub_focus = None;
            self.focus = Focus::Groups;
        }
        actions
    }

    pub(crate) fn search_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let hits = self.search_hits();
        ui.heading(format!("Search: \"{}\"", self.search.trim()));
        if hits.is_empty() {
            ui.label("Nothing matches. The search looks at setting names, groups and value labels.");
            return Vec::new();
        }
        ui.label(RichText::new(format!("{} setting(s). Click one to open it in its menu.", hits.len())).small().color(tone::weak(ui.visuals())));
        ui.add_space(6.0);
        let mut go: Option<Setting> = None;
        let mut my_actions: Vec<Action> = Vec::new();
        let has_mymenu = self.mymenu_pages().is_some();
        egui::Grid::new("search_hits").striped(true).num_columns(3).spacing([18.0, 6.0]).show(ui, |ui| {
            ui.strong("Where"); ui.strong("Setting"); ui.strong("Value"); ui.end_row();
            for s in &hits {
                ui.label(RichText::new(self.where_shown(s)).color(tab_ink(ui.visuals(), &self.schema.camera, &s.tab)));
                let r = ui.link(&s.name).on_hover_text(if has_mymenu { format!("Click to open it in its menu; right-click to add it to {}", self.schema.camera.text.my_menu_name()) } else { "Click to open it in its menu".to_string() });
                if r.clicked() { go = Some(s.clone()); }
                self.mymenu_context(&r, s, &mut my_actions);
                let v = ui.label(self.row_value(s));
                if let Some(why) = self.doc.as_ref().and_then(|d| self.unnamed_why(s, d.value(self.target, s.slot()))) { v.on_hover_text(why); }
                ui.end_row();
            }
        });
        if let Some(s) = go {
            self.view = self.view_of(&s);
            self.group = Some(self.shown_group_of(&s));
            self.item = Some(s.name.clone());
            self.item_key = Some(s.key.clone());
            self.focus = Focus::Items;
            self.search.clear();
        }
        my_actions
    }
}
