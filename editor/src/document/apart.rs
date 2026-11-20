//! A switch of the camera's own that keeps a family's copies apart (`Setting::keeps_apart`: a Different Set for Still/Mv
//! box whose effect on the copies a proof showed). While the switch keeps them apart, the family's rows say what the
//! camera did then, and that the editor does not follow it (`apart_note`, said with `copy_note`). Before such a switch is
//! changed in a file to a value that does not keep them apart (a box unticked), the window and the page say what that
//! change did on the camera and offer to do the same, or to change the switch alone (`untick_ask`; the window's
//! `untick_window`, the page's requests through `web_untick`). What the camera does on loading a file whose switch was
//! changed alone is not known, so the editor never decides it silently. Everything here comes from the definition: the
//! editor knows no switch, family or value by name, and names each value by the definition's own label
//! (docs/decisions/0020).

use crate::*;

/// The choice that does as the camera did: the switch and each family it keeps apart at the definition's value, in one
/// step.
pub(crate) const UNTICK_AS_CAMERA: &str = "Do as the camera does";
/// The choice that changes the switch alone, leaving the values the file holds.
pub(crate) const UNTICK_THIS_ONLY: &str = "Change this setting only";

/// The question before a switch leaves the values that keep a family apart in a file (`App::untick_ask`): its title and
/// words, each choice's hover and Cancel's, the switch's name and its value now and to come (named), the switch's own
/// change (set, place, value), what "Do as the camera does" sets besides (set, place, value) and the keys of those
/// settings, and why that choice cannot be made here, if so (a setting it would set is view only, or does not offer the
/// value).
pub(crate) struct UntickAsk {
    pub(crate) title: String,
    pub(crate) words: String,
    pub(crate) camera_hover: String,
    pub(crate) alone_hover: String,
    pub(crate) cancel_hover: String,
    pub(crate) switch: String,
    pub(crate) now_label: String,
    pub(crate) to_label: String,
    pub(crate) to: (usize, Slot, i64),
    pub(crate) sets: Vec<(usize, Slot, i64)>,
    pub(crate) keys: Vec<String>,
    pub(crate) blocked: Option<String>,
}

impl UntickAsk {
    /// The changes "Do as the camera does" makes besides the switch's own.
    pub(crate) fn camera_actions(&self) -> Vec<Action> {
        self.sets.iter().map(|&(si, slot, v)| Action::Set(si, slot, v)).collect()
    }

    /// The question as the page draws it: its title and words, the name of the field its answer goes back in, each
    /// choice as [its words, the answer, its hover, why it cannot be chosen or null], and Cancel's hover.
    pub(crate) fn web(&self) -> serde_json::Value {
        serde_json::json!({ "title": self.title, "text": self.words, "field": "untick",
            "choices": [[UNTICK_AS_CAMERA, "camera", self.camera_hover, self.blocked], [UNTICK_THIS_ONLY, "box", self.alone_hover, null]],
            "cancel": self.cancel_hover })
    }
}

/// The window's question while it waits for its answer: the question, the changes asked for, the file's state then
/// (`Doc::rev`), so an answer to a question about a file since changed changes nothing, and what a copy of several rows
/// at once had told `apply` (`rows_copied`, `rows_set`, `copy_skipped`), given back to it with the answer.
pub(crate) struct UntickPending {
    pub(crate) ask: UntickAsk,
    pub(crate) actions: Vec<Action>,
    pub(crate) rev: u64,
    pub(crate) copied: Option<Option<usize>>,
    pub(crate) rows_set: Vec<(usize, Slot)>,
    pub(crate) skipped: Left,
}

/// Names in a sentence, the last after "or": "A", "A or B", "A, B or C".
pub(crate) fn or_list(names: &[String]) -> String {
    match names {
        [] => String::new(),
        [one] => one.clone(),
        [rest @ .., last] => format!("{} or {last}", rest.join(", ")),
    }
}

impl App {
    /// The family a switch's entry keeps apart (`KeepsApart::setting`), when the definition names it with copies: the
    /// family's setting, then each copy the definition names.
    fn family_of_entry(&self, k: &camset_editor::schema::KeepsApart) -> Option<Vec<&Setting>> {
        let fam = &self.schema.settings[self.index_of_key(&k.setting)?];
        if fam.copies.is_empty() {
            return None;
        }
        Some(std::iter::once(fam).chain(fam.copies.iter().filter_map(|c| self.index_of_key(c).map(|i| &self.schema.settings[i]))).collect())
    }

    /// The switch that keeps setting `s`'s family apart (`keeps_apart`; `s` the family's setting or one of its copies),
    /// with its entry, the family's setting and the copies: the first the definition names.
    pub(crate) fn switch_of(&self, s: &Setting) -> Option<(&Setting, &camset_editor::schema::KeepsApart, &Setting, Vec<&Setting>)> {
        let fam = if s.copies.is_empty() { self.main_of(s)? } else { s };
        self.schema.settings.iter().find_map(|sw| sw.keeps_apart.iter().find(|k| k.setting == fam.key).map(|k| (sw, k)))
            .and_then(|(sw, k)| {
                let all = self.family_of_entry(k)?;
                Some((sw, k, all[0], all[1..].to_vec()))
            })
    }

    /// What a row says beside a setting whose family a switch keeps apart (`keeps_apart`; the family's setting or one of
    /// its copies), in set `section`, while the switch holds a value that keeps it apart there (one of `apart`; a set the
    /// switch is kept in only): what a change made on the camera then did, and that the editor does not follow the
    /// switch (what changes with an edit here is the copies rule, `copy_note`). None for any other setting, or where
    /// the switch shares the family's values, or the file does not hold it.
    pub(crate) fn apart_note(&self, s: &Setting, section: usize) -> Option<String> {
        let d = self.doc.as_ref()?;
        let (sw, k, fam, copies) = self.switch_of(s)?;
        let now = d.value(section, sw.slot())?;
        if !kept_in(sw, section) || !kept_in(fam, section) || !k.apart.contains(&now) {
            return None;
        }
        let copies: Vec<String> = copies.iter().filter(|c| kept_in(c, section)).map(|c| c.name.clone()).collect();
        if copies.is_empty() {
            return None;
        }
        Some(format!("{} is {} in this file: when this was tried on the camera, a change of {} then changed only the copy for the shooting mode it was made in, {}. The editor does not follow that setting: here the copies that held {}'s value when this file was opened or read change with it.",
            sw.name, Self::label(sw, now), fam.name, or_list(&copies), fam.name))
    }

    /// Value `v` of setting `s` named as the editor names it (`describe`), for a sentence: no space left after a number
    /// shown with no unit.
    fn label(s: &Setting, v: i64) -> String {
        Self::describe(s, Some(v)).trim().to_string()
    }

    /// Whether setting `p` takes value `v` in set `section` as an edit here would: a number of its range on its step,
    /// else one of the values offered there (`offered_values`), and never one of another video system than the file's.
    fn takes_value(&self, p: &Setting, v: i64, section: usize) -> bool {
        let offered = match p.range {
            Some((lo, hi)) => (lo..=hi).contains(&v) && (v - lo) % p.step.unwrap_or(1).max(1) == 0,
            None => self.offered_values(p, section).iter().any(|(o, _)| *o == v),
        };
        offered && self.other_system_words(p, v, section).is_none()
    }

