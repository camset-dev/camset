//! What each record means, written from the mapping work by `kit/schema_update.py` (via `kit/tools/build_docs.py`).

use crate::camset::{CamSet, CamSetError, FileFormat, firmware_number};
use serde::Deserialize;
use std::path::{Path, PathBuf};
use std::sync::Arc;

#[derive(Clone, Debug, Deserialize)]
pub struct Setting {
    pub key: String,
    pub area: String,
    pub id: u16,
    pub name: String,
    pub tab: String,
    pub group: String,
    pub order: i64,
    /// Where the setting sits on the camera's menu: the camera's row labels from its camera group's top row down to the
    /// row it is on (kit/camkit/placement.py), in `row_tab` when that is not `tab`, in `row_group` when that is not
    /// `group`, in `row_mode`'s menu when only
    /// that mode's has the row. Empty when the definition does not place it: then it comes after the camera's rows
    /// (`menu_rows`).
    #[serde(default)]
    pub row: Vec<String>,
    /// The sort key of `row`, one number per label: the top row's position in its tab (the rows only another mode's
    /// menu has slotted in where that menu has them), then each row's among its siblings, so the groups and rows follow
    /// the camera's order.
    #[serde(default)]
    pub row_at: Vec<i64>,
    /// The option of its row's own setting this setting is the choice for ("Continuous Shooting" for the continuous
    /// shooting speed under Drive Mode): shown under that option in the detail panel.
    #[serde(default)]
    pub under_option: Option<String>,
    /// The tab whose menu holds `row`, when it is not `tab` (no row of its own tab is reached by its proofs, one of
    /// another's is): the tab that shows the setting while the rows are laid out as on the camera
    /// (`menu_rows::camera_tab`), in `row_group` there. The flat list, Compare and the exports keep `tab`.
    #[serde(default)]
    pub row_tab: Option<String>,
    /// The camera group whose page holds `row`, by the definition's name for it, when it is not `group` (a screen the
    /// definition keeps as a group of its own, which sits on its row in another group): the group that shows the
    /// setting while the rows are laid out as on the camera (`menu_rows::camera_group`).
    #[serde(default)]
    pub row_group: Option<String>,
    /// The shooting mode whose menu holds `row` ("Movie"), named by the definition, when the Stills menu has no such
    /// row: listed after its group's other rows, under the mode's name (`menu_rows::Line::Mode`).
    #[serde(default)]
    pub row_mode: Option<String>,
    /// Known (file value, label) pairs. Only these are offered for editing by default.
    pub values: Vec<(i64, String)>,
    /// The same values as the camera lays them out when it nests them (`option_tree` in the definition): its main
    /// options in order, each one value or the choices of its own axis (Focus Area's Spot with its sizes). Empty when
    /// the camera lists them flat; `option_tree()` checks it fits `values` before the detail panel uses it.
    #[serde(default)]
    pub option_tree: Vec<OptionNode>,
    /// What the setting is and how it behaves, in plain words: shown in Expert mode only (`note_shown`).
    #[serde(default)]
    pub note: String,
    /// Whether the record also exists in the memory sets.
    pub in_sets: bool,
    /// Shown in Expert mode only: a derived working copy, a flag or an alternate numbering, not a setting of the
    /// camera's menus.
    #[serde(default)]
    pub expert: bool,
    pub scalar: bool,
    /// Record shape the mapping was made on (element size, element count); 0 = unknown.
    #[serde(default)]
    pub size: u16,
    #[serde(default)]
    pub count: u16,
    /// Numeric settings: inclusive [min, max] as stored in the file, and a display unit.
    #[serde(default)]
    pub range: Option<(i64, i64)>,
    #[serde(default)]
    pub unit: String,
    /// Allowed increment within the range (e.g. 250 for Knee Point); values are snapped to it.
    #[serde(default)]
    pub step: Option<i64>,
    /// How a number is shown, when not as stored: the stored number divided by `divide`, with `decimals` decimals,
    /// before `unit` (7500 with divide 100 is "75 %"). Editing takes the shown number and stores it multiplied back.
    #[serde(default)]
    pub shown_as: Option<ShownAs>,
    /// The proofs disagree on this setting: left out of them until a mapper decides (Expert mode says so).
    #[serde(default)]
    pub disputed: bool,
    /// Text settings (e.g. file-name prefix): exact length and allowed characters.
    #[serde(default)]
    pub text: Option<TextRule>,
    /// Greyed-out rule: the camera ignores this setting while another record has certain values.
    #[serde(default)]
    pub inactive_when: Option<InactiveRule>,
    /// For array records: which element this setting is (e.g. 0-10 for PP1-PP11).
    #[serde(default)]
    pub index: Option<u16>,
    /// Values the camera accepts but replaces on load: (written, stored), from verification runs.
    #[serde(default)]
    pub rewritten: Vec<(i64, i64)>,
    /// Values that make the camera reject the whole file, from verification runs.
    #[serde(default)]
    pub refused: Vec<i64>,
    /// When the camera shows something other than the stored value (a physical dial, a mode, a clamp).
    #[serde(default)]
    pub display_rule: String,
    /// Shooting modes in which the menu item appears (Sony Help Guide): "still image, movie, S&Q".
    #[serde(default)]
    pub modes: String,
    /// The code My Menu stores for this setting's menu item (None = cannot be added, or not crawled).
    #[serde(default)]
    pub menu_code: Option<i64>,
    /// Proved on the camera: each option chosen in its own menu, the settings file downloaded and
    /// compared (the mapping kit's pass 2), as the lean definition says it: which values that checked. None = not
    /// proved yet.
    #[serde(default)]
    pub proved: Option<Proved>,
    /// Why no proof can be made, when none can, by kind (`unproved_words`): "not_on_camera" (no menu reaches it on
    /// this body), "skipped" (the owner chose not to prove it), "state" (a working value the camera keeps),
    /// "camera_only" (only the camera's own saves write it), "equipment" (greyed without equipment the camera was
    /// proved without), "network" (changed by hand only) or "unknown" (every row tried left it). None = not proved
    /// yet, or proved.
    #[serde(default)]
    pub unproved_reason: Option<UnprovedReason>,
    /// The memory sets (sections) of a set setting where no proof can reach it, and why; elsewhere it is as
    /// `proved` and `unproved_reason` say.
    #[serde(default)]
    pub unproved_sets: Option<UnprovedSets>,
    /// The settings (keys) the camera keeps at this setting's value (a Picture Profile parameter in use and its stills
    /// and movie copies): in a file the camera wrote, this setting's value is the value of at least one of them, and
    /// where the copies say whose mode they are (`copy_for`) the value of the copy for the mode of the set it is in. An
    /// edit takes the copy for that mode with it, or where no mode is known every copy that held the old value when the
    /// file was opened, in the same step (`App::apply`).
    #[serde(default)]
    pub copies: Vec<String>,
    /// The setting (key) whose value the camera keeps in this one (`copies` on that setting).
    #[serde(default)]
    pub copy_of: Option<String>,
    /// The shooting modes whose value this copy is (`camera.memory_sets.modes` names them): in a set of one of those
    /// modes (`Camera::mode_of`), the camera keeps the setting and this copy as one value. Empty: not said.
    #[serde(default)]
    pub copy_for: Vec<String>,
    /// The values the camera's menus offer under one video system only, by the system's name as the container block
    /// names it (`camera.file.video_system.names`): a value listed under one is offered only in a file saved under
    /// that one, a value listed under none under both. None: every value under both.
    #[serde(default)]
    pub video_system_values: Option<std::collections::BTreeMap<String, Vec<i64>>>,
    /// Values the camera's menus never offer, with why (a list walked whole that never showed them): left out of the
    /// choice even in Expert mode, unless the file holds one now; one marked `held` (a factory value the camera writes
    /// itself, which its list cannot choose back) stays offered.
    #[serde(default)]
    pub not_offered: Vec<NotOffered>,
    /// Help for this setting's menu item: the project's own words in the published schema, or a help
    /// file's (`Schema::apply_help`). Empty = none written.
    #[serde(default)]
    pub help: String,
    /// `help` came from a help file found on this computer (the camera's own text, `Schema::apply_help`), not
    /// from the definition (the project's own words): the editor and the page say which.
    #[serde(skip)]
    pub help_from_file: bool,
    /// The values whose `option_help` came from that help file, value by value; the others' is the definition's
    /// own words. Each option's hover says whose.
    #[serde(skip)]
    pub option_help_from_file: Vec<i64>,
    /// Help for each option, by stored value: the definition's own words, each replaced by a help file's where it
    /// has one for that value (`option_help_from_file`).
    #[serde(default)]
    pub option_help: Vec<(i64, String)>,
}

/// One main option of a setting's `option_tree`: as the camera names it, and either one stored value or the choices on
/// its own axis ([value, label under the option], in the camera's order).
#[derive(Clone, Debug, Deserialize)]
pub struct OptionNode {
    pub label: String,
    #[serde(default)]
    pub value: Option<i64>,
    #[serde(default)]
    pub options: Vec<(i64, String)>,
}

impl OptionNode {
    /// Whether the option opens a choice of its own.
    pub fn is_nest(&self) -> bool {
        !self.options.is_empty()
    }

