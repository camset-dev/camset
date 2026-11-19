//! Two settings the camera keeps in order, a lower limit and an upper one (`Setting::at_most` on the lower, naming the
//! upper; `at_least` on the upper, naming it back). The camera never lets the lower sit above the upper: a value chosen
//! past the other moves the other to it. The editor does the same in `apply` (`limit_moves`), whichever view asked,
//! and says what moved (`moved_words`); a row says the rule beforehand (`limit_note`, shown with `copy_note`); a pair a
//! file holds out of order (opened so, or made so by a copy of rows or a memory recalled, which set both) is listed
//! before a save or a write (`out_of_order`, `IssueKind::Order`) with a one-step fix (`order_fix`). The order is each
//! value's place in the two settings' value lists, which list the same values (`Schema::check_limits`): the editor
//! never takes the codes to rise with the value, which would be a camera fact (docs/decisions/0020). Everything here
//! comes from the definition: no setting is known by name.

use crate::*;

/// The place of value `v` in setting `s`'s value list, from 0: the order two limits are kept in (never the codes').
pub(crate) fn place(s: &Setting, v: i64) -> Option<usize> {
    s.values.iter().position(|(c, _)| *c == v)
}

/// Two limits a file holds out of order in one set (`App::out_of_order`): the set, the lower and the upper (indices
/// among the definition's settings), and whether it was so in the file as first opened or read.
pub(crate) struct OutOfOrder {
    pub(crate) section: usize,
    pub(crate) lower: usize,
    pub(crate) upper: usize,
    pub(crate) as_opened: bool,
}

/// A limit a step moves to keep two in order (`App::limit_moves`): the set, the limit moved and the one chosen past it
/// (indices among the definition's settings), and the value it takes.
pub(crate) struct LimitMove {
    pub(crate) section: usize,
    pub(crate) moved: usize,
    pub(crate) chosen: usize,
    pub(crate) value: i64,
}

impl App {
    /// Every pair of limits the definition names, (lower, upper) by index among its settings: `at_most` on the lower
    /// naming the upper, which names it back (`Schema::check_limits` refuses a definition where it does not).
    pub(crate) fn limit_pairs(&self) -> Vec<(usize, usize)> {
        self.schema.settings.iter().enumerate().filter_map(|(i, s)| Some((i, self.index_of_key(&s.at_most.as_ref()?.setting)?))).collect()
    }

    /// The pair setting `s` is a limit of, (lower, upper) by index among the definition's settings; None for any other.
    pub(crate) fn pair_of(&self, s: &Setting) -> Option<(usize, usize)> {
        match (&s.at_most, &s.at_least) {
            (Some(l), _) => Some((self.index_of_key(&s.key)?, self.index_of_key(&l.setting)?)),
            (None, Some(l)) => Some((self.index_of_key(&l.setting)?, self.index_of_key(&s.key)?)),
            (None, None) => None,
        }
    }

    /// Whether file `c` holds the lower limit past the upper in set `section`, by their value lists' places: None
    /// where the set does not keep both, or either holds a value its list does not name (no order to judge).
    pub(crate) fn crossed_in(&self, c: &CamSet, section: usize, lower: usize, upper: usize) -> Option<bool> {
        let (lo, up) = (&self.schema.settings[lower], &self.schema.settings[upper]);
        if !kept_in(lo, section) || !kept_in(up, section) {
            return None;
        }
        let held = |s: &Setting| c.sections.get(section)?.get(s.id)?.get(s.index);
        Some(place(lo, held(lo)?)? > place(up, held(up)?)?)
    }

    /// Every pair of limits file A holds out of order, in a set, which no camera writes: what the save and write windows
    /// list (`judge`), edited or not.
    pub(crate) fn out_of_order(&self) -> Vec<OutOfOrder> {
        let Some(d) = &self.doc else { return Vec::new() };
        let mut out = Vec::new();
        for (lower, upper) in self.limit_pairs() {
            for si in 0..d.edited.sections.len() {
                if self.crossed_in(&d.edited, si, lower, upper) == Some(true) {
                    out.push(OutOfOrder { section: si, lower, upper, as_opened: self.crossed_in(&d.baseline, si, lower, upper) == Some(true) });
                }
            }
        }
        out
    }

