//! Compare: files A, B and a three-way base, their columns, and how a row stands between them; copying values into
//! file A. The view itself is in `compare_view`.

use crate::*;

/// Which file a compare column comes from: A (the editable one), B, or the three-way base.
#[derive(Clone, Copy, PartialEq, Debug)]
pub(crate) enum Src {
    A,
    B,
    Base,
}

impl Src {
    pub(crate) fn letter(self) -> &'static str {
        match self { Src::A => "A", Src::B => "B", Src::Base => "Base" }
    }
    /// The file's colour in the window, for the theme in use: file A in the strongest text colour.
    pub(crate) fn tone(self, v: &egui::Visuals) -> Color32 {
        match self { Src::A => v.strong_text_color(), Src::B => tone::file_b(v), Src::Base => tone::file_base(v) }
    }
}

/// A column in the compare view: a section (0 = live, 1.. = memory sets) of one of the files.
#[derive(Clone, Copy, PartialEq, Debug)]
pub(crate) struct Col {
    pub(crate) src: Src,
    pub(crate) section: usize,
}

impl Col {
    pub(crate) fn a(section: usize) -> Col { Col { src: Src::A, section } }
    pub(crate) fn b(section: usize) -> Col { Col { src: Src::B, section } }
    pub(crate) fn base(section: usize) -> Col { Col { src: Src::Base, section } }
    /// Whether this column belongs to file A (the only editable one).
    pub(crate) fn editable(self) -> bool { self.src == Src::A }
}

/// Compare's "Open in Edit": where it put Edit (the page, group and setting shown, and the set edited) and the
/// Compare row it came from (tab, setting key). Edit offers "← Back to Compare" while it still shows that setting.
pub(crate) struct FromCompare {
    pub(crate) view: View,
    pub(crate) group: Option<String>,
    pub(crate) item: Option<String>,
    pub(crate) target: usize,
    pub(crate) row: (String, String),
}

/// How a row stands in a three-way compare (Base against A and B).
#[derive(Clone, Copy, PartialEq, Debug)]
pub(crate) enum Three {
    Same,
    AOnly,
    BOnly,
    Both,
    Conflict,
}

impl Three {
    /// The tag in the 3-way column and its hover (its colour: `tone`).
    pub(crate) fn tag(self) -> (&'static str, &'static str) {
        match self {
            Three::Same => ("", "Same in all three"),
            Three::AOnly => ("A", "Changed in A only (B still has the base value)"),
            Three::BOnly => ("B", "Changed in B only (A still has the base value): mergeable into A"),
            Three::Both => ("A=B", "A and B made the same change"),
            Three::Conflict => ("!", "Conflict: A and B changed it differently"),
        }
    }
    /// The tag's colour in the window, for the theme in use.
    pub(crate) fn tone(self, v: &egui::Visuals) -> Color32 {
        match self {
            Three::Same => Color32::TRANSPARENT,
            Three::AOnly => v.strong_text_color(),
            Three::BOnly => tone::file_b(v),
            Three::Both => tone::ok(v),
            Three::Conflict => tone::bad(v),
        }
    }
}

/// Three-way row filter.
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum ThreeFilter {
    All,
    AOnly,
    BOnly,
    Both,
    Conflicts,
}

impl ThreeFilter {
    pub(crate) fn label(self) -> &'static str {
        match self { ThreeFilter::All => "All rows", ThreeFilter::AOnly => "Changed in A", ThreeFilter::BOnly => "Changed in B", ThreeFilter::Both => "Same change", ThreeFilter::Conflicts => "Conflicts" }
    }
    pub(crate) fn keeps(self, c: Three) -> bool {
        match self {
            ThreeFilter::All => true,
            ThreeFilter::AOnly => c == Three::AOnly,
            ThreeFilter::BOnly => c == Three::BOnly,
            ThreeFilter::Both => c == Three::Both,
            ThreeFilter::Conflicts => c == Three::Conflict,
        }
    }
}

/// What the minimap shows for one row of the compare matrix.
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum RowMark {
    Same,
    Differs,
    Edited,
    Conflict,
}

/// One compare row in each column shown (`App::row_info`): its value, whether the column stores the setting at
/// all, whether it is your edit; and the row's standing.
pub(crate) struct RowInfo {
    pub(crate) vals: Vec<Option<i64>>,
    pub(crate) stored: Vec<bool>,
    pub(crate) edited: Vec<bool>,
    /// A column after the first holds another value than the first.
    pub(crate) differs: bool,
    pub(crate) class: Option<Three>,
    pub(crate) mark: RowMark,
}

/// A row of the compare matrix: (tab, group, the linked settings that store it).
pub(crate) type Row = (String, String, Vec<Setting>);

/// What a list of compare rows was worked out from: the camera definition (its generation), the search in
/// lower case, the tab, Expert mode, and whether the rows are laid out as on the camera (which records a row holds,
/// `same_row`).
pub(crate) type RowsKey = (u64, String, Option<String>, bool, bool);

/// How many lists of compare rows are kept (the window's, and a few the web page asks for).
const ROWS_KEPT: usize = 4;

impl App {
    /// Columns kept to the `n` sections a file holds, without doubles.
    pub(crate) fn fit_cols(&mut self, n: usize) {
        for col in &mut self.cols { col.section = col.section.min(n.saturating_sub(1)); }
        let mut seen: Vec<Col> = Vec::new();
        self.cols.retain(|c| if seen.contains(c) { false } else { seen.push(*c); true });
    }

