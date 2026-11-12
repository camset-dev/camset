//! A group's rows as the camera's menu lists them ("As on the camera"): from each setting's place in its definition
//! (`row`, `row_at`, `under_option`, `row_tab`, `row_group`, `row_mode`, which kit/camkit/placement.py writes from the
//! camera's menu tree and the proofs). The editor knows no menu of its own: a group whose definition places none of
//! its settings stays the flat list. As on the camera a setting is shown in the tab (`camera_tab`) and the camera group
//! (`camera_group`) whose page holds its row, and a tab's groups come in the camera's order (`group_at`).

use crate::schema::Setting;
use std::collections::{HashMap, HashSet};

/// One line of a group laid out as the camera lists it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Line {
    /// A row of the camera's menu that holds no setting of its own here (a submenu, or a row whose settings bear
    /// other names): its label, how deep it is, and its labels from the group's top row, which name it for folding.
    Heading { label: String, depth: usize, path: Vec<String> },
    /// The settings row `rows[index]`, indented by `depth`. A setting alone on a row of the camera with nothing under
    /// it is that row, under its own name ("Interval Rec Mode" on "Interval Shooting": `place_words` names the row).
    Row { index: usize, depth: usize },
    /// The heading over the rows only another shooting mode's menu has (`row_mode`, its name as the definition gives
    /// it), after the group's Stills rows and in that mode's order: `mode_words` says it.
    Mode(String),
    /// The heading over the settings the definition does not place, after the camera's rows.
    More,
}

/// The words of `Line::More`.
pub const MORE: &str = "More settings in this group";

/// The words of a `Line::Mode` heading: "In Movie mode".
pub fn mode_words(mode: &str) -> String {
    format!("In {mode} mode")
}

/// The group that shows `s` while the rows are laid out as on the camera: the camera group whose page holds its row
/// (`row_group`), else its own. The flat list, Compare and the exports keep `group`.
pub fn camera_group(s: &Setting) -> &str {
    s.row_group.as_deref().filter(|g| !g.is_empty() && s.placed()).unwrap_or(&s.group)
}

/// The tab that shows `s` while the rows are laid out as on the camera: the tab whose menu holds its row (`row_tab`:
/// the Custom Key cells a definition keeps in another tab sit on the key settings' row), else its own. The flat list,
/// Compare and the exports keep `tab`.
pub fn camera_tab(s: &Setting) -> &str {
    s.row_tab.as_deref().filter(|t| !t.is_empty() && s.placed()).unwrap_or(&s.tab)
}

/// Where a group comes in its tab as on the camera: the number of the first of its rows the definition places
/// (`row_at`, counted over the tab's rows with the other modes' slotted in), None when it places none.
pub fn group_at<'a>(settings: impl IntoIterator<Item = &'a Setting>) -> Option<i64> {
    settings.into_iter().filter(|s| s.placed()).map(|s| s.row_at[0]).min()
}

/// A tab's groups' sort key as on the camera: the ones it places rows of by `group_at`, a page an option opens
/// (`Setting::on_page`) after the group of its owner's row, by the option's place (PP1, PP2… PP10), then the others by
/// their place in the definition (`order`, the first setting's), each by name last.
pub fn group_key<'a>(order: i64, name: &str, settings: impl IntoIterator<Item = &'a Setting>) -> (bool, i64, i64, String) {
    let settings: Vec<&Setting> = settings.into_iter().collect();
    let page = settings.iter().filter_map(|s| s.page_prefix().map(|n| s.row_at[n - 1])).min().unwrap_or(-1);
    match group_at(settings) {
        Some(at) => (false, at, page, name.to_string()),
        None => (true, order, page, name.to_string()),
    }
}

/// Lower-case letters and digits only, as the kit compares menu labels (camkit.placement.norm).
pub fn norm(s: &str) -> String {
    s.to_lowercase().chars().filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit()).collect()
}

/// Whether `s` is its row's own setting: placed, named as the row, and not the sub-choice of an option.
pub fn is_own(s: &Setting) -> bool {
    s.placed() && s.under_option.is_none() && s.row.last().is_some_and(|l| norm(l) == norm(&s.name))
}

/// The row's own setting among `rows` (each a row of linked settings, the first leading) that `s` is a sub-choice
/// of, when `s` is one and its row's setting is there.
pub fn owner<'a>(rows: impl IntoIterator<Item = &'a Setting>, s: &Setting) -> Option<&'a Setting> {
    s.under_option.as_ref()?;
    rows.into_iter().find(|o| is_own(o) && o.same_row(s))
}

