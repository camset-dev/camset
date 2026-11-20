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

    /// A small count of rows that differ in a pill, Compare's: the pale amber of a value that differs, so it is not
    /// taken for a count of edits.
    fn diff_badge(ui: &mut egui::Ui, text: String, hover: &str) {
        // dark text: the amber is light in both themes
        let fill = tone::differs_mark(ui.visuals());
        let r = egui::Frame::new().fill(fill).corner_radius(8.0).inner_margin(egui::Margin::symmetric(6, 1))
            .show(ui, |ui| { ui.label(RichText::new(text).small().strong().color(Color32::BLACK)); }).response;
        r.on_hover_text(hover);
    }

    /// The camera's menus to pick one of (`menus`: two or more in the definition, the rows as on the camera), at the
    /// head of the Menu, Edit's and Compare's alike: the definition's words before them (`text.menus_label`, its hover
    /// `text.menus_hover`), then one button per menu in the definition's order, labelled from it, the menu shown
    /// pressed, each with its hover (`menu_hover`: the file's own mode says so). In Compare (`differences`) each says
    /// how many rows differ in it. A click shows that menu and changes nothing in the file (`set_menu`). Nothing
    /// without menus.
    fn menu_selector(&mut self, ui: &mut egui::Ui, differences: Option<Vec<usize>>) {
        let menus: Vec<(String, String)> = self.menus().iter().map(|m| (m.name.clone(), self.menu_hover(&m.name))).collect();
        if menus.is_empty() {
            return;
        }
        let (label, hover) = (self.schema.camera.text.menus_label().to_string(), self.schema.camera.text.menus_hover().to_string());
        ui.label(RichText::new(label).strong()).on_hover_text(&hover);
        let now = self.menu_shown();
        let mut pick = None;
        ui.horizontal_wrapped(|ui| {
            for (i, (name, tip)) in menus.iter().enumerate() {
                // named by its label, its pressed state told to screen readers (a selectable button)
                let r = ui.selectable_label(now.as_deref() == Some(name.as_str()), name).on_hover_text(if tip.is_empty() { &hover } else { tip });
                if r.clicked() {
                    pick = Some(name.clone());
                }
                if let Some(&n) = differences.as_ref().and_then(|d| d.get(i)).filter(|n| **n > 0) {
                    Self::diff_badge(ui, n.to_string(), &format!("rows that differ in the {name} menu"));
                }
            }
        });
        if let Some(m) = pick {
            self.set_menu(&m);
            self.diff_cursor = None;
        }
        ui.add_space(4.0);
    }

    /// One entry of the Menu (`BarEntry`), Edit's or Compare's: its colour mark (Main's in the strong text colour, none
    /// for All settings), its words `text`, chosen or not, underlined while the arrow keys move in the Menu, its hover,
    /// and its badge (Compare's `diff`: the rows that differ; Edit's: the settings edited, `badge_hover`). True when
    /// clicked.
    fn bar_entry_ui(ui: &mut egui::Ui, e: &BarEntry, text: String, (selected, underline): (bool, bool), diff: bool, badge_hover: &str) -> bool {
        ui.horizontal(|ui| {
            let (rect, _) = ui.allocate_exact_size(egui::vec2(6.0, 20.0), egui::Sense::hover());
            let mark = match (&e.key, e.color) {
                (BarKey::All, _) => None,
                (_, Some(c)) => Some(c),
                (_, None) => Some(ui.visuals().strong_text_color()),
            };
            if let Some(c) = mark {
                ui.painter().rect_filled(rect, 2.0, c);
            }
            let text = if underline { RichText::new(text).underline() } else { RichText::new(text) };
            let r = ui.selectable_label(selected, text);
            let r = match &e.hover { Some(h) => r.on_hover_text(h), None => r };
            if e.badge > 0 {
                if diff { Self::diff_badge(ui, e.badge.to_string(), badge_hover) } else { Self::badge(ui, e.badge.to_string(), badge_hover) }
            }
            r.clicked()
        }).inner
    }

    /// Whether Edit shows the page of the Menu's entry `key`.
    fn shows_entry(&self, key: &BarKey) -> bool {
        match key {
            BarKey::Main => self.view == View::Main,
            BarKey::MyMenu => self.view == View::MyMenu,
            BarKey::Tab(t) => self.view == View::Tab(t.clone()),
            BarKey::All => false,
        }
    }

    /// Edit's Menu: the camera's menus to pick one of (`menu_selector`), then the entries of the menu shown
    /// (`edit_entries`: Main, My Menu, the tabs with how many settings each lists, Other and what the menus do not hold,
    /// each with its edits), then the pages beside them (the search's results, the memories, the exposure page, All
    /// edits, and Expert mode's).
    pub(crate) fn side_bar(&mut self, ui: &mut egui::Ui) {
        // the camera's menus head the Menu, as on the page
        self.menu_selector(ui, None);
        ui.heading("Menu");
        ui.add_space(4.0);
        let menu = self.menu_shown();
        let entries = self.edit_entries(self.target, menu.as_deref(), &self.search, self.only_changed);
        let focused = self.focus == Focus::Tabs;
        let my_menu = self.schema.camera.text.my_menu_name().to_string();
        let mut go = None;
        for e in &entries {
            let selected = self.shows_entry(&e.key);
            // a tab says how many settings it lists; Main says nothing, My Menu's words say it
            let text = match (&e.key, e.count) { (BarKey::Tab(_), Some(n)) => format!("{}  ({n})", e.label), _ => e.label.clone() };
            let hover = if e.key == BarKey::MyMenu { format!("places and settings edited in {my_menu}") } else { "settings edited in this tab".to_string() };
            if Self::bar_entry_ui(ui, e, text, (selected, selected && focused), false, &hover) {
                go = Some(e.key.clone());
            }
        }
        match go {
            Some(BarKey::Main) => self.view = View::Main,
            Some(BarKey::MyMenu) => self.view = View::MyMenu,
            Some(BarKey::Tab(t)) => {
                self.view = View::Tab(t);
                self.focus = Focus::Groups;
            }
            Some(BarKey::All) | None => {}
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
        // the lines All edits lists, setting by setting (`edit_lines`)
        let n_changes = self.doc.as_ref().map(|d| self.edit_lines(&d.original, &d.edited).len()).unwrap_or(0);
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

    /// Compare's Menu, the same as Edit's: the camera's menus to pick one of, each with how many rows differ in it, then
    /// "All settings" and Edit's entries in the menu shown (`compare_bar`), each with how many rows it lists and how many
    /// of them differ between the columns. A click shows that entry's rows (`compare_entry`); an entry the menu no longer
    /// lists gives way to All settings.
    pub(crate) fn compare_side_bar(&mut self, ui: &mut egui::Ui) {
        let (differences, entries) = {
            let cols = self.cols.clone();
            // a row's standing worked out once a frame, whichever entries and menus list it
            let seen: std::cell::RefCell<std::collections::HashMap<String, bool>> = Default::default();
            let differs = |s: &Setting| {
                if let Some(&d) = seen.borrow().get(&s.key) {
                    return d;
                }
                let d = self.row_differs(&cols, s);
                seen.borrow_mut().insert(s.key.clone(), d);
                d
            };
            let differences = (cols.len() >= 2 && !self.menus().is_empty()).then(|| self.menu_differences(&self.search, &differs));
            (differences, self.compare_bar(self.compare_menu().as_deref(), &self.search, &differs))
        };
        self.menu_selector(ui, differences);
        ui.heading("Menu");
        ui.add_space(4.0);
        if !entries.iter().any(|e| e.key == self.compare_key()) {
            self.compare_entry = BarKey::All;
        }
        let focused = self.focus == Focus::Tabs;
        let mut go = None;
        for e in &entries {
            let selected = e.key == self.compare_key();
            let text = format!("{}  ({})", e.label, e.count.unwrap_or_default());
            if Self::bar_entry_ui(ui, e, text, (selected, selected && focused), true, "rows that differ between the columns") {
                go = Some(e.key.clone());
            }
        }
        if let Some(k) = go {
            self.compare_entry = k;
            self.diff_cursor = None;
            self.focus = Focus::Tabs;
        }
    }

    /// Up and Down while the arrow keys move in the Menu (`Focus::Tabs`, Left from the groups in Edit, a click on an
    /// entry in Compare): the previous or next of the Menu's own entries (`bar_keys`: Main, My Menu, the tabs, Other and
    /// what the menus do not hold; in Compare All settings first), the keys taken so the columns' keys do not move too.
    /// Only plain arrows: Alt with them steps through Compare's differences.
    pub(crate) fn bar_nav(&mut self, ctx: &egui::Context) {
        if self.doc.is_none() || self.focus != Focus::Tabs || typing(ctx) || ctx.memory(|m| m.any_popup_open()) {
            return;
        }
        let menu = self.menu_shown();
        let (keys, now) = match self.mode {
            Mode::Edit => {
                let now = match &self.view {
                    View::Main => BarKey::Main,
                    View::MyMenu => BarKey::MyMenu,
                    View::Tab(t) => BarKey::Tab(t.clone()),
                    _ => return,
                };
                (self.bar_keys(false, self.target, menu.as_deref(), &self.search, self.only_changed), now)
            }
            Mode::Compare if !self.compare_records => (self.bar_keys(true, 0, menu.as_deref(), &self.search, false), self.compare_key()),
            Mode::Compare => return,
        };
        // a page the bar does not list (Only edited, a search): the keys start from its first entry
        let pos = keys.iter().position(|k| *k == now);
        let arrow = |k: egui::Key| move |e: &egui::Event| matches!(e, egui::Event::Key { key, pressed: true, modifiers, .. } if *key == k && modifiers.is_none());
        let (up, down) = ctx.input_mut(|i| {
            let (up, down) = (i.events.iter().any(arrow(egui::Key::ArrowUp)), i.events.iter().any(arrow(egui::Key::ArrowDown)));
            i.events.retain(|e| !arrow(egui::Key::ArrowUp)(e) && !arrow(egui::Key::ArrowDown)(e));
            (up, down)
        });
        if up || down {
            self.keep_focus(ctx);
        }
        let step = if down { 1 } else if up { -1 } else { return };
        let next = match pos { Some(p) => step_in(keys.len(), p, step), None => (!keys.is_empty()).then_some(0) };
        let Some(key) = next.map(|i| keys[i].clone()) else { return };
        match self.mode {
            Mode::Edit => {
                let view = match key {
                    BarKey::Main => View::Main,
                    BarKey::MyMenu => View::MyMenu,
                    BarKey::Tab(t) => View::Tab(t),
                    BarKey::All => return,
                };
                // the row chosen stays chosen, as after a click on the entry
                let (item, key) = (self.item.clone(), self.item_key.clone());
                self.select(Some(view), None, item.as_deref().zip(key.as_deref()));
            }
            Mode::Compare => {
                self.compare_entry = key;
                self.diff_cursor = None;
            }
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
            self.select(None, Some(groups[0].0.clone()), None);
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
                    self.select(None, self.group.clone(), Some((&o.name, &o.key)));
                    self.sub_focus = Some(rows[i][0].key.clone());
                    self.sub_scroll.set(true);
                }
            }
            match Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref()) {
                None => {
                    let hidden = menu_rows::hidden(&lines, |p| self.folded.contains(&fold_key(p)));
                    // a row of the camera's menu chosen by the keys stays the choice while it is shown
                    let head_shown = self.item_head.as_ref().is_some_and(|p| lines.iter().zip(&hidden).any(|(l, h)| !h && matches!(l, Line::Heading { path, .. } if path == p)));
                    if !head_shown {
                        // the first row a fold leaves shown, or where every row is under a folded one, the first heading
                        let first = lines.iter().zip(&hidden).find_map(|(l, h)| match l { Line::Row { index, .. } if !h => Some(&rows[*index][0]), _ => None });
                        self.select(None, self.group.clone(), first.map(|s| (s.name.as_str(), s.key.as_str())));
                        if first.is_none() {
                            self.item_head = lines.iter().zip(&hidden).find_map(|(l, h)| match l { Line::Heading { path, .. } if !h => Some(path.clone()), _ => None });
                        }
                    }
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
        // Up/Down move through the items as drawn, like the camera's menu, stopping on its rows that hold others too
        // (Left/Right pick the column, or fold a row that holds others: see keyboard_nav)
        let mut moved = false;
        if !*family && self.focus == Focus::Items && !typing(ui.ctx()) {
            let stops: Vec<usize> = (0..lines.len()).filter(|&a| !hidden[a] && matches!(lines[a], Line::Row { .. } | Line::Heading { .. })).collect();
            let cur = Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref());
            let at = lines.iter().position(|l| match l {
                Line::Heading { path, .. } => self.item_head.as_ref() == Some(path),
                Line::Row { index, .. } => self.item_head.is_none() && Some(*index) == cur,
                _ => false,
            });
            let pos = at.and_then(|a| stops.iter().position(|&s| s == a)).unwrap_or(0);
            let (up, down) = ui.input(|i| (i.key_pressed(egui::Key::ArrowUp), i.key_pressed(egui::Key::ArrowDown)));
            let to = if down && pos + 1 < stops.len() { Some(stops[pos + 1]) } else if up && pos > 0 { Some(stops[pos - 1]) } else { None };
            match to.map(|a| &lines[a]) {
                Some(Line::Row { index, .. }) => {
                    self.select(None, self.group.clone(), Some((&rows[*index][0].name, &rows[*index][0].key)));
                    moved = true;
                }
                Some(Line::Heading { path, .. }) => {
                    self.select(None, self.group.clone(), None);
                    self.item_head = Some(path.clone());
                    moved = true;
                }
                _ => {}
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
            let mut fold_every = None;
            egui::CentralPanel::default().show_inside(ui, |ui| {
                // the family's table folded or open (`fold_all`), with its keys, as on the page
                ui.horizontal(|ui| {
                    let ctx = ui.ctx().clone();
                    let keys = |s: &egui::KeyboardShortcut| ctx.format_shortcut(s);
                    if ui.small_button("Collapse all").on_hover_text(format!("Fold the table ({})", keys(&KEY_COLLAPSE_ALL))).clicked() { fold_every = Some(true); }
                    if ui.small_button("Expand all").on_hover_text(format!("Open the table ({})", keys(&KEY_EXPAND_ALL))).clicked() { fold_every = Some(false); }
                });
                // a button's request acts in this same drawing, the table being drawn below it
                if let Some(collapse) = fold_every.take() {
                    self.fold_all(collapse);
                }
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
                    } else if let Some(label) = self.item_head.as_ref().and_then(|p| lines.iter().find_map(|l| match l { Line::Heading { label, path, .. } if path == p => Some(label.clone()), _ => None })) {
                        ui.heading(label);
                        ui.label("A row of the camera's menu that holds the settings under it. Enter or Space folds or shows them, Left folds them and Right shows them; Up and Down go on through the rows.");
                    }
                });
            });
            // column 3: items and their values
            let mut pick_item = None;
            let mut fold = None;
            let mut set_flat = None;
            let mut fold_every = None;
            egui::CentralPanel::default().show_inside(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(gname).strong());
                    // the camera's rows that hold others, all folded or all shown (`fold_all`), with their keys
                    if lines.iter().any(|l| matches!(l, Line::Heading { .. })) {
                        let ctx = ui.ctx().clone();
                        let keys = |s: &egui::KeyboardShortcut| ctx.format_shortcut(s);
                        if ui.small_button("Collapse all").on_hover_text(format!("Fold every row of the camera's menu here that holds others ({})", keys(&KEY_COLLAPSE_ALL))).clicked() { fold_every = Some(true); }
                        if ui.small_button("Expand all").on_hover_text(format!("Show every row of the camera's menu here ({})", keys(&KEY_EXPAND_ALL))).clicked() { fold_every = Some(false); }
                    }
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
                                        // chosen by the keys (`item_head`): marked as a chosen row is
                                        let chosen = self.item_head.as_ref() == Some(path);
                                        let head = if chosen { head.background_color(ui.visuals().selection.bg_fill) } else { head };
                                        let r = ui.add(egui::Label::new(head).sense(egui::Sense::click()))
                                            .on_hover_text(if closed { "A row of the camera's menu: click to show the settings under it" } else { "A row of the camera's menu: click to fold the settings under it" });
                                        if r.clicked() {
                                            fold = Some(path.clone());
                                        }
                                        if chosen && moved {
                                            r.scroll_to_me(None);
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
                self.select(None, self.group.clone(), Some((&name, &key)));
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
                        match near {
                            Some(&(_, i)) => self.select(None, self.group.clone(), Some((&rows[i][0].name, &rows[i][0].key))),
                            // none left shown: the row of the camera's menu just folded
                            None => {
                                self.select(None, self.group.clone(), None);
                                self.item_head = Some(path.clone());
                            }
                        }
                    }
                }
            }
            if let Some(flat) = set_flat {
                self.set_flat_list(flat);
            }
            if let Some(collapse) = fold_every {
                self.fold_all(collapse);
            }
        }
        if let Some(g) = pick_group {
            self.select(None, Some(g), None);
            self.focus = Focus::Groups;
        }
        actions
    }

    /// Collapse all (`collapse`) or expand all, by the buttons or by Cmd/Ctrl+Shift+↑ / ↓ (`KEY_COLLAPSE_ALL`,
    /// `KEY_EXPAND_ALL`), the page's alike: in Compare its tabs and groups, as its Collapse all and Expand all have always
    /// done; in a tab of Edit the camera's rows that hold others in the group shown (the group column picks one group at a
    /// time; the Menu's entries are pages, not folds), or a family group's table; on the exposure page its "What decides"
    /// sections, on the record map its records' bytes (`head_fold`), on the Memories page its groups (`mem_closed`). A row
    /// chosen that a fold hides gives way to the nearest row still shown, as a click on its heading does, or to none where
    /// every row is under a folded one. The rule: every foldable group of the view in front, as on the page.
    pub(crate) fn fold_all(&mut self, collapse: bool) {
        match (self.mode, self.view.clone()) {
            (Mode::Compare, _) if !self.compare_records => {
                if collapse {
                    let rows = self.compare_rows(self.compare_menu().as_deref(), &self.compare_key(), &self.search);
                    for (t, _, _) in rows.iter() {
                        self.matrix_closed.insert((t.clone(), String::new()));
                    }
                } else {
                    self.matrix_closed.clear();
                }
            }
            (Mode::Edit, View::Tab(tab)) => {
                let groups = self.tab_groups(&tab);
                let Some((gname, family, rows)) = groups.iter().find(|(n, _, _)| Some(n) == self.group.as_ref()).or(groups.first()) else { return };
                // a family's table (Picture Profiles, Creative Looks): its one collapsing header
                if *family {
                    self.head_fold = Some(collapse);
                    return;
                }
                let lines = self.group_lines(rows);
                for l in &lines {
                    if let Line::Heading { path, .. } = l {
                        let k = Self::fold_key(&tab, gname, path);
                        if collapse { self.folded.insert(k); } else { self.folded.remove(&k); }
                    }
                }
                let hidden = menu_rows::hidden(&lines, |p| self.folded.contains(&Self::fold_key(&tab, gname, p)));
                let cur = Self::pick_row(rows, self.item.as_ref(), self.item_key.as_ref());
                if let Some(at) = lines.iter().position(|l| matches!(l, Line::Row { index, .. } if Some(*index) == cur)).filter(|&a| hidden[a]) {
                    let shown = |a: &usize| !hidden[*a] && matches!(lines[*a], Line::Row { .. });
                    let near = (0..at).rev().find(shown).or_else(|| (at..lines.len()).find(shown));
                    let row = near.and_then(|a| match lines[a] { Line::Row { index, .. } => Some(rows[index][0].clone()), _ => None });
                    self.select(None, Some(gname.clone()), row.as_ref().map(|s| (s.name.as_str(), s.key.as_str())));
                    // none left shown: the row of the camera's menu, still shown, that holds it, so the keys have somewhere to be
                    if row.is_none() {
                        self.item_head = (0..at).rev().find_map(|a| match &lines[a] { Line::Heading { path, .. } if !hidden[a] => Some(path.clone()), _ => None });
                    }
                }
            }
            (Mode::Edit, View::Exposure | View::Records) => self.head_fold = Some(collapse),
            // the Memories page's groups, those the search shows
            (Mode::Edit, View::Memories) => {
                if collapse {
                    let groups: Vec<String> = self.matrix_rows_shared(&self.search, None).iter().filter(|r| r.2[0].in_sets).map(|(t, g, _)| format!("{t} > {g}")).collect();
                    self.mem_closed.extend(groups);
                } else {
                    self.mem_closed.clear();
                }
            }
            _ => {}
        }
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
            // as every jump: the camera's menu that shows it (this one if it does, else the file's, else the first)
            self.go_to(&s);
            self.search.clear();
        }
        my_actions
    }
}

