//! An edit of file A: what may be edited, the edit applied (with the copies the definition's mirrors keep in step),
//! and Undo and Redo.

use crate::*;

/// The record of setting `s` in set `section` of file `c` has the shape the setting was mapped in (a setting of
/// unknown size is taken as it is).
pub(crate) fn shape_ok_for(c: &CamSet, section: usize, s: &Setting) -> bool {
    s.size == 0 || c.sections.get(section).and_then(|sec| sec.get(s.id)).is_some_and(|r| r.elem_size == s.size && r.count == s.count)
}

/// Whether setting `s` lives in set `section` of a file: the live settings hold the global ones, a memory set the ones
/// the memories keep.
pub(crate) fn kept_in(s: &Setting, section: usize) -> bool {
    if section == 0 { s.area == "global" } else { s.in_sets }
}

/// A setting the camera keeps in other records too (`Setting::copies`), as `apply` keeps them in step: the setting (its
/// index among the definition's settings) and its place, the sets it lives in (global, kept in the memories) and its
/// record's shape, and each copy's.
struct CopyRule {
    setting: usize,
    main: CopyPlace,
    copies: Vec<CopyPlace>,
}

/// Where one setting of a `CopyRule` lives: its index among the definition's settings, its place, its sets, the
/// record shape it was mapped in (element size, element count; 0 = unknown), and for a copy the shooting modes whose
/// value it is (`Setting::copy_for`).
struct CopyPlace {
    setting: usize,
    slot: Slot,
    kept: (bool, bool),
    shape: (u16, u16),
    copy_for: Vec<String>,
}

impl CopyPlace {
    /// Whether this place is in set `section`.
    fn kept_in(&self, section: usize) -> bool {
        if section == 0 { self.kept.0 } else { self.kept.1 }
    }

    /// Its value in set `section` of file `c`, when the file holds its record in the shape it was mapped in.
    fn value(&self, c: &CamSet, section: usize) -> Option<i64> {
        let r = c.sections.get(section)?.get(self.slot.0)?;
        if self.shape.0 != 0 && (r.elem_size != self.shape.0 || r.count != self.shape.1) {
            return None;
        }
        r.get(self.slot.1)
    }

    /// What its place holds in set `section` of file `c`, whatever the record's shape: to tell a copy in step that the
    /// file holds in another shape, which is then left as it was, and said (`App::apply`).
    fn held(&self, c: &CamSet, section: usize) -> Option<i64> {
        c.sections.get(section)?.get(self.slot.0)?.get(self.slot.1)
    }
}

impl CopyRule {
    /// The one rule every file a camera writes keeps (docs/DATA_CONTRACTS.md, `copies`): whether file `c` holds the
    /// setting, in set `section`, at the value of at least one of its copies there. None when the set holds no copy of
    /// it, or not the setting, in the shape mapped: there is nothing to keep there.
    fn holds(&self, c: &CamSet, section: usize) -> Option<bool> {
        if !self.main.kept_in(section) {
            return None;
        }
        let v = self.main.value(c, section)?;
        let mut any = false;
        for cv in self.copies.iter().filter(|p| p.kept_in(section)).filter_map(|p| p.value(c, section)) {
            if cv == v {
                return Some(true);
            }
            any = true;
        }
        any.then_some(false)
    }

    /// The values the setting and its copies hold in set `section` of file `c`.
    fn values(&self, c: &CamSet, section: usize) -> Vec<Option<i64>> {
        std::iter::once(&self.main).chain(&self.copies).map(|p| p.value(c, section)).collect()
    }

    /// The copies in step with the setting in set `section` (`App::follows`): those that held its value in the file as
    /// first opened or read (`Doc::baseline`).
    fn in_step<'a>(&'a self, baseline: &'a CamSet, section: usize) -> impl Iterator<Item = &'a CopyPlace> + 'a {
        let then = self.main.value(baseline, section);
        self.copies.iter().filter(move |p| p.kept_in(section) && then.is_some() && p.held(baseline, section) == then)
    }

    /// The copy for the shooting mode set `section` is in (`mode`, `App::section_mode`), where that mode is known and a
    /// copy of this setting says it is that mode's (`copy_for`): every file a camera writes holds the setting at that
    /// copy's value there. It is checked (`keeps`), never used to decide what follows an edit: whether the camera moves
    /// the other modes' copies too is a setting of the camera's own that no proof has read yet, so what follows is the
    /// copies in step (`in_step`).
    fn for_mode(&self, mode: Option<&str>, section: usize) -> Option<&CopyPlace> {
        let m = mode?;
        self.copies.iter().find(|p| p.kept_in(section) && p.copy_for.iter().any(|x| x == m))
    }

    /// Whether file `c` keeps what the camera keeps in set `section`: where the set's mode is known (`for_mode`), the
    /// setting equals the copy for that mode; else it equals at least one of its copies (`holds`). None where there is
    /// nothing to keep there.
    fn keeps(&self, c: &CamSet, section: usize, mode: Option<&str>) -> Option<bool> {
        match self.for_mode(mode, section) {
            Some(p) => Some(self.main.value(c, section)? == p.value(c, section)?),
            None => self.holds(c, section),
        }
    }
}

/// A setting file A holds, in a set, other than the camera keeps it (`App::out_of_step`, `CopyRule::keeps`): the set,
/// the setting's index among the definition's settings, the copies it is judged against (the copy for the set's mode,
/// or every copy the set holds), whether it was so in the file as first opened or read, and the set's mode where that
/// decides it.
pub(crate) struct OutOfStep {
    pub(crate) section: usize,
    pub(crate) setting: usize,
    pub(crate) copies: Vec<usize>,
    pub(crate) as_opened: bool,
    pub(crate) mode: Option<String>,
}

/// What tells each set's shooting mode (`App::section_mode`), taken from the definition: the live record that says the
/// mode the file was saved in and the mode each of its values means (`camera.live_mode`), and each memory set's mode
/// (`camera.memory_sets.modes`).
struct Modes {
    live: Option<(Slot, std::collections::BTreeMap<String, String>)>,
    sets: std::collections::BTreeMap<usize, String>,
}

impl Modes {
    /// The mode set `section` of file `c` is in, where the definition says it.
    fn of(&self, c: &CamSet, section: usize) -> Option<String> {
        if section != 0 {
            return self.sets.get(&section).cloned();
        }
        let (slot, modes) = self.live.as_ref()?;
        let v = c.sections.first()?.get(slot.0)?.get(slot.1)?;
        modes.get(&v.to_string()).cloned()
    }
}

/// A change a view asks for on this frame: `apply` makes them all, as one undo step.
pub(crate) enum Action {
    Set(usize, Slot, i64),
    SetText(usize, u16, String),
    /// Revert a record (index None) or one element of an array record.
    Revert(usize, Slot),
    /// Open the record map on this record.
    ShowInMap(u16),
    /// Replace a whole record (undo history: put back the record as it was before one edit).
    SetRecord(usize, camset_editor::camset::Record),
}

impl App {
    pub(crate) fn undo(&mut self) {
        if let (Some(prev), Some(doc)) = (self.undo.pop(), self.doc.as_mut()) {
            self.redo.push(std::mem::replace(&mut doc.edited, prev));
            doc.rev = next_open();
            self.status = format!("Undo ({} left)", self.undo.len());
        }
    }

    pub(crate) fn redo(&mut self) {
        if let (Some(next), Some(doc)) = (self.redo.pop(), self.doc.as_mut()) {
            self.undo.push(std::mem::replace(&mut doc.edited, next));
            doc.rev = next_open();
            self.status = format!("Redo ({} left)", self.redo.len());
        }
    }

    /// Editing is allowed only for files whose record layout matches a firmware the
    /// mapping was verified on; any other layout could put values in the wrong place.
    /// A file whose checksums do not both hold under its definition's block is never edited (docs/decisions/0020).
    pub(crate) fn editable(&self) -> bool {
        self.doc.as_ref().is_some_and(|d| d.edited.checksums_ok() && (d.unchecked_ok || self.layout_checked(d)))
    }

    /// The open file's record layout is one the schema was checked on, and both its checksums held under the block.
    pub(crate) fn layout_checked(&self, d: &Doc) -> bool {
        d.edited.checksums_ok() && self.schema.camera.knows(&d.edited) && self.schema.layout(&d.signature).is_some()
    }

    /// "Edit anyway…" is offered for a file of the definition's model that is not checked, never for one whose
    /// checksums fail: the one way to edit unchecked does not override the container.
    pub(crate) fn offers_edit_anyway(&self, d: &Doc) -> bool {
        !d.unchecked_ok && !self.layout_checked(d) && d.edited.model() == self.schema.model && d.edited.checksums_ok()
    }

    /// Why setting `s` is view only in set `section` outside Expert mode: what the window and the page say beside it,
    /// in plain words (the cause, then what to do), and its hover. None when it may be changed there, and always in
    /// Expert mode. Outside it, a setting is changed only where a proof on the camera stands for it: a setting no proof
    /// reaches in that set (none at all, its `unproved_reason`, the memory sets of its `unproved_sets`, or proofs that
    /// disagree) holds only what the camera put in it, so a file with it changed is one the camera may refuse. A copy the
    /// camera keeps of another setting (`copy_of`) is changed as any setting is, taking that setting along where it is in
    /// step with it (`copy_note`, `apply`); only a copy of a setting the definition does not name is view only, as the
    /// editor cannot keep the two in step.
    pub(crate) fn locked_why(&self, s: &Setting, section: usize) -> Option<(String, String)> {
        if self.prefs.expert {
            return None;
        }
        // a copy whose setting the definition does not name says so in words, never by the key it names
        if s.copy_of.is_some() && self.main_of(s).is_none() {
            return Some(("View only: the camera keeps this as a copy of another setting, which this camera's definition does not name, so the editor cannot keep the two in step. Expert mode (⚙ Settings > Editing & Compare) can change it.".into(),
                "The camera keeps some values in more than one record; the setting this record copies is not in this camera's definition.".into()));
        }
        let unproved = s.unproved_in(section).map(|u| (u.kind.as_str(), u.why.as_str()))
            .or_else(|| s.unproved_reason.as_ref().map(|u| (u.kind.as_str(), u.why.as_str())));
        if s.proved.is_some() && !s.disputed && s.unproved_in(section).is_none() {
            return None;
        }
        let cause = match unproved.map(|(k, _)| k) {
            _ if s.disputed => "its proofs on the camera disagree, so none of them stands for it",
            Some("not_on_camera") => "this setting is not on this camera's menu, so no camera writes it",
            Some("state") => "this is a value the camera keeps for itself, not a menu setting",
            Some("camera_only") => "only the camera's own saves write this setting",
            Some("equipment") => "this setting needs equipment the camera was not proved with, so it has not been checked on the camera",
            Some("network") => "this setting is changed by hand on the camera only",
            Some("unknown") => "no menu choice tried on the camera changed this setting, so what writes it is not known",
            Some(_) | None => "this setting has not been checked on a camera yet",
        };
        let hover = unproved.map(|(_, w)| w.trim()).filter(|w| !w.is_empty()).unwrap_or("No proof on the camera chose its values yet.").to_string();
        Some((format!("View only: {cause}, and the camera may refuse a file where it was changed. Expert mode (⚙ Settings > Editing & Compare) can change it."), hover))
    }

    /// Whether `s` is view only in set `section` outside Expert mode (`locked_why`), without its words: for the lists
    /// that ask it of every row.
    pub(crate) fn locked(&self, s: &Setting, section: usize) -> bool {
        !self.prefs.expert && (s.proved.is_none() || s.disputed || s.unproved_in(section).is_some() || (s.copy_of.is_some() && self.main_of(s).is_none()))
    }

    /// The setting copy `s` copies (`copy_of`), when the definition names it.
    pub(crate) fn main_of(&self, s: &Setting) -> Option<&Setting> {
        self.index_of_key(s.copy_of.as_deref()?).map(|i| &self.schema.settings[i])
    }

    /// The index among the definition's settings of the one keyed `key`, from an index made once per definition (its
    /// generation, `schema_gen`), made again if the settings changed under it.
    pub(crate) fn index_of_key(&self, key: &str) -> Option<usize> {
        let found = |c: &Option<(u64, std::collections::HashMap<String, usize>)>| c.as_ref().filter(|(g, _)| *g == self.schema_gen)
            .map(|(_, m)| m.get(key).copied().filter(|&i| self.schema.settings.get(i).is_some_and(|s| s.key == key)));
        if let Some(Some(i)) = found(&self.key_index.borrow()) {
            return Some(i);
        }
        let index = self.schema.settings.iter().enumerate().map(|(i, s)| (s.key.clone(), i)).collect();
        *self.key_index.borrow_mut() = Some((self.schema_gen, index));
        found(&self.key_index.borrow()).flatten()
    }

    /// The shooting mode set `section` of file `c` is in: for the live settings the mode its `camera.live_mode` record
    /// says, for a memory set the mode `camera.memory_sets.modes` lists it under (`Camera::memory_mode`). None where the
    /// definition does not say, or the record holds a value it does not name.
    pub(crate) fn section_mode(&self, c: &CamSet, section: usize) -> Option<String> {
        self.modes().of(c, section)
    }

    /// `section_mode` for every set of file `c`.
    fn section_modes(&self, c: &CamSet) -> Vec<Option<String>> {
        let modes = self.modes();
        (0..c.sections.len()).map(|si| modes.of(c, si)).collect()
    }

    /// What tells each set's shooting mode (`Modes`), from the definition.
    fn modes(&self) -> Modes {
        let cam = &self.schema.camera;
        let live = cam.live_mode.as_ref().and_then(|lm| self.index_of_key(&lm.key).map(|i| (self.schema.settings[i].slot(), lm.modes.clone())));
        let sets = cam.memory_sets.as_ref().map(|m| m.modes.iter().flat_map(|(mode, sets)| sets.iter().map(move |&s| (s, mode.clone()))).collect()).unwrap_or_default();
        Modes { live, sets }
    }

    /// The rule setting `s` belongs to (`CopyRule`; for a copy, its setting's), when the definition names it.
    fn rule_of(&self, s: &Setting) -> Option<CopyRule> {
        let main = if s.copies.is_empty() { self.main_of(s)? } else { s };
        Some(self.copy_rule(self.index_of_key(&main.key)?))
    }