    /// Swap files A and B, both opened again from this computer (the window's Swap A/B and the page's): only when A
    /// has no edits left and both can still be read, so A and B never end up the same file. Err says why not.
    pub(crate) fn swap_ab(&mut self) -> Result<(), String> {
        let Some(b) = self.compare.as_ref().map(|(p, _)| p.clone()) else { return Err("Open file B first.".into()) };
        let Some(d) = &self.doc else { return Err("No file is open.".into()) };
        if d.unsaved() > 0 {
            return Err("Save or revert the edits first: swapping opens both files again.".into());
        }
        let a = d.path.clone();
        if d.source == Source::Sample || self.load(&a).is_err() {
            return Err("File A is not a file on this computer (the built-in sample, or a file moved or deleted since), so it cannot become file B.".into());
        }
        if let Err(e) = self.load(&b) {
            return Err(format!("File B cannot be read again: {e}"));
        }
        self.open(b);
        self.open_compare(a);
        Ok(())
    }

    pub(crate) fn open_compare(&mut self, path: PathBuf) {
        match self.load(&path) {
            Ok(c) => {
                self.status = format!("Comparing with {} (saved {})", path.display(), self.stamp_words(&c.timestamp()));
                self.prefs.remember(&path);
                self.compare = Some((path, c));
                // long-form compare: this file against the other, same section, differences only
                self.cols = vec![Col::a(self.target), Col::b(self.target)];
                if self.base.is_some() {
                    self.cols.insert(0, Col::base(self.target));
                }
                self.matrix_only_diff = self.prefs.matrix_only_diff;
                self.mode = Mode::Compare;
                self.diff_cursor = None;
                self.remember_session();
            }
            Err(e) => self.status = e,
        }
    }

    /// Three-way compare: open the file A and B both started from. It becomes the baseline column.
    pub(crate) fn open_base(&mut self, path: PathBuf) {
        match self.load(&path) {
            Ok(c) => {
                self.status = format!("Three-way compare against base {} (saved {})", path.display(), self.stamp_words(&c.timestamp()));
                self.prefs.remember(&path);
                self.base = Some((path, c));
                self.cols.retain(|c| c.src != Src::Base);
                let section = self.cols.first().map(|c| c.section).unwrap_or(self.target);
                self.cols.insert(0, Col::base(section));
                if !self.cols.iter().any(|c| c.src == Src::A) { self.cols.push(Col::a(section)); }
                if self.compare.is_some() && !self.cols.iter().any(|c| c.src == Src::B) { self.cols.push(Col::b(section)); }
                self.matrix_only_diff = self.prefs.matrix_only_diff;
                self.mode = Mode::Compare;
                self.compare_records = false;
                self.diff_cursor = None;
                self.remember_session();
            }
            Err(e) => self.status = e,
        }
    }

    pub(crate) fn close_base(&mut self) {
        self.base = None;
        self.cols.retain(|c| c.src != Src::Base);
        self.three_filter = ThreeFilter::All;
        self.remember_session();
    }

    /// The settings file behind a column's source, if that file is open.
    pub(crate) fn set_for(&self, src: Src) -> Option<&CamSet> {
        match src {
            Src::A => self.doc.as_ref().map(|d| &d.edited),
            Src::B => self.compare.as_ref().map(|(_, c)| c),
            Src::Base => self.base.as_ref().map(|(_, c)| c),
        }
    }

    pub(crate) fn file_name_of(&self, src: Src) -> String {
        let p = match src {
            Src::A => self.doc.as_ref().map(|d| d.path.clone()),
            Src::B => self.compare.as_ref().map(|(p, _)| p.clone()),
            Src::Base => self.base.as_ref().map(|(p, _)| p.clone()),
        };
        p.map(|p| p.file_name().unwrap_or_default().to_string_lossy().to_string()).unwrap_or_default()
    }

    /// Drop columns whose file is not open any more.
    pub(crate) fn prune_cols(&mut self) {
        let (b, base) = (self.compare.is_some(), self.base.is_some());
        self.cols.retain(|c| match c.src { Src::A => true, Src::B => b, Src::Base => base });
    }

    /// Three-way standing of a row, when a Base, an A and a B column are all shown.
    pub(crate) fn three_cols(&self) -> Option<(Col, Col, Col)> {
        self.base.as_ref()?;
        let find = |src: Src| self.cols.iter().copied().find(|c| c.src == src);
        Some((find(Src::Base)?, find(Src::A)?, find(Src::B)?))
    }

    pub(crate) fn three_way(&self, cols: (Col, Col, Col), s: &Setting) -> Three {
        let (base, a, b) = cols;
        let (vb, va, vbb) = (self.col_value(base, s), self.col_value(a, s), self.col_value(b, s));
        match (va == vb, vbb == vb, va == vbb) {
            (true, true, _) => Three::Same,
            (false, true, _) => Three::AOnly,
            (true, false, _) => Three::BOnly,
            (false, false, true) => Three::Both,
            (false, false, false) => Three::Conflict,
        }
    }

    /// The columns Compare starts with for the open file, as the definition and the preferences say.
    pub(crate) fn start_cols(&self) -> Vec<Col> {
        let n = self.doc.as_ref().map_or(usize::MAX, |d| d.edited.sections.len());
        let v: Vec<Col> = self.schema.camera.start_columns(self.prefs.all_memory_cols).into_iter().filter(|&s| s < n).map(Col::a).collect();
        if v.is_empty() { vec![Col::a(0)] } else { v }
    }

    /// Whether the compare columns carry their file's letter (A, B, Base): when file B or a base file is open.
    pub(crate) fn letters_in_use(&self) -> bool {
        self.compare.is_some() || self.base.is_some()
    }