    /// What setting `i` holds in set `si` once `actions` and the moves `more` are made (`apply`): its own last Set,
    /// Revert or whole record among them; for a copy in step with its setting (`follows`), its setting's new value, as
    /// `apply` takes such a copy along; else what it holds now.
    fn after_step(&self, d: &Doc, actions: &[Action], more: &[LimitMove], si: usize, i: usize) -> Option<i64> {
        let own = |j: usize| -> Option<Option<i64>> {
            let slot = self.schema.settings[j].slot();
            if let Some(m) = more.iter().rev().find(|m| m.section == si && m.moved == j) {
                return Some(Some(m.value));
            }
            actions.iter().rev().find_map(|a| match a {
                Action::Set(x, sl, v) if *x == si && *sl == slot => Some(Some(*v)),
                Action::Revert(x, sl) if *x == si && (*sl == slot || (sl.0 == slot.0 && sl.1.is_none())) => Some(d.original_value(si, slot)),
                Action::SetRecord(x, rec) if *x == si && rec.id == slot.0 => Some(rec.get(slot.1)),
                _ => None,
            })
        };
        if let Some(v) = own(i) {
            return v;
        }
        let s = &self.schema.settings[i];
        if let Some((m, mi)) = self.main_of(s).and_then(|m| Some((m, self.index_of_key(&m.key)?))) {
            if let Some(Some(mv)) = own(mi) {
                if Some(mv) != d.value(si, m.slot()) && self.follows(s, m, si) && shape_ok_for(&d.edited, si, s) {
                    return Some(mv);
                }
            }
        }
        d.value(si, s.slot())
    }

    /// The limits a step moves to keep each pair in order, as the camera does (`apply`): where `actions` change one limit
    /// of a pair in a set and not the other, and leave the lower past the upper by their value lists' places, the other
    /// takes the chosen one's value (the value at the same place of its own list), in the same step. A step that changes
    /// both leaves them as it asks (a copy of several rows, a memory recalled): the save and write windows list such a
    /// pair (`out_of_order`). Round by round, so a pair of copies whose settings moved is judged after them.
    pub(crate) fn limit_moves(&self, actions: &[Action]) -> Vec<LimitMove> {
        let Some(d) = &self.doc else { return Vec::new() };
        let pairs = self.limit_pairs();
        if pairs.is_empty() {
            return Vec::new();
        }
        let mut sections: Vec<usize> = actions.iter().filter_map(|a| match a {
            Action::Set(si, ..) | Action::Revert(si, _) | Action::SetRecord(si, _) => Some(*si),
            _ => None,
        }).collect();
        sections.sort_unstable();
        sections.dedup();
        let st = &self.schema.settings;
        let mut more: Vec<LimitMove> = Vec::new();
        for _ in 0..4 {
            let before = more.len();
            for &(lower, upper) in &pairs {
                for &si in &sections {
                    if !kept_in(&st[lower], si) || !kept_in(&st[upper], si) || more.iter().any(|m| m.section == si && (m.moved == lower || m.moved == upper)) {
                        continue;
                    }
                    let (Some(lo), Some(up)) = (self.after_step(d, actions, &more, si, lower), self.after_step(d, actions, &more, si, upper)) else { continue };
                    let (lower_set, upper_set) = (Some(lo) != d.value(si, st[lower].slot()), Some(up) != d.value(si, st[upper].slot()));
                    if lower_set == upper_set {
                        continue;
                    }
                    let (Some(pl), Some(pu)) = (place(&st[lower], lo), place(&st[upper], up)) else { continue };
                    if pl <= pu {
                        continue;
                    }
                    more.push(if lower_set {
                        LimitMove { section: si, moved: upper, chosen: lower, value: st[upper].values[pl].0 }
                    } else {
                        LimitMove { section: si, moved: lower, chosen: upper, value: st[lower].values[pu].0 }
                    });
                }
            }
            if more.len() == before {
                break;
            }
        }
        more
    }