    /// The stored values the option stands for: its one value, or its choices'.
    pub fn values(&self) -> impl Iterator<Item = i64> + '_ {
        self.value.into_iter().chain(self.options.iter().map(|(v, _)| *v))
    }

    pub fn holds(&self, v: i64) -> bool {
        self.values().any(|x| x == v)
    }

    /// What choosing this option stores: the value held now when it is one of the option's, else its one value or its
    /// first choice among `offered` (the values the editor offers), else its first choice.
    pub fn pick(&self, cur: Option<i64>, offered: &[i64]) -> Option<i64> {
        if let Some(c) = cur.filter(|&c| self.holds(c)) {
            return Some(c);
        }
        self.value.or_else(|| self.options.iter().map(|(v, _)| *v).find(|v| offered.contains(v))).or_else(|| self.options.first().map(|(v, _)| *v))
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct UnprovedSets {
    pub sets: Vec<usize>,
    pub kind: String,
    #[serde(default)]
    pub why: String,
}

/// Why no proof can reach a setting, in a few words, by its kind (`unproved_reason.kind`, the definition schema's); the
/// definition's `why` says it in full on hover. `in_set`: said of one memory set (`unproved_sets`). A kind this editor
/// does not know, from a newer definition, reads as no proof possible.
pub fn unproved_words(kind: &str, in_set: bool) -> String {
    let (words, set_words) = match kind {
        "not_on_camera" => ("Not on this camera", "Not on this camera in this memory set"),
        "skipped" => ("Not proved (skipped)", "Not proved in this memory set (skipped)"),
        "state" => ("Not a menu setting: the camera keeps it", "Not a menu setting in this memory set: the camera keeps it"),
        "camera_only" => ("Written only by the camera's own saves", "Written only by the camera's own saves in this memory set"),
        "equipment" => ("Not proved (needs equipment)", "Not proved in this memory set (needs equipment)"),
        "network" => ("Not proved (network, by hand only)", "Not proved in this memory set (network, by hand only)"),
        "unknown" => ("Not proved (nothing tried moved it)", "Not proved in this memory set (nothing tried moved it)"),
        _ => ("No proof possible", "No proof possible in this memory set"),
    };
    (if in_set { set_words } else { words }).to_string()
}

#[derive(Clone, Debug, Deserialize)]
pub struct UnprovedReason {
    pub kind: String,
    #[serde(default)]
    pub why: String,
}

/// A proof as the lean definition says it (definition format 2): never how, when or in which run it was made, nor
/// where each name came from; that evidence stays with whoever mapped the camera (docs/decisions/0016).
#[derive(Clone, Debug, Deserialize)]
pub struct Proved {
    /// The values a proof on the camera checked: chosen in the menu, or named from the camera's own word.
    #[serde(default)]
    pub values: Vec<i64>,
    /// A scale proved by samples instead, and whether they lie on one line.
    #[serde(default)]
    pub sampled: Option<Sampled>,
}

/// A number shown other than as stored (`Setting::shown_as`): divided by `divide`, with `decimals` decimals.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
pub struct ShownAs {
    pub divide: i64,
    #[serde(default)]
    pub decimals: u32,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Sampled {
    /// The samples lie on one straight line, so the values between are inferred (None: too few to tell).
    #[serde(default)]
    pub linear: Option<bool>,
}

/// A value the camera's menus never offer (`Setting::not_offered`): why in plain words, the menu whose list leaves it
/// out, and whether the camera writes it itself all the same (`held`: the factory value, still offered).
#[derive(Clone, Debug, Deserialize)]
pub struct NotOffered {
    pub value: i64,
    pub label: String,
    #[serde(default)]
    pub why: String,
    #[serde(default)]
    pub menu: String,
    #[serde(default)]
    pub held: bool,
}

#[derive(Clone, Debug, Deserialize)]
pub struct InactiveRule {
    pub record: u16,
    pub name: String,
    /// Inactive while the blocker has one of these values ...
    #[serde(default)]
    pub values: Vec<i64>,
    /// ... or any value except these.
    #[serde(default)]
    pub except: Vec<i64>,
    pub unlock: i64,
    pub unlock_label: String,
}

impl InactiveRule {
    pub fn inactive(&self, blocker: Option<i64>) -> bool {
        match blocker {
            None => false,
            Some(v) => self.values.contains(&v) || (!self.except.is_empty() && !self.except.contains(&v)),
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct TextRule {
    pub min_len: usize,
    pub max_len: usize,
    /// Allowed characters, e.g. "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_".
    pub charset: String,
    #[serde(default)]
    pub uppercase: bool,
}

impl TextRule {
    pub fn check(&self, t: &str) -> Result<(), String> {
        let n = t.chars().count();
        if n < self.min_len || n > self.max_len {
            return Err(if self.min_len == self.max_len { format!("must be exactly {} characters", self.max_len) }
                       else { format!("must be {}-{} characters", self.min_len, self.max_len) });
        }
        if let Some(c) = t.chars().find(|c| !self.charset.contains(*c)) {
            return Err(format!("'{c}' is not allowed (allowed: {})", self.charset));
        }
        Ok(())
    }
}

/// A record layout (one per camera firmware) the mapping is known to be valid for.
#[derive(Clone, Debug, Deserialize)]
pub struct Layout {
    pub signature: String,
    pub model: String,
    pub firmware: String,
    #[serde(default)]
    pub note: String,
}

/// Where a setting lives: record id plus element index for array records.
pub type Slot = (u16, Option<u16>);

/// A note as the window and the web page show it: nothing outside Expert mode (a note is the mapping team's words),
/// its words in Expert mode.
pub fn note_words(note: &str, expert: bool) -> String {
    if expert { note.to_string() } else { String::new() }
}

impl Layout {
    /// Its note as shown (`note_words`).
    pub fn note_shown(&self, expert: bool) -> String {
        note_words(&self.note, expert)
    }
}

impl Setting {
    /// Its note as shown (`note_words`).
    pub fn note_shown(&self, expert: bool) -> String {
        note_words(&self.note, expert)
    }

    /// Whether the camera's menu has no row for it (`unproved_reason.kind` "not_on_camera").
    pub fn not_on_camera(&self) -> bool {
        self.unproved_reason.as_ref().is_some_and(|u| u.kind == "not_on_camera")
    }

    /// One setting kept in several records, shown as one row: the same name in the same place on the camera. A copy the
    /// camera keeps of a setting's value (`copy_of`) is never one of them, though it may share the setting's name and
    /// place (ISO AUTO Max and its stills copy): it is a row of its own, view only, and says whose copy it is.
    pub fn links_with(&self, o: &Setting) -> bool {
        self.key == o.key || (self.name == o.name && self.same_place(o) && self.copy_of.is_none() && o.copy_of.is_none())
    }

    /// The proof state in a few words, and its kind ("ok", "na" no proof can reach it, "no" not proved yet):
    /// one wording for the editor's detail and its web page. The count is of the values a proof checked.
    pub fn proof_badge(&self) -> (String, &'static str) {
        match (&self.proved, &self.unproved_reason) {
            (Some(p), _) if p.sampled.is_some() => ("Proved on the camera (sampled)".into(), "ok"),
            (Some(p), _) => {
                let shown = self.values.iter().filter(|(v, _)| p.values.contains(v)).count();
                let of = self.values.len().max(shown);
                (format!("Proved on the camera ({shown}/{of})"), "ok")
            }
            (None, Some(u)) => (unproved_words(&u.kind, false), "na"),
            (None, None) => ("Not proved on the camera yet".into(), "no"),
        }
    }

    /// Why no proof can reach this setting in one section (a memory set it is not proved in), if so.
    pub fn unproved_in(&self, section: usize) -> Option<&UnprovedSets> {
        self.unproved_sets.as_ref().filter(|u| section > 0 && u.sets.contains(&section))
    }

    /// The proof badge for the setting as one section holds it.
    pub fn proof_badge_in(&self, section: usize) -> (String, &'static str) {
        match self.unproved_in(section) {
            Some(u) => (unproved_words(&u.kind, true), "na"),
            None => self.proof_badge(),
        }
    }

    /// The camera's help for one option, if it was read.
    pub fn option_help(&self, v: i64) -> Option<&str> {
        self.option_help.iter().find(|(x, _)| *x == v).map(|(_, t)| t.as_str())
    }

    pub fn slot(&self) -> Slot {
        (self.id, self.index)
    }

    /// Whether the definition places the setting on a row of the camera's menu (`row`, with a sort key as long).
    pub fn placed(&self) -> bool {
        !self.row.is_empty() && self.row.len() == self.row_at.len()
    }

    /// How many of `row`'s labels lead to the page the setting is on, when it is on one: the rows of its owner's row
    /// and the option (`under_option`, named right after them) whose Right opens a whole page of rows on the camera
    /// (Picture Profile > PP1 > Black Gamma > Level: 2). None for any other setting, a sub-choice shown beside its
    /// option among them (`row` ending at its owner's row).
    pub fn page_prefix(&self) -> Option<usize> {
        let opt = self.under_option.as_deref()?;
        if !self.placed() {
            return None;
        }
        (1..self.row.len().saturating_sub(1)).find(|&p| self.row[p] == opt).map(|p| p + 1)
    }

    /// Whether the setting is on a page an option of its owner's row opens (`page_prefix`), not beside the option.
    pub fn on_page(&self) -> bool {
        self.page_prefix().is_some()
    }

    /// Whether `own` is the row whose option opens the page `self` is on: its row is the rows before the option.
    pub fn page_of(&self, own: &Setting) -> bool {
        self.page_prefix().is_some_and(|n| own.row == self.row[..n - 1] && own.row_at == self.row_at[..n - 1])
    }

    /// On the same row of the camera's menu as `o`, in the same mode's menu (both unplaced counts as the same).
    pub fn same_row(&self, o: &Setting) -> bool {
        self.row == o.row && self.row_at == o.row_at && self.row_mode == o.row_mode
    }

    /// In the same place as `o`: the same row and the same option, so the two can be one setting kept in several
    /// records (one row of linked records in the editor).
    pub fn same_place(&self, o: &Setting) -> bool {
        self.same_row(o) && self.under_option == o.under_option
    }

    /// Hex record ID like "0x01d8" or "0x05db[0]" (for indexed array records).
    pub fn record_id_hex(&self) -> String {
        match self.index {
            Some(i) => format!("0x{:04x}[{i}]", self.id),
            None => format!("0x{:04x}", self.id),
        }
    }

    /// A stored number as shown (`shown_as`): 7500 divided by 100 with no decimals is "75", 3 by 10 with one "0.3";
    /// with more decimals when `decimals` would round it (9250 by 100 is "92.5", a step of 250 "2.5"), so no number
    /// shown stands for two stored ones. The number itself when the definition says nothing.
    pub fn shown_number(&self, v: i64) -> String {
        match self.shown_as.filter(|a| a.divide > 0) {
            Some(a) => {
                let mut d = a.decimals.min(9);
                while d < 9 && (v as i128 * 10i128.pow(d)) % a.divide as i128 != 0 {
                    d += 1;
                }
                format!("{:.*}", d as usize, v as f64 / a.divide as f64)
            }
            None => v.to_string(),
        }
    }

    /// A stored number as shown with its unit: "75 %", or the shown number alone when there is no unit.
    pub fn shown_value(&self, v: i64) -> String {
        if self.unit.is_empty() { self.shown_number(v) } else { format!("{} {}", self.shown_number(v), self.unit) }
    }

    /// The number stored for a shown one ("75", "75 %", "0,3"): multiplied back by `shown_as`'s divide and rounded;
    /// None when it is no number.
    pub fn stored_number(&self, shown: &str) -> Option<i64> {
        let t = shown.trim();
        let t = t.strip_suffix(self.unit.as_str()).filter(|_| !self.unit.is_empty()).unwrap_or(t).trim().replace(',', ".");
        let x: f64 = t.parse().ok().filter(|x: &f64| x.is_finite())?;
        let d = self.shown_as.filter(|a| a.divide > 0).map_or(1, |a| a.divide);
        Some((x * d as f64).round() as i64)
    }

    pub fn label_for(&self, v: i64) -> Option<&str> {
        self.values.iter().find(|(k, _)| *k == v).map(|(_, l)| l.as_str())
    }

    /// The options as the camera nests them, when the definition's `option_tree` fits the values: each value in it
    /// exactly once, every value there, each option one value or two choices and more, and one option with choices.
    /// None means the flat list.
    pub fn option_tree(&self) -> Option<&[OptionNode]> {
        let tree = &self.option_tree;
        if !tree.iter().any(OptionNode::is_nest) || tree.iter().any(|n| n.value.is_some() == n.is_nest() || n.options.len() == 1) {
            return None;
        }
        let mut held: Vec<i64> = tree.iter().flat_map(OptionNode::values).collect();
        let n = held.len();
        held.sort_unstable();
        held.dedup();
        let mut all: Vec<i64> = self.values.iter().map(|(v, _)| *v).collect();
        all.sort_unstable();
        all.dedup();
        (held.len() == n && held == all).then_some(tree.as_slice())
    }

    /// Whether the option tree shows `option`'s choices itself: a main option of that name with choices, or one whose
    /// choices hold the value of that flat label. A setting placed under such an option (`under_option`) is then not
    /// shown under it a second time.
    pub fn nests_option(&self, option: &str) -> bool {
        self.option_tree().is_some_and(|t| t.iter().filter(|n| n.is_nest()).any(|n| {
            n.label == option || n.options.iter().any(|(v, _)| self.label_for(*v) == Some(option))
        }))
    }

    /// Whether a proof on the camera established `v`, the editor's gate outside Expert mode: true for every value of a
    /// setting with no proof (nothing is known of it, so nothing is held back). In a proved setting, a scale proved by
    /// samples on a straight line (`proved.sampled.linear`) establishes every value, and a range every number in it;
    /// otherwise `v` is established when its proof checked it (`proved.values`: the kit lists there every value a
    /// proof chose and every one it named from the camera's own word, never a name kept from the old schema).
    pub fn established(&self, v: i64) -> bool {
        let Some(p) = &self.proved else { return true };
        p.sampled.as_ref().is_some_and(|s| s.linear == Some(true)) || p.values.contains(&v)
    }

    /// Whether a proof on the camera checked `v` in `section` (0, the live settings, or a memory set): the setting is
    /// proved, not disputed, not one no proof reaches in that set (`unproved_sets`), and its proof established `v`. The
    /// write and save windows judge an edit by it. Unlike `established`, which lets every value of a setting with no
    /// proof be offered (nothing is known of it, so nothing is held back), a setting with no proof checks nothing.
    pub fn checked_on_camera(&self, v: i64, section: usize) -> bool {
        self.proved.is_some() && !self.disputed && self.unproved_in(section).is_none() && self.established(v)
    }

    /// Why no menu of the camera writes this setting in `section`, when none does: the definition's words for
    /// `unproved_reason` (kind "not_on_camera"), or for the memory sets no proof reaches (`unproved_sets`, the same
    /// kind). None when a menu writes it there.
    pub fn not_on_camera_in(&self, section: usize) -> Option<&str> {
        if let Some(u) = self.unproved_in(section).filter(|u| u.kind == "not_on_camera") {
            return Some(u.why.as_str());
        }
        self.unproved_reason.as_ref().filter(|u| u.kind == "not_on_camera").map(|u| u.why.as_str())
    }

    /// The video system `v` belongs to when it is not `system` (`video_system_values`): the first system whose list
    /// holds `v`, when some list holds it and `system`'s does not. None when `system` is not known, when its list holds
    /// `v`, or when no list does (a value offered under both).
    pub fn other_system(&self, v: i64, system: Option<&str>) -> Option<&str> {
        let lists = self.video_system_values.as_ref()?;
        let system = system?;
        if lists.get(system).is_some_and(|l| l.contains(&v)) {
            return None;
        }
        lists.iter().find(|(_, l)| l.contains(&v)).map(|(k, _)| k.as_str())
    }

    /// What the camera stores for a written value, when a verification run saw it replaced.
    pub fn rewrite_of(&self, v: i64) -> Option<i64> {
        self.rewritten.iter().find(|(w, _)| *w == v).map(|(_, s)| *s)
    }

    /// Why the camera may not take this value, if there is a reason: refused, rewritten, never offered by its menus,
    /// or established by no proof on the camera (`established`).
    pub fn acceptance(&self, v: i64) -> Option<String> {
        if self.refused.contains(&v) {
            return Some("the camera refuses files holding this value".into());
        }
        if let Some(s) = self.rewrite_of(v) {
            return Some(format!("the camera stores {} instead", self.label_for(s).map(str::to_string).unwrap_or_else(|| s.to_string())));
        }
        if self.never_offered(v).is_some() {
            return Some("the camera's menus never offer this value; the camera may refuse a file holding it".into());
        }
        if !self.established(v) {
            return Some("not checked on the camera yet; the camera may refuse a file holding it".into());
        }
        None
    }

    /// Why the camera's menus never offer `v`, when the definition says so (`not_offered`) and the camera does not write
    /// it itself all the same (a `held` value, the factory one, stays offered).
    pub fn never_offered(&self, v: i64) -> Option<&NotOffered> {
        self.not_offered.iter().find(|n| n.value == v && !n.held)
    }

    /// Whether `v` is one the editor offers when the person asks for every value: any but one the menus never offer.
    pub fn offerable(&self, v: i64) -> bool {
        self.never_offered(v).is_none()
    }

    /// The (value, label) pairs to offer: those a proof established (`established`), or all of them when `all` is set;
    /// never one the camera's menus never offer (`never_offered`), whatever `all` says. A caller that shows the value
    /// held now adds it.
    pub fn offered(&self, all: bool) -> Vec<(i64, String)> {
        self.values.iter().filter(|(v, _)| self.offerable(*v) && (all || self.established(*v))).cloned().collect()
    }

    /// How many values `offered` leaves out because no proof on the camera established them, Expert mode's "Offer
    /// values…" bringing them back; those the menus never offer are not counted, for nothing brings them back.
    pub fn hidden_unproved(&self, all: bool) -> usize {
        self.values.iter().filter(|(v, _)| self.offerable(*v) && !all && !self.established(*v)).count()
    }
}

/// A camera definition (editor/definitions/<model>_fw<firmware>.json): what every record of one model and firmware's
/// settings file means. `Schema::default()` is no definition at all: no tabs, no settings, nothing named.
#[derive(Clone, Debug, Default, Deserialize)]
pub struct Schema {
    /// The layout of the definition file itself (`DEFINITION_FORMAT`).
    pub definition_format: u32,
    pub model: String,
    pub tabs: Vec<String>,
    /// The one record layout the definition was checked on (exactly one: `Schema::check`).
    pub layouts: Vec<Layout>,
    pub settings: Vec<Setting>,
    /// Everything the editor knows about this camera body beyond its settings. A missing part
    /// hides the feature it drives.
    #[serde(default)]
    pub camera: Camera,
    /// The help file whose text replaced the schema's, and who wrote it; empty = the schema's own.
    #[serde(skip)]
    pub help_src: String,
    /// Help files found under this definition's help file name but not used, and why in plain words: another
    /// camera's (their own model and firmware decide, not their name), or not a help file (`Schema::apply_help`).
    #[serde(skip)]
    pub help_refused: Vec<(PathBuf, String)>,
    /// Where the definition was read from.
    #[serde(skip)]
    pub origin: Origin,
    /// A definition of the user's that is used in place of a shipped one of the same model and firmware, or the
    /// shipped one so replaced.
    #[serde(skip)]
    pub overrides: bool,
    #[serde(skip)]
    pub overridden: bool,
}

/// The definition layout this editor reads. A definition of a newer format is refused with a clear message instead
/// of being misread (docs/decisions/0019). 2: the lean definition (its proofs say which values they checked, never
/// how, when or from which state; the evidence stays with whoever mapped the camera, docs/decisions/0016).
pub const DEFINITION_FORMAT: u32 = 2;

/// The oldest definition layout this editor reads: a format-1 definition carries the mapping's evidence and names its
/// checked values another way, so it is refused with what to do (write it again with the kit).
pub const OLDEST_DEFINITION_FORMAT: u32 = 2;

/// Where a definition was found: among the ones shipped with the editor (read-only), or in the user's own folder,
/// `definitions/` beside the preferences (the only folder the editor writes).
#[derive(Clone, Debug, Default, PartialEq, Eq, Hash)]
pub enum Origin {
    #[default]
    None,
    Shipped(PathBuf),
    User(PathBuf),
}

impl Origin {
    pub fn path(&self) -> Option<&Path> {
        match self {
            Origin::None => None,
            Origin::Shipped(p) | Origin::User(p) => Some(p),
        }
    }

    /// How Settings names it: "built-in" or "yours".
    pub fn word(&self) -> &'static str {
        match self {
            Origin::None => "none",
            Origin::Shipped(_) => "built-in",
            Origin::User(_) => "yours",
        }
    }

    pub fn is_shipped(&self) -> bool {
        matches!(self, Origin::Shipped(_))
    }
}

/// A help text file (schemas/help-file.schema.json): each setting's help by key, for one model and
/// firmware. The published schema carries the project's own words; a help file found on this computer
/// (the camera's own In-Camera Guide text, which is Sony's and kept privately) is shown in their place, only when
/// its own `model` and `firmware` are the definition's (`Schema::help_refusal`): setting keys can be the same on two
/// Sony bodies, so another camera's text would attach to the wrong settings.
#[derive(Clone, Debug, Default, Deserialize)]
pub struct HelpFile {
    /// The model and firmware the file says it is for; empty = it does not say, and it is not used.
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub firmware: String,
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub settings: std::collections::HashMap<String, HelpText>,
}

#[derive(Clone, Debug, Default, Deserialize)]
pub struct HelpText {
    #[serde(default)]
    pub help: String,
    #[serde(default)]
    pub option_help: Vec<(i64, String)>,
}

/// The editor's own folder (preferences, help files): camset_editor in $XDG_CONFIG_HOME, %APPDATA%
/// or ~/.config.
pub fn config_dir() -> PathBuf {
    config_dir_from(&|k| std::env::var_os(k))
}

/// `config_dir` with the environment as `var` gives it. An empty or relative value is not taken (as the XDG rules
/// say): it would put the editor's folder wherever the editor happens to be started.
fn config_dir_from(var: &dyn Fn(&str) -> Option<std::ffi::OsString>) -> PathBuf {
    let abs = |k: &str| var(k).map(PathBuf::from).filter(|p| p.is_absolute());
    let base = abs("XDG_CONFIG_HOME").or_else(|| abs("APPDATA")).or_else(|| abs("HOME").map(|h| h.join(".config")))
        .unwrap_or_else(|| PathBuf::from("."));
    base.join("camset_editor")
}

/// Camera-specific facts, from the camera's definition file (data/<model>_fw<fw>/camera_<model>_fw<fw>.json in the kit).
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Camera {
    /// Model name written in the file header (e.g. "ILCE-1M2").
    pub model: Option<String>,
    /// The name photographers know the camera by ("α1 II"), shown beside the model code; None: the code alone.
    pub display_name: Option<String>,
    /// Record count of every section (live settings first, then the memory sets).
    pub section_counts: Vec<usize>,
    /// The container the camera writes its settings in (docs/decisions/0020). None: the definition describes no
    /// file, so none opens with it.
    pub file: Option<FileFormat>,
    pub main_tiles: Option<MainTiles>,
    pub my_menu: Option<MyMenu>,
    pub memory_sets: Option<MemorySets>,
    /// Records the camera keeps as copies of each other; none: nothing is copied.
    pub mirrors: Vec<Mirror>,
    /// The live record that says which shooting mode a file was saved in, and the mode each of its values means: the
    /// mode of the live settings (`Camera::mode_of`). None: not known.
    pub live_mode: Option<LiveMode>,
    /// How long the camera link usually takes with this body.
    pub link_timing: Option<LinkTiming>,
    /// A settings file of this camera beside the definition, one it wrote with its personal text removed: Explore a
    /// sample opens it.
    pub sample: Option<String>,
    /// The name Save As offers when none of the camera's own is free; None: the file's own name.
    pub save_name: Option<SaveName>,
    /// Records that decide whether the camera stays reachable after loading a file.
    pub link_records: Vec<LinkRecord>,
    /// Live records the camera changes on every load (ignored when a read-back is compared).
    pub volatile_records: Vec<u16>,
    /// Menu tab colours, [r, g, b] by tab name (grey when missing).
    pub tab_colors: std::collections::BTreeMap<String, [u8; 3]>,
    /// Array settings shown as one table each (Picture Profiles, Creative Looks...).
    pub families: Vec<Family>,
    /// Camera wording used in hints and warnings.
    pub text: CameraText,
    /// The exposure page: which records hold each side of the exposure triangle and who sets it
    /// in each exposure mode. None = no exposure page.
    pub exposure: Option<Exposure>,
}

/// The exposure page's definition. Keys are setting keys from the schema; an empty key means the
/// file does not store that value there (`ExposureSide::live_note` says why).
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Exposure {
    pub title: String,
    /// The exposure mode in the live settings and in a memory set.
    pub mode_key: String,
    pub memory_mode_key: String,
    /// What the live mode record holds, shown under it (e.g. the mode dial's position).
    pub mode_note: String,
    /// Who sets the aperture and the shutter in each mode, by the mode record's label.
    pub control: std::collections::BTreeMap<String, Control>,
    pub aperture: ExposureSide,
    pub shutter: ExposureSide,
    pub iso: ExposureSide,
    /// Exposure compensation and its step.
    pub comp_key: String,
    pub step_key: String,
    /// The page's columns; empty: the live settings and the dial's memories.
    pub sections: Vec<usize>,
}

/// "you" or "camera" for the aperture, the shutter and (optionally) ISO in one exposure mode.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Control {
    pub aperture: String,
    pub shutter: String,
    /// Empty: the camera sets ISO when it holds its AUTO value (`ExposureSide::auto_value`), else you do.
    pub iso: String,
}

/// One side of the triangle: where its value is stored, the scale it is drawn on, and the limits
/// on what the camera may choose for it.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct ExposureSide {
    pub key: String,
    pub memory_key: String,
    /// A time stored as a fraction (seconds = numerator / denominator), in a memory set.
    pub memory_numerator_key: String,
    pub memory_denominator_key: String,
    /// The record whose value labels span the scale (its lowest and highest stops).
    pub scale_key: String,
    /// The value that hands this side to the camera (ISO AUTO).
    pub auto_value: Option<i64>,
    pub limits: Vec<ExposureLimit>,
    /// Why the live settings hold no value for this side ("on the camera's dials, not in the file").
    pub live_note: String,
}

/// A limit on one side: a range (min_key..max_key) or one bound (key), in force "always", while
/// the camera sets the side ("camera"), or while it does and ISO is on AUTO ("camera_iso_auto").
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct ExposureLimit {
    pub name: String,
    pub min_key: String,
    pub max_key: String,
    pub key: String,
    pub applies: String,
    /// How a single bound reads on the scale, e.g. "slowest".
    pub bound: String,
}

/// Groups whose name starts with `prefix` are shown together as one table titled `title`.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Family {
    pub prefix: String,
    /// How the family is shown; only "table" so far.
    pub kind: String,
    pub title: String,
    /// Each column's title: "group_suffix" the last word of its group's name ("PP3"), else the whole name.
    pub column_label: String,
    /// A line under the table.
    pub note: String,
}

impl Family {
    /// A column's title from its group's name.
    pub fn column_title(&self, group: &str) -> String {
        if self.column_label == "group_suffix" { group.rsplit(' ').next().unwrap_or("").to_string() } else { group.to_string() }
    }
}

/// Camera wording; every field is optional and the editor words things generically without it.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct CameraText {
    /// A menu tab whose items cannot be added to My Menu, and why.
    pub mymenu_excluded_tab: Option<String>,
    pub mymenu_excluded_reason: Option<String>,
    /// The camera menu item that registers the live settings into a memory.
    pub memory_register_menu: Option<String>,
    /// What recalls memory {m} on the camera, e.g. "turning the dial to {m}".
    pub memory_dial_hint: Option<String>,
    /// The Memories page's title, "{list}" standing for the dial's memories ("Memories {list}": "Memories 1, 2, 3"),
    /// and what it says the memories are.
    pub memories_title: Option<String>,
    pub memories_intro: Option<String>,
    /// Where the camera saves a settings file.
    pub save_load_path: Option<String>,
    /// How many settings files the camera's Load list shows.
    pub max_settings_files_on_card: Option<usize>,
    /// The folder on the card that holds the settings files, with "/" between folders (the editor's default:
    /// PRIVATE/SONY/CAMSET).
    pub card_folder: Option<String>,
    /// How the camera names a settings file, "nn" standing for its two-digit number (the editor's default:
    /// CAMSETnn.DAT).
    pub settings_file_name: Option<String>,
    /// Connect dialog: what to set on the camera for each link, a note under the network steps,
    /// and where the camera shows its network address. Generic steps are shown without them.
    pub connect_usb_steps: Vec<String>,
    pub connect_network_steps: Vec<String>,
    pub connect_network_note: Option<String>,
    pub address_hint: Option<String>,
    /// What to check after a read failed and the camera link named no cause, over USB and over the network.
    pub read_failed_usb: Option<String>,
    pub read_failed_network: Option<String>,
    /// Said when only the records the camera changes on every load differ after a write; "{n}" is how many.
    pub volatile_note: Option<String>,
    /// Where a setting's shooting modes ("Applies in") come from.
    pub modes_source: Option<String>,
    /// The Main page's name and My Menu's, as the camera calls them.
    pub main_title: Option<String>,
    pub my_menu_name: Option<String>,
    /// The Menu's entry for the settings the camera's menus do not hold (the editor's "Not in the menus" without it).
    pub off_menu_name: Option<String>,
}

