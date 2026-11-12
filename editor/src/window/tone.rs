//! The window's colours, taken from the theme in use (`ui.visuals()`), so the light theme is as readable
//! as the dark one. Every colour the window draws with comes from here or from egui's own visuals; a
//! fixed colour on a fixed background stays readable in only one of the two themes.
//!
//! Orange is kept for edits (yours, not yet saved) and nothing else; a difference between two files
//! or two columns is a pale amber fill, the same idea in both themes.

use eframe::egui::{Color32, Stroke, Visuals};

/// The window's theme as the app installs it: egui's dark or light visuals, with the body text a little softer than
/// egui's, and, on the light theme, an outline round a control at rest (a checkbox, a radio button, a text field, a
/// button), which egui leaves without one there: an unticked box is then seen on the light window.
pub fn visuals(light: bool) -> Visuals {
    let mut v = if light { Visuals::light() } else { Visuals::dark() };
    v.override_text_color = None;
    v.widgets.noninteractive.fg_stroke.color = if light { Color32::from_rgb(85, 90, 100) } else { Color32::from_rgb(175, 180, 190) };
    if light {
        v.widgets.inactive.bg_stroke = Stroke::new(1.0_f32, Color32::from_gray(130));
    }
    v
}

/// `a` moved towards `b` by `t` (0: a, 1: b), alpha kept opaque.
pub fn mix(a: Color32, b: Color32, t: f32) -> Color32 {
    let l = |x: u8, y: u8| (x as f32 + (y as f32 - x as f32) * t).round().clamp(0.0, 255.0) as u8;
    Color32::from_rgb(l(a.r(), b.r()), l(a.g(), b.g()), l(a.b(), b.b()))
}

/// Quiet text a person must still read (a caption, a hint, a note under a setting): egui's own weak colour is
/// half-way to the window's fill, about 2:1 on the light theme, so the window uses this one, a little apart from the
/// body text and readable (4.5:1) on the window, the panels, the tiles and the boxed notes. egui's weak colour is
/// kept for what is greyed out on purpose (a setting another one turns off, a value of another camera's file) and
/// for lines that only decorate.
pub fn weak(v: &Visuals) -> Color32 {
    mix(v.text_color(), v.panel_fill, if v.dark_mode { 0.15 } else { 0.08 })
}

/// One colour for the dark theme and one for the light theme.
fn pick(v: &Visuals, dark: Color32, light: Color32) -> Color32 {
    if v.dark_mode { dark } else { light }
}

/// An edit: text and marks of a value you changed and have not saved yet. The theme's warning colour
/// (orange), darkened on the light theme so it reads on white.
pub fn edit(v: &Visuals) -> Color32 {
    if v.dark_mode { v.warn_fg_color } else { mix(v.warn_fg_color, Color32::BLACK, 0.25) }
}

/// The fill behind a value that differs from the column it is compared with: a pale amber.
pub fn differs(v: &Visuals) -> Color32 {
    mix(v.panel_fill, Color32::from_rgb(230, 180, 70), if v.dark_mode { 0.22 } else { 0.28 })
}

/// A difference in the change map beside Compare (stronger than the cell fill, weaker than an edit).
pub fn differs_mark(v: &Visuals) -> Color32 {
    mix(v.panel_fill, Color32::from_rgb(230, 180, 70), 0.65)
}

/// Text on an `edit` fill (the count of edits on a tab or a group).
pub fn on_edit(v: &Visuals) -> Color32 {
    pick(v, Color32::BLACK, Color32::WHITE)
}

/// Something went well (a checked firmware, a confirmed write).
pub fn ok(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(90, 190, 110), Color32::from_rgb(25, 125, 55))
}

/// Something failed or is refused.
pub fn bad(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(235, 90, 70), Color32::from_rgb(190, 40, 30))
}

/// A caution that is not an edit: an unchecked firmware, a value the camera may refuse. Sand yellow, so it is
/// not taken for the orange of an edit.
pub fn caution(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(225, 195, 105), Color32::from_rgb(130, 95, 0))
}

/// A quiet note in colour (where a setting applies, how it was proved).
pub fn note(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(170, 190, 220), Color32::from_rgb(55, 85, 140))
}

/// Records and settings the editor has no name for yet (Expert pages).
pub fn unnamed(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(230, 190, 90), Color32::from_rgb(140, 100, 0))
}

/// File B in Compare.
pub fn file_b(v: &Visuals) -> Color32 {
    pick(v, Color32::LIGHT_BLUE, Color32::from_rgb(20, 95, 170))
}

/// The base file of a three-way compare.
pub fn file_base(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(190, 170, 230), Color32::from_rgb(105, 65, 165))
}

/// What the camera sets on the exposure page (a ring), as against what you set (a filled dot, `strong`).
pub fn camera(v: &Visuals) -> Color32 {
    pick(v, Color32::from_rgb(120, 180, 255), Color32::from_rgb(25, 105, 205))
}

/// A tile, card or boxed note: a little apart from the panel behind it.
pub fn raised(v: &Visuals) -> Color32 {
    mix(v.panel_fill, v.text_color(), if v.dark_mode { 0.07 } else { 0.06 })
}