/// The row's own setting among `rows` that shows `s` beside its option in the detail panel, so that `s` is no row of
/// its own as on the camera: `s` a sub-choice (`owner`) of an option its owner lists, and not one of the choices the
/// owner's option tree nests already (`Setting::nests_option`). None for any other setting, which stays a row.
pub fn beside_owner<'a>(rows: impl IntoIterator<Item = &'a Setting>, s: &Setting) -> Option<&'a Setting> {
    let opt = s.under_option.as_ref()?;
    owner(rows, s).filter(|o| o.values.iter().any(|(_, l)| l == opt) && !o.nests_option(opt))
}

/// The settings of `among` shown beside `own`'s options (`beside_owner`: the sub-choices of its options, but those its
/// option tree nests already), each with the option: in the order `own` lists its options, an option's several
/// sub-choices (White Balance's fine-tune, Creative Look's parameters) by their `order` in the definition, then name.
pub fn sub_choices<'a>(own: &Setting, among: impl IntoIterator<Item = &'a Setting>) -> Vec<(&'a Setting, String)> {
    if !is_own(own) {
        return Vec::new();
    }
    let mut out: Vec<(usize, &Setting, String)> = among.into_iter()
        // a setting on the page an option opens is no choice beside it (`pages`)
        .filter(|s| s.same_row(own) && s.key != own.key && !s.on_page())
        .filter_map(|s| {
            let opt = s.under_option.as_ref().filter(|o| !own.nests_option(o))?;
            let at = own.values.iter().position(|(_, l)| l == opt)?;
            Some((at, s, opt.clone()))
        })
        .collect();
    out.sort_by(|a, b| (a.0, a.1.order, &a.1.name).cmp(&(b.0, b.1.order, &b.1.name)));
    // one setting kept in several records is one choice, as it is one row
    let mut seen: Vec<&Setting> = Vec::new();
    out.retain(|(_, s, _)| {
        let new = !seen.iter().any(|o| o.links_with(s));
        seen.push(s);
        new
    });
    out.into_iter().map(|(_, s, o)| (s, o)).collect()
}

/// A page of rows an option of a row opens on the camera (Picture Profile's PP1: Black Level, Gamma, Black Gamma >
/// Range, Level…), from the settings on it (`Setting::on_page`): the option, the group that holds the page's rows as
/// on the camera (`camera_group`), a setting on it to open the page by, and how many settings it holds.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Page {
    pub option: String,
    pub group: String,
    pub key: String,
    pub count: usize,
}

/// The pages `own`'s options open (`Page`), from the settings of `among` on them, in the order `own` lists its
/// options; none unless `own` is its row's own setting. Its options' sub-choices are not among them (`sub_choices`).
pub fn pages<'a>(own: &Setting, among: impl IntoIterator<Item = &'a Setting>) -> Vec<Page> {
    if !is_own(own) {
        return Vec::new();
    }
    let mut out: Vec<(usize, Page)> = Vec::new();
    for s in among.into_iter().filter(|s| s.page_of(own)) {
        let Some(opt) = s.under_option.as_deref() else { continue };
        let Some(at) = own.values.iter().position(|(_, l)| l == opt) else { continue };
        match out.iter_mut().find(|(_, p)| p.option == opt) {
            Some((_, p)) => p.count += 1,
            None => out.push((at, Page { option: opt.to_string(), group: camera_group(s).to_string(), key: s.key.clone(), count: 1 })),
        }
    }
    out.sort_by_key(|(at, _)| *at);
    out.into_iter().map(|(_, p)| p).collect()
}

/// The page of `own`'s option `option` (`pages`), if it opens one.
pub fn page_for<'a>(pages: &'a [Page], option: &str) -> Option<&'a Page> {
    pages.iter().find(|p| p.option == option)
}

/// A setting's name without the copy it is of (" (stills)", " (movie)"), as the kit compares names (`norm`): the
/// stills and movie copies of a page's parameter are one row of it.
fn base_name(name: &str) -> String {
    let n = name.trim();
    let n = n.strip_suffix("(stills)").or_else(|| n.strip_suffix("(movie)")).unwrap_or(n);
    norm(n)
}

/// A row's sort key in its group: the camera's position of its row (`row_at`), then, on one row, its own setting
/// first, the sub-choices of its options in the order the own setting lists them, then the other settings on it;
/// the rows of a submenu after the row that opens it; the group's order in the definition last.
fn key(rows: &[Vec<Setting>], i: usize) -> Vec<i64> {
    let s = &rows[i][0];
    let mut k = s.row_at.clone();
    if is_own(s) {
        k.extend([-3, 0]);
    } else if let Some(opt) = &s.under_option {
        let at = owner(rows.iter().map(|r| &r[0]), s).and_then(|o| o.values.iter().position(|(_, l)| l == opt));
        k.extend([-2, at.map_or(i64::MAX, |a| a as i64)]);
    } else {
        k.extend([-1, 0]);
    }
    k.push(i as i64);
    k
}

