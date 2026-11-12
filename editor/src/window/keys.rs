//! The keyboard: the shortcuts, the arrow keys between the menu's columns, and F3 through the edits.

use crate::*;

/// One step (`step` = -1 or 1) from `pos` in a list of `len` entries, kept inside the list; None when the list is
/// empty (a tab with no groups shown, a definition with no tabs).
pub(crate) fn step_in(len: usize, pos: usize, step: i32) -> Option<usize> {
    let last = len.checked_sub(1)?;
    Some((pos as i64 + step as i64).clamp(0, last as i64) as usize)
}

/// Which of the menu columns the arrow keys move in.
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum Focus {
    Tabs,
    Groups,
    Items,
}

/// The keyboard shortcuts (`App::shortcuts`), named once so the menus and Settings show the same keys.
pub(crate) const KEY_OPEN: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::O);

pub(crate) const KEY_SAVE: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::S);

pub(crate) const KEY_FIND: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::F);

pub(crate) const KEY_CLOSE: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::W);

pub(crate) const KEY_READ: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::R);

pub(crate) const KEY_SETTINGS: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::Comma);

/// The search box's id (Edit and Compare have one each, never both on screen): Cmd/Ctrl+F focuses it.
pub(crate) const SEARCH_ID: &str = "search_box";

impl App {
    /// Arrow keys: Left/Right pick the column (tabs, groups, items); Up/Down move inside it.
    /// Items are handled in menu_view; tabs and groups here.
    pub(crate) fn keyboard_nav(&mut self, ctx: &egui::Context) {
        if self.mode != Mode::Edit || ctx.wants_keyboard_input() {
            return;
        }
        let View::Tab(tab) = self.view.clone() else { return };
        let (left, right, up, down) = ctx.input(|i| (
            i.key_pressed(egui::Key::ArrowLeft), i.key_pressed(egui::Key::ArrowRight),
            i.key_pressed(egui::Key::ArrowUp), i.key_pressed(egui::Key::ArrowDown),
        ));
        if left {
            self.focus = match self.focus { Focus::Items => Focus::Groups, _ => Focus::Tabs };
        }
        if right {
            self.focus = match self.focus { Focus::Tabs => Focus::Groups, _ => Focus::Items };
        }
        let step: i32 = if down { 1 } else if up { -1 } else { 0 };
        if step == 0 {
            return;
        }
        match self.focus {
            Focus::Tabs => {
                let tabs = self.schema.tabs.clone();
                let pos = tabs.iter().position(|t| *t == tab).unwrap_or(0);
                if let Some(t) = step_in(tabs.len(), pos, step).and_then(|i| tabs.get(i)) {
                    self.view = View::Tab(t.clone());
                    self.group = None;
                }
            }
            Focus::Groups => {
                let groups: Vec<String> = self.tab_groups(&tab).into_iter().map(|(n, _, _)| n).collect();
                let pos = groups.iter().position(|g| Some(g) == self.group.as_ref()).unwrap_or(0);
                if let Some(g) = step_in(groups.len(), pos, step).and_then(|i| groups.get(i)) {
                    self.group = Some(g.clone());
                    self.item = None;
                }
            }
            Focus::Items => {}
        }
    }

