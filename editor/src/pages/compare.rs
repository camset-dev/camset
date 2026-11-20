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
/// Compare row it came from (the Menu entry or tab it is under, setting key). Edit offers "← Back to Compare" while it
/// still shows that setting.
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
    /// The row's baseline: the first column that keeps its setting (the first column, but for a setting only the
    /// memories keep with the live settings first, which hold none of it). None where no column keeps it.
    pub(crate) base: Option<usize>,
    /// A column after the baseline that keeps the setting holds another value than the baseline.
    pub(crate) differs: bool,
    pub(crate) class: Option<Three>,
    pub(crate) mark: RowMark,
}

impl RowInfo {
    /// Whether column `i` keeps the setting and holds another value than the row's baseline (`base`).
    pub(crate) fn differs_at(&self, i: usize) -> bool {
        self.stored[i] && self.base.is_some_and(|b| b != i && self.vals[i] != self.vals[b])
    }
}

/// A row of the compare matrix: (the Menu entry or tab it is under, group, the linked settings that store it).
pub(crate) type Row = (String, String, Vec<Setting>);

/// What a list of compare rows was worked out from: the camera definition (its generation), the search in
/// lower case, the camera's menu (None: as before menus), the Menu entry, Expert mode, whether the rows are laid out as
/// on the camera (which records a row holds, `same_row`), and whether they hold the records a Main tile shows that the
/// live settings' rows leave out (`tile_records`: Compare's do, `matrix_rows_for`'s do not), and under a search what
/// they depend on in the files (`rows_files_key`), and whether they hold the settings only the memories keep
/// (`lists_memory_settings`).
pub(crate) type RowsKey = (u64, String, Option<String>, BarKey, bool, bool, bool, Vec<i64>, bool);