/// The group's rows (each a row of linked settings, the first leading) laid out as the camera lists them: the rows
/// its definition places in the camera's order, a submenu's rows indented under it, a row with no setting of its own
/// as a heading over its settings; an option's sub-choice is no row when its row's own setting is in the group
/// (`beside_owner`: the detail panel shows it beside the option, as the camera opens it with Right), else under the
/// row's heading; a setting on the page an option opens (`Setting::on_page`) is laid out as that page, its owner's
/// row and the option left out (kept as the top heading when the group holds the pages of several options), its
/// rows' headings over their rows, the stills and movie copies of one parameter side by side; then the rows only another
/// mode's menu has, under `Line::Mode`, mode by mode (the one whose first row comes first, first); then, under
/// `Line::More`, the rows it does not place, as they came. A group whose definition places none of its rows comes
/// back as it is, with no heading.
pub fn lay_out(rows: &[Vec<Setting>]) -> Vec<Line> {
    let placed: Vec<usize> = (0..rows.len()).filter(|&i| rows[i][0].placed()).collect();
    if placed.is_empty() {
        return (0..rows.len()).map(|index| Line::Row { index, depth: 0 }).collect();
    }
    // a sub-choice shown beside its owner's option is no row (its owner, placed, stays one)
    let placed: Vec<usize> = placed.into_iter().filter(|&i| beside_owner(rows.iter().map(|r| &r[0]), &rows[i][0]).is_none()).collect();
    // the page's rows without the labels leading to it: its owner's row and, when it is the group's one page, the option
    let mut lead: Vec<(&[String], &[i64])> = Vec::new();
    for &i in &placed {
        let s = &rows[i][0];
        if let Some(n) = s.page_prefix() {
            if !lead.contains(&(&s.row[..n], &s.row_at[..n])) {
                lead.push((&s.row[..n], &s.row_at[..n]));
            }
        }
    }
    let one = lead.len() == 1;
    let strip = |s: &Setting| s.page_prefix().map_or(0, |n| if one { n } else { n - 1 });
    let mut lines = Vec::new();
    nest(rows, placed.iter().copied().filter(|&i| rows[i][0].row_mode.is_none()).collect(), None, &strip, &mut lines);
    let mut modes: Vec<(i64, &str)> = Vec::new();
    for &i in &placed {
        if let Some(m) = rows[i][0].row_mode.as_deref() {
            match modes.iter_mut().find(|(_, x)| *x == m) {
                Some(e) => e.0 = e.0.min(rows[i][0].row_at[0]),
                None => modes.push((rows[i][0].row_at[0], m)),
            }
        }
    }
    modes.sort();
    for (_, m) in modes {
        lines.push(Line::Mode(m.to_string()));
        nest(rows, placed.iter().copied().filter(|&i| rows[i][0].row_mode.as_deref() == Some(m)).collect(), Some(m), &strip, &mut lines);
    }
    let rest: Vec<usize> = (0..rows.len()).filter(|&i| !rows[i][0].placed()).collect();
    if !rest.is_empty() {
        lines.push(Line::More);
        lines.extend(rest.into_iter().map(|index| Line::Row { index, depth: 0 }));
    }
    lines
}