    /// The question to ask before `actions` are made, where one of them changes a switch (`keeps_apart` with
    /// `untick_sets`) from a value that keeps a family apart to one that does not (a box unticked): a Set of the
    /// switch's place, or a record put back whole (the History window's Revert), in a set the switch is kept in, while
    /// the family's setting or a copy there holds another value than the one the camera gave them then. None for
    /// anything else (a Revert of the switch is not asked: it puts back the file as opened). A copy of several rows at
    /// once (`pin_families`) asks only where its own rows do not set every place of the family the file holds: then
    /// they bring the family from the other file. What "Do as the camera does" adds is each such family's setting and
    /// copies, those the file holds there, at that value; it is blocked (with why) where the switch or one of those
    /// settings is view only here, or one of them does not take the value (`takes_value`).
    pub(crate) fn untick_ask(&self, actions: &[Action]) -> Option<UntickAsk> {
        let d = self.doc.as_ref()?;
        let copied = self.rows_copied.get().is_some();
        let rows_set = self.rows_set.borrow();
        // each switch these actions change: its set, the switch, the value to come
        let mut changes: Vec<(usize, &Setting, i64)> = Vec::new();
        for a in actions {
            match a {
                Action::Set(si, slot, v) => changes.extend(self.schema.settings.iter().filter(|s| s.slot() == *slot && !s.keeps_apart.is_empty()).map(|s| (*si, s, *v))),
                Action::SetRecord(si, rec) => changes.extend(self.schema.settings.iter().filter(|s| s.id == rec.id && !s.keeps_apart.is_empty())
                    .filter_map(|s| rec.get(s.index).map(|v| (*si, s, v)))),
                _ => {}
            }
        }
        for (si, sw, v) in changes {
            let Some(now) = d.value(si, sw.slot()).filter(|_| kept_in(sw, si)) else { continue };
            // what the camera set, said three ways: "A to Auto, in A1 and A2 too" (the question), "A, A1 and A2 to Auto"
            // (its first choice), and every name (its second)
            let (mut sets, mut keys, mut parts, mut to, mut names_all, mut blocked) = (Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new(), None);
            for k in sw.keeps_apart.iter().filter(|k| k.apart.contains(&now) && !k.apart.contains(&v)) {
                let (Some(code), Some(all)) = (k.untick_sets, self.family_of_entry(k)) else { continue };
                let held: Vec<&Setting> = all.into_iter().filter(|p| kept_in(p, si) && d.value(si, p.slot()).is_some()).collect();
                if held.len() < 2 || held[0].key != k.setting || held.iter().all(|p| d.value(si, p.slot()) == Some(code)) {
                    continue;
                }
                if copied && held.iter().all(|p| rows_set.contains(&(si, p.slot()))) {
                    continue;
                }
                let value = Self::label(held[0], code);
                for p in &held {
                    sets.push((si, p.slot(), code));
                    keys.push(p.key.clone());
                    if blocked.is_none() && (self.locked(p, si) || !self.shape_ok_in(p, si)) {
                        blocked = Some(format!("Not changed: {} is view only here, so the editor cannot set it as the camera did. {UNTICK_THIS_ONLY} changes {} alone; Expert mode (⚙ Settings > Editing & Compare) can change it.", p.name, sw.name));
                    } else if blocked.is_none() && !self.takes_value(p, code, si) {
                        blocked = Some(format!("Not changed: {} does not take {value} in this file, so the editor cannot set it as the camera did. {UNTICK_THIS_ONLY} changes {} alone.", p.name, sw.name));
                    }
                }
                let names: Vec<String> = held.iter().map(|p| p.name.clone()).collect();
                parts.push(format!("{} to {value}, in {} too", names[0], and_list(&names[1..])));
                to.push(format!("{} to {value}", and_list(&names)));
                names_all.extend(names);
            }
            if sets.is_empty() {
                continue;
            }
            if self.locked(sw, si) {
                blocked = Some(format!("Not changed: {} is view only here, so the editor cannot change it as the camera did. Expert mode (⚙ Settings > Editing & Compare) can change it.", sw.name));
            }
            let (now_label, to_label) = (Self::label(sw, now), Self::label(sw, v));
            return Some(UntickAsk {
                title: format!("Set {} to {to_label}?", sw.name),
                words: format!("When this was tried on the camera, setting {} to {to_label} also set {}. If only {} changes here, this file keeps values that this change on the camera does not leave, and what the camera does when it loads such a file is not known.", sw.name, and_list(&parts), sw.name),
                camera_hover: format!("Sets {} to {to_label}, and {} as the camera did, in one step: one Undo takes it all back.", sw.name, and_list(&to)),
                alone_hover: format!("Sets {} to {to_label} and leaves {} as this file holds them.", sw.name, and_list(&names_all)),
                cancel_hover: format!("Leaves {} at {now_label}: nothing is changed.", sw.name),
                switch: sw.name.clone(),
                now_label,
                to_label,
                to: (si, sw.slot(), v),
                sets,
                keys,
                blocked,
            });
        }
        None
    }

    /// `actions`, the answer to an untick question (`ask`), made as one new undo step: with `like_camera` the families at
    /// the camera's value too. Returns why nothing was changed, said on the status line too: that choice blocked
    /// (`UntickAsk::blocked`), `apply`'s refusal, or a step that did not leave the switch and every place the camera's
    /// way sets at their values (a change `apply` left out). That step is taken back whole: the file as it was, the
    /// undo history as it was (the oldest step `apply` let go of at the limit, `UNDO_LIMIT`, put back), the redo the
    /// person had, and no edit for the next one to join.
    pub(crate) fn apply_untick(&mut self, mut actions: Vec<Action>, ask: &UntickAsk, like_camera: bool) -> Option<String> {
        if like_camera {
            if let Some(why) = &ask.blocked {
                // nothing is made: what a copy of several rows at once told `apply` is let go with it
                self.rows_copied.take();
                self.rows_set.take();
                self.copy_skipped.take();
                self.status = why.clone();
                return Some(why.clone());
            }
            actions.extend(ask.camera_actions());
        }
        self.last_edit = None;
        let before = self.doc.as_ref()?.edited.clone();
        let (redo, first) = (self.redo.clone(), (self.undo.len() >= UNDO_LIMIT).then(|| self.undo[0].clone()));
        if let Some(why) = self.apply(actions) {
            return Some(why);
        }
        let d = self.doc.as_mut()?;
        let (si, slot, v) = ask.to;
        let made = d.value(si, slot) == Some(v) && (!like_camera || ask.sets.iter().all(|&(si, slot, c)| d.value(si, slot) == Some(c)));
        if made {
            return None;
        }
        if before.sections.iter().zip(&d.edited.sections).any(|(a, b)| a.records != b.records) {
            self.undo.pop();
            if let Some(f) = first {
                self.undo.insert(0, f);
            }
        }
        d.edited = before;
        d.rev = next_open();
        self.redo = redo;
        self.last_edit = None;
        let why = format!("Not changed: the editor could not make every change setting {} to {} makes on the camera, so it kept none of them.", ask.switch, ask.to_label);
        self.status = why.clone();
        Some(why)
    }