    /// Compare's one line when the files open were saved under different video systems (where their container block
    /// says where it is), in the window and the web page alike: which file was saved under which, and why their
    /// values may differ for that alone. None when they agree, or when fewer than two files say.
    pub(crate) fn video_systems_note(&self) -> Option<String> {
        let said: Vec<(Src, u8, String)> = [Src::A, Src::B, Src::Base].into_iter()
            .filter_map(|src| { let c = self.set_for(src)?; Some((src, c.video_system()?.0, video_words(c)?)) })
            .collect();
        if said.iter().all(|(_, v, _)| *v == said[0].1) {
            return None;
        }
        let each: Vec<String> = said.iter().map(|(src, _, w)| format!("{} on {w}", src.letter())).collect();
        Some(format!("These files were saved with the camera set to different video systems ({}). The two use different frame rates, so settings that depend on them can differ for that reason alone.", each.join(", ")))
    }

    /// A compare column's name: "A · Live", "A · Memory 1", "B · Live", "Base · Live"; the plain section
    /// name when file A is the only file open. The Compare bar says once which file each letter is.
    pub(crate) fn col_name(&self, c: Col) -> String {
        if c.src == Src::A && !self.letters_in_use() {
            return self.schema.camera.target_name(c.section);
        }
        let section = if c.section == 0 { self.schema.camera.short_name(0) } else { self.schema.camera.target_name(c.section) };
        format!("{} · {section}", c.src.letter())
    }

    /// A column's name with its file, for an export read away from the Compare bar: "A · Live (CAMSET01.DAT)".
    pub(crate) fn col_name_with_file(&self, c: Col) -> String {
        if self.letters_in_use() { format!("{} ({})", self.col_name(c), self.file_name_of(c.src)) } else { self.col_name(c) }
    }

    /// The arrows a row gets between two adjacent compare columns, as (into the left column, into the
    /// right one): only a column of file A takes a value, only while the file may be edited, and only
    /// where both columns store the setting and hold different values.
    pub(crate) fn arrows_between(&self, left: Col, right: Col, s: &Setting) -> (bool, bool) {
        if !self.editable() {
            return (false, false);
        }
        // a column takes no value of a setting that is view only in its set outside Expert mode (`locked_why`)
        let takes = |c: Col| c.editable() && !self.locked(s, c.section);
        match (self.col_value(left, s), self.col_value(right, s)) {
            (Some(l), Some(r)) if l != r => (takes(left), takes(right)),
            _ => (false, false),
        }
    }

    /// Value of a setting's record in a column; None when the column does not store it.
    pub(crate) fn col_value(&self, c: Col, s: &Setting) -> Option<i64> {
        if c.section != 0 && !s.in_sets {
            return None;
        }
        self.set_for(c.src)?.sections.get(c.section)?.get(s.id)?.get(s.index)
    }

    /// Text of a text setting (e.g. the file-name prefix) in a column.
    pub(crate) fn col_text(&self, c: Col, s: &Setting) -> Option<String> {
        self.set_for(c.src)?.sections.get(c.section)?.get(s.id)?.text()
    }

    /// What an edited value of file A was when the file was opened, in words (a text as it was), for the cell's hover.
    pub(crate) fn col_was(&self, c: Col, s: &Setting) -> String {
        let Some(doc) = &self.doc else { return String::new() };
        match &s.text {
            Some(_) => doc.original.sections.get(c.section).and_then(|sec| sec.get(s.id)).and_then(|r| r.text()).unwrap_or_default(),
            None => Self::describe(s, doc.original_value(c.section, s.slot())),
        }
    }

    /// Whether a compare cell takes a value in place (Compare's picker, `compare_picker`, and the page's): a column of
    /// file A that keeps the setting, in a file open for editing, every record of the row in the shape it was mapped
    /// in, and a value that can change (a text, a number with a range, or two named values or more), as the detail
    /// panel allows it. File B and the base never do.
    pub(crate) fn cell_editable(&self, c: Col, linked: &[Setting]) -> bool {
        let Some(s) = linked.first() else { return false };
        if !c.editable() || !self.editable() || !(c.section == 0 || s.in_sets) || c.section >= self.n_sections() || !linked.iter().all(|l| self.shape_ok_in(l, c.section)) {
            return false;
        }
        // view only in that set outside Expert mode (a copy, or a setting no menu writes: `locked_why`)
        if self.locked(s, c.section) {
            return false;
        }
        let Some(doc) = &self.doc else { return false };
        if s.text.is_some() {
            return doc.edited.sections.get(c.section).and_then(|sec| sec.get(s.id)).is_some();
        }
        s.scalar && doc.value(c.section, s.slot()).is_some() && (s.range.is_some() || s.values.len() >= 2)
    }

    /// Where a value can be copied: the columns of file A the compare shows, in the order shown,
    /// that store the setting and that the file holds, never the cell it comes from, nor a set where the setting is view
    /// only outside Expert mode (`locked_why`).
    pub(crate) fn copy_targets(&self, from: Col, s: &Setting) -> Vec<Col> {
        self.cols.iter().copied()
            .filter(|c| c.editable() && *c != from && (c.section == 0 || s.in_sets) && c.section < self.n_sections() && !self.locked(s, c.section))
            .collect()
    }

