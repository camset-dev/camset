//! Where a setting is shown: the Menu's entries and pages, a tab's groups and rows as on the camera or as a flat list,
//! and the sets of the file a page shows.

use crate::*;

/// A tab's colour from the camera definition (camera.tab_colors); grey when not listed.
pub(crate) fn tab_color(cam: &Camera, tab: &str) -> Color32 {
    cam.tab_colors.get(tab).map_or(Color32::GRAY, |[r, g, b]| Color32::from_rgb(*r, *g, *b))
}

/// A tab's colour for text, darkened on the light theme so it reads on white.
pub(crate) fn tab_ink(v: &egui::Visuals, cam: &Camera, tab: &str) -> Color32 {
    tone::readable(v, tab_color(cam, tab))
}

/// The Menu's entry for the settings of the tabs the definition does not list (`menu_entry_of`).
pub(crate) const OTHER_TAB: &str = "Other";

/// Edit: the camera-menu columns for one file. Compare: the long-form side-by-side list.
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum Mode {
    Edit,
    Compare,
}

#[derive(Clone, Debug, PartialEq)]
pub(crate) enum View {
    Main,
    Tab(String),
    Changes,
    /// Memories 1-3 beside the live settings, with recall / register.
    Memories,
    /// My Menu as the camera shows it (camera.my_menu): its pages and items, then the settings of its own tab.
    MyMenu,
    /// The exposure triangle per column (camera.exposure).
    Exposure,
    /// Matches of the search box across every tab.
    Search,
    Unmapped,
    /// Every record of the section in file order, mapped or not.
    Records,
}

impl View {
    /// The name the preferences keep the page by (`Prefs::view`): a tab's own name for a tab; a search is kept as Main.
    pub(crate) fn key(&self) -> &str {
        match self {
            View::Main | View::Search => "Main",
            View::Changes => "Changes",
            View::Unmapped => "Unmapped",
            View::Records => "Records",
            View::Memories => "Memories",
            View::MyMenu => "MyMenu",
            View::Exposure => "Exposure",
            View::Tab(t) => t,
        }
    }

    /// The page a name the preferences kept stands for (`key`): one of `tabs`, the definition's, for a tab name; the
    /// pages for mapping work only in Expert mode (`expert`). None for a name that is none of them.
    pub(crate) fn from_key(key: &str, expert: bool, tabs: &[String]) -> Option<View> {
        Some(match key {
            "Main" => View::Main,
            "Changes" => View::Changes,
            "Memories" => View::Memories,
            "MyMenu" => View::MyMenu,
            "Exposure" => View::Exposure,
            "Unmapped" | "Records" if !expert => return None,
            "Unmapped" => View::Unmapped,
            "Records" => View::Records,
            t if tabs.iter().any(|x| x == t) => View::Tab(t.to_string()),
            _ => return None,
        })
    }
}

/// Each setting's position in the camera's order, by key (`menu_rank`).
pub(crate) type MenuRank = std::rc::Rc<std::collections::HashMap<String, i64>>;

/// The groups the camera's menus hold, as on the camera, by tab (`placed_groups`).
pub(crate) type PlacedGroups = std::rc::Rc<std::collections::HashMap<String, std::collections::HashSet<String>>>;

impl App {
    /// Edited settings, for the settings of one Menu entry (or all: `in_entry`). File B shows only in Compare mode.
    pub(crate) fn counts(&self, tab: Option<&str>) -> usize {
        let Some(d) = &self.doc else { return 0 };
        let in_set = self.target != 0;
        let in_entry = self.in_entry(tab);
        // My Menu's places count on its own entry (`mymenu_edits`), not on a tab's
        self.schema.settings.iter().filter(|s| in_entry(s)).filter(|s| if in_set { s.in_sets } else { s.area == "global" })
            .filter(|s| tab.is_none() || !self.is_mymenu_place(s))
            .filter(|s| d.value(self.target, s.slot()) != d.original_value(self.target, s.slot()))
            .count()
    }

    /// Sections in the open file (live settings plus memory sets); 1 when no file is open.
    pub(crate) fn n_sections(&self) -> usize {
        self.doc.as_ref().map_or(1, |d| d.edited.sections.len().max(1))
    }

    /// The mode-dial memories the camera definition names that this file holds.
    pub(crate) fn dial_sets(&self) -> Vec<usize> {
        let n = self.n_sections();
        self.schema.camera.dial().iter().copied().filter(|s| *s >= 1 && *s < n).collect()
    }

    /// Sections offered as columns: the live settings and the dial memories, every set in expert mode.
    pub(crate) fn shown_sections(&self) -> Vec<usize> {
        if self.prefs.expert { (0..self.n_sections()).collect() } else { std::iter::once(0).chain(self.dial_sets()).collect() }
    }

    /// Derived working copies, flags and alternate numberings, as the definition marks them: shown only in expert
    /// mode.
    pub(crate) fn expert_only(s: &Setting) -> bool {
        s.expert
    }

    fn matches_search(&self, s: &Setting) -> bool {
        self.search.is_empty() || Self::matches_query(s, &self.search.to_lowercase())
    }

    /// The name, group or a value label holds `q` (lower case).
    pub(crate) fn matches_query(s: &Setting, q: &str) -> bool {
        s.name.to_lowercase().contains(q) || s.group.to_lowercase().contains(q) || s.values.iter().any(|(_, l)| l.to_lowercase().contains(q))
    }

