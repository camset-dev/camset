//! Where a setting is shown: the Menu's entries and pages, a tab's groups and rows as on the camera or as a flat list,
//! and the sets of the file a page shows.

use crate::*;
use camset_editor::schema::MenuDef;

/// The window's choice of one of the camera's menus (`App::set_menu`): the menu's name, and the set edited and the
/// opening of the file it was made for, so that a file opened, or another set edited, opens on its own menu again
/// (`App::menu_shown`).
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct MenuChoice {
    pub(crate) name: String,
    pub(crate) target: usize,
    pub(crate) opened: u64,
}

/// How a menu's rows pick the record they show for a setting the camera keeps a copy of per shooting mode (`copy_for`,
/// `App::copy_for_menu`). `Set(mode)`: for a set saved in `mode` (None where it is not known), the setting itself where
/// `mode` is one of the menu's modes, else its copy for the menu, as Edit shows the set edited. `Menu`: always its copy
/// for the menu, as Compare shows every column, so that two files saved in different modes are compared like for like.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum Bind {
    Set(Option<String>),
    Menu,
}

/// The settings one menu lists (`App::listed`): each laid out as that menu has it (`Setting::place_in`), and where each
/// of the definition's settings is among them, by its key: a copy hidden in its setting's row, and the setting whose
/// row shows a copy, at that row.
pub(crate) struct Listed {
    pub(crate) rows: Vec<Setting>,
    pub(crate) by_key: std::collections::HashMap<String, usize>,
}

/// What a menu's listing and order were worked out for: the definition (its generation), the menu, how rows pick their
/// record (`Bind`) and Expert mode.
type MenuKey = (u64, String, Bind, bool);

/// What is worked out per menu (`App::listed`, `App::rank_in`), kept until what it was worked out for changes.
#[derive(Default)]
pub(crate) struct MenuCache {
    listed: Vec<(MenuKey, std::rc::Rc<Listed>)>,
    ranks: Vec<(MenuKey, MenuRank)>,
    /// The groups each menu's rows hold (`App::menu_groups`), by definition generation and menu.
    groups: Vec<((u64, String), MenuGroups)>,
}

/// The (tab, group) of every row one menu places a setting on (`App::menu_groups`).
type MenuGroups = std::rc::Rc<std::collections::HashSet<(String, String)>>;

/// Where a row sits in a menu, to tell a row alone on its place: its area, labels, sort key, tab and group.
type PlaceKey = (String, Vec<String>, Vec<i64>, String, String);
/// The heading rows sit under in a menu (`listed`): area, tab and group as the camera's layout has them, the labels and
/// positions of the rows above.
type HeadKey = (String, String, String, Vec<String>, Vec<i64>);

/// How many listings of menus are kept (three menus, two ways of picking records, a little room).
const MENUS_KEPT: usize = 12;

/// An entry of the Menu, the left bar, the same in Edit and in Compare (`App::bar_keys`).
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum BarKey {
    /// Compare only, first: every setting.
    All,
    /// The camera's Main page (`camera.main_tiles`), by `text.main_title`.
    Main,
    /// My Menu (`camera.my_menu`), by `text.my_menu_name`.
    MyMenu,
    /// A tab, "Other", or the entry for what the camera's menus do not hold, by its name (`menu_tabs`).
    Tab(String),
}

/// An entry of the Menu as the bar draws it (`App::edit_entries`, `App::compare_bar`): its key, its words without a
/// count, its colour (None: Main's mark, the strong text colour, or no mark for All), its hover, how many it lists
/// (None where the bar shows no count: Main, and My Menu, whose words say it) and its badge (Edit: the settings edited
/// in it; Compare: the rows that differ).
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct BarEntry {
    pub(crate) key: BarKey,
    pub(crate) label: String,
    pub(crate) color: Option<Color32>,
    pub(crate) hover: Option<String>,
    pub(crate) count: Option<usize>,
    pub(crate) badge: usize,
}