    /// The window's changes of one frame, less those a question holds back: where they change a switch as `untick_ask`
    /// asks about, all of them wait for the answer (`untick_window`), with what a copy of several rows at once told
    /// `apply`, and nothing is changed meanwhile.
    pub(crate) fn hold_untick(&mut self, actions: Vec<Action>) -> Vec<Action> {
        let Some(ask) = self.untick_ask(&actions) else { return actions };
        let rev = self.doc.as_ref().map_or(0, |d| d.rev);
        let (copied, rows_set, skipped) = (self.rows_copied.take(), self.rows_set.take(), self.copy_skipped.take());
        self.copy_shown.take();
        self.untick_pending = Some(UntickPending { ask, actions, rev, copied, rows_set, skipped });
        Vec::new()
    }

    /// The answer to the window's question: as the camera did (`Some(true)`: the switch and its families, one undo
    /// step), this setting only (`Some(false)`), or Cancel (`None`: nothing changed). A choice that cannot be made here
    /// (`UntickAsk::blocked`) leaves the question open and says why. Nothing is changed where the file changed since the
    /// question was asked, nor where the step could not be made whole (`apply_untick`); the status line says why.
    pub(crate) fn answer_untick(&mut self, camera: Option<bool>) {
        let Some(p) = self.untick_pending.take() else { return };
        if self.doc.as_ref().map(|d| d.rev) != Some(p.rev) {
            self.status = format!("Not changed: the file changed while the question about {} was open. Change it again.", p.ask.switch);
            return;
        }
        let Some(like_camera) = camera else {
            self.status = format!("Not changed: {} stays at {}.", p.ask.switch, p.ask.now_label);
            return;
        };
        if like_camera && p.ask.blocked.is_some() {
            self.status = p.ask.blocked.clone().unwrap_or_default();
            self.untick_pending = Some(p);
            return;
        }
        self.rows_copied.set(p.copied);
        *self.rows_set.borrow_mut() = p.rows_set;
        self.copy_skipped.set(p.skipped);
        if self.apply_untick(p.actions, &p.ask, like_camera).is_none() {
            self.status = format!("{} set to {}{}", p.ask.switch, p.ask.to_label, if like_camera { ", as on the camera" } else { "; the other values stay as they were" });
        }
    }

    /// The window's question before a switch leaves the values that keep a family apart (`untick_pending`): what that
    /// change did on the camera, and the two ways to go on, or Cancel. "Do as the camera does" is greyed out, saying
    /// why on hover, where it cannot be made here.
    pub(crate) fn untick_window(&mut self, ctx: &egui::Context) {
        let Some(p) = &self.untick_pending else { return };
        let (title, words) = (p.ask.title.clone(), p.ask.words.clone());
        let (camera_hover, alone_hover, cancel_hover) = (p.ask.camera_hover.clone(), p.ask.alone_hover.clone(), p.ask.cancel_hover.clone());
        let blocked = p.ask.blocked.clone();
        let mut answer: Option<Option<bool>> = None;
        egui::Window::new(title).collapsible(false).resizable(false).default_width(560.0).anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0]).show(ctx, |ui| {
            ui.add(egui::Label::new(words).wrap());
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                let camera = ui.add_enabled(blocked.is_none(), egui::Button::new(UNTICK_AS_CAMERA)).on_hover_text(camera_hover);
                if camera.on_disabled_hover_text(blocked.unwrap_or_default()).clicked() {
                    answer = Some(Some(true));
                }
                if ui.button(UNTICK_THIS_ONLY).on_hover_text(alone_hover).clicked() {
                    answer = Some(Some(false));
                }
                if ui.button("Cancel").on_hover_text(cancel_hover).clicked() {
                    answer = Some(None);
                }
            });
        });
        if let Some(a) = answer {
            self.answer_untick(a);
        }
    }
}

/// A switch that keeps copies apart (`keeps_apart`), made here on the sample: the question before it leaves the value
/// that keeps a family apart (a box unticked), in the window and on the page, from every way a change reaches it, its
/// two answers and Cancel, the answer refused where it cannot be made whole, and what the family's rows say meanwhile.
#[cfg(test)]
mod apart_tests {
    use super::*;
    use crate::document::edits::copies_tests::{as_opened, held, setting, with_copies, with_modes, MAIN, MOVIE, STILLS};
    use crate::web::tests::answer;
    use egui::accesskit::Role;
    use serde_json::json;

    /// What the editor answered the page, as JSON.
    fn body(bytes: &[u8]) -> serde_json::Value {
        serde_json::from_slice(bytes).unwrap()
    }

    /// The page's request `name` asked as the page asks it: first without an answer (the editor must ask), then again
    /// with `choice` and the file's state the question was asked of (`ask_rev`), as the page's script sends it back.
    /// Returns the second answer's status and body.
    fn answered(app: &mut App, name: &str, request: serde_json::Value, choice: &str) -> (u16, serde_json::Value) {
        let first = answer(app, name, request.clone());
        let j = body(&first.body);
        assert!(j.get("ask").is_some(), "{name} asks first: {j}");
        let mut again = request;
        again["untick"] = json!(choice);
        again["ask_rev"] = j["ask"]["rev"].clone();
        let r = answer(app, name, again);
        (r.status, body(&r.body))
    }

    /// The sample with the copies made in `copies_tests` (a setting and its stills and movie copies, holding `v`,
    /// `stills` and `movie` as the file was opened, the stills copy the first mode's and the file saved in it), and a
    /// switch made here: a setting of two values (one the memories keep too with `in_sets`), which keeps that family
    /// apart with its second value and leaving it sets the family to 0, held as the file was opened at its second value
    /// (`ticked`) or its first. Every other switch the definition names is taken out. Returns the app, the family, the
    /// switch, and its two values (the first, the second).
    fn with_switch_kept(v: i64, stills: i64, movie: i64, ticked: bool, in_sets: bool) -> (App, [Setting; 3], Setting, (i64, i64)) {
        let (mut app, _) = with_copies(v, stills, movie);
        with_modes(&mut app, true);
        let live = app.schema.camera.live_mode.as_ref().map(|m| m.key.clone()).unwrap_or_default();
        let m = app.dial_sets()[0];
        let sw = app.schema.settings.iter().find(|s| s.area == "global" && s.in_sets == in_sets && s.scalar && s.values.len() == 2 && s.proved.is_some()
            && s.copies.is_empty() && s.copy_of.is_none() && s.index.is_none() && s.text.is_none() && s.range.is_none() && s.key != live
            && app.shape_ok_in(s, 0) && app.doc.as_ref().unwrap().value(0, s.slot()).is_some()
            && (!in_sets || app.shape_ok_in(s, m) && app.memory_rows().iter().any(|r| r.2.iter().any(|x| x.key == s.key)))).cloned().expect("a setting of two values");
        let (off, on) = (sw.values[0].0, sw.values[1].0);
        for s in app.schema.settings.iter_mut() {
            s.keeps_apart = if s.key == sw.key { vec![camset_editor::schema::KeepsApart { setting: MAIN.into(), apart: vec![on], untick_sets: Some(0) }] } else { Vec::new() };
        }
        app.schema_gen += 1;
        as_opened(&mut app, |c| c.sections[0].get_mut(sw.id).unwrap().put(sw.index, if ticked { on } else { off }).unwrap());
        let three = [setting(&app, MAIN), setting(&app, STILLS), setting(&app, MOVIE)];
        let sw = setting(&app, &sw.key);
        (app, three, sw, (off, on))
    }