    /// The Menu entry that shows the settings of `tab`: a tab the definition lists is its own entry, My Menu's tab
    /// (`text.my_menu_name`) is the My Menu page's when the definition has My Menu, and any other tab is shown under
    /// "Other" (`OTHER_TAB`), so no setting is out of the Menu's reach.
    pub(crate) fn menu_entry_of<'a>(&self, tab: &'a str) -> &'a str {
        let my_menu = self.has_mymenu_page() && tab == self.schema.camera.text.my_menu_name();
        if my_menu || self.schema.tabs.iter().any(|t| t == tab) || tab == self.schema.camera.text.off_menu_name() { tab } else { OTHER_TAB }
    }

    /// Whether a setting is shown under the Menu entry `tab` (None: any): one of its own tab, or, under an entry the
    /// definition does not list ("Other"), one of a tab it gathers (`menu_entry_of`); as on the camera, a setting the
    /// camera's menus do not hold (`off_menu_in`) only under the entry for those (`text.off_menu_name`), and that
    /// entry only those.
    fn in_entry(&self, tab: Option<&str>) -> impl Fn(&Setting) -> bool {
        let gathers = tab.is_some_and(|t| !self.schema.tabs.iter().any(|x| x == t));
        let placed = (tab.is_some() && self.camera_layout()).then(|| self.placed_groups());
        let off = self.schema.camera.text.off_menu_name();
        move |s| tab.is_none_or(|t| {
            let away = placed.as_ref().is_some_and(|p| self.off_menu_in(s, p));
            // as on the camera in the tab whose menu holds its row (`layout_tab`)
            let tab = self.layout_tab(s);
            if t == off { away } else { !away && (tab == t || (gathers && self.menu_entry_of(tab) == t)) }
        })
    }

    /// The groups the camera's menus hold, as on the camera: the tab (`menu_rows::camera_tab`) and the camera group
    /// (`menu_rows::camera_group`) of every setting the definition places on a row of the camera. Worked out once per
    /// definition.
    pub(crate) fn placed_groups(&self) -> PlacedGroups {
        if let Some((generation, set)) = &*self.placed_cache.borrow() {
            if *generation == self.schema_gen {
                return set.clone();
            }
        }
        let mut by_tab: std::collections::HashMap<String, std::collections::HashSet<String>> = Default::default();
        for s in self.schema.settings.iter().filter(|s| s.placed()) {
            by_tab.entry(menu_rows::camera_tab(s).to_string()).or_default().insert(menu_rows::camera_group(s).to_string());
        }
        let set: PlacedGroups = std::rc::Rc::new(by_tab);
        *self.placed_cache.borrow_mut() = Some((self.schema_gen, set.clone()));
        set
    }

    /// Whether `s` is one of the settings the camera's menus do not hold, given the groups they do (`placed_groups`):
    /// a setting of a tab the definition lists on no row of the camera, whose group has no setting on one either (a
    /// group with some keeps the others under "More settings in this group"), and not of a family shown as one table
    /// (`camera.families`), nor of My Menu's own tab, which its page shows. Only the definition's places decide it;
    /// the layout is not asked here (`off_menu`).
    fn off_menu_in(&self, s: &Setting, placed: &std::collections::HashMap<String, std::collections::HashSet<String>>) -> bool {
        !s.placed() && self.schema.tabs.contains(&s.tab)
            && !(self.has_mymenu_page() && s.tab == self.schema.camera.text.my_menu_name())
            && !self.schema.camera.families.iter().any(|f| !f.prefix.is_empty() && s.group.starts_with(&f.prefix))
            && !placed.get(&s.tab).is_some_and(|g| g.contains(&s.group))
    }

    /// Whether `s` is shown under the Menu's entry for what the camera's menus do not hold (`text.off_menu_name`): as
    /// on the camera only (`off_menu_in`); the flat list keeps every setting in its tab.
    pub(crate) fn off_menu(&self, s: &Setting) -> bool {
        self.camera_layout() && self.off_menu_in(s, &self.placed_groups())
    }

    /// The Menu entry that shows `s` in the layout in use: the entry for what the camera's menus do not hold
    /// (`off_menu`), else the entry of the tab that shows it (`layout_tab`, `menu_entry_of`).
    pub(crate) fn entry_of(&self, s: &Setting) -> String {
        if self.off_menu(s) { self.schema.camera.text.off_menu_name().to_string() } else { self.menu_entry_of(self.layout_tab(s)).to_string() }
    }

    /// The page a jump to `s` opens, in the layout in use: the page of the Menu entry that shows it (`entry_of`,
    /// `shown_view`). Every jump to a setting goes by it, with `shown_group_of` for its group.
    pub(crate) fn view_of(&self, s: &Setting) -> View {
        self.shown_view(View::Tab(self.entry_of(s)))
    }

    /// Where `s` is shown, in words: its tab, or the entry for what the menus do not hold, and the group that shows it.
    pub(crate) fn where_shown(&self, s: &Setting) -> String {
        if self.off_menu(s) { format!("{} > {}", self.schema.camera.text.off_menu_name(), self.shown_group_of(s)) } else { format!("{} > {}", self.layout_tab(s), self.shown_group_of(s)) }
    }

    /// One of My Menu's places (a live setting of a record `camera.my_menu` names) while My Menu has its page: the page
    /// edits it, its Menu entry counts it, and next edit lands on the page.
    pub(crate) fn is_mymenu_place(&self, s: &Setting) -> bool {
        self.has_mymenu_page() && s.area == "global" && self.schema.camera.my_menu.as_ref().is_some_and(|m| m.records.contains(&s.id))
    }

    /// The settings of a Menu entry (a tab, or "Other": `in_entry`; None: every tab) that `target` holds, before the
    /// search and filters.
    pub(crate) fn settings_in(&self, target: usize, tab: Option<&str>) -> impl Iterator<Item = &Setting> {
        let in_set = target != 0;
        let in_entry = self.in_entry(tab);
        self.schema
            .settings
            .iter()
            .filter(move |s| in_entry(s))
            .filter(move |s| if in_set { s.in_sets } else { s.area == "global" })
            .filter(|s| self.prefs.expert || !Self::expert_only(s))
    }

    /// How many settings `visible_settings` lists, without copying them.
    pub(crate) fn visible_count(&self, tab: Option<&str>) -> usize {
        self.settings_in(self.target, tab)
            .filter(|s| self.matches_search(s))
            .filter(|s| !self.only_changed || self.shown_edited(s))
            .count()
    }

    /// Whether Only edited shows `s`: edited (or no file open), or, as on the camera, the row's own setting of an
    /// edited sub-choice shown beside its option (`beside`), which is reached through it.
    fn shown_edited(&self, s: &Setting) -> bool {
        self.doc.is_none() || self.changed(s) || (self.camera_layout() && self.beside(s).iter().any(|(x, _)| self.changed(x)))
    }

    pub(crate) fn visible_settings(&self, tab: Option<&str>) -> Vec<Setting> {
        self.settings_in(self.target, tab)
            .filter(|s| self.matches_search(s))
            .filter(|s| !self.only_changed || self.shown_edited(s))
            .cloned()
            .collect()
    }

    /// The group a setting's group is opened by: a group shown as one table (Picture Profiles…) by its title.
    fn shown_group(&self, g: &str) -> String {
        self.schema.camera.families.iter().find(|f| !f.prefix.is_empty() && g.starts_with(&f.prefix)).map(|f| f.title.clone()).unwrap_or_else(|| g.to_string())
    }

    /// The group that shows `s` now, in the layout in use: as on the camera, the camera group whose page holds its row
    /// (`menu_rows::camera_group`: Recall Custom hold 1's settings in Shooting Mode); in the flat list, its own; a group
    /// shown as one table by its title (`shown_group`). Every jump to a setting and every count by group goes by it.
    pub(crate) fn shown_group_of(&self, s: &Setting) -> String {
        if self.off_menu(s) { return Self::off_group(s); }
        // a setting on the page an option opens (a profile's parameter), as on the camera: that page, not the table
        if self.camera_layout() && s.on_page() { return self.layout_group(s).to_string(); }
        self.shown_group(self.layout_group(s))
    }

    /// A group of the entry for what the camera's menus do not hold, which gathers groups of several tabs: by its tab
    /// and its own name ("Shooting > …").
    pub(crate) fn off_group(s: &Setting) -> String {
        format!("{} > {}", s.tab, s.group)
    }

    /// The group `s` is listed in, in the layout in use (`shown_group_of` before a family's title). A family's setting
    /// (`camera.families`: a look's parameters) stays in its own group in both layouts, so the family's table keeps it
    /// and counts it once; the camera group's row still offers it beside its option (`beside`, by `camera_group`).
    pub(crate) fn layout_group<'a>(&self, s: &'a Setting) -> &'a str {
        if self.camera_layout() && self.family_of(std::slice::from_ref(s)).is_none() { menu_rows::camera_group(s) } else { &s.group }
    }

    /// The tab `s` is listed in, in the layout in use: as on the camera, the tab whose menu holds its row
    /// (`menu_rows::camera_tab`); in the flat list, its own. Every Menu entry, count and jump goes by it.
    pub(crate) fn layout_tab<'a>(&self, s: &'a Setting) -> &'a str {
        // a family's setting stays with its table, in its own tab, as in `layout_group`
        if self.camera_layout() && self.family_of(std::slice::from_ref(s)).is_none() { menu_rows::camera_tab(s) } else { &s.tab }
    }

    /// Whether `a` and `b` are one row of linked records in the layout in use, as the Edit page, its detail panel and
    /// the page link them and as a change writes them together (`set_linked`): the same tab and group as shown, and one
    /// setting kept in several records (`Setting::links_with`: never a copy with its setting). Compare's and the
    /// Memories page's rows hold the same records.
    pub(crate) fn same_row(&self, a: &Setting, b: &Setting) -> bool {
        a.links_with(b) && self.layout_tab(a) == self.layout_tab(b) && self.layout_group(a) == self.layout_group(b)
    }

    /// The page that shows `v`: a tab's view is the page of the Menu entry that shows that tab's settings
    /// (`menu_entry_of`), so a jump to a setting on My Menu's tab opens the My Menu page, and one on a tab the
    /// definition does not list opens Other; the My Menu page gives way to the first tab without My Menu.
    pub(crate) fn shown_view(&self, v: View) -> View {
        match v {
            View::Tab(t) if self.has_mymenu_page() && t == self.schema.camera.text.my_menu_name() => View::MyMenu,
            // the entry for what the menus do not hold is there as on the camera only
            View::Tab(t) if t == self.schema.camera.text.off_menu_name() && !self.camera_layout() => View::Tab(self.schema.tabs.first().cloned().unwrap_or_default()),
            View::Tab(t) => View::Tab(self.menu_entry_of(&t).to_string()),
            View::MyMenu if !self.has_mymenu_page() => View::Tab(self.schema.tabs.first().cloned().unwrap_or_default()),
            v => v,
        }
    }

    /// The tabs the Menu lists, in order: the definition's (My Menu's left out when it has its own page) and Other,
    /// once, which gathers the settings of the tabs the definition does not list (`menu_entry_of`); then, as on the
    /// camera, the entry for the settings the camera's menus do not hold (`text.off_menu_name`, `off_menu`).
    pub(crate) fn menu_tabs(&self) -> Vec<String> {
        let my_menu = self.has_mymenu_page().then(|| self.schema.camera.text.my_menu_name());
        let off = self.schema.camera.text.off_menu_name();
        self.schema.tabs.iter().filter(|t| Some(t.as_str()) != my_menu && *t != OTHER_TAB && *t != off).cloned().chain(std::iter::once(OTHER_TAB.to_string()))
            .chain(self.camera_layout().then(|| off.to_string())).collect()
    }

    /// Whether the side bar lists the Menu entry `tab` (`menu_tabs`): every tab the definition lists, but Other and the
    /// entry for what the camera's menus do not hold only while they show a setting. The golden Menu's test reads the
    /// entries by it too, so the kit's copy (kit/camkit/menu_rows.py) follows a change here.
    pub(crate) fn side_bar_lists(&self, tab: &str) -> bool {
        (tab != OTHER_TAB && tab != self.schema.camera.text.off_menu_name()) || self.visible_count(Some(tab)) > 0
    }

    /// What the entry for the settings the camera's menus do not hold says on hover, window and page alike.
    pub(crate) fn off_menu_hover() -> &'static str {
        "Settings the file holds that Camset can't place in the camera's menus."
    }

    /// The tab's groups in menu order. Each group holds rows of linked settings (one
    /// setting can live in several records). Picture Profiles and Creative Looks are
    /// one entry each (`family`), holding all their settings in a single row, shown as a table. As on the camera, a
    /// family's group that is the page an option opens (`Setting::on_page`: Picture Profile's PP1) is a group of its
    /// own too, after its owner's row's group, laid out as that page (`menu_rows::lay_out`); the table keeps them all.
    pub(crate) fn tab_groups(&self, tab: &str) -> Vec<(String, bool, Vec<Vec<Setting>>)> {
        let mut groups: BTreeMap<(i64, String), Vec<Setting>> = BTreeMap::new();
        let off = self.camera_layout() && tab == self.schema.camera.text.off_menu_name();
        for s in self.visible_settings(Some(tab)) {
            // the group that shows it in the layout in use (`layout_group`); under the entry for what the menus do not
            // hold, by its tab and name (`off_group`)
            let g = if off { Self::off_group(&s) } else { self.layout_group(&s).to_string() };
            let first = groups.keys().find(|(_, x)| *x == g).cloned();
            let key = first.unwrap_or((s.order, g));
            groups.entry(key).or_default().push(s);
        }
        let mut out = Vec::new();
        for f in &self.schema.camera.families {
            let (prefix, title) = (f.prefix.as_str(), f.title.as_str());
            if prefix.is_empty() { continue; }
            let fam: Vec<Setting> = groups.iter().filter(|((_, g), _)| g.starts_with(prefix)).flat_map(|(_, v)| v.clone()).collect();
            let camera = self.camera_layout();
            groups.retain(|(_, g), v| !g.starts_with(prefix) || (camera && v.iter().any(Setting::on_page)));
            if !fam.is_empty() {
                out.push((title.to_string(), true, vec![fam]));
            }
        }
        // as on the camera, the groups in the camera's order (`menu_rows::group_key`); the flat list keeps the definition's
        let mut groups: Vec<_> = groups.into_iter().collect();
        if off {
            // the gathered groups by their tab's place in the Menu, then the definition's order
            let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(usize::MAX);
            groups.sort_by_cached_key(|((order, name), items)| (items.first().map(|s| tab_idx(&s.tab)), *order, name.clone()));
        } else if self.camera_layout() {
            groups.sort_by_cached_key(|((order, name), items)| menu_rows::group_key(*order, name, items));
        }
        for ((_, group), items) in groups {
            let mut rows: Vec<Vec<Setting>> = Vec::new();
            for s in items {
                // one setting kept in several records: the same name in the same place on the camera
                match rows.iter_mut().find(|r| r[0].links_with(&s)) {
                    Some(r) => r.push(s),
                    None => rows.push(vec![s]),
                }
            }
            out.push((group, false, rows));
        }
        out
    }

    /// Whether a group's rows are laid out as on the camera: the definition places its settings (`row`) and Settings
    /// does not ask for the flat list. A definition that places none has the flat list only, and no switch.
    pub(crate) fn camera_layout(&self) -> bool {
        !self.prefs.flat_list && self.places()
    }

    /// Whether the definition places any of its settings on the camera's rows (the layout switch is offered then).
    pub(crate) fn places(&self) -> bool {
        self.schema.settings.iter().any(|s| s.placed())
    }

    /// A group's rows as drawn: as on the camera (`menu_rows::lay_out`), or the flat list in the definition's order.
    pub(crate) fn group_lines(&self, rows: &[Vec<Setting>]) -> Vec<Line> {
        if self.camera_layout() {
            menu_rows::lay_out(rows)
        } else {
            (0..rows.len()).map(|index| Line::Row { index, depth: 0 }).collect()
        }
    }

    /// The row the selection names: the one called `item`, and of two so called, the one holding `item_key`.
    pub(crate) fn pick_row(rows: &[Vec<Setting>], item: Option<&String>, key: Option<&String>) -> Option<usize> {
        let item = item?;
        let named: Vec<usize> = (0..rows.len()).filter(|&i| &rows[i][0].name == item).collect();
        named.iter().copied().find(|&i| named.len() > 1 && key.is_some_and(|k| rows[i].iter().any(|s| &s.key == k))).or(named.first().copied())
    }

    /// A folded heading's name in `folded`: its tab, group and labels.
    pub(crate) fn fold_key(tab: &str, group: &str, path: &[String]) -> String {
        format!("{tab}\u{1f}{group}\u{1f}{}", path.join("\u{1f}"))
    }

    /// Each setting's position in the camera's order across the tabs (by key): the tabs as the Menu column lists
    /// them, a tab's groups as `tab_groups` orders them, a group's rows as `menu_rows::lay_out` lays them out (linked
    /// records share their row's). Worked out once per definition, over every setting.
    pub(crate) fn menu_rank(&self) -> MenuRank {
        if let Some((generation, rank)) = &*self.rank_cache.borrow() {
            if *generation == self.schema_gen {
                return rank.clone();
            }
        }
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(usize::MAX);
        let mut groups: BTreeMap<(usize, String, i64, String), Vec<Setting>> = BTreeMap::new();
        let mut first: std::collections::HashMap<(String, String), i64> = Default::default();
        for s in &self.schema.settings {
            // as on the camera: in the tab and the camera group that hold its row (`menu_rows::camera_tab`, `camera_group`)
            let (t, g) = (menu_rows::camera_tab(s).to_string(), menu_rows::camera_group(s).to_string());
            let at = *first.entry((t.clone(), g.clone())).or_insert(s.order);
            groups.entry((tab_idx(&t), t, at, g)).or_default().push(s.clone());
        }
        // a tab's groups as `tab_groups` orders them: a family's table first, then the camera's order
        let family = |g: &str| self.schema.camera.families.iter().any(|f| !f.prefix.is_empty() && g.starts_with(&f.prefix));
        let mut groups: Vec<_> = groups.into_iter().collect();
        // a family's group that is the page an option opens comes with its owner's row's group, as `tab_groups` has it
        groups.sort_by_cached_key(|((t, _, order, name), items)| (*t, !family(name) || items.iter().any(Setting::on_page), menu_rows::group_key(*order, name, items)));
        let mut rank = std::collections::HashMap::new();
        let mut n = 0i64;
        for (_, items) in groups {
            let mut rows: Vec<Vec<Setting>> = Vec::new();
            for s in items {
                match rows.iter_mut().find(|r| r[0].links_with(&s)) {
                    Some(r) => r.push(s),
                    None => rows.push(vec![s]),
                }
            }
            let firsts: Vec<&Setting> = rows.iter().map(|r| &r[0]).collect();
            for i in menu_rows::order(&menu_rows::lay_out(&rows)) {
                for s in &rows[i] {
                    rank.entry(s.key.clone()).or_insert(n);
                }
                n += 1;
                // the sub-choices shown beside its options, right after it, as its detail panel lists them
                for (sub, _) in menu_rows::sub_choices(&rows[i][0], firsts.iter().copied()) {
                    for s in rows.iter().find(|r| r[0].key == sub.key).into_iter().flatten() {
                        rank.entry(s.key.clone()).or_insert(n);
                    }
                    n += 1;
                }
            }
        }
        let rank = std::rc::Rc::new(rank);
        *self.rank_cache.borrow_mut() = Some((self.schema_gen, rank.clone()));
        rank
    }

    /// Where a setting comes in its tab, to sort by beside the tab's position: its place in the camera's order when
    /// the rows are laid out as on the camera (`menu_rank`), else its `order`, as the flat list has it.
    pub(crate) fn menu_at(&self) -> impl Fn(&Setting) -> i64 + use<> {
        let rank = self.camera_layout().then(|| self.menu_rank());
        move |s: &Setting| rank.as_ref().and_then(|r| r.get(&s.key).copied()).unwrap_or(s.order)
    }

    /// Lay a group's rows out as on the camera or as a flat list (Settings' "As on the camera" / "Flat list"),
    /// remembered. The orders worked out for the other layout are let go.
    pub(crate) fn set_flat_list(&mut self, flat: bool) {
        if self.prefs.flat_list != flat {
            self.prefs.flat_list = flat;
            self.prefs.save();
            self.rows_cache.borrow_mut().clear();
            // the setting chosen stays chosen, in the group that shows it in this layout
            let chosen = self.item_key.as_ref().and_then(|k| self.schema.settings.iter().find(|s| &s.key == k));
            if let Some((g, v)) = chosen.filter(|s| self.item.as_ref() == Some(&s.name)).map(|s| (self.shown_group_of(s), self.view_of(s))) {
                self.group = Some(g);
                // and on the page that shows it in this layout (in or out of the entry for what the menus do not hold)
                if matches!(self.view, View::Tab(_)) { self.view = v; }
            }
        }
    }

    /// Settings matching the search box, across every tab (live settings only).
    pub(crate) fn search_hits(&self) -> Vec<Setting> {
        if self.search.trim().is_empty() { return Vec::new(); }
        let mut seen = std::collections::HashSet::new();
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
        let mut list: Vec<Setting> = self.schema.settings.iter()
            .filter(|s| s.area == "global" && self.matches_search(s) && (self.prefs.expert || !Self::expert_only(s)))
            .filter(|s| seen.insert((s.tab.clone(), s.name.clone())))
            .cloned().collect();
        let at = self.menu_at();
        list.sort_by_key(|s| (tab_idx(self.layout_tab(s)), at(s)));
        list
    }

    /// Open a setting in its menu, as a click on an item of the My Menu page does: the page that shows its tab
    /// (`shown_view`), its group (a family's by its title: `shown_group`) and the setting.
    /// Open the page an option opens on the camera, by a setting on it (`menu_rows::Page::key`): its tab and the group
    /// that shows it (`shown_group_of`: the page as on the camera), its first row chosen.
    pub(crate) fn open_page_of(&mut self, key: &str) {
        let Some(s) = self.schema.settings.iter().find(|s| s.key == key).cloned() else { return };
        self.mode = Mode::Edit;
        self.view = self.view_of(&s);
        self.group = Some(self.shown_group_of(&s));
        self.item = None;
        self.item_key = None;
        self.sub_focus = None;
        self.focus = Focus::Items;
    }

    /// The pages `s`'s options open on the camera (`menu_rows::pages`: Picture Profile's PP1…), in the set edited.
    pub(crate) fn option_pages(&self, s: &Setting) -> Vec<menu_rows::Page> {
        if !menu_rows::is_own(s) {
            return Vec::new();
        }
        menu_rows::pages(s, self.settings_in(self.target, None))
    }

    pub(crate) fn open_in_menu(&mut self, s: &Setting) {
        self.view = self.view_of(s);
        self.group = Some(self.shown_group_of(s));
        self.item = Some(s.name.clone());
        self.item_key = Some(s.key.clone());          // of two rows of one name, this one (`pick_row`)
        self.focus = Focus::Items;
    }
}