impl CameraText {
    /// The Main page's name ("Main").
    pub fn main_title(&self) -> &str {
        self.main_title.as_deref().filter(|t| !t.is_empty()).unwrap_or("Main")
    }

    /// My Menu's name ("My Menu").
    pub fn my_menu_name(&self) -> &str {
        self.my_menu_name.as_deref().filter(|t| !t.is_empty()).unwrap_or("My Menu")
    }

    /// The Menu's entry for the settings the camera's menus do not hold ("Not in the menus").
    pub fn off_menu_name(&self) -> &str {
        self.off_menu_name.as_deref().filter(|t| !t.is_empty()).unwrap_or("Not in the menus")
    }
}

/// How long the camera link usually takes, in seconds. Without the definition's, the link's usual times.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(default)]
pub struct LinkTiming {
    /// A read, until this computer has timed its own (the editor then names the median of its last reads).
    pub read_s: u32,
    /// How long after an upload the camera is usually back: the first try to read it back starts then.
    pub restart_s: u32,
    /// After a try to read it back that failed, the next starts once this has passed since that one began (at once
    /// when the try took longer).
    pub poll_s: u32,
    /// When to give up reading the camera back, counted from the end of the upload.
    pub timeout_s: u32,
}

impl Default for LinkTiming {
    /// A camera whose definition names no times: the times measured on a body back 28 s after an upload (so a
    /// restart of 30). A slower body costs only a failed try or two, `poll_s` apart, before it answers; a faster one
    /// would cost the wait.
    fn default() -> Self {
        LinkTiming { read_s: 5, restart_s: 30, poll_s: 8, timeout_s: 180 }
    }
}

/// The name Save As offers when it finds none of the camera's own free: the opened file's name cut to `stem_chars`
/// characters, upper case, then `suffix`.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct SaveName {
    pub stem_chars: usize,
    pub suffix: String,
}

/// The camera's Main page tiles, left to right, top to bottom.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct MainTiles(pub Vec<TileSet>);

/// One Main page of the camera (e.g. Stills, Movie, S&Q): its name and tiles.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct TileSet {
    pub name: String,
    pub tiles: Vec<Tile>,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TileKind {
    /// Fixed settings (`keys`).
    #[default]
    Keys,
    /// `keys` in the live settings, `memory_keys` in a memory set.
    LiveOrMemory,
    /// A fraction stored in memory sets only (shutter speed): n/d, or n" when d is 1.
    Fraction,
}

/// One Main page tile; keys are setting keys from the schema.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Tile {
    pub caption: String,
    pub kind: TileKind,
    pub keys: Vec<String>,
    pub memory_keys: Vec<String>,
    pub numerator_key: Option<String>,
    pub denominator_key: Option<String>,
    /// What the tile shows in the live settings when they hold no value for it ("not stored (live)").
    pub live_text: String,
}

impl Tile {
    /// The setting keys the tile shows when editing `target` (0 = live settings).
    pub fn keys_for(&self, target: usize) -> Vec<&str> {
        match self.kind {
            TileKind::Keys => self.keys.iter().map(String::as_str).collect(),
            TileKind::LiveOrMemory => if target == 0 { &self.keys } else { &self.memory_keys }.iter().map(String::as_str).collect(),
            TileKind::Fraction => if target == 0 { vec![] } else { self.numerator_key.iter().chain(&self.denominator_key).map(String::as_str).collect() },
        }
    }
}

/// My Menu: one array record per page in the live settings.
#[derive(Clone, Debug, Deserialize)]
#[serde(default)]
pub struct MyMenu {
    pub records: Vec<u16>,
    /// The code of an empty slot.
    pub empty: i64,
    pub max_items: usize,
    /// The camera keeps the items packed from the top: adding fills the first empty slot, removing closes the gap.
    /// False: removing only empties the slot.
    pub packed: bool,
}

impl Default for MyMenu {
    fn default() -> Self {
        MyMenu { records: Vec::new(), empty: 0, max_items: 0, packed: true }
    }
}

/// The memory sets on the mode dial and how the others are named.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct MemorySets {
    /// Sections the mode dial recalls (1 = the first memory set).
    pub dial: Vec<usize>,
    /// The memory sets of each shooting mode, by mode ("Stills": [1, 2, 3], "Movie": [4, 5, 6], …). Ordered by
    /// their first set where an order is needed (`Camera::modes`).
    pub modes: std::collections::BTreeMap<String, Vec<usize>>,
    pub names: std::collections::BTreeMap<String, String>,
    /// Name of the other memory sets: "<prefix> <n>".
    pub other_prefix: String,
    /// Short column labels by section ("1": "M1"); a section left out is "M<n>" on the dial, "S<n>" off it.
    pub short_names: std::collections::BTreeMap<String, String>,
    /// The sections Compare starts with (0 = the live settings); empty: the live settings and the dial's memories.
    pub default_columns: Vec<usize>,
}

/// The live record that says which shooting mode a file was saved in (`Camera::live_mode`): the setting's key, and the
/// mode each value means, by the value written as a number ("1": "Movie"), the modes named as `memory_sets.modes` names
/// them.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct LiveMode {
    pub key: String,
    pub modes: std::collections::BTreeMap<String, String>,
}

/// Two records the camera keeps as copies of each other (docs/decisions/0020): a live record holding one element
/// per memory set, and the same block in each set. A write to either is made to the other too.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Mirror {
    /// What the copies are, in words, for the note when a file does not hold them as the definition says.
    pub what: String,
    pub live_record: u16,
    pub set_record: u16,
    /// Bytes per element; None: the live record's element size in the file.
    pub element_bytes: Option<usize>,
    /// The section the live record's first element is the copy of.
    pub first_section: usize,
    /// The sections that hold a copy.
    pub sections: Vec<usize>,
}

impl Mirror {
    /// The element size, when `c` holds both records as the mirror needs them: the live record as one element of
    /// that size per section listed, and each of those sections' record of that size. None: the mirror is off for
    /// this file.
    pub fn stride_in(&self, c: &CamSet) -> Option<usize> {
        let live = c.sections.first()?.get(self.live_record)?;
        let stride = self.element_bytes.unwrap_or(live.elem_size as usize);
        if stride == 0 || self.sections.is_empty() || live.value.len() != self.sections.len() * stride {
            return None;
        }
        for &s in &self.sections {
            if s < self.first_section || c.sections.get(s)?.get(self.set_record)?.value.len() != stride {
                return None;
            }
        }
        Some(stride)
    }

    /// The other place of bytes [`at`, `at + n`) of record `id` in section `sec`: (section, record, offset).
    fn other_place(&self, sec: usize, id: u16, at: usize, n: usize, stride: usize) -> Option<(usize, u16, usize)> {
        if sec == 0 && id == self.live_record {
            let s = self.first_section + at / stride;
            (self.sections.contains(&s) && at % stride + n <= stride).then_some((s, self.set_record, at % stride))
        } else if sec != 0 && id == self.set_record && self.sections.contains(&sec) && at + n <= stride {
            Some((0, self.live_record, (sec - self.first_section) * stride + at))
        } else {
            None
        }
    }

    /// Whether byte `at` of record `id` in section `sec` is one the mirror keeps a copy of in `c`, and holds what that
    /// copy holds.
    pub fn in_step(&self, c: &CamSet, sec: usize, id: u16, at: usize) -> bool {
        let Some(stride) = self.stride_in(c) else { return false };
        let Some((s2, id2, at2)) = self.other_place(sec, id, at, 1, stride) else { return false };
        let byte = |s: usize, i: u16, a: usize| c.sections.get(s).and_then(|x| x.get(i)).and_then(|r| r.value.get(a)).copied();
        byte(sec, id, at).is_some() && byte(sec, id, at) == byte(s2, id2, at2)
    }

    /// After bytes [`at`, `at + n`) of record `id` in section `sec` were written: the same bytes in the copy.
    pub fn sync_bytes(&self, c: &mut CamSet, sec: usize, id: u16, at: usize, n: usize, stride: usize) {
        let Some((s2, id2, at2)) = self.other_place(sec, id, at, n, stride) else { return };
        let Some(bytes) = c.sections.get(sec).and_then(|x| x.get(id)).and_then(|r| r.value.get(at..at + n)).map(<[u8]>::to_vec) else { return };
        if let Some(dst) = c.sections.get_mut(s2).and_then(|x| x.get_mut(id2)).and_then(|r| r.value.get_mut(at2..at2 + n)) {
            dst.copy_from_slice(&bytes);
        }
    }

    /// After record `id` of section `sec` was replaced whole: every element of it in its copies.
    pub fn sync_record(&self, c: &mut CamSet, sec: usize, id: u16, stride: usize) {
        if sec == 0 && id == self.live_record {
            for &s in &self.sections {
                self.sync_bytes(c, 0, id, (s - self.first_section) * stride, stride, stride);
            }
        } else {
            self.sync_bytes(c, sec, id, 0, stride, stride);
        }
    }
}

/// A live record that can cut the link the editor uses. Records sharing a `group` warn only when
/// all of them are outside their ok values; a record without a group warns on its own.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct LinkRecord {
    pub record: u16,
    pub name: String,
    /// "network" or "usb".
    pub link: String,
    pub ok_values: Vec<i64>,
    pub group: Option<String>,
    pub message: String,
}

impl Camera {
    pub fn dial(&self) -> &[usize] {
        self.memory_sets.as_ref().map_or(&[], |m| m.dial.as_slice())
    }
    pub fn is_dial(&self, section: usize) -> bool {
        self.dial().contains(&section)
    }
    /// Display name of a file section: live settings, a dial memory or another memory set.
    pub fn target_name(&self, section: usize) -> String {
        if section == 0 {
            return "Live settings".into();
        }
        match &self.memory_sets {
            Some(m) => m.names.get(&section.to_string()).cloned()
                .unwrap_or_else(|| format!("{} {section}", if m.other_prefix.is_empty() { "Set" } else { &m.other_prefix })),
            None => format!("Set {section}"),
        }
    }
    /// Short column label: Live, else the definition's (`memory_sets.short_names`), else M<n> for dial memories and
    /// S<n> for the other sets.
    pub fn short_name(&self, section: usize) -> String {
        if let Some(s) = self.memory_sets.as_ref().and_then(|m| m.short_names.get(&section.to_string())).filter(|s| !s.is_empty()) {
            return s.clone();
        }
        match section {
            0 => "Live".into(),
            n if self.is_dial(n) => format!("M{n}"),
            n => format!("S{n}"),
        }
    }

    /// The shooting mode of a memory set (1 = the first): the mode `memory_sets.modes` lists it under. The live
    /// settings' mode is in the file itself (`live_mode`), so it is None here for set 0, as for a set no mode lists.
    pub fn memory_mode(&self, section: usize) -> Option<&str> {
        if section == 0 {
            return None;
        }
        self.memory_sets.as_ref()?.modes.iter().find(|(_, sets)| sets.contains(&section)).map(|(m, _)| m.as_str())
    }

    /// The shooting modes' memory sets, ordered by their first set ("Stills" 1-3, "Movie" 4-6, …).
    pub fn modes(&self) -> Vec<(&str, &[usize])> {
        let mut v: Vec<(&str, &[usize])> = self.memory_sets.as_ref().map(|m| m.modes.iter().map(|(k, s)| (k.as_str(), s.as_slice())).collect()).unwrap_or_default();
        v.sort_by_key(|(_, s)| s.iter().min().copied().unwrap_or(usize::MAX));
        v
    }