    /// Actions that copy one row (every linked record) from column `from` into `to`. A row that either file holds
    /// in another shape than the setting was mapped in (another firmware, under "Edit anyway") is left alone, as
    /// the single-setting editors leave it: its values would be read and written by element or byte offset in a
    /// layout the mapping was not made on. Such rows are counted in `copy_skipped`, which `apply` reports. Of the
    /// records that differ, one view only outside Expert mode (`locked_why`: a setting no menu of the camera writes)
    /// is left alone, and so is a value the menus offer under another video system than file A was saved under
    /// (`Setting::other_system`); a row so left, whole or in part, is counted too, by why. A copy the camera keeps of
    /// another setting (`copy_of`) is changed as an edit changes it (`apply`): in step with its setting, it takes that
    /// setting and the copies in step with it along, as its row says (`copy_note`); a copy of several rows at once keeps
    /// each row's own value (`pin_families`).
    pub(crate) fn copy_row(&self, linked: &[Setting], from: Col, to: Col) -> Vec<Action> {
        let pairs: Vec<(&Setting, i64, i64)> = linked.iter().filter_map(|l| Some((l, self.col_value(from, l)?, self.col_value(to, l)?))).collect();
        if pairs.iter().all(|(_, v, cur)| v == cur) {
            return Vec::new();
        }
        let mut left = self.copy_skipped.get();
        let src = self.set_for(from.src);
        let shaped = pairs.iter().all(|(l, _, _)| src.is_some_and(|c| shape_ok_for(c, from.section, l)) && self.shape_ok_in(l, to.section));
        if !shaped {
            left.shape += 1;
            self.copy_skipped.set(left);
            return Vec::new();
        }
        let sys = self.system_in(to.section);
        let (mut locked, mut other) = (false, false);
        let mut out = Vec::new();
        for (l, v, _) in pairs.into_iter().filter(|(_, v, cur)| v != cur) {
            if self.locked(l, to.section) {
                locked = true;
            } else if l.other_system(v, sys.as_deref()).is_some() {
                other = true;
            } else {
                out.push(Action::Set(to.section, l.slot(), v));
            }
        }
        left.locked += usize::from(locked);
        left.other_system += usize::from(other);
        self.copy_skipped.set(left);
        out
    }

    /// Settings as rows, grouped like the camera menu: (tab, group, linked records), for the
    /// window's search and tab filter (the views use `matrix_rows_shared`; the tests compare with it).
    #[cfg(test)]
    pub(crate) fn matrix_rows(&self) -> Vec<(String, String, Vec<Setting>)> {
        self.matrix_rows_for(&self.search, self.compare_tab.as_deref())
    }

    /// The compare matrix's rows for a search `q` (empty: every setting) and a tab (None: every
    /// tab), so a view other than the window's (the web page) gets them for its own filters.
    pub(crate) fn matrix_rows_for(&self, q: &str, tab: Option<&str>) -> Vec<(String, String, Vec<Setting>)> {
        (*self.matrix_rows_shared(q, tab)).clone()
    }

    /// The compare matrix's rows (`matrix_rows_for`) without a copy: kept for the definition, search, tab and
    /// Expert mode they were worked out for, so a frame does not work them out again.
    pub(crate) fn matrix_rows_shared(&self, q: &str, tab: Option<&str>) -> std::rc::Rc<Vec<Row>> {
        let key: RowsKey = (self.schema_gen, q.to_lowercase(), tab.map(str::to_string), self.prefs.expert, self.camera_layout());
        if let Some((_, rows)) = self.rows_cache.borrow().iter().find(|(k, _)| *k == key) {
            return rows.clone();
        }
        let rows = std::rc::Rc::new(self.build_matrix_rows(&key.1, tab));
        let mut cache = self.rows_cache.borrow_mut();
        if cache.len() >= ROWS_KEPT { cache.remove(0); }
        cache.push((key, rows.clone()));
        rows
    }

    /// Work out the compare matrix's rows: the live settings matching `q` (lower case) in `tab`, in menu order, one row
    /// per setting as the Edit page has it (`same_row`): the records the editor writes together are one row, whole
    /// whatever the search or the tab leaves out, so a copy takes them all, as Edit's and the page's changes do; each
    /// Picture Profile's parameter is a row of its own under its profile's group, and a copy the camera keeps of a
    /// setting is never in that setting's row. Each group kept together where it first appears.
    pub(crate) fn build_matrix_rows(&self, q: &str, tab: Option<&str>) -> Vec<Row> {
        let tab_idx: std::collections::HashMap<&str, usize> = self.schema.tabs.iter().enumerate().map(|(i, t)| (t.as_str(), i)).collect();
        let tab_idx = |t: &str| tab_idx.get(t).copied().unwrap_or(99);
        let shown = |s: &&Setting| s.area == "global" && (self.prefs.expert || !Self::expert_only(s));
        let mut list: Vec<&Setting> = self.schema.settings.iter().filter(shown)
            .filter(|s| q.is_empty() || Self::matches_query(s, q))
            .filter(|s| tab.is_none_or(|t| s.tab == t))
            .collect();
        let at = self.menu_at();
        list.sort_by_key(|s| (tab_idx(&s.tab), at(s)));
        // the settings of each name, where a setting's row partners are looked for
        let mut by_name: std::collections::HashMap<&str, Vec<&Setting>> = Default::default();
        for s in self.schema.settings.iter().filter(shown) {
            by_name.entry(s.name.as_str()).or_default().push(s);
        }
        let mut seen: std::collections::HashSet<&str> = Default::default();
        let mut rows: Vec<Row> = Vec::new();
        for s in list {
            if seen.contains(s.key.as_str()) {
                continue;
            }
            let mut linked: Vec<Setting> = vec![s.clone()];
            seen.insert(s.key.as_str());
            for o in by_name.get(s.name.as_str()).into_iter().flatten() {
                if !seen.contains(o.key.as_str()) && self.same_row(s, o) {
                    seen.insert(o.key.as_str());
                    linked.push((*o).clone());
                }
            }
            rows.push((s.tab.clone(), s.group.clone(), linked));
        }
        // keep each group together, in the order its first setting appears
        let mut first: std::collections::HashMap<(String, String), usize> = Default::default();
        for (i, r) in rows.iter().enumerate() { first.entry((r.0.clone(), r.1.clone())).or_insert(i); }
        let mut keyed: Vec<((usize, usize), Row)> = rows.into_iter().map(|r| ((tab_idx(&r.0), first[&(r.0.clone(), r.1.clone())]), r)).collect();
        keyed.sort_by_key(|(k, _)| *k);
        keyed.into_iter().map(|(_, r)| r).collect()
    }