/// A boxed note that stands out more than `raised` (the greyed-out notice in the detail panel).
pub fn boxed(v: &Visuals) -> Color32 {
    mix(v.panel_fill, v.text_color(), if v.dark_mode { 0.14 } else { 0.10 })
}

/// The tile last clicked on the Main page.
pub fn chosen(v: &Visuals) -> Color32 {
    v.selection.bg_fill
}

/// Text on `chosen`.
pub fn chosen_text(v: &Visuals) -> Color32 {
    v.selection.stroke.color
}

/// A colour from the camera definition (a tab's colour) used for text: as it is on the dark theme, darkened on
/// the light one so it reads on white.
pub fn readable(v: &Visuals, c: Color32) -> Color32 {
    if v.dark_mode { c } else { mix(c, Color32::BLACK, 0.4) }
}

/// The background of the change map beside Compare.
pub fn track(v: &Visuals) -> Color32 {
    mix(v.panel_fill, v.text_color(), 0.10)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// WCAG relative luminance and contrast ratio.
    fn lum(c: Color32) -> f32 {
        let ch = |x: u8| {
            let s = x as f32 / 255.0;
            if s <= 0.03928 { s / 12.92 } else { ((s + 0.055) / 1.055).powf(2.4) }
        };
        0.2126 * ch(c.r()) + 0.7152 * ch(c.g()) + 0.0722 * ch(c.b())
    }
    fn contrast(a: Color32, b: Color32) -> f32 {
        let (x, y) = (lum(a), lum(b));
        (x.max(y) + 0.05) / (x.min(y) + 0.05)
    }

    /// Every text colour reads on the panel, and on the fills it is drawn on, in both themes (WCAG: 4.5 for
    /// body text; 3 for bold or large text and for marks).
    #[test]
    fn readable_in_both_themes() {
        for v in [visuals(false), visuals(true)] {
            let theme = if v.dark_mode { "dark" } else { "light" };
            let panel = v.panel_fill;
            for (name, c, min) in [
                ("edit", edit(&v), 4.5), ("ok", ok(&v), 4.0), ("bad", bad(&v), 4.0), ("caution", caution(&v), 4.0),
                ("note", note(&v), 4.5), ("unnamed", unnamed(&v), 4.0), ("file B", file_b(&v), 4.5),
                ("base", file_base(&v), 4.5), ("camera", camera(&v), 4.0), ("strong", v.strong_text_color(), 7.0),
                ("weak", weak(&v), 4.5),
            ] {
                let r = contrast(c, panel);
                assert!(r >= min, "{theme}: {name} on the panel is {r:.2}:1");
            }
            // quiet text on every fill it is drawn on: the window (Settings, Backups), the panels, a tile or card, a
            // boxed note, a striped row, a text field
            let stripe = mix(panel, Color32::WHITE, 5.0 / 255.0);
            for (fill_name, fill) in [("window", v.window_fill), ("panel", panel), ("raised", raised(&v)), ("boxed", boxed(&v)),
                ("striped row", stripe), ("text field", v.extreme_bg_color)] {
                let r = contrast(weak(&v), fill);
                assert!(r >= 4.5, "{theme}: weak text on the {fill_name} is {r:.2}:1");
            }
            // and still quieter than the body text, so a caption reads as one
            assert!(contrast(weak(&v), panel) < contrast(v.text_color(), panel), "{theme}: weak text as strong as the body text");
            // an unticked checkbox or radio button, and a text field, can be seen at rest: their outline (or, on the
            // dark theme, their fill) stands apart from the panel and a tile (WCAG 1.4.11: 3:1 for the outline)
            let at_rest = &v.widgets.inactive;
            if !v.dark_mode {
                for (fill_name, fill) in [("panel", panel), ("raised", raised(&v))] {
                    let r = contrast(at_rest.bg_stroke.color, fill);
                    assert!(at_rest.bg_stroke.width >= 1.0 && r >= 3.0, "light: a control's outline at rest on the {fill_name} is {r:.2}:1");
                }
            }
            let r = contrast(at_rest.fg_stroke.color, at_rest.bg_fill);
            assert!(r >= 4.5, "{theme}: a tick or a button's text on its fill is {r:.2}:1");
            let r = contrast(on_edit(&v), edit(&v));
            assert!(r >= 4.5, "{theme}: an edit count on its badge is {r:.2}:1");
            for (name, fill) in [("differs", differs(&v)), ("raised", raised(&v)), ("boxed", boxed(&v))] {
                for (tn, t) in [("text", v.text_color()), ("edit", edit(&v)), ("file B", file_b(&v))] {
                    let r = contrast(t, fill);
                    assert!(r >= 3.0, "{theme}: {tn} on {name} is {r:.2}:1");
                }
            }
            let r = contrast(chosen_text(&v), chosen(&v));
            assert!(r >= 4.5, "{theme}: text on the chosen tile is {r:.2}:1");
            // a difference and an edit must not look alike in the change map
            assert!(contrast(differs_mark(&v), edit(&v)) > 1.15 || v.dark_mode, "{theme}: change map marks too alike");
        }
    }
}