    /// `with_switch_kept` with a switch the memories do not keep.
    fn with_switch(v: i64, stills: i64, movie: i64, ticked: bool) -> (App, [Setting; 3], Setting, (i64, i64)) {
        with_switch_kept(v, stills, movie, ticked, false)
    }

    fn switch_now(app: &App, sw: &Setting) -> Option<i64> {
        app.doc.as_ref().unwrap().value(0, sw.slot())
    }

    /// A value named as the question names it.
    fn named(s: &Setting, v: i64) -> String {
        App::describe(s, Some(v)).trim().to_string()
    }

    /// The question's words, as the window and the page show them, for the switch set to `off`.
    fn words(sw: &Setting, three: &[Setting; 3], off: i64) -> String {
        format!("When this was tried on the camera, setting {} to {} also set {} to {}, in {} and {} too. If only {} changes here, this file keeps values that this change on the camera does not leave, and what the camera does when it loads such a file is not known.",
            sw.name, named(sw, off), three[0].name, named(&three[0], 0), three[1].name, three[2].name, sw.name)
    }

    /// The window's controls as a screen reader is told them, over two frames of the question: (name, role, off).
    fn window_controls(app: &mut App) -> Vec<(String, Role, bool)> {
        let ctx = egui::Context::default();
        ctx.enable_accesskit();
        let mut said = Vec::new();
        for _ in 0..2 {
            let o = ctx.run(egui::RawInput::default(), |ctx| app.untick_window(ctx));
            said = o.platform_output.accesskit_update.map(|t| t.nodes.iter().filter_map(|(_, n)| n.label().map(|l| (l.to_string(), n.role(), n.is_disabled()))).collect::<Vec<_>>()).unwrap_or_default();
        }
        said
    }

    /// A step "Do as the camera does" cannot make whole: the question as asked, with one more place to set that the
    /// file does not hold, so `apply` leaves it out.
    fn shortfall(app: &mut App, sw: &Setting, off: i64) -> Option<String> {
        let mut ask = app.untick_ask(&[Action::Set(0, sw.slot(), off)]).unwrap();
        ask.sets.push((0, (0xfffe, None), 1));
        app.apply_untick(vec![Action::Set(0, sw.slot(), off)], &ask, true)
    }