    /// Whether copy `c` is in step with `main` in set `section` (`CopyRule::in_step`): it held main's value in the file
    /// as first opened or read (`Doc::baseline`), decided once for the session, whatever values the two pass through
    /// meanwhile. A copy in step changes with its setting, and outside Expert mode takes it along when changed or
    /// reverted itself (`apply`); one apart changes alone.
    pub(crate) fn follows(&self, c: &Setting, main: &Setting, section: usize) -> bool {
        self.doc.as_ref().is_some_and(|d| {
            let held = d.baseline_value(section, c.slot());
            held.is_some() && held == d.baseline_value(section, main.slot())
        })
    }

    /// Where set `section`'s shooting mode comes from, for the notes: "this file was saved in Stills mode", "Memory 1
    /// is a Stills memory set", the mode named as the definition names it.
    fn mode_where(&self, section: usize, mode: &str) -> String {
        if section == 0 {
            format!("this file was saved in {mode} mode")
        } else {
            format!("{} is a {mode} memory set", self.schema.camera.target_name(section))
        }
    }

    /// What a row or tile says beside a setting the camera keeps in more than one record (`copies`, `copy_of`) in set
    /// `section`, and its hover. Where file A does not keep what the camera keeps there (`CopyRule::keeps`: the setting
    /// apart from the copy for the set's shooting mode, or where that is not known held by none of its copies): that it
    /// is out of step, and what to do. Else, beside a copy, what changing it changes (`apply`): one in step with its
    /// setting (`follows`) takes the setting and the copies in step with it along, and its Revert is theirs; one apart
    /// changes alone; in Expert mode a copy changes alone. The words hold whatever the camera does with the other modes'
    /// copies, which no proof has read. None for any other setting.
    pub(crate) fn copy_note(&self, s: &Setting, section: usize) -> Option<(String, String)> {
        let d = self.doc.as_ref()?;
        let rule = self.rule_of(s)?;
        if !rule.main.kept_in(section) {
            return None;
        }
        let main = &self.schema.settings[rule.setting];
        let mode = self.section_mode(&d.edited, section);
        let own = rule.for_mode(mode.as_deref(), section);
        let name = |o: &Setting| if o.name == s.name && o.key != s.key { format!("the other {} row", o.name) } else { o.name.clone() };
        // the hover names the records from the definition's own settings, never a camera's
        let copies: Vec<String> = rule.copies.iter().filter(|p| p.kept_in(section)).map(|p| self.schema.settings[p.setting].name.clone()).collect();
        let mut hover = format!("The camera keeps the value of {} in {} too, and every file it writes holds it in at least one of them. The ones that held its value when this file was opened or read change with it here; the others change alone.", main.name, and_list(&copies));
        if let (Some(p), Some(m)) = (own, &mode) {
            hover.push_str(&format!(" In {m} mode the camera always holds {} at the value of {}.", main.name, self.schema.settings[p.setting].name));
        }
        if rule.keeps(&d.edited, section, mode.as_deref()) == Some(false) {
            let as_opened = rule.keeps(&d.baseline, section, self.section_mode(&d.baseline, section).as_deref()) == Some(false);
            let words = match (own, &mode) {
                (Some(p), Some(m)) => {
                    let copy = &self.schema.settings[p.setting].name;
                    let todo = if as_opened {
                        format!("It was so when this file was opened or read: set {copy} to the value of {}, or read the camera again.", main.name)
                    } else {
                        "Revert what was changed here.".to_string()
                    };
                    format!("Out of step: {}, and in {m} mode the camera always holds {} at the value of {copy}, but here the two differ, so the camera may refuse this file. {todo}", self.mode_where(section, m), main.name)
                }
                _ => {
                    let held: Vec<String> = rule.copies.iter().filter(|p| p.kept_in(section) && p.value(&d.edited, section).is_some()).map(|p| self.schema.settings[p.setting].name.clone()).collect();
                    let todo = if as_opened {
                        format!("It was so when this file was opened or read: set {} to a value one of them holds, or read the camera again.", main.name)
                    } else {
                        format!("Revert what was changed here, or set {} again, which takes the copies in step with it along.", main.name)
                    };
                    format!("Out of step: the camera keeps the value of {} in {} too, and none of them holds it here, so the camera may refuse this file. {todo}", main.name, and_list(&held))
                }
            };
            return Some((words, hover));
        }
        s.copy_of.as_ref()?;
        let m = name(main);
        if !self.follows(s, main, section) {
            return Some((format!("A copy the camera keeps of {m}, which held another value than {m} when this file was opened or read: it changes alone, and stays as it is when {m} changes."), hover));
        }
        if self.prefs.expert {
            return Some((format!("A copy the camera keeps of {m}, in step with it when this file was opened or read: in Expert mode changing it changes it alone, and it still changes when {m} does."), hover));
        }
        let along: Vec<String> = std::iter::once(m).chain(rule.in_step(&d.baseline, section)
            .filter(|p| self.schema.settings[p.setting].key != s.key && p.value(&d.edited, section).is_some())
            .map(|p| name(&self.schema.settings[p.setting]))).collect();
        Some((format!("Changing this changes {} too, and reverting it reverts them: they held the same value when this file was opened or read, so the editor keeps them together. Expert mode (⚙ Settings > Editing & Compare) changes this one alone.", and_list(&along)), hover))
    }

    /// Every setting the camera keeps in other records too (`copies`) that file A holds, in a set, other than the camera
    /// keeps it (`CopyRule::keeps`), which no camera writes: what the save and write windows list (`judge`), edited or
    /// not.
    pub(crate) fn out_of_step(&self) -> Vec<OutOfStep> {
        let Some(d) = &self.doc else { return Vec::new() };
        let (now, then) = (self.section_modes(&d.edited), self.section_modes(&d.baseline));
        let mut out = Vec::new();
        for r in self.copy_rules() {
            for (si, mode) in now.iter().enumerate() {
                let mode = mode.as_deref();
                if r.keeps(&d.edited, si, mode) != Some(false) {
                    continue;
                }
                let copies = match r.for_mode(mode, si) {
                    Some(p) => vec![p.setting],
                    None => r.copies.iter().filter(|p| p.kept_in(si) && p.value(&d.edited, si).is_some()).map(|p| p.setting).collect(),
                };
                let as_opened = r.keeps(&d.baseline, si, then.get(si).cloned().flatten().as_deref()) == Some(false);
                out.push(OutOfStep { section: si, setting: r.setting, copies, as_opened, mode: r.for_mode(mode, si).and(mode.map(str::to_string)) });
            }
        }
        out
    }

    /// The actions that put setting `main`'s copies back at its value in set `section`, where they hold another and
    /// their records have the shape mapped: the copy for the set's shooting mode where that is known (`CopyRule::keeps`),
    /// else the copies in step with it (`follows`). The Write window's fix for a setting out of step with its copies
    /// (`issue_fix`); empty when none is to be put back.
    pub(crate) fn back_in_step(&self, main: &Setting, section: usize) -> Vec<Action> {
        let (Some(d), Some(rule)) = (self.doc.as_ref(), self.rule_of(main)) else { return Vec::new() };
        let Some(v) = rule.main.value(&d.edited, section) else { return Vec::new() };
        let mode = self.section_mode(&d.edited, section);
        match rule.for_mode(mode.as_deref(), section) {
            // the copy for the set's shooting mode, which the file must hold at the setting's value
            Some(p) => p.value(&d.edited, section).filter(|cv| *cv != v).map(|_| Action::Set(section, p.slot, v)).into_iter().collect(),
            None => rule.in_step(&d.baseline, section).filter(|p| p.value(&d.edited, section).is_some_and(|cv| cv != v)).map(|p| Action::Set(section, p.slot, v)).collect(),
        }
    }

    /// After a copy of several rows at once into set `to` (`copy_row` for each, `actions` what they asked), from set
    /// `from` of file A (a memory recalled into the live settings, the live settings registered into one) or from another
    /// file (None): every
    /// place of a setting the camera keeps in more than one record (the setting and each of its copies, `copies`) that
    /// this copy leaves as it is while another place of that setting takes a value, set to the value it holds. Each place
    /// then keeps exactly what it held, the rows copied take the other file's values (`apply` changes a place this step
    /// sets by itself, never by its setting), and file A holds what the other column holds, row by row; the check after
    /// the step refuses a copy that would leave a setting other than the camera keeps it, and says what to do. A copy of
    /// one row is an edit of it, and takes its setting along where it is in step (`copy_note`).
    pub(crate) fn pin_families(&self, from: Option<usize>, to: usize, actions: &mut Vec<Action>) {
        self.rows_copied.set(Some(from));
        let Some(d) = &self.doc else { return };
        let set: std::collections::HashSet<Slot> = actions.iter().filter_map(|a| match a {
            Action::Set(si, slot, _) if *si == to => Some(*slot),
            _ => None,
        }).collect();
        let mut pins = Vec::new();
        for r in self.copy_rules().iter().filter(|r| r.main.kept_in(to)) {
            let places: Vec<&CopyPlace> = std::iter::once(&r.main).chain(&r.copies).filter(|p| p.kept_in(to)).collect();
            if !places.iter().any(|p| set.contains(&p.slot)) {
                continue;
            }
            for p in places.into_iter().filter(|p| !set.contains(&p.slot)) {
                if let Some(v) = p.value(&d.edited, to) {
                    pins.push(Action::Set(to, p.slot, v));
                }
            }
        }
        actions.extend(pins);
    }

    /// The value that puts `s` back where the camera keeps it in set `section`, when it is not there now: a copy that
    /// goes with its setting (`follows`) takes that setting's value as it is now, so it is in step with it again;
    /// anything else what the file held when first opened or read (`Doc::baseline`), which is what the camera wrote.
    /// None when it holds that already. Outside Expert mode this is the one change a view-only setting takes (`apply`),
    /// as it only ever restores what the camera keeps, and a copy so put back changes alone.
    pub(crate) fn put_back_value(&self, s: &Setting, section: usize) -> Option<i64> {
        let d = self.doc.as_ref()?;
        let target = match self.main_of(s) {
            Some(m) if self.follows(s, m, section) => d.value(section, m.slot())?,
            _ => d.baseline_value(section, s.slot())?,
        };
        (d.value(section, s.slot()) != Some(target)).then_some(target)
    }

    /// What puts a row of linked records (`linked`) back where the camera keeps them in set `section`, where the plain
    /// Revert (back to the file as last opened or saved) changes nothing, and its words: what the camera wrote, when a
    /// Save As kept another value (`REVERT_TO_CAMERA`); a copy in step with its setting, back at that setting's value
    /// ("Back in step with …"). A record the file holds in another shape than mapped is left out, and `apply` says so;
    /// None when the plain Revert serves or nothing is to be put back. The detail panel, Compare's menu and the page
    /// offer it, with `put_back_hover` saying what it does.
    pub(crate) fn put_back_choice(&self, linked: &[Setting], section: usize) -> Option<(String, Vec<Action>)> {
        let d = self.doc.as_ref()?;
        if linked.iter().any(|l| d.value(section, l.slot()) != d.original_value(section, l.slot())) {
            return None;
        }
        let acts: Vec<(Slot, i64, bool)> = linked.iter().filter_map(|l| self.put_back_value(l, section).map(|v| (l.slot(), v, self.shape_ok_in(l, section)))).collect();
        let &(slot, v, _) = acts.iter().find(|a| a.2)?;
        let words = if Some(v) == d.baseline_value(section, slot) {
            REVERT_TO_CAMERA.to_string()
        } else {
            let main = linked.iter().find_map(|l| self.main_of(l));
            format!("Back in step with {}", main.map_or("its setting", |m| m.name.as_str()))
        };
        Some((words, acts.into_iter().map(|(slot, v, _)| Action::Set(section, slot, v)).collect()))
    }

    /// What a put-back (`put_back_choice`, `issue_fix`) does, by its words: the hover the detail panel and the page give
    /// its button.
    pub(crate) fn put_back_hover(words: &str) -> String {
        match words.strip_prefix("Back in step with ") {
            Some(main) => format!("Sets this copy to the value {main} holds now: the camera keeps the two as one value, and they held the same value when the file was opened or read."),
            None if words == "Revert" => "Puts back what the file held when it was last opened or saved.".into(),
            None => "Puts back what the camera wrote here, as the file was first opened or read.".into(),
        }
    }

    /// The first lock (`locked_why`) of a setting living in `slot` of set `section`, `at` holding each slot's settings.
    fn lock_at(&self, section: usize, slot: Slot, at: &std::collections::HashMap<Slot, Vec<usize>>) -> Option<String> {
        let s = at.get(&slot)?.iter().map(|&i| &self.schema.settings[i]).find(|s| kept_in(s, section) && self.locked(s, section))?;
        self.locked_why(s, section).map(|(w, _)| w)
    }

    /// Whether setting `v` in `slot` of set `section` only puts a setting living there back where the camera keeps it
    /// (`put_back_value`).
    fn puts_back(&self, section: usize, slot: Slot, v: i64, at: &std::collections::HashMap<Slot, Vec<usize>>) -> bool {
        at.get(&slot).into_iter().flatten().map(|&i| &self.schema.settings[i]).any(|s| kept_in(s, section) && self.put_back_value(s, section) == Some(v))
    }

    /// The rule of the setting at index `i` among the definition's settings (`CopyRule`), with the places of the copies
    /// it names.
    fn copy_rule(&self, i: usize) -> CopyRule {
        let place = |i: usize| {
            let s = &self.schema.settings[i];
            CopyPlace { setting: i, slot: s.slot(), kept: (s.area == "global", s.in_sets), shape: (s.size, s.count), copy_for: s.copy_for.clone() }
        };
        let copies = self.schema.settings[i].copies.iter().filter_map(|k| self.index_of_key(k)).map(place).collect();
        CopyRule { setting: i, main: place(i), copies }
    }

    /// The definition's copies (`Setting::copies`): each setting that has some, with the places of those it names.
    fn copy_rules(&self) -> Vec<CopyRule> {
        (0..self.schema.settings.len()).filter(|&i| !self.schema.settings[i].copies.is_empty()).map(|i| self.copy_rule(i)).collect()
    }

    /// The record still has the shape it had when the setting was mapped.
    pub(crate) fn shape_ok(&self, s: &Setting) -> bool {
        self.shape_ok_in(s, self.target)
    }

    pub(crate) fn shape_ok_in(&self, s: &Setting, target: usize) -> bool {
        if s.size == 0 {
            return true;
        }
        let Some(doc) = &self.doc else { return false };
        shape_ok_for(&doc.edited, target, s)
    }

