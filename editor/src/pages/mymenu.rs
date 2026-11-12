//! My Menu as the camera shows it: its pages and places, adding, removing, moving and changing items.

use crate::*;

/// One place on a My Menu page as the My Menu page shows it (`mymenu_places`): the menu-item code it holds, the
/// camera's name for that item (from the places' value lists), the settings that carry the code (`menu_code`), the
/// one the item opens leading, and whether the place was changed since the file was opened, with what it held then.
pub(crate) struct MyMenuPlace {
    pub(crate) code: i64,
    pub(crate) empty: bool,
    pub(crate) name: String,
    pub(crate) settings: Vec<Setting>,
    pub(crate) edited: bool,
    pub(crate) was: String,
}

/// One item a place of My Menu can hold (`mymenu_items`): its menu-item code, the camera's name for it, and the tab of
/// the setting that carries it, None when no setting the Menu shows does.
#[derive(Clone)]
pub(crate) struct MyMenuItem {
    pub(crate) code: i64,
    pub(crate) name: String,
    pub(crate) tab: Option<String>,
}

impl App {
    /// My Menu: one array record per page in the live settings (camera.my_menu).
    pub(crate) fn mymenu_pages(&self) -> Option<Vec<Vec<i64>>> {
        let mm = self.schema.camera.my_menu.as_ref().filter(|m| !m.records.is_empty())?;
        let doc = self.doc.as_ref()?;
        let sec = doc.edited.sections.first()?;
        mm.records.iter().map(|&id| {
            let r = sec.get(id)?;
            Some((0..r.count).map(|i| r.get(Some(i)).unwrap_or(mm.empty)).collect())
        }).collect()
    }

    /// My Menu has a page of its own in the Menu, under Main: the definition names its records (`camera.my_menu`).
    /// A file without them still opens the page, which says so.
    pub(crate) fn has_mymenu_page(&self) -> bool {
        self.schema.camera.my_menu.as_ref().is_some_and(|m| !m.records.is_empty())
    }

    /// My Menu's pages as the My Menu page shows them (`MyMenuPlace`), from the live settings. An item is named as
    /// the camera names it: the label of its code in its place's value list (any place's when its own has none),
    /// else the name of a setting that carries the code. The setting an item opens leads its settings: the one named
    /// as the camera names the item, then one with a record of its own before an element of a list, then the first
    /// in menu order; the records of one setting (one name in one group) count once. Only settings the Menu shows
    /// in the live settings are carried.
    pub(crate) fn mymenu_places(&self) -> Option<Vec<Vec<MyMenuPlace>>> {
        let pages = self.mymenu_pages()?;
        let mm = self.schema.camera.my_menu.as_ref()?;
        let doc = self.doc.as_ref()?;
        let lists: std::collections::HashMap<(u16, Option<u16>), &Setting> = self.schema.settings.iter()
            .filter(|s| mm.records.contains(&s.id) && !s.values.is_empty()).map(|s| ((s.id, s.index), s)).collect();
        let any_list = self.schema.settings.iter().find(|s| mm.records.contains(&s.id) && !s.values.is_empty());
        let mut carriers: std::collections::HashMap<i64, Vec<&Setting>> = Default::default();
        for s in self.settings_in(0, None) {
            if let Some(c) = s.menu_code { carriers.entry(c).or_default().push(s); }
        }
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
        let label = |slot: Slot, code: i64| lists.get(&slot).copied().or(any_list).and_then(|s| s.label_for(code)).map(str::to_string);
        // what a place holds, in words: the camera's name for the item, else a setting's, else its code
        let named = |slot: Slot, code: i64, settings: &[Setting]| label(slot, code)
            .or_else(|| settings.first().map(|s| s.name.clone()))
            .unwrap_or_else(|| if code == mm.empty { "(empty)".into() } else { format!("an item the editor has no name for yet (code {code})") });
        let carried = |code: i64, name: Option<&str>| {
            let mut v: Vec<Setting> = carriers.get(&code).map(|v| v.iter().map(|s| (*s).clone()).collect()).unwrap_or_default();
            v.sort_by_key(|s| (Some(s.name.as_str()) != name, s.index.is_some(), tab_idx(&s.tab), s.order));
            let mut seen = std::collections::HashSet::new();
            v.retain(|s| seen.insert((s.tab.clone(), s.group.clone(), s.name.clone())));
            v
        };
        Some(pages.iter().enumerate().map(|(p, page)| page.iter().enumerate().map(|(i, &code)| {
            let slot = (mm.records[p], Some(i as u16));
            let empty = code == mm.empty;
            let settings = if empty { Vec::new() } else { carried(code, label(slot, code).as_deref()) };
            let was = doc.original_value(0, slot).unwrap_or(mm.empty);
            let was_words = if was == code { String::new() } else { named(slot, was, &carried(was, label(slot, was).as_deref())) };
            MyMenuPlace { code, empty, name: named(slot, code, &settings), settings, edited: was != code, was: was_words }
        }).collect()).collect())
    }

    /// How many of My Menu's places hold an item, and how many it has (`my_menu.max_items`, else every place of its
    /// pages); None when the file holds no My Menu.
    pub(crate) fn mymenu_used(&self) -> Option<(usize, usize)> {
        let pages = self.mymenu_pages()?;
        let mm = self.schema.camera.my_menu.as_ref()?;
        let max = if mm.max_items > 0 { mm.max_items } else { pages.iter().map(Vec::len).sum() };
        Some((pages.iter().flatten().filter(|&&c| c != mm.empty).count(), max))
    }