    /// The columns Compare starts with: the definition's `default_columns`, else the live settings and the dial's
    /// memories; with `more`, the second shooting mode's memories too (`modes`).
    pub fn start_columns(&self, more: bool) -> Vec<usize> {
        let mut v: Vec<usize> = match self.memory_sets.as_ref().map(|m| m.default_columns.clone()).filter(|c| !c.is_empty()) {
            Some(c) => c,
            None => std::iter::once(0).chain(self.dial().iter().copied()).collect(),
        };
        if more {
            if let Some((_, sets)) = self.modes().get(1) {
                v.extend(sets.iter().filter(|s| !v.contains(s)).copied().collect::<Vec<_>>());
            }
        }
        v
    }

    /// The first two shooting modes' names, for the switch that adds the second's memories to Compare's columns;
    /// None with fewer than two modes.
    pub fn more_columns_modes(&self) -> Option<(String, String)> {
        let m = self.modes();
        Some((m.first()?.0.to_string(), m.get(1)?.0.to_string()))
    }
    /// Whether a file matches this camera's model and section sizes. Parts the definition leaves out are not checked
    /// (the layout signature still has to match); the container is, as the file is read with the block.
    pub fn knows(&self, c: &crate::camset::CamSet) -> bool {
        c.is_known_layout_for(self.model.as_deref(), &self.section_counts)
    }
    /// Messages for every link record that would cut `link` ("network" or "usb"), given the
    /// live value of a record.
    pub fn link_warnings(&self, link: &str, live: impl Fn(u16) -> Option<i64>) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        let recs: Vec<&LinkRecord> = self.link_records.iter().filter(|r| r.link == link).collect();
        let fails = |r: &LinkRecord| live(r.record).is_some_and(|v| !r.ok_values.contains(&v));
        for r in &recs {
            let warn = match &r.group {
                Some(g) => recs.iter().filter(|x| x.group.as_ref() == Some(g)).all(|x| fails(x)),
                None => fails(r),
            };
            if warn && !out.contains(&r.message) {
                out.push(r.message.clone());
            }
        }
        out
    }
}

/// Where the definitions shipped with the editor are looked for, in order: $CAMSET_DEFINITIONS_DIR; `definitions/`
/// beside the program (the Windows zip, the Linux tarball and install); the app's Resources/definitions (macOS); and,
/// running from a checkout, editor/definitions, the program being editor/target/<profile>/camset_editor. Only
/// places found from the program itself: a `definitions/` folder wherever the editor happens to be started is not
/// taken for the shipped set.
pub fn shipped_dirs() -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = std::env::var_os("CAMSET_DEFINITIONS_DIR").map(PathBuf::from).into_iter().collect();
    // the program as it was started, and with links followed (a link in ~/.local/bin, say; macOS keeps the link)
    let exe = std::env::current_exe().ok();
    let real = exe.as_deref().and_then(|e| std::fs::canonicalize(e).ok());
    for dir in [real.as_deref(), exe.as_deref()].into_iter().flatten().filter_map(Path::parent) {
        for d in [dir.join("definitions"), dir.join("../Resources/definitions"), dir.join("../../definitions")] {
            if !v.contains(&d) {
                v.push(d);
            }
        }
    }
    v
}

/// The first of `shipped_dirs` that is a folder.
pub fn shipped_dir() -> Option<PathBuf> {
    shipped_dirs().into_iter().find(|d| d.is_dir())
}

/// Every definition the editor found: the shipped ones first, then the user's, which replace a shipped one of the
/// same model and firmware; and the files it could not use, with why.
#[derive(Clone, Debug, Default)]
pub struct Definitions {
    pub list: Vec<Schema>,
    /// Files that are not used, and why in plain words (format too new, not a definition, a duplicate…).
    pub rejected: Vec<(PathBuf, String)>,
    /// Files used but named otherwise than `<model>_fw<firmware>.json`: the name to give them.
    pub misnamed: Vec<(PathBuf, String)>,
    /// The shipped set's folder (None: not found) and where it was looked for.
    pub shipped_dir: Option<PathBuf>,
    pub looked_in: Vec<PathBuf>,
    /// The user's folder: the only one the editor writes.
    pub user_dir: PathBuf,
    /// The model and the save time each sample beside a definition names in its header (`camera.sample`, read with
    /// that definition's container block): how the sample, and any file made from it, is known however it is opened
    /// (`is_sample`). The editor never changes a header, so a file saved from the sample keeps both.
    pub sample_marks: Vec<(String, String)>,
}

impl Definitions {
    /// Read the shipped folder (when there is one) and the user's, applying the help files found in `help_dirs`.
    pub fn load(shipped_dir: Option<PathBuf>, looked_in: Vec<PathBuf>, user_dir: PathBuf, help_dirs: &[PathBuf]) -> Definitions {
        let mut d = Definitions { shipped_dir, looked_in, user_dir, ..Default::default() };
        d.reload(help_dirs);
        d
    }

    /// Read both folders again (a definition may have been changed, added or removed).
    pub fn reload(&mut self, help_dirs: &[PathBuf]) {
        let (mut list, mut rejected, mut misnamed) = (Vec::new(), Vec::new(), Vec::new());
        if let Some(dir) = &self.shipped_dir {
            Self::read_folder(dir, true, &mut list, &mut rejected, &mut misnamed);
        }
        let shipped = list.len();
        Self::read_folder(&self.user_dir, false, &mut list, &mut rejected, &mut misnamed);
        // a user definition replaces the shipped one of the same model and firmware
        for i in shipped..list.len() {
            let key = (list[i].model.clone(), list[i].firmware().to_string());
            for j in 0..shipped {
                if (list[j].model.as_str(), list[j].firmware()) == (key.0.as_str(), key.1.as_str()) {
                    list[j].overridden = true;
                    list[i].overrides = true;
                }
            }
        }
        for s in &mut list {
            s.apply_help(help_dirs);
        }
        (self.list, self.rejected, self.misnamed) = (list, rejected, misnamed);
        self.sample_marks = self.read_sample_marks();
    }

    /// The model and save time in each sample's header (`sample_marks`), read with its own definition's block; a
    /// sample that cannot be read, or that the block does not describe, names none.
    fn read_sample_marks(&self) -> Vec<(String, String)> {
        let mut out: Vec<(String, String)> = Vec::new();
        for (i, p) in self.samples() {
            let (Some(block), Ok(d)) = (self.list[i].camera.file.as_ref(), std::fs::read(&p)) else { continue };
            if !block.magic_matches(&d) {
                continue;
            }
            if let (Some(model), Some(saved)) = (block.peek_model(&d), block.peek_saved(&d)) {
                if !out.contains(&(model.clone(), saved.clone())) {
                    out.push((model, saved));
                }
            }
        }
        out
    }

    /// Whether `c` is a sample beside a definition, or a file made from one: its header names the model and the save
    /// time one of them names (`sample_marks`). Such a file is never written to a camera: the sample is the camera's
    /// file with its personal text taken out and a save time of its own put in, so no camera wrote it as it is.
    pub fn is_sample(&self, c: &CamSet) -> bool {
        let (model, saved) = (c.model(), c.timestamp());
        self.sample_marks.iter().any(|(m, s)| *m == model && *s == saved)
    }

    /// The *.json files of one folder, sorted by name, read as definitions. A second file of the same model and
    /// firmware in the folder is not used.
    fn read_folder(dir: &Path, shipped: bool, list: &mut Vec<Schema>, rejected: &mut Vec<(PathBuf, String)>, misnamed: &mut Vec<(PathBuf, String)>) {
        let mut files: Vec<PathBuf> = std::fs::read_dir(dir)
            .map(|it| it.flatten().map(|e| e.path()).filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("json")) && p.is_file()).collect())
            .unwrap_or_default();
        files.sort();
        let first = list.len();
        for p in files {
            match Schema::from_file(&p) {
                Ok(mut s) => {
                    if let Some(other) = list[first..].iter().find(|o| o.model == s.model && o.firmware() == s.firmware()) {
                        let name = other.origin.path().and_then(Path::file_name).unwrap_or_default().to_string_lossy();
                        rejected.push((p, format!("{} firmware {} is defined already by {name} in the same folder", s.model, s.firmware())));
                        continue;
                    }
                    if p.file_name().and_then(|n| n.to_str()) != Some(s.file_name().as_str()) {
                        misnamed.push((p.clone(), s.file_name()));
                    }
                    s.origin = if shipped { Origin::Shipped(p) } else { Origin::User(p) };
                    list.push(s);
                }
                Err(e) => rejected.push((p, e)),
            }
        }
    }

    /// The definitions in use: every one but a shipped one the user's replaces.
    pub fn in_use(&self) -> impl Iterator<Item = &Schema> {
        self.list.iter().filter(|s| !s.overridden)
    }

    /// The definition in use for a model and firmware.
    pub fn find(&self, model: &str, firmware: &str) -> Option<&Schema> {
        self.in_use().find(|s| s.model == model && s.firmware() == firmware)
    }

    /// The shipped definition of a model and firmware, whether or not the user's replaces it.
    pub fn shipped(&self, model: &str, firmware: &str) -> Option<&Schema> {
        self.list.iter().find(|s| s.origin.is_shipped() && s.model == model && s.firmware() == firmware)
    }

    /// The samples the definitions name (`camera.sample`, a file beside the definition) that are there: each
    /// definition's place in `list` and the file. The shipped ones first.
    pub fn samples(&self) -> Vec<(usize, PathBuf)> {
        self.list.iter().enumerate().filter_map(|(i, s)| {
            let name = s.camera.sample.as_deref().filter(|n| Path::new(n).file_name().is_some_and(|f| f == *n))?;
            let p = s.origin.path()?.parent()?.join(name);
            p.is_file().then_some((i, p))
        }).collect()
    }

    /// "ILCE-1M2 (firmware 4.00)" for each definition in use: what the editor works with. One from the user's folder
    /// says so, as Settings' list of definitions does: "(firmware 4.00, added by you)", or, used in place of a
    /// built-in one of the same model and firmware, "(firmware 4.00, yours, in place of the built-in one)".
    pub fn works_with(&self) -> Vec<String> {
        self.in_use().map(|s| {
            let yours = match (&s.origin, s.overrides) {
                (Origin::User(_), true) => ", yours, in place of the built-in one",
                (Origin::User(_), false) => ", added by you",
                _ => "",
            };
            format!("{} (firmware {}{yours})", s.model_words(), s.firmware())
        }).collect()
    }

    /// A model code as the window names that camera: with the name a definition of it gives ("ILCE-1M2 · α1 II"),
    /// else the code as it is.
    pub fn model_words(&self, model: &str) -> String {
        self.in_use().find(|s| s.model == model).map(|s| s.model_words()).unwrap_or_else(|| model.to_string())
    }

    /// The distinct container blocks of the definitions `pool` lets through, in order: definitions of one container
    /// share its block, so a file is read once per distinct block.
    fn blocks(&self, pool: impl Fn(&Schema) -> bool) -> Vec<&FileFormat> {
        let mut out: Vec<&FileFormat> = Vec::new();
        for f in self.list.iter().filter(|s| pool(s)).filter_map(|s| s.camera.file.as_ref()) {
            if !out.contains(&f) {
                out.push(f);
            }
        }
        out
    }

    /// How many first bytes of a file `is_settings_file` looks at: as far as the furthest container's magic ends.
    pub fn magic_len(&self) -> usize {
        self.blocks(|_| true).iter().filter_map(|f| f.magic_end()).max().unwrap_or(0)
    }

    /// Whether `d` starts as some definition's container does (a settings file, as far as its first bytes say).
    pub fn is_settings_file(&self, d: &[u8]) -> bool {
        self.blocks(|_| true).iter().any(|f| f.magic_matches(d))
    }

    /// Read a settings file by trial (docs/decisions/0019, 0020): for each distinct block of the definitions in use
    /// (with `shipped_only`, of the shipped ones, as the sample is read), its magic first; then the file framed with
    /// it, which its trailer checksum must confirm; then its model text against the definitions sharing the block;
    /// then its firmware, that firmware's definition, else the nearest of that model. A file of a model no definition
    /// covers is read with the first block whose magic matched and that frames it, and matches none.
    pub fn open(&self, d: &[u8], shipped_only: bool) -> Result<Opened, CamSetError> {
        let pool = |s: &Schema| if shipped_only { s.origin.is_shipped() } else { !s.overridden };
        let mut err = CamSetError::NotCamSet;
        // framed with `block`, its trailer checksum holding; else why not, kept for the end
        let mut frame = |block: &FileFormat| match CamSet::read(d, &Arc::new(block.clone())) {
            Ok(s) if s.trailer_checksum_ok() => Some(s),
            Ok(_) => {
                err = CamSet::parse(d, &Arc::new(block.clone())).err().unwrap_or(CamSetError::NotCamSet);
                None
            }
            Err(e) => {
                err = e;
                None
            }
        };
        // before a definition is picked, only the magic, the model and the firmware are read
        let mut others: Vec<&FileFormat> = Vec::new();
        for block in self.blocks(pool) {
            let (Some(model), Some(fw)) = (block.peek_model(d), block.peek_firmware(d)) else { continue };
            if !block.magic_matches(d) {
                continue;
            }
            match self.pick(block, &model, &fw, shipped_only) {
                (Some(i), how) => {
                    if let Some(set) = frame(block) {
                        return Ok(Opened { set, def: Some(i), how });
                    }
                }
                (None, _) => others.push(block),
            }
        }
        // no definition of its model: the first container that frames it
        for block in others {
            if let Some(set) = frame(block) {
                return Ok(Opened { set, def: None, how: Match::None });
            }
        }
        Err(err)
    }

    /// The definition for a file read with `block` that names `model` and firmware `fw`: of the definitions sharing
    /// the block (in use, or shipped only), that model's at that firmware, else the nearest firmware of that model (a
    /// tie going to the newer), else none. Its place in `list`.
    pub fn pick(&self, block: &FileFormat, model: &str, fw: &str, shipped_only: bool) -> (Option<usize>, Match) {
        let pool = |s: &Schema| if shipped_only { s.origin.is_shipped() } else { !s.overridden };
        let of_model: Vec<usize> = (0..self.list.len())
            .filter(|&i| pool(&self.list[i]) && self.list[i].camera.file.as_ref() == Some(block) && self.list[i].model == model)
            .collect();
        if let Some(&i) = of_model.iter().find(|&&i| self.list[i].firmware() == fw) {
            return (Some(i), Match::Exact);
        }
        let near = |i: usize| {
            let (a, b) = (firmware_number(fw), firmware_number(self.list[i].firmware()));
            // nearest first; of two as near, the newer
            (a.zip(b).map_or(u32::MAX, |(a, b)| a.abs_diff(b)), std::cmp::Reverse(b))
        };
        match of_model.iter().min_by_key(|&&i| near(i)) {
            Some(&i) => (Some(i), Match::Near { file_fw: fw.to_string() }),
            None => (None, Match::None),
        }
    }
}

/// How a settings file found its definition.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub enum Match {
    /// The definition of the file's model and firmware.
    Exact,
    /// No definition of the file's own firmware: the nearest one of its model. `file_fw` is the file's firmware.
    Near { file_fw: String },
    /// No definition of the file's model: the file is read with the framing of a container that fits it, and
    /// nothing is named.
    #[default]
    None,
}

/// A file read by trial (`Definitions::open`): the file, the definition picked (its place in `Definitions::list`)
/// and how it matched.
#[derive(Debug)]
pub struct Opened {
    pub set: CamSet,
    pub def: Option<usize>,
    pub how: Match,
}


/// The definition formats this editor reads, in words: "format 2", or "formats 2 to 3".
fn formats_read() -> String {
    if OLDEST_DEFINITION_FORMAT == DEFINITION_FORMAT {
        format!("format {DEFINITION_FORMAT}")
    } else {
        format!("formats {OLDEST_DEFINITION_FORMAT} to {DEFINITION_FORMAT}")
    }
}