    /// Whether a proof showed the camera do move `m` (`moves_it` on the limit chosen past the other), or none tried it.
    fn move_proved(&self, m: &LimitMove) -> bool {
        let chosen = &self.schema.settings[m.chosen];
        chosen.at_most.as_ref().or(chosen.at_least.as_ref()).is_some_and(|l| l.moves_it)
    }

    /// What the status line and the page say of a limit a step moved (`limit_moves`), as a copy's note says what changes
    /// with it: which limit moved where, and why; where no proof showed the camera move it that way, that too.
    pub(crate) fn moved_words(&self, m: &LimitMove) -> String {
        let st = &self.schema.settings;
        let (moved, chosen) = (&st[m.moved], &st[m.chosen]);
        let up = moved.at_least.is_some();
        let (lower, upper) = if up { (chosen, moved) } else { (moved, chosen) };
        let to = Self::describe(moved, Some(m.value));
        let set = if m.section > 0 { format!(" in {}", self.schema.camera.target_name(m.section)) } else { String::new() };
        let dir = if up { "up" } else { "down" };
        if self.move_proved(m) {
            format!("{} moved {dir} to {to} too{set}, as the camera moves it: it keeps {} at or below {}.", moved.name, lower.name, upper.name)
        } else {
            format!("{} moved {dir} to {to} too{set}, so the file keeps the order the camera keeps, {} at or below {}. What the camera itself does when {} is set {} {} was not tried on it.",
                moved.name, lower.name, upper.name, chosen.name, if up { "above" } else { "below" }, moved.name)
        }
    }

    /// What a row says beside a limit of a pair the camera keeps in order (`at_most`, `at_least`; shown with `copy_note`)
    /// in set `section`, and its hover: where file A holds the pair out of order there, that it does and how it is put
    /// back; else what a value past the other does, here as on the camera (`limit_moves`), or, where no proof showed the
    /// camera do it, that it was not tried. None for any other setting.
    pub(crate) fn limit_note(&self, s: &Setting, section: usize) -> Option<(String, String)> {
        let d = self.doc.as_ref()?;
        let (lower, upper) = self.pair_of(s)?;
        let (lo, up) = (&self.schema.settings[lower], &self.schema.settings[upper]);
        if !kept_in(lo, section) || !kept_in(up, section) {
            return None;
        }
        let hover = format!("{} and {} are the two ends of one range, and the camera keeps them in order: never the lower above the upper. A value chosen past the other moves the other to it.", lo.name, up.name);
        if self.crossed_in(&d.edited, section, lower, upper) == Some(true) {
            let held = |x: &Setting| Self::describe(x, d.value(section, x.slot()));
            let then = if self.crossed_in(&d.baseline, section, lower, upper) == Some(true) { " It was so when this file was opened or read." } else { "" };
            return Some((format!("Out of order: {} is above {} here ({} against {}), which no camera writes, so the camera may refuse this file.{then} Changing either of the two puts them back in order, as on the camera; the Before saving and Write windows offer it in one step.",
                lo.name, up.name, held(lo), held(up)), hover));
        }
        let is_lower = s.at_most.is_some();
        let (other, rule, past, dir) = if is_lower { (up, "below", "above", "up") } else { (lo, "above", "below", "down") };
        let proved = s.at_most.as_ref().or(s.at_least.as_ref()).is_some_and(|l| l.moves_it);
        let words = if proved {
            format!("The camera keeps this at or {rule} {0}: a value {past} it moves {0} {dir} to the same value, here as on the camera.", other.name)
        } else {
            format!("The camera keeps this at or {rule} {0}: a value {past} it moves {0} {dir} to the same value here, so the file stays in that order; what the camera itself does then was not tried on it.", other.name)
        };
        Some((words, hover))
    }