/// How many lists of compare rows are kept: every entry of the Menu in the menu shown, each menu's whole list for its
/// button's count, and a few the web page asks for.
const ROWS_KEPT: usize = 48;

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

    /// Why file `c` cannot be compared with file A, as file B or as the base (`what` names it): Compare reads it with
    /// file A's definition, record by record, and copies its values into A, so it must be from the same camera model,
    /// where another model's names mean nothing. One of another firmware of that model is compared, with a line saying
    /// what that means (`firmware_note`). What it is and why, in plain words; None when it may be compared, or no file
    /// A is open.
    pub(crate) fn compare_refusal(&self, c: &CamSet, what: &str) -> Option<String> {
        let a = &self.doc.as_ref()?.edited;
        (c.model() != a.model()).then(|| format!("Not compared: {what} is from a {} (firmware {}) and file A from a {}. The editor compares files of one camera model only: it reads both with file A's camera definition, and another model keeps other settings in the same places.", c.model(), c.firmware(), a.model()))
    }

    /// The line Compare shows, window and page, while file B or the base is from the same camera as file A but keeps
    /// its settings as another firmware does (another `CamSet::layout_signature`): which firmware, and what that means,
    /// in the words the Edit anyway window uses (a firmware update can move settings; the settings that sit where the
    /// editor expects them). It is compared, and copies take only those settings (`copy_row` leaves the others alone).
    /// None when every file open is laid out as file A.
    pub(crate) fn firmware_note(&self) -> Option<String> {
        let d = self.doc.as_ref()?;
        let a = &d.edited;
        let mut who = Vec::new();
        for (src, name) in [(Src::B, "File B"), (Src::Base, "The base file")] {
            let Some(c) = self.set_for(src).filter(|c| c.model() == a.model() && c.layout_signature() != d.signature) else { continue };
            who.push(if c.firmware() != a.firmware() {
                format!("{name} is from firmware {} of this camera, file A from firmware {}.", c.firmware(), a.firmware())
            } else {
                format!("{name} keeps its settings in other places than file A, though both say firmware {}.", a.firmware())
            });
        }
        (!who.is_empty()).then(|| format!("{} A firmware update can move settings: the editor reads both files the way file A's firmware keeps them, so a setting the other firmware keeps elsewhere can show a wrong value here, and only the settings that sit where the editor expects them in both files are copied into A.", who.join(" ")))
    }

    /// After file A changed (another file opened or read, the sample, a recovery): file B and the base close where they
    /// are of another model (`compare_refusal`), and the status says why; one of another firmware stays, and the status
    /// says what that means (`firmware_note`), as Compare's line does.
    pub(crate) fn close_unlike_compare(&mut self) {
        if let Some(why) = self.compare.as_ref().and_then(|(_, c)| self.compare_refusal(c, "file B")) {
            self.compare = None;
            self.status = format!("{} {why}", self.status).trim_start().to_string();
        }
        if let Some(why) = self.base.as_ref().and_then(|(_, c)| self.compare_refusal(c, "the base file")) {
            self.base = None;
            self.status = format!("{} {why}", self.status).trim_start().to_string();
        }
        if let Some(note) = self.firmware_note() {
            self.status = format!("{} {note}", self.status).trim_start().to_string();
        }
        self.prune_cols();
    }

    pub(crate) fn open_compare(&mut self, path: PathBuf) {
        match self.load(&path) {
            Ok(c) => {
                if let Some(why) = self.compare_refusal(&c, "file B") {
                    self.status = why;
                    return;
                }
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
                // another firmware of the same camera: what that means, as Compare's line says it
                if let Some(note) = self.firmware_note() {
                    self.status = format!("{}. {note}", self.status);
                }
                self.remember_session();
            }
            Err(e) => self.status = e,
        }
    }

    /// Three-way compare: open the file A and B both started from. It becomes the baseline column.
    pub(crate) fn open_base(&mut self, path: PathBuf) {
        match self.load(&path) {
            Ok(c) => {
                if let Some(why) = self.compare_refusal(&c, "the base file") {
                    self.status = why;
                    return;
                }
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
                if let Some(note) = self.firmware_note() {
                    self.status = format!("{}. {note}", self.status);
                }
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
        // a column takes no value of a setting that is view only in its set outside Expert mode (`locked_why`), nor of
        // one of My Menu's places, which its page changes (`place_why`), nor of a fraction's part whose other part the
        // two columns do not both keep (`copy_row`)
        let place = self.compare_why(s).is_some();
        let half = self.fraction_of(s).is_some_and(|(n, d, _)| [n, d].iter().any(|p| self.col_value(left, p).is_none() || self.col_value(right, p).is_none()));
        let takes = |c: Col| c.editable() && !self.locked(s, c.section) && !place && !half;
        match (self.col_value(left, s), self.col_value(right, s)) {
            (Some(l), Some(r)) if l != r => (takes(left), takes(right)),
            _ => (false, false),
        }
    }

    /// Value of a setting's record in a column; None when the column does not store it, nor where its set does not keep
    /// the setting (`kept_in`: a memory's own record in the live settings, a live one in a memory).
    pub(crate) fn col_value(&self, c: Col, s: &Setting) -> Option<i64> {
        if !kept_in(s, c.section) {
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
        if !c.editable() || !self.editable() || !kept_in(s, c.section) || c.section >= self.n_sections() || !linked.iter().all(|l| self.shape_ok_in(l, c.section)) {
            return false;
        }
        // view only in that set outside Expert mode (a copy, or a setting no menu writes: `locked_why`), or one of My
        // Menu's places, which its page changes (`place_why`)
        if self.locked(s, c.section) || self.compare_why(s).is_some() {
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
        if self.compare_why(s).is_some() {
            return Vec::new();
        }
        self.cols.iter().copied()
            .filter(|c| c.editable() && *c != from && kept_in(s, c.section) && c.section < self.n_sections() && !self.locked(s, c.section))
            .collect()
    }

    /// The two parts of the fraction tile `s` is one of (`TileKind::Fraction`: its `numerator_key` and `denominator_key`,
    /// the definition's settings) and the tile's label; None for any other setting. Taken from the definition's own
    /// tiles, never from a name.
    pub(crate) fn fraction_of(&self, s: &Setting) -> Option<(Setting, Setting, String)> {
        let key = &self.def_of(s).key;
        let sets = self.schema.camera.main_tiles.as_ref()?;
        sets.0.iter().flat_map(|set| &set.tiles).filter(|t| t.kind == TileKind::Fraction).find_map(|t| {
            let (n, d) = (t.numerator_key.as_ref()?, t.denominator_key.as_ref()?);
            if n != key && d != key {
                return None;
            }
            let find = |k: &String| self.index_of_key(k).map(|i| self.schema.settings[i].clone());
            Some((find(n)?, find(d)?, t.caption.clone()))
        })
    }

    /// What one is told before a copy of a fraction's part (`fraction_of`), where one presses (an arrow, a cell, a
    /// right-click), the window's and the page's: the two go together. None for any other setting, and where Compare
    /// copies neither (`compare_why`).
    pub(crate) fn fraction_words(&self, s: &Setting) -> Option<String> {
        if self.compare_why(s).is_some() {
            return None;
        }
        let (n, d, caption) = self.fraction_of(s)?;
        Some(format!("{} and {} are the two parts of {caption}: a copy takes both from the same column, in one step, or neither, so the value is always one a file held. Neither part takes a value of its own here.", n.name, d.name))
    }

    /// A copy over rows: the rows it goes over as shown (every record of each), so that a fraction's part whose other
    /// part is not among them is left, and counted (`copy_row`). Kept until the step is applied (`apply`).
    pub(crate) fn copying_over<'a>(&self, rows: impl IntoIterator<Item = &'a Row>) {
        *self.copy_shown.borrow_mut() = Some(rows.into_iter().flat_map(|r| r.2.iter().map(|s| self.def_of(s).key.clone())).collect());
    }

    /// A three-way merge over the rows Compare shows (`rows`), the window's buttons and the page's alike: each row whose
    /// standing among `cols` (base, A, B: `three_way`) is `want` takes column `take`'s values into A (`copy_row`, a
    /// fraction's two parts together: `copying_over`), each place of a family kept as the rows leave it
    /// (`pin_families`). The actions, and how many rows.
    pub(crate) fn merge_rows(&self, rows: &[Row], cols: (Col, Col, Col), want: Three, take: Col) -> (Vec<Action>, usize) {
        self.copying_over(rows);
        let (mut actions, mut n) = (Vec::new(), 0);
        for (_, _, linked) in rows {
            if self.three_way(cols, &linked[0]) == want {
                n += 1;
                actions.extend(self.copy_row(linked, take, cols.1));
            }
        }
        self.pin_families(None, cols.1.section, &mut actions);
        (actions, n)
    }

    /// Why Compare writes no value of `s` outside Expert mode, where a person would press, the window's and the page's:
    /// one of My Menu's places (`place_why`), or one of Expert mode's own records (`expert_why`). None where it may.
    pub(crate) fn compare_why(&self, s: &Setting) -> Option<String> {
        self.place_why(s).or_else(|| self.expert_why(s))
    }

    /// Why one of Expert mode's own records (`expert_only`) that Compare shows outside it (a fraction tile's parts:
    /// Edit's Main shows the tile and changes it nowhere, a tile of two settings not being edited in place) takes no
    /// value there. None for any other setting, and in Expert mode.
    pub(crate) fn expert_why(&self, s: &Setting) -> Option<String> {
        let d = self.def_of(s);
        if self.prefs.expert || !Self::expert_only(d) {
            return None;
        }
        Some(match self.fraction_of(d) {
            Some((n, den, caption)) => format!("{} and {}, the two parts of {caption}, are Expert mode's own records: Edit's Main page shows {caption} and changes it nowhere, so outside Expert mode Compare copies neither. Expert mode (⚙ Settings > Editing & Compare) copies the two together.", n.name, den.name),
            None => "This is Expert mode's own record: outside Expert mode it is shown, not changed. Expert mode (⚙ Settings > Editing & Compare) changes it.".to_string(),
        })
    }

    /// A compare cell's Revert in file A's set `section`, the window's: its words and its actions. Outside Expert mode a
    /// place of My Menu is never reverted alone (an item could then stand in two places): all of My Menu's places go
    /// back as the file was opened, in one step, a My Menu the camera itself wrote, and the words say so
    /// (`mymenu_revert_all`); any other row, its records.
    pub(crate) fn cell_revert(&self, linked: &[Setting], section: usize) -> (String, Vec<Action>) {
        if linked.first().is_some_and(|s| self.place_why(s).is_some()) {
            return self.mymenu_revert_all();
        }
        // a fraction's part: both parts back, in either mode (`revert_actions`), and the words say so
        if let Some((n, d, caption)) = linked.first().and_then(|s| self.fraction_of(s)) {
            return (format!("Revert {caption} ({} and {} together, as the file was opened)", n.name, d.name), self.revert_actions(linked, section));
        }
        ("Revert".into(), self.revert_actions(linked, section))
    }

    /// The Revert of a row of records in set `section`, the window's and the page's: each record of the row as the file
    /// was opened; a fraction tile's part with its other part (`fraction_of`), so no Revert leaves a pair of values no
    /// camera wrote.
    pub(crate) fn revert_actions(&self, linked: &[Setting], section: usize) -> Vec<Action> {
        let mut slots: Vec<Slot> = linked.iter().map(|l| l.slot()).collect();
        if let Some((n, d, _)) = linked.first().and_then(|s| self.fraction_of(s)) {
            slots.extend([n.slot(), d.slot()].into_iter().filter(|s| !linked.iter().any(|l| l.slot() == *s)));
        }
        slots.into_iter().map(|slot| Action::Revert(section, slot)).collect()
    }

    /// Why one of My Menu's places (`is_mymenu_place`) takes no value from Compare outside Expert mode, in the window
    /// and on the page alike: Compare writes a record at a time and would pass by every rule the My Menu page keeps for
    /// its items (`mymenu_set`: an item once, the pages packed, what the camera takes). None for any other setting, and
    /// in Expert mode, which changes it here as before.
    pub(crate) fn place_why(&self, s: &Setting) -> Option<String> {
        (!self.prefs.expert && self.is_mymenu_place(self.def_of(s))).then(|| format!("{} Open in Edit opens this place there.", self.places_rule()))
    }

    /// My Menu's places as its page shows them, page by page and place by place, those the search `q` (lower case,
    /// trimmed) finds by their name or the item they hold in the live settings (`place_found`): Compare's rows for them,
    /// each under My Menu, in a group per page named as the page heads it (`place_page`).
    pub(crate) fn place_rows(&self, q: &str) -> Vec<Row> {
        let Some(mm) = self.schema.camera.my_menu.as_ref() else { return Vec::new() };
        let mut places: Vec<&Setting> = self.schema.settings.iter().filter(|s| self.is_mymenu_place(s) && self.place_found(s, q)).collect();
        places.sort_by_key(|s| (mm.records.iter().position(|&r| r == s.id), s.index));
        let name = self.schema.camera.text.my_menu_name().to_string();
        places.into_iter().map(|s| (name.clone(), self.place_page(s), vec![s.clone()])).collect()
    }

    /// Whether the search `q` (lower case, trimmed) finds one of My Menu's places: by its name, or by the name of the item
    /// it holds in file A's live settings (never by every item it could hold).
    pub(crate) fn place_found(&self, s: &Setting, q: &str) -> bool {
        q.is_empty() || s.name.to_lowercase().contains(q) || self.place_codes_at(s).into_iter().filter_map(|c| s.label_for(c)).any(|l| l.to_lowercase().contains(q))
    }

    /// The items the open files hold at place `s` of My Menu (file A as edited, file B, the base), in that order.
    fn place_codes_at(&self, s: &Setting) -> Vec<i64> {
        let files = [self.doc.as_ref().map(|d| &d.edited), self.compare.as_ref().map(|(_, c)| c), self.base.as_ref().map(|(_, c)| c)];
        files.into_iter().flatten().filter_map(|c| c.sections.first()?.get(s.id)?.get(s.index)).collect()
    }

    /// What Compare's rows under the search `q` depend on in the files (`place_found`): the items every open file holds
    /// in My Menu's places, kept with the rows (`RowsKey`) so they are worked out again when one changes. Empty without
    /// a search, or without My Menu's page.
    fn rows_files_key(&self, q: &str) -> Vec<i64> {
        if q.trim().is_empty() || !self.has_mymenu_page() {
            return Vec::new();
        }
        self.schema.settings.iter().filter(|s| self.is_mymenu_place(s)).flat_map(|s| self.place_codes_at(s)).collect()
    }

    /// The page of My Menu a place is on, as its page heads it ("My Menu 2").
    pub(crate) fn place_page(&self, s: &Setting) -> String {
        let p = self.schema.camera.my_menu.as_ref().and_then(|m| m.records.iter().position(|&r| r == s.id)).unwrap_or(0);
        format!("{} {}", self.schema.camera.text.my_menu_name(), p + 1)
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
        // a fraction tile's part (`fraction_of`) goes with its other part, from the same column, in this same step, or not
        // at all: where one of the two is not kept in both columns, is view only there, has another shape, or is not
        // among the rows a copy over rows shows (`copying_over`), neither is written, and the row is counted as left
        let mut with_other: Vec<Setting>;
        let linked = match linked.first().filter(|l| self.compare_why(l).is_none()).and_then(|l| self.fraction_of(l)) {
            None => linked,
            Some((num, den, _)) => {
                let parts = [num, den];
                let held: Vec<(Option<i64>, Option<i64>)> = parts.iter().map(|p| (self.col_value(from, p), self.col_value(to, p))).collect();
                if held.iter().all(|(a, b)| a.is_none() || b.is_none()) || held.iter().all(|(a, b)| a == b) {
                    return Vec::new();
                }
                let src = self.set_for(from.src);
                let whole = held.iter().all(|(a, b)| a.is_some() && b.is_some())
                    && parts.iter().all(|p| !self.locked(p, to.section) && self.shape_ok_in(p, to.section) && src.is_some_and(|c| shape_ok_for(c, from.section, p)));
                let shown = self.copy_shown.borrow().as_ref().is_none_or(|keys| parts.iter().all(|p| keys.contains(&p.key)));
                if !whole || !shown {
                    let mut left = self.copy_skipped.get();
                    left.fraction += 1;
                    self.copy_skipped.set(left);
                    return Vec::new();
                }
                with_other = linked.to_vec();
                with_other.extend(parts.into_iter().filter(|p| !linked.iter().any(|l| l.key == p.key)));
                &with_other
            }
        };
        let pairs: Vec<(&Setting, i64, i64)> = linked.iter().filter_map(|l| Some((l, self.col_value(from, l)?, self.col_value(to, l)?))).collect();
        // every place this row leaves at the other column's value (`rows_set`): one holding it already, and one set to
        // it below; not one left alone (view only, another video system's, another shape)
        let covered = |places: &mut dyn Iterator<Item = Slot>| self.rows_set.borrow_mut().extend(places.map(|slot| (to.section, slot)));
        if pairs.iter().all(|(_, v, cur)| v == cur) {
            covered(&mut pairs.iter().map(|(l, _, _)| l.slot()));
            return Vec::new();
        }
        let mut left = self.copy_skipped.get();
        // one of My Menu's places, outside Expert mode: its page changes it, never a copy (`place_why`); one of Expert
        // mode's own records outside it (`expert_why`), changed nowhere outside Expert mode; each counted, and said
        if linked.iter().any(|l| self.place_why(l).is_some()) {
            left.places += 1;
            self.copy_skipped.set(left);
            return Vec::new();
        }
        if linked.iter().any(|l| self.expert_why(l).is_some()) {
            left.expert += 1;
            self.copy_skipped.set(left);
            return Vec::new();
        }
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
        covered(&mut pairs.iter().filter(|(_, v, cur)| v == cur).map(|(l, _, _)| l.slot()));
        for (l, v, _) in pairs.into_iter().filter(|(_, v, cur)| v != cur) {
            if self.locked(l, to.section) {
                locked = true;
            } else if l.other_system(v, sys.as_deref()).is_some() {
                other = true;
            } else {
                out.push(Action::Set(to.section, l.slot(), v));
                covered(&mut std::iter::once(l.slot()));
            }
        }
        left.locked += usize::from(locked);
        left.other_system += usize::from(other);
        self.copy_skipped.set(left);
        out
    }

    /// The window's Compare rows: those of its Menu entry (`compare_key`) in the camera's menu it shows
    /// (`compare_menu`), for its search (the view uses `compare_rows`; the tests compare with it).
    #[cfg(test)]
    pub(crate) fn matrix_rows(&self) -> Vec<(String, String, Vec<Setting>)> {
        (*self.compare_rows(self.compare_menu().as_deref(), &self.compare_key(), &self.search)).clone()
    }

    /// The compare rows as before menus (no camera menu) for a search `q` (empty: every setting) and a tab's entry of the
    /// Menu (None: All settings): what the Memories page, a recall, the page's copy and the tests build on, whatever
    /// menu the window shows.
    pub(crate) fn matrix_rows_for(&self, q: &str, tab: Option<&str>) -> Vec<(String, String, Vec<Setting>)> {
        (*self.matrix_rows_shared(q, tab)).clone()
    }

    /// `matrix_rows_for` without a copy (`compare_rows` with no camera menu, without the records a Main tile shows that
    /// the live settings' rows leave out).
    pub(crate) fn matrix_rows_shared(&self, q: &str, tab: Option<&str>) -> std::rc::Rc<Vec<Row>> {
        self.rows_with(None, &tab.filter(|t| !t.is_empty()).map_or(BarKey::All, |t| BarKey::Tab(t.to_string())), q, false, None)
    }

    /// The camera's menu Compare shows: the one the Menu shows (`menu_shown`), one choice for Edit and Compare; None
    /// without menus.
    pub(crate) fn compare_menu(&self) -> Option<String> {
        self.menu_shown()
    }

    /// The window's Compare entry of the Menu (`compare_entry`): a key, so a tab named as the Main page or My Menu is
    /// never taken for them.
    pub(crate) fn compare_key(&self) -> BarKey {
        self.compare_entry.clone()
    }

    /// Compare's rows of Menu entry `entry` in the camera's menu `menu`, for the search `q`: the one list the window
    /// draws, counts on its bar (`compare_bar`), exports and merges over, and the page answers with. In a menu (one of
    /// `menus`), as Edit shows that entry there (`entry_rows`): its groups and rows in the camera's layout and order in
    /// that menu, each row bound to the record for that menu, so files saved in different modes are compared like for
    /// like. Without one, as before menus: All settings is the rows Compare always had (`build_matrix_rows`), a tab,
    /// Other, the entry for what the menus do not hold or My Menu those of them Edit lists under it (its tab as laid
    /// out, `menu_entry_of`, or `off_menu`), under its name, so each row is under one entry; Main its tiles' settings
    /// (`entry_rows`). Every record a Main tile shows is All's too, under the entry that shows it (`tile_records`). Kept
    /// for what they were worked out for (`RowsKey`), so a frame does not work them out again.
    pub(crate) fn compare_rows(&self, menu: Option<&str>, entry: &BarKey, q: &str) -> std::rc::Rc<Vec<Row>> {
        self.compare_rows_in(menu, entry, q, &self.cols)
    }

    /// `compare_rows` for the columns `cols` (the page's own, a copy's, a merge's): with the settings only the memories
    /// keep where a memory of the menu is among them (`lists_memory_settings`), as Edit lists them for that memory.
    pub(crate) fn compare_rows_in(&self, menu: Option<&str>, entry: &BarKey, q: &str, cols: &[Col]) -> std::rc::Rc<Vec<Row>> {
        self.rows_with(menu, entry, q, true, self.memory_column(menu, cols))
    }

    /// Whether Compare lists the settings only the memories keep (`area` "set": a slot's focus frames, its stored
    /// exposure and mode): with a memory among the columns `cols`, in menu `menu` one Edit offers there (`menu_sets`: a
    /// memory of one of the menu's modes, any in Expert mode; without menus any memory). The live settings hold none of
    /// them, so with the live settings alone they are listed nowhere.
    pub(crate) fn lists_memory_settings(&self, menu: Option<&str>, cols: &[Col]) -> bool {
        self.memory_column(menu, cols).is_some()
    }

    /// The set of the first column that makes Compare list the settings only the memories keep (`lists_memory_settings`),
    /// whose rows Edit lists for them.
    fn memory_column(&self, menu: Option<&str>, cols: &[Col]) -> Option<usize> {
        let offered = menu.filter(|m| self.menu_named(m).is_some()).map(|m| self.menu_sets(Some(m)));
        cols.iter().map(|c| c.section).find(|&s| s != 0 && s < self.n_sections() && offered.as_ref().is_none_or(|o| o.contains(&s)))
    }

    /// Compare's line under a search that finds settings only the memories keep where no memory of the menu is a
    /// column (`lists_memory_settings`), so none is shown: how many, and what shows them. None otherwise.
    pub(crate) fn compare_memory_note(&self, menu: Option<&str>, q: &str, cols: &[Col]) -> Option<String> {
        let q = Self::query(q);
        if q.is_empty() || self.lists_memory_settings(menu, cols) {
            return None;
        }
        let menu = menu.filter(|m| self.menu_named(m).is_some());
        let n = self.schema.settings.iter()
            .filter(|s| s.area == "set" && (self.prefs.expert || !Self::expert_only(s)) && Self::matches_query(s, &q))
            .filter(|s| menu.is_none_or(|m| self.menus_of(s).iter().any(|x| x == m) || self.menus_of(s).is_empty()))
            .count();
        (n > 0).then(|| {
            let whose = if menu.is_some() { "a memory of this menu" } else { "a memory" };
            format!("{n} setting(s) that match are kept only in the memories: they are shown when {whose} is one of the columns.")
        })
    }

    /// `compare_rows`, with the records a Main tile shows that the live settings' rows leave out (`tiles`) or without
    /// them (`matrix_rows_for`: the Memories page and a recall compare the sets' own rows).
    fn rows_with(&self, menu: Option<&str>, entry: &BarKey, q: &str, tiles: bool, mem: Option<usize>) -> std::rc::Rc<Vec<Row>> {
        let menu = menu.filter(|m| self.menu_named(m).is_some());
        let key: RowsKey = (self.schema_gen, Self::query(q), menu.map(str::to_string), entry.clone(), self.prefs.expert, self.camera_layout(), tiles, self.rows_files_key(q), mem.is_some());
        if let Some((_, rows)) = self.rows_cache.borrow().iter().find(|(k, _)| *k == key) {
            return rows.clone();
        }
        let under = |s: &Setting, t: &str| self.entry_here(s) == t;
        let named = |t: String| -> Vec<Row> {
            self.rows_with(None, &BarKey::All, q, tiles, mem).iter().filter(|r| under(&r.2[0], &t)).map(|(_, g, linked)| (t.clone(), g.clone(), linked.clone())).collect()
        };
        let rows = match (menu, entry) {
            (Some(m), e) => self.entry_rows_in(Some(m), e, &key.1, mem),
            (None, BarKey::All) => {
                let mut rows = self.build_matrix_rows(&key.1, None, mem.is_some());
                // a tile's record that those rows hold already (a memory's, with a memory column) is not listed twice
                let held: std::collections::HashSet<String> = rows.iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect();
                // the records a Main tile shows that those rows leave out, each beside its group (`tile_records`)
                // (a memory's record only with a memory column: the live settings hold none of it)
                for s in self.tile_records(&key.1).into_iter().filter(|s| tiles && !held.contains(&s.key) && (mem.is_some() || s.area != "set")) {
                    let at = rows.iter().rposition(|r| r.0 == s.tab && r.1 == s.group).or_else(|| rows.iter().rposition(|r| r.0 == s.tab)).map_or(rows.len(), |i| i + 1);
                    rows.insert(at, (s.tab.clone(), s.group.clone(), vec![s]));
                }
                rows
            }
            (None, BarKey::Tab(t)) => named(t.clone()),
            (None, BarKey::MyMenu) => named(self.schema.camera.text.my_menu_name().to_string()),
            (None, BarKey::Main) => self.entry_rows_in(None, &BarKey::Main, &key.1, mem),
        };
        let rows = std::rc::Rc::new(rows);
        let mut cache = self.rows_cache.borrow_mut();
        if cache.len() >= ROWS_KEPT { cache.remove(0); }
        cache.push((key, rows.clone()));
        rows
    }

    /// A Compare row's title, the window's and the page's: its setting's (`setting_title`), and under Main the tile's
    /// label first where that title does not begin with it ("Slot 1: File Format (Slot 1)"; "Shutter speed: numerator"
    /// already does), so a row says what it is part of.
    pub(crate) fn compare_title(&self, row: &Row) -> String {
        let title = self.setting_title(&row.2[0]);
        if row.0 == self.schema.camera.text.main_title() && !title.to_lowercase().starts_with(&row.1.to_lowercase()) {
            format!("{}: {title}", row.1)
        } else {
            title
        }
    }

    /// Whether a row differs between the columns `cols` (the first the baseline): a later column that keeps the setting
    /// holds another value (`RowInfo::differs`).
    pub(crate) fn row_differs(&self, cols: &[Col], s: &Setting) -> bool {
        // the row's baseline is the first column that keeps the setting (`RowInfo::base`)
        let Some(at) = cols.iter().position(|c| kept_in(s, c.section)) else { return false };
        let b = self.col_value(cols[at], s);
        cols[at + 1..].iter().any(|c| kept_in(s, c.section) && self.col_value(*c, s) != b)
    }

    /// Compare's entries of the Menu in the camera's menu `menu`, for the search `q`, the window's and the page's
    /// alike: "All settings", then Main, My Menu, the tabs, Other and the entry for what the menus do not hold as Edit
    /// lists them (`bar_keys`), each with how many rows it lists (`compare_rows`) and as its badge how many of them
    /// differ (`differs`, given a row's leading record).
    pub(crate) fn compare_bar(&self, menu: Option<&str>, q: &str, differs: &dyn Fn(&Setting) -> bool) -> Vec<BarEntry> {
        self.compare_bar_in(menu, q, &self.cols, differs)
    }

    /// `compare_bar` for the columns `cols` (the page's), whose memories decide the rows (`compare_rows_in`).
    pub(crate) fn compare_bar_in(&self, menu: Option<&str>, q: &str, cols: &[Col], differs: &dyn Fn(&Setting) -> bool) -> Vec<BarEntry> {
        let menu = menu.filter(|m| self.menu_named(m).is_some());
        let off = self.schema.camera.text.off_menu_name();
        self.bar_keys(true, 0, menu, q, false).into_iter().map(|key| {
            let rows = self.compare_rows_in(menu, &key, q, cols);
            let (count, badge) = (Some(rows.len()), rows.iter().filter(|r| differs(&r.2[0])).count());
            let (label, color, hover) = match &key {
                BarKey::All => (ALL_SETTINGS.to_string(), None, None),
                BarKey::Main => (self.schema.camera.text.main_title().to_string(), None, None),
                BarKey::MyMenu => {
                    let name = self.schema.camera.text.my_menu_name();
                    (name.to_string(), Some(tab_color(&self.schema.camera, name)), None)
                }
                BarKey::Tab(t) => (t.clone(), Some(tab_color(&self.schema.camera, t)), (t == off).then(|| Self::off_menu_hover().to_string())),
            };
            BarEntry { key, label, color, hover, count, badge }
        }).collect()
    }

    /// How many rows differ in each of the camera's menus (`menus`, in their order), every setting it lists with the
    /// search `q` (`compare_rows` of All settings): the counts the menu buttons show in Compare.
    pub(crate) fn menu_differences(&self, q: &str, differs: &dyn Fn(&Setting) -> bool) -> Vec<usize> {
        self.menu_differences_in(q, &self.cols, differs)
    }

    /// `menu_differences` for the columns `cols` (the page's).
    pub(crate) fn menu_differences_in(&self, q: &str, cols: &[Col], differs: &dyn Fn(&Setting) -> bool) -> Vec<usize> {
        self.menus().iter().map(|m| self.compare_rows_in(Some(&m.name), &BarKey::All, q, cols).iter().filter(|r| differs(&r.2[0])).count()).collect()
    }

    /// Work out the compare matrix's rows as before menus: the live settings matching `q` (lower case) in `tab` (its own
    /// tab; None: every tab), in menu order, one row
    /// per setting as the Edit page has it (`same_row`): the records the editor writes together are one row, whole
    /// whatever the search or the tab leaves out, so a copy takes them all, as Edit's and the page's changes do; each
    /// Picture Profile's parameter is a row of its own under its profile's group, and a copy the camera keeps of a
    /// setting is never in that setting's row. Each group kept together where it first appears.
    /// With `mem`, the settings only the memories keep too (`lists_memory_settings`).
    pub(crate) fn build_matrix_rows(&self, q: &str, tab: Option<&str>, mem: bool) -> Vec<Row> {
        let tab_idx: std::collections::HashMap<&str, usize> = self.schema.tabs.iter().enumerate().map(|(i, t)| (t.as_str(), i)).collect();
        let tab_idx = |t: &str| tab_idx.get(t).copied().unwrap_or(99);
        // My Menu's places in Expert mode or out of it, as its page shows them, which a search finds as `place_rows` does;
        // the settings only the memories keep with a memory column (`mem`)
        let shown = |s: &&Setting| (s.area == "global" || (mem && s.area == "set")) && (self.prefs.expert || !Self::expert_only(s) || self.is_mymenu_place(s));
        let mut list: Vec<&Setting> = self.schema.settings.iter().filter(shown)
            .filter(|s| q.is_empty() || if self.is_mymenu_place(s) { self.place_found(s, q) } else { Self::matches_query(s, q) })
            .filter(|s| tab.is_none_or(|t| s.tab == t))
            .collect();
        // the camera's order over every setting (`menu_rank`), never the menu the window shows: these rows are cached
        // without it (`RowsKey`)
        let rank = self.camera_layout().then(|| self.menu_rank());
        let at = |s: &Setting| rank.as_ref().and_then(|r| r.get(&s.key).copied()).unwrap_or(s.order);
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
            // a place of My Menu under My Menu, in a group per page (`place_rows`)
            match self.is_mymenu_place(s) {
                true => rows.push((self.schema.camera.text.my_menu_name().to_string(), self.place_page(s), linked)),
                false => rows.push((s.tab.clone(), s.group.clone(), linked)),
            }
        }
        // keep each group together, in the order its first setting appears
        let mut first: std::collections::HashMap<(String, String), usize> = Default::default();
        for (i, r) in rows.iter().enumerate() { first.entry((r.0.clone(), r.1.clone())).or_insert(i); }
        let mut keyed: Vec<((usize, usize), Row)> = rows.into_iter().map(|r| ((tab_idx(&r.0), first[&(r.0.clone(), r.1.clone())]), r)).collect();
        keyed.sort_by_key(|(k, _)| *k);
        keyed.into_iter().map(|(_, r)| r).collect()
    }

    /// Compare's "Open in Edit": Edit on the setting `s` in `section` of file A (the live settings when that section
    /// does not keep it), opened as every jump opens one (`go_to`: its page, the group as Edit shows it, a family by its
    /// title, and its row): in the camera's menu Compare shows where that menu lists the setting's row, on that row
    /// whatever record it shows in Edit, else the menu a jump to `s` opens; with "← Back to Compare" to the row it came
    /// from. Only edited is turned off when it would hide the setting.
    pub(crate) fn open_in_edit_from_compare(&mut self, s: &Setting, section: usize) {
        let menu = self.compare_menu();
        // the Compare row it came from, by its entry's name (a tab, Main, My Menu…) and the setting's key
        let row = self.compare_rows(menu.as_deref(), &self.compare_key(), &self.search).iter()
            .find(|r| r.2.iter().any(|x| x.key == s.key)).map_or_else(|| s.tab.clone(), |r| r.0.clone());
        self.mode = Mode::Edit;
        // the set that keeps the setting: the column's, else (a setting only the memories keep, from the live column) the
        // first memory of file A among the columns, else the live settings
        self.target = if kept_in(s, section) { section } else if s.area == "set" { self.cols.iter().find(|c| c.editable() && c.section != 0 && kept_in(s, c.section)).map_or(section, |c| c.section) } else { 0 };
        // Edit in the menu Compare showed, on the setting's row there, where that menu lists it
        match menu.and_then(|m| self.row_in_menu(s, self.target, &m).map(|row| (m, row))) {
            Some((m, row)) => {
                self.set_menu(&m);
                self.go_to(&row);
            }
            None => self.go_to(s),
        }
        if self.only_changed && !self.changed(s) {
            self.only_changed = false;
        }
        self.from_compare = Some(FromCompare { view: self.view.clone(), group: self.group.clone(), item: self.item.clone(), target: self.target, row: (row, s.key.clone()) });
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
        let stored: Vec<bool> = cols.iter().map(|c| kept_in(s, c.section)).collect();
        let edited: Vec<bool> = cols.iter().zip(&vals).zip(&stored)
            .map(|((c, v), st)| *st && c.editable() && self.doc.as_ref().is_some_and(|d| d.original_value(c.section, s.slot()) != *v))
            .collect();
        // the first column that keeps the setting is the row's baseline: the live settings hold none of a memory's own
        let base = stored.iter().position(|s| *s);
        let differs = base.is_some_and(|b| (b + 1..cols.len()).any(|i| stored[i] && vals[i] != vals[b]));
        let class = three.map(|tc| self.three_way(tc, s));
        let mark = if edited.iter().any(|e| *e) { RowMark::Edited }
            else if class == Some(Three::Conflict) { RowMark::Conflict }
            else if differs { RowMark::Differs }
            else { RowMark::Same };
        RowInfo { vals, stored, edited, base, differs, class, mark }
    }
}

#[cfg(test)]
pub(crate) mod copy_tests {
    use super::*;

    /// File B and the base are read with file A's definition and copied from into A. Another model's file, where A's
    /// names mean nothing, is not compared: the status (the page: its refusal) says what it is and why. One from another
    /// firmware of the same camera is compared, with a line the window's Compare bar and the page's draw, and the status
    /// says, naming the firmware and what it means (copies take only the settings that sit where the editor expects
    /// them in both: `copies_leave_other_shapes_alone` and `the_page_leaves_other_shapes_alone`). A file A opened while
    /// B is open closes a B of another model, and says why; a B of another firmware stays, with the line.
    #[test]
    fn compare_takes_only_a_file_of_file_as_camera() {
        use crate::write::safety_tests::{other_firmware, other_model};
        let dir = std::env::temp_dir().join(format!("camset_compare_like_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let file = |name: &str, c: &CamSet| { let p = dir.join(name); std::fs::write(&p, c.to_bytes()).unwrap(); p };
        let (model, firmware) = (file("MODEL.DAT", &other_model()), file("OLD.DAT", &other_firmware()));
        let note = |name: &str| format!("{name} is from firmware 2.00 of this camera, file A from firmware 4.00. A firmware update can move settings: the editor reads both files the way file A's firmware keeps them, so a setting the other firmware keeps elsewhere can show a wrong value here, and only the settings that sit where the editor expects them in both files are copied into A.");
        let state = |app: &mut App| -> serde_json::Value { serde_json::from_slice(&crate::web::tests::answer(app, "state", serde_json::json!({})).body).unwrap() };
        // what the window's Compare bar draws (its second frame)
        let drawn = |app: &mut App| -> Vec<String> {
            let ctx = egui::Context::default();
            let mut frame = eframe::Frame::_new_kittest();
            let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame));
            crate::test_support::texts(&ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame)).shapes)
        };
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        // another model: not compared, as B or as the base, in the window and on the page
        app.open_compare(model.clone());
        assert!(app.compare.is_none() && app.mode != Mode::Compare, "not opened");
        assert!(app.status.starts_with("Not compared: file B is from a ILCE-0TEST (firmware 4.00) and file A from a ILCE-1M2.") && app.status.contains("camera definition"), "{}", app.status);
        let r = crate::web::tests::upload(&mut app, "open_b", &other_model().to_bytes(), "MODEL_B.DAT");
        let j: serde_json::Value = serde_json::from_slice(&r.body).unwrap();
        assert!(r.status == 409 && j["error"].as_str().unwrap().starts_with("Not compared: file B is from a ILCE-0TEST"), "{j}");
        assert!(app.compare.is_none());
        // another firmware of the same camera: compared, with the line in the window, on the page and in the status
        app.open_compare(firmware.clone());
        assert!(app.compare.is_some() && app.mode == Mode::Compare, "{}", app.status);
        assert_eq!(app.firmware_note(), Some(note("File B")));
        assert!(app.status.ends_with(&note("File B")), "{}", app.status);
        assert!(drawn(&mut app).contains(&format!("⚠ {}", note("File B"))), "the window's Compare bar draws the line");
        assert_eq!(state(&mut app)["compare"]["firmware_note"], serde_json::json!(note("File B")));
        app.open_base(model.clone());
        assert!(app.base.is_none() && app.status.starts_with("Not compared: the base file is from a ILCE-0TEST"), "{}", app.status);
        app.open_base(firmware.clone());
        assert!(app.base.is_some() && app.firmware_note() == Some(format!("{} {}", note("File B").split(" A firmware").next().unwrap(), note("The base file"))), "{:?}", app.firmware_note());
        app.close_base();
        // the page's open_b of another firmware: compared, the line in its state
        assert_eq!(crate::web::tests::upload(&mut app, "open_b", &other_firmware().to_bytes(), "OLD_B.DAT").status, 200);
        assert_eq!(state(&mut app)["compare"]["firmware_note"], serde_json::json!(note("File B")));
        // file B of file A's firmware: no line
        let same = file("SAME.DAT", &app.doc.as_ref().unwrap().edited.clone());
        app.open_compare(same.clone());
        assert!(app.firmware_note().is_none() && state(&mut app)["compare"]["firmware_note"].is_null());
        assert!(!drawn(&mut app).iter().any(|t| t.contains("A firmware update can move settings")));
        // a file A of another firmware opened while B is open: B stays, with the line, and the status says it
        app.open(firmware);
        assert_eq!(app.compare.as_ref().map(|(p, _)| p.clone()), Some(same.clone()));
        let back = "File B is from firmware 4.00 of this camera, file A from firmware 2.00.";
        assert!(app.firmware_note().is_some_and(|n| n.starts_with(back)) && app.status.contains(back), "{}", app.status);
        // a file A of another model: B closes, and the status says why
        app.open(model);
        assert!(app.compare.is_none() && app.status.contains("Not compared: file B is from a ILCE-1M2 (firmware 4.00) and file A from a ILCE-0TEST."), "{}", app.status);
        assert!(app.cols.iter().all(|c| c.src == Src::A));
        let _ = std::fs::remove_dir_all(&dir);
    }

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
        // a setting stored in the memories whose Memory 1 value differs from Live (not one of Expert mode's own records,
        // which Compare copies in Expert mode only: `expert_why`)
        let s = app.schema.settings.iter().filter(|s| s.in_sets && s.scalar && s.area == "global" && !App::expert_only(s))
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
        // as before menus, whatever the shipped definition lists (this test is not about the menus)
        crate::test_support::as_before_menus(&mut app);
        app.open_sample_now();
        let rows = app.matrix_rows_for("", None);
        assert!(rows.iter().all(|r| r.2.iter().all(|s| app.same_row(&r.2[0], s))), "a row holds linked records only");
        let keys: Vec<&str> = rows.iter().flat_map(|r| r.2.iter().map(|s| s.key.as_str())).collect();
        let unique: std::collections::HashSet<&str> = keys.iter().copied().collect();
        assert_eq!(keys.len(), unique.len(), "each setting once");
        // (My Menu's places, rows of Compare outside Expert mode too since its left bar is Edit's, are linked from My
        // Menu's page, never as a row of a tab: no page link takes one there)
        for r in rows.iter().filter(|r| !app.is_mymenu_place(&r.2[0])) {
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
        // (Compare's All for the page's columns: the rows as before menus and the records a Main tile shows that those
        // leave out, a memory's own with a memory column only, which these are not)
        assert_eq!(j["total"], serde_json::json!(app.compare_rows_in(None, &BarKey::All, "", &[Col::a(0), Col::b(0)]).len()));
        assert_eq!(j["rows"].as_array().unwrap().len() as u64, j["shown"].as_u64().unwrap());
        assert!(j["rows"].as_array().unwrap().iter().filter(|r| r["key"] == serde_json::json!(one.2[0].key) || r["key"] == serde_json::json!(two.2[0].key)).count() == 2, "both rows on the page");
        // every row Compare lists is under one entry of its Menu (a tab, Other, the entry for what the menus do not
        // hold, My Menu), and All settings holds those rows and no other; Main shows some of them again, its tiles'.
        // Without menus, and in each of the camera's menus
        let partition = |app: &App, menu: Option<&str>| {
            let mut all: Vec<String> = app.compare_rows(menu, &BarKey::All, "").iter().map(|r| r.2[0].key.clone()).collect();
            let records: std::collections::HashSet<String> = app.compare_rows(menu, &BarKey::All, "").iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect();
            let mut under: Vec<String> = Vec::new();
            for k in app.bar_keys(true, 0, menu, "", false) {
                let rows = app.compare_rows(menu, &k, "");
                match k {
                    BarKey::All => {}
                    BarKey::Main => assert!(rows.iter().flat_map(|r| r.2.iter()).all(|s| records.contains(&s.key)), "{menu:?}: Main's rows are All settings'"),
                    _ => under.extend(rows.iter().map(|r| r.2[0].key.clone())),
                }
            }
            let n = under.len();
            under.sort();
            under.dedup();
            assert_eq!(under.len(), n, "{menu:?}: each row under one entry");
            all.sort();
            assert_eq!(under, all, "{menu:?}: All settings holds every entry's rows, and only those");
        };
        partition(&app, None);
        let my_menu = app.schema.camera.text.my_menu_name().to_string();
        assert!(app.compare_rows(None, &BarKey::MyMenu, "").iter().any(|r| r.2[0].tab == my_menu), "My Menu's own setting under My Menu");
        let (app, dir, user) = crate::test_support::sample_app("cmp_one_entry", Some(crate::test_support::stub_menus));
        for m in app.menus().iter().map(|m| m.name.clone()).collect::<Vec<_>>() {
            partition(&app, Some(&m));
        }
        crate::test_support::done(&dir, &user);
    }

    /// One setting the camera keeps in several records (the reviewer's case: Exposure Comp., three records the Edit page
    /// links and writes together) is one row in Compare and on the Memories page, and every way of changing it there
    /// changes all its records: the window's arrow and copy, the window's picker, the page's copy and its picker.
    #[test]
    fn records_written_together_are_copied_together() {
        let mut app = App::new(vec![], Prefs::default());
        // as before menus, whatever the shipped definition lists (this test is not about the menus)
        crate::test_support::as_before_menus(&mut app);
        app.open_sample_now();
        let rows = app.matrix_rows_for("", None);
        let row = rows.iter().find(|r| r.2.len() >= 3 && r.2.iter().all(|s| s.scalar && s.values.len() >= 3 && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none()))
            .cloned().expect("a setting kept in three records");
        let linked = row.2.clone();
        assert_eq!(rows.iter().filter(|r| r.2.iter().any(|s| linked.iter().any(|l| l.key == s.key))).count(), 1, "one row for all its records");
        let label_of = |v: i64| linked[0].label_for(v).map(str::to_string);
        let cur = app.col_value(Col::a(0), &linked[0]).unwrap();
        let other = linked[0].values.iter().map(|(v, _)| *v).find(|v| *v != cur && linked[0].checked_on_camera(*v, 0)).expect("another value");
        // each record's own number for that value, as `apply` writes it (`Setting::twin_value`)
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
        app.apply(vec![Action::Set(0, row.2[0].slot(), other)]);
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

    /// My Menu with `n` items at the top of its first page (added when the sample holds fewer), taken as an edit.
    fn fill_mymenu(app: &mut App, n: usize) {
        let mm = app.schema.camera.my_menu.clone().unwrap();
        while app.mymenu_pages().unwrap()[0].iter().filter(|&&c| c != mm.empty).count() < n {
            let code = app.schema.settings.iter().filter_map(|s| s.menu_code).find(|&c| app.mymenu_find(c).is_none()).unwrap();
            let (acts, _) = app.mymenu_add(code).unwrap();
            assert_eq!(app.apply(acts), None);
        }
    }

    /// My Menu's places, as its page shows them: page by page, place by place (the definition's settings of the records
    /// `camera.my_menu` names).
    fn place_keys(app: &App) -> Vec<String> {
        let mm = app.schema.camera.my_menu.clone().unwrap();
        let mut places: Vec<&Setting> = app.schema.settings.iter().filter(|s| app.is_mymenu_place(s)).collect();
        places.sort_by_key(|s| (mm.records.iter().position(|&r| r == s.id), s.index));
        places.into_iter().map(|s| s.key.clone()).collect()
    }

    /// Integration review finding 2: My Menu in Compare. With items in My Menu's places, for a definition without menus
    /// and one with the stub's, in both layouts, outside Expert mode and in it, in each menu (or none) and for a search
    /// or none: every record of every row of All settings sits in exactly one row under exactly one entry other than All
    /// and Main, and those list nothing All lacks (by every record of a row); Main's records are All's; and without a
    /// search My Menu lists what Edit's My Menu page shows: one row per place, page by page, then its own tab's rows,
    /// outside Expert mode too, and in Expert mode nowhere else (not under the entry for what the menus do not hold).
    #[test]
    fn my_menu_in_compare_as_on_its_page() {
        use crate::test_support::{done, sample_app, strip_menus, stub_menus};
        for (with_menus, stub) in [(false, strip_menus as fn(&mut serde_json::Value)), (true, stub_menus)] {
            let (mut app, dir, user) = sample_app("cmp_mymenu", Some(stub));
            fill_mymenu(&mut app, 2);
            let places = place_keys(&app);
            assert_eq!(places.len(), 42);
            for flat in [false, true] {
                app.prefs.flat_list = flat;
                for expert in [false, true] {
                    app.prefs.expert = expert;
                    let menus: Vec<Option<String>> = std::iter::once(None).chain(app.menus().iter().map(|m| Some(m.name.clone()))).collect();
                    for menu in &menus {
                        let menu = menu.as_deref();
                        for q in ["", "iso"] {
                            let at = format!("menus {with_menus} flat {flat} expert {expert} menu {menu:?} q {q:?}");
                            let records = |k: &BarKey| -> Vec<String> { app.compare_rows(menu, k, q).iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect() };
                            let all = records(&BarKey::All);
                            let mut sorted = all.clone();
                            sorted.sort();
                            sorted.dedup();
                            assert_eq!(sorted.len(), all.len(), "{at}: each record of All once");
                            let mut under: Vec<String> = Vec::new();
                            for k in app.bar_keys(true, 0, menu, q, false) {
                                match k {
                                    BarKey::All => {}
                                    BarKey::Main => assert!(records(&k).iter().all(|r| sorted.binary_search(r).is_ok()), "{at}: Main's records are All's"),
                                    k => under.extend(records(&k)),
                                }
                            }
                            under.sort();
                            assert_eq!(under, sorted, "{at}: each record of All under one entry, and nothing else");
                            if q.is_empty() {
                                let mine: Vec<Vec<String>> = app.compare_rows(menu, &BarKey::MyMenu, q).iter().map(|r| r.2.iter().map(|s| s.key.clone()).collect()).collect();
                                let own: Vec<Vec<String>> = app.mymenu_groups().into_iter().flat_map(|(_, rows)| rows.into_iter().map(|r| r.into_iter().map(|s| s.key).collect())).collect();
                                let want: Vec<Vec<String>> = places.iter().map(|p| vec![p.clone()]).chain(own).collect();
                                let mut got = mine.clone();
                                for r in got.iter_mut() { r.sort(); }
                                let mut want_sorted = want.clone();
                                for r in want_sorted.iter_mut() { r.sort(); }
                                assert_eq!(got, want_sorted, "{at}: My Menu's rows as its page shows them");
                                let off = app.schema.camera.text.off_menu_name().to_string();
                                assert!(!records(&BarKey::Tab(off)).iter().any(|r| places.contains(r)), "{at}: no place under the entry for what the menus do not hold");
                            }
                        }
                    }
                }
            }
            // Edit's side: a place is under My Menu's page only, in Expert mode too
            app.prefs.flat_list = false;
            app.prefs.expert = true;
            let place = app.schema.settings.iter().find(|s| s.key == places[0]).cloned().unwrap();
            assert_eq!(app.entry_of(&place), app.schema.camera.text.my_menu_name());
            assert_eq!(app.view_of(&place), View::MyMenu);
            assert!(app.menu_tabs().iter().all(|t| !app.settings_in(0, Some(t)).any(|s| s.key == place.key)), "under no tab");
            done(&dir, &user);
        }
    }

    /// The decision on a fraction's two parts: in every way Compare writes, the two parts of a fraction tile (the
    /// definition's own tile: the Shutter Speed tile's `numerator_key` and `denominator_key`) go together, from the same
    /// column, in one undo step, or not at all, so the speed written is always the source's. The arrows and a
    /// right-click copy (`copy_row`), the picker (none for one part), a copy over rows with both parts shown or one
    /// (`copying_over`: left, and said), the page's copy and copy of the rows shown, a merge in the window
    /// (`merge_rows`) and on the page, a register from the live settings (which keep neither part: nothing written,
    /// nothing said), and a memory that keeps one part only (left, said, no arrow); the words where one presses name
    /// both parts. Without menus and in each of the stub's menus, in Expert mode, where Compare copies them (outside it
    /// they are view only: `a_fractions_parts_are_view_only_outside_expert_mode`).
    #[test]
    fn a_fractions_two_parts_are_copied_together() {
        use crate::test_support::{done, sample_app, strip_menus, stub_menus, SAMPLE_BYTES};
        for (with_menus, stub) in [(false, strip_menus as fn(&mut serde_json::Value)), (true, stub_menus)] {
            let (mut app, dir, user) = sample_app("cmp_fraction", Some(stub));
            app.prefs.expert = true;
            let tile = app.schema.camera.main_tiles.clone().unwrap().0[0].tiles.iter().find(|t| t.kind == TileKind::Fraction).cloned().unwrap();
            let find = |app: &App, k: &str| app.schema.settings.iter().find(|s| s.key == k).cloned().unwrap();
            let (num, den) = (find(&app, tile.numerator_key.as_deref().unwrap()), find(&app, tile.denominator_key.as_deref().unwrap()));
            let (m1, m2) = (app.dial_sets()[0], app.dial_sets()[1]);
            // a file whose memories hold the speeds given (numerator, denominator)
            let file = |speeds: &[(usize, i64, i64)]| {
                let mut c = test_parse(SAMPLE_BYTES).unwrap();
                for &(m, n, d) in speeds {
                    c.sections[m].get_mut(num.id).unwrap().put(num.index, n).unwrap();
                    c.sections[m].get_mut(den.id).unwrap().put(den.index, d).unwrap();
                }
                c
            };
            let f = dir.join("CAMSET02.DAT");
            std::fs::write(&f, file(&[(m1, 2, 1), (m2, 1, 2)]).to_bytes()).unwrap();
            app.open(f);
            let speed = |app: &App, c: Col| (app.col_value(c, &num), app.col_value(c, &den));
            let (a1, a2) = (Col::a(m1), Col::a(m2));
            let (two, half) = ((Some(2), Some(1)), (Some(1), Some(2)));
            assert_eq!((speed(&app, a1), speed(&app, a2)), (two, half));
            let page = |app: &mut App, name: &str, mut body: serde_json::Value, menu: Option<&str>| -> serde_json::Value {
                if let Some(m) = menu { body["menu"] = serde_json::json!(m); }
                let a = crate::web::tests::answer(app, name, body);
                assert_eq!(a.status, 200, "{name}: {}", String::from_utf8_lossy(&a.body));
                serde_json::from_slice(&a.body).unwrap()
            };
            // with menus, Compare always shows one (and the page names it in every request)
            let menus: Vec<Option<String>> = if app.menus().is_empty() { vec![None] } else { app.menus().iter().map(|m| Some(m.name.clone())).collect() };
            for menu in &menus {
                let menu = menu.as_deref();
                let at = format!("menus {with_menus} menu {menu:?}");
                let main = app.compare_rows(menu, &BarKey::Main, "");
                let row_of = |k: &str| main.iter().find(|r| r.2.iter().any(|s| s.key == k)).cloned().unwrap();
                let (nrow, drow) = (row_of(&num.key), row_of(&den.key));
                // the words where one presses, and no picker for one part
                let words = app.fraction_words(&nrow.2[0]).unwrap();
                assert!(words.contains(&num.name) && words.contains(&den.name) && words.contains(&tile.caption), "{at}: {words}");
                assert!(!app.cell_editable(a2, &nrow.2) && !app.cell_editable(a2, &drow.2), "{at}: no value of one part alone");
                // an arrow or a right-click copy of either part: both, from that column, undone in one step
                for row in [&nrow, &drow] {
                    assert_eq!(app.arrows_between(a1, a2, &row.2[0]), (true, true), "{at}");
                    assert!(app.copy_targets(a1, &row.2[0]).contains(&a2));
                    let acts = app.copy_row(&row.2, a1, a2);
                    app.apply(acts);
                    assert_eq!(speed(&app, a2), two, "{at}: {}", row.2[0].name);
                    app.undo();
                    assert_eq!(speed(&app, a2), half, "{at}: one undo step");
                }
                // a copy over rows: one part shown is left, and said; both shown, the source's speed
                app.copying_over([&nrow]);
                assert!(app.copy_row(&nrow.2, a1, a2).is_empty());
                assert_eq!(app.copy_skipped.get().fraction, 1);
                app.apply(Vec::new());
                assert!(app.status.contains("two parts of a value a Main tile shows as a fraction") && speed(&app, a2) == half, "{at}: {}", app.status);
                app.copying_over([&nrow, &drow]);
                let acts: Vec<Action> = [&nrow, &drow].iter().flat_map(|r| app.copy_row(&r.2, a1, a2)).collect();
                app.apply(acts);
                assert_eq!(speed(&app, a2), two, "{at}: both shown");
                app.undo();
                // the page: a copy of one part, a copy of the rows shown with one part and with both
                page(&mut app, "copy", serde_json::json!({ "from": ["a", m1], "to": ["a", m2], "key": num.key, "entry": "main" }), menu);
                assert_eq!(speed(&app, a2), two, "{at}: the page's copy");
                app.undo();
                let j = page(&mut app, "copy_rows", serde_json::json!({ "from": ["a", m1], "to": ["a", m2], "keys": [num.key], "entry": "main" }), menu);
                assert!(j["message"].as_str().is_some_and(|m| m.contains("as a fraction")) && speed(&app, a2) == half, "{at}: {j}");
                page(&mut app, "copy_rows", serde_json::json!({ "from": ["a", m1], "to": ["a", m2], "keys": [num.key, den.key], "entry": "main" }), menu);
                assert_eq!(speed(&app, a2), two, "{at}: the page's copy of both");
                app.undo();
                // a merge: base 1/2, A 1/4 (its denominator changed), B 3/2 (its numerator): B's speed, in the window
                // and on the page; with only the numerator shown, nothing
                app.apply(vec![Action::Set(m2, den.slot(), 4)]);
                app.base = Some((PathBuf::from("base.DAT"), file(&[(m1, 2, 1), (m2, 1, 2)])));
                app.compare = Some((PathBuf::from("B.DAT"), file(&[(m1, 2, 1), (m2, 3, 2)])));
                let cols = (Col::base(m2), a2, Col::b(m2));
                let all = app.compare_rows(menu, &BarKey::All, "");
                let (acts, _) = app.merge_rows(&all, cols, Three::BOnly, Col::b(m2));
                app.apply(acts);
                assert_eq!(speed(&app, a2), (Some(3), Some(2)), "{at}: the window's merge");
                app.undo();
                let j = page(&mut app, "merge", serde_json::json!({ "base": ["base", m2], "a": ["a", m2], "b": ["b", m2], "kind": "b_into_a", "entry": "all" }), menu);
                assert_eq!(speed(&app, a2), (Some(3), Some(2)), "{at}: the page's merge: {j}");
                app.undo();
                let one: Vec<Row> = all.iter().filter(|r| r.2[0].key != den.key).cloned().collect();
                let (acts, _) = app.merge_rows(&one, cols, Three::BOnly, Col::b(m2));
                app.apply(acts);
                assert_eq!(speed(&app, a2), (Some(1), Some(4)), "{at}: one part shown: left");
                app.undo();
                (app.base, app.compare) = (None, None);
                // a register from the live settings, which keep neither part: the memory's speed as it was, nothing said
                let j = page(&mut app, "register", serde_json::json!({ "memory": m1, "shown": true, "entry": "main" }), menu);
                assert!(speed(&app, a1) == two && !j["message"].as_str().unwrap_or("").contains("fraction"), "{at}: {j}");
                app.undo();
            }
            // a memory that keeps one part only: no arrow, the copy left and counted
            for s in app.schema.settings.iter_mut().filter(|s| s.key == den.key) { s.in_sets = false; }
            app.schema_gen += 1;
            assert_eq!(app.arrows_between(a1, a2, &num), (false, false));
            app.copy_skipped.set(Default::default());
            assert!(app.copy_row(std::slice::from_ref(&num), a1, a2).is_empty() && app.copy_skipped.get().fraction == 1);
            done(&dir, &user);
        }
    }

    /// Integration review finding 6, as corrected: Compare's Main lists every record a Main tile shows, outside Expert
    /// mode too, the Shutter Speed tile's two parts (Expert-only records a memory keeps) included, each titled with the
    /// tile's label first (`compare_title`); All settings holds them, each under one entry; without menus and in each
    /// of the stub's menus, the window's rows and the page's alike.
    #[test]
    fn compares_main_lists_every_record_a_tile_shows() {
        use crate::test_support::{done, sample_app, strip_menus, stub_menus};
        for (with_menus, stub) in [(false, strip_menus as fn(&mut serde_json::Value)), (true, stub_menus)] {
            let (mut app, dir, user) = sample_app("cmp_main_tiles", Some(stub));
            let sets = app.schema.camera.main_tiles.clone().unwrap().0;
            let menus: Vec<Option<String>> = std::iter::once(None).chain(app.menus().iter().map(|m| Some(m.name.clone()))).collect();
            for menu in &menus {
                let menu = menu.as_deref();
                let at = format!("menus {with_menus} menu {menu:?}");
                // a memory of this menu among the columns, so a memory's own records are listed (`lists_memory_settings`),
                // the window's and the page's alike
                let mem = menu.map_or(1, |m| app.menu_sets(Some(m)).into_iter().find(|&s| s != 0).unwrap_or(1));
                app.cols = vec![Col::a(0), Col::a(mem)];
                let tiles = &sets[menu.and_then(|m| app.menu_tile_set(m)).unwrap_or(0)].tiles;
                let main = app.compare_rows(menu, &BarKey::Main, "");
                let shown: Vec<String> = main.iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect();
                // every record each tile shows, as that menu's row shows it (`row_record`)
                for t in tiles {
                    for k in t.keys.iter().chain(&t.memory_keys).chain(&t.numerator_key).chain(&t.denominator_key) {
                        let s = app.schema.settings.iter().find(|s| &s.key == k).unwrap();
                        let want = match menu { Some(m) => app.row_record(s, m, &Bind::Menu).key.clone(), None => s.key.clone() };
                        assert!(shown.contains(&want), "{at}: {} of {}", s.name, t.caption);
                    }
                }
                // a memory's own record holds no value in the live settings' column, and takes none there
                for s in app.tile_records("").iter().filter(|s| s.area != "global") {
                    assert_eq!(app.col_value(Col::a(0), s), None, "{at}: {} in the live settings", s.name);
                    assert!(app.col_value(Col::a(1), s).is_some(), "{at}: {} in a memory", s.name);
                }
                // the fraction's two parts, under the tile, its label first
                let shutter = tiles.iter().find(|t| t.kind == TileKind::Fraction).expect("the Shutter Speed tile");
                for k in shutter.numerator_key.iter().chain(&shutter.denominator_key) {
                    let row = main.iter().find(|r| r.2.iter().any(|s| &s.key == k)).unwrap();
                    let title = app.compare_title(row);
                    assert!(row.1 == shutter.caption && title.to_lowercase().starts_with(&shutter.caption.to_lowercase()), "{at}: {title}");
                }
                // All holds them, each record under one entry other than All and Main
                let records = |k: &BarKey| -> Vec<String> { app.compare_rows(menu, k, "").iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect() };
                let mut all = records(&BarKey::All);
                let n = all.len();
                all.sort();
                all.dedup();
                assert_eq!(n, all.len(), "{at}: each record of All once");
                assert!(shown.iter().all(|k| all.binary_search(k).is_ok()), "{at}: Main's records are All's");
                let mut under: Vec<String> = app.bar_keys(true, 0, menu, "", false).into_iter().filter(|k| !matches!(k, BarKey::All | BarKey::Main)).flat_map(|k| records(&k)).collect();
                under.sort();
                assert_eq!(under, all, "{at}: each record of All under one entry");
                // the page: the same rows under Main, with the same titles
                let mut body = serde_json::json!({ "cols": [["a", 0], ["a", mem]], "entry": "main", "only_diff": false });
                if let Some(m) = menu { body["menu"] = serde_json::json!(m); }
                let a = crate::web::tests::answer(&mut app, "compare", body);
                let j: serde_json::Value = serde_json::from_slice(&a.body).unwrap();
                let page: Vec<(String, String)> = j["rows"].as_array().unwrap().iter().map(|r| (r["key"].as_str().unwrap().to_string(), r["name"].as_str().unwrap().to_string())).collect();
                let window: Vec<(String, String)> = main.iter().map(|r| (r.2[0].key.clone(), app.compare_title(r))).collect();
                assert_eq!(page, window, "{at}: the page's Main as the window's");
                // with the live settings alone, none of a memory's own records: they hold none of them
                let live = app.compare_rows_in(menu, &BarKey::Main, "", &[Col::a(0)]);
                assert!(live.iter().all(|r| r.2.iter().all(|s| s.area != "set")), "{at}: no memory record with the live settings alone");
            }
            done(&dir, &user);
        }
    }

    /// Second integration review, MUST 1: outside Expert mode Compare's Revert on a place of My Menu puts back all of My
    /// Menu's places as the file was opened, in one undo step, and says so before the press; never one place alone (two
    /// items, the first moved down: a Revert of that place alone would hold one item twice). Expert mode as before.
    #[test]
    fn a_places_revert_in_compare_puts_back_all_of_my_menu() {
        use crate::test_support::{done, sample_app, strip_menus};
        let (mut app, dir, user) = sample_app("cmp_mymenu_revert", Some(strip_menus));
        let opened = app.mymenu_pages().unwrap();
        fill_mymenu(&mut app, 2);
        let (acts, _) = app.mymenu_move(0, 0, 1).unwrap();
        app.apply(acts);
        let moved = app.mymenu_pages().unwrap();
        let place = app.schema.settings.iter().find(|s| s.key == place_keys(&app)[0]).cloned().unwrap();
        let (words, acts) = app.cell_revert(std::slice::from_ref(&place), 0);
        assert_eq!(words, "Revert My Menu (all its items, as the file was opened)");
        app.apply(acts);
        assert_eq!(app.mymenu_pages().unwrap(), opened, "My Menu as the file was opened");
        app.undo();
        assert_eq!(app.mymenu_pages().unwrap(), moved, "one undo step");
        app.prefs.expert = true;
        let (words, acts) = app.cell_revert(std::slice::from_ref(&place), 0);
        assert_eq!((words.as_str(), acts.len()), ("Revert", 1), "Expert mode: that place");
        done(&dir, &user);
    }

    /// Second integration review, MUST 2: Compare's rows under a search follow the files: an item put into My Menu on
    /// its page is found at once (and gone after an undo), and a place is found by the item file B holds there too.
    #[test]
    fn compares_rows_under_a_search_follow_the_files() {
        use crate::test_support::{done, sample_app, strip_menus};
        let (mut app, dir, user) = sample_app("cmp_mymenu_search", Some(strip_menus));
        let mm = app.schema.camera.my_menu.clone().unwrap();
        let place = app.schema.settings.iter().find(|s| s.key == place_keys(&app)[0]).cloned().unwrap();
        let (code, label) = place.values.iter().filter(|(v, _)| *v != mm.empty && app.mymenu_find(*v).is_none() && app.mymenu_add(*v).is_ok())
            .find(|(_, l)| app.compare_rows(None, &BarKey::MyMenu, l).is_empty()).cloned().expect("an item no place holds");
        let found = |app: &App| app.compare_rows(None, &BarKey::MyMenu, &label).iter().filter(|r| app.is_mymenu_place(&r.2[0])).count();
        assert_eq!(found(&app), 0);
        let (acts, _) = app.mymenu_add(code).unwrap();
        app.apply(acts);
        assert_eq!(found(&app), 1, "{label}: found once put in");
        app.undo();
        assert_eq!(found(&app), 0, "{label}: gone after an undo");
        let mut b = app.doc.as_ref().unwrap().edited.clone();
        b.sections[0].get_mut(place.id).unwrap().put(place.index, code).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        assert_eq!(found(&app), 1, "{label}: the item file B holds there");
        done(&dir, &user);
    }

    /// The reviewer's third look: a Revert of a fraction's part puts back both parts, as the file was opened, in one
    /// step, in either mode, and says so before the press: Compare's cell in the window, the page's revert (Expert mode,
    /// the only one in which the page finds the part), and All edits and History, which list the two as one line.
    /// The scenario: in Expert mode an arrow from B takes both parts (0,0 becomes B's 1,2); then Expert mode off.
    #[test]
    fn a_fractions_parts_are_reverted_together() {
        use crate::test_support::{done, sample_app, strip_menus};
        let (mut app, dir, user) = sample_app("cmp_fraction_revert", Some(strip_menus));
        let tile = app.schema.camera.main_tiles.clone().unwrap().0[0].tiles.iter().find(|t| t.kind == TileKind::Fraction).cloned().unwrap();
        let find = |app: &App, k: &Option<String>| app.schema.settings.iter().find(|s| Some(&s.key) == k.as_ref()).cloned().unwrap();
        let (num, den) = (find(&app, &tile.numerator_key), find(&app, &tile.denominator_key));
        let m = app.dial_sets()[0];
        let speed = |app: &App| (app.col_value(Col::a(m), &num), app.col_value(Col::a(m), &den));
        let opened = speed(&app);
        let (n0, d0) = (opened.0.unwrap(), opened.1.unwrap());
        let mut b = app.doc.as_ref().unwrap().edited.clone();
        b.sections[m].get_mut(num.id).unwrap().put(num.index, n0 + 1).unwrap();
        b.sections[m].get_mut(den.id).unwrap().put(den.index, d0 + 2).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        let theirs = (Some(n0 + 1), Some(d0 + 2));
        app.prefs.expert = true;
        let acts = app.copy_row(std::slice::from_ref(&num), Col::b(m), Col::a(m));
        app.apply(acts);
        assert_eq!(speed(&app), theirs, "the arrow took both parts");
        // Compare's cell Revert, out of Expert mode and in it
        for expert in [false, true] {
            app.prefs.expert = expert;
            let (words, acts) = app.cell_revert(std::slice::from_ref(&num), m);
            assert!(words.contains(&num.name) && words.contains(&den.name) && words.contains(&tile.caption), "{words}");
            app.apply(acts);
            assert_eq!(speed(&app), opened, "expert {expert}: both parts as the file was opened");
            app.undo();
            assert_eq!(speed(&app), theirs, "one undo step");
        }
        // the page's revert, in Expert mode
        let a = crate::web::tests::answer(&mut app, "revert", serde_json::json!({ "target": m, "key": num.key }));
        assert_eq!(a.status, 200, "{}", String::from_utf8_lossy(&a.body));
        assert_eq!(speed(&app), opened, "the page: both parts");
        app.undo();
        // All edits and History: the two parts one line, whose Revert puts back both
        for expert in [false, true] {
            app.prefs.expert = expert;
            let doc = app.doc.as_ref().unwrap();
            let lines: Vec<EditLine> = app.edit_lines(&doc.original, &doc.edited).into_iter().filter(|l| l.slots.contains(&num.slot()) || l.slots.contains(&den.slot())).collect();
            assert_eq!(lines.len(), 1, "expert {expert}: one line for the two parts");
            assert!(lines[0].slots.contains(&num.slot()) && lines[0].slots.contains(&den.slot()));
            app.apply(lines[0].slots.iter().map(|&slot| Action::Revert(m, slot)).collect());
            assert_eq!(speed(&app), opened, "expert {expert}: All edits' Revert");
            app.undo();
            let step = app.undo.len() - 1;
            let doc = app.doc.as_ref().unwrap();
            let line = app.history_lines(step, &doc.edited).iter().find(|l| l.slots.contains(&num.slot())).cloned().unwrap();
            assert!(line.slots.contains(&den.slot()), "expert {expert}: History's line holds both");
            let acts = line.put_back(&app.undo[step], &doc.edited);
            app.history_revert(acts);
            assert_eq!(speed(&app), opened, "expert {expert}: History's Revert");
            app.undo();
        }
        done(&dir, &user);
    }

    /// Follow-up 2: a note on a Compare row names the other menus by Compare's binding (each menu its own mode's copy),
    /// where it differs from Edit's: a file whose mode is not known, ISO's movie copy apart from it when the file was
    /// opened. A change of Movie's row in Compare writes that copy alone, which S&Q's Compare row shows too, so the note
    /// names S&Q; Edit's rows (which show the setting itself there) say it changes Movie's alone. The page the same.
    #[test]
    fn a_compare_rows_note_names_the_menus_compare_shows() {
        use crate::test_support::{done, sample_app, stub_menus, SAMPLE_BYTES};
        let (mut app, dir, user) = sample_app("cmp_note_bind", Some(stub_menus));
        let rec = app.schema.settings.iter().find(|s| Some(&s.key) == app.schema.camera.live_mode.as_ref().map(|m| &m.key)).cloned().unwrap();
        let (iso, movie) = ["global:0x0334", "global:0x0df4"].map(|k| app.schema.settings.iter().find(|s| s.key == k).cloned().unwrap()).into();
        let mut c = test_parse(SAMPLE_BYTES).unwrap();
        c.sections[0].get_mut(rec.id).unwrap().put(rec.index, 9).unwrap();
        let held = c.sections[0].get(movie.id).unwrap().get(movie.index).unwrap();
        let other = movie.values.iter().map(|(v, _)| *v).find(|v| *v != held).unwrap();
        c.sections[0].get_mut(movie.id).unwrap().put(movie.index, other).unwrap();
        let f = dir.join("CAMSET04.DAT");
        std::fs::write(&f, c.to_bytes()).unwrap();
        app.open(f);
        let row = app.compare_rows(Some("Movie"), &BarKey::All, "").iter().find(|r| r.2[0].key == movie.key).map(|r| r.2[0].clone()).expect("Movie's ISO row shows the movie copy");
        let (compare, _) = app.copy_note_bound(&row, 0, &Bind::Menu).unwrap();
        assert!(compare.starts_with("Changing this changes it in the S&Q menu too"), "{compare}");
        // the same row told of by Edit's binding (each menu the setting itself here): Movie's alone, untrue in Compare
        let (edit, _) = app.copy_note(&row, 0).unwrap();
        assert!(edit.starts_with("Changing this changes it in the Movie menu alone"), "{edit}");
        // the change itself: S&Q's Compare row moves with it
        let v = movie.values.iter().map(|(v, _)| *v).find(|v| *v != other && *v != held).unwrap();
        let sq = |app: &App| app.col_value(Col::a(0), &app.row_record(&iso, "S&Q", &Bind::Menu).clone());
        app.apply(vec![Action::Set(0, row.slot(), v)]);
        assert_eq!(sq(&app), Some(v), "S&Q's Compare row changed with it");
        app.undo();
        // the page's Compare cell says the same
        let a = crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["a", 1]], "menu": "Movie", "only_diff": false }));
        let j: serde_json::Value = serde_json::from_slice(&a.body).unwrap();
        let r = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == movie.key.as_str()).cloned().unwrap();
        assert!(r["cells"][0]["why"].as_str().is_some_and(|w| w.contains("in the S&Q menu too")), "{r}");
        done(&dir, &user);
    }

    /// Follow-up 3: a fraction's two parts changed in two steps (two Expert-mode edits, one part each) never come apart in
    /// History: the first step's line holds both parts, and its Revert puts the pair back as it was before that step
    /// (the second step's part too), a pair a file held, never one part from one state and one from another; its words
    /// say so; All edits' line puts both back as the file was opened.
    #[test]
    fn a_fractions_parts_changed_in_two_steps_go_back_together() {
        use crate::test_support::{done, sample_app, strip_menus};
        let (mut app, dir, user) = sample_app("cmp_fraction_steps", Some(strip_menus));
        let tile = app.schema.camera.main_tiles.clone().unwrap().0[0].tiles.iter().find(|t| t.kind == TileKind::Fraction).cloned().unwrap();
        let find = |app: &App, k: &Option<String>| app.schema.settings.iter().find(|s| Some(&s.key) == k.as_ref()).cloned().unwrap();
        let (num, den) = (find(&app, &tile.numerator_key), find(&app, &tile.denominator_key));
        let m = app.dial_sets()[0];
        let speed = |app: &App| (app.col_value(Col::a(m), &num), app.col_value(Col::a(m), &den));
        let opened = speed(&app);
        app.prefs.expert = true;
        app.apply(vec![Action::Set(m, num.slot(), opened.0.unwrap() + 1)]);
        app.last_edit = None;
        app.apply(vec![Action::Set(m, den.slot(), opened.1.unwrap() + 3)]);
        assert_eq!(app.undo.len(), 2);
        for expert in [false, true] {
            app.prefs.expert = expert;
            let doc = app.doc.as_ref().unwrap();
            let line = app.history_lines(0, &doc.edited).iter().find(|l| l.slots.contains(&num.slot())).cloned().unwrap();
            assert!(line.slots.contains(&den.slot()), "expert {expert}: the first step's line holds both parts");
            assert!(app.edit_line_revert_words(&line, true).is_some_and(|w| w.contains(&tile.caption)), "expert {expert}: its words");
            // the reviewer's finding 2: the later change to the other part goes back too, and its words say so; the
            // second step's line, with nothing changed since, says nothing of the kind, the page as the window
            let words = app.history_revert_words(0, &line, &doc.edited).unwrap();
            assert!(words.contains(&format!("A later edit changed {} since", den.name)), "expert {expert}: {words}");
            let second = app.history_lines(1, &doc.edited).iter().find(|l| l.slots.contains(&den.slot())).cloned().unwrap();
            assert!(!app.history_revert_words(1, &second, &doc.edited).unwrap().contains("later edit"), "expert {expert}");
            let j: serde_json::Value = serde_json::from_slice(&crate::web::tests::answer(&mut app, "history", serde_json::json!({})).body).unwrap();
            assert!(j["steps"].as_array().unwrap().iter().any(|s| s["step"] == 0 && s["revert_words"].as_str().is_some_and(|w| w.contains("A later edit changed"))), "expert {expert}: the page");
            let doc = app.doc.as_ref().unwrap();
            let acts = line.put_back(&app.undo[0], &doc.edited);
            app.history_revert(acts);
            assert_eq!(speed(&app), opened, "expert {expert}: the pair as before that step");
            app.undo();
            let doc = app.doc.as_ref().unwrap();
            let lines: Vec<EditLine> = app.edit_lines(&doc.original, &doc.edited).into_iter().filter(|l| l.slots.contains(&num.slot()) || l.slots.contains(&den.slot())).collect();
            assert!(lines.len() == 1 && app.edit_line_revert_words(&lines[0], false).is_some_and(|w| w.contains("together")), "expert {expert}: All edits' one line");
        }
        done(&dir, &user);
    }

    /// Second integration review, MUST 3: Edit's Main shows the Shutter Speed tile but changes it nowhere (a tile of two
    /// settings is not edited in place), so outside Expert mode Compare writes neither of its parts: no arrow, picker
    /// or copy target, a copy leaves them and says so, the reason is where one presses, in the window and on the page.
    /// Each part is under one entry besides Main (the one that shows it).
    #[test]
    fn a_fractions_parts_are_view_only_outside_expert_mode() {
        use crate::test_support::{done, sample_app, strip_menus};
        let (mut app, dir, user) = sample_app("cmp_fraction_ro", Some(strip_menus));
        let tile = app.schema.camera.main_tiles.clone().unwrap().0[0].tiles.iter().find(|t| t.kind == TileKind::Fraction).cloned().unwrap();
        let num = app.schema.settings.iter().find(|s| Some(&s.key) == tile.numerator_key.as_ref()).cloned().unwrap();
        let m = app.dial_sets()[0];
        let mut b = app.doc.as_ref().unwrap().edited.clone();
        let cur = app.col_value(Col::a(m), &num).unwrap();
        b.sections[m].get_mut(num.id).unwrap().put(num.index, cur + 1).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(m), Col::b(m)], false);
        let why = app.compare_why(&num).expect("a reason outside Expert mode");
        assert!(why.contains(&tile.caption) && why.contains("Expert mode"), "{why}");
        assert_eq!(app.arrows_between(Col::b(m), Col::a(m), &num), (false, false));
        assert!(!app.cell_editable(Col::a(m), std::slice::from_ref(&num)) && app.copy_targets(Col::b(m), &num).is_empty());
        app.copy_skipped.set(Default::default());
        assert!(app.copy_row(std::slice::from_ref(&num), Col::b(m), Col::a(m)).is_empty() && app.copy_skipped.get().expert == 1);
        app.apply(Vec::new());
        assert!(app.status.contains("Expert mode's own record"), "{}", app.status);
        let a = crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", m], ["b", m]], "entry": "main", "only_diff": false }));
        let j: serde_json::Value = serde_json::from_slice(&a.body).unwrap();
        let row = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == num.key.as_str()).cloned().unwrap();
        assert!(row["cells"][0]["why"].as_str().is_some_and(|w| w.contains(&tile.caption)) && row["arrows"][0] == serde_json::json!([false, false]), "{row}");
        // one entry besides Main: the one that shows it (`entry_here`)
        let under: Vec<BarKey> = app.bar_keys(true, 0, None, "", false).into_iter().filter(|k| !matches!(k, BarKey::All | BarKey::Main))
            .filter(|k| app.compare_rows(None, k, "").iter().any(|r| r.2.iter().any(|s| s.key == num.key))).collect();
        assert_eq!(under, vec![BarKey::Tab(app.entry_of(&num))]);
        app.prefs.expert = true;
        assert!(app.compare_why(&num).is_none() && app.arrows_between(Col::b(m), Col::a(m), &num) == (false, true), "Expert mode: an arrow, which takes the two together");
        done(&dir, &user);
    }

    /// Integration review finding 2: outside Expert mode a place of My Menu is never written from Compare, in the window
    /// or on the page, whichever way: no arrow into file A, no picker, no copy target, a copy of its row leaves it and
    /// says how many it left and why (the arrows, the right-click copy, the buttons over the rows shown, the page's
    /// copy, copy of the rows shown and merge), the page's set refuses it, and the reason is in the cell where one would
    /// press; Open in Edit opens it on My Menu's page. Expert mode copies it as before.
    #[test]
    fn my_menus_places_are_changed_on_its_page_only() {
        use crate::test_support::{done, sample_app, strip_menus};
        let (mut app, dir, user) = sample_app("cmp_mymenu_ro", Some(strip_menus));
        fill_mymenu(&mut app, 2);
        let place = app.schema.settings.iter().find(|s| s.key == place_keys(&app)[0]).cloned().unwrap();
        let code = app.col_value(Col::a(0), &place).unwrap();
        let other = place.values.iter().map(|(v, _)| *v).find(|v| *v != code && app.mymenu_find(*v).is_none() && *v != app.schema.camera.my_menu.as_ref().unwrap().empty).unwrap();
        let mut b = app.doc.as_ref().unwrap().edited.clone();
        b.sections[0].get_mut(place.id).unwrap().put(place.index, other).unwrap();
        app.base = Some((PathBuf::from("base.DAT"), app.doc.as_ref().unwrap().edited.clone()));
        app.compare = Some((PathBuf::from("B.DAT"), b));
        (app.mode, app.cols, app.matrix_only_diff) = (Mode::Compare, vec![Col::a(0), Col::b(0)], false);
        let why = app.place_why(&place).expect("outside Expert mode, a reason");
        assert!(why.contains("My Menu page"), "{why}");
        assert_eq!(app.arrows_between(Col::b(0), Col::a(0), &place), (false, false), "no arrow into A");
        assert!(!app.cell_editable(Col::a(0), std::slice::from_ref(&place)), "no picker");
        assert!(app.copy_targets(Col::b(0), &place).is_empty(), "no copy target");
        app.copy_skipped.set(Default::default());
        assert!(app.copy_row(std::slice::from_ref(&place), Col::b(0), Col::a(0)).is_empty(), "a copy leaves it");
        assert_eq!(app.copy_skipped.get().places, 1);
        app.apply(Vec::new());
        assert!(app.status.contains("1 of My Menu's places left as it was") && app.status.contains("My Menu page"), "{}", app.status);
        // the page: the cell's reason, its set refused, and each copy over rows leaving it, saying so
        let ask = |app: &mut App, name: &str, body: serde_json::Value| -> (u16, serde_json::Value) {
            let a = crate::web::tests::answer(app, name, body);
            (a.status, serde_json::from_slice(&a.body).unwrap_or(serde_json::Value::Null))
        };
        let (_, j) = ask(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["b", 0]], "entry": "mymenu", "only_diff": false }));
        let row = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == place.key.as_str()).cloned().expect("the place's row");
        assert!(row["cells"][0]["why"].as_str().is_some_and(|w| w.contains("My Menu page")) && row["cells"][0].get("editable").is_none() && row["arrows"][0] == serde_json::json!([false, false]), "{row}");
        let (status, _) = ask(&mut app, "set", serde_json::json!({ "target": 0, "key": place.key, "value": other, "col": ["a", 0] }));
        assert!(status >= 400 && app.col_value(Col::a(0), &place) == Some(code), "the page's set refuses it: {status}");
        for (name, body) in [
            ("copy", serde_json::json!({ "from": ["b", 0], "to": ["a", 0], "key": place.key })),
            ("copy_rows", serde_json::json!({ "from": ["b", 0], "to": ["a", 0], "keys": [place.key] })),
            ("merge", serde_json::json!({ "base": ["base", 0], "a": ["a", 0], "b": ["b", 0], "kind": "b_into_a", "entry": "mymenu" })),
        ] {
            let (status, j) = ask(&mut app, name, body);
            assert_eq!(status, 200, "{name}: {j}");
            assert!(j["message"].as_str().is_some_and(|m| m.contains("of My Menu's places left as it was") && m.contains("My Menu page")), "{name}: {j}");
            assert_eq!(app.col_value(Col::a(0), &place), Some(code), "{name}: the place as it was");
        }
        // the page: its link on the place's row opens My Menu's page by the place's key, which the page's My Menu
        // answer gives that place, so the page marks it as the window does
        assert_eq!((row["open_tab"].as_str(), row.get("open_key").and_then(|k| k.as_str()).unwrap_or(row["key"].as_str().unwrap())), (Some(app.schema.camera.text.my_menu_name()), place.key.as_str()), "{row}");
        let (_, mm) = ask(&mut app, "mymenu_page", serde_json::json!({ "target": 0 }));
        assert_eq!(mm["pages"][0]["places"][0]["key"].as_str(), Some(place.key.as_str()));
        // Open in Edit opens it on My Menu's page
        app.open_in_edit_from_compare(&place, 0);
        assert!(app.mode == Mode::Edit && app.view == View::MyMenu, "{:?}", app.view);
        assert_eq!(app.item_key.as_deref(), Some(place.key.as_str()));
        // Expert mode: as before
        (app.mode, app.prefs.expert) = (Mode::Compare, true);
        assert!(app.place_why(&place).is_none() && app.cell_editable(Col::a(0), std::slice::from_ref(&place)) && app.arrows_between(Col::b(0), Col::a(0), &place) == (false, true));
        let acts = app.copy_row(std::slice::from_ref(&place), Col::b(0), Col::a(0));
        app.apply(acts);
        assert_eq!(app.col_value(Col::a(0), &place), Some(other), "Expert mode copies it");
        done(&dir, &user);
    }
}