    /// The keyboard shortcuts besides undo, zoom and the arrows (listed in Settings > Appearance): open, save,
    /// search, close, read, Settings, the next or previous edit (Edit mode), and Esc, which closes the topmost
    /// window or, with none open, clears the search.
    pub(crate) fn shortcuts(&mut self, ctx: &egui::Context) {
        let pressed = |s: &egui::KeyboardShortcut| ctx.input_mut(|i| i.consume_shortcut(s));
        if pressed(&KEY_OPEN) { self.ask(ctx, DialogKind::OpenA, None); }
        if pressed(&KEY_SAVE) && self.can_save_as() { self.save_as(ctx); }
        if pressed(&KEY_FIND) && self.doc.is_some() { ctx.memory_mut(|m| m.request_focus(egui::Id::new(SEARCH_ID))); }
        if pressed(&KEY_CLOSE) { self.close_file(); }
        if pressed(&KEY_READ) && self.have_helper() && self.camera_job.is_none() {
            if self.prefs.link.is_empty() { self.show_connect = true; } else { self.start_camera_job(None); }
        }
        if pressed(&KEY_SETTINGS) { self.show_settings = !self.show_settings; }
        if self.mode == Mode::Edit && !ctx.wants_keyboard_input() {
            let (next, prev) = ctx.input(|i| (i.key_pressed(egui::Key::F3) && !i.modifiers.shift, i.key_pressed(egui::Key::F3) && i.modifiers.shift));
            if next { self.step_edit(1); }
            if prev { self.step_edit(-1); }
        }
        // an open menu or list takes Esc itself
        if !ctx.memory(|m| m.any_popup_open()) && ctx.input_mut(|i| i.consume_key(egui::Modifiers::NONE, egui::Key::Escape)) {
            if self.camera_report.is_some() { self.camera_report = None; }
            else if self.show_unchecked { self.show_unchecked = false; }
            else if self.show_connect { self.show_connect = false; }
            else if self.show_history { self.show_history = false; }
            else if self.show_backups { self.show_backups = false; }
            else if self.show_log { self.show_log = false; }
            else if self.show_settings { self.show_settings = false; }
            else if self.toast.is_some() { self.toast = None; }
            else if !self.search.is_empty() {
                self.search.clear();
                if self.view == View::Search { self.view = View::Main; }
            }
        }
    }

    /// Edit mode: go to the next (`dir` 1) or previous (-1) edited setting of the set being edited, in menu order.
    pub(crate) fn step_edit(&mut self, dir: i32) {
        let Some(doc) = &self.doc else { return };
        let in_set = self.target != 0;
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
        // in the order the rows are drawn (`menu_at`); one row per setting and place, its records together
        let at = self.menu_at();
        let place = |s: &Setting| format!("{:?}{:?}{:?}{:?}", s.row, s.row_at, s.under_option, s.row_mode);
        // by the Menu entry that shows it (`entry_of`): a place of My Menu on the My Menu page, though the place itself is
        // Expert-only, and a setting the camera's menus do not hold under the entry for those, after the tabs
        let off = self.schema.camera.text.off_menu_name();
        let entry = |s: &Setting| if self.is_mymenu_place(s) { self.schema.camera.text.my_menu_name().to_string() } else { self.entry_of(s) };
        let mut edits: Vec<(usize, i64, String, String, String, String, String)> = doc.changes().into_iter()
            .filter(|(si, _)| *si == self.target)
            .filter_map(|(_, id)| self.schema.find(in_set, id))
            .filter(|s| self.prefs.expert || !Self::expert_only(s) || self.is_mymenu_place(s))
            .map(|s| { let e = entry(s); (if e == off { usize::MAX } else { tab_idx(self.layout_tab(s)) }, at(s), e, self.shown_group_of(s), s.name.clone(), place(s), s.key.clone()) })
            .collect();
        edits.sort();
        edits.dedup_by(|a, b| (&a.2, &a.3, &a.4, &a.5) == (&b.2, &b.3, &b.4, &b.5));
        if edits.is_empty() {
            self.status = format!("No edits in {}", self.schema.camera.target_name(self.target));
            return;
        }
        // the edit shown now, on the page that shows its tab (`shown_view`: My Menu's tab on the My Menu page, a tab
        // the definition does not list under Other), and of two rows of one name the one `item_key` names
        let selected_place = self.item_key.as_ref().and_then(|k| self.schema.settings.iter().find(|s| &s.key == k)).map(place);
        let here = edits.iter().position(|e| self.shown_view(View::Tab(e.2.clone())) == self.view && Some(&e.3) == self.group.as_ref() && Some(&e.4) == self.item.as_ref()
            && selected_place.as_ref().is_none_or(|p| *p == e.5 || !edits.iter().any(|o| o.4 == e.4 && o.3 == e.3 && o.5 == *p)));
        let n = edits.len();
        let k = match (here, dir > 0) {
            (Some(i), true) => (i + 1) % n,
            (Some(i), false) => (i + n - 1) % n,
            (None, true) => 0,
            (None, false) => n - 1,
        };
        let (_, _, tab, group, name, _, key) = edits[k].clone();
        self.status = format!("Edit {} of {n}: {name}", k + 1);
        self.view = self.shown_view(View::Tab(tab));
        self.group = Some(group);
        self.item = Some(name);
        self.item_key = Some(key);
        self.focus = Focus::Items;
    }
}