    /// My Menu's entry in the Menu: its name with how many places hold an item, and its hover.
    pub(crate) fn mymenu_entry_words(&self) -> (String, String) {
        let name = self.schema.camera.text.my_menu_name();
        match self.mymenu_used() {
            Some((n, max)) => (format!("{name}  ({n})"), format!("{name} as the camera shows it: {n} of its {max} places hold an item")),
            None => (name.to_string(), format!("{name} as the camera shows it")),
        }
    }

    /// Edits to My Menu, as its Menu entry counts them: the places changed and the settings of its own tab changed, in
    /// the live settings.
    pub(crate) fn mymenu_edits(&self) -> usize {
        let (Some(doc), Some(mm)) = (&self.doc, &self.schema.camera.my_menu) else { return 0 };
        let places = mm.records.iter().filter_map(|&id| Some((doc.edited.sections.first()?.get(id)?, doc.original.sections.first()?.get(id)?)))
            .map(|(a, b)| (0..a.count.min(b.count)).filter(|&i| a.get(Some(i)) != b.get(Some(i))).count()).sum::<usize>();
        let name = self.schema.camera.text.my_menu_name();
        places + self.settings_in(0, Some(name)).filter(|s| doc.value(0, s.slot()) != doc.original_value(0, s.slot())).count()
    }

    /// The My Menu page's lines over its pages: how many places hold an item, and how an item is added (any item with
    /// a page's "Add here…", or another put in a place with its "Change…", or from a setting); `right_click` names the
    /// window's way to a setting (a right-click on it), else the web page's (its name, right-clicked or opened).
    pub(crate) fn mymenu_lead(&self, right_click: bool) -> String {
        let name = self.schema.camera.text.my_menu_name();
        let used = match self.mymenu_used() { Some((n, max)) => format!("{n} of {max} places hold an item. "), None => String::new() };
        let how = if right_click { "right-click a setting in its menu" } else { "right-click a setting's name in its menu, or click the name to unfold it," };
        format!("{used}To add any of the camera's items, use \"Add here…\" on a page; \"Change…\" puts another item in a place. Or {how} and choose Add to {name}.")
    }

    /// Said on the My Menu page for a file that does not hold its records.
    pub(crate) fn mymenu_missing(&self) -> String {
        format!("This file does not hold {}'s pages, so they cannot be shown here.", self.schema.camera.text.my_menu_name())
    }

    /// Said on the My Menu page while a memory (`target`) is the set being edited: My Menu is part of the live
    /// settings.
    pub(crate) fn mymenu_memory_note(&self, target: usize) -> Option<String> {
        (target != 0).then(|| format!("{} is part of the live settings, not of a memory, so this page shows and changes the live settings; the other pages still edit {}.",
            self.schema.camera.text.my_menu_name(), self.schema.camera.target_name(target)))
    }

    /// The settings of My Menu's own tab (`text.my_menu_name`) by group, in menu order, the records of one setting
    /// (one name in one group) linked into one row, as the My Menu page shows them for the live settings.
    pub(crate) fn mymenu_groups(&self) -> Vec<(String, Vec<Vec<Setting>>)> {
        if !self.has_mymenu_page() {
            return Vec::new();
        }
        let mut list: Vec<&Setting> = self.settings_in(0, Some(self.schema.camera.text.my_menu_name())).collect();
        list.sort_by_key(|s| s.order);
        let mut groups: Vec<(String, Vec<Vec<Setting>>)> = Vec::new();
        for s in list {
            let g = self.shown_group_of(s);
            let at = match groups.iter().position(|(x, _)| *x == g) {
                Some(at) => at,
                None => { groups.push((g, Vec::new())); groups.len() - 1 }
            };
            // one setting kept in several records: the same name in the same place on the camera, as in a tab
            match groups[at].1.iter_mut().find(|r| r[0].links_with(s)) {
                Some(r) => r.push(s.clone()),
                None => groups[at].1.push(vec![s.clone()]),
            }
        }
        groups
    }

    /// Where a menu item sits in My Menu: (page, slot), both from 0.
    pub(crate) fn mymenu_find(&self, code: i64) -> Option<(usize, usize)> {
        let pages = self.mymenu_pages()?;
        pages.iter().enumerate().find_map(|(p, v)| v.iter().position(|&c| c == code).map(|i| (p, i)))
    }

    /// Actions that add a menu item to the first page with room, after the items already there
    /// (the camera keeps each page packed from the top).
    pub(crate) fn mymenu_add(&self, code: i64) -> Result<(Vec<Action>, String), String> {
        let name = self.schema.camera.text.my_menu_name();
        if let Some((p, i)) = self.mymenu_find(code) {
            return Err(format!("Already in {name} (page {}, item {})", p + 1, i + 1));
        }
        let pages = self.mymenu_pages().ok_or(format!("This file has no {name} records"))?;
        let Some(mm) = &self.schema.camera.my_menu else { return Err(format!("This camera has no {name}")) };
        // as many items as the camera takes (`max_items`), which can be fewer than its pages' places, as `mymenu_set` keeps
        if let Some((n, max)) = self.mymenu_used().filter(|(n, max)| n >= max) {
            return Err(format!("{name} is full ({n} of {max} items). Remove one first."));
        }
        for (p, v) in pages.iter().enumerate() {
            if let Some(i) = v.iter().position(|&c| c == mm.empty) {
                return Ok((vec![Action::Set(0, (mm.records[p], Some(i as u16)), code)], format!("Added to {name} page {}, item {}; save, or write to the camera, to keep it", p + 1, i + 1)));
            }
        }
        let max = if mm.max_items > 0 { mm.max_items } else { pages.iter().map(Vec::len).sum() };
        Err(format!("{name} is full ({max} items). Remove one first."))
    }