/// The camera's menus in the window (the definition's `camera.menus`, stubbed onto the sample's in memory): the
/// selector, the Menu's entries in Edit and in Compare, Compare's rows per menu, the "Editing:" row, the Main page's
/// tiles, the detail panel's name, the jumps and the arrow keys in the Menu; and without menus, the window as before.
#[cfg(test)]
mod menus_window_tests {
    use super::*;
    use crate::test_support::{done, sample_app, strip_menus, stub_menus, stub_menus_and_a_place, texts, SAMPLE_BYTES};
    use eframe::App as _;
    use egui::accesskit::{Action as Ak, ActionRequest, NodeId, Role, Toggled};

    /// What a screen reader is told of each control and label: its node, role, name (a label's words) and pressed
    /// state.
    type Said = Vec<(NodeId, Role, String, Option<Toggled>)>;

    /// The window run frame by frame, as a screen reader is told it.
    struct Window {
        ctx: egui::Context,
        frame: eframe::Frame,
    }

    impl Window {
        fn new() -> Self {
            let ctx = egui::Context::default();
            ctx.enable_accesskit();
            Window { ctx, frame: eframe::Frame::_new_kittest() }
        }

        /// One frame with `events`: the texts it draws and what it tells a screen reader.
        fn run(&mut self, app: &mut App, events: Vec<egui::Event>) -> (Vec<String>, Said) {
            let frame = &mut self.frame;
            let out = self.ctx.run(egui::RawInput { events, ..Default::default() }, |ctx| app.update(ctx, frame));
            let said = out.platform_output.accesskit_update
                .map(|t| t.nodes.iter().filter_map(|(id, n)| n.label().or(n.value()).map(|l| (*id, n.role(), l.to_string(), n.toggled()))).collect())
                .unwrap_or_default();
            (texts(&out.shapes), said)
        }