/// The camera facts decision 20 moved into the definition (the audit's rows 7 to 23): read from the ILCE-1M2's,
/// with the editor's plain words when a definition leaves them out.
#[cfg(test)]
pub(crate) mod facts_tests {
    use super::*;
    use crate::definitions::definitions_tests::{app_with, scratch};
    use crate::test_support::{done, sample_app, texts};

    /// The camera's own words and the pages: where the modes come from, the Main and My Menu
    /// names, a tile's live text, the exposure page's columns, live notes and ISO rule, the family tables, the
    /// save name.
    #[test]
    fn page_words_from_the_definition() {
        let (mut app, dir, user) = sample_app("pages", None);
        let t = &app.schema.camera.text;
        assert_eq!((t.main_title(), t.my_menu_name()), ("Main", "My Menu"));
        assert_eq!(app.modes_hover(), "The shooting modes in which this item appears in the camera's menu", "the source in Expert mode only");
        app.prefs.expert = true;
        assert_eq!(app.modes_hover(), "From Sony's Help Guide menu list: the shooting modes in which this menu item appears");
        app.prefs.expert = false;
        let tiles = &app.schema.camera.main_tiles.as_ref().unwrap().0[0].tiles;
        let shutter = tiles.iter().find(|t| t.kind == TileKind::Fraction).unwrap();
        assert_eq!(App::live_text(shutter), "on the camera");
        assert_eq!(app.ex_sections(), vec![0, 1, 2, 3]);
        let ex = app.schema.camera.exposure.clone().unwrap();
        let cell = app.ex_cell(&ex, 0, camset_editor::stops::Side::Aperture, None, exposure::Who::Unknown);
        assert_eq!(cell.text, "on the camera's dials, not in the file");
        let pp: Vec<Setting> = app.schema.settings.iter().filter(|s| s.group.starts_with("Picture Profile PP")).cloned().collect();
        assert_eq!((app.family_column(&pp, "Picture Profile PP3"), app.family_note(&pp)), ("PP3".to_string(), "Each column is one profile. ".to_string()));
        let doc = app.doc.as_ref().unwrap();
        assert_eq!(app.suggested_name(doc), "CAMSETE1.DAT");
        // My Menu kept packed: removing closes the gap; a camera that does not pack only empties the slot
        let pages = app.mymenu_pages().unwrap();
        let (code, next) = (pages[0][0], pages[0][1]);
        let empty = app.schema.camera.my_menu.as_ref().unwrap().empty;
        if code != empty && next != empty {
            let (acts, said) = app.mymenu_remove(code).unwrap();
            assert!(said.starts_with("Removed from My Menu page 1") && acts.len() > 1, "{said}");
            app.schema.camera.my_menu.as_mut().unwrap().packed = false;
            let (acts, _) = app.mymenu_remove(code).unwrap();
            assert_eq!(acts.len(), 1, "only the slot emptied");
        }
        // ISO by the mode's own word, when the definition gives one
        if let Some(e) = app.schema.camera.exposure.as_mut() {
            for c in e.control.values_mut() { c.iso = "you".into(); }
        }
        let ex = app.schema.camera.exposure.clone().unwrap();
        let mode = app.ex_mode(&ex, 1);
        let iso = app.ex_cell(&ex, 1, camset_editor::stops::Side::Iso, mode.as_deref(), exposure::Who::Unknown);
        assert!(mode.is_none() || iso.who == exposure::Who::You);
        done(&dir, &user);
        // without them: the editor's plain words
        let (app, dir, user) = sample_app("pages_bare", Some(|v| {
            let c = v["camera"].as_object_mut().unwrap();
            for k in ["modes_source", "main_title", "my_menu_name"] { c["text"].as_object_mut().unwrap().remove(k); }
            c.remove("save_name");
            c["exposure"].as_object_mut().unwrap().remove("sections");
            c["exposure"]["aperture"].as_object_mut().unwrap().remove("live_note");
            for f in c["families"].as_array_mut().unwrap() { f.as_object_mut().unwrap().remove("column_label"); f.as_object_mut().unwrap().remove("note"); }
            for ts in c["main_tiles"].as_array_mut().unwrap() { for t in ts["tiles"].as_array_mut().unwrap() { t.as_object_mut().unwrap().remove("live_text"); } }
        }));
        assert_eq!(app.modes_hover(), "The shooting modes in which this item appears in the camera's menu");
        assert_eq!(app.suggested_name(app.doc.as_ref().unwrap()), "CAMSET01.DAT");
        assert_eq!(app.ex_sections(), vec![0, 1, 2, 3], "the live settings and the dial's memories");
        let ex = app.schema.camera.exposure.clone().unwrap();
        assert_eq!(app.ex_cell(&ex, 0, camset_editor::stops::Side::Aperture, None, exposure::Who::Unknown).text, "not in the file");
        let pp: Vec<Setting> = app.schema.settings.iter().filter(|s| s.group.starts_with("Picture Profile PP")).cloned().collect();
        assert_eq!((app.family_column(&pp, "Picture Profile PP3"), app.family_note(&pp)), ("Picture Profile PP3".to_string(), String::new()));
        let tiles = &app.schema.camera.main_tiles.as_ref().unwrap().0[0].tiles;
        assert_eq!(App::live_text(tiles.iter().find(|t| t.kind == TileKind::Fraction).unwrap()), crate::main_page::ON_CAMERA);
        done(&dir, &user);
    }

