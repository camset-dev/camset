//! The keyboard: the shortcuts, the arrow keys between the menu's columns, and F3 through the edits.

use crate::*;

/// One step (`step` = -1 or 1) from `pos` in a list of `len` entries, kept inside the list; None when the list is
/// empty (a tab with no groups shown, a definition with no tabs).
pub(crate) fn step_in(len: usize, pos: usize, step: i32) -> Option<usize> {
    let last = len.checked_sub(1)?;
    Some((pos as i64 + step as i64).clamp(0, last as i64) as usize)
}

/// Which of the menu columns the arrow keys move in.
#[derive(Clone, Copy, Debug, PartialEq)]
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

/// Collapse all, in Edit and Compare (`App::fold_all`): Cmd/Ctrl+Shift+↑, the page's too. Arrows sit in the same place
/// on every keyboard layout; the editor has no other use for them with these modifiers, and outside a text field (which
/// keeps them for selecting) no browser or desktop it runs on is known to take them.
pub(crate) const KEY_COLLAPSE_ALL: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND.plus(egui::Modifiers::SHIFT), egui::Key::ArrowUp);

/// Expand all, in Edit and Compare (`App::fold_all`): Cmd/Ctrl+Shift+↓, the page's too.
pub(crate) const KEY_EXPAND_ALL: egui::KeyboardShortcut = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND.plus(egui::Modifiers::SHIFT), egui::Key::ArrowDown);

/// The search box's id (Edit and Compare have one each, never both on screen): Cmd/Ctrl+F focuses it.
pub(crate) const SEARCH_ID: &str = "search_box";

impl App {
    /// Arrow keys in Edit: Left/Right pick the column (the Menu's entries, groups, items), from a tab's page or from
    /// Main's and My Menu's, where Left takes the Menu's; Up/Down move inside the groups' column here. Up/Down in the
    /// Menu's column are `bar_nav`'s, which runs first and takes them (in Edit and Compare); the items' are menu_view's.
    pub(crate) fn keyboard_nav(&mut self, ctx: &egui::Context) {
        if self.mode != Mode::Edit || ctx.wants_keyboard_input() {
            return;
        }
        let tab = match self.view.clone() {
            View::Tab(t) => Some(t),
            View::Main | View::MyMenu => None,
            _ => return,
        };
        let (left, right, up, down) = ctx.input(|i| (
            i.key_pressed(egui::Key::ArrowLeft), i.key_pressed(egui::Key::ArrowRight),
            i.key_pressed(egui::Key::ArrowUp), i.key_pressed(egui::Key::ArrowDown),
        ));
        if left {
            self.focus = match self.focus { Focus::Items if tab.is_some() => Focus::Groups, _ => Focus::Tabs };
        }
        if right && tab.is_some() {
            self.focus = match self.focus { Focus::Tabs => Focus::Groups, _ => Focus::Items };
        }
        let step: i32 = if down { 1 } else if up { -1 } else { 0 };
        let (Some(tab), Focus::Groups) = (tab, self.focus) else { return };
        if step == 0 {
            return;
        }
        let groups: Vec<String> = self.tab_groups(&tab).into_iter().map(|(n, _, _)| n).collect();
        let pos = groups.iter().position(|g| Some(g) == self.group.as_ref()).unwrap_or(0);
        if let Some(g) = step_in(groups.len(), pos, step).and_then(|i| groups.get(i)).cloned() {
            self.select(None, Some(g), None);
        }
    }

    /// Collapse all and Expand all by the keys (`KEY_COLLAPSE_ALL`, `KEY_EXPAND_ALL`, `fold_all`), taken before the
    /// arrows move anything (`bar_nav`, `keyboard_nav`), only where something folds (Compare's table, a tab of Edit); a
    /// text field with the keyboard keeps them for its text, and an open menu or list for itself.
    pub(crate) fn fold_keys(&mut self, ctx: &egui::Context) {
        let here = matches!(self.mode, Mode::Compare) && !self.compare_records || matches!((self.mode, &self.view), (Mode::Edit, View::Tab(_)));
        if self.doc.is_none() || !here || ctx.wants_keyboard_input() || ctx.memory(|m| m.any_popup_open()) {
            return;
        }
        let collapse = ctx.input_mut(|i| i.consume_shortcut(&KEY_COLLAPSE_ALL));
        let expand = ctx.input_mut(|i| i.consume_shortcut(&KEY_EXPAND_ALL));
        if collapse || expand {
            self.fold_all(collapse);
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
            // Changes opens from Settings > About, over it, but the status bar's version brings Settings back over it:
            // of the two, the one on top
            else if self.show_changes && !(self.show_settings && settings_over_changes(ctx)) { self.show_changes = false; }
            else if self.show_settings { self.show_settings = false; }
            else if self.toast.is_some() { self.toast = None; }
            else if !self.search.is_empty() {
                self.search.clear();
                if self.view == View::Search { self.view = View::Main; }
            }
        }
    }