    /// After a write to record `id` of section `sec` (a 16-bit field at a byte offset, or the whole record with
    /// `index` None): the same in the copies the definition's mirrors name (`camera.mirrors`), those this file holds
    /// in the shape they need (`Mirror::stride_in`).
    fn sync_mirror(mirrors: &[(camset_editor::schema::Mirror, usize)], edited: &mut CamSet, sec: usize, id: u16, index: Option<u16>) {
        for (m, stride) in mirrors {
            match index {
                Some(i) if i & camset::FIELD != 0 => m.sync_bytes(edited, sec, id, (i & !camset::FIELD) as usize, 2, *stride),
                Some(_) => {}
                None => m.sync_record(edited, sec, id, *stride),
            }
        }
    }

    /// The definition's mirrors that `c` holds in the shape they need, with their element size.
    fn mirrors_for(&self, c: &CamSet) -> Vec<(camset_editor::schema::Mirror, usize)> {
        self.schema.camera.mirrors.iter().filter_map(|m| m.stride_in(c).map(|s| (m.clone(), s))).collect()
    }

    /// What the status line adds when a file does not hold a mirror's records as the definition says: those copies
    /// are not kept in step for it.
    pub(crate) fn mirror_note(&self, c: &CamSet) -> String {
        self.schema.camera.mirrors.iter().filter(|m| m.stride_in(c).is_none())
            .map(|m| format!(" {} is not kept in step with its copy for this file: its records are not shaped as the definition says.",
                if m.what.is_empty() { format!("Record 0x{:04x}", m.live_record) } else { m.what.clone() }))
            .collect()
    }

    /// Make the changes the views asked for on this frame, as one undo step, keeping the copies the camera keeps of a
    /// value (`Setting::copies`) and the definition's mirrors as the camera keeps them. Returns why nothing was changed,
    /// when the changes were refused (the status line says it too): outside Expert mode, a value for a view-only setting
    /// (`locked_why`), or a step that would leave a setting at a value none of its copies holds (`CopyRule::holds`).
    pub(crate) fn apply(&mut self, mut actions: Vec<Action>) -> Option<String> {
        // rows a copy left alone (`copy_row`): said once, after what the copy itself said
        let skipped = self.copy_skipped.replace(Left::default());
        // a copy of several rows at once (`pin_families`): a refusal says what to do about the copy
        let copied = self.rows_copied.replace(None);
        if skipped.total() > 0 {
            self.status = with_left(&self.status, skipped);
        }
        if actions.is_empty() {
            return None;
        }
        if let Some(pos) = actions.iter().position(|a| matches!(a, Action::ShowInMap(_))) {
            if let Action::ShowInMap(id) = actions.remove(pos) {
                self.view = View::Records;
                self.search = format!("0x{id:04x}");
                self.mode = Mode::Edit;
            }
        }
        let expert = self.prefs.expert;
        let rules = self.copy_rules();
        let mut at: std::collections::HashMap<Slot, Vec<usize>> = Default::default();
        for (i, s) in self.schema.settings.iter().enumerate() {
            at.entry(s.slot()).or_default().push(i);
        }
        // a copy whose record the file holds in another shape than mapped takes no value, whichever view asked (a
        // put-back, a copy taken along): it is left as it was, and said
        let mut odd_copies: std::collections::HashSet<(usize, Slot)> = Default::default();
        if let Some(d) = &self.doc {
            actions.retain(|a| {
                let Action::Set(si, slot, _) = a else { return true };
                let odd = at.get(slot).into_iter().flatten().map(|&i| &self.schema.settings[i]).any(|s| s.copy_of.is_some() && kept_in(s, *si) && !shape_ok_for(&d.edited, *si, s));
                if odd {
                    odd_copies.insert((*si, *slot));
                }
                !odd
            });
        }
        if !expert {
            // outside Expert mode a setting that is view only (one no proof stands for: `locked_why`) takes no value but
            // to be put back where the camera keeps it (or, in a copy of several rows, the value it holds, which changes
            // nothing: the copy pins it so, `pin_families`), whichever view asked: the last guard behind the views' own. Said
            // when nothing else is left to do (a row of linked records some of which are view only changes the others,
            // as the views show)
            let mut why: Option<String> = None;
            actions.retain(|a| {
                let refused = match a {
                    Action::Set(si, slot, v) => self.lock_at(*si, *slot, &at)
                        .filter(|_| !self.puts_back(*si, *slot, *v, &at) && !(copied.is_some() && self.doc.as_ref().and_then(|d| d.value(*si, *slot)) == Some(*v))),
                    Action::SetText(si, id, _) => self.lock_at(*si, (*id, None), &at),
                    _ => None,
                };
                match refused {
                    Some(w) => {
                        why.get_or_insert(w);
                        false
                    }
                    None => true,
                }
            });
            if actions.is_empty() {
                if !odd_copies.is_empty() {
                    self.status = with_left("", Left { copies_shape: odd_copies.len(), ..Default::default() });
                }
                if let Some(w) = &why {
                    self.status = w.clone();
                }
                return why;
            }
            // a copy in step with its setting (`follows`), changed or reverted by itself, takes the setting and the
            // copies in step with it along (a copy in step is never reverted alone: its Revert is its setting's), and
            // the setting's Revert reverts those copies too: the same change made to each, in this step, as the row says
            // beforehand (`copy_note`). Not where this step changes the setting itself (Compare's copy of a whole row
            // set: each takes its own value), nor for a put-back (`put_back_value`), which changes the copy
            // alone, nor for a Set that leaves the copy's own record as it is, which changes nothing anywhere
            if let Some(d) = &self.doc {
                let direct: std::collections::HashSet<(usize, Slot)> = actions.iter().filter_map(|a| match a {
                    Action::Set(si, slot, _) | Action::Revert(si, slot) => Some((*si, *slot)),
                    _ => None,
                }).collect();
                let mut grown = Vec::with_capacity(actions.len());
                for a in actions {
                    let (si, slot) = match &a {
                        Action::Set(si, slot, _) | Action::Revert(si, slot) => (*si, *slot),
                        _ => {
                            grown.push(a);
                            continue;
                        }
                    };
                    let put_back = matches!(a, Action::Set(_, _, v) if self.puts_back(si, slot, v, &at) || d.value(si, slot) == Some(v));
                    let hit = rules.iter().filter(|r| r.main.kept_in(si)).find_map(|r| {
                        let tied: Vec<&CopyPlace> = r.in_step(&d.baseline, si).collect();
                        let on_main = r.main.slot == slot && matches!(a, Action::Revert(..));
                        let on_copy = !direct.contains(&(si, r.main.slot)) && tied.iter().any(|p| p.slot == slot);
                        (on_main || on_copy).then_some((r, tied))
                    });
                    let Some((r, tied)) = hit.filter(|_| !put_back) else {
                        grown.push(a);
                        continue;
                    };
                    // a setting that is view only takes no value through its copy either
                    let main = &self.schema.settings[r.setting];
                    if matches!(a, Action::Set(..)) && self.locked(main, si) {
                        why = why.or_else(|| self.locked_why(main, si).map(|(w, _)| w));
                        continue;
                    }
                    for p in std::iter::once(&r.main).chain(tied) {
                        // a place this step changes by its own action keeps it
                        if p.slot != slot && direct.contains(&(si, p.slot)) {
                            continue;
                        }
                        if p.value(&d.edited, si).is_none() {
                            if p.slot != r.main.slot {
                                odd_copies.insert((si, p.slot));
                            }
                            continue;
                        }
                        grown.push(match &a {
                            Action::Set(_, _, v) => Action::Set(si, p.slot, *v),
                            _ => Action::Revert(si, p.slot),
                        });
                    }
                }
                actions = grown;
            }
            if actions.is_empty() {
                if let Some(w) = &why {
                    self.status = w.clone();
                }
                return why;
            }
        }
        let mirrors = self.doc.as_ref().map(|d| self.mirrors_for(&d.edited)).unwrap_or_default();
        let modes = self.modes();
        let Some(doc) = &mut self.doc else { return None };
        // a value being dragged sends a Set every frame: while the same slots change again soon after, those Sets
        // join the undo step the drag began with (no new snapshot, no copy of the file per frame)
        let slots: Option<Vec<(usize, Slot)>> = actions.iter().map(|a| if let Action::Set(si, slot, _) = a { Some((*si, *slot)) } else { None }).collect();
        let joins = match (&slots, &self.last_edit) {
            (Some(s), Some((last, at))) => s == last && at.elapsed() < std::time::Duration::from_millis(800) && !self.undo.is_empty() && self.redo.is_empty(),
            _ => false,
        };
        // the places this step changes directly: a copy among them takes its own value, never its setting's (below)
        let direct: std::collections::HashSet<(usize, Slot)> = actions.iter().filter_map(|a| match a {
            Action::Set(si, slot, _) | Action::Revert(si, slot) => Some((*si, *slot)),
            _ => None,
        }).collect();
        // outside Expert mode, the settings with copies whose places this step touches, set by set, and whether the file
        // kept what the camera keeps there before it (`CopyRule::keeps`): a step that takes that away is refused (below)
        let mut watched: Vec<(usize, usize, Option<bool>)> = Vec::new();
        if !expert {
            for a in &actions {
                let (si, id) = match a {
                    Action::Set(si, (id, _), _) | Action::Revert(si, (id, _)) | Action::SetText(si, id, _) => (*si, *id),
                    Action::SetRecord(si, rec) => (*si, rec.id),
                    Action::ShowInMap(_) => continue,
                };
                // the record that says the live settings' shooting mode changes which copy every setting there is checked
                // against (`camera.live_mode`)
                let mode_record = si == 0 && modes.live.as_ref().is_some_and(|(slot, _)| slot.0 == id);
                for (k, r) in rules.iter().enumerate() {
                    let touches = (mode_record && r.main.kept_in(0)) || std::iter::once(&r.main).chain(&r.copies).any(|p| p.slot.0 == id && p.kept_in(si));
                    if touches && !watched.iter().any(|w| w.0 == k && w.1 == si) {
                        watched.push((k, si, r.keeps(&doc.edited, si, modes.of(&doc.edited, si).as_deref())));
                    }
                }
            }
        }
        let start = (!joins || !watched.is_empty()).then(|| doc.edited.clone());
        for a in actions {
            // the settings with copies in the record this action changes, and their values before it (`Setting::copies`)
            let touched = match &a {
                Action::Set(si, (id, _), _) | Action::Revert(si, (id, _)) | Action::SetText(si, id, _) => Some((*si, *id)),
                Action::SetRecord(si, rec) => Some((*si, rec.id)),
                Action::ShowInMap(_) => None,
            };
            let mains: Vec<(usize, usize, Option<i64>)> = touched.map(|(si, id)| {
                rules.iter().enumerate().filter(|(_, r)| r.main.slot.0 == id && r.main.kept_in(si))
                    .map(|(k, r)| (si, k, doc.value(si, r.main.slot))).collect()
            }).unwrap_or_default();
            match a {
                Action::Set(si, (id, index), v) => {
                    if let Some(r) = doc.edited.sections.get_mut(si).and_then(|s| s.get_mut(id)) {
                        if let Err(e) = r.put(index, v) {
                            let details = details(expert, &e);
                            self.status = format!("That value does not fit this setting. Pick one of the offered values instead.{details}");
                        } else {
                            Self::sync_mirror(&mirrors, &mut doc.edited, si, id, index);
                        }
                    }
                }
                Action::SetText(si, id, t) => {
                    if let Some(r) = doc.edited.sections.get_mut(si).and_then(|s| s.get_mut(id)) {
                        if let Err(e) = r.set_text(&t) {
                            let details = details(expert, &e);
                            self.status = format!("That text does not fit. Use only the characters and length the camera allows for this text.{details}");
                        }
                    }
                }
                Action::Revert(si, (id, index)) => {
                    let original = doc.original.sections.get(si).and_then(|s| s.get(id)).cloned();
                    if let (Some(o), Some(r)) = (original, doc.edited.sections.get_mut(si).and_then(|s| s.get_mut(id))) {
                        match index.and_then(|i| o.get(Some(i)).map(|v| (i, v))) {
                            Some((i, v)) => {
                                let _ = r.put(Some(i), v);
                                Self::sync_mirror(&mirrors, &mut doc.edited, si, id, Some(i));
                            }
                            None => {
                                *r = o;
                                Self::sync_mirror(&mirrors, &mut doc.edited, si, id, None);
                            }
                        }
                    }
                }
                Action::ShowInMap(_) => {}
                Action::SetRecord(si, rec) => {
                    let id = rec.id;
                    if let Some(r) = doc.edited.sections.get_mut(si).and_then(|s| s.get_mut(id)) {
                        *r = rec;
                        Self::sync_mirror(&mirrors, &mut doc.edited, si, id, None);
                    }
                }
            }
            // a setting the camera keeps in other records too: the copies in step with it take its new value, in this
            // same step. Which are in step is decided once, from the file as opened or read (`baseline`), set by set: a
            // copy that held the setting's value there follows it for the whole session, one that held another never
            // does, whatever values the two pass through meanwhile (a drag, steps of + and −). The set's shooting mode
            // (`copy_for`) does not decide it: whether the camera moves the other modes' copies too is a setting of its
            // own no proof has read. A copy this step changes itself keeps the value it was given. A copy whose record
            // has another shape than mapped is left as it was, and said
            for (si, k, old) in mains {
                let r = &rules[k];
                let (Some(old), Some(new)) = (old, doc.value(si, r.main.slot)) else { continue };
                if old == new {
                    continue;
                }
                let follow: Vec<(Slot, (u16, u16))> = r.in_step(&doc.baseline, si).filter(|p| !direct.contains(&(si, p.slot))).map(|p| (p.slot, p.shape)).collect();
                for (slot, (size, count)) in follow {
                    let Some(rec) = doc.edited.sections.get_mut(si).and_then(|s| s.get_mut(slot.0)) else { continue };
                    if size != 0 && (rec.elem_size != size || rec.count != count) {
                        odd_copies.insert((si, slot));
                        continue;
                    }
                    if rec.get(slot.1) != Some(new) && rec.put(slot.1, new).is_ok() {
                        Self::sync_mirror(&mirrors, &mut doc.edited, si, slot.0, slot.1);
                    }
                }
            }
        }
        // outside Expert mode, a step that leaves the file other than the camera keeps it (`CopyRule::keeps`: a setting
        // apart from the copy for its set's shooting mode, or where the mode is not known held by none of its copies),
        // where it kept it before, is a file no camera writes: it is undone and refused, with what to do, unless it puts
        // the setting and its copies back as the file was first opened or read. A file already so may be edited
        // further, or mended
        let broken = watched.iter().find(|&&(k, si, before)| {
            let r = &rules[k];
            before == Some(true) && r.keeps(&doc.edited, si, modes.of(&doc.edited, si).as_deref()) == Some(false) && (r.values(&doc.edited, si), modes.of(&doc.edited, si)) != (r.values(&doc.baseline, si), modes.of(&doc.baseline, si))
        }).map(|&(k, si, _)| (k, si));
        if let (Some((k, si)), Some(start)) = (broken, &start) {
            // the mode the step would have left the set in, which the words name
            let mode = modes.of(&doc.edited, si);
            doc.edited = start.clone();
            let r = &rules[k];
            let own = r.for_mode(mode.as_deref(), si).map(|p| p.setting);
            let held: Vec<String> = r.copies.iter().filter(|p| p.kept_in(si) && p.value(&doc.edited, si).is_some()).map(|p| self.schema.settings[p.setting].name.clone()).collect();
            let in_step = r.in_step(&doc.baseline, si).any(|p| p.value(&doc.edited, si).is_some());
            let own_in_step = own.is_some_and(|c| r.in_step(&doc.baseline, si).any(|p| p.setting == c));
            let live = modes.of(&doc.edited, 0);
            let main = &self.schema.settings[r.setting].name;
            // the row that says the live settings' shooting mode, by its own name, for a copy into them
            let mode_row = self.schema.camera.live_mode.as_ref().filter(|_| si == 0).and_then(|lm| self.index_of_key(&lm.key)).map(|i| self.schema.settings[i].name.clone());
            // a memory recalled into the live settings, or the live settings registered into one: the memory's mode and
            // the file's, by the definition's names
            let memory = match copied.flatten() {
                Some(m) if m != 0 && si == 0 => Some((m, "Not recalled", "recalls")),
                Some(0) if si != 0 => Some((si, "Not registered", "registers")),
                _ => None,
            };
            let words = match (own, &mode) {
                (Some(_), Some(_)) if memory.is_some_and(|(m, _, _)| modes.sets.contains_key(&m)) => {
                    let (m, not, does) = memory.unwrap_or((si, "Not copied", "copies"));
                    let its = modes.sets.get(&m).cloned().unwrap_or_default();
                    let saved = live.as_ref().map_or("this file does not say which mode it was saved in".to_string(), |l| format!("this file was saved in {l} mode"));
                    format!("{not}: {} is a {its} memory and {saved}; the camera {does} a mode's memories only in that mode, so these values would leave a file no camera writes. Expert mode (⚙ Settings > Editing & Compare) copies it all the same.", self.schema.camera.target_name(m))
                }
                (Some(c), Some(m)) if copied.is_some() => {
                    let copy = &self.schema.settings[c].name;
                    let todo = match &mode_row {
                        Some(row) => format!("Copy the {row} row too, so this file is in the same mode as the one copied from, or copy in Expert mode (⚙ Settings > Editing & Compare), which takes the rows as they are."),
                        None => "Copy in Expert mode (⚙ Settings > Editing & Compare), which takes the rows as they are.".to_string(),
                    };
                    format!("Not copied: {}, and in {m} mode the camera always holds {main} at the value of {copy}, so these rows would leave a file no camera writes. {todo}", self.mode_where(si, m))
                }
                (_, _) if copied.is_some() => {
                    format!("Not copied: {main} would then hold a value none of its copies here holds ({}), and no camera writes a file like that. Copy the rows of {main} and its copies together, or copy in Expert mode (⚙ Settings > Editing & Compare).", and_list(&held))
                }
                (Some(c), Some(m)) => {
                    let copy = &self.schema.settings[c].name;
                    let todo = if own_in_step {
                        format!("Change or revert {main} or {copy} instead: the two change together.")
                    } else {
                        format!("Expert mode (⚙ Settings > Editing & Compare) changes {main} and {copy} one at a time: give both the same value there.")
                    };
                    format!("Not changed: {}, and in {m} mode the camera always holds {main} at the value of {copy}, so a file where they differ is one no camera writes. {todo}", self.mode_where(si, m))
                }
                _ => {
                    let todo = if in_step { format!("Change {main} instead: the copies in step with it change with it.") } else { format!("Set {main} to a value one of them holds.") };
                    format!("Not changed: {main} would then hold a value none of its copies here holds ({}), and no camera writes a file like that. {todo} Expert mode (⚙ Settings > Editing & Compare) changes them apart.", and_list(&held))
                }
            };
            self.status = words.clone();
            return Some(words);
        }
        if !odd_copies.is_empty() {
            self.status = with_left(&self.status, Left { copies_shape: odd_copies.len(), ..Default::default() });
        }
        doc.rev = next_open();
        match start.filter(|_| !joins) {
            // a new step, when the file changed (records compared directly: no copy of the whole file as bytes)
            Some(before) => {
                let changed = before.sections.iter().zip(&doc.edited.sections).any(|(a, b)| a.records != b.records);
                if changed {
                    if self.undo.len() >= 300 {
                        self.undo.remove(0);
                    }
                    self.undo.push(before);
                    self.redo.clear();
                }
                self.last_edit = slots.filter(|_| changed).map(|s| (s, std::time::Instant::now()));
            }
            // joined to the step the drag began with, which holds the file as it was before it
            None => self.last_edit = slots.map(|s| (s, std::time::Instant::now())),
        }
        None
    }
}