    /// Every setting of the shipped definition the Menu shows (Expert mode's left out) is listed under an entry of
    /// the Menu: its own tab, the My Menu page for My Menu's tab, or Other for a tab the definition does not list; a
    /// jump to it (`shown_view`) opens that page. Without My Menu in the definition, its tab's settings are under
    /// Other and the My Menu page gives way to the first tab.
    #[test]
    fn every_setting_has_a_place_in_the_menu() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        // a tab the definition does not list, as a definition may name one
        let first = app.schema.tabs[0].clone();
        let moved = app.schema.settings.iter().position(|s| s.area == "global" && !s.expert && s.tab == first).unwrap();
        app.schema.settings[moved].tab = "A tab of no list".into();
        for with_my_menu in [true, false] {
            if !with_my_menu {
                app.schema.camera.my_menu = None;
            }
            let name = app.schema.camera.text.my_menu_name().to_string();
            let off = app.schema.camera.text.off_menu_name().to_string();
            for flat in [false, true] {
                app.prefs.flat_list = flat;
                let tabs = app.menu_tabs();
                assert_eq!(tabs.last(), Some(&if flat { OTHER_TAB.to_string() } else { off.clone() }), "the entry for what the menus do not hold last, as on the camera only");
                assert!(!tabs.contains(&name), "My Menu is not a tab of the Menu");
                let on_my_menu: Vec<String> = app.mymenu_groups().into_iter().flat_map(|(_, rows)| rows.into_iter().flatten().map(|s| s.key)).collect();
                assert_eq!(!on_my_menu.is_empty(), with_my_menu, "My Menu's own tab is on its page only with My Menu");
                let groups: std::collections::HashMap<String, Vec<String>> = tabs.iter().map(|t| (t.clone(), app.tab_groups(t).into_iter().map(|(g, _, _)| g).collect())).collect();
                for s in app.schema.settings.iter().filter(|s| !s.expert) {
                    let target = if s.area == "global" { 0 } else { 1 };
                    match app.view_of(s) {
                        View::MyMenu => assert!(with_my_menu && on_my_menu.contains(&s.key), "{} is not on the My Menu page", s.name),
                        View::Tab(t) => {
                            assert!(tabs.contains(&t) && t == app.entry_of(s), "{}: {t} is not an entry of the Menu", s.name);
                            assert!(app.settings_in(target, Some(&t)).any(|o| o.key == s.key), "{} is not under {t}", s.name);
                            assert_eq!(app.settings_in(target, None).filter(|o| o.key == s.key).count(), 1);
                            let shown = app.shown_group_of(s);
                            assert!(groups[&t].contains(&shown) || app.target != target, "{}: {t} has no group {shown}", s.name);
                        }
                        v => panic!("{}: a jump opens {v:?}", s.name),
                    }
                }
            }
            app.prefs.flat_list = false;
            assert_eq!(app.menu_entry_of("A tab of no list"), OTHER_TAB);
            assert_eq!(app.menu_entry_of(&name) == name, with_my_menu);
            assert!(app.settings_in(0, Some(OTHER_TAB)).any(|s| s.tab == "A tab of no list"));
        }
        assert_eq!(app.shown_view(View::MyMenu), View::Tab(first), "no My Menu page without My Menu");
    }

    /// As on the camera, the settings the camera's menus do not hold are under an entry of their own, after the tabs
    /// (`text.off_menu_name`, "Not in the menus" without it): every one on no camera row whose group has none on one
    /// either, grouped by tab and group; a group with a row keeps its other settings under "More settings in this
    /// group", a family's table and My Menu's own tab stay where they are, and a setting with a row stays on it
    /// whatever its source. The rule rests on the places alone. The flat list moves nothing. Jumps (open in its
    /// menu, Compare's Open in Edit, the search, next edit) and the switch of layout follow it, and the edit counts.
    #[test]
    fn what_the_menus_do_not_hold_has_an_entry_of_its_own() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let off = app.schema.camera.text.off_menu_name().to_string();
        assert_eq!(off, "Not in the menus");
        assert!(app.camera_layout() && app.menu_tabs().last() == Some(&off));
        let away: Vec<Setting> = app.settings_in(0, Some(&off)).cloned().collect();
        assert!(!away.is_empty());
        let placed = app.placed_groups();
        for s in &away {
            assert!(!s.placed() && app.schema.tabs.contains(&s.tab), "{}", s.name);
            assert!(!placed.get(&s.tab).is_some_and(|g| g.contains(&s.group)), "{}: its group has a camera row", s.name);
            assert!(app.settings_in(0, Some(&s.tab)).all(|o| o.key != s.key), "{} is under its tab too", s.name);
        }
        // a group with a camera row keeps its settings with none; a family's table and My Menu's own tab stay
        let mixed = app.settings_in(0, None).find(|s| !s.placed() && placed.get(&s.tab).is_some_and(|g| g.contains(&s.group))).cloned().unwrap();
        assert!(!app.off_menu(&mixed) && app.entry_of(&mixed) == mixed.tab);
        let fam = |s: &&Setting| app.schema.camera.families.iter().any(|f| !f.prefix.is_empty() && s.group.starts_with(&f.prefix));
        let family = app.settings_in(0, None).filter(fam).find(|s| !s.placed()).or_else(|| app.settings_in(0, None).find(fam)).cloned().unwrap();
        assert!(!app.off_menu(&family));
        let my_menu = app.schema.camera.text.my_menu_name().to_string();
        assert!(app.settings_in(0, Some(&my_menu)).all(|s| !app.off_menu(s)));
        // groups by tab and group, in the Menu's order of tabs; none of them left in its tab's groups column
        let groups = app.tab_groups(&off);
        let tab_at = |g: &str| app.schema.tabs.iter().position(|t| g.starts_with(&format!("{t} > "))).unwrap();
        assert!(groups.iter().all(|(g, family, rows)| !family && rows.iter().flatten().all(|s| *g == App::off_group(s))));
        assert!(groups.windows(2).all(|w| tab_at(&w[0].0) <= tab_at(&w[1].0)));
        let one = away[0].clone();
        assert!(app.tab_groups(&one.tab).iter().all(|(_, _, rows)| rows.iter().flatten().all(|s| s.key != one.key)));
        assert_eq!(app.where_shown(&one), format!("{off} > {} > {}", one.tab, one.group));
        // the rule rests on the places: a setting placed on a camera row brings its whole group back to its tab
        let mut moved = app.schema.settings.iter().find(|s| s.key == one.key).cloned().unwrap();
        moved.row = vec!["A row".into()];
        moved.row_at = vec![1];
        let mut placed_app = App::new(vec![], Prefs::default());
        placed_app.open_sample();
        let at = placed_app.schema.settings.iter().position(|s| s.key == one.key).unwrap();
        placed_app.schema.settings[at] = moved;
        assert!(placed_app.settings_in(0, None).filter(|s| s.tab == one.tab && s.group == one.group).all(|s| !placed_app.off_menu(s)));
        // jumps: open in its menu, Open in Edit, the search, next edit
        app.open_in_menu(&one);
        assert_eq!((&app.view, app.group.clone(), app.item.as_deref()), (&View::Tab(off.clone()), Some(App::off_group(&one)), Some(one.name.as_str())));
        app.view = View::Main;
        app.open_in_edit_from_compare(&one, 0);
        assert_eq!(app.view, View::Tab(off.clone()));
        let doc = app.doc.as_ref().unwrap();
        let editable = away.iter().find(|s| s.scalar && s.offered(false).len() >= 2 && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none() && doc.value(0, s.slot()).is_some()).cloned().unwrap();
        let cur = doc.value(0, editable.slot()).unwrap();
        let other = editable.offered(false).into_iter().map(|(v, _)| v).find(|&v| v != cur).unwrap();
        app.apply(vec![Action::Set(0, editable.slot(), other)]);
        assert_eq!((app.counts(Some(&off)), app.counts(Some(&editable.tab))), (1, 0), "the edit counts where it is shown");
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!((&app.view, app.group.clone(), app.item.as_deref()), (&View::Tab(off.clone()), Some(App::off_group(&editable)), Some(editable.name.as_str())));
        // the flat list: back in its tab, the chosen setting still chosen; the entry gives way to the first tab
        app.item_key = Some(editable.key.clone());
        app.set_flat_list(true);
        assert_eq!((&app.view, app.group.clone()), (&View::Tab(editable.tab.clone()), Some(editable.group.clone())));
        assert!(!app.menu_tabs().contains(&off) && app.settings_in(0, Some(&off)).next().is_none());
        assert!(app.settings_in(0, Some(&one.tab)).any(|s| s.key == one.key) && app.shown_group_of(&one) == one.group);
        assert_eq!(app.shown_view(View::Tab(off.clone())), View::Tab(app.schema.tabs[0].clone()));
        assert_eq!((app.counts(Some(&off)), app.counts(Some(&editable.tab))), (0, 1));
        app.set_flat_list(false);
        assert_eq!((&app.view, app.group.clone()), (&View::Tab(off.clone()), Some(App::off_group(&editable))));
        // the search's link opens it there too
        app.search = editable.name.clone();
        assert!(app.search_hits().iter().any(|s| s.key == editable.key));
        // another name for the entry, from the definition's text
        app.schema.camera.text.off_menu_name = Some("Elsewhere".into());
        assert_eq!(app.entry_of(&one), "Elsewhere");
    }

    /// The rows as on the camera, from the definition's places alone (`row`, `row_at`, `under_option`): Drive Mode
    /// first, the choices of its options no rows (its detail panel shows them beside the option), a submenu as a
    /// heading; two settings of one name in two places
    /// stay two rows, told apart by `item_key`; F3, the search and Compare follow the layout shown, and Flat list is
    /// the definition's order. A definition without places has the flat list only, and no switch.
    #[test]
    fn rows_as_on_the_camera_from_the_definition() {
        let (mut app, dir, user) = sample_app("rows", None);
        assert!(app.places() && app.camera_layout(), "the default, when the definition places its settings");
        let group = |app: &App, g: &str| app.tab_groups("Shooting").into_iter().find(|(n, _, _)| n == g).unwrap().2;
        let rows = group(&app, "Drive Mode");
        let lines = app.group_lines(&rows);
        let drawn: Vec<(&str, usize)> = lines.iter().filter_map(|l| match l { Line::Row { index, depth, .. } => Some((rows[*index][0].name.as_str(), *depth)), _ => None }).collect();
        assert_eq!(drawn[0], ("Drive Mode", 0));
        assert!(!drawn.iter().any(|(n, _)| n.starts_with("Drive memory")), "the choices of its options are beside them, no rows: {drawn:?}");
        assert_eq!(drawn.len() + 7, rows.len(), "the group still holds (and counts) its seven choices");
        assert!(lines.iter().any(|l| matches!(l, Line::Heading { label, depth: 0, .. } if label == "Cont. Shooting Speed")));
        assert!(!lines.contains(&Line::More), "every Drive Mode setting has its place");
        // the choices of Drive Mode's options, as its detail panel names them
        let own = &rows[menu_rows::order(&lines)[0]][0];
        let options: Vec<String> = menu_rows::sub_choices(own, rows.iter().map(|r| &r[0])).into_iter().map(|(_, o)| o).collect();
        assert_eq!((options.len(), options[0].as_str(), options[6].as_str()), (7, "Continuous Shooting", "DRO Bracket"), "{options:?}");          // the labels as the definition names them
        // one name in two places: two rows, never linked; item_key tells them apart
        let zoom = group(&app, "Zoom");
        let fixed: Vec<usize> = (0..zoom.len()).filter(|&i| zoom[i][0].name == "Fixed Speed REC").collect();
        assert_eq!(fixed.len(), 2, "two places, two settings");
        let name = "Fixed Speed REC".to_string();
        assert_eq!(App::pick_row(&zoom, Some(&name), Some(&zoom[fixed[1]][0].key)), Some(fixed[1]));
        assert_eq!(App::pick_row(&zoom, Some(&name), None), Some(fixed[0]));
        assert_eq!(App::pick_row(&zoom, Some(&name), Some(&"global:0xffff".to_string())), Some(fixed[0]));
        // F3 in the order shown: as on the camera, Drive Mode's choices before Drive Mode Limit; flat, by order
        let find = |app: &App, n: &str| app.schema.settings.iter().find(|s| s.name == n && s.area == "global").unwrap().clone();
        let (speed, limit) = (find(&app, "Drive memory - continuous shooting speed"), find(&app, "Drive Mode Limit: Cont. Bracket"));
        for s in [&speed, &limit] {
            let cur = app.doc.as_ref().unwrap().value(0, s.slot());
            let v = s.values.iter().map(|(v, _)| *v).find(|v| Some(*v) != cur).unwrap();
            app.apply(vec![Action::Set(0, s.slot(), v)]);
        }
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!((app.item.as_deref(), app.item_key.as_deref()), (Some(speed.name.as_str()), Some(speed.key.as_str())));
        let at = |hits: &[Setting], n: &str| hits.iter().position(|s| s.name == n).unwrap();
        app.search = "continuous".into();
        assert!(at(&app.search_hits(), &speed.name) < at(&app.search_hits(), "Drive Mode Limit: Continuous Shooting: Hi"));
        let in_compare = |app: &App, n: &str| app.build_matrix_rows("continuous", Some("Shooting")).iter().position(|r| r.2[0].name == n).unwrap();
        assert!(in_compare(&app, &speed.name) < in_compare(&app, "Drive Mode Limit: Continuous Shooting: Hi"));
        app.set_flat_list(true);
        assert!(!app.camera_layout() && app.places(), "the switch stays, set to the flat list");
        assert_eq!(app.group_lines(&rows), (0..rows.len()).map(|index| Line::Row { index, depth: 0 }).collect::<Vec<_>>());
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!(app.item.as_deref(), Some(limit.name.as_str()), "by order: Drive Mode Limit (47) before the choices (2000)");
        assert!(at(&app.search_hits(), &speed.name) > at(&app.search_hits(), "Drive Mode Limit: Continuous Shooting: Hi"));
        assert!(in_compare(&app, &speed.name) > in_compare(&app, "Drive Mode Limit: Continuous Shooting: Hi"));
        // drawn both ways, the detail panel with Drive Mode's choice, a folded row and the named twin too
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        app.search.clear();
        for (flat, group, item, key) in [(false, "Drive Mode", "Drive Mode", None), (true, "Drive Mode", "Drive Mode", None), (false, "Zoom", "Fixed Speed REC", Some(zoom[fixed[1]][0].key.clone()))] {
            app.set_flat_list(flat);
            (app.mode, app.view, app.group, app.item, app.item_key) = (Mode::Edit, View::Tab("Shooting".into()), Some(group.into()), Some(item.into()), key);
            app.folded.insert(App::fold_key("Shooting", "Drive Mode", &["Cont. Shooting Speed".to_string()]));
            let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
            assert_eq!(app.item.as_deref(), Some(item), "the selection stays");
        }
        // a choice opened from a search (or F3, All edits, Compare, the history) opens Drive Mode, its box marked;
        // in the flat list it is a row of its own and opens as one
        for flat in [false, true] {
            app.set_flat_list(flat);
            app.folded.clear();
            (app.mode, app.view, app.group, app.item, app.item_key, app.sub_focus) = (Mode::Edit, View::Search, None, None, None, None);
            app.open_in_menu(&speed);
            let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
            if flat {
                assert_eq!((app.item.as_deref(), app.sub_focus.as_deref()), (Some(speed.name.as_str()), None));
            } else {
                assert_eq!((app.item.as_deref(), app.sub_focus.as_deref()), (Some("Drive Mode"), Some(speed.key.as_str())), "its owner's row, its box marked");
                assert!(!app.sub_scroll.get(), "scrolled to once, the frame it was drawn");
            }
        }
        app.set_flat_list(false);
        done(&dir, &user);

        let strip = |v: &mut serde_json::Value| {
            for s in v["settings"].as_array_mut().unwrap() {
                for k in ["row", "row_at", "under_option", "row_group", "row_mode"] {
                    s.as_object_mut().unwrap().remove(k);
                }
            }
        };
        let (app, dir, user) = sample_app("rows_none", Some(strip));
        assert!(!app.places() && !app.camera_layout(), "no places: the flat list, and no switch");
        let rows = group(&app, "Drive Mode");
        assert_eq!(app.group_lines(&rows).len(), rows.len());
        assert_eq!(group(&app, "Zoom").iter().filter(|r| r[0].name == "Fixed Speed REC").count(), 1, "as before places: one row of linked records");
        done(&dir, &user);
    }

    /// Focus Area's options as the camera lays them out, from the definition's `option_tree`: the detail panel draws the
    /// main options and, under Spot, its sizes; choosing Spot from Wide stores its first size, choosing it again keeps
    /// the size, a size is stored as itself; the row, Compare and the search keep the flat label ("Spot: M"). A
    /// definition without the field draws the flat list, as before.
    #[test]
    fn options_nested_as_on_the_camera() {
        let (mut app, dir, user) = sample_app("option_tree", None);
        let fa = app.schema.settings.iter().find(|s| s.key == "global:0x0f46").unwrap().clone();
        assert!(fa.scalar && app.shape_ok_in(&fa, 0), "a setting the sample lets the editor change");
        let tree = fa.option_tree().expect("the shipped definition nests Focus Area").to_vec();
        let (wide, spot) = (&tree[0], tree.iter().find(|n| n.label == "Spot").unwrap());
        let offered: Vec<i64> = fa.offered(true).iter().map(|(v, _)| *v).collect();
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        let mut draw = |app: &mut App| -> Vec<String> {
            (app.mode, app.view, app.group, app.item, app.item_key) = (Mode::Edit, View::Tab(fa.tab.clone()), Some(app.shown_group_of(&fa)), Some(fa.name.clone()), Some(fa.key.clone()));
            let out = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame));
            assert_eq!(app.item_key.as_deref(), Some(fa.key.as_str()), "the selection stays");
            texts(&out.shapes)
        };
        app.allow_unobserved = true;
        // on Wide: a plain option; choosing Spot stores its first size
        app.apply(vec![Action::Set(0, fa.slot(), wide.value.unwrap())]);
        let drawn = draw(&mut app);
        assert!(["Wide", "Spot", "Custom", "Tracking"].iter().all(|m| drawn.iter().any(|t| t == m)), "the main options");
        assert!(!drawn.iter().any(|t| t == "XS" || t == "Spot: XS"), "Spot's sizes only under Spot, once chosen");
        let first = spot.pick(Some(wide.value.unwrap()), &offered).unwrap();
        assert_eq!(first, spot.options[0].0);
        app.apply(vec![Action::Set(0, fa.slot(), first)]);
        draw(&mut app);
        // a size of its own; Spot again keeps it
        let m = spot.options.iter().find(|(_, l)| l == "M").unwrap().0;
        app.apply(vec![Action::Set(0, fa.slot(), m)]);
        let drawn = draw(&mut app);
        assert!(["XL", "L", "M", "S", "XS"].iter().all(|z| drawn.iter().any(|t| t == z)), "Spot's sizes under it: {drawn:?}");
        assert_eq!(spot.pick(Some(m), &offered), Some(m));
        let cur = app.doc.as_ref().unwrap().value(0, fa.slot());
        assert_eq!(App::describe(&fa, cur), "Spot: M", "the flat label everywhere else");
        done(&dir, &user);
        // no option_tree in the definition: the flat list
        let strip = |v: &mut serde_json::Value| {
            for s in v["settings"].as_array_mut().unwrap() {
                s.as_object_mut().unwrap().remove("option_tree");
            }
        };
        let (mut app, dir, user) = sample_app("option_tree_none", Some(strip));
        let fa = app.schema.settings.iter().find(|s| s.key == "global:0x0f46").unwrap().clone();
        assert!(fa.option_tree().is_none() && fa.values.len() == 24);
        app.allow_unobserved = true;
        let drawn = draw(&mut app);
        assert!(drawn.iter().any(|t| t == "Spot: XS") && !drawn.iter().any(|t| t == "XS"), "the flat list");
        done(&dir, &user);
    }

    /// As on the camera, a screen the definition keeps as a group of its own sits on its camera row in the camera's
    /// group (Recall Custom hold 1 under Reg. Custom Shoot Set, in Shooting Mode) and leaves the groups column; the
    /// rows only the Movie menu has follow a group's Stills rows under "In Movie mode", and a group only that menu has
    /// (TC/UB) comes where that menu has it. Every jump, F3, the order and the edit counts follow the layout in use;
    /// the flat list is the definition's groups, as before.
    #[test]
    fn sub_screens_and_movie_rows_as_on_the_camera() {
        let (mut app, dir, user) = sample_app("subscreens", None);
        let names = |app: &App| app.tab_groups("Shooting").into_iter().map(|(n, _, _)| n).collect::<Vec<_>>();
        let group = |app: &App, g: &str| app.tab_groups("Shooting").into_iter().find(|(n, _, _)| n == g).unwrap().2;
        let hold = app.schema.settings.iter().find(|s| s.group == "Recall Custom hold 1" && s.name == "Shoot Mode" && s.area == "global").unwrap().clone();
        let drive = app.schema.settings.iter().find(|s| s.group == "Drive Mode" && s.name == "Drive Mode" && s.area == "global").unwrap().clone();
        assert_eq!(hold.row_group.as_deref(), Some("Shooting Mode"));
        // as on the camera
        let shown = names(&app);
        assert!(!shown.iter().any(|g| g.starts_with("Recall Custom hold")), "{shown:?}");
        let at = |n: &str| shown.iter().position(|x| x == n).unwrap();
        assert!(at("Shutter/Silent") < at("Audio Recording") && at("Audio Recording") < at("TC/UB") && at("TC/UB") < at("Image Stabilization"), "{shown:?}");
        assert!(at("Shooting Mode") < at("Drive Mode"));
        assert_eq!(app.shown_group_of(&hold), "Shooting Mode");
        let rows = group(&app, "Shooting Mode");
        let lines = app.group_lines(&rows);
        assert!(lines.iter().any(|l| matches!(l, Line::Heading { label, depth: 1, path } if label == "Recall Custom hold 1" && path[0] == "Reg. Custom Shoot Set")), "{lines:?}");
        let tc = group(&app, "TC/UB");
        assert_eq!(app.group_lines(&tc)[0], Line::Mode("Movie".into()), "TC/UB is the Movie menu's only");
        let iq = group(&app, "Image Quality/Rec");
        let lines = app.group_lines(&iq);
        let mode = lines.iter().position(|l| *l == Line::Mode("Movie".into())).expect("the Movie menu's rows of Image Quality/Rec");
        assert!(lines[..mode].iter().all(|l| !matches!(l, Line::Row { index, .. } if iq[*index][0].row_mode.is_some())), "the Stills rows first");
        assert!(lines[mode + 1..].iter().any(|l| matches!(l, Line::Heading { label, .. } if label == "S&Q Settings")));
        // the order across the tab follows the layout: Shooting Mode, with the hold, before Drive Mode
        let rank = app.menu_at();
        assert!(rank(&hold) < rank(&drive));
        // a jump, F3 and the edit counts in the camera's group
        app.open_in_menu(&hold);
        assert_eq!((app.group.as_deref(), app.item.as_deref()), (Some("Shooting Mode"), Some("Shoot Mode")));
        let cur = app.doc.as_ref().unwrap().value(0, hold.slot());
        let v = hold.values.iter().map(|(v, _)| *v).find(|v| Some(*v) != cur).unwrap();
        app.apply(vec![Action::Set(0, hold.slot(), v)]);
        let edited = |app: &App, g: &str| group(app, g).iter().filter(|r| r.iter().any(|s| app.changed(s))).count();
        assert_eq!(edited(&app, "Shooting Mode"), 1);
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!((app.group.as_deref(), app.item_key.as_deref()), (Some("Shooting Mode"), Some(hold.key.as_str())));
        app.open_in_edit_from_compare(&hold, 0);
        assert_eq!(app.group.as_deref(), Some("Shooting Mode"));
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
        assert_eq!((app.group.as_deref(), app.item_key.as_deref()), (Some("Shooting Mode"), Some(hold.key.as_str())), "the selection stays");
        // the flat list: the setting's own group, chosen still after the switch, in the definition's order
        app.set_flat_list(true);
        assert_eq!((app.group.as_deref(), app.item.as_deref()), (Some("Recall Custom hold 1"), Some("Shoot Mode")));
        assert!(names(&app).contains(&"Recall Custom hold 1".to_string()));
        assert_eq!(edited(&app, "Recall Custom hold 1"), 1);
        assert_eq!(edited(&app, "Shooting Mode"), 0);
        app.open_in_menu(&hold);
        assert_eq!(app.group.as_deref(), Some("Recall Custom hold 1"));
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!(app.group.as_deref(), Some("Recall Custom hold 1"));
        let rank = app.menu_at();
        assert!(rank(&hold) > rank(&drive), "by order");
        let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
        app.set_flat_list(false);
        assert_eq!(app.group.as_deref(), Some("Shooting Mode"));
        done(&dir, &user);
    }

    /// A setting whose row is in another tab (`row_tab`: a Custom Key cell the definition keeps in Shooting, on Setup's
    /// key settings' row) is shown there as on the camera: that tab lists it in the row's group, the jumps, F3 and the
    /// edit counts go there, and the camera's order across the tabs puts it there; the flat list keeps its own tab.
    #[test]
    fn a_row_in_another_tab_as_on_the_camera() {
        let (mut app, dir, user) = sample_app("rowtab", None);
        let key = app.schema.settings.iter().find(|s| s.area == "global" && !s.expert && s.row_tab.is_some() && s.row_mode.is_none() && s.tab != "Setup" && s.row_tab.as_deref() == Some("Setup")).unwrap().clone();
        let (own, there) = (key.tab.clone(), "Setup".to_string());
        let group = key.row_group.clone().unwrap();
        let listed = |app: &App, tab: &str, g: &str| app.tab_groups(tab).into_iter().filter(|(n, _, _)| n == g).flat_map(|(_, _, r)| r).flatten().any(|s| s.key == key.key);
        // as on the camera
        assert_eq!(app.layout_tab(&key), there);
        assert!(listed(&app, &there, &group) && !app.tab_groups(&own).into_iter().flat_map(|(_, _, r)| r).flatten().any(|s| s.key == key.key));
        assert!(app.settings_in(0, Some(&there)).any(|s| s.key == key.key) && !app.settings_in(0, Some(&own)).any(|s| s.key == key.key));
        assert_eq!((app.entry_of(&key), app.view_of(&key), app.shown_group_of(&key)), (there.clone(), View::Tab(there.clone()), group.clone()));
        assert_eq!(app.where_shown(&key), format!("{there} > {group}"));
        let rows = app.tab_groups(&there).into_iter().find(|(n, _, _)| *n == group).unwrap().2;
        let lines = app.group_lines(&rows);
        let at = lines.iter().position(|l| matches!(l, Line::Row { index, .. } if rows[*index].iter().any(|s| s.key == key.key))).unwrap();
        assert!(matches!(&lines[at], Line::Row { depth: 1, .. }), "under its row's heading: {lines:?}");
        assert!(menu_rows::place_words(&key).unwrap().starts_with(&format!("On the camera: {there} > {group} > ")));
        app.open_in_menu(&key);
        assert_eq!((&app.view, app.group.as_deref(), app.item.as_deref()), (&View::Tab(there.clone()), Some(group.as_str()), Some(key.name.as_str())));
        let cur = app.doc.as_ref().unwrap().value(0, key.slot());
        let v = key.values.iter().map(|(v, _)| *v).find(|v| Some(*v) != cur).unwrap();
        app.apply(vec![Action::Set(0, key.slot(), v)]);
        assert_eq!((app.counts(Some(&there)), app.counts(Some(&own))), (1, 0), "the edit counts where it is shown");
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!((&app.view, app.group.as_deref(), app.item_key.as_deref()), (&View::Tab(there.clone()), Some(group.as_str()), Some(key.key.as_str())));
        let ranked = app.menu_rank();
        let first_setup = app.schema.settings.iter().filter(|s| menu_rows::camera_tab(s) == there).filter_map(|s| ranked.get(&s.key)).min().copied().unwrap();
        let last_setup = app.schema.settings.iter().filter(|s| menu_rows::camera_tab(s) == there).filter_map(|s| ranked.get(&s.key)).max().copied().unwrap();
        assert!((first_setup..=last_setup).contains(&ranked[&key.key]), "ranked among its row's tab");
        // the flat list: its own tab and group
        app.set_flat_list(true);
        assert_eq!((app.layout_tab(&key), app.entry_of(&key), app.shown_group_of(&key)), (own.as_str(), own.clone(), key.group.clone()));
        assert!(app.settings_in(0, Some(&own)).any(|s| s.key == key.key) && !app.settings_in(0, Some(&there)).any(|s| s.key == key.key));
        assert_eq!((app.counts(Some(&there)), app.counts(Some(&own))), (0, 1));
        app.open_in_menu(&key);
        assert_eq!((&app.view, app.group.as_deref()), (&View::Tab(own.clone()), Some(key.group.as_str())));
        app.set_flat_list(false);
        done(&dir, &user);
    }

    /// A jump names the tab, group and setting (My Menu's links, Compare's Open in Edit, the search, F3): in either
    /// layout it lands on that setting's row, of two rows of one name on the one it opens, on a row a folded row of
    /// the camera hid (which it unfolds) and on one under "More settings in this group"; Compare's way back stays.
    #[test]
    fn jumps_land_on_their_row_in_either_layout() {
        let (mut app, dir, user) = sample_app("jumps", None);
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        let nth = |app: &App, group: &str, name: &str, n: usize| app.schema.settings.iter().filter(|s| s.group == group && s.name == name && s.area == "global").nth(n).unwrap().clone();
        let hi = nth(&app, "Drive Mode", "Hi(E-Shutter)", 0);
        let fixed = nth(&app, "Zoom", "Fixed Speed REC", 1);
        let unplaced = app.schema.settings.iter().find(|s| s.group == "Shooting Mode" && s.area == "global" && !s.placed() && !s.expert).unwrap().clone();
        let speeds = App::fold_key("Shooting", "Drive Mode", &["Cont. Shooting Speed".to_string()]);
        for flat in [false, true] {
            app.set_flat_list(flat);
            for (s, from_compare) in [(&hi, false), (&fixed, true), (&unplaced, false), (&fixed, false)] {
                app.folded.insert(speeds.clone());
                // from Compare, or from the My Menu page (Edit)
                let mode = if from_compare { Mode::Compare } else { Mode::Edit };
                (app.mode, app.view, app.group, app.item, app.item_key) = (mode, View::Main, None, None, None);
                if from_compare { app.open_in_edit_from_compare(s, 0) } else { app.open_in_menu(s) }
                let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
                let shown = app.shown_group_of(s);
                assert_eq!((&app.view, app.group.as_deref(), app.item.as_deref()), (&View::Tab(s.tab.clone()), Some(shown.as_str()), Some(s.name.as_str())), "{} (flat {flat})", s.name);
                let rows = app.tab_groups(&s.tab).into_iter().find(|(g, _, _)| *g == shown).unwrap().2;
                let i = App::pick_row(&rows, app.item.as_ref(), app.item_key.as_ref()).unwrap();
                assert!(rows[i].iter().any(|o| o.key == s.key), "{} (flat {flat}): another row of that name is chosen", s.name);
                if s.key == hi.key && !flat {
                    assert!(!app.folded.contains(&speeds), "the folded row of the camera above it opens");
                }
                assert_eq!(app.from_compare.is_some(), from_compare, "{}: ← Back to Compare", s.name);
            }
        }
        app.set_flat_list(false);
        done(&dir, &user);
    }

    /// The sample is a file beside its definition: offered while one is there, read with the shipped definition,
    /// and not offered at all when no definition names one.
    #[test]
    fn the_sample_is_beside_its_definition() {
        let (dir, user) = (scratch("sample_ship"), scratch("sample_user"));
        let mut app = app_with(&user);
        let samples = app.defs.samples();
        assert_eq!(samples.len(), 1);
        assert!(samples[0].1.ends_with("ILCE-1M2_fw4.00.DAT"));
        assert_eq!(app.defs.list[samples[0].0].camera.sample.as_deref(), Some("ILCE-1M2_fw4.00.DAT"));
        app.open_sample();
        assert!(app.doc.as_ref().is_some_and(|d| d.source == Source::Sample) && app.schema.origin.is_shipped());
        // a shipped folder holding the definition without its sample: no sample to offer
        std::fs::copy(crate::definitions::definitions_tests::shipped().join("ILCE-1M2_fw4.00.json"), dir.join("ILCE-1M2_fw4.00.json")).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        app.defs = Definitions::load(Some(dir.clone()), vec![dir.clone()], user.clone(), &[]);
        assert!(app.defs.samples().is_empty());
        app.open_sample();
        assert!(app.doc.is_none() && app.status.starts_with("There is no sample to explore"), "{}", app.status);
        // and no definition at all
        app.defs = Definitions::load(None, vec![dir.join("missing")], user.clone(), &[]);
        app.open_sample();
        assert!(app.doc.is_none() && app.status.contains("No camera definition was found"), "{}", app.status);
        done(&dir, &user);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The page shown is kept by its name and comes back by it at the next start; a page for mapping work only in
    /// Expert mode, a tab only while the definition has it.
    #[test]
    fn a_page_comes_back_by_its_name() {
        let tabs = vec!["Shooting".to_string()];
        for v in [View::Main, View::Changes, View::Memories, View::MyMenu, View::Exposure, View::Unmapped, View::Records, View::Tab("Shooting".into())] {
            assert_eq!(View::from_key(v.key(), true, &tabs), Some(v.clone()), "{v:?}");
        }
        assert_eq!(View::Search.key(), "Main", "a search is not kept");
        assert_eq!(View::from_key("Records", false, &tabs), None);
        assert_eq!(View::from_key("Unmapped", false, &tabs), None);
        assert_eq!(View::from_key("Gone", true, &tabs), None, "a tab the definition no longer has");
    }

    /// The shipped ILCE-1M2 definition's default Menu (the live settings, Expert mode's left out, the rows as on the
    /// camera), as the kit's definition viewer must lay it out too: each entry the side bar lists, its groups as
    /// `tab_groups` orders them, a family's table by its records' keys, and every other group's lines as `group_lines`
    /// lays them out (a row by the keys of its linked records). kit/camkit/menu_rows.py, the kit's copy of this layout,
    /// is compared with the same file by kit/tests/test_menu_rows.py, so either side changed alone fails a test. After
    /// a change to the definition or to the layout, write the file again with
    /// `CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one`, and look at its diff.
    #[test]
    fn the_default_menu_is_the_golden_one() {
        use crate::test_support::{done, sample_app};
        let (app, dir, user) = sample_app("menu_golden", None);
        let mut groups_text = Vec::new();
        let mut got = Vec::new();
        for tab in app.menu_tabs() {
            if !app.side_bar_lists(&tab) {
                continue;
            }
            let mut groups = Vec::new();
            for (name, family, rows) in app.tab_groups(&tab) {
                let keys = |i: usize| rows[i].iter().map(|s| s.key.clone()).collect::<Vec<_>>();
                let group = if family {
                    serde_json::json!({ "group": name, "family": true, "keys": keys(0) })
                } else {
                    let lines: Vec<serde_json::Value> = app.group_lines(&rows).into_iter().map(|l| match l {
                        Line::Heading { label, depth, .. } => serde_json::json!(["heading", label, depth]),
                        Line::Row { index, depth } => serde_json::json!(["row", keys(index), depth]),
                        Line::Mode(m) => serde_json::json!(["mode", m]),
                        Line::More => serde_json::json!(["more"]),
                    }).collect();
                    serde_json::json!({ "group": name, "family": false, "lines": lines })
                };
                groups_text.push((tab.clone(), serde_json::to_string(&group).unwrap()));
                groups.push(group);
            }
            got.push(serde_json::json!({ "entry": tab, "groups": groups }));
        }
        done(&dir, &user);
        let got = serde_json::json!({ "definition": "ILCE-1M2_fw4.00", "entries": got });
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("data").join("menu_ILCE-1M2_fw4.00.json");
        if std::env::var("CAMSET_BLESS").is_ok_and(|v| v == "1") {
            // one group a line, so a change reads as a diff of the groups it touched
            let mut text = String::from("{\"definition\": \"ILCE-1M2_fw4.00\", \"entries\": [\n");
            let tabs: Vec<String> = got["entries"].as_array().unwrap().iter().map(|e| e["entry"].as_str().unwrap().to_string()).collect();
            for (n, tab) in tabs.iter().enumerate() {
                let lines: Vec<&String> = groups_text.iter().filter(|(t, _)| t == tab).map(|(_, g)| g).collect();
                text += &format!(" {{\"entry\": {}, \"groups\": [\n  {}\n ]}}{}\n", serde_json::to_string(tab).unwrap(),
                    lines.iter().map(|g| g.as_str()).collect::<Vec<_>>().join(",\n  "), if n + 1 < tabs.len() { "," } else { "" });
            }
            text += "]}\n";
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(&path, text).unwrap();
            return;
        }
        let want: serde_json::Value = std::fs::read_to_string(&path).ok().and_then(|t| serde_json::from_str(&t).ok())
            .unwrap_or_else(|| panic!("{} is missing or unreadable: write it with CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one", path.display()));
        assert!(got == want, "the default Menu is not {}: if the definition or the layout changed on purpose, write it again with CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one, look at its diff, and make kit/camkit/menu_rows.py lay it out the same (kit/tests/test_menu_rows.py)", path.display());
    }
}