    /// The one step that puts a pair file A holds out of order in set `section` back in order, `lower` the pair's lower
    /// limit, and its words (`issue_fix`): where only one of the two changed since the file was first opened or read,
    /// the other moves to its value, as the camera moves it when that one is chosen past it; where both or neither did,
    /// the upper moves up to the lower's value, unless only the other way was shown on the camera. None where the pair
    /// is in order there, or a value is not named.
    pub(crate) fn order_fix(&self, section: usize, lower: usize) -> Option<(String, Vec<Action>)> {
        let d = self.doc.as_ref()?;
        let st = &self.schema.settings;
        let lo = &st[lower];
        let upper = self.index_of_key(&lo.at_most.as_ref()?.setting)?;
        let up = &st[upper];
        let (pl, pu) = (place(lo, d.value(section, lo.slot())?)?, place(up, d.value(section, up.slot())?)?);
        if pl <= pu {
            return None;
        }
        let changed = |s: &Setting| d.value(section, s.slot()) != d.baseline_value(section, s.slot());
        let raise = match (changed(lo), changed(up)) {
            (true, false) => true,
            (false, true) => false,
            _ => lo.at_most.as_ref().is_some_and(|l| l.moves_it) || !up.at_least.as_ref().is_some_and(|l| l.moves_it),
        };
        let (s, v) = if raise { (up, up.values[pl].0) } else { (lo, lo.values[pu].0) };
        Some((format!("Set {} to {}", s.name, Self::describe(s, Some(v))), vec![Action::Set(section, s.slot(), v)]))
    }

    /// `said`, with what the last step moved to keep two limits in order (`limits_moved`), when it moved anything: for
    /// the page's handlers, which say what they did after `apply`.
    pub(crate) fn with_moved(&self, said: String) -> String {
        match &self.limits_moved.1 {
            Some(m) => format!("{said} {m}"),
            None => said,
        }
    }
}

/// Two limits the camera keeps in order, whichever view edits them: the detail panel, the page, a memory recalled; the
/// save and write windows' list; the Exposure page. The a1 II's ISO Range Limit ends and ISO AUTO's Minimum and Maximum
/// with their copies, by their keys, given the fields here as the kit writes them (the definition shipped may not carry
/// them yet); made-up values (places in the lists), never a camera's.
#[cfg(test)]
pub(crate) mod limits_tests {
    use super::*;
    use crate::copies_tests::{as_opened, setting};
    use crate::web::tests::answer;
    use camset_editor::schema::OtherLimit;
    use serde_json::json;

    /// ISO Range Limit's lower end and its two other records, and its upper end and its two (one row each).
    const LOWER: [&str; 3] = ["global:0x0b65", "global:0x0b69", "global:0x0b6d"];
    const UPPER: [&str; 3] = ["global:0x0b63", "global:0x0b67", "global:0x0b6b"];
    /// ISO AUTO's Minimum with its stills and movie copies, and its Maximum with its two.
    const MIN: [&str; 3] = ["global:0x0dfa", "global:0x0dfc", "global:0x0dfe"];
    const MAX: [&str; 3] = ["global:0x0e00", "global:0x0e02", "global:0x0e04"];

    /// The a1 II's pairs as the kit writes them: ISO Range Limit, a value past the other proved to move it both ways;
    /// ISO AUTO and each mode's copies of it, a Minimum above the Maximum proved to raise it, the other way not tried.
    fn pairs() -> Vec<(&'static str, &'static str, bool, bool)> {
        vec![(LOWER[0], UPPER[0], true, true), (MIN[0], MAX[0], true, false), (MIN[1], MAX[1], true, false), (MIN[2], MAX[2], true, false)]
    }

    /// The sample open with those pairs, every record of each lower side at place `lo` of its list and of each upper side
    /// at place `up`, in every set that keeps them, as the file was opened.
    pub(crate) fn with_pairs(lo: usize, up: usize) -> App {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        for s in app.schema.settings.iter_mut() {
            for (l, u, lower_moves, upper_moves) in pairs() {
                if s.key == l { s.at_most = Some(OtherLimit { setting: u.into(), moves_it: lower_moves }); }
                if s.key == u { s.at_least = Some(OtherLimit { setting: l.into(), moves_it: upper_moves }); }
            }
        }
        app.schema_gen += 1;
        hold(&mut app, lo, up);
        app
    }

