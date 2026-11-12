//! Exposure in stops (APEX), read from the camera's own value labels: Av = 2·log2(N) for an
//! F-number N, Tv = −log2(t) for a time t in seconds, Sv = log2(ISO/100). One stop on any of the
//! three halves or doubles the light, so they can be drawn on aligned scales and added:
//! EV100 = Av + Tv − Sv is the scene brightness the three together expose for.

/// Which side of the exposure triangle a label belongs to.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Side {
    Aperture,
    Shutter,
    Iso,
}

/// Stops of a value label ("F2.8", "1/250", "30\"", "ISO 100"); None for anything else
/// ("AUTO", "BULB", "—").
pub fn stops(side: Side, label: &str) -> Option<f64> {
    let t = label.trim();
    match side {
        Side::Aperture => {
            let n: f64 = t.strip_prefix('F').or_else(|| t.strip_prefix('f'))?.trim().parse().ok()?;
            (n > 0.0).then(|| 2.0 * n.log2())
        }
        Side::Shutter => seconds(t).map(|s| -s.log2()),
        Side::Iso => {
            let n: f64 = t.strip_prefix("ISO").unwrap_or(t).trim().replace(',', "").parse().ok()?;
            (n > 0.0).then(|| (n / 100.0).log2())
        }
    }
}

/// A shutter time in seconds: "1/250", "30\"", "0.5\"" or a plain number of seconds.
pub fn seconds(t: &str) -> Option<f64> {
    let t = t.trim();
    let s = if let Some((n, d)) = t.split_once('/') {
        n.trim().parse::<f64>().ok()? / d.trim().parse::<f64>().ok()?
    } else {
        t.trim_end_matches('"').trim().parse::<f64>().ok()?
    };
    (s > 0.0 && s.is_finite()).then_some(s)
}

/// Stops of a shutter time stored as a fraction: numerator / denominator seconds.
pub fn fraction_stops(numerator: i64, denominator: i64) -> Option<f64> {
    (numerator > 0 && denominator > 0).then(|| -(numerator as f64 / denominator as f64).log2())
}

/// The scene brightness (EV at ISO 100) that an aperture, shutter and ISO, in stops, expose for.
pub fn ev100(av: f64, tv: f64, sv: f64) -> f64 {
    av + tv - sv
}

#[cfg(test)]
mod tests {
    use super::*;

    fn close(a: Option<f64>, b: f64) -> bool {
        a.is_some_and(|a| (a - b).abs() < 0.05)
    }

    #[test]
    fn labels_in_stops() {
        assert!(close(stops(Side::Aperture, "F1"), 0.0));
        assert!(close(stops(Side::Aperture, "F2.8"), 2.97));
        assert!(close(stops(Side::Aperture, "F8"), 6.0));
        assert!(close(stops(Side::Shutter, "1/250"), 7.97));
        assert!(close(stops(Side::Shutter, "30\""), -4.91));
        assert!(close(stops(Side::Shutter, "0.5\""), 1.0));
        assert!(close(stops(Side::Iso, "ISO 100"), 0.0));
        assert!(close(stops(Side::Iso, "ISO 6400"), 6.0));
        assert!(close(stops(Side::Iso, "ISO 102400"), 10.0));
        for none in ["AUTO", "BULB", "—", "Fast", ""] {
            assert_eq!(stops(Side::Shutter, none), None);
            assert_eq!(stops(Side::Iso, none), None);
            assert_eq!(stops(Side::Aperture, none), None);
        }
    }

    #[test]
    fn sunny_sixteen_is_ev15() {
        // f/16, 1/100 s at ISO 100: the classic exposure for direct sun
        let ev = ev100(stops(Side::Aperture, "F16").unwrap(), fraction_stops(1, 100).unwrap(), stops(Side::Iso, "ISO 100").unwrap());
        assert!((ev - 14.6).abs() < 0.1, "{ev}");
    }
}