    /// Compare's "Open in Edit": Edit on the setting `s` in `section` of file A (the live settings when that section
    /// does not keep it), its menu opened as the search's results open one (tab, the group as Edit shows it, a family
    /// by its title, and the setting), with "← Back to Compare" to the row it came from. Only edited is turned off when
    /// it would hide the setting.
    pub(crate) fn open_in_edit_from_compare(&mut self, s: &Setting, section: usize) {
        let group = self.shown_group_of(s);          // as Edit shows it, in the layout in use
        self.mode = Mode::Edit;
        self.target = if section == 0 || s.in_sets { section } else { 0 };
        self.view = self.view_of(s);          // the page that shows it: its tab's, My Menu's own, Other for a tab the definition does not list, or the entry for what the menus do not hold
        self.group = Some(group);
        self.item = Some(s.name.clone());
        self.item_key = Some(s.key.clone());          // of two rows of one name, this one (`pick_row`)
        self.focus = Focus::Items;
        if self.only_changed && !self.changed(s) {
            self.only_changed = false;
        }
        self.from_compare = Some(FromCompare { view: self.view.clone(), group: self.group.clone(), item: self.item.clone(), target: self.target, row: (s.tab.clone(), s.key.clone()) });
        self.status = format!("{} opened in Edit, in {}. ← Back to Compare returns to its row.", s.name, self.schema.camera.target_name(self.target));
    }

    /// "← Back to Compare": Compare again, the row the setting was opened from under the difference cursor and in view.
    pub(crate) fn back_to_compare(&mut self) {
        if let Some(f) = self.from_compare.take() {
            self.mode = Mode::Compare;
            self.compare_row_to = Some(f.row);
        }
    }

    /// One compare row's values in each column, worked out once a frame: whether each column stores the setting,
    /// which hold your edits, whether it differs from the first column, its three-way standing and its change-map mark.
    pub(crate) fn row_info(&self, cols: &[Col], three: Option<(Col, Col, Col)>, s: &Setting) -> RowInfo {
        let vals: Vec<Option<i64>> = cols.iter().map(|c| self.col_value(*c, s)).collect();
        let stored: Vec<bool> = cols.iter().map(|c| c.section == 0 || s.in_sets).collect();
        let edited: Vec<bool> = cols.iter().zip(&vals).zip(&stored)
            .map(|((c, v), st)| *st && c.editable() && self.doc.as_ref().is_some_and(|d| d.original_value(c.section, s.slot()) != *v))
            .collect();
        let differs = (1..cols.len()).any(|i| stored[i] && vals[i] != vals[0]);
        let class = three.map(|tc| self.three_way(tc, s));
        let mark = if edited.iter().any(|e| *e) { RowMark::Edited }
            else if class == Some(Three::Conflict) { RowMark::Conflict }
            else if differs { RowMark::Differs }
            else { RowMark::Same };
        RowInfo { vals, stored, edited, differs, class, mark }
    }
}

#[cfg(test)]
pub(crate) mod copy_tests {
    use super::*;