/// The settings only the memories keep (`area` "set": a slot's focus frames, its stored exposure and mode, and a flag of
/// unknown meaning), listed in Compare whenever a memory slot is one of the columns compared, where Edit lists them for
/// that slot, and everything Compare does with a row holding for them.
#[cfg(test)]
pub(crate) mod memory_settings_tests {
    use super::*;
    use crate::test_support::{done, sample_app, strip_menus};

    /// The settings only the memories keep, as Edit shows them outside Expert mode (or in it).
    fn memory_only(app: &App) -> Vec<Setting> {
        app.schema.settings.iter().filter(|s| s.area == "set" && (app.prefs.expert || !App::expert_only(s))).cloned().collect()
    }

    fn keys_in(rows: &[Row]) -> std::collections::HashSet<String> {
        rows.iter().flat_map(|r| r.2.iter().map(|s| s.key.clone())).collect()
    }

    /// Listed where Edit lists them for the slot: with a memory of the menu's own modes among the columns, under the same
    /// entries and groups as Edit's for that memory (a slot registered in Movie under Movie's menu); with the live
    /// settings alone, nowhere; with two slots of different modes, in each of their menus and in no other; in Expert
    /// mode with any memory column in any menu, as Edit offers every set there. No row twice (a tile's records).
    #[test]
    fn memory_only_settings_are_listed_with_a_memory_of_the_menu_among_the_columns() {
        let (mut app, dir, user) = sample_app("cmp_mem_rows", None);
        let mem = memory_only(&app);
        assert_eq!(mem.len(), 57, "the a1 II's settings only the memories keep, outside Expert mode");
        let got = |app: &App, m: &str, e: &BarKey, cols: &[Col]| keys_in(&app.compare_rows_in(Some(m), e, "", cols));
        let none_of = |keys: &std::collections::HashSet<String>| mem.iter().all(|s| !keys.contains(&s.key));
        let all_of = |keys: &std::collections::HashSet<String>| mem.iter().all(|s| keys.contains(&s.key));
        let (live, still, movie, mixed) = ([Col::a(0)], [Col::a(0), Col::a(1)], [Col::a(0), Col::a(4)], [Col::a(1), Col::a(4)]);
        assert!(none_of(&got(&app, "Still", &BarKey::All, &live)), "the live settings alone hold none of them");
        assert!(all_of(&got(&app, "Still", &BarKey::All, &still)), "a Still memory: every one in the Still menu");
        assert!(none_of(&got(&app, "Movie", &BarKey::All, &still)), "not in the Movie menu, which a Still memory is not in");
        assert!(all_of(&got(&app, "Movie", &BarKey::All, &movie)), "a Movie memory: every one in the Movie menu");
        for m in ["Still", "Movie"] {
            assert!(all_of(&got(&app, m, &BarKey::All, &mixed)), "a Still and a Movie memory: in the {m} menu");
        }
        assert!(none_of(&got(&app, "S&Q", &BarKey::All, &mixed)), "and in no other");
        // under Edit's entries and groups for that memory
        for (m, t) in [("Still", 1), ("Movie", 4)] {
            for tab in ["Shooting", "Focus"] {
                let edit: Vec<(String, String)> = app.tab_groups_in(t, Some(m), tab, "", false).into_iter()
                    .flat_map(|(g, _, rows)| rows.into_iter().flatten().filter(|s| s.area == "set").map(move |s| (g.clone(), s.key)))
                    .collect();
                let cols = [Col::a(0), Col::a(t)];
                let cmp: Vec<(String, String)> = app.compare_rows_in(Some(m), &BarKey::Tab(tab.into()), "", &cols).iter()
                    .flat_map(|r| r.2.iter().filter(|s| s.area == "set").map(|s| (r.1.clone(), s.key.clone())).collect::<Vec<_>>())
                    .collect();
                // Edit's, and besides them only a Main tile's records (a fraction's parts, Expert-only), as All always lists
                let tiles: std::collections::HashSet<String> = app.tile_records("").into_iter().map(|s| s.key).collect();
                assert!(edit.iter().all(|x| cmp.contains(x)), "{m} > {tab}: Edit's rows for memory {t} under the same groups: {edit:?} / {cmp:?}");
                assert!(cmp.iter().all(|x| edit.contains(x) || tiles.contains(&x.1)), "{m} > {tab}: nothing else but a tile's records");
                assert!(!cmp.is_empty());
            }
        }
        // no row twice, a tile's memory records too
        let rows = app.compare_rows_in(Some("Still"), &BarKey::All, "", &still);
        let n: usize = rows.iter().map(|r| r.2.len()).sum();
        assert_eq!(n, keys_in(&rows).len(), "no setting twice in All");
        // Expert mode: any memory column in any menu
        app.prefs.expert = true;
        let mem_x = memory_only(&app);
        let keys = got(&app, "Movie", &BarKey::All, &still);
        assert!(mem_x.iter().all(|s| keys.contains(&s.key)), "Expert mode: a Still memory's in the Movie menu too");
        app.prefs.expert = false;
        // the window's own columns
        app.cols = still.to_vec();
        assert!(all_of(&keys_in(&app.compare_rows(Some("Still"), &BarKey::All, ""))), "the window's Compare, by its columns");
        app.cols = live.to_vec();
        assert!(none_of(&keys_in(&app.compare_rows(Some("Still"), &BarKey::All, ""))));
        done(&dir, &user);
    }