/// Names in a sentence: "A", "A and B", "A, B and C".
pub(crate) fn and_list(names: &[String]) -> String {
    match names {
        [] => String::new(),
        [one] => one.clone(),
        [rest @ .., last] => format!("{} and {last}", rest.join(", ")),
    }
}

/// A value the camera keeps in several records (`copies`, `copy_of`), and the settings that are view only outside Expert
/// mode (`locked_why`), whichever view edits or reverts them: the detail panel, the page, Compare's copy, the Memories
/// page, the Main tiles, My Menu, Undo, Revert, the history.
#[cfg(test)]
mod copies_tests {
    use super::*;
    use crate::web::tests::answer;
    use egui::accesskit::Role;
    use serde_json::json;

    /// What the window and the page say beside a setting no menu of the camera writes (`App::locked_why`), outside
    /// Expert mode, word for word: the definition's own reason is its hover.
    const NOT_ON_CAMERA_LOCK: &str = "View only: this setting is not on this camera's menu, so no camera writes it, and the camera may refuse a file where it was changed. Expert mode (⚙ Settings > Editing & Compare) can change it.";

    /// A Picture Profile parameter in use (PP1's Black Level) and its stills and movie copies, the records the
    /// definition's copies are made of here (`copies`, `copy_of`), as the kit writes them.
    const MAIN: &str = "global:0x04e9[0]";
    const STILLS: &str = "global:0x04ff[0]";
    const MOVIE: &str = "global:0x0515[0]";

    fn setting(app: &App, key: &str) -> Setting {
        app.schema.settings.iter().find(|s| s.key == key).cloned().unwrap_or_else(|| panic!("{key}"))
    }

    /// What the editor answered the page, as JSON.
    macro_rules! body {
        ($r:expr) => {
            serde_json::from_slice::<serde_json::Value>(&$r.body).unwrap()
        };
    }

    /// The file as opened changed by `f`: what it held when opened (`original`), as edited and as the baseline the
    /// edits are judged against and copies follow from (`baseline`), as though the camera had written it so.
    fn as_opened(app: &mut App, f: impl Fn(&mut CamSet)) {
        let d = app.doc.as_mut().unwrap();
        f(&mut d.original);
        d.edited = d.original.clone();
        d.baseline = d.original.clone();
    }

    /// The sample open with the copies made here, the three records holding `v`, `stills` and `movie` in every set as
    /// the file was opened; no copy says whose mode it is (`copy_for`), so the copies in step go with the setting.
    fn with_copies(v: i64, stills: i64, movie: i64) -> (App, [Setting; 3]) {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        for s in app.schema.settings.iter_mut() {
            if s.key == MAIN { s.copies = vec![STILLS.into(), MOVIE.into()]; }
            if s.key == STILLS || s.key == MOVIE { s.copy_of = Some(MAIN.into()); }
            if [MAIN, STILLS, MOVIE].contains(&s.key.as_str()) { (s.scalar, s.copy_for) = (true, Vec::new()); }
        }
        app.schema.camera.live_mode = None;
        app.schema_gen += 1;
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        let n = app.doc.as_ref().unwrap().edited.sections.len();
        as_opened(&mut app, |c| for section in c.sections.iter_mut().take(n) {
            for (s, x) in three.iter().zip([v, stills, movie]) {
                section.get_mut(s.id).unwrap().put(s.index, x).unwrap();
            }
        });
        (app, three)
    }

    /// The shooting modes as a definition says them (`camera.live_mode`, `copy_for`), made here: a live record of the
    /// sample the memories do not keep says the mode the file was saved in, its first value the first mode
    /// `camera.memory_sets.modes` lists and its second the second (a third it does not name); the stills copy is the
    /// first mode's, the movie copy every other mode's. The live settings are saved in the first mode (`first`) or the
    /// second; returns the modes' names, the first two.
    fn with_modes(app: &mut App, first: bool) -> (String, String) {
        let modes: Vec<String> = app.schema.camera.modes().iter().map(|(m, _)| m.to_string()).collect();
        let mode = app.schema.settings.iter().find(|s| s.area == "global" && s.scalar && s.text.is_none() && s.copies.is_empty() && s.copy_of.is_none() && s.values.len() >= 3 && s.range.is_none() && s.index.is_none() && !s.in_sets).cloned().unwrap();
        let (a, b) = (mode.values[0].0, mode.values[1].0);
        app.schema.camera.live_mode = Some(camset_editor::schema::LiveMode { key: mode.key.clone(), modes: [(a.to_string(), modes[0].clone()), (b.to_string(), modes[1].clone())].into() });
        for s in app.schema.settings.iter_mut() {
            if s.key == STILLS { s.copy_for = vec![modes[0].clone()]; }
            if s.key == MOVIE { s.copy_for = modes[1..].to_vec(); }
        }
        app.schema_gen += 1;
        as_opened(app, |c| c.sections[0].get_mut(mode.id).unwrap().put(mode.index, if first { a } else { b }).unwrap());
        (modes[0].clone(), modes[1].clone())
    }

    fn held(app: &App, three: &[Setting; 3], si: usize) -> [Option<i64>; 3] {
        let d = app.doc.as_ref().unwrap();
        [d.value(si, three[0].slot()), d.value(si, three[1].slot()), d.value(si, three[2].slot())]
    }

    /// An edit of the setting takes the copies that held its value in the file as opened, in the same undoable step, in
    /// the set edited only; Revert and the history's revert take them back the same way.
    #[test]
    fn an_edit_takes_the_copies_that_followed_in_the_file_as_opened() {
        let (mut app, three) = with_copies(0, 0, 0);
        app.apply(vec![Action::Set(0, three[0].slot(), 3)]);
        assert_eq!(held(&app, &three, 0), [Some(3); 3]);
        assert_eq!(held(&app, &three, 1), [Some(0); 3], "Memory 1 keeps its own");
        assert_eq!(app.undo.len(), 1, "one step");
        app.undo();
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        app.redo();
        assert_eq!(held(&app, &three, 0), [Some(3); 3]);
        app.apply(vec![Action::Revert(0, three[0].slot())]);
        assert_eq!(held(&app, &three, 0), [Some(0); 3], "Revert takes the copies back with it");
        // the history's revert puts the record back whole; the copies follow it too
        app.apply(vec![Action::Set(0, three[0].slot(), 5)]);
        let before = app.undo.last().unwrap().sections[0].get(three[0].id).unwrap().clone();
        app.apply(vec![Action::SetRecord(0, before)]);
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        // in a memory set, the same in that set alone
        app.apply(vec![Action::Set(1, three[0].slot(), -2)]);
        assert_eq!((held(&app, &three, 1), held(&app, &three, 0)), ([Some(-2); 3], [Some(0); 3]));
        // a copy that held another value in the file as opened is left as it was
        let (mut app, three) = with_copies(0, 4, 0);
        app.apply(vec![Action::Set(0, three[0].slot(), 2)]);
        assert_eq!(held(&app, &three, 0), [Some(2), Some(4), Some(2)]);
        assert!(app.acceptance_issues().iter().all(|i| i.kind != IssueKind::Copy), "the movie copy holds the value: as a camera writes it");
    }