/// The rows `placed` of one menu (the Stills menu's, or `mode`'s) nested as the camera lists them, onto `lines`; a
/// mode's headings are named for folding after the mode, so they fold apart from the Stills rows of the same labels.
/// `strip(s)` is how many of a setting's labels lead to the page it is on and are left out (`lay_out`).
fn nest(rows: &[Vec<Setting>], placed: Vec<usize>, mode: Option<&str>, strip: &dyn Fn(&Setting) -> usize, lines: &mut Vec<Line>) {
    type Node = (Vec<i64>, Vec<String>);
    let node = |s: &Setting, n: usize| -> Node { let k = strip(s); (s.row_at[k..k + n].to_vec(), s.row[k..k + n].to_vec()) };
    let len = |s: &Setting| s.row.len() - strip(s);
    // which rows sit on each of the camera's rows (a page's stills and movie copies of one parameter as one), and
    // which have rows deeper down
    let mut here: HashMap<Node, HashSet<String>> = HashMap::new();
    let mut deeper: HashSet<Node> = HashSet::new();
    for &i in &placed {
        let s = &rows[i][0];
        here.entry(node(s, len(s))).or_default().insert(if s.on_page() { base_name(&s.name) } else { s.key.clone() });
        for n in 1..len(s) {
            deeper.insert(node(s, n));
        }
    }
    let mut order = placed;
    order.sort_by_cached_key(|&i| key(rows, i));
    let mut open: Vec<(i64, String)> = Vec::new();          // the camera's rows open above the next line
    let mut row_here: Option<Vec<(i64, String)>> = None;          // the page's row drawn as its setting's own line
    for i in order {
        let s = &rows[i][0];
        let k = strip(s);
        let path: Vec<(i64, String)> = s.row_at[k..].iter().copied().zip(s.row[k..].iter().cloned()).collect();
        let common = open.iter().zip(&path).take_while(|(a, b)| a == b).count();
        open.truncate(common);
        if common == path.len() {
            // the other copy of a page's parameter beside the first, else a row under the one open
            let depth = if row_here.as_ref() == Some(&path) { path.len() - 1 } else { path.len() };
            lines.push(Line::Row { index: i, depth });
            continue;
        }
        row_here = None;
        for level in common..path.len() {
            let label = path[level].1.clone();
            let labels: Vec<String> = mode.map(str::to_string).into_iter().chain(path[..=level].iter().map(|p| p.1.clone())).collect();
            open.push(path[level].clone());
            let mine = node(s, level + 1);
            if level + 1 < path.len() {
                lines.push(Line::Heading { label, depth: level, path: labels });
            } else if is_own(s) || ((s.under_option.is_none() || s.on_page()) && here.get(&mine).is_some_and(|h| h.len() == 1) && !deeper.contains(&mine)) {
                // its own setting, or one alone on it with no rows under it: the row itself
                lines.push(Line::Row { index: i, depth: level });
                if s.on_page() {
                    row_here = Some(path.clone());
                }
            } else {
                lines.push(Line::Heading { label, depth: level, path: labels });
                lines.push(Line::Row { index: i, depth: level + 1 });
            }
        }
    }
}

/// The rows of `lines` in the order they are drawn.
pub fn order(lines: &[Line]) -> Vec<usize> {
    lines.iter().filter_map(|l| match l { Line::Row { index, .. } => Some(*index), _ => None }).collect()
}

/// Which lines a folded heading hides: `folded(path)` says whether the heading of those labels is folded. Each line's
/// flag, true when one of the headings above it is folded.
pub fn hidden(lines: &[Line], folded: impl Fn(&[String]) -> bool) -> Vec<bool> {
    let mut out = Vec::with_capacity(lines.len());
    let mut under: Option<usize> = None;          // the depth of the folded heading lines are hidden below
    for l in lines {
        let depth = match l { Line::Heading { depth, .. } | Line::Row { depth, .. } => *depth, Line::Mode(_) | Line::More => 0 };
        if under.is_some_and(|d| depth <= d) || matches!(l, Line::Mode(_) | Line::More) {
            under = None;
        }
        out.push(under.is_some());
        if under.is_none() {
            if let Line::Heading { path, depth, .. } = l {
                if folded(path) {
                    under = Some(*depth);
                }
            }
        }
    }
    out
}

/// The headings above line `at` (their labels from the top row), the nearest last: the ones to unfold to show it.
pub fn headings_above(lines: &[Line], at: usize) -> Vec<Vec<String>> {
    let mut depth = match lines.get(at) { Some(Line::Heading { depth, .. } | Line::Row { depth, .. }) => *depth, _ => return Vec::new() };
    let mut out = Vec::new();
    for l in lines[..at].iter().rev() {
        match l {
            Line::Mode(_) | Line::More => break,
            Line::Heading { depth: d, path, .. } if *d < depth => {
                out.push(path.clone());
                depth = *d;
            }
            Line::Row { depth: d, .. } if *d < depth => depth = *d,
            _ => {}
        }
        if depth == 0 {
            break;
        }
    }
    out.reverse();
    out
}