    /// Actions that remove a menu item: on a camera that keeps its pages packed (`my_menu.packed`, the default),
    /// the items after it move up to close the gap; else only its slot is emptied.
    pub(crate) fn mymenu_remove(&self, code: i64) -> Option<(Vec<Action>, String)> {
        let (p, at) = self.mymenu_find(code)?;
        let pages = self.mymenu_pages()?;
        let mm = self.schema.camera.my_menu.as_ref()?;
        let v: Vec<i64> = if mm.packed {
            let mut v: Vec<i64> = pages[p].iter().copied().filter(|&c| c != code).collect();
            v.resize(pages[p].len(), mm.empty);
            v
        } else {
            let mut v = pages[p].clone();
            v[at] = mm.empty;
            v
        };
        let id = mm.records[p];
        let acts = v.iter().enumerate().filter(|(i, c)| pages[p][*i] != **c).map(|(i, c)| Action::Set(0, (id, Some(i as u16)), *c)).collect();
        Some((acts, format!("Removed from {} page {}; save, or write to the camera, to keep it", self.schema.camera.text.my_menu_name(), p + 1)))
    }

    /// Actions that move the item in place `i` of page `p` one place up (`by` -1) or down (1) on its page, swapping it
    /// with its neighbour, as the camera sorts My Menu's items; on a camera that keeps its pages packed
    /// (`my_menu.packed`) only past another item, so no gap opens. None: it cannot move that way.
    pub(crate) fn mymenu_move(&self, p: usize, i: usize, by: isize) -> Option<(Vec<Action>, String)> {
        let pages = self.mymenu_pages()?;
        let mm = self.schema.camera.my_menu.as_ref()?;
        let j = i.checked_add_signed(by)?;
        let (a, b) = (*pages.get(p)?.get(i)?, *pages.get(p)?.get(j)?);
        if a == mm.empty || (mm.packed && b == mm.empty) {
            return None;
        }
        let id = mm.records[p];
        Some((vec![Action::Set(0, (id, Some(j as u16)), a), Action::Set(0, (id, Some(i as u16)), b)],
            format!("Moved to {} page {}, item {}; save, or write to the camera, to keep it", self.schema.camera.text.my_menu_name(), p + 1, j + 1)))
    }

    /// Every item a place of My Menu can hold, in the camera's order: the codes and the camera's names for them in
    /// its places' value lists (the empty place's code left out), each with the settings the Menu shows that carry
    /// it (`menu_code`), the first by tab and menu order leading, so an item a setting carries says where it is; the
    /// items of the tab the camera keeps out of My Menu (`text.mymenu_excluded_tab`) are left out.
    pub(crate) fn mymenu_items(&self) -> Vec<MyMenuItem> {
        let Some(mm) = self.schema.camera.my_menu.as_ref() else { return Vec::new() };
        let excluded = self.schema.camera.text.mymenu_excluded_tab.as_deref().filter(|t| !t.is_empty());
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
        let mut carriers: std::collections::HashMap<i64, Vec<&Setting>> = Default::default();
        for s in self.schema.settings.iter().filter(|s| s.area == "global") {
            if let Some(c) = s.menu_code { carriers.entry(c).or_default().push(s); }
        }
        let mut seen = std::collections::HashSet::new();
        let mut out = Vec::new();
        for s in self.schema.settings.iter().filter(|s| s.area == "global" && mm.records.contains(&s.id)) {
            for (code, label) in &s.values {
                if *code == mm.empty || !seen.insert(*code) { continue; }
                let mut on: Vec<&Setting> = carriers.get(code).cloned().unwrap_or_default();
                if excluded.is_some_and(|x| on.iter().any(|c| c.tab == x)) { continue; }
                on.retain(|c| self.prefs.expert || !Self::expert_only(c));
                on.sort_by_key(|c| (tab_idx(&c.tab), c.order));
                out.push(MyMenuItem { code: *code, name: label.clone(), tab: on.first().map(|c| c.tab.clone()) });
            }
        }
        out
    }

    /// What the My Menu page's item pickers say about the items they leave out: the camera's reason for the tab it
    /// keeps out of My Menu (`text.mymenu_excluded_reason`, else said from the tab's name); None when it keeps none out.
    pub(crate) fn mymenu_excluded_words(&self) -> Option<String> {
        let txt = &self.schema.camera.text;
        let t = txt.mymenu_excluded_tab.as_deref().filter(|t| !t.is_empty())?;
        Some(txt.mymenu_excluded_reason.clone().filter(|w| !w.is_empty()).unwrap_or_else(|| format!("This camera does not allow {t} items in {}", txt.my_menu_name())))
    }