        /// Two frames, the window settled: the second's.
        fn settle(&mut self, app: &mut App) -> (Vec<String>, Said) {
            let _ = self.run(app, vec![]);
            self.run(app, vec![])
        }

        /// A screen reader's click on the one control of `role` named `name`, then the window settled.
        fn click(&mut self, app: &mut App, said: &Said, role: Role, name: &str) -> (Vec<String>, Said) {
            let hit: Vec<NodeId> = said.iter().filter(|(_, r, l, _)| *r == role && l == name).map(|(id, ..)| *id).collect();
            assert_eq!(hit.len(), 1, "{name}: {said:?}");
            let _ = self.run(app, vec![egui::Event::AccessKitActionRequest(ActionRequest { action: Ak::Click, target: hit[0], data: None })]);
            self.settle(app)
        }

        /// An arrow key, plain or with Alt, then a frame more.
        fn key(&mut self, app: &mut App, key: egui::Key, alt: bool) {
            let modifiers = if alt { egui::Modifiers::ALT } else { egui::Modifiers::NONE };
            let _ = self.run(app, vec![egui::Event::Key { key, physical_key: None, pressed: true, repeat: false, modifiers }]);
            let _ = self.run(app, vec![]);
        }
    }

    /// The pressed state of each button named `name`.
    fn buttons(said: &Said, name: &str) -> Vec<Option<Toggled>> {
        said.iter().filter(|(_, r, l, _)| *r == Role::Button && l == name).map(|(.., t)| *t).collect()
    }