    /// A definition without menus: All settings and the definition's tabs list them with a memory column, under their
    /// own tab and group; with the live settings alone, nowhere.
    #[test]
    fn without_menus_they_are_all_settings_rows_with_a_memory_column() {
        let (app, dir, user) = sample_app("cmp_mem_flat", Some(strip_menus));
        let mem = memory_only(&app);
        let all = keys_in(&app.compare_rows_in(None, &BarKey::All, "", &[Col::a(0), Col::a(1)]));
        assert!(mem.iter().all(|s| all.contains(&s.key)), "missing {:?}", mem.iter().filter(|s| !all.contains(&s.key)).map(|s| &s.key).collect::<Vec<_>>());
        assert!(mem.iter().all(|s| !keys_in(&app.compare_rows_in(None, &BarKey::All, "", &[Col::a(0)])).contains(&s.key)));
        // under the entries Edit lists them in for that memory (each under its definition's group, as Compare without menus
        // groups every row)
        let tiles: std::collections::HashSet<String> = app.tile_records("").into_iter().map(|s| s.key).collect();
        for tab in app.menu_tabs() {
            let edit: std::collections::HashSet<String> = app.tab_groups_in(1, None, &tab, "", false).into_iter()
                .flat_map(|(_, _, rows)| rows.into_iter().flatten().filter(|s| s.area == "set").map(|s| s.key)).collect();
            let rows = app.compare_rows_in(None, &BarKey::Tab(tab.clone()), "", &[Col::a(0), Col::a(1)]);
            let cmp: std::collections::HashSet<String> = rows.iter().flat_map(|r| r.2.iter().filter(|s| s.area == "set").map(|s| s.key.clone())).collect();
            assert!(edit.is_subset(&cmp), "{tab}: Edit's rows for memory 1");
            assert!(cmp.iter().all(|k| edit.contains(k) || tiles.contains(k)), "{tab}: nothing else but a tile's records");
            assert!(rows.iter().all(|r| r.2.iter().filter(|s| s.area == "set").all(|s| r.1 == s.group)), "{tab}: each under its definition's group");
        }
        done(&dir, &user);
    }