/// The words of Compare's first entry, which lists every setting.
pub(crate) const ALL_SETTINGS: &str = "All settings";

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
    /// Edited settings, for the settings of one Menu entry (or all: `in_entry`), in the set and menu the window shows
    /// (`counts_in`, which the bar's entries count by: `edit_entries`).
    #[cfg(test)]
    pub(crate) fn counts(&self, tab: Option<&str>) -> usize {
        self.counts_in(self.target, self.menu_shown().as_deref(), tab)
    }

    /// Edited settings of set `target`, for the settings one Menu entry lists in menu `menu` (or all: `in_entry`; None:
    /// no menu shown, every setting as before menus), as the bar's badge counts them; My Menu's places count on its own
    /// entry (`mymenu_edits`), not on a tab's.
    pub(crate) fn counts_in(&self, target: usize, menu: Option<&str>, tab: Option<&str>) -> usize {
        let Some(d) = &self.doc else { return 0 };
        let edited = |s: &Setting| d.value(target, s.slot()) != d.original_value(target, s.slot());
        if let Some(m) = menu.filter(|m| self.menu_named(m).is_some()) {
            return self.settings_in_menu(target, m, tab).iter().filter(|s| tab.is_none() || !self.is_mymenu_place(s)).filter(|s| edited(s)).count();
        }
        let in_set = target != 0;
        let in_entry = self.in_entry(tab);
        self.schema.settings.iter().filter(|s| in_entry(s)).filter(|s| if in_set { s.in_sets } else { s.area == "global" })
            .filter(|s| tab.is_none() || !self.is_mymenu_place(s))
            .filter(|s| edited(s))
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

    /// Sections offered as columns and as sets to edit: the live settings and the dial memories, and where the Menu
    /// shows the camera's menus the memory sets of each menu's modes (`menu_sets`); every set in expert mode.
    pub(crate) fn shown_sections(&self) -> Vec<usize> {
        if self.prefs.expert {
            return (0..self.n_sections()).collect();
        }
        let mut v: Vec<usize> = std::iter::once(0).chain(self.dial_sets()).collect();
        for m in self.menus() {
            v.extend(self.menu_sets(Some(&m.name)));
        }
        v.sort_unstable();
        v.dedup();
        v
    }

    /// Derived working copies, flags and alternate numberings, as the definition marks them: shown only in expert
    /// mode.
    pub(crate) fn expert_only(s: &Setting) -> bool {
        s.expert
    }

    /// The name, group or a value label holds `q` (lower case).
    /// The search as every answer takes it, the window's and the page's: trimmed and in lower case, once.
    pub(crate) fn query(q: &str) -> String {
        q.trim().to_lowercase()
    }

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
        // My Menu's places are its page's (`entry_here`), under no tab and not under the entry for what the menus do not hold
        move |s| tab.is_none_or(|t| !self.is_mymenu_place(s) && {
            let away = placed.as_ref().is_some_and(|p| self.off_menu_in(s, p));
            // as on the camera in the tab whose menu holds its row (`layout_tab`)
            let tab = self.layout_tab(s);
            if t == off { away } else { !away && (tab == t || (gathers && self.menu_entry_of(tab) == t)) }
        })
    }

    /// The groups the camera's menus hold, as on the camera: the tab (`menu_rows::camera_tab`) and the camera group
    /// (`menu_rows::camera_group`) of every setting the definition places on a row of the camera, in any of its menus
    /// (`row_places` too). Worked out once per definition.
    pub(crate) fn placed_groups(&self) -> PlacedGroups {
        if let Some((generation, set)) = &*self.placed_cache.borrow() {
            if *generation == self.schema_gen {
                return set.clone();
            }
        }
        let mut by_tab: std::collections::HashMap<String, std::collections::HashSet<String>> = Default::default();
        for s in self.schema.settings.iter().filter(|s| s.placed_anywhere()) {
            // its own place, and each one menu gives it (`row_places`)
            let places = std::iter::once(s.clone()).chain(s.row_places.keys().map(|m| s.place_in(m)));
            for p in places.filter(Setting::placed) {
                by_tab.entry(menu_rows::camera_tab(&p).to_string()).or_default().insert(menu_rows::camera_group(&p).to_string());
            }
        }
        let set: PlacedGroups = std::rc::Rc::new(by_tab);
        *self.placed_cache.borrow_mut() = Some((self.schema_gen, set.clone()));
        set
    }

    /// Whether `s` is one of the settings the camera's menus do not hold, given the groups they do (`placed_groups`):
    /// a setting of a tab the definition lists on no row of the camera (in none of its menus), whose group has no
    /// setting on one either (a
    /// group with some keeps the others under "More settings in this group"), and not of a family shown as one table
    /// (`camera.families`), nor of My Menu's own tab or one of its places, which its page shows. Only the definition's
    /// places decide it; the layout is not asked here (`off_menu`).
    fn off_menu_in(&self, s: &Setting, placed: &std::collections::HashMap<String, std::collections::HashSet<String>>) -> bool {
        !s.placed_anywhere() && self.schema.tabs.contains(&s.tab)
            && !(self.has_mymenu_page() && s.tab == self.schema.camera.text.my_menu_name()) && !self.is_mymenu_place(s)
            && !self.schema.camera.families.iter().any(|f| !f.prefix.is_empty() && s.group.starts_with(&f.prefix))
            && !placed.get(&s.tab).is_some_and(|g| g.contains(&s.group))
    }

    /// The records a Main tile shows (of every tile set: `keys`, `memory_keys`, a fraction's `numerator_key` and
    /// `denominator_key`) that the live settings' rows leave out: a record a memory keeps alone, and one of Expert mode's
    /// outside it (a fraction's parts). Compare lists them under Main, and in All under the entry that shows them
    /// (`entry_here`), since every record shown anywhere outside Expert mode is All's. Those the search `q` (lower case,
    /// trimmed) finds, each once, in the definition's order.
    pub(crate) fn tile_records(&self, q: &str) -> Vec<Setting> {
        let Some(sets) = self.schema.camera.main_tiles.as_ref() else { return Vec::new() };
        let keys: std::collections::HashSet<&String> = sets.0.iter().flat_map(|set| &set.tiles)
            .flat_map(|t| t.keys.iter().chain(&t.memory_keys).chain(&t.numerator_key).chain(&t.denominator_key)).collect();
        self.schema.settings.iter()
            .filter(|s| keys.contains(&s.key) && !(s.area == "global" && (self.prefs.expert || !Self::expert_only(s))))
            .filter(|s| q.is_empty() || Self::matches_query(s, q))
            .cloned().collect()
    }

    /// Whether `s` is shown under the Menu's entry for what the camera's menus do not hold (`text.off_menu_name`): as
    /// on the camera only (`off_menu_in`); the flat list keeps every setting in its tab.
    pub(crate) fn off_menu(&self, s: &Setting) -> bool {
        self.camera_layout() && self.off_menu_in(s, &self.placed_groups())
    }

    /// The Menu entry that shows `s` in the layout in use: the entry for what the camera's menus do not hold
    /// (`off_menu`), else the entry of the tab that shows it (`layout_tab`, `menu_entry_of`); where the Menu shows the
    /// camera's menus, in the menu a jump to `s` opens (`jump_place`).
    pub(crate) fn entry_of(&self, s: &Setting) -> String {
        let s = self.shown_as(s);
        self.entry_here(&s)
    }

    /// `s` as the menu a jump to it opens lays it out, for set edited (`jump_place`, `listed_record`); `s` itself
    /// without menus.
    fn shown_as<'a>(&self, s: &'a Setting) -> std::borrow::Cow<'a, Setting> {
        match self.menu_for(s, self.target, self.menu_shown().as_deref()) {
            Some(m) => std::borrow::Cow::Owned(self.listed_record(s, self.target, &m)),
            None => std::borrow::Cow::Borrowed(s),
        }
    }

    /// `entry_of` for a setting as the menu it is listed in lays it out.
    pub(crate) fn entry_here(&self, s: &Setting) -> String {
        if self.is_mymenu_place(s) {
            // one of My Menu's places: its page's, in Expert mode too
            self.schema.camera.text.my_menu_name().to_string()
        } else if self.off_menu(s) {
            self.schema.camera.text.off_menu_name().to_string()
        } else {
            self.menu_entry_of(self.layout_tab(s)).to_string()
        }
    }

    /// The page a jump to `s` opens, in the layout in use: the page of the Menu entry that shows it (`entry_of`,
    /// `shown_view`). Every jump to a setting goes by it, with `shown_group_of` for its group (`go_to` does both, and
    /// picks the menu first).
    pub(crate) fn view_of(&self, s: &Setting) -> View {
        self.shown_view(View::Tab(self.entry_of(s)))
    }

    /// Where `s` is shown, in words: its tab, or the entry for what the menus do not hold, and the group that shows it;
    /// where the Menu shows the camera's menus, the menu first ("Movie > Shooting > Audio Recording": `where_in`).
    pub(crate) fn where_shown(&self, s: &Setting) -> String {
        self.where_in(s, self.target, self.menu_shown().as_deref())
    }

    /// Where `s` is shown for set `target`, the Menu showing menu `now` (None: no menu shown), in words: the menu a jump
    /// to it opens and then, as `where_shown` has it, its entry and group.
    pub(crate) fn where_in(&self, s: &Setting, target: usize, now: Option<&str>) -> String {
        let (menu, _, _) = self.jump_place(s, target, now);
        let shown = match &menu { Some(m) => self.listed_record(s, target, m), None => s.clone() };
        // the entry a click opens (`entry_here`, as the jump: My Menu's page for one of its places)
        let here = format!("{} > {}", self.entry_here(&shown), self.group_here(&shown));
        match menu { Some(m) => format!("{m} > {here}"), None => here }
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

    /// How many settings `visible_settings` lists, in the set and menu the window shows (`visible_count_in`, which the
    /// bar's entries count by: `edit_entries`).
    #[cfg(test)]
    pub(crate) fn visible_count(&self, tab: Option<&str>) -> usize {
        self.visible_count_in(self.target, self.menu_shown().as_deref(), tab, &self.search, self.only_changed)
    }

    /// How many settings one Menu entry lists for set `target` in menu `menu`, with the search `q` and Only edited
    /// (`visible_in`): the count the bar shows beside a tab.
    pub(crate) fn visible_count_in(&self, target: usize, menu: Option<&str>, tab: Option<&str>, q: &str, only_changed: bool) -> usize {
        self.visible_in(target, menu, tab, q, only_changed).len()
    }

    /// Whether Only edited shows `s` in set `target` and menu `menu`: edited (or no file open), or, as on the camera, the
    /// row's own setting of an edited sub-choice shown beside its option (`beside_in`), which is reached through it.
    fn shown_edited_in(&self, target: usize, menu: Option<&str>, s: &Setting) -> bool {
        let Some(d) = &self.doc else { return true };
        let changed = |x: &Setting| d.value(target, x.slot()) != d.original_value(target, x.slot());
        changed(s) || (self.camera_layout() && self.beside_in(target, menu, s).iter().any(|(x, _)| changed(x)))
    }

    pub(crate) fn visible_settings(&self, tab: Option<&str>) -> Vec<Setting> {
        self.visible_in(self.target, self.menu_shown().as_deref(), tab, &self.search, self.only_changed)
    }

    /// The settings one Menu entry lists (`tab`; None: every entry) for set `target` in menu `menu` (None: no menu
    /// shown, every setting as before menus), with the search `q` (as the search box takes it) and Only edited, each as
    /// that menu lays it out (`listed`): what the bar counts and the entry's groups hold. The window and the page alike.
    pub(crate) fn visible_in(&self, target: usize, menu: Option<&str>, tab: Option<&str>, q: &str, only_changed: bool) -> Vec<Setting> {
        let q = Self::query(q);
        // by the setting's own name too, where a menu titles its row as the camera draws it
        let matches = |s: &Setting| q.is_empty() || Self::matches_query(s, &q) || Self::matches_query(self.def_of(s), &q);
        match menu.filter(|m| self.menu_named(m).is_some()) {
            Some(m) => self.settings_in_menu(target, m, tab).into_iter()
                .filter(|s| matches(s))
                .filter(|s| !only_changed || self.shown_edited_in(target, Some(m), s))
                .collect(),
            None => self.settings_in(target, tab)
                .filter(|s| matches(s))
                .filter(|s| !only_changed || self.shown_edited_in(target, None, s))
                .cloned()
                .collect(),
        }
    }

    /// The group a setting's group is opened by: a group shown as one table (Picture Profiles…) by its title.
    fn shown_group(&self, g: &str) -> String {
        self.schema.camera.families.iter().find(|f| !f.prefix.is_empty() && g.starts_with(&f.prefix)).map(|f| f.title.clone()).unwrap_or_else(|| g.to_string())
    }

    /// The group that shows `s` now, in the layout in use: as on the camera, the camera group whose page holds its row
    /// (`menu_rows::camera_group`: Recall Custom hold 1's settings in Shooting Mode); in the flat list, its own; a group
    /// shown as one table by its title (`shown_group`). Every jump to a setting and every count by group goes by it.
    /// Where the Menu shows the camera's menus: in the menu a jump to `s` opens (`jump_place`), as it lays `s` out.
    pub(crate) fn shown_group_of(&self, s: &Setting) -> String {
        let s = self.shown_as(s);
        self.group_here(&s)
    }

    /// `shown_group_of` for a setting as the menu it is listed in lays it out.
    fn group_here(&self, s: &Setting) -> String {
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
    /// the page link them and as a change writes them together (`apply`): the same tab and group as shown, and one
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
    #[cfg(test)]
    pub(crate) fn side_bar_lists(&self, tab: &str) -> bool {
        self.side_bar_lists_in(self.target, self.menu_shown().as_deref(), tab, &self.search, self.only_changed)
    }

    /// `side_bar_lists` for set `target` in menu `menu`, with the search `q` and Only edited: where a menu is shown, a
    /// tab only while that menu holds one of its settings (whatever the search), as the camera lists none it has not.
    pub(crate) fn side_bar_lists_in(&self, target: usize, menu: Option<&str>, tab: &str, q: &str, only_changed: bool) -> bool {
        let regular = tab != OTHER_TAB && tab != self.schema.camera.text.off_menu_name();
        match menu.filter(|m| self.menu_named(m).is_some()) {
            Some(m) if regular => !self.settings_in_menu(target, m, Some(tab)).is_empty(),
            _ => regular || self.visible_count_in(target, menu, Some(tab), q, only_changed) > 0,
        }
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
        self.groups_of(self.visible_settings(Some(tab)), tab)
    }

    /// `tab_groups` for set `target` in menu `menu` (None: no menu shown), with the search `q` and Only edited: the
    /// groups and rows one Menu entry shows, the window's and the page's alike. In a menu, each setting as that menu
    /// lays it out (`listed`): its rows in that menu's order, titled as the camera draws them, and a row of a setting
    /// the camera keeps a copy of per shooting mode showing the record for that menu (`row_record`).
    pub(crate) fn tab_groups_in(&self, target: usize, menu: Option<&str>, tab: &str, q: &str, only_changed: bool) -> Vec<(String, bool, Vec<Vec<Setting>>)> {
        self.groups_of(self.visible_in(target, menu, Some(tab), q, only_changed), tab)
    }

    /// The groups of Menu entry `tab` that `list` (its settings, as the layout in use has them) makes: `tab_groups`.
    fn groups_of(&self, list: Vec<Setting>, tab: &str) -> Vec<(String, bool, Vec<Vec<Setting>>)> {
        let mut groups: BTreeMap<(i64, String), Vec<Setting>> = BTreeMap::new();
        let off = self.camera_layout() && tab == self.schema.camera.text.off_menu_name();
        for s in list {
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
        let rank = std::rc::Rc::new(self.rank_over(&self.schema.settings));
        *self.rank_cache.borrow_mut() = Some((self.schema_gen, rank.clone()));
        rank
    }

    /// `menu_rank` of the settings `list` (the definition's, or one menu's as it lays them out), by key.
    fn rank_over(&self, list: &[Setting]) -> std::collections::HashMap<String, i64> {
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(usize::MAX);
        let mut groups: BTreeMap<(usize, String, i64, String), Vec<Setting>> = BTreeMap::new();
        let mut first: std::collections::HashMap<(String, String), i64> = Default::default();
        for s in list {
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
        rank
    }

    /// Where a setting comes in its tab, to sort by beside the tab's position: its place in the camera's order when
    /// the rows are laid out as on the camera (`menu_rank`; in the menu the window shows, that menu's: `rank_in`),
    /// else its `order`, as the flat list has it.
    pub(crate) fn menu_at(&self) -> impl Fn(&Setting) -> i64 + use<> {
        let rank = match self.menu_shown() {
            Some(m) => Some(self.rank_in(&m, &self.bind_for(self.target))),
            None => self.camera_layout().then(|| self.menu_rank()),
        };
        move |s: &Setting| rank.as_ref().and_then(|r| r.get(&s.key).copied()).unwrap_or(s.order)
    }

    /// The camera's order in menu `menu` (`menu_rank` over the settings it lists, `listed`), by the key of each of the
    /// definition's settings it shows: a setting whose row shows a copy, and a copy shown in its setting's row, at
    /// that row's place. A setting the menu does not list has none.
    pub(crate) fn rank_in(&self, menu: &str, bind: &Bind) -> MenuRank {
        let key: MenuKey = (self.schema_gen, menu.to_string(), bind.clone(), self.prefs.expert);
        if let Some((_, r)) = self.menus_cache.borrow().ranks.iter().find(|(k, _)| *k == key) {
            return r.clone();
        }
        let listed = self.listed(menu, bind);
        let mut rank = self.rank_over(&listed.rows);
        for (k, &i) in &listed.by_key {
            if let Some(&r) = rank.get(&listed.rows[i].key) {
                rank.entry(k.clone()).or_insert(r);
            }
        }
        let rank = std::rc::Rc::new(rank);
        let mut cache = self.menus_cache.borrow_mut();
        if cache.ranks.len() >= MENUS_KEPT { cache.ranks.remove(0); }
        cache.ranks.push((key, rank.clone()));
        rank
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
            if let Some((g, v, s)) = chosen.filter(|s| self.item.as_ref() == Some(&s.name)).map(|s| (self.shown_group_of(s), self.view_of(s), s.clone())) {
                // and on the page that shows it in this layout (in or out of the entry for what the menus do not hold)
                let view = matches!(self.view, View::Tab(_)).then_some(v);
                self.select(view, Some(g), Some((&s.name, &s.key)));
            }
        }
    }

    /// Settings matching the search box, across every tab and every menu (live settings only), as `search_hits_in`
    /// orders them for the window.
    pub(crate) fn search_hits(&self) -> Vec<Setting> {
        self.search_hits_in(self.target, self.menu_shown().as_deref(), &self.search).into_iter().map(|(s, _)| s).collect()
    }

    /// The live settings matching the search `q` (name, group or a value label), across every tab and every menu, the
    /// definition's settings themselves (one per tab and name), each with the menu a click on it opens for set `target`
    /// while the Menu shows menu `now` (`jump_place`; None without menus): in the menus' order, then the Menu's order of
    /// tabs and the camera's order in that menu. The window's and the page's search alike.
    pub(crate) fn search_hits_in(&self, target: usize, now: Option<&str>, q: &str) -> Vec<(Setting, Option<String>)> {
        let q = Self::query(q);
        if q.is_empty() { return Vec::new(); }
        let mut seen = std::collections::HashSet::new();
        let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
        let list: Vec<Setting> = self.schema.settings.iter()
            .filter(|s| s.area == "global" && Self::matches_query(s, &q) && (self.prefs.expert || !Self::expert_only(s)))
            .filter(|s| seen.insert((s.tab.clone(), s.name.clone())))
            .cloned().collect();
        if self.menus().is_empty() {
            let at = self.menu_at();
            let mut list = list;
            list.sort_by_key(|s| (tab_idx(self.layout_tab(s)), at(s)));
            return list.into_iter().map(|s| (s, None)).collect();
        }
        let menu_idx = |m: &Option<String>| m.as_ref().and_then(|m| self.menus().iter().position(|x| &x.name == m)).unwrap_or(usize::MAX);
        type Hit = ((usize, usize, i64), (Setting, Option<String>));
        let mut hits: Vec<Hit> = list.into_iter().map(|s| {
            let menu = self.jump_place(&s, target, now).0;
            let (tab, at) = match &menu {
                Some(m) => {
                    let shown = self.listed_record(&s, target, m);
                    let rank = self.rank_in(m, &self.bind_for(target));
                    (tab_idx(self.layout_tab(&shown)), rank.get(&s.key).copied().unwrap_or(s.order))
                }
                None => (tab_idx(self.layout_tab(&s)), s.order),
            };
            ((menu_idx(&menu), tab, at), (s, menu))
        }).collect();
        hits.sort_by_key(|(k, _)| *k);
        hits.into_iter().map(|(_, h)| h).collect()
    }

    /// Open the page an option opens on the camera, by a setting on it (`menu_rows::Page::key`): its tab and the group
    /// that shows it (`shown_group_of`: the page as on the camera), its first row chosen; in the menu that shows it.
    pub(crate) fn open_page_of(&mut self, key: &str) {
        let Some(s) = self.schema.settings.iter().find(|s| s.key == key).cloned() else { return };
        self.mode = Mode::Edit;
        self.switch_menu_for(&s);
        self.select(Some(self.view_of(&s)), Some(self.shown_group_of(&s)), None);
        self.focus = Focus::Items;
    }

    /// Choose a row in the window, the one way every site chooses or clears one (a jump, a click on a row or a group,
    /// the arrow keys, My Menu's page, a menu picked, another set edited): the page `view` (None: the page shown
    /// stays), the group `group`, and the row `row` by its name and key together (None: no row chosen), no option's
    /// box marked. The name and the key then always name one row, which is what `follow_selection` acts on.
    pub(crate) fn select(&mut self, view: Option<View>, group: Option<String>, row: Option<(&str, &str)>) {
        if let Some(v) = view {
            self.view = v;
        }
        self.group = group;
        (self.item, self.item_key) = row.map_or((None, None), |(n, k)| (Some(n.to_string()), Some(k.to_string())));
        self.item_head = None;
        self.sub_focus = None;
    }

    /// The row camera menu `menu` shows for the definition's setting `s` (or a copy of it) in set `target`, where that
    /// menu lists the setting's row (`menus_of`), as it lays it out (`listed_record`; outside Expert mode the row of the
    /// setting, whichever record it shows there). None where the menu does not list it. Where a picked menu, another
    /// set edited or Compare's Open in Edit keeps the row chosen.
    pub(crate) fn row_in_menu(&self, s: &Setting, target: usize, menu: &str) -> Option<Setting> {
        let d = self.def_of(s);
        let row = if self.prefs.expert { d } else { self.main_of(d).unwrap_or(d) };
        self.menus_of(d).iter().any(|m| m == menu).then(|| self.listed_record(row, target, menu))
    }

    /// The pages `s`'s options open on the camera (`menu_rows::pages`: Picture Profile's PP1…), in the set edited; of a
    /// setting laid out for a menu, in that menu.
    pub(crate) fn option_pages(&self, s: &Setting) -> Vec<menu_rows::Page> {
        if !menu_rows::is_own(s) {
            return Vec::new();
        }
        match s.shown_in.as_deref().filter(|m| self.menu_named(m).is_some()) {
            Some(m) => menu_rows::pages(s, &self.settings_in_menu(self.target, m, None)),
            None => menu_rows::pages(s, self.settings_in(self.target, None)),
        }
    }

    /// Open a setting in its menu, as a click on an item of the My Menu page does: `go_to`.
    pub(crate) fn open_in_menu(&mut self, s: &Setting) {
        self.go_to(s);
    }

    /// A jump to setting `s` in the window, the way every jump goes: the menu that shows it (`jump_place`, where the
    /// Menu shows the camera's menus), the page that shows its tab (`shown_view`), its group (a family's by its title:
    /// `shown_group`) and its row chosen, as that menu lays it out (`listed_record`: of a setting the camera keeps a copy
    /// of per shooting mode, the row that shows it). Changes no record.
    pub(crate) fn go_to(&mut self, s: &Setting) {
        self.switch_menu_for(s);
        let shown = match self.menu_shown() { Some(m) => self.listed_record(s, self.target, &m), None => s.clone() };
        // of two rows of one name, this one (`pick_row`)
        self.select(Some(self.shown_view(View::Tab(self.entry_here(&shown)))), Some(self.group_here(&shown)), Some((&shown.name, &shown.key)));
        self.focus = Focus::Items;
    }

    /// Each title the row of the definition's setting `s` takes: its own name (its full name) and its setting's (a
    /// copy), and what each camera menu's row showing it is titled.
    fn titles_of(&self, s: &Setting) -> Vec<String> {
        let d = self.def_of(s);
        let mut t = vec![s.name.clone(), d.name.clone()];
        t.extend(self.main_of(d).map(|m| m.name.clone()));
        t.extend(self.menus().iter().map(|m| self.listed_record(s, self.target, &m.name).name));
        t
    }

    /// Show the menu a jump to `s` opens (`jump_place`), where it is not the one shown.
    fn switch_menu_for(&mut self, s: &Setting) {
        let now = self.menu_shown();
        if let Some(m) = self.menu_for(s, self.target, now.as_deref()) {
            if Some(&m) != now.as_ref() {
                self.menu = Some(MenuChoice { name: m, target: self.target, opened: self.doc.as_ref().map_or(0, |d| d.opened) });
            }
        }
    }

    /// Keep the window's chosen row where a jump set it by the definition's setting (`item_key`, as every jump does):
    /// the menu that shows that setting, and its row there as that menu titles it and picks its record. Called once
    /// a frame, before the pages are drawn; nothing without menus, or with a row of the menu shown chosen.
    pub(crate) fn follow_selection(&mut self) {
        if self.menus().is_empty() || self.mode != Mode::Edit {
            return;
        }
        let chosen = self.item_key.as_ref().and_then(|k| self.index_of_key(k)).map(|i| self.schema.settings[i].clone());
        // another set edited, or a file opened: its own menu, and the row chosen only where that menu shows it
        let opened = self.doc.as_ref().map_or(0, |d| d.opened);
        if self.menu.as_ref().is_none_or(|c| c.target != self.target || c.opened != opened) {
            let Some(m) = self.opening_menu(self.target) else { return };
            self.menu = Some(MenuChoice { name: m.clone(), target: self.target, opened });
            let row = chosen.and_then(|s| self.row_in_menu(&s, self.target, &m));
            self.select(None, self.group.clone(), row.as_ref().map(|r| (r.name.as_str(), r.key.as_str())));
            return;
        }
        if !matches!(self.view, View::Tab(_)) {
            return;
        }
        let Some(s) = chosen else { return };
        // only a row whose name is one its key's setting takes: a name set without its key (no site does: `select`)
        // stays, and the stale key goes
        if !self.item.as_ref().is_some_and(|i| self.titles_of(&s).contains(i)) {
            self.item_key = None;
            return;
        }
        let now = self.menu_shown();
        let menu = self.jump_place(&s, self.target, now.as_deref()).0;
        let shown = match &menu { Some(m) => self.listed_record(&s, self.target, m), None => return };
        if menu == now && self.item.as_ref() == Some(&shown.name) && self.item_key.as_ref() == Some(&shown.key) {
            return;
        }
        self.switch_menu_for(&s);
        self.select(Some(self.shown_view(View::Tab(self.entry_here(&shown)))), Some(self.group_here(&shown)), Some((&shown.name, &shown.key)));
    }

    // --- the camera's menus (`camera.menus`): the one the Menu shows, what it lists, which record a row shows ---

    /// The camera's menus the Menu offers to pick one of (`Camera::menu_list`), in the definition's order, in the "As on
    /// the camera" layout only. Empty: no choice of menu (none or one in the definition, or the flat list), the rows as
    /// before menus.
    pub(crate) fn menus(&self) -> &[MenuDef] {
        if self.camera_layout() { self.schema.camera.menu_list() } else { &[] }
    }

    /// The menu of `menus` named `name`.
    pub(crate) fn menu_named(&self, name: &str) -> Option<&MenuDef> {
        self.menus().iter().find(|m| m.name == name)
    }

    /// The shooting mode set `target` of the open file is in (`section_mode`: the live settings by `camera.live_mode`,
    /// a memory set by `memory_sets.modes`), as the definition names it; None where it is not known or no file is open.
    pub(crate) fn set_mode(&self, target: usize) -> Option<String> {
        self.doc.as_ref().and_then(|d| self.section_mode(&d.edited, target))
    }

    /// The menu set `target` opens on: the menu whose modes hold the set's shooting mode (`set_mode`), else the first;
    /// None without menus (`menus`).
    pub(crate) fn opening_menu(&self, target: usize) -> Option<String> {
        let first = self.menus().first()?;
        let mode = self.set_mode(target);
        Some(mode.and_then(|m| self.menus().iter().find(|x| x.modes.contains(&m))).unwrap_or(first).name.clone())
    }

    /// The menu the window shows: the one picked for the set edited in this opening of the file (`set_menu`, a jump),
    /// else the one that set opens on (`opening_menu`). So it follows the set edited and a file opened, and otherwise
    /// keeps the choice. None without menus.
    pub(crate) fn menu_shown(&self) -> Option<String> {
        let opened = self.doc.as_ref().map_or(0, |d| d.opened);
        match &self.menu {
            Some(c) if c.opened == opened && c.target == self.target && self.menu_named(&c.name).is_some() => Some(c.name.clone()),
            _ => self.opening_menu(self.target),
        }
    }

    /// Show menu `name` in the window (one of `menus`; any other name changes nothing). Changes no record. The row
    /// chosen stays chosen where the menu shows its setting; else none is, on the page shown where the menu lists it,
    /// else on the first tab it lists.
    pub(crate) fn set_menu(&mut self, name: &str) {
        if self.menu_named(name).is_none() {
            return;
        }
        let chosen = self.item_key.as_ref().and_then(|k| self.index_of_key(k)).map(|i| self.schema.settings[i].clone());
        self.menu = Some(MenuChoice { name: name.to_string(), target: self.target, opened: self.doc.as_ref().map_or(0, |d| d.opened) });
        match chosen.and_then(|s| self.row_in_menu(&s, self.target, name)) {
            Some(e) => {
                let (view, group) = if matches!(self.view, View::Tab(_)) { (Some(self.shown_view(View::Tab(self.entry_here(&e)))), Some(self.group_here(&e))) } else { (None, self.group.clone()) };
                self.select(view, group, Some((&e.name, &e.key)));
            }
            None => {
                let mut page = (None, self.group.clone());
                if let View::Tab(t) = &self.view {
                    if !self.side_bar_lists_in(self.target, Some(name), t, "", false) {
                        let first = self.menu_tabs().into_iter().find(|t| self.side_bar_lists_in(self.target, Some(name), t, "", false));
                        page = (Some(View::Tab(first.unwrap_or_default())), None);
                    }
                }
                self.select(page.0, page.1, None);
            }
        }
    }

    /// A menu button's hover, window and page alike: the definition's words for it (`MenuDef::hover`), and on the menu
    /// of the mode the open file's live settings were saved in, "This file was saved in Movie mode." Empty with neither.
    pub(crate) fn menu_hover(&self, name: &str) -> String {
        let Some(m) = self.menu_named(name) else { return String::new() };
        let mut words: Vec<String> = m.hover.iter().filter(|h| !h.is_empty()).cloned().collect();
        if let Some(mode) = self.set_mode(0).filter(|x| m.modes.contains(x)) {
            words.push(format!("This file was saved in {mode} mode."));
        }
        words.join(" ")
    }

    /// The index in `camera.main_tiles` of the tile set the Main page shows in menu `menu` (`MenuDef::main_tiles`);
    /// None without menus or where the menu names none there.
    pub(crate) fn menu_tile_set(&self, menu: &str) -> Option<usize> {
        let name = self.menu_named(menu)?.main_tiles.as_deref()?;
        self.schema.camera.main_tiles.as_ref()?.0.iter().position(|t| t.name == name)
    }

    /// The sets the "Editing:" row offers in menu `menu`: the live settings and, outside Expert mode, the memory sets
    /// whose shooting mode is one of the menu's (`memory_sets.modes`); every set in Expert mode; without a menu (None,
    /// or a name `menus` does not hold) the live settings and the dial's memories, as before menus.
    pub(crate) fn menu_sets(&self, menu: Option<&str>) -> Vec<usize> {
        if self.prefs.expert {
            return (0..self.n_sections()).collect();
        }
        match menu.and_then(|m| self.menu_named(m)) {
            Some(m) => std::iter::once(0).chain((1..self.n_sections()).filter(|&s| self.schema.camera.memory_mode(s).is_some_and(|x| m.modes.iter().any(|y| y == x)))).collect(),
            None => std::iter::once(0).chain(self.dial_sets()).collect(),
        }
    }

    /// How set `target`'s rows pick the record they show (`Bind::Set`, by the set's shooting mode). A mode no menu
    /// names counts as one not known: each row shows the setting itself, in every menu, which holds the live value.
    pub(crate) fn bind_for(&self, target: usize) -> Bind {
        Bind::Set(self.set_mode(target).filter(|m| self.menus().iter().any(|x| x.modes.contains(m))))
    }

    /// The definition's own setting a row shows (`s` itself, or the setting a menu laid `s` out from, by key).
    pub(crate) fn def_of<'a>(&'a self, s: &'a Setting) -> &'a Setting {
        if s.shown_in.is_none() {
            return s;
        }
        self.index_of_key(&s.key).map_or(s, |i| &self.schema.settings[i])
    }

    /// The full name of the setting a row shows, as the definition names it: for the detail panel, where a menu titles
    /// the row as the camera draws it (`listed`: "SteadyShot" for "SteadyShot (Movie)", "ISO" for "ISO (movie)").
    pub(crate) fn full_name(&self, s: &Setting) -> String {
        self.def_of(s).name.clone()
    }

    /// The copy of setting `s` that holds menu `menu`'s value: its one copy whose `copy_for` meets the menu's modes;
    /// None when none does, or more than one (then its rows are as before menus).
    pub(crate) fn copy_for_menu(&self, s: &Setting, menu: &str) -> Option<&Setting> {
        let m = self.schema.camera.menu_named(menu)?;
        let s = self.def_of(s);
        let mut hits = s.copies.iter().filter_map(|k| self.index_of_key(k)).map(|i| &self.schema.settings[i])
            .filter(|c| c.copy_for.iter().any(|x| m.modes.contains(x)));
        let first = hits.next()?;
        hits.next().is_none().then_some(first)
    }

    /// The record setting `s`'s row shows and edits in menu `menu` (point 4 of the design), as `bind` picks: `Set(mode)`,
    /// the setting itself where `mode` is one of the menu's modes or not known, else its copy for the menu
    /// (`copy_for_menu`); `Menu`, its copy for the menu. The setting itself where it has no such copy, and for a copy.
    pub(crate) fn row_record<'a>(&'a self, s: &'a Setting, menu: &str, bind: &Bind) -> &'a Setting {
        let s = self.def_of(s);
        let (Some(m), Some(c)) = (self.schema.camera.menu_named(menu), self.copy_for_menu(s, menu)) else { return s };
        match bind {
            Bind::Menu => c,
            Bind::Set(Some(mode)) if !m.modes.contains(mode) => c,
            Bind::Set(_) => s,
        }
    }

    /// The menus whose rows list the definition's setting `s` (in their order): a setting placed on a row, the menus
    /// that place it (`Camera::menus_of`); a copy, its setting's; a setting placed nowhere, the menus whose rows hold
    /// a setting of its group (it is under "More settings in this group" there), else every menu (under the entry for
    /// what the camera's menus do not hold, a family's table, My Menu). Empty without menus.
    pub(crate) fn menus_of(&self, s: &Setting) -> Vec<String> {
        if self.menus().is_empty() {
            return Vec::new();
        }
        let s = self.def_of(s);
        let s = self.main_of(s).unwrap_or(s);
        if s.placed_anywhere() {
            return self.schema.camera.menus_of(s).into_iter().map(str::to_string).collect();
        }
        let holding: Vec<String> = self.menus().iter().filter(|m| self.menu_groups(&m.name).contains(&(s.tab.clone(), s.group.clone()))).map(|m| m.name.clone()).collect();
        if holding.is_empty() { self.menus().iter().map(|m| m.name.clone()).collect() } else { holding }
    }

    /// The (tab, group) of every row menu `menu` places a setting on, as the camera's layout has them
    /// (`menu_rows::camera_tab`, `camera_group`), and of each such setting's own: where a setting placed nowhere joins it.
    fn menu_groups(&self, menu: &str) -> MenuGroups {
        let key = (self.schema_gen, menu.to_string());
        if let Some((_, g)) = self.menus_cache.borrow().groups.iter().find(|(k, _)| *k == key) {
            return g.clone();
        }
        let mut out = std::collections::HashSet::new();
        for s in self.schema.settings.iter().filter(|s| s.copy_of.is_none() && s.placed_anywhere()) {
            if self.schema.camera.menus_of(s).contains(&menu) {
                let p = s.place_in(menu);
                if p.placed() {
                    out.insert((menu_rows::camera_tab(&p).to_string(), menu_rows::camera_group(&p).to_string()));
                    out.insert((s.tab.clone(), s.group.clone()));
                }
            }
        }
        let out = std::rc::Rc::new(out);
        let mut cache = self.menus_cache.borrow_mut();
        if cache.groups.len() >= MENUS_KEPT { cache.groups.remove(0); }
        cache.groups.push((key, out.clone()));
        out
    }

    /// Where a jump to setting `s` (the definition's, or as a menu lays it out) lands for set `target`, the Menu showing
    /// menu `now`: the menu (`menu_for`; None without menus), the Menu entry and the group that show it there. A search
    /// hit's "Where" says these, and the page's links carry the three (`open_menu`, …).
    pub(crate) fn jump_place(&self, s: &Setting, target: usize, now: Option<&str>) -> (Option<String>, String, String) {
        let menu = self.menu_for(s, target, now);
        let shown = match &menu { Some(m) => self.listed_record(s, target, m), None => s.clone() };
        (menu, self.entry_here(&shown), self.group_here(&shown))
    }

    /// The menu of `jump_place`: of the menus that list `s`'s row (`menus_of`), those whose row shows that very record
    /// (`listed_record`: a setting the camera keeps once, every one; the setting itself, the menu of the set's mode; a
    /// copy, the menus whose mode it is the copy for), and of those `now`, else the menu of the set's mode, else the
    /// first. Where no row shows it (the copy for the set's own mode, whose value the setting itself shows there): the
    /// menu of that copy's mode, on the row that shows its setting itself. Else as before: `now` where it lists the row,
    /// the set's mode's, the first.
    fn menu_for(&self, s: &Setting, target: usize, now: Option<&str>) -> Option<String> {
        if self.menus().is_empty() {
            return None;
        }
        let d = self.def_of(s);
        let fit = self.menus_of(d);
        let own = self.opening_menu(target);
        let pick = |among: &[String]| now.filter(|n| among.iter().any(|m| m == n)).map(str::to_string)
            .or_else(|| own.clone().filter(|o| among.contains(o)))
            .or_else(|| among.first().cloned());
        let showing: Vec<String> = fit.iter().filter(|m| self.listed_record(d, target, m).key == d.key).cloned().collect();
        let of_its_mode: Vec<String> = fit.iter().filter(|m| self.schema.camera.menu_named(m).is_some_and(|md| md.modes.iter().any(|x| d.copy_for.contains(x)))).cloned().collect();
        pick(&showing).or_else(|| pick(&of_its_mode)).or_else(|| pick(&fit)).or_else(|| now.map(str::to_string))
    }

    /// The setting the rows of menu `menu` show for the definition's setting `s` in set `target` (`listed`): `s` as that
    /// menu lays it out, or the row that shows it there (a copy in its setting's row, a setting whose row shows its
    /// copy); `s` as the menu would lay it out where the menu does not list it.
    pub(crate) fn listed_record(&self, s: &Setting, target: usize, menu: &str) -> Setting {
        let listed = self.listed(menu, &self.bind_for(target));
        match listed.by_key.get(&s.key) {
            Some(&i) => listed.rows[i].clone(),
            None => self.def_of(s).place_in(menu),
        }
    }

    /// The settings of set `target` one Menu entry lists in menu `menu` (`tab`; None: every entry), before the search
    /// and filters, as that menu lays them out (`listed`).
    pub(crate) fn settings_in_menu(&self, target: usize, menu: &str, tab: Option<&str>) -> Vec<Setting> {
        self.listed_in(target, menu, &self.bind_for(target), tab)
    }

    /// `settings_in_menu`, the rows picking their records as `bind` says.
    fn listed_in(&self, target: usize, menu: &str, bind: &Bind, tab: Option<&str>) -> Vec<Setting> {
        let in_set = target != 0;
        let in_entry = self.in_entry(tab);
        self.listed(menu, bind).rows.iter()
            .filter(|s| in_entry(s))
            .filter(|s| if in_set { s.in_sets } else { s.area == "global" })
            .filter(|s| self.prefs.expert || !Self::expert_only(s))
            .cloned().collect()
    }

    /// Every setting menu `menu` lists, as it lays each out (`Setting::place_in`, design points 3 and 4): those its rows
    /// hold (`menus_of`), a setting the camera keeps a copy of per shooting mode as the record `bind` picks
    /// (`row_record`) at the setting's place under its name, and outside Expert mode none of those copies as rows of
    /// their own; a setting placed nowhere where `menus_of` lists it. Outside Expert mode a row alone on its place in
    /// the camera's menu (no other setting of its area there, but the choices of its options and Expert mode's) is
    /// titled by its place's last label, as
    /// the camera draws it; the setting's full name is `full_name`. The definition's order. Worked out once per
    /// definition, menu, `bind` and Expert mode.
    pub(crate) fn listed(&self, menu: &str, bind: &Bind) -> std::rc::Rc<Listed> {
        let key: MenuKey = (self.schema_gen, menu.to_string(), bind.clone(), self.prefs.expert);
        if let Some((_, l)) = self.menus_cache.borrow().listed.iter().find(|(k, _)| *k == key) {
            return l.clone();
        }
        let expert = self.prefs.expert;
        let mut rows: Vec<Setting> = Vec::new();
        let mut by_key: std::collections::HashMap<String, usize> = Default::default();
        let mut row_of: std::collections::HashMap<String, usize> = Default::default();          // a setting's row, by its key
        let mut hidden: Vec<(String, String)> = Vec::new();          // a copy shown in its setting's row: (copy, setting)
        let in_menu = |s: &Setting| self.menus_of(s).iter().any(|m| m == menu);
        for s in &self.schema.settings {
            if !in_menu(s) {
                continue;
            }
            if let Some(main) = self.main_of(s) {
                if !expert && self.copy_for_menu(main, menu).is_some() {
                    hidden.push((s.key.clone(), main.key.clone()));
                    continue;
                }
            }
            let p = s.place_in(menu);
            let rec = if expert { s } else { self.row_record(s, menu, bind) };
            let row = if rec.key == s.key {
                p
            } else {
                // the copy's record at the setting's place, in its tab and group, under its name
                let mut b = rec.place_in(menu);
                (b.name, b.tab, b.group, b.row, b.row_at, b.row_tab, b.row_group, b.under_option) = (p.name, p.tab, p.group, p.row, p.row_at, p.row_tab, p.row_group, p.under_option);
                b
            };
            row_of.insert(s.key.clone(), rows.len());
            by_key.insert(s.key.clone(), rows.len());
            by_key.insert(row.key.clone(), rows.len());
            rows.push(row);
        }
        for (copy, main) in hidden {
            if let Some(&i) = row_of.get(&main) {
                by_key.entry(copy).or_insert(i);
            }
        }
        if !expert {
            // a row alone on its place in the camera's menu (among the live settings', or one memory set's, that are
            // not Expert mode's), titled as the camera draws it (`menu_rows::drawn`), unless another row under the same
            // heading would then be titled alike
            let place = |s: &Setting| (s.area.clone(), s.row.clone(), s.row_at.clone(), menu_rows::camera_tab(s).to_string(), menu_rows::camera_group(s).to_string());
            let above = |s: &Setting| s.row.len().saturating_sub(1);
            let head = |s: &Setting| -> HeadKey { (s.area.clone(), menu_rows::camera_tab(s).to_string(), menu_rows::camera_group(s).to_string(), s.row[..above(s)].to_vec(), s.row_at[..above(s).min(s.row_at.len())].to_vec()) };
            let counted = |s: &Setting| s.placed() && s.under_option.is_none() && !Self::expert_only(s);
            let mut on: std::collections::HashMap<PlaceKey, usize> = Default::default();
            for s in rows.iter().filter(|s| counted(s)) {
                *on.entry(place(s)).or_default() += 1;
            }
            let titles: Vec<Option<String>> = rows.iter().map(|s| {
                (counted(s) && !s.on_page() && on.get(&place(s)) == Some(&1)).then(|| s.row.last().map(|l| menu_rows::drawn(l).to_string()).filter(|l| !l.is_empty())).flatten()
            }).collect();
            let mut alike: std::collections::HashMap<(HeadKey, String), usize> = Default::default();
            for (s, t) in rows.iter().zip(&titles).filter(|(s, _)| counted(s)) {
                *alike.entry((head(s), t.clone().unwrap_or_else(|| s.name.clone()))).or_default() += 1;
            }
            for (s, t) in rows.iter_mut().zip(titles) {
                if let Some(t) = t {
                    if alike.get(&(head(s), t.clone())) == Some(&1) {
                        s.name = t;
                    }
                }
            }
        }
        let listed = std::rc::Rc::new(Listed { rows, by_key });
        let mut cache = self.menus_cache.borrow_mut();
        if cache.listed.len() >= MENUS_KEPT { cache.listed.remove(0); }
        cache.listed.push((key, listed.clone()));
        listed
    }

    /// `beside` for set `target` in menu `menu` (None: as before menus): the settings shown beside `s`'s options in the
    /// detail panel, each with its option, from its camera group as that menu lays it out.
    pub(crate) fn beside_in(&self, target: usize, menu: Option<&str>, s: &Setting) -> Vec<(Setting, String)> {
        if !menu_rows::is_own(s) {
            return Vec::new();
        }
        let tab = self.layout_tab(s).to_string();
        let group = menu_rows::camera_group(s).to_string();
        let among: Vec<Setting> = match menu.filter(|m| self.menu_named(m).is_some()) {
            Some(m) => self.settings_in_menu(target, m, Some(&tab)),
            None => self.settings_in(target, Some(&tab)).cloned().collect(),
        };
        menu_rows::sub_choices(s, among.iter().filter(|o| menu_rows::camera_group(o) == group)).into_iter().map(|(x, o)| (x.clone(), o)).collect()
    }

    /// The Menu's entries a section shows (`compare`: Compare's, else Edit's) for set `target` in menu `menu`, the one
    /// function both build their bar from: Compare's "All settings" first; Main, where the definition has its tiles; My
    /// Menu, where it has My Menu; then the tabs, Other and the entry for what the camera's menus do not hold as
    /// `side_bar_lists_in` lists them (the search `q` and Only edited count for Other and that entry, as in the window).
    pub(crate) fn bar_keys(&self, compare: bool, target: usize, menu: Option<&str>, q: &str, only_changed: bool) -> Vec<BarKey> {
        let mut out = Vec::new();
        if compare {
            out.push(BarKey::All);
        }
        if self.schema.camera.main_tiles.as_ref().is_some_and(|t| !t.0.is_empty()) {
            out.push(BarKey::Main);
        }
        if self.has_mymenu_page() {
            out.push(BarKey::MyMenu);
        }
        out.extend(self.menu_tabs().into_iter().filter(|t| self.side_bar_lists_in(target, menu, t, q, only_changed)).map(BarKey::Tab));
        out
    }

    /// Edit's entries of the Menu (`bar_keys`) for set `target` in menu `menu`, with the search `q` and Only edited:
    /// Main by `text.main_title`; My Menu by its words and hover (`mymenu_entry_words`) and its edits; each tab by name
    /// with its colour, how many settings it lists (`visible_count_in`) and how many are edited (`counts_in`), the entry
    /// for what the menus do not hold with its hover. The window's and the page's bar alike.
    pub(crate) fn edit_entries(&self, target: usize, menu: Option<&str>, q: &str, only_changed: bool) -> Vec<BarEntry> {
        let off = self.schema.camera.text.off_menu_name();
        self.bar_keys(false, target, menu, q, only_changed).into_iter().map(|key| match &key {
            BarKey::Main => BarEntry { label: self.schema.camera.text.main_title().to_string(), color: None, hover: None, count: None, badge: 0, key },
            BarKey::MyMenu => {
                let (label, hover) = self.mymenu_entry_words();
                let name = self.schema.camera.text.my_menu_name();
                BarEntry { label, color: Some(tab_color(&self.schema.camera, name)), hover: Some(hover), count: None, badge: self.mymenu_edits(), key }
            }
            BarKey::Tab(t) => BarEntry {
                label: t.clone(), color: Some(tab_color(&self.schema.camera, t)), hover: (t == off).then(|| Self::off_menu_hover().to_string()),
                count: Some(self.visible_count_in(target, menu, Some(t), q, only_changed)), badge: self.counts_in(target, menu, Some(t)), key: key.clone(),
            },
            BarKey::All => BarEntry { label: ALL_SETTINGS.to_string(), color: None, hover: None, count: None, badge: 0, key },
        }).collect()
    }

    /// The sets the "Editing:" row offers as buttons for set `target` in menu `menu`, the window's and the page's alike:
    /// outside Expert mode in one of the camera's menus, the live settings and the memory sets of that menu's shooting
    /// modes (`menu_sets`), and `target` should it be another, so the row always shows the set edited; else the live
    /// settings and the dial's memories (in Expert mode the other memories are in a list of their own beside them).
    pub(crate) fn editing_sets_in(&self, target: usize, menu: Option<&str>) -> Vec<usize> {
        match menu.filter(|m| !self.prefs.expert && self.menu_named(m).is_some()) {
            Some(m) => {
                let mut v = self.menu_sets(Some(m));
                if !v.contains(&target) && target < self.n_sections() {
                    v.push(target);
                    v.sort_unstable();
                }
                v
            }
            None => std::iter::once(0).chain(self.dial_sets()).collect(),
        }
    }

    /// The sets Compare's column picker offers in menu `menu`, the window's and the page's alike: in one of the camera's
    /// menus outside Expert mode, that menu's (`menu_sets`), so the picker holds as many as before menus; else every set
    /// a column may show (`shown_sections`). A column chosen already stays whatever the menu.
    pub(crate) fn column_sets_in(&self, menu: Option<&str>) -> Vec<usize> {
        match menu.filter(|m| !self.prefs.expert && self.menu_named(m).is_some()) {
            Some(m) => self.menu_sets(Some(m)),
            None => self.shown_sections(),
        }
    }

    /// The sets the column picker draws a toggle for in menu `menu`, the window's and the page's alike: those it offers
    /// (`column_sets_in`) and any of the columns `cols` chosen already, in the sets' order.
    pub(crate) fn picker_sets(&self, menu: Option<&str>, cols: &[Col]) -> Vec<usize> {
        let mut v = self.column_sets_in(menu);
        v.extend(cols.iter().map(|c| c.section));
        v.sort_unstable();
        v.dedup();
        v
    }

    /// Compare's rows of Menu entry `entry` in menu `menu` laid out as Edit lays the entry out, the live settings with
    /// the search `q`: (the entry's name, the group, the row's linked records), its groups in their order, a group's
    /// rows as `group_lines` lays them out, the choices beside an option right after its row, a family's settings each a
    /// row under its own group but those the page an option opens shows (which come with that page's group), every row
    /// bound to the record for that menu (`Bind::Menu`, so files saved in different modes compare like for like). Each
    /// setting under one entry once: All is every tab's and My Menu's, in the Menu's order; My Menu its own tab's
    /// settings (`text.my_menu_name`); Main the settings of the menu's tiles (`menu_tile_set`, else the first set) under
    /// each tile's caption, which the tabs list too. Compare lists them through `compare_rows`.
    pub(crate) fn entry_rows(&self, menu: Option<&str>, entry: &BarKey, q: &str) -> Vec<(String, String, Vec<Setting>)> {
        let q = Self::query(q);
        let menu = menu.filter(|m| self.menu_named(m).is_some());
        let matches = |s: &Setting| q.is_empty() || Self::matches_query(s, &q) || Self::matches_query(self.def_of(s), &q);
        let link = |list: Vec<Setting>| -> Vec<Vec<Setting>> {
            let mut rows: Vec<Vec<Setting>> = Vec::new();
            for s in list {
                match rows.iter_mut().find(|r| r[0].links_with(&s)) {
                    Some(r) => r.push(s),
                    None => rows.push(vec![s]),
                }
            }
            rows
        };
        match entry {
            BarKey::All => self.bar_keys(true, 0, menu, "", false).iter().filter(|k| matches!(k, BarKey::Tab(_) | BarKey::MyMenu)).flat_map(|k| self.entry_rows(menu, k, &q)).collect(),
            BarKey::Main => {
                let Some(sets) = self.schema.camera.main_tiles.as_ref() else { return Vec::new() };
                let at = menu.and_then(|m| self.menu_tile_set(m)).unwrap_or(0);
                let Some(set) = sets.0.get(at) else { return Vec::new() };
                let mut out = Vec::new();
                for tile in &set.tiles {
                    // every record the tile shows, in the live settings or a memory, as Edit's Main draws it: a fraction's
                    // two parts too, Expert-only or not (`tile_records`)
                    let keys: Vec<&String> = tile.keys.iter().chain(&tile.memory_keys).chain(&tile.numerator_key).chain(&tile.denominator_key).collect();
                    let list: Vec<Setting> = keys.iter().filter_map(|k| self.index_of_key(k)).map(|i| &self.schema.settings[i])
                        .map(|s| match menu { Some(m) => self.row_record(s, m, &Bind::Menu).clone(), None => s.clone() })
                        .filter(|s| matches(s)).collect();
                    out.extend(link(list).into_iter().map(|r| (self.schema.camera.text.main_title().to_string(), tile.caption.clone(), r)));
                }
                out
            }
            BarKey::MyMenu => {
                // as Edit's My Menu page: its places, page by page, then the settings of its own tab, under its name
                let name = self.schema.camera.text.my_menu_name().to_string();
                let mut out = self.place_rows(&q);
                out.extend(self.entry_rows(menu, &BarKey::Tab(name.clone()), &q));
                out
            }
            BarKey::Tab(t) => {
                let mut list: Vec<Setting> = match menu {
                    Some(m) => self.listed_in(0, m, &Bind::Menu, Some(t)),
                    None => self.settings_in(0, Some(t)).cloned().collect(),
                }.into_iter().filter(|s| matches(s)).collect();
                // the records a Main tile shows that the live settings' rows leave out, under the entry that shows them
                // (`tile_records`), so Main's rows are All's
                list.extend(self.tile_records(&q).into_iter().filter(|s| self.entry_here(s) == *t).map(|s| match menu { Some(m) => s.place_in(m), None => s }));
                let groups = self.groups_of(list, t);
                // a family's setting on the page an option opens comes with that page's group, not again in the family's
                let on_pages: std::collections::HashSet<String> = groups.iter().filter(|(_, family, _)| !family).flat_map(|(_, _, rows)| rows.iter().flatten().map(|s| s.key.clone())).collect();
                let mut out = Vec::new();
                for (group, family, rows) in groups {
                    if family {
                        // each setting of a family's table a row of its own, under its own group (a profile's)
                        let mut by_group: Vec<(String, Vec<Setting>)> = Vec::new();
                        for s in rows.into_iter().flatten().filter(|s| !on_pages.contains(&s.key)) {
                            match by_group.iter_mut().find(|(g, _)| *g == s.group) {
                                Some((_, v)) => v.push(s),
                                None => by_group.push((s.group.clone(), vec![s])),
                            }
                        }
                        for (g, list) in by_group {
                            out.extend(link(list).into_iter().map(|r| (t.clone(), g.clone(), r)));
                        }
                        continue;
                    }
                    let lines = self.group_lines(&rows);
                    let firsts: Vec<&Setting> = rows.iter().map(|r| &r[0]).collect();
                    let mut done = vec![false; rows.len()];
                    for i in menu_rows::order(&lines) {
                        if !std::mem::replace(&mut done[i], true) {
                            out.push((t.clone(), group.clone(), rows[i].clone()));
                        }
                        // the choices beside its options, right after it, as its detail panel lists them
                        for (sub, _) in menu_rows::sub_choices(&rows[i][0], firsts.iter().copied()) {
                            if let Some(j) = rows.iter().position(|r| r[0].key == sub.key) {
                                if !std::mem::replace(&mut done[j], true) {
                                    out.push((t.clone(), group.clone(), rows[j].clone()));
                                }
                            }
                        }
                    }
                    out.extend((0..rows.len()).filter(|&i| !done[i]).map(|i| (t.clone(), group.clone(), rows[i].clone())));
                }
                out
            }
        }
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
                // the groups of an entry in the camera's menu a jump opens (`jump_place`; none without menus)
                let mut groups: std::collections::HashMap<(Option<String>, String), Vec<String>> = Default::default();
                for s in app.schema.settings.iter().filter(|s| !s.expert) {
                    let target = if s.area == "global" { 0 } else { 1 };
                    match app.view_of(s) {
                        View::MyMenu => assert!(with_my_menu && on_my_menu.contains(&s.key), "{} is not on the My Menu page", s.name),
                        View::Tab(t) => {
                            assert!(tabs.contains(&t) && t == app.entry_of(s), "{}: {t} is not an entry of the Menu", s.name);
                            assert!(app.settings_in(target, Some(&t)).any(|o| o.key == s.key), "{} is not under {t}", s.name);
                            assert_eq!(app.settings_in(target, None).filter(|o| o.key == s.key).count(), 1);
                            let shown = app.shown_group_of(s);
                            let menu = app.jump_place(s, target, app.menu_shown().as_deref()).0;
                            let held = groups.entry((menu.clone(), t.clone())).or_insert_with(|| app.tab_groups_in(target, menu.as_deref(), &t, "", false).into_iter().map(|(g, _, _)| g).collect());
                            assert!(held.contains(&shown) || app.target != target, "{}: {t} has no group {shown} in {menu:?}", s.name);
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
        // as before menus, whatever the shipped definition lists (this test is not about the menus)
        crate::test_support::as_before_menus(&mut app);
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
        assert_eq!(drawn.len() + 13, rows.len(), "the group still holds (and counts) its thirteen choices: Drive Mode's seven, Bracket Type's six");
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
        let (mut app, dir, user) = sample_app("subscreens", Some(crate::test_support::strip_menus));
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
        let (mut app, dir, user) = sample_app("rowtab", Some(crate::test_support::strip_menus));
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
        let (mut app, dir, user) = sample_app("jumps", Some(crate::test_support::strip_menus));
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        let nth = |app: &App, group: &str, name: &str, n: usize| app.schema.settings.iter().filter(|s| s.group == group && s.name == name && s.area == "global").nth(n).unwrap().clone();
        let hi = nth(&app, "Drive Mode", "Hi(E-Shutter)", 0);
        let fixed = nth(&app, "Zoom", "Fixed Speed REC", 1);
        // a setting of Shooting Mode placed nowhere: one made so where the definition places them all
        let loose = |app: &App| app.schema.settings.iter().find(|s| s.group == "Shooting Mode" && s.area == "global" && !s.placed() && !s.expert).cloned();
        if loose(&app).is_none() {
            let i = app.schema.settings.iter().position(|s| s.group == "Shooting Mode" && s.area == "global" && s.placed() && !s.expert && s.under_option.is_none() && s.copy_of.is_none()).unwrap();
            (app.schema.settings[i].row, app.schema.settings[i].row_at) = (Vec::new(), Vec::new());
            app.schema_gen += 1;
        }
        let unplaced = loose(&app).unwrap();
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

    /// The interface the window's and the page's views build on, with the camera's menus stubbed onto the sample's
    /// definition (`stub_menus`): the menus in the definition's order, the one shown, the entries and groups of a
    /// menu, the record a row shows, a jump that changes menus, the search across menus; a menu picked changes no
    /// byte of the file. Without menus: none, and the bar as before.
    #[test]
    fn the_menus_interface() {
        use crate::test_support::stub_menus;
        let (mut app, dir, user) = sample_app("menus_iface", Some(stub_menus));
        let names: Vec<&str> = app.menus().iter().map(|m| m.name.as_str()).collect();
        assert_eq!(names, ["Still", "Movie", "S&Q"]);
        let first = app.opening_menu(0).unwrap();
        assert_eq!(app.menu_shown(), Some(first.clone()));
        let tabs = |app: &App, m: &str| app.edit_entries(0, Some(m), "", false).into_iter().map(|e| (e.key, e.count)).collect::<Vec<_>>();
        assert!(tabs(&app, "Movie").iter().any(|(k, n)| *k == BarKey::Tab("Shooting".into()) && n.is_some_and(|n| n > 0)));
        assert_ne!(tabs(&app, "Movie"), tabs(&app, "Still"));
        let groups = |app: &App, m: &str| app.tab_groups_in(0, Some(m), "Shooting", "", false).into_iter().map(|(g, _, _)| g).collect::<Vec<_>>();
        assert!(groups(&app, "Movie").contains(&"TC/UB".to_string()) && !groups(&app, "Still").contains(&"TC/UB".to_string()));
        // the ISO row: in the menu of the file's mode the setting itself, in the other its copy for that menu, under its name
        let iso = app.schema.settings.iter().find(|s| s.key == "global:0x0334").unwrap().clone();
        let other = app.menus().iter().map(|m| m.name.clone()).find(|m| *m != first && app.copy_for_menu(&iso, m).is_some()).unwrap();
        let shown = app.listed_record(&iso, 0, &other);
        assert_eq!((shown.name.as_str(), shown.key.as_str()), ("ISO", app.copy_for_menu(&iso, &other).unwrap().key.as_str()));
        assert_eq!(app.listed_record(&iso, 0, &first).key, iso.key);
        assert_eq!(app.full_name(&shown), app.copy_for_menu(&iso, &other).unwrap().name);
        // a menu picked changes no byte of the file
        let before = app.doc.as_ref().unwrap().edited.to_bytes();
        app.set_menu("S&Q");
        assert_eq!(app.menu_shown().as_deref(), Some("S&Q"));
        app.set_menu("Movie");
        assert_eq!(app.doc.as_ref().unwrap().edited.to_bytes(), before);
        // a jump to a row only Movie's menu has, from Still's
        app.set_menu("Still");
        let tc = app.schema.settings.iter().find(|s| s.group == "TC/UB" && s.placed() && s.area == "global" && !s.expert).unwrap().clone();
        app.go_to(&tc);
        assert_eq!(app.menu_shown().as_deref(), Some("Movie"));
        assert_eq!((app.view.clone(), app.group.as_deref()), (View::Tab("Shooting".into()), Some("TC/UB")));
        // the search across menus names the menu a hit opens
        let hits = app.search_hits_in(0, Some("Still"), &tc.name);
        assert!(hits.iter().any(|(s, m)| s.key == tc.key && m.as_deref() == Some("Movie")), "{hits:?}");
        assert!(app.where_in(&tc, 0, Some("Still")).starts_with("Movie > Shooting > TC/UB"));
        done(&dir, &user);
        // without menus: none, and Edit's bar as before
        let (app, dir, user) = sample_app("menus_none", Some(crate::test_support::strip_menus));
        assert!(app.menus().is_empty() && app.menu_shown().is_none());
        let keys: Vec<BarKey> = app.edit_entries(0, None, "", false).into_iter().map(|e| e.key).collect();
        let tabs: Vec<BarKey> = app.menu_tabs().into_iter().filter(|t| app.side_bar_lists(t)).map(BarKey::Tab).collect();
        assert_eq!(keys, [vec![BarKey::Main, BarKey::MyMenu], tabs].concat());
        done(&dir, &user);
    }

    /// The stub's menus given other names and modes (`stub_menus`): the menus and each setting's `row_menus`.
    fn menus_as(v: &mut serde_json::Value, menus: serde_json::Value, rename: &[(&str, &[&str])]) {
        crate::test_support::stub_menus(v);
        v["camera"]["menus"] = menus;
        for s in v["settings"].as_array_mut().unwrap() {
            let Some(was) = s["row_menus"].as_array().cloned() else { continue };
            let mut now: Vec<&str> = Vec::new();
            for w in was.iter().filter_map(|w| w.as_str()) {
                for n in rename.iter().find(|(from, _)| *from == w).map_or(&[][..], |(_, to)| *to) {
                    if !now.contains(n) { now.push(n); }
                }
            }
            s["row_menus"] = serde_json::json!(now);
        }
    }

    /// Review finding 11: one trimming of the search, so "iso", "iso " and " ISO " give the same search hits, the same
    /// rows and counts of each entry, in Edit and in Compare, with menus and without.
    #[test]
    fn the_search_is_trimmed_once_for_every_answer() {
        for stub in [crate::test_support::strip_menus as fn(&mut serde_json::Value), crate::test_support::stub_menus] {
            let (app, dir, user) = sample_app("menus_trim", Some(stub));
            let menu = app.menu_shown();
            let menu = menu.as_deref();
            let answers = |q: &str| {
                let hits: Vec<String> = app.search_hits_in(0, menu, q).into_iter().map(|(s, _)| s.key).collect();
                let counts: Vec<Option<usize>> = app.edit_entries(0, menu, q, false).into_iter().map(|e| e.count).collect();
                let shown: Vec<String> = app.visible_in(0, menu, None, q, false).into_iter().map(|s| s.key).collect();
                let compare: Vec<usize> = app.bar_keys(true, 0, menu, q, false).iter().map(|k| app.compare_rows(menu, k, q).len()).collect();
                (hits, counts, shown, compare)
            };
            let want = answers("iso");
            assert!(!want.0.is_empty());
            for q in ["iso ", " ISO "] {
                assert!(answers(q) == want, "{q:?}");
            }
            done(&dir, &user);
        }
    }

    /// Two menus, Still and Movie, and no menu for S&Q and Time-lapse.
    fn no_sq_menu(v: &mut serde_json::Value) {
        menus_as(v, serde_json::json!([{ "name": "Still", "modes": ["Stills"] }, { "name": "Movie", "modes": ["Movie"] }]),
            &[("Still", &["Still"]), ("Movie", &["Movie"]), ("S&Q", &["Movie"])]);
    }

    /// Review finding 10: a file saved in a mode no menu names (S&Q, with menus for Still and Movie only) and one whose
    /// live mode holds a value the definition does not name behave alike and lose no row: the first menu opens, and in
    /// every menu each row shows the setting itself (no copy bound), which holds the live value; its copies are rows
    /// of none.
    #[test]
    fn a_mode_no_menu_names_shows_the_setting_itself_in_every_menu() {
        for (stub, value, tag) in [(no_sq_menu as fn(&mut serde_json::Value), 2, "menus_no_sq"), (crate::test_support::stub_menus, 9, "menus_odd_mode")] {
            let (mut app, dir, user) = sample_app(tag, Some(stub));
            let lm = app.schema.camera.live_mode.clone().unwrap();
            let rec = setting(&app, &lm.key);
            let mut c = crate::camera::job::test_parse(crate::test_support::SAMPLE_BYTES).unwrap();
            c.sections[0].get_mut(rec.id).unwrap().put(rec.index, value).unwrap();
            let f = dir.join("CAMSET03.DAT");
            std::fs::write(&f, c.to_bytes()).unwrap();
            app.open(f);
            let first = app.menus()[0].name.clone();
            assert_eq!(app.opening_menu(0), Some(first), "{tag}: the first menu");
            let iso = setting(&app, "global:0x0334");
            for m in app.menus().iter().map(|m| m.name.clone()).collect::<Vec<_>>() {
                assert_eq!(app.listed_record(&iso, 0, &m).key, iso.key, "{tag}: {m}: the setting itself");
                let rows = app.settings_in_menu(0, &m, None);
                assert!(rows.iter().any(|s| s.key == iso.key) && !rows.iter().any(|s| iso.copies.contains(&s.key)), "{tag}: {m}: its row, no copy a row");
            }
            done(&dir, &user);
        }
    }

    /// Two menus: "Still", and "Motion" for Movie, S&Q and Time-lapse.
    fn two_menus(v: &mut serde_json::Value) {
        menus_as(v, serde_json::json!([{ "name": "Still", "modes": ["Stills"] }, { "name": "Motion", "modes": ["Movie", "S&Q", "Time-lapse"] }]),
            &[("Still", &["Still"]), ("Movie", &["Motion"]), ("S&Q", &["Motion"])]);
    }

    /// Four menus named otherwise, one per shooting mode.
    fn four_menus(v: &mut serde_json::Value) {
        menus_as(v, serde_json::json!([{ "name": "One", "modes": ["Stills"] }, { "name": "Two", "modes": ["Movie"] }, { "name": "Three", "modes": ["S&Q"] }, { "name": "Four", "modes": ["Time-lapse"] }]),
            &[("Still", &["One"]), ("Movie", &["Two"]), ("S&Q", &["Three", "Four"])]);
    }

    /// Two menus, the first for Stills and Movie, so that both of ISO's copies are for it.
    fn shared_menus(v: &mut serde_json::Value) {
        menus_as(v, serde_json::json!([{ "name": "A", "modes": ["Stills", "Movie"] }, { "name": "B", "modes": ["S&Q", "Time-lapse"] }]),
            &[("Still", &["A"]), ("Movie", &["A"]), ("S&Q", &["B"])]);
    }

    /// One menu: no choice of menu.
    fn one_menu(v: &mut serde_json::Value) {
        menus_as(v, serde_json::json!([{ "name": "Still", "modes": ["Stills", "Movie", "S&Q", "Time-lapse"] }]), &[("Still", &["Still"]), ("Movie", &["Still"]), ("S&Q", &["Still"])]);
    }

    /// One frame of the window.
    fn frame(app: &mut App) {
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame));
    }

    fn setting(app: &App, key: &str) -> Setting {
        app.schema.settings.iter().find(|s| s.key == key).unwrap().clone()
    }

    /// A menu shows its own rows (design point 3): no "In Movie mode" heading in any menu, a row of Movie mode's menu in
    /// Movie's and S&Q's alone, each menu's own SteadyShot titled as the camera draws its row with its full name for the
    /// detail; the entry for what the menus do not hold the same in every menu, a group's unplaced settings under "More
    /// settings in this group" where the menu shows the group. Expert mode: every record a row under its own name.
    #[test]
    fn a_menu_shows_its_own_rows_as_the_camera_draws_them() {
        let (mut app, dir, user) = sample_app("menus_rows", Some(crate::test_support::stub_menus));
        for m in ["Still", "Movie", "S&Q"] {
            for tab in app.menu_tabs() {
                for (g, family, rows) in app.tab_groups_in(0, Some(m), &tab, "", false) {
                    assert!(family || !app.group_lines(&rows).iter().any(|l| matches!(l, Line::Mode(_))), "{m} > {tab} > {g}");
                }
            }
        }
        let row = |app: &App, m: &str, key: &str| app.settings_in_menu(0, m, None).into_iter().find(|s| s.key == key);
        assert!(row(&app, "Movie", "global:0x02e9").is_some() && row(&app, "S&Q", "global:0x02e9").is_some() && row(&app, "Still", "global:0x02e9").is_none());
        let movie = row(&app, "Movie", "global:0x02f9").unwrap();
        assert_eq!((movie.name.as_str(), app.full_name(&movie).as_str()), ("SteadyShot", "SteadyShot (Movie)"));
        assert_eq!(row(&app, "Still", "global:0x02f7").unwrap().name, "SteadyShot");
        assert!(row(&app, "Still", "global:0x02f9").is_none() && row(&app, "Movie", "global:0x02f7").is_none());
        // the entry for what the menus do not hold: the same in every menu, as before menus
        let off = app.schema.camera.text.off_menu_name().to_string();
        let keys = |app: &App, m: Option<&str>| app.visible_in(0, m, Some(&off), "", false).into_iter().map(|s| s.key).collect::<Vec<_>>();
        assert!(!keys(&app, Some("Still")).is_empty());
        assert!(["Movie", "S&Q"].iter().all(|m| keys(&app, Some(m)) == keys(&app, Some("Still"))));
        assert_eq!(keys(&app, Some("Still")), keys(&app, None).into_iter().filter(|k| keys(&app, Some("Still")).contains(k)).collect::<Vec<_>>());
        // a group's settings placed nowhere, under "More settings in this group" in a menu that shows the group: one made
        // so here (a setting of a group of several placed ones), whatever the definition places
        let rows = app.settings_in_menu(0, "Still", Some("Shooting"));
        let loose = rows.iter().find(|s| s.placed() && s.under_option.is_none() && !s.on_page() && rows.iter().filter(|o| o.group == s.group && o.placed()).count() > 2).cloned().unwrap();
        for x in app.schema.settings.iter_mut().filter(|x| x.key == loose.key) {
            (x.row, x.row_at, x.row_menus) = (Vec::new(), Vec::new(), Vec::new());
        }
        app.schema_gen += 1;
        let more = app.tab_groups_in(0, Some("Still"), "Shooting", "", false).into_iter().find(|(_, f, rows)| !f && rows.iter().flatten().any(|s| s.key == loose.key));
        assert!(more.is_some_and(|(_, _, rows)| app.group_lines(&rows).contains(&Line::More)), "{} under More settings in this group", loose.name);
        // Expert mode: every record a row of its own, under its own name
        app.prefs.expert = true;
        let names: Vec<String> = app.settings_in_menu(0, "Movie", None).into_iter().filter(|s| s.row == ["ISO"] && s.under_option.is_none()).map(|s| s.name).collect();
        assert!(["ISO", "ISO (stills)", "ISO (movie)"].iter().all(|n| names.contains(&n.to_string())), "{names:?}");
        assert_eq!(row(&app, "Movie", "global:0x02f9").unwrap().name, "SteadyShot (Movie)");
        done(&dir, &user);
    }

    /// A setting a menu places otherwise (`row_places`): under that place's rows in that menu, as its own place says in
    /// the other; a jump from that menu lands on it there.
    #[test]
    fn a_place_of_its_own_in_one_menu() {
        let (mut app, dir, user) = sample_app("menus_place", Some(crate::test_support::stub_menus_and_a_place));
        let audio = setting(&app, "global:0x02e9");
        let lines = |app: &App, m: &str| {
            let groups = app.tab_groups_in(0, Some(m), "Shooting", "", false);
            let (_, _, rows) = groups.into_iter().find(|(_, _, rows)| rows.iter().flatten().any(|s| s.key == audio.key)).unwrap();
            app.group_lines(&rows).into_iter().map(|l| match l {
                Line::Heading { label, depth, .. } => format!("{label}/{depth}"),
                Line::Row { index, depth } => format!("{}#{depth}", rows[index][0].key),
                _ => String::new(),
            }).collect::<Vec<_>>()
        };
        let sq = lines(&app, "S&Q");
        let at = sq.iter().position(|l| l == "Audio Settings/0").expect("its place's row, a heading in S&Q's menu");
        assert_eq!(sq[at + 1], format!("{}#1", audio.key));
        assert!(lines(&app, "Movie").contains(&format!("{}#0", audio.key)), "its own place in Movie's");
        app.set_menu("S&Q");
        app.go_to(&audio);
        assert_eq!((app.menu_shown().as_deref(), app.item_key.as_deref()), (Some("S&Q"), Some(audio.key.as_str())));
        done(&dir, &user);
    }

    /// Review finding 8: what an edit writes together never depends on `row_menus` or `row_places`. A setting kept in
    /// two records of one name on one row (`twin_of`) whose records the menus name otherwise (one Still's, one Movie's)
    /// writes both, as without menus; and every setting the sample keeps in more than one record (twins, copies) writes
    /// the same records with the stub's menus as without. Inside one menu, rows laid out for two menus are two rows.
    #[test]
    fn what_an_edit_writes_together_does_not_depend_on_the_menus() {
        use crate::test_support::{strip_menus, stub_menus};
        let (mut plain, d1, u1) = sample_app("menus_twins_plain", Some(strip_menus));
        let (mut menus, d2, u2) = sample_app("menus_twins_menus", Some(stub_menus));
        let other = |app: &App, s: &Setting| app.offered_values(s, 0).into_iter().map(|(v, _)| v).find(|v| app.doc.as_ref().unwrap().value(0, s.slot()) != Some(*v));
        let written = |app: &mut App, s: &Setting, v: i64| -> Vec<(usize, u16)> {
            app.apply(vec![Action::Set(0, s.slot(), v)]);
            let out = app.doc.as_ref().unwrap().changes();
            app.undo();
            out
        };
        let editable = |app: &App, s: &Setting| s.area == "global" && s.scalar && !app.locked(s, 0) && app.shape_ok_in(s, 0);
        // two records of one setting that an edit of the first writes both of, without menus
        let pairs: Vec<(Setting, Setting, i64)> = plain.schema.settings.iter().filter(|s| editable(&plain, s))
            .filter_map(|s| Some((s.clone(), plain.schema.settings.iter().find(|o| s.twin_of(o) && o.id != s.id)?.clone(), other(&plain, s)?))).collect();
        let (a, b, v) = pairs.into_iter().find(|(a, b, v)| written(&mut plain, a, *v).contains(&(0, b.id))).expect("two records of one setting written together");
        for s in menus.schema.settings.iter_mut() {
            if s.key == a.key { s.row_menus = vec!["Still".into()]; }
            if s.key == b.key { s.row_menus = vec!["Movie".into()]; }
        }
        menus.schema_gen += 1;
        let both = written(&mut plain, &a, v);
        assert_eq!(written(&mut menus, &a, v), both, "{}: the same records with the menus naming them otherwise", a.name);
        // inside one menu, rows laid out for two menus are two rows; the definition's own records one row
        assert!(a.same_row(&b) && !a.place_in("Still").same_row(&b.place_in("Movie")) && a.place_in("Still").same_row(&b.place_in("Still")));
        // every setting kept in more than one record
        let several: Vec<Setting> = plain.schema.settings.iter().filter(|s| editable(&plain, s) && (s.copy_of.is_some() || !s.copies.is_empty() || plain.schema.settings.iter().any(|o| s.twin_of(o)))).cloned().collect();
        assert!(several.len() > 20, "{}", several.len());
        for s in several {
            let Some(v) = other(&plain, &s) else { continue };
            assert_eq!(written(&mut menus, &s, v), written(&mut plain, &s, v), "{}", s.name);
        }
        done(&d1, &u1);
        done(&d2, &u2);
    }

    /// Page file B9: one search path for the window and the page: the same hits in the same order, each titled as the
    /// window titles it (the definition's name) under the same Where words with the same separator, for three searches
    /// without menus and in each of the stub's menus. The window's side is what its search page draws.
    #[test]
    fn the_pages_search_is_the_windows() {
        for stub in [crate::test_support::strip_menus as fn(&mut serde_json::Value), crate::test_support::stub_menus] {
            let (mut app, dir, user) = sample_app("menus_search_one", Some(stub));
            let menus: Vec<Option<String>> = if app.menus().is_empty() { vec![None] } else { app.menus().iter().map(|m| Some(m.name.clone())).collect() };
            let mut w = Win::new();
            for menu in &menus {
                if let Some(m) = menu { app.set_menu(m); }
                for q in ["iso", "white balance", "focus area"] {
                    (app.search, app.view) = (q.to_string(), View::Search);
                    let drawn = w.drawn(&mut app);
                    let n: usize = drawn.iter().find_map(|t| t.strip_suffix(" setting(s). Click one to open it in its menu.").and_then(|n| n.parse().ok())).expect("the window's count");
                    let mut body = serde_json::json!({ "target": 0, "q": q });
                    if let Some(m) = menu { body["menu"] = serde_json::json!(m); }
                    let a = crate::web::tests::answer(&mut app, "tab", body);
                    let j: serde_json::Value = serde_json::from_slice(&a.body).unwrap();
                    let page: Vec<String> = j["groups"].as_array().unwrap().iter()
                        .flat_map(|g| g["rows"].as_array().unwrap().iter().flat_map(|r| [g["name"].as_str().unwrap().to_string(), r["name"].as_str().unwrap().to_string()]).collect::<Vec<_>>()).collect();
                    assert_eq!(page.len(), 2 * n, "{menu:?} {q}: as many hits as the window's");
                    let mut at = drawn.iter();
                    for want in &page {
                        assert!(at.any(|t| t == want), "{menu:?} {q}: {want} where the window draws it, in its order");
                    }
                }
            }
            done(&dir, &user);
        }
    }

    /// Integration review finding 4: in a camera menu the page's compare CSV, its column picker and its Editing row are
    /// the window's for that menu: the CSV the window exports for the menu and entry (`csv_text_in`), the picker the
    /// window's (`picker_sets` with the columns shown), and, editing a Movie memory with Still's menu picked, the
    /// Editing row the window draws (`editing_sets`), which keeps that memory.
    #[test]
    fn the_pages_csv_picker_and_editing_row_follow_its_menu() {
        let (mut app, dir, user) = sample_app("menus_page_parity", Some(crate::test_support::stub_menus));
        let movie_set = app.menu_sets(Some("Movie")).into_iter().find(|&s| s != 0).unwrap();
        let still_set = app.menu_sets(Some("Still")).into_iter().find(|&s| s != 0).unwrap();
        let cols = [Col::a(0), Col::a(still_set)];
        for menu in ["Still", "Movie"] {
            let body = serde_json::json!({ "compare": true, "cols": [["a", 0], ["a", still_set]], "only_diff": false, "menu": menu, "entry": "tab:Shooting" });
            let r = crate::web::tests::answer(&mut app, "csv", body);
            let want = app.csv_text_in(Some(menu), Some((&cols, false, app.show_raw)), 0, "", &BarKey::Tab("Shooting".into()), false).0;
            assert_eq!(String::from_utf8(r.body).unwrap(), want, "{menu}: the CSV the window exports");
            let a = crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["a", still_set]], "menu": menu, "only_diff": false }));
            let j: serde_json::Value = serde_json::from_slice(&a.body).unwrap();
            let page: Vec<u64> = j["sections"].as_array().unwrap().iter().map(|s| s[0].as_u64().unwrap()).collect();
            assert_eq!(page, app.picker_sets(Some(menu), &cols).into_iter().map(|s| s as u64).collect::<Vec<_>>(), "{menu}: the window's column picker");
        }
        assert_ne!(app.picker_sets(Some("Still"), &cols), app.picker_sets(Some("Movie"), &cols), "the case: the menus' pickers differ");
        // the Editing row: a Movie memory edited, Still's menu picked
        app.target = movie_set;
        app.set_menu("Still");
        let window = app.editing_sets();
        assert!(window.contains(&movie_set));
        let s = crate::web::tests::answer(&mut app, "state", serde_json::json!({ "target": movie_set, "menu": "Still" }));
        let s: serde_json::Value = serde_json::from_slice(&s.body).unwrap();
        let page: Vec<usize> = s["targets"].as_array().unwrap().iter().map(|t| t[0].as_u64().unwrap() as usize).collect();
        assert_eq!(page, window, "the Editing row the window draws");
        done(&dir, &user);
    }

    /// Integration review finding 5: Up/Down in the Menu column move from the first entry where the page shown is not
    /// one of the bar's (Only edited with no edit there): Down opens the bar's first entry.
    #[test]
    fn the_menus_keys_start_from_the_first_entry_where_the_page_is_not_listed() {
        for stub in [crate::test_support::strip_menus as fn(&mut serde_json::Value), crate::test_support::stub_menus] {
            let (mut app, dir, user) = sample_app("menus_keys_unlisted", Some(stub));
            let iso = setting(&app, "global:0x0334");
            let v = app.offered_values(&iso, 0).into_iter().map(|(v, _)| v).find(|v| app.doc.as_ref().unwrap().value(0, iso.slot()) != Some(*v)).unwrap();
            app.apply(vec![Action::Set(0, iso.slot(), v)]);
            app.only_changed = true;
            let keys = app.bar_keys(false, 0, app.menu_shown().as_deref(), "", true);
            let unlisted = app.menu_tabs().into_iter().find(|t| !keys.contains(&BarKey::Tab(t.clone()))).expect("a tab with no edit");
            (app.view, app.focus) = (View::Tab(unlisted), Focus::Tabs);
            let down = egui::RawInput { events: vec![egui::Event::Key { key: egui::Key::ArrowDown, physical_key: None, pressed: true, repeat: false, modifiers: Default::default() }], ..Default::default() };
            let _ = egui::Context::default().run(down, |ctx| app.bar_nav(ctx));
            let want = match &keys[0] { BarKey::Main => View::Main, BarKey::MyMenu => View::MyMenu, BarKey::Tab(t) => View::Tab(t.clone()), BarKey::All => unreachable!() };
            assert_eq!(app.view, want);
            done(&dir, &user);
        }
    }

    /// Second integration review, item 5: in Expert mode a search hit for a place of My Menu says where a click on it
    /// opens (My Menu's page, `entry_here`), with menus and without, as the jump lands.
    #[test]
    fn a_places_search_hit_says_my_menus_page() {
        use crate::test_support::{strip_menus, stub_menus};
        for stub in [strip_menus as fn(&mut serde_json::Value), stub_menus] {
            let (mut app, dir, user) = sample_app("menus_place_where", Some(stub));
            app.prefs.expert = true;
            let place = app.schema.settings.iter().find(|s| app.is_mymenu_place(s)).cloned().unwrap();
            let said = app.where_shown(&place);
            let my = app.schema.camera.text.my_menu_name().to_string();
            let menu = app.menu_shown().map(|m| format!("{m} > ")).unwrap_or_default();
            assert!(said.starts_with(&format!("{menu}{my} > ")), "{said}");
            app.go_to(&place);
            assert_eq!(app.view, View::MyMenu, "the click opens My Menu's page");
            done(&dir, &user);
        }
    }

    /// Integration review finding 3: the rows as before menus (Compare's rows without a menu, the Memories page,
    /// recall, the page's copy lookup) come in one order, whatever menu the window shows and whatever was asked before.
    #[test]
    fn the_rows_as_before_menus_keep_one_order() {
        let keys = |app: &App| app.matrix_rows_for("", None).iter().map(|r| r.2[0].key.clone()).collect::<Vec<_>>();
        let (mut app, dir, user) = sample_app("menus_rows_order", Some(crate::test_support::stub_menus));
        app.set_menu("Still");
        let first = keys(&app);
        app.set_menu("Movie");
        assert_eq!(keys(&app), first, "asked again with Movie's menu shown");
        app.rows_cache.borrow_mut().clear();
        assert_eq!(keys(&app), first, "worked out afresh with Movie's menu shown");
        assert_eq!(app.matrix_rows_for("", None).iter().map(|r| r.2[0].key.clone()).collect::<Vec<_>>(), first);
        done(&dir, &user);
    }

    /// Review finding 6: a row alone on its place keeps its full name where another row under the same heading would
    /// be titled alike (the a1 II's Recording Media and Recording Media (Movie), each alone on its place under Rec.
    /// Media Settings, both in Movie's menu); and a label the definition tells apart from another of the same words by
    /// `#n` (docs/DATA_CONTRACTS.md) is drawn without it, in a row's title and in a heading, and told apart with it.
    #[test]
    fn rows_titled_alike_under_one_heading_keep_their_names() {
        let (mut app, dir, user) = sample_app("menus_titles_clash", Some(crate::test_support::stub_menus));
        let (media, movie, adjust) = (setting(&app, "global:0x0298"), setting(&app, "global:0x029a"), setting(&app, "global:0x02fb"));
        let title = |app: &App, s: &Setting, menu: &str| app.listed_record(s, 0, menu).name;
        assert_eq!((title(&app, &media, "Movie"), title(&app, &movie, "Movie")), (media.name.clone(), movie.name.clone()), "in Movie's menu, each its full name");
        assert_eq!(title(&app, &adjust, "Still"), "SteadyShot Adjust.", "a row alone, as the camera draws it");
        // in no menu two rows under one heading titled alike where one is retitled
        for m in ["Still", "Movie", "S&Q"] {
            let rows: Vec<Setting> = app.settings_in_menu(0, m, None).into_iter().filter(|s| s.placed() && s.under_option.is_none()).collect();
            for s in rows.iter().filter(|s| s.name != app.full_name(s)) {
                let head = |x: &Setting| (x.tab.clone(), x.group.clone(), x.row[..x.row.len() - 1].to_vec(), x.row_at[..x.row.len() - 1].to_vec());
                assert!(!rows.iter().any(|x| x.key != s.key && x.name == s.name && head(x) == head(s)), "{m}: {} twice under one heading", s.name);
            }
        }
        // labels told apart by `#n`
        for s in app.schema.settings.iter_mut() {
            match s.key.as_str() {
                "global:0x0298" => s.row = vec!["Rec. Media Settings#1".into(), "Recording Media".into()],
                "global:0x029a" => s.row = vec!["Rec. Media Settings#1".into(), "Recording Media#1".into()],
                "global:0x02fb" => s.row = vec!["SteadyShot Adjust.#1".into()],
                _ => {}
            }
        }
        app.schema_gen += 1;
        assert_eq!((title(&app, &media, "Movie"), title(&app, &movie, "Movie")), (media.name.clone(), movie.name.clone()), "drawn alike: each its full name");
        assert_eq!(title(&app, &media, "Still"), "Recording Media", "alone under its heading in Still's menu");
        assert_eq!(title(&app, &adjust, "Still"), "SteadyShot Adjust.", "drawn without its #1");
        let groups = app.tab_groups_in(0, Some("Still"), &media.tab, "", false);
        let (_, _, rows) = groups.iter().find(|(g, _, _)| *g == media.group).unwrap();
        let lines = menu_rows::lay_out(rows);
        assert!(lines.iter().any(|l| matches!(l, Line::Heading { label, path, .. } if label == "Rec. Media Settings" && path == &["Rec. Media Settings#1".to_string()])), "{lines:?}");
        assert_eq!(menu_rows::place_words(&media).map(|_| ()), Some(()));
        let placed = app.schema.settings.iter().find(|s| s.key == movie.key).cloned().unwrap();
        assert_eq!(menu_rows::place_words(&placed).as_deref(), Some("On the camera: Rec. Media Settings > Recording Media"));
        done(&dir, &user);
    }

    /// Where the selection is, in the words of a search hit's "Where": the menu, the entry and the group.
    fn where_now(app: &App) -> String {
        let View::Tab(tab) = &app.view else { panic!("{:?}", app.view) };
        format!("{} > {tab} > {}", app.menu_shown().unwrap(), app.group.clone().unwrap())
    }

    /// Review finding 5: a jump to a record opens the menu whose row shows that record (the one shown first, then the
    /// file's mode's, then the first); where no row shows it (the copy for the file's own mode), the menu of that copy's
    /// mode, on the row that shows its setting itself; a jump to the setting itself, the menu of the file's mode. A
    /// search hit's "Where" names the place a click on it opens. A setting the camera keeps once stays in the menu shown.
    #[test]
    fn a_jump_to_a_record_opens_the_menu_whose_row_shows_it() {
        let (mut app, dir, user) = sample_app("menus_jump_record", Some(crate::test_support::stub_menus));
        let (iso, stills, movie) = (setting(&app, "global:0x0334"), setting(&app, "global:0x0df2"), setting(&app, "global:0x0df4"));
        // a setting the camera keeps once, a row of every menu, its search hit itself
        let steady = app.schema.settings.iter().find(|s| s.copies.is_empty() && s.copy_of.is_none() && s.area == "global" && menu_rows::is_own(s) && !App::expert_only(s)
            && app.menus_of(s).len() == 3 && app.search_hits_in(0, None, &s.name).iter().any(|(h, _)| h.key == s.key)).cloned().unwrap();
        assert_eq!(app.opening_menu(0).as_deref(), Some("Still"), "a file saved in Stills");
        for (from, s, menu, row) in [
            ("Movie", &stills, "Still", &iso), ("S&Q", &stills, "Still", &iso),
            ("Movie", &iso, "Still", &iso), ("S&Q", &iso, "Still", &iso),
            ("Still", &movie, "Movie", &movie), ("S&Q", &movie, "S&Q", &movie),
            ("Movie", &steady, "Movie", &steady), ("S&Q", &steady, "S&Q", &steady),
        ] {
            app.set_menu(from);
            let said = app.where_shown(s);
            app.go_to(s);
            assert_eq!((app.menu_shown().as_deref(), app.item_key.as_deref()), (Some(menu), Some(row.key.as_str())), "{} from {from}", s.name);
            assert_eq!(said, where_now(&app), "{} from {from}: the hit's Where", s.name);
            // the search hit, with its Where, opens the same place
            let (hit, at) = app.search_hits_in(0, Some(from), &s.name).into_iter().find(|(h, _)| h.key == s.key).unwrap();
            assert_eq!((at.as_deref(), app.where_in(&hit, 0, Some(from))), (Some(menu), said.clone()), "{} from {from}", s.name);
        }
        done(&dir, &user);
    }

    /// Review finding 4: Compare's Open in Edit stays in the menu Compare showed where that menu lists the setting's
    /// row, on its row there, whatever record Compare's row showed: a file saved in Movie, Compare in Movie's menu on
    /// the ISO row (the movie copy, as Compare shows each menu's mode), opens Edit in Movie's menu on its ISO row.
    #[test]
    fn open_in_edit_stays_in_the_menu_compare_showed() {
        let (mut app, dir, user) = sample_app("menus_open_in_edit", Some(crate::test_support::stub_menus));
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let rec = setting(&app, &lm.key);
        let mut c = crate::camera::job::test_parse(crate::test_support::SAMPLE_BYTES).unwrap();
        c.sections[0].get_mut(rec.id).unwrap().put(rec.index, 1).unwrap();
        let f = dir.join("CAMSET05.DAT");
        std::fs::write(&f, c.to_bytes()).unwrap();
        app.open(f);
        assert_eq!(app.opening_menu(0).as_deref(), Some("Movie"), "a file saved in Movie");
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::a(1)], false);
        app.set_menu("Movie");
        let iso = setting(&app, "global:0x0334");
        let bound = app.row_record(&iso, "Movie", &Bind::Menu).key.clone();
        assert_eq!(bound, "global:0x0df4", "Compare's row shows Movie's copy");
        let row = app.compare_rows(Some("Movie"), &BarKey::All, "").iter().find(|r| r.2[0].key == bound).cloned().unwrap();
        // the page's link on that row says the same place
        let a = crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["a", 1]], "menu": "Movie", "only_diff": false }));
        let j: serde_json::Value = serde_json::from_slice(&a.body).unwrap();
        let link = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == bound.as_str()).cloned().unwrap();
        app.open_in_edit_from_compare(&row.2[0], 0);
        app.follow_selection();
        assert!(app.mode == Mode::Edit);
        assert_eq!(app.menu_shown().as_deref(), Some("Movie"));
        assert_eq!(app.item_key, Some(app.listed_record(&iso, 0, "Movie").key), "its row in Movie's menu");
        let View::Tab(tab) = app.view.clone() else { panic!() };
        assert_eq!((link["open_menu"].as_str(), link["open_key"].as_str(), link["open_tab"].as_str(), link["open_group"].as_str()), (Some("Movie"), app.item_key.as_deref(), Some(tab.as_str()), app.group.as_deref()), "the page: {link}");
        done(&dir, &user);
    }

    /// Review finding 3: in a camera menu, outside Expert mode, a row's note says in the menu's terms which other
    /// camera menus' value an edit of it changes (exactly those `apply` then changes), why, and how to change this
    /// menu's alone (the switch the definition names in `keeps_apart`, where it names one, and Expert mode); it names
    /// no record the menus do not show, and the page sends the window's words.
    #[test]
    fn a_rows_note_in_a_menu_says_which_other_menus_change_with_it() {
        let (mut app, dir, user) = sample_app("menus_copies_note", Some(crate::test_support::stub_menus));
        let menus = ["Still", "Movie", "S&Q"];
        for (key, switch) in [("global:0x0334", None), ("global:0x0367", Some(("global:0x0187", "Ticked")))] {
            let main = setting(&app, key);
            for menu in menus {
                let row = app.listed_record(&main, 0, menu);
                let (note, _) = app.copy_note(&row, 0).unwrap_or_else(|| panic!("{} in {menu}", main.name));
                // what an edit changes: the other menus whose row shows another value after it
                let shown = |app: &App| menus.map(|m| app.doc.as_ref().unwrap().value(0, app.listed_record(&main, 0, m).slot()));
                let keep = app.doc.as_ref().map(|d| d.edited.clone());
                let before = shown(&app);
                let v = app.offered_values(&row, 0).into_iter().map(|(v, _)| v).find(|v| Some(*v) != before[0]).unwrap();
                app.apply(vec![Action::Set(0, row.slot(), v)]);
                let after = shown(&app);
                if let (Some(d), Some(edited)) = (app.doc.as_mut(), keep) {
                    d.edited = edited;
                }
                let changed: Vec<String> = menus.iter().zip(before.iter().zip(&after)).filter(|(m, (b, a))| **m != menu && b != a).map(|(m, _)| m.to_string()).collect();
                assert_eq!(changed.len(), 2, "{} in {menu}: the sample holds each menu's record at one value", main.name);
                assert!(note.starts_with(&format!("Changing this changes it in the {} menus too", and_list(&changed))), "{} in {menu}: {note}", main.name);
                assert!(note.contains("held the same value when this file was opened or read") && note.contains("shares between shooting modes"), "{note}");
                assert!(note.contains(&format!("To change it in the {menu} menu alone")) && note.contains("Expert mode"), "{note}");
                if let Some((sw, label)) = switch {
                    assert!(note.contains(&format!("{} set to {label}", setting(&app, sw).name)), "the switch: {note}");
                }
                for c in &main.copies {
                    assert!(!note.contains(&setting(&app, c).name), "no record the menus do not show: {note}");
                }
                // the page: the same words for the same row
                let linked = app.web_linked_in(0, Some(menu), &main.key).unwrap();
                assert_eq!(app.web_row_in(0, Some(menu), &linked)["copy_note"].as_str(), Some(note.as_str()), "{} in {menu}", main.name);
            }
        }
        done(&dir, &user);
    }

    /// The window run frame by frame as a screen reader is told it, and clicked as one clicks.
    struct Win {
        ctx: egui::Context,
        frame: eframe::Frame,
    }

    impl Win {
        fn new() -> Self {
            let ctx = egui::Context::default();
            ctx.enable_accesskit();
            Win { ctx, frame: eframe::Frame::_new_kittest() }
        }

        /// One frame with `events`: each control and label a screen reader is told of (node, role, words).
        fn run(&mut self, app: &mut App, events: Vec<egui::Event>) -> Vec<(egui::accesskit::NodeId, egui::accesskit::Role, String)> {
            let frame = &mut self.frame;
            let out = self.ctx.run(egui::RawInput { events, ..Default::default() }, |ctx| eframe::App::update(app, ctx, frame));
            out.platform_output.accesskit_update.map(|t| t.nodes.iter().filter_map(|(id, n)| n.label().or(n.value()).map(|l| (*id, n.role(), l.to_string()))).collect()).unwrap_or_default()
        }

        /// The window settled (two frames), then a click on the one control of `role` whose words are `name`, then
        /// settled again.
        fn click(&mut self, app: &mut App, role: egui::accesskit::Role, name: &str) {
            self.click_where(app, &[role], |l| l == name, name);
        }

        /// `click` on the one control of one of `roles` whose words `fits` (`what` names it in a failure).
        fn click_where(&mut self, app: &mut App, roles: &[egui::accesskit::Role], fits: impl Fn(&str) -> bool, what: &str) {
            let _ = self.run(app, vec![]);
            let said = self.run(app, vec![]);
            let hit: Vec<egui::accesskit::NodeId> = said.iter().filter(|(_, r, l)| roles.contains(r) && fits(l)).map(|(id, ..)| *id).collect();
            assert_eq!(hit.len(), 1, "{what}: {said:?}");
            let click = egui::accesskit::ActionRequest { action: egui::accesskit::Action::Click, target: hit[0], data: None };
            let _ = self.run(app, vec![egui::Event::AccessKitActionRequest(click)]);
            // a header opening takes a few frames to show what it holds
            for _ in 0..6 {
                let _ = self.run(app, vec![]);
            }
        }

        /// The texts the window draws, settled (two frames), in the order it draws them.
        fn drawn(&mut self, app: &mut App) -> Vec<String> {
            let _ = self.run(app, vec![]);
            let frame = &mut self.frame;
            let out = self.ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, frame));
            crate::test_support::texts(&out.shapes)
        }

        /// A key pressed with `modifiers`, then the window settled.
        fn key_with(&mut self, app: &mut App, key: egui::Key, modifiers: egui::Modifiers) {
            let _ = self.run(app, vec![egui::Event::Key { key, physical_key: None, pressed: true, repeat: false, modifiers }]);
            let _ = self.run(app, vec![]);
            let _ = self.run(app, vec![]);
        }

        /// An arrow key pressed, then the window settled.
        fn key(&mut self, app: &mut App, key: egui::Key) {
            let _ = self.run(app, vec![egui::Event::Key { key, physical_key: None, pressed: true, repeat: false, modifiers: egui::Modifiers::NONE }]);
            let _ = self.run(app, vec![]);
            let _ = self.run(app, vec![]);
        }
    }

    /// Item 4: Collapse all and Expand all by Cmd/Ctrl+Shift+↑ / ↓, in Edit (the camera's rows that hold others in the
    /// group shown: Shooting > Drive Mode) and in Compare (its tabs and groups), leave what the buttons leave; the row
    /// chosen under a heading gives way to a row still shown; a text field with the keyboard keeps the keys.
    #[test]
    fn collapse_and_expand_all_by_the_keys_and_the_buttons() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("fold_keys", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        let (tab, group) = ("Shooting", "Drive Mode");
        let groups = app.tab_groups(tab);
        let (_, _, rows) = groups.iter().find(|(g, _, _)| g == group).cloned().unwrap();
        let lines = app.group_lines(&rows);
        let heads: Vec<String> = lines.iter().filter_map(|l| match l { Line::Heading { path, .. } => Some(App::fold_key(tab, group, path)), _ => None }).collect();
        assert!(!heads.is_empty(), "the group has rows that hold others");
        // a row under one of them (a heading above it)
        let under = lines.iter().enumerate().find_map(|(at, l)| match l { Line::Row { index, .. } if !menu_rows::headings_above(&lines, at).is_empty() => Some(rows[*index][0].clone()), _ => None }).unwrap();
        app.select(Some(View::Tab(tab.into())), Some(group.into()), Some((&under.name, &under.key)));
        let _ = w.run(&mut app, vec![]);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        let by_keys = app.folded.clone();
        assert!(heads.iter().all(|k| by_keys.contains(k)), "Edit: every row that holds others folded");
        assert_ne!(app.item_key.as_deref(), Some(under.key.as_str()), "the row chosen gave way to one still shown");
        assert_eq!(app.group.as_deref(), Some(group), "the group stays");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert!(heads.iter().all(|k| !app.folded.contains(k)), "Edit: every one shown");
        w.click(&mut app, Role::Button, "Collapse all");
        assert_eq!(app.folded, by_keys, "the button leaves what the keys leave");
        w.click(&mut app, Role::Button, "Expand all");
        assert!(heads.iter().all(|k| !app.folded.contains(k)));
        // a text field with the keyboard keeps the keys for its text
        w.ctx.memory_mut(|m| m.request_focus(egui::Id::new(SEARCH_ID)));
        let _ = w.run(&mut app, vec![]);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(heads.iter().all(|k| !app.folded.contains(k)), "the search box had the keyboard");
        w.ctx.memory_mut(|m| m.surrender_focus(egui::Id::new(SEARCH_ID)));
        // Compare: its tabs, by the keys as by the button
        let b = app.doc.as_ref().unwrap().original.clone();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::b(0)], false);
        let _ = w.run(&mut app, vec![]);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        let closed = app.matrix_closed.clone();
        assert!(!closed.is_empty(), "Compare: every tab folded");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert!(app.matrix_closed.is_empty());
        w.click(&mut app, Role::Button, "Collapse all");
        assert_eq!(app.matrix_closed, closed, "the button leaves what the keys leave");
        done(&dir, &user);
    }

    /// The Memories page's groups fold (all open to start with): every one by the keys as by its Collapse all and Expand
    /// all, one by a click on its heading or by Space or Enter with the focus on it.
    #[test]
    fn the_memories_groups_fold_by_the_keys_the_buttons_and_one_heading() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("fold_memories", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        app.view = View::Memories;
        let groups: std::collections::HashSet<String> = app.matrix_rows_shared("", None).iter().filter(|r| r.2[0].in_sets).map(|(t, g, _)| format!("{t} > {g}")).collect();
        let _ = w.run(&mut app, vec![]);
        assert!(app.mem_closed.is_empty() && groups.len() > 1, "all open to start with");
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert_eq!(app.mem_closed, groups, "Collapse all by the keys");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert!(app.mem_closed.is_empty(), "Expand all by the keys");
        w.click(&mut app, Role::Button, "Collapse all");
        assert_eq!(app.mem_closed, groups, "the button leaves what the keys leave");
        w.click(&mut app, Role::Button, "Expand all");
        assert!(app.mem_closed.is_empty());
        // one heading, the first drawn: by a click, then by Space with the focus on it
        let _ = w.run(&mut app, vec![]);
        let said = w.run(&mut app, vec![]);
        let (id, _, label) = said.iter().find(|(_, r, l)| *r == Role::Label && l.starts_with("⏷ ")).cloned().expect("a heading drawn");
        let first = label.trim_start_matches("⏷ ").to_string();
        let click = egui::accesskit::ActionRequest { action: egui::accesskit::Action::Click, target: id, data: None };
        let _ = w.run(&mut app, vec![egui::Event::AccessKitActionRequest(click)]);
        let _ = w.run(&mut app, vec![]);
        assert!(app.mem_closed.contains(&first) && app.mem_closed.len() == 1, "a click folds that group alone");
        let _ = w.run(&mut app, vec![]);
        let said = w.run(&mut app, vec![]);
        let (id, ..) = *said.iter().find(|(_, r, l)| *r == Role::Label && *l == format!("⏵ {first}")).expect("the heading, folded");
        let focus = egui::accesskit::ActionRequest { action: egui::accesskit::Action::Focus, target: id, data: None };
        let _ = w.run(&mut app, vec![egui::Event::AccessKitActionRequest(focus)]);
        w.key(&mut app, egui::Key::Space);
        assert!(app.mem_closed.is_empty(), "Space with the focus on it shows it again");
        done(&dir, &user);
    }

    /// The reviewer's mend 3: on the Memories page a new search opens the groups of its hits, as a jump to a row under a
    /// folded heading does in Edit, and a group folded during that search stays folded; a row control with egui's focus
    /// whose group folds gives the focus to that group's heading, never left on a control no longer drawn.
    #[test]
    fn memories_a_search_opens_its_groups_and_a_fold_gives_the_focus_to_the_heading() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("mem_search_focus", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        (app.view, app.prefs.memories_only_diff) = (View::Memories, false);
        // a setting of the memories made to differ between Memory 1 and Live, so its row has arrows
        let (tab, grp, s) = app.matrix_rows_shared("", None).iter().map(|r| (r.0.clone(), r.1.clone(), r.2[0].clone()))
            .find(|(_, _, s)| s.in_sets && s.area == "global" && s.scalar && s.text.is_none() && s.values.len() >= 2 && s.copies.is_empty() && s.copy_of.is_none() && !app.locked(s, 0) && !app.locked(s, 1)).unwrap();
        let cur = app.doc.as_ref().unwrap().value(1, s.slot()).unwrap();
        let v = s.values.iter().map(|(v, _)| *v).find(|v| *v != cur).unwrap();
        assert!(app.apply(vec![Action::Set(1, s.slot(), v)]).is_none());
        let g = format!("{tab} > {grp}");
        let settle = |w: &mut Win, app: &mut App| for _ in 0..3 { let _ = w.run(app, vec![]); };
        settle(&mut w, &mut app);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(app.mem_closed.contains(&g), "every group folded");
        app.search = s.name.clone();
        settle(&mut w, &mut app);
        assert!(!app.mem_closed.contains(&g), "the search opened its hit's group");
        app.mem_closed.insert(g.clone());
        settle(&mut w, &mut app);
        assert!(app.mem_closed.contains(&g), "folded during the same search, it stays folded");
        // the row's arrow focused, then every group folded by the keys: the heading has the focus
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        let back = App::arrow_words(&app.col_name(Col::a(1)), &app.col_name(Col::a(0)));
        let _ = w.run(&mut app, vec![]);
        let said = w.run(&mut app, vec![]);
        let (arrow, ..) = *said.iter().find(|(_, r, l)| *r == Role::Button && *l == back).expect("the row's arrow");
        let focus = egui::accesskit::ActionRequest { action: egui::accesskit::Action::Focus, target: arrow, data: None };
        let _ = w.run(&mut app, vec![egui::Event::AccessKitActionRequest(focus)]);
        assert!(w.ctx.memory(|m| m.focused()).is_some_and(|f| f.value() == arrow.0), "the arrow has the focus");
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        settle(&mut w, &mut app);
        let said = w.run(&mut app, vec![]);
        let (head, ..) = *said.iter().find(|(_, r, l)| *r == Role::Label && *l == format!("⏵ {g}")).expect("the folded heading");
        assert!(w.ctx.memory(|m| m.focused()).is_some_and(|f| f.value() == head.0), "the heading has the focus");
        done(&dir, &user);
    }

    /// The reviewer's mend 2: once a control holds egui's focus (as Tab or a screen reader leaves it), the arrows still move
    /// the menu's choice, in the items column and the groups column, and the control keeps the focus; Tab still moves
    /// through the controls; a text field with the caret keeps the arrows for its text.
    #[test]
    fn the_arrows_move_the_choice_with_a_control_focused() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("arrows_focus", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let (tab, group) = ("Shooting", "Drive Mode");
        let rows = app.tab_groups(tab).into_iter().find(|(g, _, _)| g == group).unwrap().2;
        let first = app.group_lines(&rows).iter().find_map(|l| match l { Line::Row { index, .. } => Some(rows[*index][0].clone()), _ => None }).unwrap();
        app.select(Some(View::Tab(tab.into())), Some(group.into()), Some((&first.name, &first.key)));
        app.focus = Focus::Items;
        let _ = w.run(&mut app, vec![]);
        let said = w.run(&mut app, vec![]);
        let (button, ..) = *said.iter().find(|(_, r, l)| *r == Role::Button && l == "Expand all").expect("a button");
        let focus = egui::accesskit::ActionRequest { action: egui::accesskit::Action::Focus, target: button, data: None };
        let _ = w.run(&mut app, vec![egui::Event::AccessKitActionRequest(focus)]);
        let focused = |w: &Win| w.ctx.memory(|m| m.focused()).map(|f| f.value());
        assert_eq!(focused(&w), Some(button.0), "the button has the focus");
        w.key(&mut app, egui::Key::ArrowDown);
        assert!(app.item_key.as_deref() != Some(first.key.as_str()) || app.item_head.is_some(), "Down moved the choice in the items column");
        assert_eq!(focused(&w), Some(button.0), "and the button kept the focus");
        app.focus = Focus::Groups;
        w.key(&mut app, egui::Key::ArrowDown);
        assert_ne!(app.group.as_deref(), Some(group), "Down moved to the next group");
        assert_eq!(focused(&w), Some(button.0), "the button kept the focus");
        // Tab moves through the controls from the one focused
        w.key(&mut app, egui::Key::Tab);
        assert!(focused(&w).is_some_and(|f| f != button.0), "Tab moved the focus to another control");
        // a text field with the caret keeps the arrows
        let now = app.group.clone();
        w.ctx.memory_mut(|m| m.request_focus(egui::Id::new(SEARCH_ID)));
        let _ = w.run(&mut app, vec![]);
        w.key(&mut app, egui::Key::ArrowDown);
        assert_eq!(app.group, now, "the search box with the caret kept the arrow");
        done(&dir, &user);
    }

    /// The reviewer's mend 1: a Collapse all the view in front does not take acts on no later view. On a family group,
    /// Cmd/Ctrl+Shift+↑ and a plain ↓ in the same frame: the ↓ moves to the next group, the request is dropped after that
    /// frame's panel, and the family's table, back in front, is open as it was.
    #[test]
    fn a_fold_request_not_taken_acts_on_no_later_view() {
        let (mut app, dir, user) = sample_app("fold_stale", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let (tab, group) = app.schema.tabs.iter().find_map(|t| app.tab_groups(t).into_iter().find(|(_, family, _)| *family).map(|(g, _, _)| (t.clone(), g))).expect("a family group");
        app.select(Some(View::Tab(tab.clone())), Some(group.clone()), None);
        app.focus = Focus::Groups;
        let open = |w: &mut Win, app: &mut App| {
            for _ in 0..8 {
                let _ = w.run(app, vec![]);
            }
            w.drawn(app).iter().any(|t| t.contains("Values the camera never produces are not offered."))
        };
        assert!(open(&mut w, &mut app));
        let key = |key, modifiers| egui::Event::Key { key, physical_key: None, pressed: true, repeat: false, modifiers };
        let _ = w.run(&mut app, vec![key(egui::Key::ArrowUp, egui::Modifiers::COMMAND | egui::Modifiers::SHIFT), key(egui::Key::ArrowDown, egui::Modifiers::NONE)]);
        assert_ne!(app.group.as_deref(), Some(group.as_str()), "the plain Down moved to the next group");
        assert!(app.head_fold.is_none(), "the request the view in front did not take is gone after the panel");
        let _ = w.run(&mut app, vec![]);
        app.select(Some(View::Tab(tab)), Some(group), None);
        assert!(open(&mut w, &mut app), "the family's table, back in front, is open as it was");
        done(&dir, &user);
    }

    /// The reviewer's inventory, B: the record map (Expert mode) folds and shows its records' bytes by the keys as by its
    /// own Collapse all and Expand all: Expand all the multi-byte records listed, Collapse all every one.
    #[test]
    fn the_record_maps_bytes_fold_by_the_keys_and_the_buttons() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("fold_records", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        (app.prefs.expert, app.view) = (true, View::Records);
        let open = |w: &mut Win, app: &mut App| {
            let _ = w.run(app, vec![]);
            let _ = w.run(app, vec![]);
            w.ctx.data(|d| d.get_temp::<std::collections::HashSet<u16>>(egui::Id::new("rm_expanded"))).unwrap_or_default()
        };
        let big: std::collections::HashSet<u16> = app.record_rows().iter().filter(|r| r.big).map(|r| r.id).collect();
        assert!(!big.is_empty() && open(&mut w, &mut app).is_empty(), "every record folded to start with");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        let shown = open(&mut w, &mut app);
        assert_eq!(shown, big, "Expand all: every multi-byte record listed");
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(open(&mut w, &mut app).is_empty(), "Collapse all");
        w.click(&mut app, Role::Button, "Expand all");
        assert_eq!(open(&mut w, &mut app), shown, "the button leaves what the keys leave");
        w.click(&mut app, Role::Button, "Collapse all");
        assert!(open(&mut w, &mut app).is_empty());
        done(&dir, &user);
    }

    /// The reviewer's inventory, A: a family group's table (Picture Profiles, Creative Looks) folds and opens by the keys
    /// as by its own Collapse all and Expand all, as on the page.
    #[test]
    fn a_family_groups_table_folds_by_the_keys_and_the_buttons() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("fold_family", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        let (tab, group) = app.schema.tabs.iter().find_map(|t| app.tab_groups(t).into_iter().find(|(_, family, _)| *family).map(|(g, _, _)| (t.clone(), g))).expect("a family group");
        app.select(Some(View::Tab(tab)), Some(group), None);
        let open = |w: &mut Win, app: &mut App| {
            for _ in 0..8 {
                let _ = w.run(app, vec![]);
            }
            w.drawn(app).iter().any(|t| t.contains("Values the camera never produces are not offered."))
        };
        assert!(open(&mut w, &mut app), "open to start with");
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(!open(&mut w, &mut app), "Collapse all by the keys");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert!(open(&mut w, &mut app), "Expand all by the keys");
        w.click(&mut app, Role::Button, "Collapse all");
        assert!(!open(&mut w, &mut app), "the button leaves what the keys leave");
        w.click(&mut app, Role::Button, "Expand all");
        assert!(open(&mut w, &mut app));
        done(&dir, &user);
    }

    /// The owner's report ("in the edit, when in the pane 3 of 4 I'm not able to collapse or expand"): the keys fold
    /// and open from every pane of Edit (the Menu, the groups, the settings, a control with egui's focus) and of Compare,
    /// and only a text field with the caret in it keeps them.
    #[test]
    fn the_fold_keys_work_from_every_pane() {
        let (mut app, dir, user) = sample_app("fold_panes", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        let (tab, group) = ("Shooting", "Drive Mode");
        let rows = app.tab_groups(tab).into_iter().find(|(g, _, _)| g == group).unwrap().2;
        let heads: Vec<String> = app.group_lines(&rows).iter().filter_map(|l| match l { Line::Heading { path, .. } => Some(App::fold_key(tab, group, path)), _ => None }).collect();
        app.select(Some(View::Tab(tab.into())), Some(group.into()), None);
        let _ = w.run(&mut app, vec![]);
        for pane in [Focus::Tabs, Focus::Groups, Focus::Items] {
            app.focus = pane;
            w.key_with(&mut app, egui::Key::ArrowUp, cs);
            assert!(heads.iter().all(|k| app.folded.contains(k)), "Edit, {pane:?}: Collapse all");
            w.key_with(&mut app, egui::Key::ArrowDown, cs);
            assert!(heads.iter().all(|k| !app.folded.contains(k)), "Edit, {pane:?}: Expand all");
        }
        // a control with egui's focus that is no text field: the first button, focused as a screen reader focuses it
        let tab_to_control = |w: &mut Win, app: &mut App| {
            let _ = w.run(app, vec![]);
            let said = w.run(app, vec![]);
            let (id, ..) = *said.iter().find(|(_, r, _)| *r == egui::accesskit::Role::Button).expect("a button");
            let focus = egui::accesskit::ActionRequest { action: egui::accesskit::Action::Focus, target: id, data: None };
            let _ = w.run(app, vec![egui::Event::AccessKitActionRequest(focus)]);
            let _ = w.run(app, vec![]);
            assert!(w.ctx.memory(|m| m.focused()).is_some_and(|f| f.value() == id.0), "the button has the focus");
            assert!(!typing(&w.ctx), "and it is no text field");
            id.0
        };
        let held = tab_to_control(&mut w, &mut app);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(heads.iter().all(|k| app.folded.contains(k)), "Edit, a control focused: Collapse all");
        assert!(w.ctx.memory(|m| m.focused()).is_some_and(|f| f.value() == held), "the focus is back on the control that had it");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert!(heads.iter().all(|k| !app.folded.contains(k)));
        w.ctx.memory_mut(|m| m.request_focus(egui::Id::new(SEARCH_ID)));
        let _ = w.run(&mut app, vec![]);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(heads.iter().all(|k| !app.folded.contains(k)), "the search box with the caret keeps them");
        w.ctx.memory_mut(|m| m.surrender_focus(egui::Id::new(SEARCH_ID)));
        // Compare: from its Menu and from a control with the focus
        let b = app.doc.as_ref().unwrap().original.clone();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::b(0)], false);
        let _ = w.run(&mut app, vec![]);
        for pane in [Focus::Tabs, Focus::Items] {
            app.focus = pane;
            w.key_with(&mut app, egui::Key::ArrowUp, cs);
            assert!(!app.matrix_closed.is_empty(), "Compare, {pane:?}: Collapse all");
            w.key_with(&mut app, egui::Key::ArrowDown, cs);
            assert!(app.matrix_closed.is_empty(), "Compare, {pane:?}: Expand all");
        }
        tab_to_control(&mut w, &mut app);
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(!app.matrix_closed.is_empty(), "Compare, a control focused: Collapse all");
        done(&dir, &user);
    }

    /// The reviewer's finding 4: the window takes the fold keys as the page does: never with Alt held too, and not
    /// while a list, a popup or a right-click menu is open.
    #[test]
    fn the_fold_keys_are_left_alone_with_alt_or_a_menu_open() {
        let (mut app, dir, user) = sample_app("fold_keys_alike", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        let (tab, group) = ("Shooting", "Drive Mode");
        let rows = app.tab_groups(tab).into_iter().find(|(g, _, _)| g == group).unwrap().2;
        let lines = app.group_lines(&rows);
        let heads: Vec<String> = lines.iter().filter_map(|l| match l { Line::Heading { path, .. } => Some(App::fold_key(tab, group, path)), _ => None }).collect();
        let first = lines.iter().find_map(|l| match l { Line::Row { index, .. } => Some(rows[*index][0].clone()), _ => None }).unwrap();
        app.select(Some(View::Tab(tab.into())), Some(group.into()), Some((&first.name, &first.key)));
        let _ = w.run(&mut app, vec![]);
        w.key_with(&mut app, egui::Key::ArrowUp, cs | egui::Modifiers::ALT);
        assert!(heads.iter().all(|k| !app.folded.contains(k)), "Alt held too: nothing folds");
        // a popup open
        w.ctx.memory_mut(|m| m.open_popup(egui::Id::new("a popup")));
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(heads.iter().all(|k| !app.folded.contains(k)), "a popup open: nothing folds");
        w.ctx.memory_mut(|m| m.close_popup());
        // a right-click menu open, by a right click on the row's name
        let _ = w.run(&mut app, vec![]);
        let frame = &mut w.frame;
        let out = w.ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, frame));
        let tree = out.platform_output.accesskit_update.expect("the window's tree");
        let rect = tree.nodes.iter().find(|(_, n)| n.label() == Some(first.name.as_str())).and_then(|(_, n)| n.bounds()).expect("the row's name");
        let at = egui::pos2(((rect.x0 + rect.x1) / 2.0) as f32, ((rect.y0 + rect.y1) / 2.0) as f32);
        let click = |pressed| egui::Event::PointerButton { pos: at, button: egui::PointerButton::Secondary, pressed, modifiers: egui::Modifiers::NONE };
        let _ = w.run(&mut app, vec![egui::Event::PointerMoved(at)]);
        let _ = w.run(&mut app, vec![click(true)]);
        let _ = w.run(&mut app, vec![click(false)]);
        let _ = w.run(&mut app, vec![]);
        assert!(w.ctx.is_context_menu_open(), "the row's right-click menu is open");
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert!(heads.iter().all(|k| !app.folded.contains(k)), "a right-click menu open: nothing folds");
        done(&dir, &user);
    }

    /// A single row of the camera's menu that holds others folds by the keyboard alone: Up and Down stop on it (column 4
    /// says what it is), Enter or Space folds or shows what it holds, Left folds it and Right shows it, and Down goes on
    /// to the next row.
    #[test]
    fn a_heading_folds_by_the_keyboard() {
        let (mut app, dir, user) = sample_app("fold_head_keys", Some(crate::test_support::strip_menus));
        let mut w = Win::new();
        let (tab, group) = ("Shooting", "Drive Mode");
        let rows = app.tab_groups(tab).into_iter().find(|(g, _, _)| g == group).unwrap().2;
        let lines = app.group_lines(&rows);
        // the first heading and the row just above it (or, at the top, the row just below)
        let h = lines.iter().position(|l| matches!(l, Line::Heading { .. })).unwrap();
        let Line::Heading { path, label, .. } = &lines[h] else { unreachable!() };
        let key = App::fold_key(tab, group, path);
        let next = lines[h + 1..].iter().find_map(|l| match l { Line::Row { index, .. } => Some(rows[*index][0].clone()), _ => None }).unwrap();
        app.select(Some(View::Tab(tab.into())), Some(group.into()), Some((&next.name, &next.key)));
        app.focus = Focus::Items;
        let _ = w.run(&mut app, vec![]);
        // Up from the row under it, until the heading is chosen
        for _ in 0..(lines.len()) {
            if app.item_head.as_ref() == Some(path) { break; }
            w.key(&mut app, egui::Key::ArrowUp);
        }
        assert_eq!(app.item_head.as_ref(), Some(path), "Up stops on the heading");
        assert!(app.item.is_none(), "no setting chosen with it");
        assert!(w.drawn(&mut app).iter().any(|t| t.contains("Enter or Space folds or shows them")), "column 4 says what it is");
        w.key(&mut app, egui::Key::Space);
        assert!(app.folded.contains(&key), "Space folds it");
        w.key(&mut app, egui::Key::Enter);
        assert!(!app.folded.contains(&key), "Enter shows it");
        w.key(&mut app, egui::Key::ArrowLeft);
        assert!(app.folded.contains(&key) && app.focus == Focus::Items, "Left folds it, the column stays");
        w.key(&mut app, egui::Key::ArrowRight);
        assert!(!app.folded.contains(&key), "Right shows it");
        assert_eq!(app.item_head.as_ref(), Some(path), "still chosen: {label}");
        w.key(&mut app, egui::Key::ArrowDown);
        assert_eq!(app.item_key.as_deref(), Some(next.key.as_str()), "Down goes on to the row under it");
        assert!(app.item_head.is_none());
        done(&dir, &user);
    }

    /// The exposure page's "What decides" sections fold and open by Cmd/Ctrl+Shift+↑ / ↓ as by its own Collapse all and
    /// Expand all (every foldable group of the view in front), and a text field with the keyboard keeps the keys.
    #[test]
    fn the_exposure_pages_sections_fold_by_the_keys_and_the_buttons() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("fold_keys_ex", None);
        let mut w = Win::new();
        let cs = egui::Modifiers::COMMAND | egui::Modifiers::SHIFT;
        app.view = View::Exposure;
        // which sections show what they hold, once the header's animation is over
        let open = |w: &mut Win, app: &mut App| {
            for _ in 0..8 {
                let _ = w.run(app, vec![]);
            }
            let drawn = w.drawn(app);
            crate::pages::exposure::EFFECTS.iter().map(|(_, _, effect)| drawn.iter().any(|t| t.contains(&effect[..24]))).collect::<Vec<_>>()
        };
        assert_eq!(open(&mut w, &mut app), [false; 3], "folded to start with");
        let heads = w.drawn(&mut app);
        assert!(["What decides the aperture", "What decides the shutter speed", "What decides ISO"].iter().all(|h| heads.iter().any(|t| t == h)), "the page is drawn: {heads:?}");
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert_eq!(open(&mut w, &mut app), [true; 3], "Expand all by the keys");
        w.key_with(&mut app, egui::Key::ArrowUp, cs);
        assert_eq!(open(&mut w, &mut app), [false; 3], "Collapse all by the keys");
        w.click(&mut app, Role::Button, "Expand all");
        assert_eq!(open(&mut w, &mut app), [true; 3], "the button leaves what the keys leave");
        w.click(&mut app, Role::Button, "Collapse all");
        assert_eq!(open(&mut w, &mut app), [false; 3]);
        // a text field with the keyboard keeps the keys for its text
        w.ctx.memory_mut(|m| m.request_focus(egui::Id::new(SEARCH_ID)));
        let _ = w.run(&mut app, vec![]);
        w.key_with(&mut app, egui::Key::ArrowDown, cs);
        assert_eq!(open(&mut w, &mut app), [false; 3], "the search box had the keyboard");
        done(&dir, &user);
    }

    /// Integration review finding 1: with a row chosen, Up/Down in the groups column move to the next group, with menus
    /// as without ("JPEG/HEIF Switch" chosen, Left, Down: the group after Image Quality/Rec); a row picked on the My Menu
    /// page and then a click on Setup in the Menu opens Setup; and a menu picked with a row chosen keeps that row where
    /// the menu lists it (ISO in Still, then Movie: its ISO row, the movie copy's).
    #[test]
    fn a_row_chosen_never_takes_the_selection_back() {
        use egui::accesskit::Role;
        for menus in [None, Some(crate::test_support::stub_menus as fn(&mut serde_json::Value))] {
            let (mut app, dir, user) = sample_app("menus_select", menus);
            let mut w = Win::new();
            let jpeg = setting(&app, "global:0x01d8");
            app.go_to(&jpeg);
            let View::Tab(tab) = app.view.clone() else { panic!() };
            let groups: Vec<String> = app.tab_groups(&tab).into_iter().map(|(n, _, _)| n).collect();
            let at = groups.iter().position(|g| Some(g) == app.group.as_ref()).unwrap();
            w.key(&mut app, egui::Key::ArrowLeft);
            assert!(app.focus == Focus::Groups);
            w.key(&mut app, egui::Key::ArrowDown);
            assert_eq!((app.view.clone(), app.group.clone()), (View::Tab(tab.clone()), Some(groups[at + 1].clone())), "menus: {}", menus.is_some());
            // the group step alone (`keyboard_nav`, before the pages draw and `follow_selection` acts): the next group,
            // no row, its name and key together (`select`)
            app.go_to(&jpeg);
            app.focus = Focus::Groups;
            let down = egui::RawInput { events: vec![egui::Event::Key { key: egui::Key::ArrowDown, physical_key: None, pressed: true, repeat: false, modifiers: Default::default() }], ..Default::default() };
            let _ = egui::Context::default().run(down, |ctx| app.keyboard_nav(ctx));
            assert_eq!((app.group.clone(), app.item.as_deref(), app.item_key.as_deref()), (Some(groups[at + 1].clone()), None, None), "menus: {}", menus.is_some());
            // My Menu's page, a row of its own picked there, then Setup
            let iso = setting(&app, "global:0x0334");
            app.go_to(&iso);
            app.view = View::MyMenu;
            w.click_where(&mut app, &[Role::Button, Role::Link, Role::Label], |l| l == "Display From My Menu", "Display From My Menu");
            assert_eq!(app.item.as_deref(), Some("Display From My Menu"));
            // the pick chose that row by its name and its key (`select`)
            assert_eq!(app.item_key.as_deref(), Some("global:0x01d7"), "menus: {}", menus.is_some());
            w.click_where(&mut app, &[Role::Button], |l| l.starts_with("Setup  ("), "Setup");
            assert_eq!(app.view, View::Tab("Setup".into()), "menus: {}", menus.is_some());
            if menus.is_some() {
                app.set_menu("Still");
                app.go_to(&iso);
                app.set_menu("Movie");
                let _ = w.run(&mut app, vec![]);
                let row = app.listed_record(&iso, 0, "Movie");
                assert_eq!((app.menu_shown().as_deref(), app.item.clone(), app.item_key.clone()), (Some("Movie"), Some(row.name), Some(row.key)), "the row stays chosen in Movie's menu");
            }
            done(&dir, &user);
        }
    }

    /// Review finding 2: the record map's and the Exposure page's jumps land on the setting clicked and stay there, the
    /// row chosen before (SteadyShot) not taking the selection back; one to a row only Movie's menu has opens Movie's;
    /// and a jump made by hand with only `item` set (no `item_key`) is left alone by `follow_selection`.
    #[test]
    fn the_record_maps_and_the_exposure_pages_jumps_land() {
        use egui::accesskit::Role;
        let (mut app, dir, user) = sample_app("menus_jumps_land", Some(crate::test_support::stub_menus));
        let (steady, lower, audio) = (setting(&app, "global:0x02f7"), setting(&app, "global:0x0b65"), setting(&app, "global:0x02e9"));
        let choose_steady = |app: &mut App| {
            app.set_menu("Still");
            app.go_to(&steady);
            assert_eq!(app.item_key.as_deref(), Some(steady.key.as_str()));
        };
        let landed = |app: &App, s: &Setting| {
            let shown = app.listed_record(s, 0, &app.menu_shown().unwrap());
            (app.view.clone(), app.group.clone(), app.item.clone(), app.item_key.clone()) == (app.view_of(s), Some(app.shown_group_of(s)), Some(shown.name.clone()), Some(shown.key.clone()))
        };
        let mut w = Win::new();
        // the record map (Expert mode's), filtered to one record by its number
        app.prefs.expert = true;
        for (s, menu) in [(&lower, "Still"), (&audio, "Movie")] {
            choose_steady(&mut app);
            (app.view, app.search) = (View::Records, format!("0x{:04x}", s.id));
            w.click(&mut app, Role::Label, &s.name);
            assert_eq!(app.menu_shown().as_deref(), Some(menu), "{}", s.name);
            assert!(landed(&app, s), "{}: {:?} {:?} {:?} {:?}", s.name, app.view, app.group, app.item, app.item_key);
        }
        app.prefs.expert = false;
        app.search.clear();
        // the Exposure page, with one setting under "What decides ISO" alone
        {
            let ex = app.schema.camera.exposure.as_mut().unwrap();
            (ex.mode_key, ex.memory_mode_key) = (String::new(), String::new());
            for side in [&mut ex.aperture, &mut ex.shutter, &mut ex.iso] {
                (side.key, side.memory_key, side.memory_numerator_key, side.memory_denominator_key) = (String::new(), String::new(), String::new(), String::new());
                side.limits.clear();
            }
        }
        for (i, (s, menu)) in [(&lower, "Still"), (&audio, "Movie")].into_iter().enumerate() {
            app.schema.camera.exposure.as_mut().unwrap().iso.key = s.key.clone();
            choose_steady(&mut app);
            app.view = View::Exposure;
            if i == 0 {
                // opened once, it stays open
                w.click(&mut app, Role::Button, "What decides ISO");
            }
            w.click(&mut app, Role::Button, "Show in menu");
            assert_eq!(app.menu_shown().as_deref(), Some(menu), "{}", s.name);
            assert!(landed(&app, s), "{}: {:?} {:?} {:?} {:?}", s.name, app.view, app.group, app.item, app.item_key);
        }
        // a jump made by hand that sets `item` alone: the row chosen before does not take the selection back
        choose_steady(&mut app);
        (app.view, app.group, app.item) = (View::Tab("Exposure/Color".into()), Some("Exposure".into()), Some(lower.name.clone()));
        let _ = w.run(&mut app, vec![]);
        assert_eq!((app.group.as_deref(), app.item.as_deref()), (Some("Exposure"), Some(lower.name.as_str())), "left alone");
        done(&dir, &user);
    }

    /// Review finding 1: a copy shown in its setting's row in a menu sits where the setting sits, in its tab and group,
    /// whatever the copy's own tab and group say: White Balance's fine-tune movie copy (its own place Shooting > Other
    /// settings) in the Movie menu of a file saved in Stills is the choice beside White Balance's option, in
    /// Exposure/Color > White Balance, and no row of a group of its own.
    #[test]
    fn a_copy_in_its_settings_row_sits_in_its_settings_tab_and_group() {
        let (app, dir, user) = sample_app("menus_copy_place", Some(crate::test_support::stub_menus));
        let main = setting(&app, "global:0x0c63");
        let copy = app.copy_for_menu(&main, "Movie").cloned().unwrap();
        assert!(copy.tab != main.tab || copy.group != main.group, "the case: the copy's own tab and group are other");
        assert_ne!(app.opening_menu(0).as_deref(), Some("Movie"), "a file saved in another mode than Movie's");
        let shown = app.listed_record(&main, 0, "Movie");
        assert_eq!(shown.key, copy.key);
        assert_eq!((shown.tab.as_str(), shown.group.as_str()), (main.tab.as_str(), main.group.as_str()));
        assert_eq!((app.layout_tab(&shown), app.layout_group(&shown)), (app.layout_tab(&main.place_in("Movie")), app.layout_group(&main.place_in("Movie"))));
        // as on the camera, beside White Balance's option, not a row of another group
        let wb = app.settings_in_menu(0, "Movie", None).into_iter().find(|s| menu_rows::is_own(s) && s.row == ["White Balance"]).unwrap();
        assert!(app.beside_in(0, Some("Movie"), &wb).iter().any(|(x, _)| x.key == copy.key), "the fine-tune choice beside White Balance's option");
        assert!(app.tab_groups_in(0, Some("Movie"), &copy.tab, "", false).iter().all(|(_, _, rows)| rows.iter().flatten().all(|s| s.key != copy.key || s.tab == main.tab)));
        done(&dir, &user);
    }

    /// Design point 4: in a menu other than the one of the mode the file was saved in, the ISO row shows its copy for
    /// that menu, under the setting's name, and an edit goes to that copy's record (what follows it is `apply`'s rule,
    /// as before menus); the copies are no rows of their own there; in the file's own menu the row is the setting.
    #[test]
    fn the_iso_row_in_another_modes_menu_shows_and_edits_its_copy() {
        let (mut app, dir, user) = sample_app("menus_iso", Some(crate::test_support::stub_menus));
        let own = app.opening_menu(0).unwrap();
        let iso = setting(&app, "global:0x0334");
        let other = app.menus().iter().map(|m| m.name.clone()).find(|m| *m != own && app.copy_for_menu(&iso, m).is_some()).unwrap();
        let copy = app.copy_for_menu(&iso, &other).unwrap().clone();
        let groups = app.tab_groups_in(0, Some(&other), "Exposure/Color", "", false);
        let rows: Vec<Vec<Setting>> = groups.into_iter().filter(|(g, _, _)| g == "Exposure").flat_map(|(_, _, r)| r).collect();
        let named: Vec<&Vec<Setting>> = rows.iter().filter(|r| r[0].row == ["ISO"] && r[0].under_option.is_none() && app.full_name(&r[0]).starts_with("ISO (")).collect();
        assert_eq!(named.len(), 1, "one ISO row");
        let row = named[0][0].clone();
        assert_eq!((row.name.as_str(), row.key.as_str()), ("ISO", copy.key.as_str()));
        assert!(!rows.iter().any(|r| r[0].name.starts_with("ISO (")), "no copy a row of its own");
        let doc = app.doc.as_ref().unwrap();
        assert_eq!(app.row_value(&row), App::describe(&copy, doc.value(0, copy.slot())));
        let cur = doc.value(0, copy.slot()).unwrap();
        let v = copy.offered(false).into_iter().map(|(v, _)| v).find(|&v| v != cur).unwrap();
        assert_eq!(app.apply(vec![Action::Set(0, row.slot(), v)]), None);
        assert_eq!(app.doc.as_ref().unwrap().value(0, copy.slot()), Some(v), "the copy's record takes it");
        assert_eq!(app.listed_record(&iso, 0, &own).key, iso.key, "in the file's own menu, the setting");
        // Compare's rows always show the copy for the menu
        assert_eq!(app.row_record(&iso, &own, &Bind::Menu).key, app.copy_for_menu(&iso, &own).unwrap().key);
        done(&dir, &user);
    }

    /// Two menus, four named otherwise, a menu two of a setting's copies are for (its rows as before menus), and one
    /// menu (no choice: every listing as before menus).
    #[test]
    fn two_four_and_one_menu() {
        let movie_copy = "global:0x0df4";
        let (app, dir, user) = sample_app("menus_two", Some(two_menus));
        assert_eq!(app.menus().iter().map(|m| m.name.as_str()).collect::<Vec<_>>(), ["Still", "Motion"]);
        let iso = setting(&app, "global:0x0334");
        assert_eq!(app.copy_for_menu(&iso, "Motion").map(|c| c.key.as_str()), Some(movie_copy));
        assert_eq!(app.menu_sets(Some("Motion")), [0, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
        assert_eq!(app.menu_sets(Some("Still")), [0, 1, 2, 3]);
        done(&dir, &user);
        let (app, dir, user) = sample_app("menus_four", Some(four_menus));
        assert_eq!(app.menus().iter().map(|m| m.name.as_str()).collect::<Vec<_>>(), ["One", "Two", "Three", "Four"]);
        assert_eq!((app.menu_sets(Some("Four")), app.opening_menu(10), app.opening_menu(7)), (vec![0, 10, 11, 12], Some("Four".into()), Some("Three".into())));
        assert!(app.tab_groups_in(0, Some("Two"), "Shooting", "", false).iter().any(|(g, _, _)| g == "TC/UB"));
        assert!(!app.tab_groups_in(0, Some("One"), "Shooting", "", false).iter().any(|(g, _, _)| g == "TC/UB"));
        assert_eq!(app.copy_for_menu(&iso, "Four").map(|c| c.key.as_str()), Some(movie_copy));
        done(&dir, &user);
        let (app, dir, user) = sample_app("menus_shared", Some(shared_menus));
        assert!(app.copy_for_menu(&iso, "A").is_none(), "two copies are for A");
        let names: Vec<String> = app.settings_in_menu(0, "A", None).into_iter().filter(|s| s.row == ["ISO"] && s.under_option.is_none()).map(|s| s.name).collect();
        assert!(["ISO (stills)", "ISO (movie)"].iter().all(|n| names.contains(&n.to_string())), "the rows as before menus: {names:?}");
        done(&dir, &user);
        let (one, dir, user) = sample_app("menus_one", Some(one_menu));
        let (plain, dir2, user2) = sample_app("menus_plain", Some(crate::test_support::strip_menus));
        assert!(one.menus().is_empty() && one.menu_shown().is_none());
        let shape = |app: &App, tab: &str| app.tab_groups(tab).into_iter().map(|(g, f, rows)| (g, f, rows.iter().map(|r| r[0].key.clone()).collect::<Vec<_>>())).collect::<Vec<_>>();
        for tab in plain.menu_tabs() {
            assert_eq!(shape(&one, &tab), shape(&plain, &tab), "{tab}");
        }
        done(&dir, &user);
        done(&dir2, &user2);
    }

    /// Design point 2 and 5: each set opens on its mode's menu; the viewer's pick holds until another set is edited;
    /// the file saved in another mode opens on that mode's menu, whose button says so; the "Editing:" row's sets are
    /// the menu's; no menu picked, nor any frame drawn with it, changes a byte of the file.
    #[test]
    fn a_menu_opens_on_the_sets_mode_and_changes_no_byte() {
        let (mut app, dir, user) = sample_app("menus_open", Some(crate::test_support::stub_menus));
        assert_eq!([1, 4, 7, 10].map(|t| app.opening_menu(t)), [Some("Still".into()), Some("Movie".into()), Some("S&Q".into()), Some("S&Q".into())]);
        let before = app.doc.as_ref().unwrap().edited.to_bytes();
        let own = app.opening_menu(0).unwrap();
        app.view = View::Tab("Shooting".into());
        frame(&mut app);
        assert_eq!(app.menu_shown(), Some(own.clone()));
        app.set_menu("S&Q");
        frame(&mut app);
        assert_eq!(app.menu_shown().as_deref(), Some("S&Q"), "the pick holds");
        app.target = 4;
        frame(&mut app);
        assert_eq!(app.menu_shown().as_deref(), Some("Movie"), "another set: its own menu");
        app.target = 0;
        frame(&mut app);
        assert_eq!(app.menu_shown(), Some(own.clone()));
        for m in ["Still", "Movie", "S&Q"] {
            app.set_menu(m);
            frame(&mut app);
            assert_eq!(app.doc.as_ref().unwrap().edited.to_bytes(), before, "{m}");
        }
        assert_eq!(app.shown_sections(), (0..13).collect::<Vec<_>>(), "every menu's sets can be edited");
        assert_eq!(app.menu_sets(Some("Movie")), [0, 4, 5, 6]);
        // saved in Movie mode: Movie's menu, and its button says so
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let mode = setting(&app, &lm.key);
        let movie = lm.modes.iter().find(|(_, m)| *m == "Movie").map(|(v, _)| v.parse::<i64>().unwrap()).unwrap();
        app.allow_unobserved = true;
        app.apply(vec![Action::Set(0, mode.slot(), movie)]);
        app.menu = None;
        assert_eq!(app.menu_shown().as_deref(), Some("Movie"));
        assert!(app.menu_hover("Movie").ends_with("This file was saved in Movie mode."), "{}", app.menu_hover("Movie"));
        assert_eq!(app.menu_hover("S&Q"), "Slow and quick motion, and time-lapse");
        done(&dir, &user);
    }

    /// Design point 7: the next edit (F3) goes from a row of Still's menu to one only Movie's has, showing Movie's
    /// menu, and back; a jump a view makes by hand (the setting's key chosen) shows the menu that shows the row from
    /// the next frame; a jump to a copy opens its setting's row where that row shows it.
    #[test]
    fn jumps_and_the_next_edit_change_menus() {
        let (mut app, dir, user) = sample_app("menus_jump", Some(crate::test_support::stub_menus));
        let (still, audio) = (setting(&app, "global:0x02f7"), setting(&app, "global:0x02e9"));
        for s in [&still, &audio] {
            let cur = app.doc.as_ref().unwrap().value(0, s.slot());
            let v = s.values.iter().map(|(v, _)| *v).find(|v| Some(*v) != cur).unwrap();
            assert_eq!(app.apply(vec![Action::Set(0, s.slot(), v)]), None);
        }
        app.set_menu("Still");
        app.view = View::Main;
        app.step_edit(1);
        assert_eq!((app.menu_shown().as_deref(), app.item_key.as_deref()), (Some("Still"), Some(still.key.as_str())));
        app.step_edit(1);
        assert_eq!((app.menu_shown().as_deref(), app.item_key.as_deref(), app.group.as_deref()), (Some("Movie"), Some(audio.key.as_str()), Some("Audio Recording")));
        app.step_edit(1);
        assert_eq!((app.menu_shown().as_deref(), app.item_key.as_deref()), (Some("Still"), Some(still.key.as_str())));
        // a jump made by hand
        (app.view, app.group, app.item, app.item_key) = (View::Tab("Shooting".into()), Some("Audio Recording".into()), Some(audio.name.clone()), Some(audio.key.clone()));
        frame(&mut app);
        assert_eq!((app.menu_shown().as_deref(), app.item.as_deref()), (Some("Movie"), Some("Audio Recording")));
        // a copy: its setting's row, in the menu where that row shows it
        let iso = setting(&app, "global:0x0334");
        let own = app.opening_menu(0).unwrap();
        let (m, copy) = app.menus().iter().map(|m| m.name.clone()).filter(|m| *m != own).find_map(|m| app.copy_for_menu(&iso, &m).cloned().map(|c| (m, c))).unwrap();
        app.set_menu(&own);
        app.go_to(&copy);
        assert_eq!((app.menu_shown(), app.item.as_deref(), app.item_key.as_deref()), (Some(m), Some("ISO"), Some(copy.key.as_str())));
        done(&dir, &user);
    }

    /// Design point 9's keys, as the frame takes them (`bar_nav`, then `keyboard_nav`): Up and Down in the Menu's column
    /// step through the bar's own entries, Main and My Menu above the tabs and the entry for what the camera's menus do
    /// not hold below them; Left from Main's page takes the Menu's column; in a menu, only the tabs it holds. (Compare's
    /// bar and Alt with the arrows: menu_view's `up_and_down_step_through_the_bars_own_entries`.)
    #[test]
    fn the_menus_column_by_the_keys_in_edit() {
        let press = |app: &mut App, key: egui::Key| {
            let ctx = egui::Context::default();
            let input = egui::RawInput { events: vec![egui::Event::Key { key, physical_key: None, pressed: true, repeat: false, modifiers: Default::default() }], ..Default::default() };
            let _ = ctx.run(input, |ctx| {
                app.bar_nav(ctx);
                app.keyboard_nav(ctx);
            });
        };
        let (mut app, dir, user) = sample_app("menus_keys", None);
        let first = app.menu_tabs()[0].clone();
        (app.mode, app.view, app.focus) = (Mode::Edit, View::Tab(first), Focus::Tabs);
        press(&mut app, egui::Key::ArrowUp);
        assert_eq!(app.view, View::MyMenu);
        press(&mut app, egui::Key::ArrowUp);
        press(&mut app, egui::Key::ArrowUp);
        assert_eq!(app.view, View::Main, "Main first, and no further");
        for _ in 0..20 {
            press(&mut app, egui::Key::ArrowDown);
        }
        let off = app.schema.camera.text.off_menu_name().to_string();
        assert_eq!(app.view, View::Tab(off.clone()), "the entry for what the menus do not hold, last");
        // from Main's page, Left takes the Menu's column
        (app.view, app.focus) = (View::Main, Focus::Items);
        press(&mut app, egui::Key::ArrowLeft);
        press(&mut app, egui::Key::ArrowDown);
        assert_eq!((app.focus, app.view.clone()), (Focus::Tabs, View::MyMenu));
        done(&dir, &user);
        let (mut app, dir, user) = sample_app("menus_keys_menu", Some(crate::test_support::stub_menus));
        let listed: Vec<BarKey> = app.bar_keys(false, 0, Some("Movie"), "", false);
        let all: Vec<BarKey> = app.bar_keys(false, 0, Some("Still"), "", false);
        assert!(listed.len() <= all.len() && listed.contains(&BarKey::Tab("Shooting".into())));
        app.set_menu("Movie");
        (app.mode, app.view, app.focus) = (Mode::Edit, View::Main, Focus::Tabs);
        let mut seen = Vec::new();
        for _ in 0..listed.len() {
            press(&mut app, egui::Key::ArrowDown);
            seen.push(app.view.clone());
        }
        let want: Vec<View> = listed[1..].iter().map(|k| match k { BarKey::MyMenu => View::MyMenu, BarKey::Tab(t) => View::Tab(t.clone()), _ => View::Main }).collect();
        assert_eq!(seen[..want.len()], want[..]);
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
        let (got, text) = golden_menu(&app, "ILCE-1M2_fw4.00");
        done(&dir, &user);
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("data").join("menu_ILCE-1M2_fw4.00.json");
        if std::env::var("CAMSET_BLESS").is_ok_and(|v| v == "1") {
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(&path, text).unwrap();
            return;
        }
        let want: serde_json::Value = std::fs::read_to_string(&path).ok().and_then(|t| serde_json::from_str(&t).ok())
            .unwrap_or_else(|| panic!("{} is missing or unreadable: write it with CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one", path.display()));
        assert!(got == want, "the default Menu is not {}: if the definition or the layout changed on purpose, write it again with CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one, look at its diff, and make kit/camkit/menu_rows.py lay it out the same (kit/tests/test_menu_rows.py)", path.display());
    }

    /// The golden Menu of `app`'s definition (`definition` its name), the value and the file's text, one group a line
    /// so that a change reads as a diff of the groups it touched. Without the camera's menus: `{"definition", "entries"}`.
    /// With them: `{"definition", "menus": [{"menu", "mode", "entries"}]}`, each menu laid out for the live settings,
    /// `mode` the shooting mode the sample was saved in (by which a row picks its record: `Bind::Set`), and a row the
    /// menu titles otherwise than the definition names its setting with that title last.
    pub(crate) fn golden_menu(app: &App, definition: &str) -> (serde_json::Value, String) {
        let def = serde_json::to_string(definition).unwrap();
        let block = |entries: &[(String, Vec<String>)], pad: &str| -> String {
            entries.iter().enumerate().map(|(n, (tab, groups))| format!("{pad}{{\"entry\": {}, \"groups\": [\n{pad} {}\n{pad}]}}{}\n", serde_json::to_string(tab).unwrap(),
                groups.join(&format!(",\n{pad} ")), if n + 1 < entries.len() { "," } else { "" })).collect()
        };
        let parse = |entries: &[(String, Vec<String>)]| -> Vec<serde_json::Value> {
            entries.iter().map(|(tab, groups)| serde_json::json!({ "entry": tab, "groups": groups.iter().map(|g| serde_json::from_str::<serde_json::Value>(g).unwrap()).collect::<Vec<_>>() })).collect()
        };
        if app.menus().is_empty() {
            let entries = golden_entries(app, None);
            let text = format!("{{\"definition\": {def}, \"entries\": [\n{}]}}\n", block(&entries, " "));
            return (serde_json::json!({ "definition": definition, "entries": parse(&entries) }), text);
        }
        let mode = app.set_mode(0);
        let menus: Vec<String> = app.menus().iter().map(|m| m.name.clone()).collect();
        let mut text = format!("{{\"definition\": {def}, \"menus\": [\n");
        let mut got = Vec::new();
        for (n, m) in menus.iter().enumerate() {
            let entries = golden_entries(app, Some(m));
            text += &format!(" {{\"menu\": {}, \"mode\": {}, \"entries\": [\n{} ]}}{}\n", serde_json::to_string(m).unwrap(), serde_json::to_string(&mode).unwrap(),
                block(&entries, "  "), if n + 1 < menus.len() { "," } else { "" });
            got.push(serde_json::json!({ "menu": m, "mode": mode, "entries": parse(&entries) }));
        }
        text += "]}\n";
        (serde_json::json!({ "definition": definition, "menus": got }), text)
    }

    /// The golden Menu's entries in menu `menu` (None: without menus), each with its groups as JSON text: each entry the
    /// side bar lists, its groups, a family's table by its records' keys, every other group's lines (a row by the keys
    /// of its linked records, and in a menu its title where it is not its setting's name).
    fn golden_entries(app: &App, menu: Option<&str>) -> Vec<(String, Vec<String>)> {
        let mut out = Vec::new();
        for tab in app.menu_tabs() {
            if !app.side_bar_lists_in(0, menu, &tab, "", false) {
                continue;
            }
            let mut groups = Vec::new();
            for (name, family, rows) in app.tab_groups_in(0, menu, &tab, "", false) {
                let keys = |i: usize| rows[i].iter().map(|s| s.key.clone()).collect::<Vec<_>>();
                let group = if family {
                    serde_json::json!({ "group": name, "family": true, "keys": keys(0) })
                } else {
                    let lines: Vec<serde_json::Value> = app.group_lines(&rows).into_iter().map(|l| match l {
                        Line::Heading { label, depth, .. } => serde_json::json!(["heading", label, depth]),
                        Line::Row { index, depth } if menu.is_some() && rows[index][0].name != app.full_name(&rows[index][0]) => serde_json::json!(["row", keys(index), depth, rows[index][0].name]),
                        Line::Row { index, depth } => serde_json::json!(["row", keys(index), depth]),
                        Line::Mode(m) => serde_json::json!(["mode", m]),
                        Line::More => serde_json::json!(["more"]),
                    }).collect();
                    serde_json::json!({ "group": name, "family": false, "lines": lines })
                };
                groups.push(serde_json::to_string(&group).unwrap());
            }
            out.push((tab, groups));
        }
        out
    }
}