    /// Actions that put the item `code` in place `i` of page `p`, as the camera's own "add here" does: an item already
    /// there is replaced where it stands, so no gap opens; an empty place on a camera that keeps its pages packed
    /// (`my_menu.packed`) takes it after the page's items (the page's first empty place), else in that place; the
    /// empty code takes the item out (`mymenu_remove`). An item already elsewhere in My Menu, one of the tab the camera
    /// keeps out, a full My Menu (`max_items`) and a place the file does not hold are refused, and say why.
    pub(crate) fn mymenu_set(&self, p: usize, i: usize, code: i64) -> Result<(Vec<Action>, String), String> {
        let name = self.schema.camera.text.my_menu_name();
        let pages = self.mymenu_pages().ok_or(format!("This file has no {name} records"))?;
        let Some(mm) = &self.schema.camera.my_menu else { return Err(format!("This camera has no {name}")) };
        let held = *pages.get(p).and_then(|v| v.get(i)).ok_or(format!("{name} has no page {}, item {}", p + 1, i + 1))?;
        if code == mm.empty {
            return if held == mm.empty { Err("This place is already empty.".into()) } else { self.mymenu_remove(held).ok_or(format!("Not in {name}")) };
        }
        if code == held {
            return Err("This place already holds that item.".into());
        }
        let items = self.mymenu_items();
        let Some(item) = items.iter().find(|x| x.code == code) else {
            return Err(self.mymenu_excluded_words().unwrap_or_else(|| format!("{name} cannot hold that item.")));
        };
        if let Some((q, j)) = self.mymenu_find(code) {
            return Err(format!("{} is already in {name} (page {}, item {}). Remove it there first, or move it.", item.name, q + 1, j + 1));
        }
        let id = mm.records[p];
        if held != mm.empty {
            let was = items.iter().find(|x| x.code == held).map(|x| x.name.clone()).unwrap_or_else(|| format!("code {held}"));
            return Ok((vec![Action::Set(0, (id, Some(i as u16)), code)],
                format!("{name} page {}, item {} now holds {} in place of {was}; save, or write to the camera, to keep it", p + 1, i + 1, item.name)));
        }
        if let Some((n, max)) = self.mymenu_used().filter(|(n, max)| n >= max) {
            return Err(format!("{name} is full ({n} of {max} items). Remove one first."));
        }
        let at = if mm.packed { pages[p].iter().position(|&c| c == mm.empty).unwrap_or(i) } else { i };
        Ok((vec![Action::Set(0, (id, Some(at as u16)), code)], format!("Added {} to {name} page {}, item {}; save, or write to the camera, to keep it", item.name, p + 1, at + 1)))
    }