    /// Their differences are counted among the slots that keep them: the live settings hold none of them, so a live
    /// baseline is no difference; the first column that keeps a setting is its row's baseline. The cells, the counts and
    /// the window's and the page's marks alike.
    #[test]
    fn memory_only_rows_differ_among_the_slots_never_against_the_live_settings() {
        let (mut app, dir, user) = sample_app("cmp_mem_diff", None);
        let mem = memory_only(&app);
        let x = mem.iter().find(|s| s.key == "set:0x019c").cloned().unwrap();
        let y = mem.iter().find(|s| s.key == "set:0x019e").cloned().unwrap();
        let cols = [Col::a(0), Col::a(1), Col::a(2)];
        let v = app.col_value(Col::a(1), &x).unwrap();
        app.prefs.expert = true;
        assert!(app.apply(vec![Action::Set(2, x.slot(), v + 10)]).is_none());
        app.prefs.expert = false;
        let ix = app.row_info(&cols, None, &x);
        assert_eq!(ix.stored, vec![false, true, true], "the live settings keep none of them");
        assert_eq!(ix.base, Some(1), "the first column that keeps it is the row's baseline");
        assert!(ix.differs && !ix.differs_at(1) && ix.differs_at(2) && !ix.differs_at(0));
        let iy = app.row_info(&cols, None, &y);
        assert!(!iy.differs && !(0..3).any(|i| iy.differs_at(i)), "the same in both memories: no difference, the live baseline holding nothing");
        assert!(app.row_differs(&cols, &x) && !app.row_differs(&cols, &y));
        // the page's cells and counts
        let j: serde_json::Value = serde_json::from_slice(&crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["a", 1], ["a", 2]], "only_diff": false, "entry": "tab:Focus", "menu": "Still" })).body).unwrap();
        let row = |k: &str| j["rows"].as_array().unwrap().iter().find(|r| r["key"] == k).cloned().unwrap_or_else(|| panic!("{k} listed"));
        let (rx, ry) = (row(&x.key), row(&y.key));
        assert_eq!(rx["cells"][0]["stored"], false);
        assert_eq!(rx["cells"][0]["text"], "—");
        assert_eq!((rx["cells"][1]["differs"].as_bool(), rx["cells"][2]["differs"].as_bool()), (Some(false), Some(true)));
        assert_ne!(rx["mark"], "same", "an edit of the second memory: differs");
        assert_eq!(ry["mark"], "same");
        assert_eq!(rx["live"], false, "the page knows the live settings keep none of it");
        done(&dir, &user);
    }

    /// Everything Compare does with a row holds for them: an arrow or the picker copies between the memories (never into
    /// the live settings, which do not keep them), Revert puts a value back, a merge takes B's, the CSV lists them, Open in
    /// Edit opens the memory that keeps them on their row. A box's X and Y and its size are copied one by one, as Edit
    /// writes them (no rule ties them: the definition's frame data is read only to be checked).
    #[test]
    fn everything_compare_does_with_a_row_holds_for_them() {
        let (mut app, dir, user) = sample_app("cmp_mem_ops", None);
        let mem = memory_only(&app);
        let x = mem.iter().find(|s| s.key == "set:0x019c").cloned().unwrap();
        let cols = vec![Col::a(0), Col::a(1), Col::a(2)];
        app.cols = cols.clone();
        let v1 = app.col_value(Col::a(1), &x).unwrap();
        // copy targets and the picker: the other memory, never the live settings
        assert_eq!(app.copy_targets(Col::a(1), &x), vec![Col::a(2)]);
        assert!(!app.cell_editable(Col::a(0), std::slice::from_ref(&x)), "no picker in the live column");
        assert!(app.copy_row(std::slice::from_ref(&x), Col::a(1), Col::a(0)).is_empty(), "nothing into the live settings");
        // an arrow from M2 into M1, then Revert
        app.prefs.expert = true;
        assert!(app.apply(vec![Action::Set(2, x.slot(), v1 + 6)]).is_none());
        app.prefs.expert = false;
        let acts = app.copy_row(std::slice::from_ref(&x), Col::a(2), Col::a(1));
        assert!(!acts.is_empty());
        assert!(app.apply(acts).is_none());
        assert_eq!(app.col_value(Col::a(1), &x), Some(v1 + 6), "copied between the memories");
        let (_, back) = app.cell_revert(std::slice::from_ref(&x), 1);
        assert!(app.apply(back).is_none());
        assert_eq!(app.col_value(Col::a(1), &x), Some(v1), "Revert puts it back");
        // the CSV: the live column empty, the memories' values
        let (csv, _) = app.csv_text_in(Some("Still"), Some((&cols, false, false)), 0, "", &BarKey::Tab("Focus".into()), false);
        let line = csv.lines().find(|l| l.contains(&x.name)).unwrap_or_else(|| panic!("{} in the CSV", x.name));
        assert!(line.split(',').nth(3).is_some_and(|c| c.is_empty() || c == "\"\""), "the live settings keep none of it: {line}");
        // Open in Edit: the memory that keeps it, on its row
        app.open_in_edit_from_compare(&x, 1);
        assert_eq!((app.target, app.item_key.as_deref()), (1, Some(x.key.as_str())));
        app.mode = Mode::Compare;
        // a merge: B's change to a memory's frame comes into A
        let mut b = app.doc.as_ref().unwrap().edited.clone();
        b.sections[1].get_mut(x.id).unwrap().put(x.index, v1 + 2).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        app.base = Some((PathBuf::from("base.DAT"), app.doc.as_ref().unwrap().edited.clone()));
        let three = (Col::base(1), Col::a(1), Col::b(1));
        app.cols = vec![three.0, three.1, three.2];
        let rows = app.compare_rows_in(Some("Still"), &BarKey::Tab("Focus".into()), "", &app.cols.clone());
        assert!(rows.iter().any(|r| r.2[0].key == x.key), "listed with these memory columns");
        let (acts, n) = app.merge_rows(&rows, three, Three::BOnly, three.2);
        assert!(n >= 1 && app.apply(acts).is_none());
        assert_eq!(app.col_value(Col::a(1), &x), Some(v1 + 2), "the merge took B's value");
        done(&dir, &user);
    }

    /// A search that would find one of them with no memory of the menu among the columns says why none is shown.
    #[test]
    fn a_search_says_why_a_memorys_setting_is_not_shown() {
        let (mut app, dir, user) = sample_app("cmp_mem_search", None);
        let note = |app: &App, cols: &[Col], q: &str| app.compare_memory_note(Some("Still"), q, cols);
        let words = note(&app, &[Col::a(0)], "AF point position").expect("a note");
        assert!(words.contains("kept only in the memories"), "{words}");
        assert!(note(&app, &[Col::a(0), Col::a(1)], "AF point position").is_none(), "shown: no note");
        assert!(note(&app, &[Col::a(0)], "").is_none() && note(&app, &[Col::a(0)], "White Balance").is_none(), "no search, or none of them found: no note");
        let j: serde_json::Value = serde_json::from_slice(&crate::web::tests::answer(&mut app, "compare", serde_json::json!({ "cols": [["a", 0], ["a", 1]], "q": "AF point position", "menu": "Movie" })).body).unwrap();
        assert!(j["memory_note"].as_str().is_some_and(|w| w.contains("kept only in the memories")), "the page, in the Movie menu with a Still memory: {}", j["memory_note"]);
        done(&dir, &user);
    }
}
