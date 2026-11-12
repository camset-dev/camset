//! Time in words: the stamps the camera writes into a file's header and the editor writes into its own files'
//! names (YYYYMMDD_HHMMSS), and spans of time as the window and the web page say them.


/// A span of time in words: "5 seconds", "a minute", "three minutes".
pub(crate) fn duration_words(secs: u32) -> String {
    match (secs, secs % 60, secs / 60) {
        (1, _, _) => "1 second".into(),
        (s, _, 0) => format!("{s} seconds"),
        (_, 0, 1) => "a minute".into(),
        (_, 0, 2) => "two minutes".into(),
        (_, 0, 3) => "three minutes".into(),
        (_, 0, m) => format!("{m} minutes"),
        (s, _, _) => format!("{s} seconds"),
    }
}

/// Local time as YYYYMMDD_HHMMSS, the same form the camera writes into the file header.
pub(crate) fn local_stamp() -> String {
    stamp_of(std::time::SystemTime::now())
}

/// A moment as a local YYYYMMDD_HHMMSS stamp (UTC where local time is not available).
pub(crate) fn stamp_of(when: std::time::SystemTime) -> String {
    let secs = when.duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
    #[cfg(unix)]
    {
        let t = secs as libc::time_t;
        let mut tm: libc::tm = unsafe { std::mem::zeroed() };
        unsafe { libc::localtime_r(&t, &mut tm) };
        return format!("{:04}{:02}{:02}_{:02}{:02}{:02}", tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec);
    }
    #[allow(unreachable_code)]
    utc_stamp(secs)
}

/// A YYYYMMDD_HHMMSS stamp (a file's header, or this computer's local time) in words, the one way a time is shown:
/// "17:44" on the day `now` (a local stamp) names, else "1 Jan 2026 at 00:00". Anything that is not such a stamp is
/// given as it is.
pub(crate) fn when_words_at(stamp: &str, now: &str) -> String {
    // by `get`, not by slicing: a hand-edited stamp with a non-ASCII character is shown as it is, never a crash
    let num = |a: usize, b: usize| stamp.get(a..b).filter(|t| t.bytes().all(|c| c.is_ascii_digit())).and_then(|t| t.parse::<usize>().ok());
    let (Some(y), Some(mo), Some(d), Some(h), Some(mi)) = (num(0, 4), num(4, 6), num(6, 8), num(9, 11), num(11, 13)) else { return stamp.to_string() };
    if stamp.get(8..9) != Some("_") || !(1..=12).contains(&mo) || !(1..=31).contains(&d) || h > 23 || mi > 59 {
        return stamp.to_string();
    }
    if stamp.get(0..8) == now.get(0..8) {
        return format!("{h:02}:{mi:02}");
    }
    const MONTHS: [&str; 12] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    format!("{d} {} {y} at {h:02}:{mi:02}", MONTHS[mo - 1])
}

/// `when_words`, with the stamp itself after it when `raw` (Expert mode): "1 Jan 2026 at 00:00 (20260101_000000)".
pub(crate) fn stamp_in_words(stamp: &str, raw: bool) -> String {
    let w = when_words(stamp);
    if raw && w != stamp { format!("{w} ({stamp})") } else { w }
}

/// `when_words_at` against this computer's clock now.
pub(crate) fn when_words(stamp: &str) -> String {
    when_words_at(stamp, &local_stamp())
}

/// This computer's local time for the names of the files the editor keeps: "2026-11-05_17-44-05".
pub(crate) fn file_stamp() -> String {
    let s = local_stamp();
    match (s.get(0..4), s.get(4..6), s.get(6..8), s.get(9..11), s.get(11..13), s.get(13..15)) {
        (Some(y), Some(mo), Some(d), Some(h), Some(mi), Some(se)) => format!("{y}-{mo}-{d}_{h}-{mi}-{se}"),
        _ => s,
    }
}

/// A span of minutes in words: "35 minutes", "12 hours", "2 days and 3 hours".
pub(crate) fn minutes_words(m: i64) -> String {
    let (days, hours, mins) = (m / 1440, (m % 1440) / 60, m % 60);
    let unit = |n: i64, one: &str| format!("{n} {one}{}", if n == 1 { "" } else { "s" });
    match (days, hours, mins) {
        (0, 0, mi) => unit(mi, "minute"),
        (0, h, 0) => unit(h, "hour"),
        (0, h, mi) => format!("{} and {}", unit(h, "hour"), unit(mi, "minute")),
        (d, 0, _) => unit(d, "day"),
        (d, h, _) => format!("{} and {}", unit(d, "day"), unit(h, "hour")),
    }
}

/// Minutes represented by a YYYYMMDD_HHMMSS stamp (for comparing two stamps); None for a text that is not one.
pub(crate) fn stamp_minutes(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    if b.len() < 15 || b[8] != b'_' { return None; }
    let n = |a: usize, l: usize| s.get(a..a + l)?.parse::<i64>().ok();
    let (y, mo, d, h, mi) = (n(0, 4)?, n(4, 2)?, n(6, 2)?, n(9, 2)?, n(11, 2)?);
    // days from civil (Howard Hinnant)
    let y2 = if mo <= 2 { y - 1 } else { y };
    let era = y2.div_euclid(400); let yoe = y2 - era * 400;
    let mp = (mo + 9) % 12; let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    Some(days * 1440 + h * 60 + mi)
}

/// A moment as a UTC YYYYMMDD_HHMMSS stamp, where local time is not available.
fn utc_stamp(secs: u64) -> String {
    // civil date from days since the epoch (Howard Hinnant's algorithm)
    let days = (secs / 86400) as i64; let (h, m, s) = ((secs % 86400) / 3600, (secs % 3600) / 60, secs % 60);
    let z = days + 719468; let era = z.div_euclid(146097); let doe = z.rem_euclid(146097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365; let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100); let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1; let mo = if mp < 10 { mp + 3 } else { mp - 9 }; let y = if mo <= 2 { y + 1 } else { y };
    format!("{y:04}{mo:02}{d:02}_{h:02}{m:02}{s:02}")
}