    /// Leaving the switch's value in the window asks first, and nothing changes until the answer: "Do as the camera
    /// does" sets the switch and the family in one undo step; "Change this setting only" sets the switch alone; Cancel
    /// changes nothing. Taking the value that keeps the family apart, a Revert, a family already at the camera's value
    /// and an entry with no such value ask nothing; Expert mode asks too; an answer to a question about a file since
    /// changed changes nothing. The window draws the question with its three buttons, every word from the definition,
    /// a number with no unit named with no space after it.
    #[test]
    fn leaving_the_switchs_value_asks_first_then_does_as_the_camera_or_this_setting_only() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        let ask = app.untick_ask(&[Action::Set(0, sw.slot(), off)]).expect("a question");
        assert_eq!(ask.title, format!("Set {} to {}?", sw.name, named(&sw, off)));
        assert_eq!(ask.words, words(&sw, &three, off));
        assert!(!ask.words.contains(" ,") && !ask.camera_hover.contains("  "), "{}", ask.words);
        assert_eq!(ask.camera_hover, format!("Sets {} to {}, and {}, {} and {} to {} as the camera did, in one step: one Undo takes it all back.", sw.name, named(&sw, off), three[0].name, three[1].name, three[2].name, named(&three[0], 0)));
        assert_eq!(ask.alone_hover, format!("Sets {} to {} and leaves {}, {} and {} as this file holds them.", sw.name, named(&sw, off), three[0].name, three[1].name, three[2].name));
        assert_eq!(ask.cancel_hover, format!("Leaves {} at {}: nothing is changed.", sw.name, named(&sw, on)));
        assert_eq!((ask.keys.clone(), ask.blocked.is_none()), (vec![MAIN.to_string(), STILLS.to_string(), MOVIE.to_string()], true));
        // the window: held back, nothing changed, until the answer
        assert!(app.hold_untick(vec![Action::Set(0, sw.slot(), off)]).is_empty());
        assert!(app.untick_pending.is_some() && app.undo.is_empty() && switch_now(&app, &sw) == Some(on));
        let said = window_controls(&mut app);
        for b in [UNTICK_AS_CAMERA, UNTICK_THIS_ONLY, "Cancel"] {
            assert!(said.iter().any(|(l, r, off)| l == b && *r == Role::Button && !off), "{b}: {said:?}");
        }
        assert!(app.untick_pending.is_some(), "drawing it answers nothing");
        // as the camera does: the switch and the family, one step
        app.answer_untick(Some(true));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(0); 3]));
        assert_eq!((app.undo.len(), app.untick_pending.is_none()), (1, true));
        assert_eq!(app.status, format!("{} set to {}, as on the camera", sw.name, named(&sw, off)));
        assert_eq!(held(&app, &three, 1), [Some(3), Some(3), Some(5)], "a memory set keeps its own");
        app.undo();
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(on), [Some(3), Some(3), Some(5)]));
        // this setting only
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.answer_untick(Some(false));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(off), [Some(3), Some(3), Some(5)], 1));
        app.undo();
        // Cancel
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.answer_untick(None);
        assert_eq!((switch_now(&app, &sw), app.undo.len()), (Some(on), 0));
        assert_eq!(app.status, format!("Not changed: {} stays at {}.", sw.name, named(&sw, on)));
        // a file changed while the question was open: the answer changes nothing
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.apply(vec![Action::Set(0, three[0].slot(), 4)]);
        let steps = app.undo.len();
        app.answer_untick(Some(true));
        assert_eq!((switch_now(&app, &sw), app.undo.len()), (Some(on), steps));
        assert!(app.status.starts_with("Not changed: the file changed while the question"), "{}", app.status);
        app.undo();
        // Expert mode asks too
        app.prefs.expert = true;
        assert!(app.untick_ask(&[Action::Set(0, sw.slot(), off)]).is_some());
        app.prefs.expert = false;
        // nothing to ask: taking the value that keeps it apart, a Revert, the same value, the switch already there
        let (app2, _, sw2, (off2, on2)) = with_switch(3, 3, 5, false);
        assert!(app2.untick_ask(&[Action::Set(0, sw2.slot(), on2)]).is_none(), "the value that keeps it apart: the switch alone, as on the camera");
        assert!(app.untick_ask(&[Action::Revert(0, sw.slot())]).is_none() && app.untick_ask(&[Action::Set(0, sw.slot(), on)]).is_none());
        assert!(app2.untick_ask(&[Action::Set(0, sw2.slot(), off2)]).is_none(), "already at that value");
        // the family already at the camera's value, or no such value given: nothing to ask, the switch changes alone
        let (app3, _, sw3, (off3, _)) = with_switch(0, 0, 0, true);
        assert!(app3.untick_ask(&[Action::Set(0, sw3.slot(), off3)]).is_none());
        for s in app.schema.settings.iter_mut().filter(|s| s.key == sw.key) {
            s.keeps_apart[0].untick_sets = None;
        }
        app.schema_gen += 1;
        assert!(app.untick_ask(&[Action::Set(0, sw.slot(), off)]).is_none());
        assert_eq!(app.hold_untick(vec![Action::Set(0, sw.slot(), off)]).len(), 1, "made at once");
    }

    /// An answer is a step of its own (the reviewer's mutant N18): made right after an edit of the same place, it is
    /// never joined to that edit, so one Undo takes back the answer alone.
    #[test]
    fn an_answer_is_never_joined_to_the_edit_before_it() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, false);
        app.apply(vec![Action::Set(0, sw.slot(), on)]);
        assert!(app.last_edit.is_some(), "an edit the next of the same place could join");
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.answer_untick(Some(false));
        assert_eq!((switch_now(&app, &sw), app.undo.len()), (Some(off), 2));
        app.undo();
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(on), [Some(3), Some(3), Some(5)]));
    }

    /// The page asks the same question, with the same words and the file's state, and changes nothing until the answer
    /// comes back in `untick` with that state: "camera" sets the switch and the family in one step, the family's rows
    /// coming with the reply; "box" sets the switch alone; an answer the question does not offer, and one with no state
    /// or another, are refused. A copy of the switch's row from file B asks too.
    #[test]
    fn the_page_asks_the_same_question() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        let set = json!({ "target": 0, "key": sw.key, "value": off });
        let r = answer(&mut app, "set", set.clone());
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        let j = body(&r.body);
        assert_eq!((j["ask"]["title"].clone(), j["ask"]["text"].clone(), j["ask"]["field"].clone()), (json!(format!("Set {} to {}?", sw.name, named(&sw, off))), json!(words(&sw, &three, off)), json!("untick")));
        assert_eq!(j["ask"]["rev"], json!(app.ask_rev()), "the file's state the question is asked of");
        let choices: Vec<(String, String, serde_json::Value)> = j["ask"]["choices"].as_array().unwrap().iter().map(|c| (c[0].as_str().unwrap().to_string(), c[1].as_str().unwrap().to_string(), c[3].clone())).collect();
        assert_eq!(choices, vec![(UNTICK_AS_CAMERA.to_string(), "camera".to_string(), json!(null)), (UNTICK_THIS_ONLY.to_string(), "box".to_string(), json!(null))]);
        assert_eq!(j["ask"]["cancel"], json!(format!("Leaves {} at {}: nothing is changed.", sw.name, named(&sw, on))));
        assert_eq!((j["row"]["key"].clone(), j["value"].clone()), (json!(sw.key), json!(on)), "the row as it still is, for the page to put its control back");
        assert_eq!((switch_now(&app, &sw), app.undo.len()), (Some(on), 0), "nothing changed");
        assert!(app.untick_pending.is_none(), "the window asks nothing of a question the page asked");
        // an answer with no state, or another's, is refused
        let mut stale = set.clone();
        stale["untick"] = json!("camera");
        assert_eq!(answer(&mut app, "set", stale.clone()).status, 409);
        stale["ask_rev"] = json!("0");
        assert_eq!((answer(&mut app, "set", stale).status, switch_now(&app, &sw)), (409, Some(on)));
        // "camera"
        let (status, j) = answered(&mut app, "set", set.clone(), "camera");
        assert_eq!(status, 200, "{j}");
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(off), [Some(0); 3], 1));
        let keys: Vec<String> = j["rows"].as_array().unwrap().iter().map(|x| x["key"].as_str().unwrap_or("").to_string()).collect();
        assert!([MAIN, STILLS, MOVIE].iter().all(|k| keys.contains(&k.to_string())), "the family's rows come with the reply: {keys:?}");
        app.undo();
        // "box", and an answer it does not offer
        assert_eq!(answered(&mut app, "set", set.clone(), "box").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(3), Some(3), Some(5)]));
        app.undo();
        assert_eq!(answered(&mut app, "set", set.clone(), "both").0, 409);
        // a copy of the switch's row from file B, where it is at the other value
        let mut b = app.doc.as_ref().unwrap().original.clone();
        b.sections[0].get_mut(sw.id).unwrap().put(sw.index, off).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        let copy = json!({ "from": ["b", 0], "to": ["a", 0], "key": sw.key });
        let r = answer(&mut app, "copy", copy.clone());
        assert_eq!((body(&r.body)["ask"]["text"].clone(), switch_now(&app, &sw)), (json!(words(&sw, &three, off)), Some(on)));
        assert_eq!(answered(&mut app, "copy", copy, "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(off), [Some(0); 3], 1));
    }

    /// "Do as the camera does" is refused, nothing changed, where a setting it would set is view only here: the
    /// window greys the button out, says why on hover, and keeps the question open (an answer given all the same is
    /// refused, and the question stays); "Change this setting only" still unticks it alone; the page sends the choice
    /// with its reason, and refuses it in the same words.
    #[test]
    fn the_camera_choice_is_refused_where_a_family_member_is_view_only() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        for s in app.schema.settings.iter_mut().filter(|s| s.key == MOVIE) {
            s.proved = None;
        }
        app.schema_gen += 1;
        let why = format!("Not changed: {} is view only here, so the editor cannot set it as the camera did. {UNTICK_THIS_ONLY} changes {} alone; Expert mode (⚙ Settings > Editing & Compare) can change it.", three[2].name, sw.name);
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        let said = window_controls(&mut app);
        assert!(said.iter().any(|(l, r, off)| l == UNTICK_AS_CAMERA && *r == Role::Button && *off), "greyed out: {said:?}");
        assert!(said.iter().any(|(l, _, off)| l == UNTICK_THIS_ONLY && !off));
        app.answer_untick(Some(true));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(on), [Some(3), Some(3), Some(5)], 0));
        assert_eq!((app.status.as_str(), app.untick_pending.is_some()), (why.as_str(), true), "the question stays open");
        app.answer_untick(Some(false));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(3), Some(3), Some(5)]));
        app.undo();
        // the page
        let set = json!({ "target": 0, "key": sw.key, "value": off });
        let j = body(&answer(&mut app, "set", set.clone()).body);
        assert_eq!(j["ask"]["choices"][0][3], json!(why), "the page greys the choice out, with its reason");
        let (status, j) = answered(&mut app, "set", set, "camera");
        assert_eq!((status, j["error"].clone()), (409, json!(why)));
        assert_eq!((switch_now(&app, &sw), app.undo.len()), (Some(on), 0));
    }

    /// The reviewer's probes 1 and 11: a copy of several rows at once asks first where its rows set the switch but not
    /// its whole family, on the page as in the window, and its answer makes the copy; where its rows cover the whole
    /// family (each place set to the other file's value or holding it already), nothing is asked. What the copy told
    /// `apply` is let go with the question, and once the step is made (mutant N7). The window's answer gives that back
    /// to `apply` (mutant N9): a step the copies rule refuses says so as a copy does.
    #[test]
    fn a_copy_of_rows_that_leaves_the_family_behind_asks_first() {
        let (mut app, three, sw, (off, on)) = with_switch(7, 7, 5, true);
        let mut b = app.doc.as_ref().unwrap().original.clone();
        b.sections[0].get_mut(sw.id).unwrap().put(sw.index, off).unwrap();
        for (s, v) in three.iter().zip([7, 7, 7]) {
            b.sections[0].get_mut(s.id).unwrap().put(s.index, v).unwrap();
        }
        app.compare = Some((PathBuf::from("B.DAT"), b));
        let rows = |keys: &[&str]| json!({ "from": ["b", 0], "to": ["a", 0], "keys": keys });
        let r = answer(&mut app, "copy_rows", rows(&[&sw.key]));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!((body(&r.body)["ask"]["text"].clone(), switch_now(&app, &sw), app.undo.len()), (json!(words(&sw, &three, off)), Some(on), 0));
        assert!(app.rows_copied.get().is_none() && app.rows_set.borrow().is_empty(), "nothing left for the next step");
        assert_eq!(answered(&mut app, "copy_rows", rows(&[&sw.key]), "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(off), [Some(0); 3], 1));
        assert!(app.rows_set.borrow().is_empty(), "the step made lets go of what the copy covered");
        app.undo();
        // some of the family's rows only: asks
        assert!(body(&answer(&mut app, "copy_rows", rows(&[&sw.key, MOVIE])).body).get("ask").is_some());
        // the whole family's rows, two places holding B's value already: no question, each takes B's value
        let r = answer(&mut app, "copy_rows", rows(&[&sw.key, MAIN, STILLS, MOVIE]));
        assert!(r.status == 200 && body(&r.body).get("ask").is_none(), "{}", String::from_utf8_lossy(&r.body));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(7); 3]));
        app.undo();
        // the window: the same copy, made by its views, waits for the answer, and the answer makes it as a copy
        let mut acts = app.copy_row(std::slice::from_ref(&sw), Col::b(0), Col::a(0));
        app.pin_families(None, 0, &mut acts);
        assert!(app.hold_untick(acts).is_empty() && app.untick_pending.is_some());
        app.apply(Vec::new());
        app.answer_untick(Some(false));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(off), [Some(7), Some(7), Some(5)], 1));
        app.undo();
        // the switch's row and the stills copy's, B's stills value apart from the setting: the copies rule refuses the
        // answer, in a copy's words, which needs the copy's state given back with it
        let mut b = app.compare.as_ref().unwrap().1.clone();
        b.sections[0].get_mut(three[1].id).unwrap().put(three[1].index, 2).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        let mut acts: Vec<Action> = [&sw, &three[1]].iter().flat_map(|s| app.copy_row(std::slice::from_ref(*s), Col::b(0), Col::a(0))).collect();
        app.pin_families(None, 0, &mut acts);
        assert!(app.hold_untick(acts).is_empty());
        app.apply(Vec::new());
        app.answer_untick(Some(false));
        assert!(app.status.starts_with("Not copied:"), "{}", app.status);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(on), [Some(7), Some(7), Some(5)], 0));
    }

    /// The reviewer's probe 15: two questions in a row, each answered with its own state, are both taken; an answer
    /// replayed with the first question's state is refused; a display preference changed in the window while the
    /// page's question is open (record ids, the proof line, raw values, the rows' layout) refuses nothing, while Expert
    /// mode, which changes what is blocked, does.
    #[test]
    fn each_answer_is_to_its_own_question_and_a_display_preference_changes_nothing() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        let set = json!({ "target": 0, "key": sw.key, "value": off });
        let ask = |app: &mut App| body(&answer(app, "set", set.clone()).body)["ask"]["rev"].clone();
        let reply = |app: &mut App, choice: &str, rev: &serde_json::Value| {
            let mut a = set.clone();
            a["untick"] = json!(choice);
            a["ask_rev"] = rev.clone();
            answer(app, "set", a).status
        };
        let first = ask(&mut app);
        assert_eq!(reply(&mut app, "box", &first), 200);
        app.apply(vec![Action::Set(0, sw.slot(), on)]);
        let second = ask(&mut app);
        assert_ne!(first, second);
        assert_eq!(reply(&mut app, "box", &second), 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(3), Some(3), Some(5)]));
        app.apply(vec![Action::Set(0, sw.slot(), on)]);
        assert_eq!(reply(&mut app, "box", &first), 409, "a replayed answer");
        // display preferences changed while the question is open: the answer is taken
        let open = ask(&mut app);
        app.prefs.show_record_ids = !app.prefs.show_record_ids;
        app.prefs.show_proof = !app.prefs.show_proof;
        app.prefs.flat_list = !app.prefs.flat_list;
        app.show_raw = !app.show_raw;
        app.allow_raw_edits = !app.allow_raw_edits;
        assert_eq!((reply(&mut app, "box", &open), switch_now(&app, &sw)), (200, Some(off)));
        // Expert mode changed meanwhile: refused
        app.apply(vec![Action::Set(0, sw.slot(), on)]);
        let open = ask(&mut app);
        app.prefs.expert = true;
        assert_eq!((reply(&mut app, "box", &open), switch_now(&app, &sw)), (409, Some(on)));
    }

    /// The reviewer's R8 and R9: a copy of the switch's row and all three of its family's rows, two of whose places hold
    /// the other file's value already, asks nothing (the rows bring the whole family); the same copy with one family
    /// place view only, which the copy leaves alone, asks.
    #[test]
    fn a_copy_of_the_whole_family_asks_nothing_unless_a_place_is_left_alone() {
        for locked in [false, true] {
            let (mut app, three, sw, (off, on)) = with_switch(7, 7, 5, true);
            let mut b = app.doc.as_ref().unwrap().original.clone();
            b.sections[0].get_mut(sw.id).unwrap().put(sw.index, off).unwrap();
            for (s, v) in three.iter().zip([7, 7, 7]) {
                b.sections[0].get_mut(s.id).unwrap().put(s.index, v).unwrap();
            }
            app.compare = Some((PathBuf::from("B.DAT"), b));
            if locked {
                for s in app.schema.settings.iter_mut().filter(|s| s.key == MOVIE) {
                    s.proved = None;
                }
                app.schema_gen += 1;
            }
            let r = answer(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": [sw.key, MAIN, STILLS, MOVIE] }));
            assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
            assert_eq!(body(&r.body).get("ask").is_some(), locked, "locked: {locked}");
            if locked {
                assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(on), [Some(7), Some(7), Some(5)]), "nothing changed yet");
            } else {
                assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(7); 3]));
            }
        }
    }

    /// The reviewer's R10: the page's recall of a memory into the live settings, its rows narrowed (`shown`) to the
    /// switch's, which the memories keep, asks first (the family stays behind), and its answer makes the recall.
    #[test]
    fn a_page_memory_recall_that_leaves_the_family_behind_asks_first() {
        let (mut app, three, sw, (off, on)) = with_switch_kept(3, 3, 5, true, true);
        let m = app.dial_sets()[0];
        as_opened(&mut app, |c| c.sections[m].get_mut(sw.id).unwrap().put(sw.index, off).unwrap());
        let recall = json!({ "memory": m, "shown": true, "q": sw.name });
        let r = answer(&mut app, "recall", recall.clone());
        assert_eq!((r.status, body(&r.body)["ask"]["text"].clone(), switch_now(&app, &sw)), (200, json!(words(&sw, &three, off)), Some(on)));
        assert!(app.rows_copied.get().is_none() && app.rows_set.borrow().is_empty(), "nothing left for the next step");
        assert_eq!(answered(&mut app, "recall", recall, "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(0); 3]));
    }

    /// The reviewer's mutant N16: the page's merge (Merge B into A) whose rows change the switch but not its family asks
    /// first, as a copy of several rows does.
    #[test]
    fn a_merge_that_leaves_the_family_behind_asks_first() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        let base = app.doc.as_ref().unwrap().original.clone();
        let mut b = base.clone();
        b.sections[0].get_mut(sw.id).unwrap().put(sw.index, off).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        app.base = Some((PathBuf::from("Base.DAT"), base));
        let merge = json!({ "base": ["base", 0], "a": ["a", 0], "b": ["b", 0], "kind": "b_into_a" });
        let r = answer(&mut app, "merge", merge.clone());
        assert_eq!((r.status, body(&r.body)["ask"]["text"].clone(), switch_now(&app, &sw)), (200, json!(words(&sw, &three, off)), Some(on)));
        assert_eq!(answered(&mut app, "merge", merge, "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(0); 3]));
    }

    /// The reviewer's probe 2: a put-back of the switch asks on the page as in the window, and "camera" sets the family
    /// with it.
    #[test]
    fn a_put_back_of_the_switch_asks_on_the_page_as_in_the_window() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, false);
        app.apply(vec![Action::Set(0, sw.slot(), on)]);
        {
            let d = app.doc.as_mut().unwrap();
            d.original = d.edited.clone();
        }
        let (_, acts) = app.put_back_choice(std::slice::from_ref(&sw), 0).expect("a put-back");
        assert!(app.untick_ask(&acts).is_some(), "the window asks");
        let restore = json!({ "target": 0, "key": sw.key });
        let r = answer(&mut app, "restore", restore.clone());
        assert_eq!((body(&r.body)["ask"]["text"].clone(), switch_now(&app, &sw)), (json!(words(&sw, &three, off)), Some(on)));
        assert_eq!(answered(&mut app, "restore", restore, "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(0); 3]));
    }

    /// The History window's Revert of an edit that took the switch to the value keeping the family apart asks, in the
    /// window (its own Revert, mutant N13) and on the page; the page's answer is refused where the history moved since
    /// the question (another edit), so it never puts back another step's record.
    #[test]
    fn a_history_put_back_of_the_switch_asks() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, false);
        app.apply(vec![Action::Set(0, sw.slot(), on)]);
        let before = app.undo[0].sections[0].get(sw.id).unwrap().clone();
        let ask = app.untick_ask(&[Action::SetRecord(0, before.clone())]).expect("the window asks");
        assert_eq!(ask.to, (0, sw.slot(), off));
        app.history_revert(vec![Action::SetRecord(0, before.clone())]);
        assert!(app.untick_pending.is_some() && switch_now(&app, &sw) == Some(on), "the History window's Revert waits for the answer");
        app.untick_pending = None;
        let revert = json!({ "step": 0, "section": 0, "id": sw.id });
        let r = answer(&mut app, "revert_history", revert.clone());
        assert_eq!((r.status, body(&r.body)["ask"]["text"].clone()), (200, json!(words(&sw, &three, off))));
        assert_eq!(answered(&mut app, "revert_history", revert.clone(), "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(0); 3]));
        app.undo();
        // the history moves between the question and the answer: refused, nothing changed
        let j = body(&answer(&mut app, "revert_history", revert.clone()).body);
        app.last_edit = None;
        app.apply(vec![Action::Set(0, three[0].slot(), 4)]);
        let steps = app.undo.len();
        let mut late = revert;
        late["untick"] = json!("camera");
        late["ask_rev"] = j["ask"]["rev"].clone();
        let r = answer(&mut app, "revert_history", late);
        assert_eq!((r.status, switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (409, Some(on), [Some(4), Some(4), Some(5)], steps));
        assert!(body(&r.body)["error"].as_str().unwrap().starts_with("Not changed: the file changed while the question was open"));
    }

    /// The reviewer's probe 13: a switch the memories keep, its row copied from a memory into the live settings by the
    /// page's arrow, asks as the window's arrow does; the page's answer makes it.
    #[test]
    fn a_memory_arrow_asks_on_the_page_as_in_the_window() {
        let (mut app, three, sw, (off, on)) = with_switch_kept(3, 3, 5, true, true);
        let m = app.dial_sets()[0];
        as_opened(&mut app, |c| c.sections[m].get_mut(sw.id).unwrap().put(sw.index, off).unwrap());
        let acts = app.copy_row(std::slice::from_ref(&sw), Col::a(m), Col::a(0));
        assert!(app.untick_ask(&acts).is_some(), "the window's arrow asks");
        app.apply(Vec::new());
        let arrow = json!({ "key": sw.key, "from": m, "to": 0 });
        let r = answer(&mut app, "memory_copy", arrow.clone());
        assert_eq!((r.status, body(&r.body)["ask"]["text"].clone(), switch_now(&app, &sw)), (200, json!(words(&sw, &three, off)), Some(on)));
        assert_eq!(answered(&mut app, "memory_copy", arrow, "camera").0, 200);
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0)), (Some(off), [Some(0); 3]));
    }

    /// The reviewer's probes 3 and 4: a value the definition says the camera sets that a record of the family does not
    /// take here (off its range, not offered) blocks "Do as the camera does", in the window and on the page, with
    /// nothing changed.
    #[test]
    fn a_value_a_record_does_not_take_blocks_the_camera_choice() {
        for bad in [100000, -100] {
            let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
            for s in app.schema.settings.iter_mut().filter(|s| s.key == sw.key) {
                s.keeps_apart[0].untick_sets = Some(bad);
            }
            app.schema_gen += 1;
            let ask = app.untick_ask(&[Action::Set(0, sw.slot(), off)]).unwrap();
            assert_eq!(ask.blocked, Some(format!("Not changed: {} does not take {} in this file, so the editor cannot set it as the camera did. {UNTICK_THIS_ONLY} changes {} alone.", three[0].name, named(&three[0], bad), sw.name)));
            app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
            app.answer_untick(Some(true));
            assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(on), [Some(3), Some(3), Some(5)], 0));
            app.untick_pending = None;
            let (status, _) = answered(&mut app, "set", json!({ "target": 0, "key": sw.key, "value": off }), "camera");
            assert_eq!((status, held(&app, &three, 0), app.undo.len()), (409, [Some(3), Some(3), Some(5)], 0));
        }
    }

    /// The reviewer's probes 8, 9 and 10: a step `apply` makes in part is taken back whole and said, never called done:
    /// the file as it was, a redo the person had kept, the undo history as it was even at its limit (`UNDO_LIMIT`,
    /// where `apply` let go of the oldest step), and no edit left for the next one to join.
    #[test]
    fn a_step_made_in_part_is_taken_back_whole() {
        // a redo the person had
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        app.apply(vec![Action::Set(0, three[2].slot(), 6)]);
        app.undo();
        let (redo, before) = (app.redo.len(), app.doc.as_ref().unwrap().edited.to_bytes());
        assert!(shortfall(&mut app, &sw, off).is_some());
        assert_eq!((app.doc.as_ref().unwrap().edited.to_bytes() == before, app.undo.len(), app.redo.len()), (true, 0, redo));
        assert!(app.status.starts_with("Not changed: the editor could not make every change"), "{}", app.status);
        assert!(app.last_edit.is_none(), "nothing for the next edit to join");
        app.redo();
        assert_eq!(held(&app, &three, 0), [Some(3), Some(3), Some(6)], "the redo is the person's");
        // at the undo history's limit
        let (mut app, three, sw, (off, on2)) = with_switch(3, 3, 5, true);
        let marks: Vec<CamSet> = (0..UNDO_LIMIT).map(|i| {
            let mut c = app.doc.as_ref().unwrap().edited.clone();
            c.sections[0].get_mut(three[2].id).unwrap().put(three[2].index, (i % 15) as i64).unwrap();
            c
        }).collect();
        app.undo = marks;
        let first = app.undo[0].to_bytes();
        assert!(shortfall(&mut app, &sw, off).is_some());
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(on2), [Some(3), Some(3), Some(5)], UNDO_LIMIT));
        assert_eq!(app.undo[0].to_bytes(), first, "the oldest step is back");
        let _ = on;
    }

    /// The reviewer's probe 5: Undo after "Do as the camera does" gives back the file byte for byte, and Redo the step's.
    #[test]
    fn undo_and_redo_of_the_camera_choice_are_byte_for_byte() {
        let (mut app, _, sw, (off, _)) = with_switch(3, 3, 5, true);
        let before = app.doc.as_ref().unwrap().edited.to_bytes();
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.answer_untick(Some(true));
        let after = app.doc.as_ref().unwrap().edited.to_bytes();
        assert_ne!(before, after);
        app.undo();
        assert_eq!(app.doc.as_ref().unwrap().edited.to_bytes(), before);
        app.redo();
        assert_eq!(app.doc.as_ref().unwrap().edited.to_bytes(), after);
    }

    /// The reviewer's probe 6: an answer from the page to a question that no longer stands (the switch was changed in
    /// the window meanwhile) is refused, and changes nothing.
    #[test]
    fn a_page_answer_to_a_question_that_no_longer_stands_changes_nothing() {
        let (mut app, three, sw, (off, _)) = with_switch(3, 3, 5, true);
        let set = json!({ "target": 0, "key": sw.key, "value": off });
        let j = body(&answer(&mut app, "set", set.clone()).body);
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.answer_untick(Some(false));
        let steps = app.undo.len();
        let mut late = set;
        late["untick"] = json!("camera");
        late["ask_rev"] = j["ask"]["rev"].clone();
        let r = answer(&mut app, "set", late);
        assert_eq!((r.status, switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (409, Some(off), [Some(3), Some(3), Some(5)], steps));
    }

    /// The reviewer's probe 7: the switch itself view only: the page refuses the change at once, as for any view-only
    /// setting; a change of it reaching the window all the same (a put-back) asks, with "Do as the camera does"
    /// blocked, and nothing changes through it.
    #[test]
    fn a_view_only_switch_changes_nothing_through_the_question() {
        let (mut app, three, sw, (off, on)) = with_switch(3, 3, 5, true);
        for s in app.schema.settings.iter_mut().filter(|s| s.key == sw.key) {
            s.proved = None;
        }
        app.schema_gen += 1;
        let r = answer(&mut app, "set", json!({ "target": 0, "key": sw.key, "value": off }));
        assert_eq!((r.status, switch_now(&app, &sw), held(&app, &three, 0)), (409, Some(on), [Some(3), Some(3), Some(5)]));
        let ask = app.untick_ask(&[Action::Set(0, sw.slot(), off)]).expect("asked");
        assert_eq!(ask.blocked, Some(format!("Not changed: {} is view only here, so the editor cannot change it as the camera did. Expert mode (⚙ Settings > Editing & Compare) can change it.", sw.name)));
        app.hold_untick(vec![Action::Set(0, sw.slot(), off)]);
        app.answer_untick(Some(true));
        assert_eq!((switch_now(&app, &sw), held(&app, &three, 0), app.undo.len()), (Some(on), [Some(3), Some(3), Some(5)], 0));
    }

    /// While the switch keeps the family apart, the family's rows (the setting and each copy, in the live settings the
    /// switch is kept in) say what a change on the camera then did, and that the editor does not follow the switch:
    /// after the copies rule's own note on a copy, alone on the setting; the page's rows say the same. With the switch
    /// at its other value, or in a memory set (which does not keep it), nothing is said. What the editor does is as
    /// before: an edit of the setting takes along every copy that held its value as the file was opened, the other
    /// mode's too, though the camera, with the switch so, changed only the copy for its mode.
    #[test]
    fn a_switch_that_keeps_the_family_apart_says_so_on_its_rows() {
        let (mut app, three, sw, (_, on)) = with_switch(3, 3, 3, true);
        let hint = format!("{} is {} in this file: when this was tried on the camera, a change of {} then changed only the copy for the shooting mode it was made in, {} or {}. The editor does not follow that setting: here the copies that held {}'s value when this file was opened or read change with it.",
            sw.name, named(&sw, on), three[0].name, three[1].name, three[2].name, three[0].name);
        assert_eq!(app.apart_note(&three[0], 0), Some(hint.clone()));
        assert_eq!(app.copy_note(&three[0], 0).map(|(w, _)| w), Some(hint.clone()), "the setting itself: the hint alone");
        let (copy, _) = app.copy_note(&three[1], 0).unwrap();
        assert!(copy.starts_with(&format!("Changing this changes {} and {} too", three[0].name, three[2].name)) && copy.ends_with(&hint), "{copy}");
        assert_eq!(app.web_row(0, std::slice::from_ref(&three[0]))["copy_note"], json!(hint), "the page's row");
        assert!(app.apart_note(&three[0], 1).is_none() && app.copy_note(&three[0], 1).is_none(), "a memory set does not keep the switch");
        // what the editor does, as before: the copies in step follow, the other mode's too
        app.apply(vec![Action::Set(0, three[0].slot(), 6)]);
        assert_eq!(held(&app, &three, 0), [Some(6); 3]);
        // the switch at its other value: nothing said
        let (app, three, _, _) = with_switch(3, 3, 3, false);
        assert!(app.apart_note(&three[0], 0).is_none() && app.copy_note(&three[0], 0).is_none());
    }
}