    /// Copying a memory's value into Live (and Live into every memory) really changes file A.
    #[test]
    fn copy_between_live_and_memories() {
        // a file this layout's bodies wrote, from private/ when it is there (its header naming the definition's model,
        // firmware and layout), else the built-in sample
        let sample = crate::test_support::private_files(|c, def| c.checksums_ok() && def.camera.knows(c) && def.layout(&c.layout_signature()).is_some())
            .into_iter().next()
            .unwrap_or_else(|| std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.DAT"));
        let mut app = App::new(vec![], Prefs::default());
        app.open(sample);
        assert!(app.editable(), "sample must be editable");
        let dial = app.dial_sets();
        assert!(!dial.is_empty());
        // a setting stored in the memories whose Memory 1 value differs from Live
        let s = app.schema.settings.iter().filter(|s| s.in_sets && s.scalar && s.area == "global")
            .find(|s| { let l = app.col_value(Col::a(0), s); let m = app.col_value(Col::a(dial[0]), s); l.is_some() && m.is_some() && l != m })
            .cloned().expect("a setting that differs between Live and Memory 1");
        let want = app.col_value(Col::a(dial[0]), &s);
        let acts = app.copy_row(std::slice::from_ref(&s), Col::a(dial[0]), Col::a(0));
        assert!(!acts.is_empty());
        app.apply(acts);
        assert_eq!(app.col_value(Col::a(0), &s), want, "{} not copied into Live", s.name);
        // with Live and every memory shown, Live copies into all the memories
        app.cols = std::iter::once(0).chain(dial.iter().copied()).map(Col::a).collect();
        let targets = app.copy_targets(Col::a(0), &s);
        assert_eq!(targets, dial.iter().map(|d| Col::a(*d)).collect::<Vec<_>>());
        let mut acts = Vec::new();
        for t in &targets { acts.extend(app.copy_row(std::slice::from_ref(&s), Col::a(0), *t)); }
        app.apply(acts);
        for d in &dial { assert_eq!(app.col_value(Col::a(*d), &s), want, "{} not copied into section {d}", s.name); }
        // a live-only setting offers Live alone
        if let Some(lo) = app.schema.settings.iter().find(|s| !s.in_sets && s.area == "global").cloned() {
            assert_eq!(app.copy_targets(Col::a(dial[0]), &lo), vec![Col::a(0)]);
        }
    }

    /// Compare shows one row per setting as the Edit page has it (`same_row`): the records the editor writes together are
    /// one row, and a parameter of a family (each Picture Profile's Black Level) is a row of its own under its own group,
    /// which names the profile, so copying it from file B changes that one only; what the window's and the page's
    /// summaries count are those rows.
    #[test]
    fn compare_rows_are_one_per_setting() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let rows = app.matrix_rows_for("", None);
        assert!(rows.iter().all(|r| r.2.iter().all(|s| app.same_row(&r.2[0], s))), "a row holds linked records only");
        let keys: Vec<&str> = rows.iter().flat_map(|r| r.2.iter().map(|s| s.key.as_str())).collect();
        let unique: std::collections::HashSet<&str> = keys.iter().copied().collect();
        assert_eq!(keys.len(), unique.len(), "each setting once");
        for r in &rows {
            let linked = app.web_linked(0, &r.2[0].key).unwrap();
            let mut a: Vec<&str> = linked.iter().map(|s| s.key.as_str()).collect();
            let mut b: Vec<&str> = r.2.iter().map(|s| s.key.as_str()).collect();
            a.sort_unstable();
            b.sort_unstable();
            assert_eq!(a, b, "Compare's row holds what the Edit page and the page link, for {}", r.2[0].name);
        }
        // two settings of one name in two groups of a family: rows of their own, each under its own group
        let fam = app.schema.camera.families.iter().find(|f| !f.prefix.is_empty()).cloned().expect("a family");
        let (one, two) = rows.iter().filter(|r| r.1.starts_with(&fam.prefix) && r.2[0].scalar && app.locked_why(&r.2[0], 0).is_none() && app.shape_ok_in(&r.2[0], 0))
            .find_map(|r| rows.iter().find(|o| o.2[0].name == r.2[0].name && o.1 != r.1 && o.2[0].scalar && app.locked_why(&o.2[0], 0).is_none()).map(|o| (r.clone(), o.clone())))
            .expect("one parameter in two profiles");
        assert!(one.1 != two.1 && one.2[0].key != two.2[0].key);
        // file B holds other values in both; copying the first row changes that profile alone
        let pick = |s: &Setting, cur: i64| s.range.map(|(lo, hi)| if cur < hi { cur + s.step.unwrap_or(1).max(1) } else { lo })
            .or_else(|| s.values.iter().map(|(v, _)| *v).find(|v| *v != cur)).unwrap();
        let mut b = app.doc.as_ref().unwrap().original.clone();
        let (a1, a2) = (app.col_value(Col::a(0), &one.2[0]).unwrap(), app.col_value(Col::a(0), &two.2[0]).unwrap());
        let (b1, b2) = (pick(&one.2[0], a1), pick(&two.2[0], a2));
        b.sections[0].get_mut(one.2[0].id).unwrap().put(one.2[0].index, b1).unwrap();
        b.sections[0].get_mut(two.2[0].id).unwrap().put(two.2[0].index, b2).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        let acts = app.copy_row(&one.2, Col::b(0), Col::a(0));
        app.apply(acts);
        assert_eq!((app.col_value(Col::a(0), &one.2[0]), app.col_value(Col::a(0), &two.2[0])), (Some(b1), Some(a2)), "the other profile is left as it was");
        // the page counts the same rows
        let j: serde_json::Value = serde_json::from_slice(&crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["b", 0]], "only_diff": false })).body).unwrap();
        assert_eq!(j["total"], serde_json::json!(app.matrix_rows_for("", None).len()));
        assert_eq!(j["rows"].as_array().unwrap().len() as u64, j["shown"].as_u64().unwrap());
        assert!(j["rows"].as_array().unwrap().iter().filter(|r| r["key"] == serde_json::json!(one.2[0].key) || r["key"] == serde_json::json!(two.2[0].key)).count() == 2, "both rows on the page");
    }

    /// One setting the camera keeps in several records (the reviewer's case: Exposure Comp., three records the Edit page
    /// links and writes together) is one row in Compare and on the Memories page, and every way of changing it there
    /// changes all its records: the window's arrow and copy, the window's picker, the page's copy and its picker.
    #[test]
    fn records_written_together_are_copied_together() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let rows = app.matrix_rows_for("", None);
        let row = rows.iter().find(|r| r.2.len() >= 3 && r.2.iter().all(|s| s.scalar && s.values.len() >= 3 && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none()))
            .cloned().expect("a setting kept in three records");
        let linked = row.2.clone();
        assert_eq!(rows.iter().filter(|r| r.2.iter().any(|s| linked.iter().any(|l| l.key == s.key))).count(), 1, "one row for all its records");
        let label_of = |v: i64| linked[0].label_for(v).map(str::to_string);
        let cur = app.col_value(Col::a(0), &linked[0]).unwrap();
        let other = linked[0].values.iter().map(|(v, _)| *v).find(|v| *v != cur && linked[0].checked_on_camera(*v, 0)).expect("another value");
        // each record's own number for that value, as `set_linked` writes it
        let want: Vec<Option<i64>> = linked.iter().map(|l| l.values.iter().find(|(_, lab)| Some(lab.clone()) == label_of(other)).map(|(v, _)| *v)).collect();
        let held = |app: &App| linked.iter().map(|l| app.col_value(Col::a(0), l)).collect::<Vec<_>>();
        let mut b = app.doc.as_ref().unwrap().original.clone();
        for (l, v) in linked.iter().zip(&want) {
            b.sections[0].get_mut(l.id).unwrap().put(l.index, v.unwrap()).unwrap();
        }
        app.compare = Some((PathBuf::from("B.DAT"), b));
        // the window's arrow (a copy of the row)
        let acts = app.copy_row(&row.2, Col::b(0), Col::a(0));
        app.apply(acts);
        assert_eq!(held(&app), want, "the window's copy takes every record");
        assert!(app.write_issues().is_empty(), "as the camera writes it: nothing to list");
        app.undo();
        // the window's picker, as Compare's cell sets it
        app.apply(App::set_linked(0, &row.2, other));
        assert_eq!(held(&app), want, "the window's picker takes every record");
        app.undo();
        // the page's copy and its picker
        assert_eq!(crate::web::tests::answer(&mut app, "copy", serde_json::json!({ "from": ["b", 0], "to": ["a", 0], "key": linked[1].key })).status, 200);
        assert_eq!(held(&app), want, "the page's copy takes every record");
        app.undo();
        assert_eq!(crate::web::tests::answer(&mut app, "set", serde_json::json!({ "target": 0, "key": linked[1].key, "value": want[1], "col": ["a", 0] })).status, 200);
        assert_eq!(held(&app), want, "the page's picker takes every record");
        // the Memories page: one row, its arrow copies the records the memories keep together
        let mem = app.memory_rows();
        let kept: Vec<&Setting> = linked.iter().filter(|l| l.in_sets).collect();
        if !kept.is_empty() {
            assert_eq!(mem.iter().filter(|r| r.2.iter().any(|s| kept.iter().any(|k| k.key == s.key))).count(), 1, "one Memories row");
            let r = mem.iter().find(|r| r.2.iter().any(|s| s.key == kept[0].key)).unwrap();
            let m = app.dial_sets()[0];
            let acts = app.copy_row(&r.2, Col::a(0), Col::a(m));
            app.apply(acts);
            for k in &kept {
                assert_eq!(app.col_value(Col::a(m), k), app.col_value(Col::a(0), k), "{} copied with the others", k.key);
            }
        }
    }

    /// In a compare a value copies only into the columns of file A that are shown, in their order.
    #[test]
    fn copy_targets_are_the_shown_columns_of_file_a() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert!(app.n_sections() > 1, "the sample holds memories");
        let s = app.schema.settings.iter().find(|s| s.in_sets && s.area == "global").cloned()
            .expect("a setting stored in the memories");
        // file B's live settings beside file A's: a value in B goes into A's Live only
        app.cols = vec![Col::b(0), Col::a(0)];
        assert_eq!(app.copy_targets(Col::b(0), &s), vec![Col::a(0)]);
        // a value in A's Live has nowhere to go: file B is never edited
        app.cols = vec![Col::a(0), Col::b(0)];
        assert!(app.copy_targets(Col::a(0), &s).is_empty());
        // with A's Memory 1 shown too: two targets, in the order shown
        app.cols = vec![Col::b(0), Col::a(0), Col::a(1)];
        assert_eq!(app.copy_targets(Col::b(0), &s), vec![Col::a(0), Col::a(1)]);
        // a setting the memories do not store goes into Live only
        if let Some(lo) = app.schema.settings.iter().find(|s| !s.in_sets && s.area == "global").cloned() {
            assert_eq!(app.copy_targets(Col::b(0), &lo), vec![Col::a(0)]);
        }
    }

    /// Column names are short: the file's letter and the section, or the plain section with file A alone.
    #[test]
    fn column_names_are_short() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert_eq!(app.col_name(Col::a(0)), "Live settings");
        assert_eq!(app.col_name(Col::a(1)), "Memory 1");
        let other = app.doc.as_ref().unwrap().edited.clone();
        app.compare = Some((PathBuf::from("other.DAT"), other.clone()));
        assert_eq!(app.col_name(Col::a(0)), "A · Live");
        assert_eq!(app.col_name(Col::a(1)), "A · Memory 1");
        assert_eq!(app.col_name(Col::b(0)), "B · Live");
        app.base = Some((PathBuf::from("base.DAT"), other));
        assert_eq!(app.col_name(Col::base(0)), "Base · Live");
        // an export, read away from the Compare bar, names the file as well
        assert_eq!(app.col_name_with_file(Col::b(0)), "B · Live (other.DAT)");
    }

    /// The arrows between two columns point only into file A, and only where the values differ.
    #[test]
    fn arrows_point_into_file_a_where_values_differ() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert!(app.editable(), "the sample must be editable");
        let both = |app: &App, s: &Setting| app.col_value(Col::a(0), s).is_some() && app.col_value(Col::a(1), s).is_some();
        let kept = app.schema.settings.iter().find(|s| s.in_sets && s.area == "global" && s.scalar && both(&app, s))
            .cloned().expect("a setting kept in the memories");
        let live_only = app.schema.settings.iter().find(|s| !s.in_sets && s.area == "global" && app.col_value(Col::a(0), s).is_some())
            .cloned().expect("a live-only setting");
        // file B and the base: copies of the sample, so every value is equal at first
        let same = app.doc.as_ref().unwrap().edited.clone();
        app.compare = Some((PathBuf::from("other.DAT"), same.clone()));
        app.base = Some((PathBuf::from("base.DAT"), same.clone()));
        assert_eq!(app.arrows_between(Col::b(0), Col::a(0), &kept), (false, false));
        // a made-up value in B's live settings: the arrow points into A only
        let v = app.col_value(Col::a(0), &kept).unwrap();
        let mut other = same.clone();
        other.sections[0].get_mut(kept.id).unwrap().put(kept.index, v ^ 1).unwrap();
        app.compare = Some((PathBuf::from("other.DAT"), other));
        assert_eq!(app.arrows_between(Col::b(0), Col::a(0), &kept), (false, true));
        assert_eq!(app.arrows_between(Col::a(0), Col::b(0), &kept), (true, false));
        // B and the base differ too, but neither is ever changed
        assert_eq!(app.arrows_between(Col::b(0), Col::base(0), &kept), (false, false));
        // A's live settings beside its Memory 1: both take a value, unless the memories do not keep the setting
        let m = app.col_value(Col::a(1), &kept).unwrap();
        app.doc.as_mut().unwrap().edited.sections[1].get_mut(kept.id).unwrap().put(kept.index, if m == v { v ^ 1 } else { m }).unwrap();
        assert_eq!(app.arrows_between(Col::a(0), Col::a(1), &kept), (true, true));
        assert_eq!(app.arrows_between(Col::a(0), Col::a(1), &live_only), (false, false));
    }

    #[test]
    fn mirror_sync_between_0x0180_and_0x018c() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert!(app.doc.is_some());
        // Edit set:0x0180 in memory set 1 (section 1) at offset 288
        let test_val = 280; // f/2.8
        app.apply(vec![Action::Set(1, (0x0180, Some(camset::FIELD | 288)), test_val)]);
        let doc = app.doc.as_ref().unwrap();
        let r_live = doc.edited.sections[0].get(0x018c).unwrap();
        assert_eq!(r_live.get(Some(camset::FIELD | 288)), Some(test_val));

        // Now edit global:0x018c in section 0 at offset 288 to something else
        let test_val2 = 400; // f/4.0
        app.apply(vec![Action::Set(0, (0x018c, Some(camset::FIELD | 288)), test_val2)]);
        let doc = app.doc.as_ref().unwrap();
        let r_set = doc.edited.sections[1].get(0x0180).unwrap();
        assert_eq!(r_set.get(Some(camset::FIELD | 288)), Some(test_val2));

        // Also test memory set 2 (section 2) at offset 288 -> live offset 320 + 288 = 608
        let test_val3 = 560; // f/5.6
        app.apply(vec![Action::Set(2, (0x0180, Some(camset::FIELD | 288)), test_val3)]);
        let doc = app.doc.as_ref().unwrap();
        let r_live = doc.edited.sections[0].get(0x018c).unwrap();
        assert_eq!(r_live.get(Some(camset::FIELD | 608)), Some(test_val3));

        let test_val4 = 800; // f/8.0
        app.apply(vec![Action::Set(0, (0x018c, Some(camset::FIELD | 608)), test_val4)]);
        let doc = app.doc.as_ref().unwrap();
        let r_set = doc.edited.sections[2].get(0x0180).unwrap();
        assert_eq!(r_set.get(Some(camset::FIELD | 288)), Some(test_val4));
        // the copy is the definition's (camera.mirrors), not the program's
        let m = &app.schema.camera.mirrors[0];
        assert_eq!((m.live_record, m.set_record, m.element_bytes, m.first_section), (0x018c, 0x0180, Some(320), 1));
    }

    /// A whole record put back or replaced is copied too: Revert of every edit (the record as opened) and a record
    /// replaced whole (the History's Revert).
    #[test]
    fn mirror_follows_whole_records() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let field = |app: &App, sec: usize, id: u16, at: u16| app.doc.as_ref().unwrap().edited.sections[sec].get(id).unwrap().get(Some(camset::FIELD | at));
        let was = field(&app, 1, 0x0180, 288);
        app.apply(vec![Action::Set(1, (0x0180, Some(camset::FIELD | 288)), 280)]);
        assert_eq!(field(&app, 0, 0x018c, 288), Some(280));
        // Revert of the whole record: the live copy goes back too
        app.apply(vec![Action::Revert(1, (0x0180, None))]);
        assert_eq!((field(&app, 1, 0x0180, 288), field(&app, 0, 0x018c, 288)), (was, was));
        // a live record replaced whole: every memory set's copy follows
        let mut live = app.doc.as_ref().unwrap().edited.sections[0].get(0x018c).unwrap().clone();
        live.value[2 * 320 + 288..2 * 320 + 290].copy_from_slice(&560u16.to_le_bytes());
        app.apply(vec![Action::SetRecord(0, live)]);
        assert_eq!(field(&app, 3, 0x0180, 288), Some(560));
    }

    /// A file whose live record is not one element per memory set of the definition's size: nothing is copied, and
    /// the status line says so when it opens.
    #[test]
    fn mirror_off_for_another_shape() {
        let dir = crate::definitions::definitions_tests::scratch("mirror_shape");
        let mut c = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        let r = c.sections[0].get_mut(0x018c).unwrap();
        r.count = 11;
        r.value.truncate(11 * 320);
        let f = dir.join("CAMSET01.DAT");
        std::fs::write(&f, c.to_bytes()).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        app.open(f);
        assert!(app.status.contains("is not kept in step with its copy for this file"), "{}", app.status);
        let live = app.doc.as_ref().unwrap().edited.sections[0].get(0x018c).unwrap().clone();
        app.doc.as_mut().unwrap().unchecked_ok = true;
        app.apply(vec![Action::Set(1, (0x0180, Some(camset::FIELD | 288)), 280)]);
        assert_eq!(app.doc.as_ref().unwrap().edited.sections[0].get(0x018c).unwrap(), &live, "nothing copied");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