    /// Whether `got` holds `want` in that order, other texts between them.
    fn in_order(got: &[String], want: &[String]) -> bool {
        let mut at = 0;
        want.iter().all(|w| match got[at..].iter().position(|g| g == w) {
            Some(p) => {
                at += p + 1;
                true
            }
            None => false,
        })
    }

    /// Setting `s` given another value than file A's live settings hold, in file `c`'s.
    fn other_value(app: &App, c: &mut CamSet, s: &Setting) {
        let cur = app.col_value(Col::a(0), s).unwrap();
        let v = s.values.iter().map(|(v, _)| *v).find(|v| *v != cur).or_else(|| s.range.map(|(lo, hi)| if cur < hi { cur + 1 } else { lo })).unwrap();
        c.sections[0].get_mut(s.id).unwrap().put(s.index, v).unwrap();
    }

    /// A row's names: its entry, group and records' keys.
    fn names(rows: &[Row]) -> Vec<(String, String, Vec<String>)> {
        rows.iter().map(|r| (r.0.clone(), r.1.clone(), r.2.iter().map(|s| s.key.clone()).collect())).collect()
    }

    /// The live record of the shooting mode a file was saved in, and the number it holds for a mode of menu `menu`.
    fn saved_in(app: &App, menu: &str) -> (Setting, i64) {
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let modes = app.menu_named(menu).unwrap().modes.clone();
        let code = lm.modes.iter().find(|(_, m)| modes.contains(m)).map(|(c, _)| c.parse::<i64>().unwrap()).unwrap();
        (app.schema.settings.iter().find(|s| s.key == lm.key).unwrap().clone(), code)
    }

    /// The ISO setting, which the camera keeps a copy of per shooting mode, the menu the sample opens on, another menu
    /// whose rows show its copy, and that copy.
    fn iso_and_its_copy(app: &App) -> (Setting, String, String, Setting) {
        let iso = app.schema.settings.iter().find(|s| s.key == "global:0x0334").unwrap().clone();
        let own = app.menu_shown().unwrap();
        let other = app.menus().iter().map(|m| m.name.clone()).find(|m| *m != own && app.copy_for_menu(&iso, m).is_some()).unwrap();
        let copy = app.copy_for_menu(&iso, &other).unwrap().clone();
        (iso, own, other, copy)
    }