impl Schema {
    /// A definition read from its text, checked: the format first (a newer one is refused with what to do), then
    /// the typed reading (its message names the line and column), then `check`.
    pub fn from_text(text: &str) -> Result<Schema, String> {
        let v: serde_json::Value = serde_json::from_str(text).map_err(|e| format!("not a readable JSON file ({e})"))?;
        if !v.is_object() || v.get("settings").is_none() {
            return Err("not a camera definition (it has no settings list)".into());
        }
        match v.get("definition_format") {
            None => return Err("no definition_format: written for an older Camset Editor, or not by the kit".into()),
            Some(f) => match f.as_u64() {
                Some(n) if n > DEFINITION_FORMAT as u64 => {
                    return Err(format!("needs a newer Camset Editor (definition format {n}; this one reads up to {DEFINITION_FORMAT})"));
                }
                Some(n) if n >= 1 && n < OLDEST_DEFINITION_FORMAT as u64 => {
                    return Err(format!("it was made by an older mapping kit (definition format {n}), and this editor needs the newer form ({}). Ask whoever made it for a new one (if you mapped the camera yourself: run kit/schema_update.py --write)", formats_read()));
                }
                Some(n) if n >= 1 => {}
                _ => return Err(format!("its definition_format is {f}, which is not a format this editor knows (it reads {})", formats_read())),
            },
        }
        drop(v);
        let s: Schema = serde_json::from_str(text).map_err(|e| format!("does not read as a camera definition: {e}"))?;
        s.check()?;
        Ok(s)
    }

    /// A definition file read and checked (`from_text`); Err says why it cannot be used, in plain words.
    pub fn from_file(p: &Path) -> Result<Schema, String> {
        let text = std::fs::read_to_string(p).map_err(|e| format!("could not be read ({e})"))?;
        Self::from_text(&text)
    }

    /// What the typed reading does not check: one layout, of the definition's own model.
    pub fn check(&self) -> Result<(), String> {
        if self.model.trim().is_empty() {
            return Err("it names no model".into());
        }
        if self.layouts.len() != 1 {
            return Err(format!("a definition holds exactly one layout (one model and firmware); this one holds {}", self.layouts.len()));
        }
        let l = &self.layouts[0];
        if l.model != self.model {
            return Err(format!("its layout is for the {} but the definition is for the {}", l.model, self.model));
        }
        if l.firmware.trim().is_empty() {
            return Err("its layout names no firmware".into());
        }
        if let Some(m) = self.camera.model.as_ref().filter(|m| **m != self.model) {
            return Err(format!("its camera section is for the {m} but the definition is for the {}", self.model));
        }
        if let Some(f) = &self.camera.file {
            f.check().map_err(|e| format!("its file block does not hold together: {e}"))?;
        }
        Ok(())
    }

    /// The camera as the window names it: the model code with the name photographers know it by, when the definition
    /// gives one ("ILCE-1M2 · α1 II"), else the code.
    pub fn model_words(&self) -> String {
        match self.camera.display_name.as_deref().map(str::trim).filter(|n| !n.is_empty()) {
            Some(n) => format!("{} · {n}", self.model),
            None => self.model.clone(),
        }
    }

    /// The firmware the definition was checked on ("4.00"); empty for no definition.
    pub fn firmware(&self) -> &str {
        self.layouts.first().map_or("", |l| l.firmware.as_str())
    }

    /// The file name the definition goes by: `<model>_fw<firmware>.json`.
    pub fn file_name(&self) -> String {
        format!("{}_fw{}.json", self.model, self.firmware())
    }

    /// How many settings were proved on the camera.
    pub fn proved(&self) -> usize {
        self.settings.iter().filter(|s| s.proved.is_some()).count()
    }

    /// Where help files are looked for, in order: $CAMSET_HELP_DIR; private/help in the working folder
    /// and in the folders above the program (a checkout with its private folder); help/ beside the
    /// program or in the app's Resources (an internal build, packaging/build_macos_app.sh); help/ in the
    /// editor's own folder.
    pub fn help_dirs() -> Vec<PathBuf> {
        let mut v: Vec<PathBuf> = std::env::var_os("CAMSET_HELP_DIR").map(PathBuf::from).into_iter().collect();
        v.push(PathBuf::from("private/help"));
        v.push(PathBuf::from("../private/help"));
        if let Ok(exe) = std::env::current_exe() {
            v.extend(exe.ancestors().skip(1).take(5).map(|a| a.join("private/help")));
            if let Some(dir) = exe.parent() {
                v.push(dir.join("help"));
                v.push(dir.join("../Resources/help"));
            }
        }
        v.push(config_dir().join("help"));
        v
    }

    /// The help file's name for this schema: help_<model>_fw<firmware>.json.
    pub fn help_file_name(&self) -> String {
        format!("help_{}_fw{}.json", self.model, self.firmware())
    }

    /// The first help file found in `dirs` that is for this definition's camera replaces the help of each setting it
    /// names, text by text: a setting's help, and each option's by its value. Where the file has none, the
    /// definition's own words stay, and `help_from_file` and `option_help_from_file` say whose each text is. A file
    /// of the help file's name that is another camera's (`help_refusal`) or not a help file is not used: it goes into
    /// `help_refused`, with why, and the next folder is looked in.
    pub fn apply_help(&mut self, dirs: &[PathBuf]) {
        self.help_refused.clear();
        for d in dirs {
            let p = d.join(self.help_file_name());
            let Ok(text) = std::fs::read_to_string(&p) else { continue };
            let h = match serde_json::from_str::<HelpFile>(&text) {
                Ok(h) => h,
                Err(_) => {
                    self.help_refused.push((p, "it does not read as a help file".into()));
                    continue;
                }
            };
            if let Some(why) = self.help_refusal(&h) {
                self.help_refused.push((p, why));
                continue;
            }
            for s in &mut self.settings {
                if let Some(t) = h.settings.get(&s.key) {
                    if !t.help.is_empty() {
                        s.help = t.help.clone();
                        s.help_from_file = true;
                    }
                    for (v, text) in t.option_help.iter().filter(|(_, text)| !text.is_empty()) {
                        match s.option_help.iter_mut().find(|(x, _)| x == v) {
                            Some(own) => own.1 = text.clone(),
                            None => s.option_help.push((*v, text.clone())),
                        }
                        s.option_help_from_file.push(*v);
                    }
                }
            }
            self.help_src = format!("{} ({})", p.display(), h.source);
            return;
        }
    }

    /// Why a help file is not for this definition's camera, in plain words; None when the model and firmware it
    /// says it is for are the definition's. Only what the file says counts, never its name: a file copied or
    /// renamed for another camera, one of another firmware of the same model, or one that names neither, is not used.
    pub fn help_refusal(&self, h: &HelpFile) -> Option<String> {
        if h.model.is_empty() || h.firmware.is_empty() {
            return Some("it does not say which camera it is for (its model and firmware)".into());
        }
        (h.model != self.model || h.firmware != self.firmware())
            .then(|| format!("it is for the {} firmware {}, not the {} firmware {}", h.model, h.firmware, self.model, self.firmware()))
    }

    /// Each help file not used, in a sentence for Settings > Camera support & web page: its file name (never its
    /// folder), why, and whose help is shown instead.
    pub fn help_refusals(&self) -> Vec<String> {
        let instead = if self.help_src.is_empty() {
            "The help shown is Camset's own, from the definition, where it has some."
        } else {
            "A file of the same name in another folder, which is for this camera, is used instead."
        };
        self.help_refused.iter().map(|(p, why)| {
            let name = p.file_name().unwrap_or_default().to_string_lossy();
            format!("Help file not used: {name}: {why}. {instead}")
        }).collect()
    }

    /// The firmware this definition was checked on, for messages ("unverified" with no definition).
    pub fn firmwares(&self) -> String {
        let v: Vec<&str> = self.layouts.iter().map(|l| l.firmware.as_str()).collect();
        if v.is_empty() { "unverified".into() } else { v.join(", ") }
    }

    pub fn layout(&self, signature: &str) -> Option<&Layout> {
        self.layouts.iter().find(|l| l.signature == signature)
    }