    /// Which copies follow is decided from the file as opened, never from the values the setting passes through: a
    /// drag (one undo step) or + and − steps (several) through a value a copy happens to hold do not take that copy.
    #[test]
    fn a_copy_that_differed_in_the_file_as_opened_never_follows() {
        // the setting 0, the stills copy 0, the movie copy 2: stepped 0, 1, 2, 3 as one drag
        let (mut app, three) = with_copies(0, 0, 2);
        for v in 1..=3 {
            app.apply(vec![Action::Set(0, three[0].slot(), v)]);
        }
        assert_eq!(app.undo.len(), 1, "a drag is one step");
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(2)], "the movie copy did not follow through 2");
        // the same in separate steps, the setting stopping on 2 on the way
        let (mut app, three) = with_copies(0, 0, 2);
        app.apply(vec![Action::Set(0, three[0].slot(), 2)]);
        app.last_edit = None;
        app.apply(vec![Action::Set(0, three[0].slot(), 3)]);
        assert_eq!(app.undo.len(), 2);
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(2)]);
        assert!(app.acceptance_issues().iter().all(|i| i.kind != IssueKind::Copy), "the stills copy holds the value");
    }

    /// Where no mode is known, a copy in step with its setting (the three equal as the file was opened) may be changed,
    /// and changing it changes the setting and the other copy in step, in one undo step, as its row says beforehand:
    /// from the window's row, the page, Compare's picker and arrow, and in a memory set. Its Revert is its setting's: it
    /// never goes back alone (the reviewer's case: all three changed through the stills copy, then the stills copy
    /// reverted). A copy of several rows at once keeps each row's own value. In Expert mode the copy changes alone.
    #[test]
    fn a_copy_in_step_changed_changes_its_setting_and_the_copies_in_step() {
        let (mut app, three) = with_copies(0, 0, 0);
        assert!(app.locked_why(&three[1], 0).is_none() && !app.locked(&three[1], 0), "a copy is not view only");
        let (note, hover) = app.copy_note(&three[1], 0).expect("the row says what changes");
        // its hover names the records from the definition's settings, never a camera's (decision 20)
        assert!(hover.starts_with(&format!("The camera keeps the value of {} in {} and {} too", three[0].name, three[1].name, three[2].name)), "{hover}");
        assert!(note.starts_with(&format!("Changing this changes {} and {} too", three[0].name, three[2].name)) && note.contains("Expert mode"), "{note}");
        assert!(app.copy_note(&three[0], 0).is_none(), "the setting itself needs no note");
        // the window's row
        app.apply(vec![Action::Set(0, three[1].slot(), 4)]);
        assert_eq!(held(&app, &three, 0), [Some(4); 3]);
        assert_eq!(app.undo.len(), 1, "one step");
        app.undo();
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        app.redo();
        // Revert of the copy is its setting's Revert: all three go back, never the copy alone
        app.apply(vec![Action::Revert(0, three[1].slot())]);
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        // the page: the copy's row is editable and carries the note; a change of it takes the setting and the other
        // copy, whose rows come with the reply; its Revert takes them back
        let row = app.web_row(0, std::slice::from_ref(&three[1]));
        assert_eq!((row["editable"].clone(), row["locked"].is_null(), row["copy_note"].as_str()), (json!(true), true, Some(note.as_str())));
        let r = answer(&mut app, "set", json!({ "target": 0, "key": STILLS, "value": 3 }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!(held(&app, &three, 0), [Some(3); 3]);
        let keys: Vec<String> = body!(r)["rows"].as_array().unwrap().iter().map(|x| x["key"].as_str().unwrap_or("").to_string()).collect();
        assert!(keys.contains(&MAIN.to_string()) && keys.contains(&MOVIE.to_string()), "the rows that moved come with the reply: {keys:?}");
        assert_eq!(answer(&mut app, "revert", json!({ "target": 0, "key": STILLS })).status, 200);
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        // a memory set: the same in that set alone
        app.apply(vec![Action::Set(1, three[2].slot(), -2)]);
        assert_eq!((held(&app, &three, 1), held(&app, &three, 0)), ([Some(-2); 3], [Some(0); 3]));
        app.undo();
        // Compare: the copy's cell takes a value in place, and an arrow brings it in, as an edit of it
        assert!(app.cell_editable(Col::a(0), std::slice::from_ref(&three[1])));
        let mut b = app.doc.as_ref().unwrap().original.clone();
        b.sections[0].get_mut(three[1].id).unwrap().put(three[1].index, 5).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        assert_eq!(app.arrows_between(Col::b(0), Col::a(0), &three[1]), (false, true));
        let acts = app.copy_row(std::slice::from_ref(&three[1]), Col::b(0), Col::a(0));
        app.apply(acts);
        assert_eq!(held(&app, &three, 0), [Some(5); 3], "one row copied is an edit of the copy");
        app.undo();
        // every row at once keeps each row's own value: file A then holds what B holds (the stills copy apart)
        let mut acts: Vec<Action> = three.iter().flat_map(|s| app.copy_row(std::slice::from_ref(s), Col::b(0), Col::a(0))).collect();
        app.pin_families(None, 0, &mut acts);
        app.apply(acts);
        assert_eq!(held(&app, &three, 0), [Some(0), Some(5), Some(0)]);
        app.undo();
        let r = answer(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": [MAIN, STILLS, MOVIE] }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!(held(&app, &three, 0), [Some(0), Some(5), Some(0)], "the page's Copy all shown rows");
        app.undo();
        // Expert mode: the copy changes alone, and its row says so
        app.prefs.expert = true;
        assert!(app.copy_note(&three[1], 0).unwrap().0.contains("in Expert mode changing it changes it alone"));
        app.apply(vec![Action::Set(0, three[1].slot(), 9)]);
        assert_eq!(held(&app, &three, 0), [Some(0), Some(9), Some(0)]);
    }

    /// A Main page tile keyed to a copy (the shipped definition keys the movie Main page's tiles to the movie copies) is
    /// editable, says what a change takes along, and a change from the window's tile or the page's takes the setting
    /// and the copies in step with it, in one step.
    #[test]
    fn a_tile_keyed_to_a_copy_changes_its_setting_too() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let pages = app.schema.camera.main_tiles.clone().expect("the a1 II's Main page");
        let (page, copy) = pages.0.iter().enumerate().find_map(|(i, p)| p.tiles.iter().filter(|t| t.keys_for(0).len() == 1)
            .filter_map(|t| app.schema.settings.iter().find(|s| s.key == t.keys_for(0)[0] && s.copy_of.is_some() && s.scalar && s.values.len() >= 3).cloned())
            .find(|s| app.main_of(s).is_some_and(|m| m.scalar)).map(|s| (i, s))).expect("a tile keyed to a copy");
        let main = app.main_of(&copy).cloned().unwrap();
        let offered = app.offered_values(&copy, 0);
        let (v0, v1) = (offered[0].0, offered[1].0);
        // the setting and every copy of it holding one value as the file was opened: all in step
        let all: Vec<Setting> = std::iter::once(main.clone()).chain(main.copies.iter().map(|k| setting(&app, k))).collect();
        as_opened(&mut app, |c| for s in &all { c.sections[0].get_mut(s.id).unwrap().put(s.index, v0).unwrap(); });
        assert!(app.tile_changes_in_place(&copy, 0), "the window's tile changes in place");
        let (note, _) = app.copy_note(&copy, 0).expect("the tile says what changes");
        assert!(note.starts_with(&format!("Changing this changes {}", main.name)), "{note}");
        let m = body!(answer(&mut app, "main", json!({ "target": 0, "set": page })));
        let tile = m["tiles"].as_array().unwrap().iter().find(|t| t["edit"]["key"] == json!(copy.key)).expect("the page's tile changes in place").clone();
        assert_eq!(tile["edit"]["copy_note"], json!(note));
        assert!(tile["why"].as_str().unwrap_or("").contains(&note), "its hover says it too");
        // the window's tile asks for the copy's value, as its popup does
        app.apply(vec![Action::Set(0, copy.slot(), v1)]);
        let d = app.doc.as_ref().unwrap();
        assert!(all.iter().all(|s| d.value(0, s.slot()) == Some(v1)), "the setting and every copy in step took it");
        assert_eq!(app.undo.len(), 1);
        app.undo();
        assert_eq!(answer(&mut app, "set", json!({ "target": 0, "key": copy.key, "value": v1 })).status, 200);
        let d = app.doc.as_ref().unwrap();
        assert!(all.iter().all(|s| d.value(0, s.slot()) == Some(v1)), "the page's tile the same");
    }

    /// A copy that held another value than its setting as the file was opened changes alone, says so, and goes back
    /// alone.
    #[test]
    fn a_copy_apart_changes_alone() {
        let (mut app, three) = with_copies(0, 4, 0);
        let (note, _) = app.copy_note(&three[1], 0).unwrap();
        assert!(note.contains("it changes alone") && note.contains("held another value"), "{note}");
        app.apply(vec![Action::Set(0, three[1].slot(), 6)]);
        assert_eq!(held(&app, &three, 0), [Some(0), Some(6), Some(0)]);
        app.apply(vec![Action::Revert(0, three[1].slot())]);
        assert_eq!(held(&app, &three, 0), [Some(0), Some(4), Some(0)]);
        assert_eq!(answer(&mut app, "set", json!({ "target": 0, "key": STILLS, "value": 2 })).status, 200);
        assert_eq!(held(&app, &three, 0), [Some(0), Some(2), Some(0)]);
    }

    /// Outside Expert mode an edit that would leave the setting held by none of its copies is refused, with why and
    /// what to do, and nothing changes; one that puts things back as the file was opened, or leaves a file opened so no
    /// worse, is not. In Expert mode it is made.
    #[test]
    fn an_edit_that_leaves_a_setting_held_by_no_copy_is_refused() {
        // opened so (no camera wrote it): edits no worse are made, one that mends it is made, and then one that breaks it
        // again is refused; the copy's Revert puts it back as opened
        let (mut app, three) = with_copies(1, 2, 3);
        assert!(app.apply(vec![Action::Set(0, three[0].slot(), 4)]).is_none());
        assert_eq!(held(&app, &three, 0), [Some(4), Some(2), Some(3)]);
        app.undo();
        assert!(app.apply(vec![Action::Set(0, three[1].slot(), 1)]).is_none(), "mended");
        let steps = app.undo.len();
        let why = app.apply(vec![Action::Set(0, three[1].slot(), 5)]).expect("refused");
        assert_eq!(held(&app, &three, 0), [Some(1), Some(1), Some(3)], "nothing changed");
        assert_eq!((app.undo.len(), app.status.as_str()), (steps, why.as_str()));
        assert!(why.starts_with("Not changed") && why.contains(&format!("Set {} to a value one of them holds", three[0].name)) && why.contains("Expert mode"), "{why}");
        let r = answer(&mut app, "set", json!({ "target": 0, "key": STILLS, "value": 5 }));
        assert_eq!((r.status, body!(r)["error"].clone()), (409, json!(why)), "the page says the same");
        assert!(app.apply(vec![Action::Revert(0, three[1].slot())]).is_none());
        assert_eq!(held(&app, &three, 0), [Some(1), Some(2), Some(3)], "back as opened");
        // the copies in step moved apart in Expert mode, the setting held by the copy apart alone: changing that copy is
        // refused, and the words say to change the setting, which the copies in step follow
        let (mut app, three) = with_copies(0, 4, 0);
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[0].slot(), 4)]);
        app.apply(vec![Action::Set(0, three[2].slot(), 9)]);
        assert_eq!(held(&app, &three, 0), [Some(4), Some(4), Some(9)]);
        app.prefs.expert = false;
        let why = app.apply(vec![Action::Set(0, three[1].slot(), 5)]).expect("refused");
        assert!(why.contains(&format!("Change {} instead", three[0].name)), "{why}");
        assert_eq!(held(&app, &three, 0), [Some(4), Some(4), Some(9)]);
        // Expert mode makes it, and the windows list it
        app.prefs.expert = true;
        assert!(app.apply(vec![Action::Set(0, three[1].slot(), 5)]).is_none());
        assert!(app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Copy && i.slot == three[0].slot() && i.section == 0));
    }

    /// Where a set's shooting mode is known (`camera.live_mode`, `copy_for`), it is checked, never used to decide what
    /// follows (whether the camera moves the other modes' copies too is a setting of its own no proof has read): the
    /// copies in step follow as where it is not known, the other mode's among them, and a copy in step is reverted only
    /// with its setting. An edit or a Revert that would part the setting from its mode's copy is refused outside Expert
    /// mode, with why, though another copy holds the value (the weaker rule would pass it), in a memory set by its own
    /// mode; in Expert mode it is made, listed, and put back by the windows' fix.
    #[test]
    fn with_the_mode_known_the_copy_for_it_is_checked() {
        let (mut app, _) = with_copies(0, 0, 0);
        let (first, second) = with_modes(&mut app, true);
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        let (note, _) = app.copy_note(&three[1], 0).unwrap();
        assert!(note.contains("they held the same value when this file was opened or read, so the editor keeps them together") && note.contains("Expert mode"), "{note}");
        assert!(app.copy_note(&three[2], 0).unwrap().0.starts_with("Changing this changes"), "the other mode's copy in step follows too");
        // what follows: the copies in step, the other mode's among them, in one step
        app.apply(vec![Action::Set(0, three[0].slot(), 6)]);
        assert_eq!(held(&app, &three, 0), [Some(6); 3]);
        assert_eq!(app.undo.len(), 1);
        // the stills copy's record put back by itself would part the setting from its mode's copy: refused, though the
        // movie copy holds the value; the page says the same
        let steps = app.undo.len();
        let why = app.apply(vec![Action::Revert(0, (three[1].id, None))]).expect("refused");
        assert!(why.starts_with("Not changed") && why.contains(&format!("this file was saved in {first} mode, and in {first} mode the camera always holds")), "{why}");
        assert!(why.contains("Change or revert"), "what to do: {why}");
        assert_eq!((held(&app, &three, 0), app.undo.len()), ([Some(6); 3], steps));
        assert_eq!(answer(&mut app, "revert_record", json!({ "section": 0, "id": three[1].id })).status, 409);
        // the movie copy's record put back by itself is as a camera writes it
        assert!(app.apply(vec![Action::Revert(0, (three[2].id, None))]).is_none());
        assert_eq!(held(&app, &three, 0), [Some(6), Some(6), Some(0)]);
        app.undo();
        // the Revert of a copy in step is its setting's, the mode known or not
        app.apply(vec![Action::Set(0, three[1].slot(), 5)]);
        assert_eq!(held(&app, &three, 0), [Some(5); 3]);
        app.apply(vec![Action::Revert(0, three[1].slot())]);
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        app.undo();
        app.undo();
        assert_eq!(held(&app, &three, 0), [Some(6); 3]);
        // a memory set of the second mode: its movie copy is the one checked
        let m = app.schema.camera.modes()[1].1[0];
        app.apply(vec![Action::Set(m, three[0].slot(), 2)]);
        assert_eq!(held(&app, &three, m), [Some(2); 3]);
        assert!(app.apply(vec![Action::Revert(m, (three[1].id, None))]).is_none(), "the stills copy apart in a {second} memory set");
        let why = app.apply(vec![Action::Revert(m, (three[2].id, None))]).expect("refused");
        assert!(why.contains(&format!("is a {second} memory set")), "{why}");
        assert_eq!(held(&app, &three, m), [Some(2), Some(0), Some(2)]);
        // Expert mode: made, then listed in the windows with a way back
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[1].slot(), 9)]);
        assert_eq!(held(&app, &three, 0), [Some(6), Some(9), Some(6)]);
        app.prefs.expert = false;
        for issues in [app.acceptance_issues(), app.write_issues()] {
            let one = issues.iter().find(|i| i.kind == IssueKind::Copy && i.section == 0).expect("listed");
            assert!(one.slot == three[0].slot() && one.reason.contains(&format!("in {first} mode the camera keeps this value in {}", three[1].name)), "{}", one.reason);
        }
        let issues = app.write_issues();
        let one = issues.iter().find(|i| i.kind == IssueKind::Copy && i.section == 0).unwrap();
        let (words, fix) = app.issue_fix(one).expect("a way back");
        assert_eq!(words, COPIES_BACK_IN_STEP);
        app.apply(fix);
        assert_eq!(held(&app, &three, 0), [Some(6); 3]);
        assert!(app.write_issues().iter().all(|i| !(i.kind == IssueKind::Copy && i.section == 0)));
        // with no mode known, the stills copy's record put back by itself is made: the movie copy holds the value
        app.schema.camera.live_mode = None;
        app.schema_gen += 1;
        assert!(app.apply(vec![Action::Revert(0, (three[1].id, None))]).is_none());
        assert_eq!(held(&app, &three, 0), [Some(6), Some(0), Some(6)]);
    }

    /// A file whose setting differs from the copy for its mode is listed in the save and write windows, edited or not,
    /// though another copy holds its value (the rule where no mode is known would pass it), its rows say it is out of
    /// step, and the windows' fix sets that copy to the setting's value; the same values in a file saved in the other
    /// mode are as a camera writes them.
    #[test]
    fn a_file_out_of_step_with_its_mode_is_listed() {
        let (mut app, _) = with_copies(0, 4, 0);
        assert!(app.acceptance_issues().iter().all(|i| i.kind != IssueKind::Copy), "no mode known: the movie copy holds it");
        let (first, _) = with_modes(&mut app, true);
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        for issues in [app.acceptance_issues(), app.write_issues()] {
            let one = issues.iter().find(|i| i.kind == IssueKind::Copy && i.section == 0).expect("listed though nothing was edited");
            assert!(one.slot == three[0].slot() && one.reason.contains("it was so when the file was opened"), "{}", one.reason);
        }
        let (note, _) = app.copy_note(&three[0], 0).unwrap();
        assert!(note.starts_with(&format!("Out of step: this file was saved in {first} mode")), "{note}");
        assert_eq!(app.web_row(0, std::slice::from_ref(&three[0]))["copy_note"], json!(note));
        // the memory sets of the second mode hold the setting at its movie copy's value: not listed
        let m = app.schema.camera.modes()[1].1[0];
        assert!(app.acceptance_issues().iter().all(|i| i.section != m));
        // the fix: the stills copy at the setting's value
        let issues = app.acceptance_issues();
        let one = issues.iter().find(|i| i.kind == IssueKind::Copy && i.section == 0).unwrap();
        let (_, fix) = app.issue_fix(one).expect("a way back");
        assert!(app.apply(fix).is_none());
        assert_eq!(held(&app, &three, 0), [Some(0), Some(0), Some(0)]);
        assert!(app.acceptance_issues().iter().all(|i| !(i.kind == IssueKind::Copy && i.section == 0)));
        // saved in the second mode: the movie copy is the one, and it holds the value
        let (mut app, _) = with_copies(0, 4, 0);
        with_modes(&mut app, false);
        assert!(app.acceptance_issues().iter().all(|i| !(i.kind == IssueKind::Copy && i.section == 0)));
    }

    /// A live record holding a value the definition's modes do not name leaves the live settings' mode unknown: the
    /// weaker check stands there (the setting equal to at least one copy), and a copy in step is reverted only with its
    /// setting, as everywhere.
    #[test]
    fn a_mode_not_named_falls_back_to_the_weaker_check() {
        let (mut app, _) = with_copies(0, 4, 0);
        with_modes(&mut app, true);
        assert!(app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Copy && i.section == 0), "named: listed");
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let s = setting(&app, &lm.key);
        let unnamed = s.values.iter().map(|(v, _)| *v).find(|v| !lm.modes.contains_key(&v.to_string())).expect("a value no mode names");
        as_opened(&mut app, |c| c.sections[0].get_mut(s.id).unwrap().put(s.index, unnamed).unwrap());
        assert!(app.section_mode(&app.doc.as_ref().unwrap().edited, 0).is_none());
        assert!(app.acceptance_issues().iter().all(|i| !(i.kind == IssueKind::Copy && i.section == 0)), "not named: the movie copy holds the value");
        let (mut app, three) = with_copies(0, 0, 0);
        with_modes(&mut app, true);
        as_opened(&mut app, |c| c.sections[0].get_mut(s.id).unwrap().put(s.index, unnamed).unwrap());
        app.apply(vec![Action::Set(0, three[1].slot(), 5)]);
        assert_eq!(held(&app, &three, 0), [Some(5); 3]);
        app.apply(vec![Action::Revert(0, three[1].slot())]);
        assert_eq!(held(&app, &three, 0), [Some(0); 3], "the copy's Revert is the setting's");
    }

    /// The live record that says the shooting mode, changed, changes which copy every setting there is checked against:
    /// a change of it that leaves a setting apart from the new mode's copy is refused outside Expert mode, with why.
    #[test]
    fn changing_the_mode_record_is_checked() {
        let (mut app, _) = with_copies(0, 0, 4);
        let (_, second) = with_modes(&mut app, true);
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let mode = mode_record_proved(&mut app);
        assert!(!app.locked(&mode, 0));
        let movie = lm.modes.iter().find(|(_, m)| **m == second).map(|(v, _)| v.parse::<i64>().unwrap()).unwrap();
        let why = app.apply(vec![Action::Set(0, mode.slot(), movie)]).expect("refused");
        assert!(why.contains(&format!("this file was saved in {second} mode")), "{why}");
        assert_eq!(held(&app, &three, 0), [Some(0), Some(0), Some(4)]);
        // with the movie copy at the setting's value it is made
        let (mut app, _) = with_copies(0, 0, 0);
        with_modes(&mut app, true);
        mode_record_proved(&mut app);
        assert!(app.apply(vec![Action::Set(0, mode.slot(), movie)]).is_none());
    }

    /// The mode record proved, so that only the copies' check stands in the way of changing or copying it.
    fn mode_record_proved(app: &mut App) -> Setting {
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let proof = app.schema.settings.iter().find_map(|s| s.proved.clone()).unwrap();
        for s in app.schema.settings.iter_mut().filter(|s| s.key == lm.key) {
            (s.proved, s.disputed, s.unproved_reason, s.unproved_sets) = (Some(proof.clone()), false, None, None);
        }
        app.schema_gen += 1;
        setting(app, &lm.key)
    }

    /// Several rows copied at once (Copy all shown rows, a memory's recall), the window's and the page's: each place of a
    /// setting kept in more than one record takes what the other file holds, a copy equal in both files included, which
    /// then never follows its setting (the reviewer's case: A saved in the first mode at (0, 0, 0), B at (3, 3, 0): A ends
    /// at B's (3, 3, 0), not (3, 3, 3)). A copy that would leave the setting apart from its mode's copy (B saved in the
    /// second mode, its shooting-mode row left out) is refused, saying to copy that row too or to use Expert mode, and is
    /// made with the row.
    #[test]
    fn a_copy_of_rows_keeps_each_place_as_the_other_file_holds_it() {
        let (mut app, _) = with_copies(0, 0, 0);
        let (_, second) = with_modes(&mut app, true);
        let mode = mode_record_proved(&mut app);
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        let put = |c: &mut CamSet, si: usize, vals: [i64; 3]| for (s, x) in three.iter().zip(vals) { c.sections[si].get_mut(s.id).unwrap().put(s.index, x).unwrap(); };
        let mut b = app.doc.as_ref().unwrap().original.clone();
        put(&mut b, 0, [3, 3, 0]);
        app.compare = Some((PathBuf::from("B.DAT"), b.clone()));
        // the window's Copy all shown rows
        let mut acts: Vec<Action> = three.iter().flat_map(|s| app.copy_row(std::slice::from_ref(s), Col::b(0), Col::a(0))).collect();
        app.pin_families(None, 0, &mut acts);
        assert!(app.apply(acts).is_none());
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(0)]);
        app.undo();
        // the page's
        let r = answer(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": [MAIN, STILLS, MOVIE] }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(0)]);
        app.undo();
        // a memory of the first mode holding (3, 3, 0) recalled into the live settings, in the window and on the page
        let m = app.dial_sets()[0];
        as_opened(&mut app, |c| put(c, m, [3, 3, 0]));
        let mut acts: Vec<Action> = app.memory_rows().iter().flat_map(|r| app.copy_row(&r.2, Col::a(m), Col::a(0))).collect();
        app.pin_families(Some(m), 0, &mut acts);
        assert!(app.apply(acts).is_none());
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(0)]);
        app.undo();
        let r = answer(&mut app, "recall", json!({ "memory": m }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(0)]);
        app.undo();
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        // B saved in the second mode at (3, 0, 3): its rows without its shooting-mode row would leave A's setting apart
        // from the first mode's copy; refused, in the window and on the page, and nothing changed
        let lm = app.schema.camera.live_mode.clone().unwrap();
        let movie = lm.modes.iter().find(|(_, x)| **x == second).map(|(v, _)| v.parse::<i64>().unwrap()).unwrap();
        put(&mut b, 0, [3, 0, 3]);
        b.sections[0].get_mut(mode.id).unwrap().put(mode.index, movie).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        let mut acts: Vec<Action> = three.iter().flat_map(|s| app.copy_row(std::slice::from_ref(s), Col::b(0), Col::a(0))).collect();
        app.pin_families(None, 0, &mut acts);
        let why = app.apply(acts).expect("refused");
        assert!(why.starts_with("Not copied") && why.contains(&format!("Copy the {} row too", mode.name)) && why.contains("Expert mode"), "{why}");
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        let r = answer(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": [MAIN, STILLS, MOVIE] }));
        assert_eq!((r.status, body!(r)["error"].clone()), (409, json!(why)));
        // with the shooting-mode row, the file is in B's mode and holds B's values
        let r = answer(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": [MAIN, STILLS, MOVIE, mode.key] }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!(held(&app, &three, 0), [Some(3), Some(0), Some(3)]);
        assert_eq!(app.section_mode(&app.doc.as_ref().unwrap().edited, 0), Some(second));
    }

    /// A Set that leaves its own record as it is changes nothing: outside a copy of several rows it does not pass the
    /// lock guard for a view-only copy, and it never takes the copy's setting and the copies in step along (the
    /// reviewer's case: a view-only copy changed alone to 2 in Expert mode, the setting and the other copy at 0, then
    /// set to 2 again outside it, which once made all three 2 and an undo step).
    #[test]
    fn a_set_that_changes_nothing_spreads_nothing() {
        let (mut app, three) = with_copies(0, 0, 0);
        for s in app.schema.settings.iter_mut().filter(|s| s.key == MOVIE) {
            s.proved = None;
        }
        app.schema_gen += 1;
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[2].slot(), 2)]);
        app.prefs.expert = false;
        assert_eq!(held(&app, &three, 0), [Some(0), Some(0), Some(2)]);
        let steps = app.undo.len();
        let why = app.apply(vec![Action::Set(0, three[2].slot(), 2)]).expect("view only");
        assert!(why.starts_with("View only"), "{why}");
        assert_eq!((held(&app, &three, 0), app.undo.len()), ([Some(0), Some(0), Some(2)], steps));
        // the copy free to change: the same Set still changes nothing anywhere
        let (mut app, three) = with_copies(0, 0, 0);
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[1].slot(), 2)]);
        app.prefs.expert = false;
        let steps = app.undo.len();
        assert!(app.apply(vec![Action::Set(0, three[1].slot(), 2)]).is_none());
        assert_eq!((held(&app, &three, 0), app.undo.len()), ([Some(0), Some(2), Some(0)], steps));
    }

    /// A whole memory recalled into, or the live settings registered into, a memory of another shooting mode than the
    /// file was saved in, which would leave a file no camera writes, is refused in words true of the Memories page (it
    /// has no shooting-mode row to copy): the memory's mode, the file's, that the camera recalls or registers a mode's
    /// memories only in that mode, and that Expert mode copies it all the same; in the window and on the page.
    #[test]
    fn a_recall_or_register_across_modes_says_why() {
        let (mut app, _) = with_copies(0, 0, 0);
        let (first, second) = with_modes(&mut app, false);
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        let put = |c: &mut CamSet, si: usize, vals: [i64; 3]| for (s, x) in three.iter().zip(vals) { c.sections[si].get_mut(s.id).unwrap().put(s.index, x).unwrap(); };
        let m = app.dial_sets()[0];
        assert_eq!(app.schema.camera.memory_mode(m), Some(first.as_str()));
        let name = app.schema.camera.target_name(m);
        // recalled: the first mode's memory into a file saved in the second
        as_opened(&mut app, |c| put(c, m, [3, 3, 0]));
        let mut acts: Vec<Action> = app.memory_rows().iter().flat_map(|r| app.copy_row(&r.2, Col::a(m), Col::a(0))).collect();
        app.pin_families(Some(m), 0, &mut acts);
        let why = app.apply(acts).expect("refused");
        assert_eq!(why, format!("Not recalled: {name} is a {first} memory and this file was saved in {second} mode; the camera recalls a mode's memories only in that mode, so these values would leave a file no camera writes. Expert mode (⚙ Settings > Editing & Compare) copies it all the same."));
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        let r = answer(&mut app, "recall", json!({ "memory": m }));
        assert_eq!((r.status, body!(r)["error"].clone()), (409, json!(why)));
        // registered: the live settings, as the second mode keeps them, into the first mode's memory
        as_opened(&mut app, |c| { put(c, 0, [3, 0, 3]); put(c, m, [0, 0, 0]); });
        let mut acts: Vec<Action> = app.memory_rows().iter().flat_map(|r| app.copy_row(&r.2, Col::a(0), Col::a(m))).collect();
        app.pin_families(Some(0), m, &mut acts);
        let why = app.apply(acts).expect("refused");
        assert!(why.starts_with(&format!("Not registered: {name} is a {first} memory and this file was saved in {second} mode; the camera registers a mode's memories only in that mode")) && why.contains("Expert mode") && !why.contains("row too"), "{why}");
        assert_eq!(held(&app, &three, m), [Some(0); 3]);
        let r = answer(&mut app, "register", json!({ "memory": m }));
        assert_eq!((r.status, body!(r)["error"].clone()), (409, json!(why)));
    }

    /// The page's "activate" (a greyed-out setting's switch) says a refusal as the other handlers do: 409 with the reason,
    /// the status keeping it, nothing changed.
    #[test]
    fn the_pages_activate_says_a_refusal() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        // a greyed-out setting whose switch is a record a setting of its own holds whole, made view only
        let (grey, rule) = app.schema.settings.iter().filter(|s| kept_in(s, 0)).find_map(|s| {
            let r = s.inactive_when.clone()?;
            app.schema.settings.iter().any(|o| o.slot() == (r.record, None) && o.area == "global").then(|| (s.clone(), r))
        }).expect("a greyed-out setting");
        for o in app.schema.settings.iter_mut().filter(|o| o.slot() == (rule.record, None)) {
            o.proved = None;
        }
        app.schema_gen += 1;
        // the switch off as the file was opened, so the change is a real one
        let switch = app.schema.settings.iter().find(|o| o.slot() == (rule.record, None)).cloned().unwrap();
        let off = switch.values.iter().map(|(v, _)| *v).find(|v| *v != rule.unlock).unwrap_or(rule.unlock + 1);
        as_opened(&mut app, |c| c.sections[0].get_mut(rule.record).unwrap().put(None, off).unwrap());
        let before = app.doc.as_ref().unwrap().value(0, (rule.record, None));
        let r = answer(&mut app, "activate", json!({ "target": 0, "key": grey.key }));
        let error = body!(r)["error"].as_str().unwrap_or("").to_string();
        assert_eq!(r.status, 409, "{}", String::from_utf8_lossy(&r.body));
        assert!(error.starts_with("View only") && app.status == error, "{error} / {}", app.status);
        assert_eq!(app.doc.as_ref().unwrap().value(0, (rule.record, None)), before);
    }

    /// The Expert-mode dead end: a copy changed by itself, its setting left as the file held it, the other copy still
    /// holding the setting's value: a normal difference, never listed. Outside Expert mode its Revert is its setting's,
    /// which puts all three back; after a save, the copy is put back in step with its setting, in words that say so.
    #[test]
    fn a_copy_changed_alone_in_expert_mode() {
        let (mut app, three) = with_copies(0, 0, 0);
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[1].slot(), 5)]);
        app.prefs.expert = false;
        assert!(app.write_issues().iter().all(|i| i.kind != IssueKind::Copy), "the movie copy holds the setting's value");
        let r = answer(&mut app, "revert", json!({ "target": 0, "key": STILLS }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
        // the setting changed, then the copy apart from it in Expert mode, and the file saved so: Revert changes nothing,
        // and what puts the copy back is "Back in step with" its setting, its hover true to that
        app.apply(vec![Action::Set(0, three[0].slot(), 7)]);
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[1].slot(), -1)]);
        app.prefs.expert = false;
        let d = app.doc.as_mut().unwrap();
        d.original = d.edited.clone();
        let (words, fix) = app.put_back_choice(std::slice::from_ref(&three[1]), 0).expect("offered");
        assert_eq!(words, format!("Back in step with {}", three[0].name));
        let hover = App::put_back_hover(&words);
        assert!(hover.starts_with(&format!("Sets this copy to the value {} holds now", three[0].name)) && !hover.contains("what the camera wrote"), "{hover}");
        let row = app.web_row(0, std::slice::from_ref(&three[1]));
        assert_eq!((row["put_back"].clone(), row["put_back_why"].clone()), (json!(words), json!(hover)));
        app.apply(fix);
        assert_eq!(held(&app, &three, 0), [Some(7); 3]);
        assert!(App::put_back_hover(REVERT_TO_CAMERA).contains("what the camera wrote"));
    }

    /// A copy whose setting the definition does not name says so in words, never by the key it names, outside Expert
    /// mode; it is view only, as the editor cannot keep the two in step.
    #[test]
    fn a_copy_of_a_setting_not_named_says_so_in_words() {
        let (mut app, _) = with_copies(0, 0, 0);
        for s in app.schema.settings.iter_mut().filter(|s| s.key == STILLS) {
            s.copy_of = Some("global:0x7ffe".into());
        }
        app.schema_gen += 1;
        let s = setting(&app, STILLS);
        let (why, _) = app.locked_why(&s, 0).expect("view only");
        assert!(why.starts_with("View only: the camera keeps this as a copy of another setting") && !why.contains("0x7ffe") && !why.contains("global:"), "{why}");
        assert!(app.locked(&s, 0));
    }

    /// A file no camera wrote that way (the setting holding none of its copies' values): listed in the save and write
    /// windows whenever the file holds it, edited or not, with what to do, and its rows say so; a normal difference
    /// between the copies is not listed. One made so in Expert mode is put back by putting its copies back in step.
    #[test]
    fn a_setting_none_of_its_copies_holds_is_listed() {
        let (mut app, three) = with_copies(1, 2, 3);
        for issues in [app.acceptance_issues(), app.write_issues()] {
            let main = issues.iter().find(|i| i.kind == IssueKind::Copy && i.section == 0).expect("listed though nothing was edited");
            assert_eq!(main.slot, three[0].slot());
            assert!(main.reason.contains("none of them holds it") && main.reason.contains("it was so when the file was opened"), "{}", main.reason);
            assert!(app.issue_fix(main).is_none(), "no copy was in step with it to put back");
            assert!(issues.iter().any(|i| i.kind == IssueKind::Copy && i.section == 1), "the memory sets too");
        }
        for s in &three {
            let (note, _) = app.copy_note(s, 0).unwrap();
            assert!(note.starts_with("Out of step"), "{note}");
        }
        assert!(app.web_row(0, std::slice::from_ref(&three[0]))["copy_note"].as_str().unwrap().starts_with("Out of step"));
        app.apply(vec![Action::Set(0, three[0].slot(), 4)]);
        assert!(app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Copy && i.slot == three[0].slot() && i.section == 0));
        // a normal difference: the stills copy apart
        let (app, _) = with_copies(0, 4, 0);
        assert!(app.acceptance_issues().iter().all(|i| i.kind != IssueKind::Copy));
        // made so in Expert mode: listed with its fix, which puts the copies in step back at its value
        let (mut app, three) = with_copies(0, 0, 0);
        app.prefs.expert = true;
        app.apply(vec![Action::Set(0, three[1].slot(), -1), Action::Set(0, three[2].slot(), -2)]);
        app.prefs.expert = false;
        let issues = app.acceptance_issues();
        let main = issues.iter().find(|i| i.kind == IssueKind::Copy && i.section == 0).expect("listed");
        assert!(main.reason.contains("put its copies back in step"), "{}", main.reason);
        let (words, fix) = app.issue_fix(main).expect("a fix");
        assert_eq!(words, COPIES_BACK_IN_STEP);
        app.apply(fix);
        assert_eq!(held(&app, &three, 0), [Some(0); 3]);
    }

    /// A copy whose record has another shape than it was mapped in takes no value, whichever way one comes (its setting
    /// changed, the copy changed and taking others along, a put-back), and the status says so.
    #[test]
    fn a_copy_of_another_shape_is_left_and_said() {
        let (mut app, three) = with_copies(0, 0, 0);
        for s in app.schema.settings.iter_mut().filter(|s| s.key == MOVIE) {
            s.count += 1;
        }
        app.schema_gen += 1;
        let said = "was not changed with it, as the file holds it in another shape";
        app.apply(vec![Action::Set(0, three[0].slot(), 2)]);
        assert_eq!(held(&app, &three, 0), [Some(2), Some(2), Some(0)]);
        assert!(app.status.contains(said), "{}", app.status);
        app.undo();
        app.apply(vec![Action::Set(0, three[1].slot(), 3)]);
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(0)]);
        assert!(app.status.contains(said), "{}", app.status);
        // a put-back aimed at it: left, and said; the detail panel and the page offer none for it alone
        app.status.clear();
        app.apply(vec![Action::Set(0, three[2].slot(), 3)]);
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(0)]);
        assert!(app.status.contains(said), "{}", app.status);
        let d = app.doc.as_mut().unwrap();
        d.original = d.edited.clone();
        assert!(app.put_back_choice(&[setting(&app, MOVIE)], 0).is_none());
        let r = answer(&mut app, "restore", json!({ "target": 0, "key": MOVIE }));
        assert_eq!(r.status, 409);
        assert!(String::from_utf8_lossy(&r.body).contains("in another shape"), "{}", String::from_utf8_lossy(&r.body));
        // the fix for a setting out of step leaves it out too
        assert!(app.back_in_step(&three[0], 0).iter().all(|a| !matches!(a, Action::Set(_, slot, _) if *slot == three[2].slot())));
    }

    /// A copy that shares its setting's name and place (ISO AUTO Max and its stills copy, in the shipped definition) is
    /// never linked with it into one row: the setting's row is its own, the copy has a row of its own, which says it
    /// takes the other row along; nothing drags the copy along by label, in Expert mode either.
    #[test]
    fn a_copy_with_its_settings_name_is_a_row_of_its_own() {
        let (mut app, three) = with_copies(0, 0, 0);
        let main = three[0].clone();
        for s in app.schema.settings.iter_mut().filter(|s| s.key == STILLS) {
            (s.name, s.row, s.row_at, s.under_option, s.row_mode, s.group, s.tab) = (main.name.clone(), main.row.clone(), main.row_at.clone(), main.under_option.clone(), main.row_mode.clone(), main.group.clone(), main.tab.clone());
        }
        app.schema_gen += 1;
        let copy = setting(&app, STILLS);
        assert!(copy.same_place(&main) && copy.name == main.name && !copy.links_with(&main) && !main.links_with(&copy));
        let linked = app.web_linked(0, MAIN).unwrap();
        assert_eq!(linked.iter().map(|s| s.key.as_str()).collect::<Vec<_>>(), vec![MAIN], "the setting's row holds it alone");
        assert_eq!(app.web_linked(0, STILLS).unwrap().iter().map(|s| s.key.as_str()).collect::<Vec<_>>(), vec![STILLS]);
        assert!(app.web_row(0, &linked)["locked"].is_null() && app.web_row(0, &linked)["editable"] == json!(true));
        let (note, _) = app.copy_note(&copy, 0).unwrap();
        assert!(note.starts_with(&format!("Changing this changes the other {} row", main.name)), "{note}");
        // the window's rows: the setting and its copy in rows of their own
        let rows: Vec<Vec<String>> = app.tab_groups(&main.tab).into_iter().filter(|(_, family, _)| !family).flat_map(|(_, _, r)| r).filter(|r| r.iter().any(|s| s.key == MAIN || s.key == STILLS))
            .map(|r| r.into_iter().map(|s| s.key).collect()).collect();
        assert!(rows.iter().all(|r| r.len() == 1), "{rows:?}");
        // the page's set changes the setting, and the copy follows it as a copy, not as a linked row
        assert_eq!(answer(&mut app, "set", json!({ "target": 0, "key": MAIN, "value": 5 })).status, 200);
        assert_eq!(held(&app, &three, 0), [Some(5); 3]);
        // Expert mode: a copy that differed in the file as opened is not dragged along by the setting's label
        let (mut app, three) = with_copies(0, 1, 0);
        for s in app.schema.settings.iter_mut().filter(|s| s.key == STILLS) {
            (s.name, s.row, s.row_at, s.under_option, s.row_mode, s.group, s.tab) = (main.name.clone(), main.row.clone(), main.row_at.clone(), main.under_option.clone(), main.row_mode.clone(), main.group.clone(), main.tab.clone());
        }
        app.schema_gen += 1;
        app.prefs.expert = true;
        let linked = app.web_linked(0, MAIN).unwrap();
        app.apply(App::set_linked(0, &linked, 6));
        assert_eq!(held(&app, &three, 0), [Some(6), Some(1), Some(6)]);
    }

    /// A setting no menu of the camera writes (`unproved_reason.kind` "not_on_camera", marked here on a setting the
    /// sample can change) is view only outside Expert mode with its reason, in the window, the page and Compare's copy;
    /// Expert mode changes it, and the write window lists the change as not checked on the camera. The shipped
    /// definition's PP7 to PP9 parameters are such settings.
    #[test]
    fn a_setting_no_menu_writes_is_view_only_outside_expert_mode() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let (s, v) = crate::write::safety_tests::changeable(&app);
        let why = "No menu of this body writes it (made here).";
        for x in app.schema.settings.iter_mut().filter(|x| x.key == s.key) {
            x.proved = None;
            x.unproved_reason = Some(camset_editor::schema::UnprovedReason { kind: "not_on_camera".into(), why: why.into() });
        }
        app.schema_gen += 1;
        let s = setting(&app, &s.key);
        let cur = app.doc.as_ref().unwrap().value(0, s.slot());
        assert_eq!(app.locked_why(&s, 0), Some((NOT_ON_CAMERA_LOCK.to_string(), why.to_string())));
        assert!(app.locked(&s, 0) && app.locked(&s, 1), "the lists' quick check says the same, in every set");
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert_eq!((app.doc.as_ref().unwrap().value(0, s.slot()), app.status.as_str()), (cur, NOT_ON_CAMERA_LOCK));
        let row = app.web_row(0, std::slice::from_ref(&s));
        assert_eq!((row["editable"].clone(), row["locked"].as_str(), row["locked_why"].as_str()), (json!(false), Some(NOT_ON_CAMERA_LOCK), Some(why)));
        assert_eq!(answer(&mut app, "set", json!({ "target": 0, "key": s.key, "value": v })).status, 409);
        assert!(!app.cell_editable(Col::a(0), std::slice::from_ref(&s)));
        let mut b = app.doc.as_ref().unwrap().original.clone();
        b.sections[0].get_mut(s.id).unwrap().put(s.index, v).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        assert!(app.copy_row(std::slice::from_ref(&s), Col::b(0), Col::a(0)).is_empty());
        assert_eq!(app.copy_skipped.get().locked, 1, "counted, and said");
        app.apply(Vec::new());
        assert!(app.status.contains("it is view only outside Expert mode") && app.status.contains("Expert mode (⚙ Settings > Editing & Compare) copies it"), "what to do: {}", app.status);
        // the page's Compare: no arrow into A, and the row names the sets that take no copy
        let j = body!(answer(&mut app, "compare", json!({ "cols": [["b", 0], ["a", 0]], "q": s.name, "only_diff": false })));
        let row = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).expect("the row").clone();
        assert!(row["locked"].as_array().unwrap().contains(&json!(0)) && row["arrows"][0] == json!([false, false]), "{row}");
        // Expert mode changes it, and the write window lists it as not checked on the camera
        app.prefs.expert = true;
        assert!(app.locked_why(&s, 0).is_none() && app.cell_editable(Col::a(0), std::slice::from_ref(&s)));
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), Some(v));
        assert!(app.acceptance_issues().iter().any(|i| i.slot == s.slot() && i.kind == IssueKind::NotChecked));
        // the shipped definition: the parameters of the profiles no menu of the a1 II offers
        app.prefs.expert = false;
        app.open_sample_now();
        let none: Vec<&Setting> = app.schema.settings.iter().filter(|x| x.scalar && x.not_on_camera_in(0).is_some()).collect();
        assert!(none.len() >= 150 && none.iter().all(|x| app.locked_why(x, 0).is_some()), "{}", none.len());
    }

    /// Outside Expert mode a setting is changed only where a proof on the camera stands for it: one with no proof is
    /// view only, saying why in its reason's words, or, with no reason, that it has not been checked on a camera yet.
    /// In the shipped definition this locks, beyond the settings no menu writes and the copies, the five the definition
    /// gives other reasons for, and no text and no My Menu place.
    #[test]
    fn a_setting_no_proof_stands_for_is_view_only_outside_expert_mode() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let (s, _) = crate::write::safety_tests::changeable(&app);
        for x in app.schema.settings.iter_mut().filter(|x| x.key == s.key) {
            x.proved = None;
            x.unproved_reason = None;
        }
        app.schema_gen += 1;
        let s = setting(&app, &s.key);
        let (why, hover) = app.locked_why(&s, 0).expect("view only");
        assert!(why.starts_with("View only: this setting has not been checked on a camera yet") && why.ends_with("Expert mode (⚙ Settings > Editing & Compare) can change it."), "{why}");
        assert_eq!(hover, "No proof on the camera chose its values yet.");
        for (kind, words) in [("equipment", "needs equipment"), ("unknown", "what writes it is not known"), ("state", "the camera keeps for itself"), ("camera_only", "camera's own saves"), ("network", "by hand")] {
            for x in app.schema.settings.iter_mut().filter(|x| x.key == s.key) {
                x.unproved_reason = Some(camset_editor::schema::UnprovedReason { kind: kind.into(), why: format!("The {kind} reason.") });
            }
            let (why, hover) = app.locked_why(&setting(&app, &s.key), 0).unwrap();
            assert!(why.contains(words) && hover == format!("The {kind} reason."), "{kind}: {why}");
        }
        app.prefs.expert = true;
        assert!(app.locked_why(&setting(&app, &s.key), 0).is_none());
        app.prefs.expert = false;
        // the shipped definition: what this locks that a person could change before, beyond the settings no menu writes
        // and the copies; never a text or a My Menu place
        app.open_sample_now();
        let mm = app.schema.camera.my_menu.as_ref().map(|m| m.records.clone()).unwrap_or_default();
        let newly: Vec<&Setting> = app.schema.settings.iter()
            .filter(|x| !x.expert && x.copy_of.is_none() && x.not_on_camera_in(0).is_none() && x.proved.is_none())
            .filter(|x| x.text.is_some() || (x.scalar && (x.range.is_some() || x.values.len() >= 2)))
            .collect();
        assert!(newly.iter().all(|x| app.locked_why(x, 0).is_some() && x.text.is_none() && !mm.contains(&x.id)), "{:?}", newly.iter().map(|x| &x.name).collect::<Vec<_>>());
        assert!(newly.len() <= 5, "{:?}", newly.iter().map(|x| &x.name).collect::<Vec<_>>());
        assert!(app.schema.settings.iter().filter(|x| x.text.is_some() || mm.contains(&x.id)).all(|x| app.locked_why(x, 0).is_none()), "texts and My Menu places stay editable");
    }

    /// `video_system_values`, made here on a setting of the sample with the names its block gives the video systems:
    /// in the live settings a value of the other system than the file's is not offered (window and page), is refused by
    /// the page's set, is not copied by Compare (which says why), and a file holding one already is listed in the write
    /// window, with nothing to revert. In a memory set, which the camera's own files fill with either system's values,
    /// nothing is held back, refused or listed on that ground. A file whose block names no video system offers every
    /// value.
    #[test]
    fn another_video_systems_values_are_held_back_in_the_live_settings() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let sys = app.file_system().expect("the sample's block names its video system");
        let block = crate::test_block();
        let other = block.video_system.as_ref().unwrap().names.values().find(|n| **n != sys).expect("a second system").clone();
        let s = app.schema.settings.iter()
            .filter(|s| s.area == "global" && s.in_sets && s.scalar && s.text.is_none() && s.range.is_none() && s.copies.is_empty() && app.shape_ok_in(s, 0) && app.shape_ok_in(s, 1) && app.locked_why(s, 0).is_none())
            .find(|s| { let cur = app.col_value(Col::a(0), s); cur.is_some() && s.offered(false).len() >= 3 && s.offered(false).iter().any(|(v, _)| Some(*v) == cur) })
            .cloned().expect("a setting of three values or more, kept in the memories");
        let cur = app.col_value(Col::a(0), &s).unwrap();
        let mut others = s.offered(false).into_iter().map(|(v, _)| v).filter(|v| *v != cur);
        let (mine, theirs) = (others.next().unwrap(), others.next().unwrap());
        for x in app.schema.settings.iter_mut().filter(|x| x.key == s.key) {
            x.video_system_values = Some([(sys.clone(), vec![cur, mine]), (other.clone(), vec![theirs])].into_iter().collect());
        }
        app.schema_gen += 1;
        let s = setting(&app, &s.key);
        let offered: Vec<i64> = app.offered_values(&s, 0).into_iter().map(|(v, _)| v).collect();
        assert!(offered.contains(&mine) && offered.contains(&cur) && !offered.contains(&theirs), "{offered:?}");
        assert!(app.offered_values(&s, 1).iter().any(|(v, _)| *v == theirs), "a memory set offers every value");
        let row = app.web_row(0, std::slice::from_ref(&s));
        assert!(row["options"].as_array().unwrap().iter().all(|o| o[0] != json!(theirs)));
        assert!(app.web_row(1, std::slice::from_ref(&s))["options"].as_array().unwrap().iter().any(|o| o[0] == json!(theirs)));
        let r = answer(&mut app, "set", json!({ "target": 0, "key": s.key, "value": theirs }));
        let said = body!(r)["error"].as_str().unwrap_or("").to_string();
        assert_eq!(r.status, 400);
        assert!(said.starts_with("Not changed:") && said.contains(&format!("offered only with the camera set to {other}, and this file was saved with it set to {sys}")), "{said}");
        assert_eq!(answer(&mut app, "set", json!({ "target": 0, "key": s.key, "value": mine })).status, 200);
        assert_eq!(answer(&mut app, "set", json!({ "target": 1, "key": s.key, "value": theirs })).status, 200, "a memory set takes it");
        assert!(app.acceptance_issues().iter().all(|i| i.kind != IssueKind::OtherSystem), "nor is it listed there");
        // Compare: file B holds the other system's value in its live settings; it is not copied, and the status says why
        let mut b = app.doc.as_ref().unwrap().original.clone();
        b.sections[0].get_mut(s.id).unwrap().put(s.index, theirs).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        assert!(app.copy_row(std::slice::from_ref(&s), Col::b(0), Col::a(0)).is_empty());
        assert_eq!(app.copy_skipped.get().other_system, 1);
        app.apply(Vec::new());
        assert!(app.status.contains("another video system than file A was saved with"), "{}", app.status);
        // a file holding one already in its live settings: listed, unchanged, with nothing to revert
        as_opened(&mut app, |c| c.sections[0].get_mut(s.id).unwrap().put(s.index, theirs).unwrap());
        let issues = app.acceptance_issues();
        let one = issues.iter().find(|i| i.kind == IssueKind::OtherSystem).expect("listed");
        assert!(app.issue_fix(one).is_none() && one.slot == s.slot() && one.section == 0);
        // a block that says nothing of the video system: every value, as before
        let p = Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.json");
        let mut v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
        v["camera"]["file"].as_object_mut().unwrap().remove("video_system");
        let without: std::sync::Arc<camset::FileFormat> = std::sync::Arc::new(serde_json::from_value(v["camera"]["file"].clone()).unwrap());
        let c = CamSet::parse(crate::test_support::SAMPLE_BYTES, &without).unwrap();
        as_opened(&mut app, |x| *x = c.clone());
        assert!(app.file_system().is_none());
        assert!(app.offered_values(&s, 0).iter().any(|(v, _)| *v == theirs), "the video system unknown: every value");
    }

    /// What the window draws, as a screen reader is told it: each control's name, role and whether it is off.
    fn drawn(app: &mut App) -> Vec<(String, Role, bool)> {
        let ctx = egui::Context::default();
        ctx.enable_accesskit();
        let mut frame = eframe::Frame::_new_kittest();
        let mut out = Vec::new();
        for _ in 0..2 {
            let o = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame));
            out = o.platform_output.accesskit_update.map(|t| t.nodes.iter().filter_map(|(_, n)| n.label().map(|l| (l.to_string(), n.role(), n.is_disabled()))).collect()).unwrap_or_default();
        }
        out
    }

    /// The window's own controls for a view-only setting are off, and say why: the detail panel's options, the Main
    /// page's tile and its row, the My Menu page's box, the Memories page's arrows; the page's rows, tiles, My Menu rows
    /// and Memories cells say the same. A setting that may be changed keeps its controls on.
    #[test]
    fn the_views_hold_a_view_only_setting() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        // a setting of the Main page's first tiles, kept in the memories, with named values, which the sample lets change
        let pages = app.schema.camera.main_tiles.clone().expect("the a1 II's Main page");
        let s = pages.0[0].tiles.iter().filter(|t| t.keys_for(0).len() == 1).filter_map(|t| app.schema.settings.iter().find(|s| s.key == t.keys_for(0)[0]))
            .find(|s| s.in_sets && s.values.len() >= 2 && s.range.is_none() && s.option_tree().is_none() && app.tile_changes_in_place(s, 0)).cloned().expect("a tile of one setting");
        // its options but the one held now, whose words other controls show too (the row's value)
        let now = app.col_value(Col::a(0), &s);
        let options: Vec<String> = app.offered_values(&s, 0).into_iter().filter(|(v, _)| Some(*v) != now).map(|(_, l)| l).collect();
        let show = |app: &mut App| { (app.mode, app.view, app.group, app.item, app.item_key) = (Mode::Edit, View::Tab(app.layout_tab(&s).to_string()), Some(app.shown_group_of(&s)), Some(s.name.clone()), Some(s.key.clone())); };
        let off = |said: &[(String, Role, bool)], names: &[String]| -> Vec<bool> {
            said.iter().filter(|(l, r, _)| names.contains(l) && !matches!(r, Role::Label | Role::Unknown)).map(|(_, _, d)| *d).collect()
        };
        show(&mut app);
        let free = off(&drawn(&mut app), &options);
        assert!(!free.is_empty() && free.iter().all(|d| !d), "the options of a setting that may be changed are on: {free:?}");
        // the same setting with no proof: view only outside Expert mode
        for x in app.schema.settings.iter_mut().filter(|x| x.key == s.key) {
            x.proved = None;
        }
        app.schema_gen += 1;
        let s = setting(&app, &s.key);
        show(&mut app);
        let said = drawn(&mut app);
        let locked = off(&said, &options);
        assert!(!locked.is_empty() && locked.iter().all(|d| *d), "the detail panel's options are off: {:?}", said.iter().filter(|(l, r, d)| options.contains(l) && !matches!(r, Role::Label | Role::Unknown) && !d).collect::<Vec<_>>());
        // the Main page: the tile does not change in place, on the page either
        assert!(!app.tile_changes_in_place(&s, 0));
        let m = body!(answer(&mut app, "main", json!({ "target": 0, "set": 0 })));
        assert!(m["tiles"].as_array().unwrap().iter().all(|t| t["edit"]["key"] != json!(s.key)), "no tile of the page changes it");
        assert!(m["rows"].as_array().unwrap().iter().filter(|r| r["key"] == json!(s.key)).all(|r| r["editable"] == json!(false) && r["locked"].is_string()));
        app.view = View::Main;
        let said = drawn(&mut app);
        assert!(said.iter().filter(|(l, r, _)| *l == s.name && *r == Role::ComboBox).all(|(_, _, d)| *d), "the Main page's row box is off");
        // the Memories page: no arrow into the live settings or a memory, in the window and on the page
        let m1 = app.dial_sets()[0];
        as_opened(&mut app, |c| { let other = s.values.iter().map(|(v, _)| *v).find(|v| c.sections[0].get(s.id).and_then(|r| r.get(s.index)) != Some(*v)).unwrap(); c.sections[m1].get_mut(s.id).unwrap().put(s.index, other).unwrap(); });
        let page = body!(answer(&mut app, "memories", json!({ "q": s.name, "only_diff": true })));
        let cell = page["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).find(|r| r["key"] == json!(s.key)).expect("the row")["cells"][0].clone();
        assert_eq!(cell["takes"], json!([false, false]), "{cell}");
        (app.view, app.search) = (View::Memories, s.name.clone());
        let arrows = |said: &[(String, Role, bool)]| said.iter().filter(|(l, _, _)| l.starts_with("Recall") || l.contains(" into ") || l.contains("➡") || l.contains("⬅")).count();
        let locked_arrows = arrows(&drawn(&mut app));
        app.prefs.expert = true;
        let expert_arrows = arrows(&drawn(&mut app));
        assert!(expert_arrows > locked_arrows, "the window draws arrows for the row only where it may change: {locked_arrows} then {expert_arrows}");
        app.prefs.expert = false;
        // My Menu's own tab on its page, in the window and on the page
        if app.has_mymenu_page() {
            let name = app.schema.camera.text.my_menu_name().to_string();
            let own = app.settings_in(0, Some(&name)).find(|x| x.scalar && x.values.len() >= 2 && app.shape_ok_in(x, 0)).cloned();
            if let Some(own) = own {
                for x in app.schema.settings.iter_mut().filter(|x| x.key == own.key) {
                    x.proved = None;
                }
                app.schema_gen += 1;
                let j = body!(answer(&mut app, "mymenu_page", json!({ "target": 0 })));
                let mut found = Vec::new();
                fn walk(v: &serde_json::Value, key: &str, out: &mut Vec<serde_json::Value>) {
                    match v {
                        serde_json::Value::Object(m) => { if m.get("key").and_then(|k| k.as_str()) == Some(key) && m.contains_key("editable") { out.push(v.clone()); } m.values().for_each(|x| walk(x, key, out)); }
                        serde_json::Value::Array(a) => a.iter().for_each(|x| walk(x, key, out)),
                        _ => {}
                    }
                }
                walk(&j, &own.key, &mut found);
                assert!(!found.is_empty() && found.iter().all(|r| r["editable"] == json!(false) && r["locked"].is_string()), "{found:?}");
                (app.view, app.search) = (View::MyMenu, String::new());
                let said = drawn(&mut app);
                let boxes: Vec<bool> = said.iter().filter(|(l, r, _)| *l == own.name && *r == Role::ComboBox).map(|(_, _, d)| *d).collect();
                assert!(!boxes.is_empty() && boxes.iter().all(|d| *d), "My Menu's box for it is off: {boxes:?}");
            }
        }
    }
}