    /// Every record of each pair's lower side at place `lo` of its list and of its upper side at `up`, in every set that
    /// keeps them, as the file was opened.
    fn hold(app: &mut App, lo: usize, up: usize) {
        let sides: Vec<(Setting, usize)> = LOWER.iter().chain(&MIN).map(|k| (setting(app, k), lo))
            .chain(UPPER.iter().chain(&MAX).map(|k| (setting(app, k), up))).collect();
        as_opened(app, |c| for (si, sec) in c.sections.iter_mut().enumerate() {
            for (s, at) in &sides {
                if let Some(r) = sec.get_mut(s.id).filter(|_| kept_in(s, si)) {
                    r.put(s.index, s.values[*at].0).unwrap();
                }
            }
        });
    }

    /// Where each of `keys` stands in its list in set `si` (None: a value it does not name, or no record).
    fn at(app: &App, keys: &[&str], si: usize) -> Vec<Option<usize>> {
        keys.iter().map(|k| { let s = setting(app, k); app.doc.as_ref().unwrap().value(si, s.slot()).and_then(|v| place(&s, v)) }).collect()
    }

    /// The value at place `at` of a setting's list.
    fn code(app: &App, key: &str, at: usize) -> i64 {
        setting(app, key).values[at].0
    }

    /// A lower limit chosen above its upper moves the upper to the same value, in every record it is kept in, in the
    /// same undoable step, in the set edited only; the status says what moved and why, as the camera does. The other
    /// way round, the lower comes down to the upper, and stays there when the upper goes back. A value that does not
    /// cross moves nothing.
    #[test]
    fn a_limit_chosen_past_the_other_moves_the_other_to_it() {
        let mut app = with_pairs(3, 10);
        let (lo, up) = (setting(&app, LOWER[0]), setting(&app, UPPER[0]));
        assert!(app.apply(vec![Action::Set(0, lo.slot(), code(&app, LOWER[0], 6))]).is_none());
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(6); 3], vec![Some(10); 3]), "in order: nothing else moves");
        assert!(app.limits_moved.1.is_none());
        assert!(app.apply(vec![Action::Set(0, lo.slot(), code(&app, LOWER[0], 20))]).is_none());
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(20); 3], vec![Some(20); 3]));
        assert_eq!(at(&app, &UPPER, 1), vec![Some(10); 3], "another set is left as it was");
        let said = format!("{} moved up to {} too, as the camera moves it: it keeps {} at or below {}.", up.name, App::describe(&up, Some(code(&app, UPPER[0], 20))), lo.name, up.name);
        assert!(app.status.contains(&said), "{}", app.status);
        assert_eq!(app.limits_moved.0.iter().map(|&(si, i)| (si, app.schema.settings[i].key.as_str())).collect::<Vec<_>>(), vec![(0, UPPER[0])]);
        app.undo();
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(6); 3], vec![Some(10); 3]), "one step");
        // the upper chosen below the lower brings it down, a record of the row chosen as well as its first
        assert!(app.apply(vec![Action::Set(0, setting(&app, UPPER[1]).slot(), code(&app, UPPER[1], 2))]).is_none());
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(2); 3], vec![Some(2); 3]));
        assert!(app.status.contains(&format!("{} moved down to", lo.name)) && app.status.contains("as the camera moves it"), "{}", app.status);
        assert!(app.apply(vec![Action::Set(0, up.slot(), code(&app, UPPER[0], 15))]).is_none());
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(2); 3], vec![Some(15); 3]));
    }

    /// The Minimum chosen above the Maximum raises the Maximum and the copies of it in step with it; the Maximum chosen
    /// below the Minimum, a way no proof tried, brings the Minimum and its copies down so the file keeps the order, and
    /// says that the camera was not seen to do it.
    #[test]
    fn a_way_no_proof_tried_keeps_the_order_and_says_so() {
        let mut app = with_pairs(5, 12);
        let (min, max) = (setting(&app, MIN[0]), setting(&app, MAX[0]));
        assert!(app.apply(vec![Action::Set(0, min.slot(), code(&app, MIN[0], 20))]).is_none());
        assert_eq!((at(&app, &MIN, 0), at(&app, &MAX, 0)), (vec![Some(20); 3], vec![Some(20); 3]));
        assert!(app.status.contains(&format!("{} moved up to", max.name)) && app.status.contains("as the camera moves it"), "{}", app.status);
        app.undo();
        assert!(app.apply(vec![Action::Set(0, max.slot(), code(&app, MAX[0], 3))]).is_none());
        assert_eq!((at(&app, &MIN, 0), at(&app, &MAX, 0)), (vec![Some(3); 3], vec![Some(3); 3]));
        let said = format!("What the camera itself does when {} is set below {} was not tried on it.", max.name, min.name);
        assert!(app.status.contains(&format!("{} moved down to", min.name)) && app.status.contains(&said), "{}", app.status);
        assert!(!app.status.contains("as the camera moves it"), "{}", app.status);
    }

    /// Every set keeps its own pair: an edit in a memory set moves the other limit there, nowhere else; and in Expert mode
    /// a copy changed alone moves the other limit's copy for the same mode alone.
    #[test]
    fn each_memory_set_and_each_modes_copies_keep_their_order() {
        let mut app = with_pairs(5, 12);
        let m = app.dial_sets()[0];
        assert!(app.apply(vec![Action::Set(m, setting(&app, LOWER[0]).slot(), code(&app, LOWER[0], 25))]).is_none());
        assert_eq!((at(&app, &UPPER, m), at(&app, &UPPER, 0)), (vec![Some(25); 3], vec![Some(12); 3]));
        assert!(app.status.contains(&format!("too in {},", app.schema.camera.target_name(m))), "{}", app.status);
        app.prefs.expert = true;
        assert!(app.apply(vec![Action::Set(0, setting(&app, MIN[2]).slot(), code(&app, MIN[2], 20))]).is_none());
        assert_eq!((at(&app, &MIN, 0), at(&app, &MAX, 0)), (vec![Some(5), Some(5), Some(20)], vec![Some(12), Some(12), Some(20)]));
    }

    /// A limit that would have to move but cannot be changed here (view only outside Expert mode) refuses the whole step,
    /// saying why; nothing changes.
    #[test]
    fn a_limit_that_cannot_move_refuses_the_step() {
        let mut app = with_pairs(3, 10);
        for s in app.schema.settings.iter_mut().filter(|s| UPPER.contains(&s.key.as_str())) {
            s.proved = None;
        }
        let lo = setting(&app, LOWER[0]);
        let why = app.apply(vec![Action::Set(0, lo.slot(), code(&app, LOWER[0], 20))]).unwrap();
        assert!(why.starts_with("Not changed: the camera keeps") && why.contains("would have to move to") && why.contains("View only:"), "{why}");
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(3); 3], vec![Some(10); 3]));
        assert!(app.undo.is_empty());
    }

    /// A step that sets both limits (a copy of several rows, a memory recalled) leaves them as it asks; a pair it leaves
    /// out of order is listed before a save and a write under its own heading, so no all-clear shows, with a fix of one
    /// step that puts it back in order. A file opened out of order is listed too, says so, and its rows say it, on the
    /// page as in the window.
    #[test]
    fn a_pair_out_of_order_is_listed_with_its_fix() {
        let mut app = with_pairs(3, 10);
        let (lo, up) = (setting(&app, LOWER[0]), setting(&app, UPPER[0]));
        assert!(app.apply(vec![Action::Set(0, lo.slot(), code(&app, LOWER[0], 20)), Action::Set(0, up.slot(), code(&app, UPPER[0], 8))]).is_none());
        assert_eq!((at(&app, &LOWER, 0), at(&app, &UPPER, 0)), (vec![Some(20); 3], vec![Some(8); 3]), "as asked");
        let issues = app.acceptance_issues();
        let order: Vec<&Issue> = issues.iter().filter(|i| i.kind == IssueKind::Order).collect();
        assert_eq!(order.len(), 1, "{:?}", issues.iter().map(|i| (&i.name, i.kind)).collect::<Vec<_>>());
        assert!(app.write_issues().iter().any(|i| i.kind == IssueKind::Order));
        let is = order[0];
        assert_eq!((is.section, is.slot, is.value.clone()), (0, lo.slot(), App::describe(&lo, Some(code(&app, LOWER[0], 20)))));
        assert!(is.reason.contains(&format!("the camera keeps this at or below {}", up.name)) && !is.reason.contains("opened"), "{}", is.reason);
        assert_eq!(IssueKind::Order.heading().0, "Limits out of order");
        // both changed: the upper goes up to the lower, as the camera does when the lower is chosen above it
        let (words, fix) = app.issue_fix(is).unwrap();
        assert_eq!(words, format!("Set {} to {}", up.name, App::describe(&up, Some(code(&app, UPPER[0], 20)))));
        assert!(app.apply(fix).is_none());
        assert_eq!(at(&app, &UPPER, 0), vec![Some(20); 3]);
        assert!(!app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Order));
        // a file opened out of order: listed, as opened; its rows say it, on the page as in the window; the fix
        let mut app = with_pairs(20, 8);
        let mine = |app: &App| app.acceptance_issues().into_iter().find(|i| i.kind == IssueKind::Order && (i.section, i.slot) == (0, lo.slot()));
        let is = mine(&app).unwrap();
        assert!(is.reason.contains("it was so when the file was opened or read"), "{}", is.reason);
        let (note, _) = app.copy_note(&lo, 0).unwrap();
        assert!(note.starts_with(&format!("Out of order: {} is above {} here", lo.name, up.name)) && note.contains("It was so when this file was opened or read."), "{note}");
        let linked = app.web_linked(0, LOWER[0]).unwrap();
        assert_eq!(app.web_row(0, &linked)["copy_note"], json!(note));
        let (words, fix) = app.issue_fix(&is).unwrap();
        assert!(words.starts_with(&format!("Set {} to", up.name)), "neither changed: the upper goes up, the way a proof showed: {words}");
        assert!(app.apply(fix).is_none());
        assert!(mine(&app).is_none());
        assert!(app.copy_note(&lo, 0).unwrap().0.starts_with(&format!("The camera keeps this at or below {}", up.name)));
        // the page's Revert all flagged takes every pair's fix at once, in every set
        assert!(app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Order));
        assert_eq!(answer(&mut app, "revert_flagged", json!({})).status, 200);
        assert!(!app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Order), "{:?}", app.acceptance_issues().iter().map(|i| (&i.name, i.kind)).collect::<Vec<_>>());
    }

    /// A memory recalled into the live settings takes both limits as the memory holds them: a memory holding them out of
    /// order leaves the live settings so, listed with its fix.
    #[test]
    fn a_memory_recalled_out_of_order_is_listed() {
        let mut app = with_pairs(3, 10);
        let m = app.dial_sets()[0];
        let (lo, up) = (setting(&app, LOWER[0]), setting(&app, UPPER[0]));
        as_opened(&mut app, |c| {
            c.sections[m].get_mut(lo.id).unwrap().put(lo.index, lo.values[22].0).unwrap();
            c.sections[m].get_mut(up.id).unwrap().put(up.index, up.values[7].0).unwrap();
        });
        let r = answer(&mut app, "recall", json!({ "memory": m, "shown": false }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        assert_eq!((at(&app, &LOWER[..1], 0), at(&app, &UPPER[..1], 0)), (vec![Some(22)], vec![Some(7)]));
        assert!(app.acceptance_issues().iter().any(|i| i.kind == IssueKind::Order && i.section == 0));
    }

    /// The page does what the window does: its change moves the other limit, its answer carries that limit's row and
    /// says what moved; its rows say the rule beforehand, as the window's do, and that a way no proof tried was not.
    #[test]
    fn the_page_moves_the_other_limit_and_says_so() {
        let mut app = with_pairs(3, 10);
        let up = setting(&app, UPPER[0]);
        let linked = app.web_linked(0, LOWER[0]).unwrap();
        let note = app.web_row(0, &linked)["copy_note"].as_str().unwrap().to_string();
        assert_eq!(note, format!("The camera keeps this at or below {0}: a value above it moves {0} up to the same value, here as on the camera.", up.name));
        let v = code(&app, LOWER[0], 20);
        let r = answer(&mut app, "set", json!({ "target": 0, "key": LOWER[0], "value": v }));
        assert_eq!(r.status, 200, "{}", String::from_utf8_lossy(&r.body));
        let j: serde_json::Value = serde_json::from_slice(&r.body).unwrap();
        assert!(j["rows"].as_array().unwrap().iter().any(|row| row["key"] == UPPER[0]), "{}", j["rows"]);
        assert!(j["message"].as_str().unwrap().contains(&format!("{} moved up to", up.name)), "{}", j["message"]);
        assert!(app.status.contains("from the web page") && app.status.contains("moved up to"), "{}", app.status);
        assert_eq!(at(&app, &UPPER, 0), vec![Some(20); 3]);
        let max = app.copy_note(&setting(&app, MAX[0]), 0).unwrap().0;
        assert!(max.contains(&format!("a value below it moves {} down to the same value here, so the file stays in that order; what the camera itself does then was not tried on it.", setting(&app, MIN[0]).name)), "{max}");
    }

    /// The fields read from a definition's JSON, as the kit writes them, drive the same move: the a1 II's definition with
    /// at_most and at_least on its ISO Range Limit ends.
    #[test]
    fn a_definition_read_from_json_moves_the_other_limit() {
        let text = crate::definitions::definitions_tests::a1_with(|v| for s in v["settings"].as_array_mut().unwrap() {
            // the pairs a later definition carries already, out, so this one pair is the definition's only
            for f in ["at_most", "at_least"] {
                s.as_object_mut().unwrap().remove(f);
            }
            if s["key"] == LOWER[0] { s["at_most"] = json!({ "setting": UPPER[0], "moves_it": true }); }
            if s["key"] == UPPER[0] { s["at_least"] = json!({ "setting": LOWER[0], "moves_it": true }); }
        });
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        app.schema = camset_editor::schema::Schema::from_text(&text).unwrap();
        app.schema_gen += 1;
        hold(&mut app, 4, 9);
        assert_eq!(app.limit_pairs().len(), 1);
        assert!(app.apply(vec![Action::Set(0, setting(&app, LOWER[0]).slot(), code(&app, LOWER[0], 12))]).is_none());
        assert_eq!(at(&app, &UPPER, 0), vec![Some(12); 3]);
    }

    /// The Exposure page shows a pair as the file holds it and, out of order, says so in its own line and draws no band
    /// for it, never the two swapped; in order, the band as before. The page's JSON carries the same line.
    #[test]
    fn the_exposure_page_marks_a_pair_out_of_order() {
        use camset_editor::stops::Side;
        let cell = |app: &App| {
            let ex = app.schema.camera.exposure.clone().unwrap();
            app.ex_cell(&ex, 0, Side::Iso, None, crate::pages::exposure::Who::You)
        };
        let ok = cell(&with_pairs(3, 10));
        assert!(ok.odd.is_empty() && ok.band.is_some(), "{:?}", ok.notes);
        let app = with_pairs(20, 8);
        let odd = cell(&app);
        let (lo, up) = (setting(&app, LOWER[0]), setting(&app, UPPER[0]));
        let shown = format!("{} to {}", App::describe(&lo, Some(code(&app, LOWER[0], 20))), App::describe(&up, Some(code(&app, UPPER[0], 8))));
        assert!(odd.notes.iter().any(|n| n.contains(&shown)), "as the file holds it: {:?}", odd.notes);
        assert!(odd.odd.iter().any(|n| n.contains("out of order, the lower end above the upper one")), "{:?}", odd.odd);
        assert!(odd.band.is_none(), "no band drawn from a pair out of order");
        assert!(App::ex_hover("ISO", &odd).contains("out of order"));
        let mut app = app;
        let r = answer(&mut app, "exposure", json!({}));
        let page: serde_json::Value = serde_json::from_slice(&r.body).unwrap();
        assert!(page["columns"].as_array().unwrap().iter().any(|c| c["cells"]["iso"]["odd"].as_array().is_some_and(|o| !o.is_empty())), "{page}");
    }
}