    pub fn find(&self, area_is_set: bool, id: u16) -> Option<&Setting> {
        if area_is_set {
            self.settings
                .iter()
                .find(|s| s.area == "set" && s.id == id)
                .or_else(|| self.settings.iter().find(|s| s.in_sets && s.id == id))
        } else {
            self.settings.iter().find(|s| s.area == "global" && s.id == id)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The shipped definitions' folder in this checkout.
    fn shipped() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions")
    }

    /// The ILCE-1M2 firmware 4.00 definition's text, as shipped.
    fn a1_text() -> String {
        std::fs::read_to_string(shipped().join("ILCE-1M2_fw4.00.json")).expect("the shipped ILCE-1M2 definition")
    }

    fn embedded() -> Schema {
        Schema::from_text(&a1_text()).expect("the shipped definition is valid")
    }

    /// A fresh folder for one test.
    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("camset_defs_{name}_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    /// The shipped definition's text with `f` applied to it.
    fn a1_with(f: impl FnOnce(&mut serde_json::Value)) -> String {
        let mut v: serde_json::Value = serde_json::from_str(&a1_text()).unwrap();
        f(&mut v);
        v.to_string()
    }

    /// A definition written while the kit still wrote `written_with` (how a camera was set when its proofs were made:
    /// evidence, decision 16, which the editor builds no row from) still loads, the field ignored.
    #[test]
    fn a_definition_carrying_written_with_loads_and_ignores_it() {
        let text = a1_with(|v| for s in v["settings"].as_array_mut().unwrap() { s["written_with"] = serde_json::json!(["global:0x0001"]); });
        let schema = Schema::from_text(&text).expect("it loads");
        assert_eq!(schema.settings.len(), embedded().settings.len());
        let one: Setting = serde_json::from_value(serde_json::json!({
            "key": "global:0x0001", "area": "global", "id": 1, "name": "A", "source": "Menu", "tab": "T", "group": "G",
            "order": 1, "in_sets": false, "scalar": true, "values": [[0, "Off"], [1, "On"]], "written_with": ["global:0x0002"]})).unwrap();
        assert_eq!((one.key.as_str(), one.values.len()), ("global:0x0001", 2));
    }

    /// A newer format is refused with what to do, and so is format 1, the definition before it was lean (it carried
    /// the mapping's evidence and named its checked values another way): in plain words for someone given only the
    /// file (ask whoever made it for a new one) and for the mapper (the kit writes it again).
    #[test]
    fn a_newer_format_is_refused_with_what_to_do() {
        let e = Schema::from_text(&a1_with(|v| v["definition_format"] = 3.into())).unwrap_err();
        assert_eq!(e, "needs a newer Camset Editor (definition format 3; this one reads up to 2)");
        let e = Schema::from_text(&a1_with(|v| v["definition_format"] = 1.into())).unwrap_err();
        assert_eq!(e, "it was made by an older mapping kit (definition format 1), and this editor needs the newer form (format 2). Ask whoever made it for a new one (if you mapped the camera yourself: run kit/schema_update.py --write)");
        let e = Schema::from_text(&a1_with(|v| { v.as_object_mut().unwrap().remove("definition_format"); })).unwrap_err();
        assert!(e.contains("no definition_format"), "{e}");
        let e = Schema::from_text(&a1_with(|v| v["definition_format"] = "one".into())).unwrap_err();
        assert_eq!(e, "its definition_format is \"one\", which is not a format this editor knows (it reads format 2)");
        let e = Schema::from_text(&a1_with(|v| v["definition_format"] = 0.into())).unwrap_err();
        assert_eq!(e, "its definition_format is 0, which is not a format this editor knows (it reads format 2)");
        assert_eq!(embedded().definition_format, DEFINITION_FORMAT);
    }

    /// The editor's folder: $XDG_CONFIG_HOME, else %APPDATA%, else ~/.config, each only when it is a whole path, so an
    /// empty or relative value never puts the folder wherever the editor was started.
    #[test]
    fn the_editors_folder_from_the_environment() {
        let root = std::env::temp_dir();
        let env = |pairs: Vec<(&'static str, std::ffi::OsString)>| move |k: &str| pairs.iter().find(|(n, _)| *n == k).map(|(_, v)| v.clone());
        let home = root.join("home_of_user");
        let xdg = root.join("xdg");
        assert_eq!(config_dir_from(&env(vec![("XDG_CONFIG_HOME", xdg.clone().into()), ("HOME", home.clone().into())])), xdg.join("camset_editor"));
        assert_eq!(config_dir_from(&env(vec![("XDG_CONFIG_HOME", "".into()), ("HOME", home.clone().into())])), home.join(".config").join("camset_editor"));
        assert_eq!(config_dir_from(&env(vec![("XDG_CONFIG_HOME", "relative/dir".into()), ("HOME", home.clone().into())])), home.join(".config").join("camset_editor"));
        assert_eq!(config_dir_from(&env(vec![])), PathBuf::from(".").join("camset_editor"));
    }

    /// A definition holds exactly one layout, of its own model; a broken file is refused with where it broke.
    #[test]
    fn a_definition_is_checked_as_it_loads() {
        let two = a1_with(|v| { let l = v["layouts"][0].clone(); v["layouts"].as_array_mut().unwrap().push(l); });
        assert!(Schema::from_text(&two).unwrap_err().contains("exactly one layout"));
        let other = a1_with(|v| v["layouts"][0]["model"] = "ILCE-0X0".into());
        assert!(Schema::from_text(&other).unwrap_err().contains("ILCE-0X0"));
        let typed = a1_with(|v| v["settings"][0]["id"] = "not a number".into());
        let e = Schema::from_text(&typed).unwrap_err();
        assert!(e.starts_with("does not read as a camera definition") && e.contains("line"), "{e}");
        assert!(Schema::from_text("{ not json").unwrap_err().starts_with("not a readable JSON file"));
        assert!(Schema::from_text("{\"model\": \"X\"}").unwrap_err().contains("no settings list"));
    }

    /// A setting made here from its definition text, with `extra` keys added.
    fn made(extra: serde_json::Value) -> Setting {
        let mut v = serde_json::json!({
            "key": "global:0x0001", "area": "global", "id": 1, "name": "Rate", "tab": "Movie", "group": "Rate",
            "order": 1, "in_sets": true, "scalar": true, "values": [[0, "60p"], [1, "50p"], [2, "30p"], [3, "25p"], [4, "24p"]]
        });
        for (k, x) in extra.as_object().unwrap() {
            v[k] = x.clone();
        }
        serde_json::from_value(v).unwrap()
    }

    /// `video_system_values`: a value listed under one video system belongs to it, one listed under none to both; the
    /// file's system decides, and with it unknown nothing is held back. Without the field, no value belongs to one.
    #[test]
    fn a_value_belongs_to_the_video_system_that_lists_it() {
        let s = made(serde_json::json!({ "video_system_values": { "NTSC": [0, 2], "PAL": [1, 3] } }));
        assert_eq!(s.other_system(1, Some("NTSC")), Some("PAL"));
        assert_eq!(s.other_system(0, Some("PAL")), Some("NTSC"));
        assert_eq!((s.other_system(0, Some("NTSC")), s.other_system(3, Some("PAL"))), (None, None), "its own system's");
        assert_eq!(s.other_system(4, Some("NTSC")), None, "listed under neither: both");
        assert_eq!(s.other_system(1, None), None, "the file's system unknown: every value");
        assert_eq!(s.other_system(1, Some("a system the definition does not list")), Some("PAL"), "a value of a listed system is that system's only");
        assert_eq!(made(serde_json::json!({})).other_system(1, Some("NTSC")), None);
    }

    /// A proof as the lean definition says it: the values it checked, or a scale sampled and whether on one line; the
    /// badge counts the values checked, or says "sampled". The evidence a format-1 proof carried (its run, day, menu
    /// rows, name sources, the count of samples) is no field of the editor's, and the shipped definition holds none.
    #[test]
    fn a_lean_proof_says_which_values_it_checked() {
        let s = made(serde_json::json!({ "values": [[0, "Alpha"], [1, "Bravo"], [2, "Charlie"], [3, "Delta"]],
            "proved": { "values": [0, 1, 3] } }));
        assert_eq!(s.proof_badge().0, "Proved on the camera (3/4)");
        assert!(s.established(3) && !s.established(2));
        let picker = made(serde_json::json!({ "values": [[0, "Alpha"], [1, "Bravo"]], "proved": { "values": [0, 1], "sampled": { "linear": null } } }));
        assert_eq!(picker.proof_badge().0, "Proved on the camera (sampled)");
        assert!(picker.established(1));
        let range = made(serde_json::json!({ "values": [], "range": [0, 10], "proved": { "sampled": { "linear": true } } }));
        assert!(range.established(7) && range.proof_badge().0 == "Proved on the camera (sampled)");
        let v: serde_json::Value = serde_json::from_str(&a1_text()).unwrap();
        for x in v["settings"].as_array().unwrap() {
            for k in ["source", "note_evidence", "in_sets_proved", "menu_blocked"] {
                assert!(x.get(k).is_none(), "{} carries {k}", x["key"]);
            }
            if let Some(p) = x.get("proved") {
                assert!(p.as_object().unwrap().keys().all(|k| k == "values" || k == "sampled"), "{} proved: {p}", x["key"]);
            }
        }
    }

    /// What the write window judges by (`checked_on_camera`): a value a proof established, in a set the proof reaches,
    /// of a setting not disputed; a setting with no proof checks nothing, though it offers every value (`established`).
    /// And where no menu writes a setting (`not_on_camera_in`): everywhere, or in the memory sets `unproved_sets` names.
    #[test]
    fn checked_on_the_camera_is_what_a_proof_established() {
        let proved = made(serde_json::json!({ "proved": { "values": [0, 1] },
            "unproved_sets": { "sets": [4, 5], "kind": "not_on_camera", "why": "Only the stills memories write it." } }));
        assert!(proved.checked_on_camera(0, 0) && proved.checked_on_camera(1, 1));
        assert!(!proved.checked_on_camera(2, 0), "a value its proof did not establish");
        assert!(!proved.checked_on_camera(0, 4), "a memory set no proof reaches");
        assert_eq!((proved.not_on_camera_in(4), proved.not_on_camera_in(0)), (Some("Only the stills memories write it."), None));
        let unproved = made(serde_json::json!({}));
        assert!(unproved.established(2) && !unproved.checked_on_camera(2, 0), "offered, but not checked");
        let mut disputed = proved.clone();
        disputed.disputed = true;
        assert!(!disputed.checked_on_camera(0, 0));
        let nowhere = made(serde_json::json!({ "unproved_reason": { "kind": "not_on_camera", "why": "PP7 is not on this body's menu." } }));
        assert_eq!((nowhere.not_on_camera_in(0), nowhere.not_on_camera_in(3)), (Some("PP7 is not on this body's menu."), Some("PP7 is not on this body's menu.")));
        let other = made(serde_json::json!({ "unproved_reason": { "kind": "state", "why": "A flag." } }));
        assert_eq!(other.not_on_camera_in(0), None, "another kind of reason locks nothing");
        // copies, as the kit writes them
        let main = made(serde_json::json!({ "copies": ["global:0x0002", "global:0x0003"] }));
        let copy = made(serde_json::json!({ "copy_of": "global:0x0001" }));
        assert_eq!((main.copies.len(), copy.copy_of.as_deref()), (2, Some("global:0x0001")));
        assert!(made(serde_json::json!({})).copies.is_empty() && made(serde_json::json!({})).copy_of.is_none());
    }

    /// The sample is known by its header (`Definitions::is_sample`): the model and save time of the sample beside a
    /// definition, read with that definition's block. A file with another save time, or of another model, is not it;
    /// a definition beside which no sample lies names none.
    #[test]
    fn the_sample_is_known_by_its_header() {
        let (ship, user) = (scratch("sample_marks"), scratch("sample_marks_user"));
        std::fs::write(ship.join("ILCE-1M2_fw4.00.json"), a1_text()).unwrap();
        let d = Definitions::load(Some(ship.clone()), vec![], user.clone(), &[]);
        assert!(d.sample_marks.is_empty(), "no sample beside the definition");
        std::fs::write(ship.join("ILCE-1M2_fw4.00.DAT"), sample_bytes()).unwrap();
        let d = Definitions::load(Some(ship.clone()), vec![], user.clone(), &[]);
        assert_eq!(d.sample_marks.len(), 1);
        let block = Arc::new(embedded().camera.file.unwrap());
        let sample = CamSet::parse(&sample_bytes(), &block).unwrap();
        assert!(d.is_sample(&sample));
        let mut later = sample.clone();
        let at = block.saved.at.at(later.header.len()).unwrap();
        later.header[at] = later.header[at].wrapping_add(1);
        assert!(!d.is_sample(&later), "another save time: a camera's own file");
        assert!(!d.is_sample(&CamSet::parse(&retitled(&sample_bytes(), b"ILCE-0X0", [4, 0, 0]), &block).unwrap()), "another model");
        let _ = (std::fs::remove_dir_all(ship), std::fs::remove_dir_all(user));
    }

    /// `not_offered`: a value the camera's menus never offer is left out of the choice whatever "Offer values…" says,
    /// is not counted among the values Expert mode would bring back, and its acceptance says why; a held one (a
    /// factory value the camera writes itself) stays offered. The shipped definition marks the stills dials' surplus functions
    /// and ISO AUTO Minimum's factory ISO 64, held.
    #[test]
    fn a_value_the_menus_never_offer_is_left_out_unless_held() {
        let s: Setting = serde_json::from_value(serde_json::json!({
            "key": "global:0x0001", "area": "global", "id": 1, "name": "Dial", "tab": "Setup", "group": "Dial",
            "order": 1, "in_sets": false, "scalar": true, "values": [[0, "A"], [1, "B"], [2, "C"], [3, "D"]],
            "proved": { "values": [0, 3] },
            "not_offered": [{ "value": 1, "label": "B", "why": "Not on its list." },
                            { "value": 3, "label": "D", "why": "The factory value.", "held": true }]
        })).unwrap();
        let vals = |all| s.offered(all).into_iter().map(|(v, _)| v).collect::<Vec<_>>();
        assert_eq!(vals(false), vec![0, 3], "the established ones, the held one among them");
        assert_eq!(vals(true), vec![0, 2, 3], "B is never offered, Expert mode's \"Offer values…\" or not");
        assert_eq!((s.hidden_unproved(false), s.hidden_unproved(true)), (1, 0), "only C waits for \"Offer values…\"");
        assert_eq!(s.never_offered(1).map(|n| n.why.as_str()), Some("Not on its list."));
        assert!(s.never_offered(3).is_none() && s.offerable(3), "a held value stays offered");
        assert_eq!(s.acceptance(1).as_deref(), Some("the camera's menus never offer this value; the camera may refuse a file holding it"));
        assert!(s.acceptance(3).is_none(), "the factory value, which the camera writes itself");
        let shipped = embedded();
        let dial = shipped.settings.iter().find(|x| x.key == "global:0x0407").expect("Front dial (M mode)");
        for all in [false, true] {
            assert!(!dial.offered(all).iter().any(|(v, _)| [198, 861].contains(v)), "Audio Rec Level and Follow Custom are on no stills dial's list");
        }
        let min = shipped.settings.iter().find(|x| x.key == "global:0x0dfa").expect("ISO AUTO Minimum");
        assert!(min.not_offered.iter().any(|n| n.value == 3 && n.held) && min.offerable(3));
        assert!(min.never_offered(2).is_some() && min.never_offered(4).is_some(), "ISO 50 and 80 are not on its list");
    }

    /// The gate outside Expert mode reads the proofs (`established`): a setting with no proof offers every value; in a
    /// proved one a value is established when its proof lists it (`proved.values`: the kit lists there what a proof
    /// chose and what it named from the camera's own word), or by a scale sampled on a line, which establishes every
    /// value and every number of a range; a value the proof does not list is not established, and the hidden count and
    /// the acceptance say so in the gate's words. A format-1 proof's evidence (`names`, `inferred`, `run`, `date`) and an
    /// old `observed` list are no fields of the editor's: a name source establishes nothing any more.
    #[test]
    fn a_value_is_established_by_its_proof_not_by_a_list_of_held_values() {
        let mut values: Vec<serde_json::Value> = (0..=21).map(|v| serde_json::json!([v, format!("V{v}")])).collect();
        values.retain(|v| v[0].as_i64().is_some_and(|n| n == 1 || (10..=16).contains(&n) || n >= 20));
        let setting = |proved: serde_json::Value| -> Setting { serde_json::from_value(serde_json::json!({
            "key": "global:0x0001", "area": "global", "id": 1, "name": "Dial", "tab": "Setup", "group": "Dial",
            "order": 1, "in_sets": false, "scalar": true, "values": values, "observed": [21], "proved": proved
        })).unwrap() };
        let s = setting(serde_json::json!({ "values": [1, 10, 11, 12, 13, 14, 15], "names": { "16": "two readers" } }));
        for v in [1, 10, 11, 12, 13, 14, 15] {
            assert!(s.established(v), "{v} is listed");
        }
        assert!(!s.established(16), "a name source of an old definition establishes nothing");
        assert!(!s.established(20) && !s.established(21), "a value the proof does not list (the old observed list is ignored)");
        assert_eq!(s.proof_badge().0, format!("Proved on the camera (7/{})", values.len()));
        assert_eq!((s.hidden_unproved(false), s.hidden_unproved(true)), (3, 0));
        assert_eq!(s.offered(false).len(), values.len() - 3);
        assert_eq!(s.acceptance(21).as_deref(), Some("not checked on the camera yet; the camera may refuse a file holding it"));
        assert!(s.acceptance(10).is_none() && s.acceptance(1).is_none());
        let line = setting(serde_json::json!({ "sampled": { "linear": true } }));
        assert!(line.established(21) && line.hidden_unproved(false) == 0, "a scale sampled on a line establishes every value");
        let bent = setting(serde_json::json!({ "sampled": { "linear": false } }));
        assert!(!bent.established(21) && bent.hidden_unproved(false) == values.len(), "samples off a line establish none of the values between");
        let unproved: Setting = serde_json::from_value(serde_json::json!({
            "key": "global:0x0002", "area": "global", "id": 2, "name": "Knob", "tab": "Setup", "group": "Dial",
            "order": 2, "in_sets": false, "scalar": true, "values": [[0, "A"], [1, "B"]], "observed": [0]
        })).unwrap();
        assert!(unproved.established(1) && unproved.hidden_unproved(false) == 0 && unproved.acceptance(1).is_none(),
            "no proof: nothing is known, and every value is offered");
        let mut range = setting(serde_json::json!({ "sampled": { "linear": true } }));
        range.range = Some((0, 639));
        range.values.clear();
        assert!(range.established(321), "a range sampled on a line: every number in it");
        // the shipped definition: every My Menu place can be emptied outside Expert mode, its empty code named by a
        // hand table from the camera's Add Item proofs
        let shipped = embedded();
        let mm = shipped.camera.my_menu.as_ref().expect("the a1 II's My Menu");
        let places: Vec<&Setting> = shipped.settings.iter().filter(|x| x.area == "global" && mm.records.contains(&x.id) && x.index.is_some()).collect();
        assert_eq!(places.len(), 42);
        assert!(places.iter().all(|x| x.established(mm.empty) && x.offered(false).iter().any(|(v, l)| *v == mm.empty && l == "(empty)")),
            "every My Menu place offers \"(empty)\" outside Expert mode");
        // every Fn Menu place offers the functions its picker lists on the camera, the codes its group's walks proved
        // (72, 72 and 33), and no code a spelling fix alone once named (a Custom Key's "Regist. Face Priority", 1008)
        // and every playback Custom Key the 38 functions its picker lists, lent from the AEL key's full walk
        let keys: Vec<&Setting> = shipped.settings.iter().filter(|x| ["global:0x0441", "global:0x043a", "global:0x043b", "global:0x043c", "global:0x043d", "global:0x043e", "global:0x0442", "global:0x1244"].contains(&x.key.as_str())).collect();
        let walked: std::collections::BTreeSet<i64> = keys.iter().filter_map(|x| x.proved.as_ref()).flat_map(|p| p.values.iter().copied()).collect();
        assert_eq!((keys.len(), walked.len()), (8, 38));
        for x in &keys {
            assert_eq!(x.offered(false).into_iter().map(|(v, _)| v).collect::<std::collections::BTreeSet<i64>>(), walked, "{}", x.key);
        }
        for (rec, n) in [(0x0445u16, 72usize), (0x0451, 72), (0x12e7, 33)] {
            let fn_places: Vec<&Setting> = shipped.settings.iter().filter(|x| x.area == "global" && x.id == rec && x.index.is_some()).collect();
            let walked: std::collections::BTreeSet<i64> = fn_places.iter().filter_map(|x| x.proved.as_ref()).flat_map(|p| p.values.iter().copied()).collect();
            assert_eq!((fn_places.len(), walked.len()), (12, n), "0x{rec:04x}");
            for x in &fn_places {
                let offered: std::collections::BTreeSet<i64> = x.offered(false).into_iter().map(|(v, _)| v).collect();
                assert_eq!(offered, walked, "{}", x.key);
                assert!(x.offered(false).iter().filter(|(_, l)| l == "Regist. Face Priority").count() <= 1, "{}", x.key);
            }
        }
    }

    /// The shipped set and the user's folder: the user's definition of the same model and firmware is used in place
    /// of the shipped one, a file that is not a definition is listed as not used, and a second file of the same
    /// model and firmware in one folder is not used either.
    #[test]
    fn the_users_folder_overrides_the_shipped_set() {
        let (ship, user) = (scratch("ship"), scratch("user"));
        std::fs::copy(shipped().join("ILCE-1M2_fw4.00.json"), ship.join("ILCE-1M2_fw4.00.json")).unwrap();
        let d = Definitions::load(Some(ship.clone()), vec![ship.clone()], user.clone(), &[]);
        assert_eq!(d.list.len(), 1);
        assert!(d.find("ILCE-1M2", "4.00").unwrap().origin.is_shipped());
        assert!(d.rejected.is_empty() && d.misnamed.is_empty());
        assert_eq!(d.works_with(), vec!["ILCE-1M2 · α1 II (firmware 4.00)".to_string()], "a built-in one by its model and firmware");
        assert_eq!(d.magic_len(), 5, "a file's first bytes read to tell a settings file: SONY1 at 0x00");
        // the user's copy, one setting renamed
        let name = embedded().settings[0].name.clone();
        let mine = a1_with(|v| v["settings"][0]["name"] = "Renamed by me".into());
        std::fs::write(user.join("ILCE-1M2_fw4.00.json"), &mine).unwrap();
        std::fs::write(user.join("notes.json"), "{\"a\": 1}").unwrap();
        std::fs::write(user.join("newer.json"), a1_with(|v| v["definition_format"] = 9.into())).unwrap();
        std::fs::write(user.join("zz_copy.json"), &mine).unwrap();
        let d = Definitions::load(Some(ship.clone()), vec![], user.clone(), &[]);
        let used = d.find("ILCE-1M2", "4.00").unwrap();
        assert_eq!(used.origin, Origin::User(user.join("ILCE-1M2_fw4.00.json")));
        assert!(used.overrides && used.settings[0].name == "Renamed by me");
        let built_in = d.shipped("ILCE-1M2", "4.00").unwrap();
        assert!(built_in.overridden && built_in.settings[0].name == name, "the shipped one stays as it was, for the sample");
        assert_eq!(d.in_use().count(), 1);
        assert_eq!(d.works_with(), vec!["ILCE-1M2 · α1 II (firmware 4.00, yours, in place of the built-in one)".to_string()], "the model code with the name photographers know (camera.display_name); the user's own in Settings' words");
        assert_eq!((d.model_words("ILCE-1M2"), d.model_words("ILCE-0000")), ("ILCE-1M2 · α1 II".to_string(), "ILCE-0000".to_string()));
        let why = |f: &str| d.rejected.iter().find(|(p, _)| p.ends_with(f)).map(|(_, w)| w.clone()).unwrap_or_default();
        assert!(why("notes.json").contains("no settings list"));
        assert!(why("newer.json").contains("needs a newer Camset Editor"));
        assert!(why("zz_copy.json").contains("defined already by ILCE-1M2_fw4.00.json"), "{}", why("zz_copy.json"));
        // no shipped folder at all: only the user's
        let d = Definitions::load(None, vec![ship.join("missing")], user.clone(), &[]);
        assert_eq!(d.list.len(), 1);
        assert!(!d.list[0].overrides);
        assert_eq!(d.works_with(), vec!["ILCE-1M2 · α1 II (firmware 4.00, added by you)".to_string()], "the user's own, with no built-in one");
        // a definition under another name is used, and the name it should have is said
        std::fs::remove_file(user.join("ILCE-1M2_fw4.00.json")).unwrap();
        let d = Definitions::load(None, vec![], user.clone(), &[]);
        assert_eq!(d.misnamed, vec![(user.join("zz_copy.json"), "ILCE-1M2_fw4.00.json".to_string())]);
        let _ = std::fs::remove_dir_all(&ship);
        let _ = std::fs::remove_dir_all(&user);
    }

    #[test]
    fn a_set_setting_says_where_no_proof_reaches_it() {
        let s = embedded();
        let raw = s.settings.iter().find(|x| x.key == "set:0x0180@260").unwrap();
        assert_eq!(raw.proof_badge_in(4).0, "Not on this camera in this memory set");
        assert_eq!(raw.proof_badge_in(1).0, raw.proof_badge().0);
        assert!(raw.unproved_in(0).is_none());
    }

    /// Every kind of reason the definition schema allows (`unproved_reason.kind`) has words of its own, for the live
    /// settings and for a memory set, none of them the words of a kind this editor does not know; the shipped
    /// definition's settings with a reason show those words, its why on hover (2026-11-09: state, camera_only,
    /// equipment, network and unknown beside not_on_camera and skipped).
    #[test]
    fn each_reason_kind_has_its_own_words() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("schemas").join("definition.schema.json");
        let schema: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let setting = &schema["$defs"]["setting"]["properties"];
        let kinds: Vec<&str> = setting["unproved_reason"]["properties"]["kind"]["enum"].as_array().unwrap()
            .iter().map(|k| k.as_str().unwrap()).collect();
        assert_eq!(setting["unproved_sets"]["properties"]["kind"]["enum"], setting["unproved_reason"]["properties"]["kind"]["enum"]);
        assert!(kinds.len() >= 7, "{kinds:?}");
        for in_set in [false, true] {
            let words: std::collections::BTreeSet<String> = kinds.iter().map(|k| unproved_words(k, in_set)).collect();
            assert_eq!(words.len(), kinds.len(), "one wording per kind: {words:?}");
            assert!(!words.contains(&unproved_words("a kind from a newer definition", in_set)));
            assert!(words.iter().all(|w| w.contains("this memory set") == in_set), "{words:?}");
        }
        let s = embedded();
        let shown: std::collections::BTreeSet<&str> = s.settings.iter().filter(|x| x.proved.is_none())
            .filter_map(|x| x.unproved_reason.as_ref()).map(|u| u.kind.as_str()).collect();
        for kind in ["not_on_camera", "state", "camera_only", "equipment", "network", "unknown"] {
            assert!(shown.contains(kind), "the shipped definition has a reason of kind {kind}: {shown:?}");
            let x = s.settings.iter().find(|x| x.proved.is_none() && x.unproved_reason.as_ref().is_some_and(|u| u.kind == kind)).unwrap();
            assert_eq!(x.proof_badge(), (unproved_words(kind, false), "na"));
            assert!(!x.unproved_reason.as_ref().unwrap().why.is_empty(), "{} says why", x.key);
        }
    }

    /// Focus Area as the camera lays it out (`option_tree`): its main options, Spot with its sizes in the camera's
    /// order, the flat labels kept in `values`; choosing an option keeps the choice held when it is one of its own,
    /// else takes its first; a tree that does not fit the values is not used, and the flat list is shown.
    #[test]
    fn focus_area_is_nested_as_on_the_camera() {
        let s = embedded();
        let fa = s.settings.iter().find(|x| x.key == "global:0x0f46").unwrap();
        let tree = fa.option_tree().expect("the shipped definition nests Focus Area");
        let mains: Vec<&str> = tree.iter().map(|n| n.label.as_str()).collect();
        assert_eq!(mains, ["Wide", "Zone", "Center Fix", "Spot", "Expand Spot", "Custom", "Tracking"]);
        let spot = &tree[3];
        assert_eq!(spot.options.iter().map(|(_, l)| l.as_str()).collect::<Vec<_>>(), ["XL", "L", "M", "S", "XS"]);
        let m = spot.options[2].0;
        assert_eq!(fa.label_for(m), Some("Spot: M"), "the flat label stays the value's own");
        let all: Vec<i64> = fa.values.iter().map(|(v, _)| *v).collect();
        assert_eq!(spot.pick(Some(m), &all), Some(m), "already on Spot: its size stays");
        let wide = tree[0].value.unwrap();
        assert_eq!(spot.pick(Some(wide), &all), Some(spot.options[0].0), "from Wide: the first size");
        assert_eq!(spot.pick(Some(wide), &[m]), Some(m), "the first size the editor offers");
        assert_eq!(tree[0].pick(Some(m), &all), Some(wide));
        assert!(fa.nests_option("Spot") && fa.nests_option("Spot: M") && !fa.nests_option("Wide"));
        // a tree that does not fit: a value twice, a value missing, no option with choices
        let mut bad = fa.clone();
        bad.option_tree[0].value = bad.option_tree[3].options.first().map(|(v, _)| *v);
        assert!(bad.option_tree().is_none());
        let mut bad = fa.clone();
        bad.option_tree.remove(0);
        assert!(bad.option_tree().is_none());
        let mut bad = fa.clone();
        bad.option_tree.retain(|n| !n.is_nest());
        assert!(bad.option_tree().is_none());
        // a setting the camera lists flat has none
        let wb = s.settings.iter().find(|x| x.key == "global:0x0367").unwrap();
        assert!(wb.option_tree.is_empty() && wb.option_tree().is_none() && !wb.nests_option("Fluor.: Warm White"));
    }

    #[test]
    fn a_help_file_replaces_the_schemas_help() {
        let mut s = embedded();
        let key = s.settings[0].key.clone();
        let dir = std::env::temp_dir().join(format!("camset_help_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let file = serde_json::json!({"model": s.model, "firmware": s.layouts[0].firmware, "source": "a test",
            "settings": {key.clone(): {"help": "From the help file.", "option_help": [[1, "One."]]}}});
        std::fs::write(dir.join(s.help_file_name()), file.to_string()).unwrap();
        s.apply_help(&[dir.join("missing"), dir.clone()]);
        let set = s.settings.iter().find(|x| x.key == key).unwrap();
        assert_eq!(set.help, "From the help file.");
        assert!(set.help_from_file);
        assert_eq!(set.option_help(1), Some("One."));
        assert!(s.help_src.ends_with("(a test)"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_help_file_keeps_the_definitions_own_words_where_it_has_none() {
        // text by text: the file's help is the camera's, and where the file holds none the definition's own words stay
        let mut s = embedded();
        for (i, set) in s.settings.iter_mut().take(3).enumerate() {
            set.help = format!("Own words {i}.");
            set.option_help = vec![(0, format!("Own option {i}."))];
        }
        let keys: Vec<String> = s.settings.iter().take(3).map(|x| x.key.clone()).collect();
        let dir = std::env::temp_dir().join(format!("camset_help_own_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let file = serde_json::json!({"model": s.model, "firmware": s.layouts[0].firmware, "source": "a test",
            "settings": {keys[0].clone(): {"help": "The camera's words."}, keys[1].clone(): {"option_help": [[0, "The camera's option."]]}}});
        std::fs::write(dir.join(s.help_file_name()), file.to_string()).unwrap();
        s.apply_help(std::slice::from_ref(&dir));
        let get = |k: &str| s.settings.iter().find(|x| x.key == k).unwrap();
        assert_eq!((get(&keys[0]).help.as_str(), get(&keys[0]).help_from_file, get(&keys[0]).option_help(0)), ("The camera's words.", true, Some("Own option 0.")));
        assert_eq!((get(&keys[1]).help.as_str(), get(&keys[1]).help_from_file, get(&keys[1]).option_help(0)), ("Own words 1.", false, Some("The camera's option.")));
        assert_eq!((get(&keys[2]).help.as_str(), get(&keys[2]).help_from_file), ("Own words 2.", false));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Option help goes value by value: the file's text for a value where it has one, else the definition's own; a
    /// value only the file has is added; and each says whose (`option_help_from_file`).
    #[test]
    fn option_help_is_replaced_value_by_value() {
        let mut s = embedded();
        s.settings[0].option_help = vec![(0, "Own zero.".into()), (1, "Own one.".into())];
        let key = s.settings[0].key.clone();
        let dir = scratch("help_by_value");
        let file = serde_json::json!({"model": s.model, "firmware": s.layouts[0].firmware, "source": "a test",
            "settings": {key: {"option_help": [[1, "The camera's one."], [2, "The camera's two."], [0, ""]]}}});
        std::fs::write(dir.join(s.help_file_name()), file.to_string()).unwrap();
        s.apply_help(std::slice::from_ref(&dir));
        let set = &s.settings[0];
        assert_eq!((set.option_help(0), set.option_help(1), set.option_help(2)), (Some("Own zero."), Some("The camera's one."), Some("The camera's two.")));
        assert_eq!(set.option_help_from_file, vec![1, 2], "an empty text is not the camera's");
        assert!(!set.help_from_file, "no help for the setting itself in the file");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// A help file is used only for the camera it says it is for: one named for this definition that carries another
    /// model, or another firmware of the same model, or names neither, or is not a help file, is not used and says
    /// why, and the definition's own words stay; a fitting file in a later folder is used.
    #[test]
    fn a_help_file_is_used_only_for_the_camera_it_says_it_is_for() {
        let mut base = embedded();
        base.settings[0].help = "Own words.".into();
        base.settings[0].option_help = vec![(0, "Own option.".into())];
        let key = base.settings[0].key.clone();
        let (dir, good) = (scratch("help_refused"), scratch("help_fitting"));
        let name = base.help_file_name();
        let body = |model: Option<&str>, fw: Option<&str>| {
            let mut v = serde_json::json!({"source": "a test",
                "settings": {key.clone(): {"help": "Another camera's words.", "option_help": [[0, "Another camera's option."]]}}});
            if let Some(m) = model { v["model"] = m.into(); }
            if let Some(f) = fw { v["firmware"] = f.into(); }
            v.to_string()
        };
        let neither = "it does not say which camera it is for (its model and firmware)";
        for (text, why) in [
            (body(Some("ILCE-0X0"), Some("4.00")), "it is for the ILCE-0X0 firmware 4.00, not the ILCE-1M2 firmware 4.00"),
            (body(Some("ILCE-1M2"), Some("3.00")), "it is for the ILCE-1M2 firmware 3.00, not the ILCE-1M2 firmware 4.00"),
            (body(None, None), neither),
            (body(Some("ILCE-1M2"), None), neither),
            ("{ not json".to_string(), "it does not read as a help file"),
        ] {
            let mut s = base.clone();
            std::fs::write(dir.join(&name), text).unwrap();
            s.apply_help(std::slice::from_ref(&dir));
            let set = &s.settings[0];
            assert_eq!((set.help.as_str(), set.option_help(0)), ("Own words.", Some("Own option.")), "{why}");
            assert!(s.settings.iter().all(|x| !x.help_from_file && x.option_help_from_file.is_empty()), "{why}");
            assert!(s.help_src.is_empty(), "{why}");
            assert_eq!(s.help_refused, vec![(dir.join(&name), why.to_string())]);
            assert_eq!(s.help_refusals(), vec![format!("Help file not used: {name}: {why}. The help shown is Camset's own, from the definition, where it has some.")]);
        }
        // the refused file first, a fitting one in the next folder: that one is used, and the refused one still named
        std::fs::write(good.join(&name), serde_json::json!({"model": "ILCE-1M2", "firmware": "4.00", "source": "a test",
            "settings": {key.clone(): {"help": "This camera's words."}}}).to_string()).unwrap();
        let mut s = base.clone();
        s.apply_help(&[dir.clone(), good.clone()]);
        assert_eq!((s.settings[0].help.as_str(), s.settings[0].help_from_file), ("This camera's words.", true));
        assert_eq!(s.help_refused.len(), 1);
        assert!(s.help_refusals()[0].ends_with("which is for this camera, is used instead."), "{:?}", s.help_refusals());
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&good);
    }

    /// The owner's rule ("a new user with a different camera shouldn't get the a1 II help"): a made-up second
    /// camera's definition beside the shipped ILCE-1M2 one gets none of the ILCE-1M2's help file, which is not named
    /// for it, nor of a copy renamed for it, which says inside whose it is; nor does another firmware of the ILCE-1M2.
    /// The ILCE-1M2's own definition still gets it.
    #[test]
    fn another_cameras_definition_gets_none_of_the_a1s_help() {
        let (user, help) = (scratch("help_other_user"), scratch("help_other_help"));
        let bare = |model: &str, fw: &str| a1_with(|v| {
            v["model"] = model.into(); v["layouts"][0]["model"] = model.into(); v["layouts"][0]["firmware"] = fw.into();
            v["camera"]["model"] = model.into();
            for s in v["settings"].as_array_mut().unwrap() {
                let o = s.as_object_mut().unwrap();
                o.remove("help");
                o.remove("option_help");
            }
        });
        std::fs::write(user.join("ILCE-0X0_fw4.00.json"), bare("ILCE-0X0", "4.00")).unwrap();
        std::fs::write(user.join("ILCE-1M2_fw3.00.json"), bare("ILCE-1M2", "3.00")).unwrap();
        let all: serde_json::Map<String, serde_json::Value> = embedded().settings.iter()
            .map(|s| (s.key.clone(), serde_json::json!({"help": "The a1 II's words.", "option_help": [[0, "An a1 II option."]]}))).collect();
        let a1s = serde_json::json!({"model": "ILCE-1M2", "firmware": "4.00", "source": "a test", "settings": all}).to_string();
        std::fs::write(help.join("help_ILCE-1M2_fw4.00.json"), &a1s).unwrap();
        let none_of_it = |s: &Schema| s.settings.iter().all(|x| x.help.is_empty() && x.option_help.is_empty() && !x.help_from_file && x.option_help_from_file.is_empty());
        let d = Definitions::load(Some(shipped()), vec![shipped()], user.clone(), std::slice::from_ref(&help));
        let a1 = d.find("ILCE-1M2", "4.00").unwrap();
        assert!(a1.settings.iter().all(|x| x.help == "The a1 II's words." && x.help_from_file && x.option_help_from_file.contains(&0)));
        for (model, fw) in [("ILCE-0X0", "4.00"), ("ILCE-1M2", "3.00")] {
            let other = d.find(model, fw).unwrap();
            assert!(none_of_it(other) && other.help_src.is_empty() && other.help_refused.is_empty(), "{model} {fw}");
        }
        // the a1 II's file copied under the other two's names: refused for what it says inside
        std::fs::write(help.join("help_ILCE-0X0_fw4.00.json"), &a1s).unwrap();
        std::fs::write(help.join("help_ILCE-1M2_fw3.00.json"), &a1s).unwrap();
        let d = Definitions::load(Some(shipped()), vec![shipped()], user.clone(), std::slice::from_ref(&help));
        for (model, fw) in [("ILCE-0X0", "4.00"), ("ILCE-1M2", "3.00")] {
            let other = d.find(model, fw).unwrap();
            assert!(none_of_it(other) && other.help_src.is_empty(), "{model} {fw}");
            assert_eq!(other.help_refused, vec![(help.join(other.help_file_name()), format!("it is for the ILCE-1M2 firmware 4.00, not the {model} firmware {fw}"))]);
        }
        assert!(d.find("ILCE-1M2", "4.00").unwrap().help_refused.is_empty());
        let _ = std::fs::remove_dir_all(&user);
        let _ = std::fs::remove_dir_all(&help);
    }

    #[test]
    fn schema_without_camera_loads_and_hides_features() {
        let s = Schema::from_text(&a1_with(|v| { v.as_object_mut().unwrap().remove("camera"); })).expect("a schema without \"camera\" must load");
        let c = &s.camera;
        assert!(c.model.is_none() && c.section_counts.is_empty() && c.file.is_none());
        assert!(c.main_tiles.is_none() && c.my_menu.is_none() && c.memory_sets.is_none());
        assert!(c.dial().is_empty() && !c.is_dial(1));
        assert!(c.link_warnings("network", |_| Some(1)).is_empty());
        assert!(c.link_warnings("usb", |_| Some(1)).is_empty());
        assert!(c.volatile_records.is_empty() && c.tab_colors.is_empty() && c.families.is_empty());
        assert!(c.text.save_load_path.is_none() && c.text.max_settings_files_on_card.is_none());
        assert!(c.text.connect_usb_steps.is_empty() && c.text.connect_network_steps.is_empty() && c.text.address_hint.is_none());
        assert_eq!(c.target_name(0), "Live settings");
        assert_eq!(c.target_name(2), "Set 2");
        assert!(c.exposure.is_none());
    }

    #[test]
    fn exposure_page_names_real_records() {
        let s = embedded();
        let Some(ex) = &s.camera.exposure else { return };
        let get = |k: &str| s.settings.iter().find(|x| x.key == k);
        let sides = [(&ex.aperture, crate::stops::Side::Aperture), (&ex.shutter, crate::stops::Side::Shutter), (&ex.iso, crate::stops::Side::Iso)];
        let mut keys = vec![ex.mode_key.as_str(), ex.memory_mode_key.as_str(), ex.comp_key.as_str(), ex.step_key.as_str()];
        for (side, kind) in sides {
            keys.extend([side.key.as_str(), side.memory_key.as_str(), side.memory_numerator_key.as_str(), side.memory_denominator_key.as_str(), side.scale_key.as_str()]);
            for l in &side.limits {
                keys.extend([l.min_key.as_str(), l.max_key.as_str(), l.key.as_str()]);
                assert!(["always", "camera", "camera_iso_auto"].contains(&l.applies.as_str()), "{}: applies {:?}", l.name, l.applies);
            }
            // the scale spans at least a few stops of the record's own labels
            let sc = get(&side.scale_key).unwrap_or_else(|| panic!("scale key {:?}", side.scale_key));
            let st: Vec<f64> = sc.values.iter().filter_map(|(_, l)| crate::stops::stops(kind, l)).collect();
            assert!(st.len() >= 5, "{:?}: {} labels read as stops", side.scale_key, st.len());
        }
        for k in keys.into_iter().filter(|k| !k.is_empty()) {
            assert!(get(k).is_some(), "exposure key {k} is not in the schema");
        }
        // every exposure mode the mode records can hold says who sets what
        for k in [&ex.mode_key, &ex.memory_mode_key] {
            for (_, label) in &get(k).unwrap().values {
                let c = ex.control.get(label).unwrap_or_else(|| panic!("mode {label:?} has no control entry"));
                for w in [&c.aperture, &c.shutter] {
                    assert!(w == "you" || w == "camera", "{label}: {w:?}");
                }
            }
        }
    }

    #[test]
    fn camera_definition_drives_names_and_warnings() {
        let s = embedded();
        let c = &s.camera;
        let Some(m) = &c.memory_sets else { return }; // a definition without memories names nothing
        for &d in &m.dial {
            assert!(c.is_dial(d));
            assert_eq!(c.short_name(d), format!("M{d}"));
        }
        // every tile key names a setting in the schema
        if let Some(t) = &c.main_tiles {
            for tile in t.0.iter().flat_map(|set| set.tiles.iter()) {
                for k in tile.keys.iter().chain(&tile.memory_keys).chain(&tile.numerator_key).chain(&tile.denominator_key) {
                    assert!(s.settings.iter().any(|x| &x.key == k), "tile {} key {k} is not in the schema", tile.caption);
                }
            }
        }
        // a grouped record warns only when every record of its group fails
        let net: Vec<&LinkRecord> = c.link_records.iter().filter(|r| r.link == "network").collect();
        if let Some(g) = net.iter().find_map(|r| r.group.clone()) {
            let members: Vec<u16> = net.iter().filter(|r| r.group.as_ref() == Some(&g)).map(|r| r.record).collect();
            let all_ok = |id: u16| net.iter().find(|r| r.record == id).and_then(|r| r.ok_values.first().copied());
            let bad = |id: u16| net.iter().find(|r| r.record == id).map(|r| (0..100).find(|v| !r.ok_values.contains(v)).unwrap());
            assert!(c.link_warnings("network", all_ok).is_empty());
            let first = members[0];
            assert!(c.link_warnings("network", |id| if id == first { bad(id) } else { all_ok(id) }).is_empty() || members.len() == 1);
            assert!(!c.link_warnings("network", |id| if members.contains(&id) { bad(id) } else { all_ok(id) }).is_empty());
        }
    }

    #[test]
    fn camera_definition_knows_the_sample_files() {
        let s = embedded();
        if s.camera.model.is_none() { return; }
        // the files in private/ (when it is there) whose headers name this definition's model and firmware, chosen by
        // what their headers say, never by their names; the built-in sample always
        let mut files = crate::camset::tests::private_files(crate::camset::tests::of_the_definition);
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        files.push(root.join("editor").join("definitions").join("ILCE-1M2_fw4.00.DAT"));
        for f in files.iter().map(|p| p.display().to_string()) {
            let Ok(d) = std::fs::read(&f) else { continue };
            let c = CamSet::parse(&d, &Arc::new(s.camera.file.clone().unwrap())).unwrap();
            assert!(s.camera.knows(&c), "{f}");
            let other = Camera { model: Some("another body".into()), ..s.camera.clone() };
            assert!(!other.knows(&c));
        }
    }

    /// The editor's built-in sample.
    fn sample_bytes() -> Vec<u8> {
        std::fs::read(shipped().join("ILCE-1M2_fw4.00.DAT")).unwrap()
    }

    /// `d` with its model, firmware and video system bytes changed (the firmware's two, then the video system's: the
    /// ILCE-1M2's block reads them at 0x36-0x38), both checksums worked out again under the ILCE-1M2's block.
    fn retitled(d: &[u8], model: &[u8], fw: [u8; 3]) -> Vec<u8> {
        let mut c = CamSet::parse(d, &Arc::new(embedded().camera.file.unwrap())).unwrap();
        c.header[5..0x15].fill(0);
        c.header[5..5 + model.len()].copy_from_slice(model);
        c.header[0x36..0x39].copy_from_slice(&fw);
        c.to_bytes()
    }

    /// A file picks its definition by trial (docs/decisions/0019, 0020): its model and firmware, else the nearest
    /// firmware of its model, else none; two definitions sharing one container pick by model; a file no block holds
    /// is refused; a damaged one too.
    #[test]
    fn a_file_picks_its_definition() {
        let (ship, user) = (scratch("pick_ship"), scratch("pick_user"));
        std::fs::write(ship.join("ILCE-1M2_fw4.00.json"), a1_text()).unwrap();
        // the same body at firmware 3.00, and another model (made up) sharing the container
        std::fs::write(ship.join("ILCE-1M2_fw3.00.json"), a1_with(|v| v["layouts"][0]["firmware"] = "3.00".into())).unwrap();
        std::fs::write(ship.join("ILCE-0X0_fw1.00.json"), a1_with(|v| {
            v["model"] = "ILCE-0X0".into(); v["layouts"][0]["model"] = "ILCE-0X0".into(); v["layouts"][0]["firmware"] = "1.00".into();
            v["camera"]["model"] = "ILCE-0X0".into(); v["settings"][0]["name"] = "The other body's".into();
        })).unwrap();
        let d = Definitions::load(Some(ship.clone()), vec![], user.clone(), &[]);
        assert_eq!(d.list.len(), 3, "{:?}", d.rejected);
        let name = |o: &Opened| o.def.map(|i| (d.list[i].model.clone(), d.list[i].firmware().to_string()));
        let sample = sample_bytes();
        let o = d.open(&sample, false).unwrap();
        assert_eq!((name(&o), &o.how), (Some(("ILCE-1M2".into(), "4.00".into())), &Match::Exact));
        // firmware 4.00 saved with the camera on PAL: the same firmware, its own definition
        let o = d.open(&retitled(&sample, b"ILCE-1M2", [4, 0, 1]), false).unwrap();
        assert_eq!((name(&o), &o.how, o.set.firmware().as_str()), (Some(("ILCE-1M2".into(), "4.00".into())), &Match::Exact, "4.00"));
        assert_eq!(o.set.video_system(), Some((1, Some("PAL".into()))));
        // firmware 3.00 on PAL (03 00 01, which the old reading took for 3.01): its own definition too
        let o = d.open(&retitled(&sample, b"ILCE-1M2", [3, 0, 1]), false).unwrap();
        assert_eq!((name(&o), &o.how), (Some(("ILCE-1M2".into(), "3.00".into())), &Match::Exact));
        // firmware 3.01: the nearest is 3.00
        let o = d.open(&retitled(&sample, b"ILCE-1M2", [3, 1, 0]), false).unwrap();
        assert_eq!((name(&o), &o.how), (Some(("ILCE-1M2".into(), "3.00".into())), &Match::Near { file_fw: "3.01".into() }));
        // 3.50: as near to 3.00 as to 4.00, so the newer
        let o = d.open(&retitled(&sample, b"ILCE-1M2", [3, 50, 0]), false).unwrap();
        assert_eq!(name(&o), Some(("ILCE-1M2".into(), "4.00".into())));
        // another model sharing the container: its own definition
        let o = d.open(&retitled(&sample, b"ILCE-0X0", [1, 0, 0]), false).unwrap();
        assert_eq!((name(&o), &o.how), (Some(("ILCE-0X0".into(), "1.00".into())), &Match::Exact));
        // a model no definition covers: read with the container's framing, nothing named
        let o = d.open(&retitled(&sample, b"ILCE-9Z9", [4, 0, 0]), false).unwrap();
        assert_eq!((o.def, &o.how, o.set.model().as_str()), (None, &Match::None, "ILCE-9Z9"));
        assert_eq!(o.set.layout(), CamSet::read(&sample, &Arc::new(embedded().camera.file.unwrap())).unwrap().layout());
        // first bytes no block holds, a damaged file, and no definition at all
        let mut other = sample.clone();
        other[..5].copy_from_slice(b"SONY2");
        assert_eq!(d.open(&other, false).unwrap_err(), CamSetError::NotCamSet);
        assert!(!d.is_settings_file(&other) && d.is_settings_file(&sample));
        let mut damaged = sample.clone();
        damaged[0x100] ^= 0xff;
        assert!(matches!(d.open(&damaged, false), Err(CamSetError::BadChecksum { .. } | CamSetError::BadMarker(_))));
        let none = Definitions::load(None, vec![], user.clone(), &[]);
        assert_eq!(none.open(&sample, false).unwrap_err(), CamSetError::NotCamSet, "with no definition loaded, no file opens");
        // a definition without a file block describes no file
        std::fs::write(user.join("ILCE-1M2_fw4.00.json"), a1_with(|v| { v["camera"].as_object_mut().unwrap().remove("file"); })).unwrap();
        let d = Definitions::load(Some(ship.clone()), vec![], user.clone(), &[]);
        let o = d.open(&sample, false).unwrap();
        assert_eq!(name(&o), Some(("ILCE-1M2".into(), "3.00".into())), "the user's 4.00 describes no file: the nearest that does");
        let o = d.open(&sample, true).unwrap();
        assert_eq!((name(&o), &o.how), (Some(("ILCE-1M2".into(), "4.00".into())), &Match::Exact), "shipped only, as the sample is read");
        let _ = std::fs::remove_dir_all(&ship);
        let _ = std::fs::remove_dir_all(&user);
    }

    /// The settings shown in Expert mode only are the definition's `expert` ones: exactly those the editor once
    /// picked by their names (derived copies, flags, alternate numberings), the rule moved and the set not, and My
    /// Menu's places (the live settings of the records `camera.my_menu` names), which the My Menu page edits.
    #[test]
    fn expert_settings_are_the_definitions() {
        let s = embedded();
        let places = s.camera.my_menu.as_ref().map(|m| m.records.clone()).unwrap_or_default();
        let by_name = |x: &Setting| (x.area == "global" && places.contains(&x.id))
            || (x.name.to_lowercase().contains("(copy") && x.copy_of.is_none());
        // the definition's flags are the truth (the kit's rule may flag more); the old name rule's set stays inside them
        let flagged: Vec<&str> = s.settings.iter().filter(|x| x.expert).map(|x| x.key.as_str()).collect();
        let named: Vec<&str> = s.settings.iter().filter(|x| by_name(x)).map(|x| x.key.as_str()).collect();
        let missing: Vec<&&str> = named.iter().filter(|k| !flagged.contains(k)).collect();
        assert!(missing.is_empty(), "named as Expert but not flagged: {missing:?}");
        assert!(!flagged.is_empty() && flagged.len() < s.settings.len());
    }

    /// Memory-set wording and columns come from the definition; without them, the editor's own plain fallbacks.
    #[test]
    fn memory_sets_words_and_columns() {
        let c = embedded().camera;
        assert_eq!((c.short_name(0), c.short_name(2), c.short_name(5)), ("Live".to_string(), "M2".to_string(), "S5".to_string()));
        assert_eq!(c.modes().iter().map(|(m, _)| *m).collect::<Vec<_>>(), ["Stills", "Movie", "S&Q", "Time-lapse"], "ordered by their first set");
        assert_eq!(c.start_columns(false), [0, 1, 2, 3]);
        assert_eq!(c.start_columns(true), [0, 1, 2, 3, 4, 5, 6]);
        assert_eq!(c.more_columns_modes(), Some(("Stills".into(), "Movie".into())));
        assert_eq!(c.text.memories_title.as_deref(), Some("Memories {list}"));
        // a definition that names short labels of its own, and none of the rest
        let m = MemorySets { dial: vec![1], short_names: [("1".to_string(), "MR1".to_string())].into(), ..Default::default() };
        let other = Camera { memory_sets: Some(m), ..Default::default() };
        assert_eq!((other.short_name(1), other.short_name(2)), ("MR1".to_string(), "S2".to_string()));
        assert_eq!(other.start_columns(true), [0, 1], "no modes: the live settings and the dial");
        assert!(other.more_columns_modes().is_none());
        assert!(Camera::default().mirrors.is_empty());
    }

    /// An unknown kind in the file block refuses the whole definition, by name.
    #[test]
    fn an_unknown_file_kind_refuses_the_definition() {
        let e = Schema::from_text(&a1_with(|v| v["camera"]["file"]["header_checksum"]["kind"] = "crc32".into())).unwrap_err();
        assert!(e.contains("unknown variant `crc32`"), "{e}");
        let e = Schema::from_text(&a1_with(|v| v["camera"]["file"]["sections_start"] = "end-4".into())).unwrap_err();
        assert!(e.contains("file block does not hold together"), "{e}");
    }

    #[test]
    fn schema_integrity_and_no_overlaps() {
        let schema = embedded();
        assert_eq!(schema.find(true, 0x0b8d).unwrap().key, "set:0x0b8d");
        assert_eq!(schema.find(false, 0x0b8d).unwrap().key, "global:0x0b8d");

        let mut seen = std::collections::HashMap::new();
        for s in &schema.settings {
            let key = (&s.area, s.id);
            let indices = seen.entry(key).or_insert_with(Vec::new);
            for prev in indices.iter() {
                match (prev, &s.index) {
                    (None, None) => panic!("duplicate unindexed setting for {:?}", key),
                    (None, Some(_)) | (Some(_), None) => panic!("colliding index (None vs Some) for {:?}", key),
                    (Some(a), Some(b)) if a == b => panic!("duplicate index Some({}) for {:?}", a, key),
                    _ => {}
                }
            }
            indices.push(s.index);
        }

        for s in &schema.settings {
            if matches!(s.size, 1 | 2 | 4) {
                let limit = 1i64 << (8 * s.size - 1);
                let bounds = -limit..=limit - 1;
                for (v, _) in &s.values {
                    assert!(bounds.contains(v), "setting {} value {} out of bounds {:?}", s.key, v, bounds);
                }
                if let Some((min, max)) = s.range {
                    assert!(bounds.contains(&min), "setting {} range min {} out of bounds {:?}", s.key, min, bounds);
                    assert!(bounds.contains(&max), "setting {} range max {} out of bounds {:?}", s.key, max, bounds);
                }
                for v in &s.refused {
                    assert!(bounds.contains(v), "setting {} refused {} out of bounds {:?}", s.key, v, bounds);
                }
            }
        }
    }

    /// A damaged file through the definitions (`Definitions::open`: magic, model and firmware peeked, a definition
    /// picked, the records framed with its container block) never panics, and neither does what the editor asks of
    /// what opens: the sample cut short, one header byte damaged (with the checksums worked out again, so another
    /// model or firmware reads, or a time or name with odd bytes), random bytes behind the header, a file of no
    /// sections at all.
    #[test]
    fn damaged_files_through_the_definitions_never_panic() {
        use crate::camset::tests::{resealed, use_all, Rng, DAMAGE};
        let ship = shipped();
        let defs = Definitions::load(Some(ship.clone()), vec![ship], scratch("hostile_user"), &[]);
        let block = embedded().camera.file.unwrap();
        let sample = sample_bytes();
        let start = 0x3c;
        let open = |what: &str, d: &[u8]| -> bool {
            let opened = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let mut any = false;
                for shipped_only in [false, true] {
                    if let Ok(o) = defs.open(d, shipped_only) {
                        use_all(&o.set);
                        if let Some(s) = o.def.and_then(|i| defs.list.get(i)) {
                            let _ = (s.layout(&o.set.layout_signature()), s.camera.knows(&o.set), s.model_words());
                        }
                        any = true;
                    }
                }
                any
            }));
            opened.unwrap_or_else(|_| panic!("opening panicked on {what}"))
        };
        assert!(open("the sample", &sample));
        let mut lengths: Vec<usize> = (0..start + 256).collect();
        lengths.extend((start + 256..sample.len()).step_by(4999));
        for n in lengths {
            assert!(!open(&format!("the sample cut to {n} bytes"), &sample[..n]), "cut to {n} bytes: refused");
        }
        for at in 0..start {
            for damage in DAMAGE {
                let mut d = sample.clone();
                d[at] = damage(d[at]);
                let _ = open(&format!("header byte 0x{at:02x} damaged"), &d);
                let _ = open(&format!("header byte 0x{at:02x} damaged, resealed"), &resealed(&block, d));
            }
        }
        let mut rng = Rng(0x5eed);
        for i in 0..300 {
            let mut d = sample[..start].to_vec();
            let n = rng.below(2000);
            d.extend(rng.bytes(n));
            let _ = open(&format!("random bytes behind the header #{i}"), &resealed(&block, d));
        }
        // the header and the trailer's checksum, no sections: it opens, and holds nothing
        let empty = resealed(&block, [&sample[..start], &[0u8; 4][..]].concat());
        assert!(open("a file of no sections", &empty));
        assert!(defs.open(&empty, false).unwrap().set.sections.is_empty());
    }
}