    /// Edit mode: go to the next (`dir` 1) or previous (-1) edited setting of the set being edited, in menu order. Where
    /// the Menu shows the camera's menus, each edit in the menu a jump to it opens from the set's own menu
    /// (`jump_place`), the menus in their order, and the step shows that menu.
    pub(crate) fn step_edit(&mut self, dir: i32) {
        let Some(doc) = &self.doc else { return };
        let in_set = self.target != 0;
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
        let menus: Vec<String> = self.menus().iter().map(|m| m.name.clone()).collect();
        let bind = self.bind_for(self.target);
        // in the order the rows are drawn (`menu_at`, a menu's `rank_in`); one row per setting and place, its records together
        let at = self.menu_at();
        let place = |s: &Setting| format!("{:?}{:?}{:?}{:?}", s.row, s.row_at, s.under_option, s.row_mode);
        // by the Menu entry that shows it (`entry_of`): a place of My Menu on the My Menu page, though the place itself is
        // Expert-only, and a setting the camera's menus do not hold under the entry for those, after the tabs
        let off = self.schema.camera.text.off_menu_name();
        type Edit = (usize, usize, i64, String, String, String, String, String, Option<String>);
        let mut edits: Vec<Edit> = doc.changes().into_iter()
            .filter(|(si, _)| *si == self.target)
            .filter_map(|(_, id)| self.schema.find(in_set, id))
            .filter(|s| self.prefs.expert || !Self::expert_only(s) || self.is_mymenu_place(s))
            .map(|s| {
                let (menu, entry, group) = self.jump_place(s, self.target, None);
                let menu_at = menu.as_ref().and_then(|m| menus.iter().position(|x| x == m)).unwrap_or(0);
                let shown = match &menu { Some(m) => self.listed_record(s, self.target, m), None => s.clone() };
                let rank = match &menu { Some(m) => self.rank_in(m, &bind).get(&s.key).copied().unwrap_or(s.order), None => at(s) };
                let entry = if self.is_mymenu_place(s) { self.schema.camera.text.my_menu_name().to_string() } else { entry };
                (menu_at, if entry == off { usize::MAX } else { tab_idx(self.layout_tab(&shown)) }, rank, entry, group, shown.name.clone(), place(&shown), shown.key.clone(), menu)
            })
            .collect();
        edits.sort();
        edits.dedup_by(|a, b| (a.0, &a.3, &a.4, &a.5, &a.6) == (b.0, &b.3, &b.4, &b.5, &b.6));
        if edits.is_empty() {
            self.status = format!("No edits in {}", self.schema.camera.target_name(self.target));
            return;
        }
        // the edit shown now, in the menu shown, on the page that shows its tab (`shown_view`: My Menu's tab on the My
        // Menu page, a tab the definition does not list under Other), and of two rows of one name the one `item_key` names
        let now = self.menu_shown();
        let selected_place = self.item_key.as_ref().and_then(|k| edits.iter().find(|e| &e.7 == k)).map(|e| e.6.clone())
            .or_else(|| self.item_key.as_ref().and_then(|k| self.schema.settings.iter().find(|s| &s.key == k)).map(place));
        let here = edits.iter().position(|e| e.8 == now && self.shown_view(View::Tab(e.3.clone())) == self.view && Some(&e.4) == self.group.as_ref() && Some(&e.5) == self.item.as_ref()
            && selected_place.as_ref().is_none_or(|p| *p == e.6 || !edits.iter().any(|o| o.5 == e.5 && o.4 == e.4 && o.6 == *p)));
        let n = edits.len();
        let k = match (here, dir > 0) {
            (Some(i), true) => (i + 1) % n,
            (Some(i), false) => (i + n - 1) % n,
            (None, true) => 0,
            (None, false) => n - 1,
        };
        let (_, _, _, tab, group, name, _, key, menu) = edits[k].clone();
        if let Some(m) = menu.filter(|m| Some(m) != now.as_ref()) {
            self.menu = Some(MenuChoice { name: m, target: self.target, opened: self.doc.as_ref().map_or(0, |d| d.opened) });
        }
        self.status = format!("Edit {} of {n}: {}", k + 1, self.schema.settings.iter().find(|s| s.key == key).map_or(name.clone(), |s| s.name.clone()));
        self.select(Some(self.shown_view(View::Tab(tab))), Some(group), Some((&name, &key)));
        self.focus = Focus::Items;
    }
}