    /// Without menus in the definition the window is as before: no selector, Edit's Menu the same entries with the same
    /// words, Compare's rows the ones it always had (All settings) and no list of tabs, its left bar's entries Edit's
    /// with All settings first, a tab's rows those of All settings Edit lists under it.
    #[test]
    fn without_menus_the_window_is_as_before() {
        let (mut app, dir, user) = sample_app("e2_none", Some(strip_menus));
        assert!(app.menus().is_empty() && app.menu_shown().is_none());
        app.view = View::Tab(app.menu_tabs()[0].clone());
        let mut w = Window::new();
        let (drawn, _) = w.settle(&mut app);
        let label = app.schema.camera.text.menus_label().to_string();
        assert!(!drawn.contains(&label), "no selector");
        // the Menu's words as before: Main, My Menu, then each tab with how many settings it lists
        let mut want = vec![app.schema.camera.text.main_title().to_string(), app.mymenu_entry_words().0];
        want.extend(app.menu_tabs().into_iter().filter(|t| app.side_bar_lists(t)).map(|t| format!("{t}  ({})", app.visible_count(Some(&t)))));
        assert!(in_order(&drawn, &want), "{want:?} in {drawn:?}");
        let edit = app.bar_keys(false, 0, None, "", false);
        // Compare: file B with one value changed, two columns
        let rows = app.build_matrix_rows("", None, false);
        let changed = rows.iter().map(|r| r.2[0].clone()).find(|s| s.scalar && s.values.len() >= 2 && app.col_value(Col::a(0), s).is_some()).unwrap();
        let mut b = app.doc.as_ref().unwrap().original.clone();
        other_value(&app, &mut b, &changed);
        app.compare = Some((PathBuf::from("B.DAT"), b));
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::b(0)], false);
        let (drawn, said) = w.settle(&mut app);
        assert!(!drawn.contains(&label), "no selector");
        assert!(!said.iter().any(|(_, r, l, _)| *r == Role::ComboBox || l == "Tab compared"), "no list of tabs: the Menu picks");
        // All settings: the rows Compare always had, and the records a Main tile shows that those leave out (`tile_records`),
        // each a row beside its group: with no memory among these columns (A's and B's live settings) those the live
        // settings hold; a memory's own (a fraction's Expert-only parts too) wait for a memory column
        let every: Vec<Setting> = app.tile_records("");
        assert!(!every.is_empty());
        let tiles: Vec<String> = every.iter().filter(|s| s.area != "set").map(|s| s.key.clone()).collect();
        let shown = names(&app.matrix_rows());
        assert_eq!(shown.iter().filter(|r| !tiles.contains(&r.2[0])).cloned().collect::<Vec<_>>(), names(&rows), "All settings: the rows Compare always had");
        assert_eq!(shown.iter().filter(|r| tiles.contains(&r.2[0])).count(), tiles.len(), "and each tile record the live settings hold once");
        assert!(every.iter().filter(|s| s.area == "set").all(|s| !shown.iter().any(|r| r.2[0] == s.key)), "a memory's own records wait for a memory column");
        assert_eq!(names(&app.matrix_rows_for("", None)), names(&rows), "the Memories page's and a recall's rows without them");
        // and those are the definition's live settings outside Expert mode, and My Menu's places as its page shows them
        // (Compare's left bar is Edit's for every definition: All holds My Menu's places too), each record in one row
        let mut records: Vec<String> = rows.iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect();
        let n = records.len();
        records.sort();
        records.dedup();
        let mut want: Vec<String> = app.schema.settings.iter().filter(|s| s.area == "global" && (!App::expert_only(s) || app.is_mymenu_place(s))).map(|s| s.key.clone()).collect();
        want.sort();
        assert_eq!((n, &records), (want.len(), &want), "every live setting once");
        assert_eq!(app.mm_rows.len(), rows.len() + tiles.len());
        let cols = app.cols.clone();
        let entries = app.compare_bar(None, "", &|s| app.row_differs(&cols, s));
        assert_eq!(entries.iter().map(|e| e.key.clone()).collect::<Vec<_>>(), [vec![BarKey::All], edit.clone()].concat(), "Edit's entries, All settings first");
        assert!(drawn.contains(&format!("{ALL_SETTINGS}  ({})", rows.len() + tiles.len())), "{drawn:?}");
        assert!(entries[0].badge >= 1, "the row that differs");
        // a tab's rows: those of All settings Edit lists under it, under its name; each of them under one entry only
        let all: Vec<String> = app.matrix_rows().iter().map(|r| r.2[0].key.clone()).collect();
        let mut seen = std::collections::HashSet::new();
        for k in &edit {
            let BarKey::Tab(t) = k else { continue };
            let mut got: Vec<String> = Vec::new();
            for r in app.compare_rows(None, k, "").iter() {
                assert!(r.0 == *t && all.contains(&r.2[0].key) && seen.insert(r.2[0].key.clone()), "{t}: {}", r.2[0].name);
                got.extend(r.2.iter().map(|s| s.key.clone()));
            }
            // the records of the rows Edit's own page lists under that tab (`tab_groups`), not Compare's code, and the
            // records a Main tile shows that it shows (`tile_records`), but a memory's own, which wait for a memory column
            // (these columns are A's and B's live settings)
            let mut want: Vec<String> = app.tab_groups(t).into_iter().flat_map(|(_, _, rows)| rows.into_iter().flatten().map(|s| s.key)).collect();
            want.extend(app.tile_records("").into_iter().filter(|s| app.entry_of(s) == *t && s.area != "set").map(|s| s.key));
            got.sort();
            want.sort();
            want.dedup();
            assert_eq!(got, want, "{t}: the records Edit lists under it");
        }
        done(&dir, &user);
    }

    fn two_menus(v: &mut serde_json::Value) {
        stub_menus(v);
        v["camera"]["menus"] = serde_json::json!([{ "name": "Photo", "modes": ["Stills"] }, { "name": "Video", "modes": ["Movie", "S&Q", "Time-lapse"] }]);
        v["camera"]["text"]["menus_label"] = serde_json::json!("Shooting mode:");
    }

    fn four_menus(v: &mut serde_json::Value) {
        stub_menus(v);
        v["camera"]["menus"] = serde_json::json!([
            { "name": "Still", "modes": ["Stills"] }, { "name": "Movie", "modes": ["Movie"] },
            { "name": "S&Q", "modes": ["S&Q"] }, { "name": "Interval", "modes": ["Time-lapse"] },
        ]);
    }

    /// Two menus and four draw two and four buttons, in the definition's order and labelled from it, after the
    /// definition's words (or the editor's own), in Edit and in Compare; each a button named by its label and telling
    /// a screen reader whether it is pressed, the menu shown alone pressed.
    #[test]
    fn two_and_four_menus_draw_a_button_each() {
        // (the test's tag, the menus stubbed on, their names, the words before their buttons)
        type Case<'a> = (&'a str, fn(&mut serde_json::Value), &'a [&'a str], &'a str);
        let cases: [Case; 2] = [
            ("e2_two", two_menus, &["Photo", "Video"], "Shooting mode:"),
            ("e2_four", four_menus, &["Still", "Movie", "S&Q", "Interval"], "Camera menu:"),
        ];
        for (tag, stub, want, label) in cases {
            let (mut app, dir, user) = sample_app(tag, Some(stub));
            assert_eq!(app.menus().iter().map(|m| m.name.as_str()).collect::<Vec<_>>(), want);
            app.view = View::Tab(app.menu_tabs()[0].clone());
            let mut w = Window::new();
            for mode in [Mode::Edit, Mode::Compare] {
                app.mode = mode;
                let (drawn, said) = w.settle(&mut app);
                let section = if mode == Mode::Edit { "Edit" } else { "Compare" };
                assert!(said.iter().any(|(_, r, l, _)| *r == Role::Label && l == label), "{section}: the words before the buttons: {said:?}");
                let shown = app.menu_shown().unwrap();
                for n in want {
                    let pressed = if *n == shown { Toggled::True } else { Toggled::False };
                    assert_eq!(buttons(&said, n), vec![Some(pressed)], "{section}: {n}: {said:?}");
                }
                let order: Vec<String> = std::iter::once(label).chain(want.iter().copied()).map(str::to_string).collect();
                assert!(in_order(&drawn, &order), "{section}: {order:?} in {drawn:?}");
            }
            done(&dir, &user);
        }
    }

    /// The selector opens on the menu of the mode the file was saved in, whose button says so on hover; a click shows
    /// another menu, in Edit and in Compare, and changes no byte of the file; a file saved in another mode opens on
    /// that mode's menu.
    #[test]
    fn the_menu_opens_on_the_files_mode_and_a_click_changes_no_byte() {
        let (mut app, dir, user) = sample_app("e2_open", Some(stub_menus));
        let mode = app.set_mode(0).expect("the sample says the mode it was saved in");
        let own = app.menus().iter().find(|m| m.modes.contains(&mode)).unwrap().name.clone();
        let other = app.menus().iter().map(|m| m.name.clone()).find(|m| *m != own).unwrap();
        assert_eq!(app.menu_shown().as_deref(), Some(own.as_str()));
        assert!(app.menu_hover(&own).contains(&format!("This file was saved in {mode} mode.")), "{}", app.menu_hover(&own));
        assert!(!app.menu_hover(&other).contains("This file was saved in"));
        let before = app.doc.as_ref().unwrap().edited.to_bytes();
        let mut w = Window::new();
        let (_, said) = w.settle(&mut app);
        assert_eq!(buttons(&said, &own), vec![Some(Toggled::True)]);
        let (_, said) = w.click(&mut app, &said, Role::Button, &other);
        assert_eq!(app.menu_shown().as_deref(), Some(other.as_str()));
        assert_eq!((buttons(&said, &other), buttons(&said, &own)), (vec![Some(Toggled::True)], vec![Some(Toggled::False)]));
        // the same in Compare, one choice for both
        app.mode = Mode::Compare;
        let (_, said) = w.settle(&mut app);
        assert_eq!(buttons(&said, &other), vec![Some(Toggled::True)], "Compare follows the menu chosen");
        let _ = w.click(&mut app, &said, Role::Button, &own);
        assert_eq!(app.menu_shown().as_deref(), Some(own.as_str()));
        let doc = app.doc.as_ref().unwrap();
        assert!(doc.edited.to_bytes() == before && doc.changes().is_empty() && app.undo.is_empty(), "a menu picked changes no byte of the file");
        // a file saved in the other menu's mode opens on that menu
        let (rec, code) = saved_in(&app, &other);
        let mut c = test_parse(SAMPLE_BYTES).unwrap();
        c.sections[0].get_mut(rec.id).unwrap().put(rec.index, code).unwrap();
        let f = dir.join("CAMSET02.DAT");
        std::fs::write(&f, c.to_bytes()).unwrap();
        app.mode = Mode::Edit;
        app.open(f);
        let (_, said) = w.settle(&mut app);
        assert_eq!(app.menu_shown().as_deref(), Some(other.as_str()));
        assert_eq!(buttons(&said, &other), vec![Some(Toggled::True)]);
        done(&dir, &user);
    }

    /// Compare's left bar is Edit's: All settings, then Edit's entries in the menu shown, each with how many rows it
    /// lists and, as its badge, how many of them differ; the menu's button counts its differences too. A click on an
    /// entry shows its rows alone, in the camera's layout of that menu; each menu lists the rows its own layout has.
    #[test]
    fn compare_has_edits_entries_with_the_rows_that_differ() {
        let (mut app, dir, user) = sample_app("e2_cmp", Some(stub_menus_and_a_place));
        let menu = app.menu_shown().unwrap();
        let edit = app.bar_keys(false, 0, Some(&menu), "", false);
        let tab = edit.iter().find(|k| matches!(k, BarKey::Tab(_))).unwrap().clone();
        // file B: one value changed, of a row of the first tab Compare lists in this menu
        let first = app.compare_rows(Some(&menu), &tab, "").iter().map(|r| r.2[0].clone()).find(|s| s.scalar && s.values.len() >= 2 && app.col_value(Col::a(0), s).is_some()).unwrap();
        let mut b = app.doc.as_ref().unwrap().original.clone();
        other_value(&app, &mut b, &first);
        app.compare = Some((PathBuf::from("B.DAT"), b));
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::b(0)], false);
        let mut w = Window::new();
        let (drawn, said) = w.settle(&mut app);
        let cols = app.cols.clone();
        let label = {
            let differs = |s: &Setting| app.row_differs(&cols, s);
            let entries = app.compare_bar(Some(&menu), "", &differs);
            assert_eq!(entries.iter().map(|e| e.key.clone()).collect::<Vec<_>>(), [vec![BarKey::All], edit.clone()].concat(), "Edit's entries, All settings first");
            for e in &entries {
                let rows = app.compare_rows(Some(&menu), &e.key, "");
                assert_eq!((e.count, e.badge), (Some(rows.len()), rows.iter().filter(|r| differs(&r.2[0])).count()), "{}", e.label);
                assert!(drawn.contains(&format!("{}  ({})", e.label, rows.len())), "{} drawn: {drawn:?}", e.label);
            }
            let badge = |k: &BarKey| entries.iter().find(|e| e.key == *k).unwrap().badge;
            assert!(badge(&BarKey::All) >= 1 && badge(&tab) >= 1, "the row that differs counts on All settings and on its tab");
            let at = app.menus().iter().position(|m| m.name == menu).unwrap();
            assert!(app.menu_differences("", &differs)[at] >= 1, "and on its menu's button");
            entries.iter().find(|e| e.key == tab).map(|e| format!("{}  ({})", e.label, e.count.unwrap())).unwrap()
        };
        // a click on the tab: its rows alone, as the camera's layout of this menu has them
        let _ = w.click(&mut app, &said, Role::Button, &label);
        assert_eq!(app.compare_key(), tab);
        let BarKey::Tab(t) = &tab else { unreachable!() };
        let rows = app.compare_rows(Some(&menu), &tab, "");
        assert_eq!(names(&app.matrix_rows()), names(&rows));
        assert!(rows.iter().all(|r| r.0 == *t) && app.mm_rows.len() == rows.len());
        // each menu its own rows: a row of Movie mode's menus only, placed in S&Q's otherwise than in Movie's
        let lists = |m: &str| app.compare_rows(Some(m), &BarKey::All, "").iter().any(|r| r.2.iter().any(|s| s.key == "global:0x02e9"));
        let modes_menus: Vec<String> = app.menus().iter().map(|m| m.name.clone()).collect();
        assert_eq!(modes_menus.iter().map(|m| lists(m)).collect::<Vec<_>>(), [false, true, true], "{modes_menus:?}");
        // an entry the menu shown no longer lists gives way to All settings
        app.compare_entry = BarKey::Tab("A tab of no menu".into());
        let _ = w.settle(&mut app);
        assert_eq!(app.compare_key(), BarKey::All);
        done(&dir, &user);
    }

    /// Two files saved in different modes are compared like for like in each menu: a row of a setting the camera keeps
    /// a copy of per mode is read, in both columns, from the record for the menu shown, whatever mode each file was
    /// saved in.
    #[test]
    fn files_saved_in_different_modes_compare_like_for_like() {
        let (mut app, dir, user) = sample_app("e2_like", Some(stub_menus));
        let (iso, own, other, copy) = iso_and_its_copy(&app);
        // file B saved in the other menu's mode, its ISO other than file A's, its copy for that menu as file A's
        let (rec, code) = saved_in(&app, &other);
        let mut b = app.doc.as_ref().unwrap().original.clone();
        b.sections[0].get_mut(rec.id).unwrap().put(rec.index, code).unwrap();
        other_value(&app, &mut b, &iso);
        app.compare = Some((PathBuf::from("B.DAT"), b.clone()));
        let cols = vec![Col::a(0), Col::b(0)];
        let row_of = |app: &App, m: &str| -> Row {
            let bound = app.row_record(&iso, m, &Bind::Menu).key.clone();
            app.compare_rows(Some(m), &BarKey::All, "").iter().find(|r| r.2[0].key == bound).cloned().unwrap()
        };
        // in the other menu both columns are read from its copy: the files agree there
        let r = row_of(&app, &other);
        assert_eq!(r.2[0].key, copy.key);
        assert!(!app.compare_rows(Some(&other), &BarKey::All, "").iter().any(|r| r.2[0].key == iso.key), "the setting itself is no row there");
        assert!(!app.row_differs(&cols, &r.2[0]), "like for like: {} agrees", r.2[0].name);
        // in the file's own menu, from the record for that menu: the setting itself differs
        let r = row_of(&app, &own);
        assert_eq!(app.row_differs(&cols, &r.2[0]), r.2[0].key == iso.key);
        // the copy for the other menu changed in file B: they differ there now
        other_value(&app, &mut b, &copy);
        app.compare = Some((PathBuf::from("B.DAT"), b));
        assert!(app.row_differs(&cols, &row_of(&app, &other).2[0]));
        // the window draws that menu's rows so: the copy's row, in both columns
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, cols, true);
        app.set_menu(&other);
        let mut w = Window::new();
        let _ = w.settle(&mut app);
        assert!(app.matrix_rows().iter().any(|r| r.2[0].key == copy.key));
        done(&dir, &user);
    }

    /// The "Editing:" row offers the live settings and the memory sets of the menu shown, outside Expert mode: Movie's
    /// memories in the Movie menu, not the dial's; the set edited stays offered in another menu; Expert mode and a
    /// definition without menus as before.
    #[test]
    fn the_menus_memory_sets_are_offered_outside_expert() {
        let (mut app, dir, user) = sample_app("e2_sets", Some(stub_menus));
        assert!(!app.prefs.expert);
        let movie: Vec<usize> = (1..app.n_sections()).filter(|&s| app.schema.camera.memory_mode(s) == Some("Movie")).collect();
        assert!(!movie.is_empty());
        app.set_menu("Movie");
        assert_eq!(app.editing_sets(), [vec![0], movie.clone()].concat());
        let mut w = Window::new();
        let (_, said) = w.settle(&mut app);
        for &s in &movie {
            assert_eq!(buttons(&said, &app.schema.camera.target_name(s)).len(), 1, "{}: {said:?}", app.schema.camera.target_name(s));
        }
        for s in app.dial_sets() {
            assert!(buttons(&said, &app.schema.camera.target_name(s)).is_empty(), "not in the Movie menu: {}", app.schema.camera.target_name(s));
        }
        let name = app.schema.camera.target_name(movie[0]);
        let _ = w.click(&mut app, &said, Role::Button, &name);
        assert_eq!((app.target, app.menu_shown().as_deref()), (movie[0], Some("Movie")));
        // another menu while a Movie memory is edited: its sets, and the one edited
        app.set_menu("Still");
        let offered = app.editing_sets();
        assert!(offered.contains(&movie[0]) && app.menu_sets(Some("Still")).iter().all(|s| offered.contains(s)), "{offered:?}");
        // Expert mode: the live settings and the dial's memories as buttons, the others in their list, as before
        app.prefs.expert = true;
        assert_eq!(app.editing_sets(), [vec![0], app.dial_sets()].concat());
        done(&dir, &user);
        let (app, dir, user) = sample_app("e2_sets_none", None);
        assert_eq!(app.editing_sets(), [vec![0], app.dial_sets()].concat(), "without menus as before");
        done(&dir, &user);
    }

    /// The Main page shows the tiles of the menu shown, where the definition ties a tile set to it, without its own
    /// buttons to pick a set; without menus, its buttons as before.
    #[test]
    fn main_shows_the_tiles_of_the_menu_shown() {
        let (mut app, dir, user) = sample_app("e2_main", Some(stub_menus));
        let sets = app.schema.camera.main_tiles.clone().unwrap().0;
        app.view = View::Main;
        let mut w = Window::new();
        for m in app.menus().to_vec() {
            app.set_menu(&m.name);
            let at = sets.iter().position(|s| Some(&s.name) == m.main_tiles.as_ref()).unwrap();
            assert_eq!(app.main_tile_set(), (at, false));
            let (_, said) = w.settle(&mut app);
            assert!(buttons(&said, &sets[0].name).is_empty(), "{}: no buttons of the Main page's own: {said:?}", m.name);
            // a tile only this set has
            let only = sets[at].tiles.iter().map(|t| t.caption.clone()).find(|c| sets.iter().enumerate().all(|(i, s)| i == at || s.tiles.iter().all(|t| t.caption != *c)));
            if let Some(c) = only {
                assert!(said.iter().any(|(_, r, l, _)| *r == Role::Button && l.starts_with(&format!("{c}: "))), "{}: {c}: {said:?}", m.name);
            }
        }
        done(&dir, &user);
        let (mut app, dir, user) = sample_app("e2_main_none", Some(strip_menus));
        app.view = View::Main;
        assert_eq!(app.main_tile_set(), (0, true));
        let (_, said) = Window::new().settle(&mut app);
        assert_eq!(buttons(&said, &sets[0].name).len(), 1, "without menus, the Main page's own buttons");
        done(&dir, &user);
    }

    /// Where a menu titles a row as the camera draws it, the detail panel names the setting in full.
    #[test]
    fn the_detail_panel_names_the_setting_in_full() {
        let (mut app, dir, user) = sample_app("e2_detail", Some(stub_menus));
        let (_, _, other, copy) = iso_and_its_copy(&app);
        app.set_menu(&other);
        // the record that menu's ISO row shows (a jump to the setting itself opens the file's mode's menu)
        app.go_to(&copy);
        assert_eq!(app.menu_shown(), Some(other));
        let title = app.item.clone().unwrap();
        assert!(title != copy.name, "the row titled as the camera draws it: {title}");
        let (drawn, _) = Window::new().settle(&mut app);
        assert!(drawn.contains(&title) && drawn.contains(&copy.name), "{title} and {} in {drawn:?}", copy.name);
        done(&dir, &user);
    }

    /// Compare's Open in Edit opens the setting in the menu Compare shows, and ← Back to Compare comes back to its row;
    /// a search's result opens the menu that shows it.
    #[test]
    fn jumps_open_the_menu_that_shows_the_setting() {
        let (mut app, dir, user) = sample_app("e2_jumps", Some(stub_menus));
        let (_, _, other, copy) = iso_and_its_copy(&app);
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::a(1)], false);
        app.set_menu(&other);
        let row = app.compare_rows(Some(&other), &BarKey::All, "").iter().find(|r| r.2[0].key == copy.key).cloned().unwrap();
        app.open_in_edit_from_compare(&row.2[0], 0);
        assert!(app.mode == Mode::Edit);
        assert_eq!((app.menu_shown().as_deref(), app.item_key.as_deref()), (Some(other.as_str()), Some(copy.key.as_str())));
        assert_eq!(app.from_compare.as_ref().map(|f| f.row.clone()), Some((row.0.clone(), copy.key.clone())));
        let mut w = Window::new();
        let _ = w.settle(&mut app);
        assert!(app.from_compare.is_some(), "Edit shows the setting it was given");
        app.back_to_compare();
        let _ = w.settle(&mut app);
        let at = app.compare_rows(Some(&other), &BarKey::All, "").iter().position(|r| r.2[0].key == copy.key);
        assert!(app.mode == Mode::Compare && app.diff_cursor == at, "back on its row");
        // the search: a setting only Movie mode's menus list, from Still's, opens the menu of the file's mode or the
        // first that lists it
        app.mode = Mode::Edit;
        app.set_menu("Still");
        let tc = app.schema.settings.iter().filter(|s| s.group == "TC/UB" && s.placed() && s.area == "global" && !s.expert)
            .find(|s| app.search_hits_in(0, Some("Still"), &s.name).iter().filter(|(h, _)| h.name == s.name).count() == 1).unwrap().clone();
        let to = app.search_hits_in(0, Some("Still"), &tc.name).into_iter().find(|(h, _)| h.key == tc.key).and_then(|(_, m)| m).unwrap();
        assert_ne!(to, "Still");
        (app.search, app.view) = (tc.name.clone(), View::Search);
        let (_, said) = w.settle(&mut app);
        // (egui tells a screen reader its link as the label it lays out)
        let _ = w.click(&mut app, &said, Role::Label, &tc.name);
        assert_eq!(app.menu_shown(), Some(to));
        assert!(app.search.is_empty() && matches!(app.view, View::Tab(_)));
        done(&dir, &user);
    }

    /// Up and Down, while the arrow keys move in the Menu, step through its own entries: Main, My Menu, every tab,
    /// Other and what the menus do not hold, with menus or without; in Compare All settings first, the arrows with Alt
    /// left to the differences.
    #[test]
    fn up_and_down_step_through_the_bars_own_entries() {
        for (tag, stub) in [("e2_keys", None), ("e2_keys_menus", Some(stub_menus as fn(&mut serde_json::Value)))] {
            let (mut app, dir, user) = sample_app(tag, stub);
            let menu = app.menu_shown();
            let keys = app.bar_keys(false, 0, menu.as_deref(), "", false);
            let off = BarKey::Tab(app.schema.camera.text.off_menu_name().to_string());
            assert!(keys[0] == BarKey::Main && keys[1] == BarKey::MyMenu && keys.last() == Some(&off), "{tag}: {keys:?}");
            let entry = |app: &App| match &app.view {
                View::Main => BarKey::Main,
                View::MyMenu => BarKey::MyMenu,
                View::Tab(t) => BarKey::Tab(t.clone()),
                _ => BarKey::All,
            };
            (app.view, app.focus) = (View::Main, Focus::Tabs);
            let mut w = Window::new();
            let _ = w.settle(&mut app);
            for k in &keys[1..] {
                w.key(&mut app, egui::Key::ArrowDown, false);
                assert_eq!(entry(&app), *k, "{tag}");
            }
            w.key(&mut app, egui::Key::ArrowDown, false);
            assert_eq!(entry(&app), off, "{tag}: the last stays");
            for k in keys[..keys.len() - 1].iter().rev() {
                w.key(&mut app, egui::Key::ArrowUp, false);
                assert_eq!(entry(&app), *k, "{tag}");
            }
            assert!(app.focus == Focus::Tabs);
            // Compare: a click on an entry, then the arrows
            (app.mode, app.cols) = (Mode::Compare, vec![Col::a(0), Col::a(1)]);
            let (_, said) = w.settle(&mut app);
            let ckeys = app.bar_keys(true, 0, menu.as_deref(), "", false);
            let all = format!("{ALL_SETTINGS}  ({})", app.compare_rows(menu.as_deref(), &BarKey::All, "").len());
            let _ = w.click(&mut app, &said, Role::Button, &all);
            assert!(app.compare_key() == BarKey::All && app.focus == Focus::Tabs);
            w.key(&mut app, egui::Key::ArrowDown, false);
            assert_eq!(app.compare_key(), ckeys[1], "{tag}");
            w.key(&mut app, egui::Key::ArrowDown, true);
            assert_eq!(app.compare_key(), ckeys[1], "{tag}: Alt+Down is the next difference");
            w.key(&mut app, egui::Key::ArrowUp, false);
            assert_eq!(app.compare_key(), BarKey::All, "{tag}");
            done(&dir, &user);
        }
    }
}