/// "Drive Mode > Bracket Settings", and the option a sub-choice belongs to: where a placed setting sits on the
/// camera, in words, its row's tab and group first when the row is in another tab (`row_tab`); None when the
/// definition does not place it.
pub fn place_words(s: &Setting) -> Option<String> {
    if !s.placed() {
        return None;
    }
    let row = match s.row_tab.as_deref().filter(|t| !t.is_empty() && *t != s.tab) {
        Some(tab) => format!("{tab} > {} > {}", camera_group(s), s.row.join(" > ")),
        None => s.row.join(" > "),
    };
    let mode = s.row_mode.as_deref().map(|m| format!(" ({})", mode_words(m))).unwrap_or_default();
    Some(match &s.under_option {
        Some(o) if s.on_page() => format!("On the camera: {row}{mode}, on the page its option {o} opens"),
        Some(o) => format!("On the camera: {row}{mode}, the choice for its option {o}"),
        None => format!("On the camera: {row}{mode}"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(key: &str, name: &str, row: &[&str], at: &[i64], under: Option<&str>, values: &[&str]) -> Setting {
        serde_json::from_value(serde_json::json!({
            "key": key, "area": "global", "id": 1, "name": name, "tab": "Shooting", "group": "Drive Mode",
            "order": 46, "row": row, "row_at": at, "under_option": under, "in_sets": false, "scalar": true,
            "values": values.iter().enumerate().map(|(i, l)| serde_json::json!([i, l])).collect::<Vec<_>>(),
        })).unwrap()
    }

    fn rows(list: Vec<Setting>) -> Vec<Vec<Setting>> {
        list.into_iter().map(|s| vec![s]).collect()
    }

    /// The owner's case (2026-11-06): Drive Mode first, the continuous speed under it as the choice for Continuous
    /// Shooting, the submenus as headings with their rows under them, and what the definition does not place last.
    #[test]
    fn a_group_as_on_the_camera() {
        let r = rows(vec![
            s("a", "Unplaced", &[], &[], None, &[]),
            s("b", "Hi(E-Shutter)", &["Cont. Shooting Speed", "Hi (E-Shutter)"], &[28, 1], None, &[]),
            s("c", "Speed", &["Drive Mode"], &[26], Some("Continuous Shooting"), &["Hi", "Lo"]),
            s("d", "Drive Mode", &["Drive Mode"], &[26], None, &["Single Shooting", "Continuous Shooting", "Self-timer"]),
            s("e", "Hi+(E-Shutter)", &["Cont. Shooting Speed", "Hi+ (E-Shutter)"], &[28, 0], None, &[]),
            s("f", "Delay", &["Drive Mode"], &[26], Some("Self-timer"), &[]),
            s("g", "Interval Rec Mode", &["Interval Shoot Func.", "Interval Shooting"], &[33, 0], None, &[]),
            s("h", "Limit: Lo", &["Drive Mode Limit"], &[27], None, &[]),
            s("i", "Limit: Hi", &["Drive Mode Limit"], &[27], None, &[]),
        ]);
        let lines = lay_out(&r);
        let row = |index, depth| Line::Row { index, depth };
        let head = |label: &str, depth, path: &[&str]| Line::Heading { label: label.into(), depth, path: path.iter().map(|x| x.to_string()).collect() };
        assert_eq!(lines, vec![
            row(3, 0),          // its sub-choices (2, 5) beside its options in the detail panel, no rows
            head("Drive Mode Limit", 0, &["Drive Mode Limit"]), row(7, 1), row(8, 1),
            head("Cont. Shooting Speed", 0, &["Cont. Shooting Speed"]), row(4, 1), row(1, 1),
            head("Interval Shoot Func.", 0, &["Interval Shoot Func."]), row(6, 1),          // alone on Interval Shooting: that row
            Line::More, row(0, 0),
        ]);
        assert_eq!(order(&lines), vec![3, 7, 8, 4, 1, 6, 0]);
        // the sub-choices of Drive Mode, in the order it lists its options
        let subs: Vec<(&str, String)> = sub_choices(&r[3][0], r.iter().map(|x| &x[0])).into_iter().map(|(s, o)| (s.key.as_str(), o)).collect();
        assert_eq!(subs, vec![("c", "Continuous Shooting".to_string()), ("f", "Self-timer".to_string())]);
        assert_eq!(owner(r.iter().map(|x| &x[0]), &r[2][0]).map(|o| o.key.as_str()), Some("d"));
        assert!(sub_choices(&r[2][0], r.iter().map(|x| &x[0])).is_empty(), "a sub-choice has none of its own");
        assert_eq!(place_words(&r[2][0]).as_deref(), Some("On the camera: Drive Mode, the choice for its option Continuous Shooting"));
        assert_eq!(place_words(&r[0][0]), None);
    }

    /// The rows only the Movie menu has come after the group's Stills rows, under the mode's name and in its order;
    /// their headings fold apart from the Stills rows of the same labels, and unfolding stops at the mode's heading.
    #[test]
    fn a_modes_rows_after_the_stills_rows() {
        let movie = |mut x: Setting| { x.row_mode = Some("Movie".into()); x };
        let r = rows(vec![
            movie(s("a", "Rec Frame Rate", &["S&Q Settings", "Frame Rate Settings", "Rec Frame Rate"], &[5, 0, 1], None, &[])),
            s("b", "Aspect Ratio", &["Aspect Ratio"], &[2], None, &[]),
            movie(s("c", "Log Shooting", &["Log Shooting Setting", "Log Shooting"], &[7, 0], None, &[])),
            s("d", "Unplaced", &[], &[], None, &[]),
            movie(s("e", "Frame Rate", &["S&Q Settings", "Frame Rate Settings", "Frame Rate"], &[5, 0, 0], None, &[])),
            s("f", "Shading Comp.", &["Lens Compensation", "Shading Comp."], &[14, 0], None, &[]),
        ]);
        let lines = lay_out(&r);
        let row = |index, depth| Line::Row { index, depth };
        let head = |label: &str, depth, path: &[&str]| Line::Heading { label: label.into(), depth, path: path.iter().map(|x| x.to_string()).collect() };
        assert_eq!(lines, vec![
            row(1, 0), head("Lens Compensation", 0, &["Lens Compensation"]), row(5, 1),
            Line::Mode("Movie".into()),
            head("S&Q Settings", 0, &["Movie", "S&Q Settings"]), head("Frame Rate Settings", 1, &["Movie", "S&Q Settings", "Frame Rate Settings"]),
            row(4, 2), row(0, 2),
            head("Log Shooting Setting", 0, &["Movie", "Log Shooting Setting"]), row(2, 1),
            Line::More, row(3, 0),
        ]);
        assert_eq!(mode_words("Movie"), "In Movie mode");
        assert_eq!(place_words(&r[0][0]).as_deref(), Some("On the camera: S&Q Settings > Frame Rate Settings > Rec Frame Rate (In Movie mode)"));
        // a folded Stills heading hides nothing past the mode's heading; the headings above a mode's row are its own
        let fold = |p: &[String]| p == ["Lens Compensation".to_string()];
        assert_eq!(hidden(&lines, fold), vec![false, false, true, false, false, false, false, false, false, false, false, false]);
        assert_eq!(headings_above(&lines, 6).len(), 2);
        assert!(headings_above(&lines, 4).is_empty());
    }

    /// As on the camera a setting is in the camera group whose page holds its row, and a tab's groups follow the
    /// camera's order: the ones with placed rows by their first row, the others after, by the definition's order.
    #[test]
    fn the_camera_group_and_its_place() {
        let mut held = s("a", "Shoot Mode", &["Reg. Custom Shoot Set", "Recall Custom hold 1", "Shoot Mode"], &[33, 0, 0], None, &[]);
        held.group = "Recall Custom hold 1".into();
        held.row_group = Some("Shooting Mode".into());
        assert_eq!(camera_group(&held), "Shooting Mode");
        let mut unplaced = held.clone();
        unplaced.row.clear();
        unplaced.row_at.clear();
        assert_eq!(camera_group(&unplaced), "Recall Custom hold 1", "no row: its own group");
        let other = s("b", "Drive Mode", &["Drive Mode"], &[34], None, &[]);
        assert_eq!(camera_group(&other), "Drive Mode");
        assert_eq!(group_at([&held, &other]), Some(33));
        assert_eq!(group_at([&unplaced]), None);
        let mut keys = [group_key(1500, "My Menu", [&unplaced]), group_key(46, "Drive Mode", [&other]), group_key(9000, "Shooting Mode", [&held])];
        keys.sort();
        assert_eq!(keys.iter().map(|k| k.3.as_str()).collect::<Vec<_>>(), ["Shooting Mode", "Drive Mode", "My Menu"]);
    }

    /// A row in another tab (`row_tab`) shows the setting in that tab, and its words name the tab and group; without
    /// a row the setting stays in its own tab whatever it says.
    #[test]
    fn a_row_in_another_tab() {
        let mut cell = s("a", "Custom Key (Movie): AEL Button", &["Custom Key/Dial Set."], &[5], None, &[]);
        cell.row_tab = Some("Setup".into());
        cell.row_group = Some("Operation Customize".into());
        assert_eq!((camera_tab(&cell), camera_group(&cell)), ("Setup", "Operation Customize"));
        assert_eq!(place_words(&cell).as_deref(), Some("On the camera: Setup > Operation Customize > Custom Key/Dial Set."));
        let mut unplaced = cell.clone();
        unplaced.row.clear();
        unplaced.row_at.clear();
        assert_eq!(camera_tab(&unplaced), "Shooting", "no row: its own tab");
        let own = s("b", "Drive Mode", &["Drive Mode"], &[26], None, &[]);
        assert_eq!(camera_tab(&own), "Shooting");
    }

    /// The owner's case (2026-11-07): an option's sub-choices (two under B, one under A) are no rows as on the camera,
    /// only their row's own setting is; the detail panel lists them beside their option, an option's several in their
    /// order in the definition, then by name. The flat list keeps every row. A choice the option tree nests already,
    /// or one of an option the owner does not list, stays a row.
    #[test]
    fn sub_choices_beside_their_option_not_rows() {
        let mut b2 = s("b2", "B second", &["Look"], &[5], Some("B"), &[]);
        b2.order = 50;
        let mut b1 = s("b1", "B first", &["Look"], &[5], Some("B"), &[]);
        b1.order = 49;
        let mut b3 = s("b3", "Another B first", &["Look"], &[5], Some("B"), &[]);
        b3.order = 50;
        let r = rows(vec![
            b2, s("a1", "A only", &["Look"], &[5], Some("A"), &[]),
            s("own", "Look", &["Look"], &[5], None, &["A", "B"]), b1, b3,
            s("x", "Stray", &["Look"], &[5], Some("C"), &[]),
        ]);
        let lines = lay_out(&r);
        assert_eq!(lines, vec![Line::Row { index: 2, depth: 0 }, Line::Row { index: 5, depth: 1 }], "the owner, and the stray choice of an option it does not list");
        let firsts = || r.iter().map(|x| &x[0]);
        let subs: Vec<(&str, String)> = sub_choices(&r[2][0], firsts()).into_iter().map(|(s, o)| (s.key.as_str(), o)).collect();
        assert_eq!(subs, vec![("a1", "A".into()), ("b1", "B".into()), ("b3", "B".into()), ("b2", "B".into())]);
        let under_b: Vec<&str> = subs.iter().filter(|(_, o)| o == "B").map(|(k, _)| *k).collect();
        assert_eq!(under_b, ["b1", "b3", "b2"], "B's in their order, then by name");
        assert_eq!(beside_owner(firsts(), &r[0][0]).map(|o| o.key.as_str()), Some("own"));
        assert!(beside_owner(firsts(), &r[5][0]).is_none() && beside_owner(firsts(), &r[2][0]).is_none());
        // without its owner (a search left it out, or another group holds it) a sub-choice is a row again
        let alone = rows(vec![s("a1", "A only", &["Look"], &[5], Some("A"), &[])]);
        assert!(order(&lay_out(&alone)) == [0]);
        // an option tree that nests the option shows its choices itself: the setting under it stays a row
        let mut nested = r.clone();
        nested[2][0].values = vec![(0, "A".into()), (1, "B: 1".into()), (2, "B: 2".into())];
        nested[2][0].option_tree = serde_json::from_value(serde_json::json!([{ "label": "A", "value": 0 }, { "label": "B", "options": [[1, "1"], [2, "2"]] }])).unwrap();
        assert!(nested[2][0].nests_option("B"));
        assert_eq!(order(&lay_out(&nested)), vec![2, 0, 3, 4, 5], "B's settings stay rows; A's is beside its option");
    }

    /// The owner's case (2026-11-07): Right on an option of Picture Profile opens a whole page of rows. A setting on
    /// it (`row` going on past its option) is no choice beside the option: its page is laid out in its own group, the
    /// owner's row and the option left out, its rows' headings over their rows (two levels deep), the stills and movie
    /// copies of one parameter side by side; the option links to the page (`pages`).
    #[test]
    fn a_page_under_an_option() {
        let on = |key: &str, name: &str, row: &[&str], at: &[i64]| {
            let mut x = s(key, name, &[&["Profile", "P1"][..], row].concat(), &[&[29, 1][..], at].concat(), Some("P1"), &[]);
            x.group = "Profile P1".into();
            x.row_group = Some("Profile P1".into());
            x
        };
        let page = rows(vec![
            on("bl", "Black Level", &["Black Level"], &[0]),
            on("bls", "Black Level (stills)", &["Black Level"], &[0]),
            on("bgl", "Black Gamma Level", &["Black Gamma", "Level"], &[2, 1]),
            on("bgr", "Black Gamma Range", &["Black Gamma", "Range"], &[2, 0]),
            on("km", "Knee Mode", &["Knee", "Mode"], &[3, 0]),
            on("kmp", "Knee Auto Set Max Point", &["Knee", "Auto Set", "Max Point"], &[3, 1, 0]),
            on("kmps", "Knee Auto Set Max Point (stills)", &["Knee", "Auto Set", "Max Point"], &[3, 1, 0]),
        ]);
        assert!(page.iter().all(|r| r[0].on_page()) && page[0][0].page_prefix() == Some(2));
        let row = |index, depth| Line::Row { index, depth };
        let head = |label: &str, depth, path: &[&str]| Line::Heading { label: label.into(), depth, path: path.iter().map(|x| x.to_string()).collect() };
        assert_eq!(lay_out(&page), vec![
            row(0, 0), row(1, 0),          // the stills copy beside it, not under it
            head("Black Gamma", 0, &["Black Gamma"]), row(3, 1), row(2, 1),
            head("Knee", 0, &["Knee"]), row(4, 1), head("Auto Set", 1, &["Knee", "Auto Set"]), row(5, 2), row(6, 2),
        ]);
        assert_eq!(place_words(&page[2][0]).as_deref(), Some("On the camera: Profile > P1 > Black Gamma > Level, on the page its option P1 opens"));
        // the owner's row: P2's sub-choice beside its option, P1's page no choice of it, and P1 opens the page
        let own = s("own", "Profile", &["Profile"], &[29], None, &["Off", "P1", "P2"]);
        let fine = s("fine", "Fine", &["Profile"], &[29], Some("P2"), &[]);
        let all: Vec<Setting> = std::iter::once(own.clone()).chain([fine.clone()]).chain(page.iter().map(|r| r[0].clone())).collect();
        let subs: Vec<&str> = sub_choices(&own, &all).into_iter().map(|(x, _)| x.key.as_str()).collect();
        assert_eq!(subs, ["fine"]);
        assert!(all[2..].iter().all(|x| owner(&all, x).is_none() && beside_owner(&all, x).is_none() && x.page_of(&own)));
        let pages = pages(&own, &all);
        assert_eq!(pages, vec![Page { option: "P1".into(), group: "Profile P1".into(), key: "bl".into(), count: 7 }]);
        assert!(page_for(&pages, "P1").is_some() && page_for(&pages, "P2").is_none());
        assert!(super::pages(&fine, &all).is_empty() && !fine.on_page(), "a sub-choice opens no page, nor is on one");
        // the pages of two options in one group keep the option as their top heading
        let mut two = page.clone();
        let mut p2 = two[0][0].clone();
        (p2.key, p2.under_option, p2.row[1], p2.row_at[1]) = ("p2".into(), Some("P2".into()), "P2".into(), 2);
        two.push(vec![p2]);
        let lines = lay_out(&two);
        assert_eq!((&lines[0], lines.last()), (&head("P1", 0, &["P1"]), Some(&row(7, 1))), "{lines:?}");
    }

    /// Without its own setting (a search left it out) a row is a heading over the settings on it.
    #[test]
    fn a_row_without_its_own_setting_is_a_heading() {
        let r = rows(vec![s("c", "Speed", &["Drive Mode"], &[26], Some("Continuous Shooting"), &[])]);
        assert_eq!(lay_out(&r), vec![
            Line::Heading { label: "Drive Mode".into(), depth: 0, path: vec!["Drive Mode".into()] },
            Line::Row { index: 0, depth: 1 },
        ]);
    }

    /// A definition that places nothing: the rows as they came, no heading.
    #[test]
    fn nothing_placed_is_the_flat_list() {
        let r = rows(vec![s("a", "A", &[], &[], None, &[]), s("b", "B", &[], &[], None, &[])]);
        assert_eq!(lay_out(&r), vec![Line::Row { index: 0, depth: 0 }, Line::Row { index: 1, depth: 0 }]);
    }

    /// A folded heading hides what is under it, down to the next line as shallow; the headings above a line are the
    /// ones to unfold to show it.
    #[test]
    fn folding_hides_a_headings_rows() {
        let r = rows(vec![
            s("a", "Exposure Smoothing", &["Bracket Settings", "Focus Bracket Settings", "Exposure Smoothing"], &[32, 3, 1], None, &[]),
            s("b", "Selftimer during Bracket", &["Bracket Settings", "Selftimer during Bracket"], &[32, 1], None, &[]),
            s("c", "Interval Rec Mode", &["Interval Shoot Func.", "Interval Shooting"], &[33, 0], None, &[]),
        ]);
        let lines = lay_out(&r);
        assert_eq!(lines.len(), 6, "{lines:?}");          // Bracket Settings, b, Focus Bracket Settings, a, Interval Shoot Func., c
        let fold = |p: &[String]| p == ["Bracket Settings".to_string(), "Focus Bracket Settings".to_string()];
        assert_eq!(hidden(&lines, fold), vec![false, false, false, true, false, false]);
        let all = |p: &[String]| p.len() == 1 && p[0] == "Bracket Settings";
        assert_eq!(hidden(&lines, all), vec![false, true, true, true, false, false]);
        assert_eq!(headings_above(&lines, 3), vec![vec!["Bracket Settings".to_string()], vec!["Bracket Settings".to_string(), "Focus Bracket Settings".to_string()]]);
        assert!(headings_above(&lines, 0).is_empty());
    }
}