    /// The window's item picker of place `i` of page `p` (holding `held`): a drop-down of every item My Menu can hold
    /// (`mymenu_items`), narrowed by the words typed into its filter box, each with the tab of the setting that carries
    /// it, the items already in My Menu greyed out with where they are; the item chosen, if any. The words typed are
    /// kept with the window (one filter for every place), and let go once an item is chosen.
    fn mymenu_pick(&self, ui: &mut egui::Ui, items: &[MyMenuItem], p: usize, i: usize, held: Option<&str>, enabled: bool) -> Option<i64> {
        let name = self.schema.camera.text.my_menu_name().to_string();
        let pages = self.mymenu_pages().unwrap_or_default();
        let where_in = |code: i64| pages.iter().enumerate().find_map(|(q, v)| v.iter().position(|&c| c == code).map(|j| (q, j)));
        let weak = tone::weak(ui.visuals());
        let excluded = self.mymenu_excluded_words();
        let mut chosen = None;
        let filter_id = egui::Id::new("mymenu_filter");
        let mut filter: String = ui.data(|d| d.get_temp(filter_id)).unwrap_or_default();
        ui.add_enabled_ui(enabled, |ui| {
            let label = if held.is_some() { "Change…" } else { "Add here…" };
            let r = egui::ComboBox::from_id_salt(("mymenu_pick", p, i)).width(110.0).height(320.0)
                .close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside)
                .selected_text(label)
                .show_ui(ui, |ui| {
                    ui.set_min_width(300.0);
                    named(ui.add(egui::TextEdit::singleline(&mut filter).hint_text("Type to filter the items")), "Filter the items");
                    if let Some(why) = &excluded { ui.label(RichText::new(why).small().color(weak)); }
                    let q = filter.trim().to_lowercase();
                    let mut shown = 0;
                    for x in items.iter().filter(|x| q.is_empty() || x.name.to_lowercase().contains(&q) || x.tab.as_ref().is_some_and(|t| t.to_lowercase().contains(&q))) {
                        shown += 1;
                        let there = where_in(x.code);
                        let text = match (&x.tab, there) {
                            (_, Some((a, b))) => format!("{}   (in {name} {}, item {})", x.name, a + 1, b + 1),
                            (Some(t), None) => format!("{}   ({t})", x.name),
                            (None, None) => x.name.clone(),
                        };
                        let r = ui.add_enabled(there.is_none(), egui::Button::new(text).frame(false));
                        if r.clicked() {
                            chosen = Some(x.code);
                            ui.memory_mut(|m| m.close_popup());
                        }
                    }
                    if shown == 0 { ui.label(RichText::new("No item matches.").color(weak)); }
                });
            let hover = match held {
                Some(h) => format!("Put another item in place of {h}: any item {name} can hold, not only the settings shown in the menus"),
                None => format!("Add an item to this page of {name}: it goes after the page's items, as on the camera"),
            };
            r.response.on_hover_text(hover);
        });
        if chosen.is_some() { filter.clear(); }
        ui.data_mut(|d| d.insert_temp(filter_id, filter));
        chosen
    }

    /// The right-click menu of a setting row: Add to / Remove from My Menu, like the camera's trash-button menu.
    pub(crate) fn mymenu_context(&mut self, resp: &egui::Response, s: &Setting, actions: &mut Vec<Action>) {
        if self.mymenu_pages().is_none() { return; }
        let txt = &self.schema.camera.text;
        let name = txt.my_menu_name().to_string();
        let excluded = txt.mymenu_excluded_tab.clone().filter(|t| !t.is_empty()).map(|t| {
            let why = txt.mymenu_excluded_reason.clone().filter(|w| !w.is_empty()).unwrap_or_else(|| format!("This camera does not allow {t} items in {name}"));
            (t, why)
        });
        let editable = self.editable();
        let code = s.menu_code;
        let mut msg: Option<String> = None;
        resp.context_menu(|ui| {
            match code {
                Some(c) => {
                    if let Some((p, i)) = self.mymenu_find(c) {
                        ui.label(RichText::new(format!("In {name}: page {}, item {}", p + 1, i + 1)).color(tone::weak(ui.visuals())));
                        if ui.add_enabled(editable, egui::Button::new(format!("Remove from {name}"))).clicked() {
                            if let Some((a, m)) = self.mymenu_remove(c) { actions.extend(a); msg = Some(m); }
                            ui.close_menu();
                        }
                    } else if ui.add_enabled(editable, egui::Button::new(format!("Add to {name}"))).clicked() {
                        match self.mymenu_add(c) { Ok((a, m)) => { actions.extend(a); msg = Some(m); } Err(e) => msg = Some(e) }
                        ui.close_menu();
                    }
                }
                None => {
                    ui.add_enabled(false, egui::Button::new(format!("Add to {name}")))
                        .on_disabled_hover_text(match &excluded { Some((t, why)) if s.tab == *t => why.clone(), _ => format!("This item has no {name} entry on the camera (it is part of another item's screen)") });
                }
            }
        });
        if let Some(m) = msg { self.status = m; }
    }

    /// My Menu as the camera shows it (`View::MyMenu`): each page's places in order, an item by the camera's name for
    /// it, as a link that opens the setting it opens, with that setting's value, Remove and Move up / Move down; then
    /// the settings of My Menu's own tab by group, to change as in any group. Always the live settings, as My Menu
    /// is not part of a memory.
    pub(crate) fn mymenu_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let mut actions = Vec::new();
        let name = self.schema.camera.text.my_menu_name().to_string();
        ui.heading(&name);
        let Some(doc) = &self.doc else {
            ui.label(format!("Open a settings file to see its {name}."));
            return actions;
        };
        let weak = tone::weak(ui.visuals());
        if let Some(note) = self.mymenu_memory_note(self.target) {
            ui.label(note);
        }
        let editable = self.editable();
        // what was clicked: an item's setting to open, an item to take out, a move (its actions and what it says)
        let mut go: Option<Setting> = None;
        let mut remove: Option<i64> = None;
        let mut moved: Option<(Vec<Action>, String)> = None;
        // an item put in a place with its picker: the place and the item's code
        let mut put: Option<(usize, usize, i64)> = None;
        let items = self.mymenu_items();
        let packed = self.schema.camera.my_menu.as_ref().is_some_and(|m| m.packed);
        match self.mymenu_places() {
            None => { ui.label(self.mymenu_missing()); }
            Some(pages) => {
                ui.label(RichText::new(self.mymenu_lead(true)).small().color(weak));
                for (p, places) in pages.iter().enumerate() {
                    // a packed page takes a new item after its items: its first empty place has the picker
                    let first_empty = places.iter().position(|x| x.empty);
                    ui.add_space(8.0);
                    ui.label(RichText::new(format!("{name} {}  ({})", p + 1, places.iter().filter(|x| !x.empty).count())).strong());
                    egui::Grid::new(("mymenu_page", p)).striped(true).num_columns(4).spacing([14.0, 4.0]).show(ui, |ui| {
                        for (i, place) in places.iter().enumerate() {
                            // an edited place in the edit colour and marked, as any edit; what it held on hover
                            let ink = if place.edited { tone::edit(ui.visuals()) } else { ui.visuals().text_color() };
                            let mark = if place.edited { format!("{EDIT_MARK} ") } else { String::new() };
                            let was = if place.edited { format!("\nWas: {}", place.was) } else { String::new() };
                            ui.label(RichText::new((i + 1).to_string()).color(weak));
                            if place.empty {
                                ui.label(RichText::new(format!("{mark}{}", place.name)).italics().color(if place.edited { ink } else { weak })).on_hover_text(format!("An empty place{was}"));
                                ui.label("");
                                if !packed || first_empty == Some(i) {
                                    if let Some(code) = self.mymenu_pick(ui, &items, p, i, None, editable) { put = Some((p, i, code)); }
                                } else {
                                    ui.label("");
                                }
                                ui.end_row();
                                continue;
                            }
                            ui.horizontal(|ui| {
                                let text = RichText::new(format!("{mark}{}", place.name)).color(ink);
                                match place.settings.first() {
                                    Some(s) => {
                                        if ui.link(text).on_hover_text(format!("Click to open {} in its menu ({}){was}", s.name, self.where_shown(s))).clicked() {
                                            go = Some(s.clone());
                                        }
                                    }
                                    None => { ui.label(text).on_hover_text(format!("No setting the editor knows belongs to this item, so it has no value to show{was}")); }
                                }
                                if place.settings.len() > 1 {
                                    let more: Vec<String> = place.settings[1..].iter().map(|s| format!("{} > {} > {}", s.tab, s.group, s.name)).collect();
                                    ui.label(RichText::new(format!("and {} more", more.len())).small().color(weak)).on_hover_text(format!("The item holds these settings too:\n{}", more.join("\n")));
                                }
                            });
                            // the value as the search results show it; one the file does not hold is said, not dashed
                            match place.settings.first() {
                                Some(s) if s.text.is_some() || doc.value(0, s.slot()).is_some() => { ui.label(self.row_value_in(0, s)); }
                                Some(_) => { ui.label(RichText::new("not held in this file").color(weak)); }
                                None => { ui.label(""); }
                            }
                            ui.horizontal(|ui| {
                                if let Some(code) = self.mymenu_pick(ui, &items, p, i, Some(&place.name), editable) { put = Some((p, i, code)); }
                                let r = ui.add_enabled(editable, egui::Button::new("Remove").small()).on_hover_text(format!("Take {} out of {name}", place.name));
                                if r.clicked() { remove = Some(place.code); }
                                for (glyph, by, words) in [("⬆", -1, "Move up"), ("⬇", 1, "Move down")] {
                                    let to = self.mymenu_move(p, i, by);
                                    let r = named(ui.add_enabled(editable && to.is_some(), egui::Button::new(glyph).small()), words).on_hover_text(words);
                                    if r.clicked() { moved = to; }
                                }
                            });
                            ui.end_row();
                        }
                    });
                }
            }
        }
        // the settings of My Menu's own tab, by group, as the camera lists them after its pages
        let groups = self.mymenu_groups();
        let mut pick: Option<(String, String)> = None;
        if !groups.is_empty() {
            ui.add_space(12.0);
            ui.separator();
            let scrolled = egui::Id::new("mymenu_scrolled");
            for (group, rows) in &groups {
                ui.add_space(6.0);
                ui.label(RichText::new(group).strong());
                egui::Grid::new(("mymenu_group", group)).striped(true).num_columns(3).spacing([18.0, 4.0]).show(ui, |ui| {
                    for row in rows {
                        let s = &row[0];
                        let edited = row.iter().any(|l| doc.value(0, l.slot()) != doc.original_value(0, l.slot()));
                        // the setting a jump (next edit, a link) opened: marked, and brought into view once
                        let here = self.group.as_deref() == Some(group.as_str()) && self.item.as_deref() == Some(s.name.as_str());
                        let mut text = RichText::new(if edited { format!("{EDIT_MARK} {}", self.setting_title(s)) } else { self.setting_title(s) });
                        if edited { text = text.color(tone::edit(ui.visuals())).strong(); }
                        let hover = if s.note.is_empty() { self.where_kept(s) } else { format!("{}\n{}", self.where_kept(s), s.note) };
                        let r = ui.selectable_label(here, text).on_hover_text(hover);
                        let key = format!("{group}\n{}", s.name);
                        if here && ui.data(|d| d.get_temp::<String>(scrolled)).as_ref() != Some(&key) {
                            r.scroll_to_me(Some(egui::Align::Center));
                            ui.data_mut(|d| d.insert_temp(scrolled, key));
                        }
                        if r.clicked() { pick = Some((group.clone(), s.name.clone())); }
                        let mut set = Vec::new();
                        self.compact_editor_in(ui, 0, s, editable, &mut set);
                        // a setting kept in several records changes in all of them, as in its tab (`set_linked`)
                        for a in set {
                            if let Action::Set(_, _, v) = a { actions.extend(Self::set_linked(0, row, v)); }
                        }
                        if edited && ui.small_button("Revert").clicked() {
                            actions.extend(row.iter().map(|l| Action::Revert(0, l.slot())));
                        } else if !edited {
                            ui.label("");
                        }
                        ui.end_row();
                    }
                });
            }
        }
        if let Some(code) = remove {
            if let Some((a, said)) = self.mymenu_remove(code) { actions.extend(a); self.status = said; }
        }
        if let Some((a, said)) = moved {
            actions.extend(a);
            self.status = said;
        }
        if let Some((p, i, code)) = put {
            match self.mymenu_set(p, i, code) {
                Ok((a, said)) => { actions.extend(a); self.status = said; }
                Err(why) => self.status = why,
            }
        }
        if let Some((g, i)) = pick {
            (self.group, self.item) = (Some(g), Some(i));
        }
        if let Some(s) = go {
            self.open_in_menu(&s);
        }
        actions
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// "Add to My Menu" from a setting stops at the number of items the camera takes (`my_menu.max_items`), also when
    /// that is fewer than its pages' places, as a place's own "Add here…" does (`mymenu_set`).
    #[test]
    fn adding_stops_at_the_cameras_limit() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        // one item at least (added when the sample holds none): a limit of 0 is no limit, every place
        if app.mymenu_used().expect("the sample holds My Menu").0 == 0 {
            let code = app.mymenu_items().into_iter().map(|x| x.code).find(|c| app.mymenu_find(*c).is_none()).unwrap();
            let (acts, _) = app.mymenu_add(code).unwrap();
            app.apply(acts);
        }
        let (used, places) = app.mymenu_used().expect("the sample holds My Menu");
        assert!(used < places, "room left on the sample's pages");
        let code = app.mymenu_items().into_iter().map(|x| x.code).find(|c| app.mymenu_find(*c).is_none()).expect("an item not in My Menu");
        assert!(app.mymenu_add(code).is_ok(), "room on the pages and under the limit");
        // a camera that takes no more items than the sample holds, though its pages have room
        app.schema.camera.my_menu.as_mut().unwrap().max_items = used;
        let e = app.mymenu_add(code).map(|_| ()).unwrap_err();
        assert!(e.contains("is full") && e.contains(&format!("{used} of {used}")), "{e}");
        let (p, i) = app.mymenu_pages().unwrap().iter().enumerate()
            .find_map(|(p, v)| v.iter().position(|&c| c == app.schema.camera.my_menu.as_ref().unwrap().empty).map(|i| (p, i))).unwrap();
        assert!(app.mymenu_set(p, i, code).map(|_| ()).unwrap_err().contains("is full"), "the same limit for Add here…");
    }

    /// The My Menu page as the camera shows My Menu: each page's places in order, an item named by the places' value
    /// lists and opening the setting named so first; Move up / Move down swap an item with its neighbour (past
    /// another item only, on a camera that keeps its pages packed); the places changed count as My Menu's edits and
    /// are marked with what they held; next edit lands on a setting of My Menu's own tab on the My Menu page, and a
    /// jump to that tab opens the page.
    #[test]
    fn my_menu_page_as_the_camera_shows_it() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let mm = app.schema.camera.my_menu.clone().unwrap();
        let name = app.schema.camera.text.my_menu_name().to_string();
        // two items at the top of the first page (added when the sample holds fewer), taken as the file opened
        while app.mymenu_pages().unwrap()[0].iter().filter(|&&c| c != mm.empty).count() < 2 {
            let code = app.schema.settings.iter().filter_map(|s| s.menu_code).find(|&c| app.mymenu_find(c).is_none()).unwrap();
            let (acts, _) = app.mymenu_add(code).unwrap();
            app.apply(acts);
        }
        let doc = app.doc.as_mut().unwrap();
        doc.original = doc.edited.clone();
        let pages = app.mymenu_places().unwrap();
        assert_eq!(pages.len(), mm.records.len());
        let held = pages.iter().flatten().filter(|x| !x.empty).count();
        assert_eq!(app.mymenu_used(), Some((held, mm.max_items)));
        assert_eq!(app.mymenu_entry_words().0, format!("{name}  ({held})"));
        assert!(app.mymenu_lead(true).starts_with(&format!("{held} of {} places hold an item. To add any of the camera's items, use \"Add here…\"", mm.max_items)));
        let list = app.schema.settings.iter().find(|s| s.id == mm.records[0] && !s.values.is_empty()).unwrap();
        for x in pages.iter().flatten() {
            assert!(!x.edited && x.empty == (x.code == mm.empty), "{}", x.name);
            if let Some(label) = list.label_for(x.code) {
                assert_eq!(x.name, label);
            }
            if let Some(s) = x.settings.first() {
                assert!(s.menu_code == Some(x.code) && s.area == "global" && !s.expert, "{}", s.name);
                if x.settings.iter().any(|o| o.name == x.name) {
                    assert_eq!(s.name, x.name, "the setting named as the item leads");
                }
            }
        }
        // Move up / Move down
        let before = app.mymenu_pages().unwrap()[0].clone();
        assert!(app.mymenu_move(0, 0, -1).is_none(), "the first item does not move up");
        let (acts, said) = app.mymenu_move(0, 0, 1).unwrap();
        assert_eq!(said, format!("Moved to {name} page 1, item 2; save, or write to the camera, to keep it"));
        app.apply(acts);
        let after = app.mymenu_pages().unwrap()[0].clone();
        assert_eq!((after[0], after[1], &after[2..]), (before[1], before[0], &before[2..]));
        let places = app.mymenu_places().unwrap().swap_remove(0);
        assert!(places[0].edited && places[1].edited && places[2..].iter().all(|x| !x.edited));
        assert_eq!((&places[0].was, app.mymenu_edits()), (&places[1].name, 2));
        assert!(app.mymenu_move(0, after.len() - 1, 1).is_none(), "the last place does not move down");
        // the last item of a page with room after it
        let room = app.mymenu_pages().unwrap().iter().enumerate()
            .find_map(|(p, v)| v.iter().rposition(|&c| c != mm.empty).filter(|&last| last + 1 < v.len()).map(|last| (p, last)));
        if let Some((p, last)) = room {
            assert!(app.mymenu_move(p, last, 1).is_none(), "on a packed page an item moves past no empty place");
            assert!(app.mymenu_move(p, last + 1, -1).is_none(), "an empty place does not move");
            app.schema.camera.my_menu.as_mut().unwrap().packed = false;
            assert!(app.mymenu_move(p, last, 1).is_some(), "a camera that keeps no pages packed takes it");
            app.schema.camera.my_menu.as_mut().unwrap().packed = true;
        }
        // a setting of My Menu's own tab: next edit lands on it on the My Menu page, and steps on from there
        let own = app.settings_in(0, Some(&name)).find(|s| s.scalar && s.offered(false).len() >= 2 && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none()).cloned().unwrap();
        let doc = app.doc.as_ref().unwrap();
        let cur = doc.value(0, own.slot()).unwrap();
        let other = own.offered(false).into_iter().map(|(v, _)| v).find(|&v| v != cur).unwrap();
        app.apply(vec![Action::Set(0, own.slot(), other)]);
        assert_eq!(app.mymenu_edits(), 3);
        app.view = View::Main;
        for _ in 0..3 {
            app.step_edit(1);
            if app.item.as_deref() == Some(own.name.as_str()) { break; }
        }
        assert_eq!((&app.view, app.group.as_deref(), app.item.as_deref()), (&View::MyMenu, Some(own.group.as_str()), Some(own.name.as_str())));
        app.step_edit(1);
        assert_ne!(app.item.as_deref(), Some(own.name.as_str()), "the next edit, not the same one again");
        // a jump that names My Menu's tab opens the My Menu page, which draws for the live settings and for a memory
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        for target in [0, 1] {
            app.target = target;
            app.view = View::Tab(name.clone());
            let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
            assert_eq!(app.view, View::MyMenu);
            assert_eq!(app.mymenu_memory_note(target).is_some(), target != 0);
        }
        app.view = View::Tab("A tab of no list".into());
        let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
        assert_eq!(app.view, View::Tab(OTHER_TAB.into()));
    }

    /// Every place of the My Menu page takes any item the camera's places can hold (`mymenu_items`, read from the
    /// places' value lists while the place settings are Expert-only), not only the items some setting carries: an item
    /// in a place is replaced where it stands, an empty place of a packed page takes it after the page's items (of a
    /// page kept unpacked, in that place), an item already in My Menu, one of the tab the camera keeps out and a full
    /// My Menu are refused and say why, and the empty code takes the item out. The places changed are edits, which
    /// undo and revert put back.
    #[test]
    fn my_menu_places_take_any_item() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let mm = app.schema.camera.my_menu.clone().unwrap();
        let name = app.schema.camera.text.my_menu_name().to_string();
        let slots: Vec<&Setting> = app.schema.settings.iter().filter(|s| s.area == "global" && mm.records.contains(&s.id)).collect();
        assert!(!app.prefs.expert && slots.len() == 42 && slots.iter().all(|s| s.expert), "the places are Expert-only");
        assert!(app.settings_in(0, None).all(|s| !mm.records.contains(&s.id)), "and out of the default view");
        let items = app.mymenu_items();
        let codes: std::collections::BTreeSet<i64> = slots[0].values.iter().map(|(c, _)| *c).filter(|&c| c != mm.empty).collect();
        assert_eq!(items.len(), codes.len(), "every item of the places' lists, the empty place's left out");
        assert!(items.len() > 200 && items.iter().all(|x| x.code != mm.empty && !x.name.is_empty()));
        let carried: std::collections::HashSet<i64> = app.schema.settings.iter().filter_map(|s| s.menu_code).collect();
        let free = items.iter().find(|x| !carried.contains(&x.code) && app.mymenu_find(x.code).is_none()).cloned().unwrap();
        assert!(free.tab.is_none(), "no setting carries it, so it names no tab");
        let held_one = items.iter().find(|x| x.tab.is_some()).unwrap();
        assert!(app.schema.tabs.contains(held_one.tab.as_ref().unwrap()));
        // two items at the top of the first page, the rest of it empty, as the file opened
        let empty_page: Vec<Action> = (0..7u16).map(|i| Action::Set(0, (mm.records[0], Some(i)), mm.empty)).collect();
        app.apply(empty_page);
        let two: Vec<i64> = items.iter().filter(|x| carried.contains(&x.code) && app.mymenu_find(x.code).is_none()).take(2).map(|x| x.code).collect();
        app.apply(vec![Action::Set(0, (mm.records[0], Some(0)), two[0]), Action::Set(0, (mm.records[0], Some(1)), two[1])]);
        let doc = app.doc.as_mut().unwrap();
        doc.original = doc.edited.clone();
        // an item no setting carries in place of the first: replaced where it stands, shown by its name alone
        let (acts, said) = app.mymenu_set(0, 0, free.code).unwrap();
        assert_eq!(acts.len(), 1);
        assert!(said.starts_with(&format!("{name} page 1, item 1 now holds {} in place of", free.name)), "{said}");
        app.apply(acts);
        let page = app.mymenu_places().unwrap().swap_remove(0);
        assert_eq!((page[0].code, page[0].name.as_str(), page[0].settings.len(), page[0].edited), (free.code, free.name.as_str(), 0, true));
        assert_eq!(app.mymenu_edits(), 1, "marked as any edit");
        // an empty place of a packed page: after the page's items, whichever empty place was chosen
        let third = items.iter().find(|x| app.mymenu_find(x.code).is_none()).unwrap().code;
        let (acts, said) = app.mymenu_set(0, 5, third).unwrap();
        assert!(matches!(acts[..], [Action::Set(0, (r, Some(2)), c)] if r == mm.records[0] && c == third), "{said}");
        assert!(said.contains("page 1, item 3"), "{said}");
        app.schema.camera.my_menu.as_mut().unwrap().packed = false;
        let (acts, _) = app.mymenu_set(0, 5, third).unwrap();
        assert!(matches!(acts[..], [Action::Set(0, (_, Some(5)), _)]), "a page kept unpacked takes it in that place");
        app.schema.camera.my_menu.as_mut().unwrap().packed = true;
        // refused, and said
        assert!(app.mymenu_set(0, 2, two[1]).err().unwrap().contains("already in My Menu (page 1, item 2)"));
        assert_eq!(app.mymenu_set(0, 1, two[1]).err().unwrap(), "This place already holds that item.");
        assert!(app.mymenu_set(9, 0, third).is_err() && app.mymenu_set(0, 9, third).is_err(), "no such place");
        let used = app.mymenu_used().unwrap().0;
        app.schema.camera.my_menu.as_mut().unwrap().max_items = used;
        assert!(app.mymenu_set(0, 2, third).err().unwrap().starts_with(&format!("{name} is full")));
        assert!(app.mymenu_set(0, 1, third).is_ok(), "a full My Menu still takes an item in place of another");
        app.schema.camera.my_menu.as_mut().unwrap().max_items = mm.max_items;
        // the empty code takes the item out, the page kept packed
        let (acts, _) = app.mymenu_set(0, 0, mm.empty).unwrap();
        app.apply(acts);
        assert_eq!(&app.mymenu_pages().unwrap()[0][..2], &[two[1], mm.empty]);
        assert_eq!(app.mymenu_set(0, 3, mm.empty).err().unwrap(), "This place is already empty.");
        // undo puts the item back, and revert puts the file's item back
        app.undo();
        assert_eq!(app.mymenu_pages().unwrap()[0][0], free.code);
        app.apply(vec![Action::Revert(0, (mm.records[0], Some(0)))]);
        assert_eq!((app.mymenu_pages().unwrap()[0][0], app.mymenu_edits()), (two[0], 0));
        // the tab the camera keeps out: its items are not offered, and an item of it is refused with the camera's reason
        let tab = held_one.tab.clone().unwrap();
        app.schema.camera.text.mymenu_excluded_tab = Some(tab.clone());
        let kept = app.mymenu_items();
        assert!(kept.len() < items.len() && kept.iter().all(|x| x.tab.as_deref() != Some(tab.as_str())));
        assert_eq!(app.mymenu_set(0, 2, held_one.code).err().unwrap(), app.mymenu_excluded_words().unwrap());
        // a camera without My Menu offers none
        app.schema.camera.my_menu = None;
        assert!(app.mymenu_items().is_empty() && app.mymenu_set(0, 0, free.code).is_err());
    }
}
