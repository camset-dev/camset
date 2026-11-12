//! The guard for decision 20 (docs/decisions/0020): the editor knows a camera only through its definition. This test
//! reads the editor's own sources (every `.rs` under `src/`, but the test modules and `test_support.rs`, and the web
//! page's `.js` and `.html`) and fails where code or a string literal names a setting by its key ("global:0x…",
//! "set…:0x…"), a record by a bare four-digit id, a camera model, or a shipped definition's file. Comments may give
//! examples. It catches names and ids only, not behaviour: an editor that quietly treats one camera's records
//! specially without naming them passes it, so the rule still rests on review.

use std::path::{Path, PathBuf};

/// What must stay, each with why: (file name, the text found, the reason). Nothing here names a camera.
const ALLOWED: &[(&str, &str, &str)] = &[
    ("camset.rs", "0x8000", "the bit that marks a field's byte offset in a slot's index, not a record"),
    ("files.rs", "0x0001", "a Windows API flag (SEM_FAILCRITICALERRORS), not a record"),
    ("files.rs", "0x8000", "a Windows API flag (SEM_NOOPENFILEERRORBOX), not a record"),
];

/// Camera models as people and Sony write them: none may stand in the editor's code or texts.
const MODELS: &[&str] = &["ILCE", "ILME", "ZV-E", "DSC-RX", "a1 II", "a7 IV", "a7 V", "a7R", "a7S", "a7C", "a9 III"];

/// One line of a source: its number, its code with every string literal emptied and comments left out, and the
/// contents of its string literals.
struct Line {
    no: usize,
    code: String,
    strings: Vec<String>,
}

/// A Rust source read into lines (`Line`): comments (`//`, `/* */`, nested) left out, string literals (plain, byte,
/// raw) and char literals told apart from code, lifetimes left in the code.
fn rust_lines(text: &str) -> Vec<Line> {
    let c: Vec<char> = text.chars().collect();
    let mut out = vec![Line { no: 1, code: String::new(), strings: Vec::new() }];
    let newline = |out: &mut Vec<Line>| {
        let no = out.len() + 1;
        out.push(Line { no, code: String::new(), strings: Vec::new() });
    };
    let mut i = 0;
    while i < c.len() {
        let at = |i: usize, k: usize| c.get(i + k).copied().unwrap_or('\0');
        match c[i] {
            '\n' => {
                newline(&mut out);
                i += 1;
            }
            '/' if at(i, 1) == '/' => {
                while i < c.len() && c[i] != '\n' {
                    i += 1;
                }
            }
            '/' if at(i, 1) == '*' => {
                let mut depth = 0;
                while i < c.len() {
                    if c[i] == '/' && at(i, 1) == '*' {
                        depth += 1;
                        i += 2;
                    } else if c[i] == '*' && at(i, 1) == '/' {
                        depth -= 1;
                        i += 2;
                        if depth == 0 {
                            break;
                        }
                    } else {
                        if c[i] == '\n' {
                            newline(&mut out);
                        }
                        i += 1;
                    }
                }
            }
            'r' | 'b' if raw_start(&c, i).is_some() => {
                // a raw string: r"…", r#"…"#, br"…"
                let (mut k, hashes) = raw_start(&c, i).unwrap_or((i, 0));
                let mut s = String::new();
                while k < c.len() && !(c[k] == '"' && (1..=hashes).all(|h| c.get(k + h) == Some(&'#'))) {
                    if c[k] == '\n' {
                        out.last_mut().unwrap().strings.push(std::mem::take(&mut s));
                        newline(&mut out);
                    } else {
                        s.push(c[k]);
                    }
                    k += 1;
                }
                out.last_mut().unwrap().strings.push(s);
                i = k + 1 + hashes;
            }
            '"' => {
                let mut k = i + 1;
                let mut s = String::new();
                while k < c.len() && c[k] != '"' {
                    if c[k] == '\\' {
                        s.push(c[k]);
                        s.push(c.get(k + 1).copied().unwrap_or(' '));
                        if c.get(k + 1) == Some(&'\n') {
                            out.last_mut().unwrap().strings.push(std::mem::take(&mut s));
                            newline(&mut out);
                        }
                        k += 2;
                        continue;
                    }
                    if c[k] == '\n' {
                        out.last_mut().unwrap().strings.push(std::mem::take(&mut s));
                        newline(&mut out);
                    } else {
                        s.push(c[k]);
                    }
                    k += 1;
                }
                out.last_mut().unwrap().strings.push(s);
                out.last_mut().unwrap().code.push_str("\"\"");
                i = k + 1;
            }
            '\'' if at(i, 1) == '\\' => {
                // an escaped char literal: '\n', '\'', '\u{…}'
                let mut k = i + 2;
                while k < c.len() && c[k] != '\'' {
                    k += 1;
                }
                i = k + 1;
            }
            '\'' if at(i, 2) == '\'' => i += 3,
            ch => {
                out.last_mut().unwrap().code.push(ch);
                i += 1;
            }
        }
    }
    out
}

/// Where a raw string literal starting at `i` (r"…", r#"…"#, br"…") has its first character, and how many #s close
/// it; None when none starts there.
fn raw_start(c: &[char], i: usize) -> Option<(usize, usize)> {
    if i.checked_sub(1).is_some_and(|p| c[p].is_alphanumeric() || c[p] == '_') {
        return None;
    }
    let mut k = i + usize::from(c.get(i) == Some(&'b'));
    if c.get(k) != Some(&'r') {
        return None;
    }
    k += 1;
    let hashes = c[k..].iter().take_while(|ch| **ch == '#').count();
    (c.get(k + hashes) == Some(&'"')).then_some((k + hashes + 1, hashes))
}

/// The lines of a Rust source outside its test items: each `#[cfg(test)]` item (a module, a function, a use) left out,
/// to the end of its braces or its `;`.
fn outside_tests(lines: Vec<Line>) -> Vec<Line> {
    let mut out = Vec::new();
    let mut it = lines.into_iter().peekable();
    while let Some(l) = it.next() {
        if !l.code.trim_start().starts_with("#[cfg(test)]") {
            out.push(l);
            continue;
        }
        let (mut depth, mut opened) = (0i64, false);
        let mut line = Some(l);
        while let Some(l) = line {
            let rest = l.code.trim_start().strip_prefix("#[cfg(test)]").unwrap_or(&l.code).to_string();
            for ch in rest.chars() {
                match ch {
                    '{' => {
                        depth += 1;
                        opened = true;
                    }
                    '}' => depth -= 1,
                    _ => {}
                }
            }
            if (opened && depth <= 0) || (!opened && rest.trim_end().ends_with(';')) {
                break;
            }
            line = it.next();
        }
    }
    out
}

/// A web page source (`.js`, `.html`) read into lines (`Line`): `//` and `/* */` comments and `<!-- -->` left out,
/// string literals ('…', "…", `…`) told apart from code.
fn web_lines(text: &str) -> Vec<Line> {
    let c: Vec<char> = text.chars().collect();
    let mut out = vec![Line { no: 1, code: String::new(), strings: Vec::new() }];
    let mut i = 0;
    let starts = |i: usize, s: &str| s.chars().enumerate().all(|(k, ch)| c.get(i + k) == Some(&ch));
    while i < c.len() {
        if c[i] == '\n' {
            let no = out.len() + 1;
            out.push(Line { no, code: String::new(), strings: Vec::new() });
            i += 1;
        } else if starts(i, "//") && !i.checked_sub(1).is_some_and(|p| c[p] == ':' || c[p] == '\\') {
            while i < c.len() && c[i] != '\n' {
                i += 1;
            }
        } else if starts(i, "/*") || starts(i, "<!--") {
            let end = if c[i] == '/' { "*/" } else { "-->" };
            while i < c.len() && !starts(i, end) {
                if c[i] == '\n' {
                    let no = out.len() + 1;
                    out.push(Line { no, code: String::new(), strings: Vec::new() });
                }
                i += 1;
            }
            i += end.len();
        } else if matches!(c[i], '"' | '\'' | '`') {
            let quote = c[i];
            let mut k = i + 1;
            let mut s = String::new();
            while k < c.len() && c[k] != quote {
                if c[k] == '\\' {
                    k += 1;
                } else if c[k] == '\n' {
                    if quote != '`' {
                        break;
                    }
                    out.last_mut().unwrap().strings.push(std::mem::take(&mut s));
                    let no = out.len() + 1;
                    out.push(Line { no, code: String::new(), strings: Vec::new() });
                } else {
                    s.push(c[k]);
                }
                k += 1;
            }
            out.last_mut().unwrap().strings.push(s);
            i = k + 1;
        } else {
            out.last_mut().unwrap().code.push(c[i]);
            i += 1;
        }
    }
    out
}

/// Every setting key in `text`: ":0x" after "global" or after a word starting "set".
fn keys_in(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    for (at, _) in text.match_indices(":0x") {
        let word: String = text[..at].chars().rev().take_while(|c| c.is_alphanumeric() || *c == '_').collect::<Vec<_>>().into_iter().rev().collect();
        if word == "global" || word.starts_with("set") {
            out.push(format!("{word}{}", &text[at..text.len().min(at + 7)]));
        }
    }
    out
}

/// Every four-digit hex number in `code` ("0x02cf"), as a record id would be written.
fn ids_in(code: &str) -> Vec<String> {
    let b = code.as_bytes();
    let mut out = Vec::new();
    for (at, _) in code.match_indices("0x") {
        let before = at.checked_sub(1).map(|p| b[p]);
        if before.is_some_and(|p| p.is_ascii_alphanumeric() || p == b'_') {
            continue;
        }
        let digits = b[at + 2..].iter().take_while(|d| d.is_ascii_hexdigit()).count();
        let after = b.get(at + 2 + digits).copied();
        if digits == 4 && !after.is_some_and(|a| a.is_ascii_alphanumeric() || a == b'_') {
            out.push(code[at..at + 6].to_string());
        }
    }
    out
}

/// What `text` names that only a definition may: a model, or a shipped definition's file (`files`, their stems).
fn camera_names_in(text: &str, files: &[String]) -> Vec<String> {
    let mut out: Vec<String> = MODELS.iter().filter(|m| text.contains(**m)).map(|m| m.to_string()).collect();
    out.extend(files.iter().filter(|f| text.contains(f.as_str())).cloned());
    if let Some(at) = text.find("_fw") {
        if text[at + 3..].starts_with(|c: char| c.is_ascii_digit()) {
            out.push(text[at..text.len().min(at + 8)].to_string());
        }
    }
    if let Some((at, _)) = text.char_indices().find(|(k, c)| *c == 'α' && text[k + 'α'.len_utf8()..].starts_with(|d: char| d.is_ascii_digit())) {
        out.push(text[at..].chars().take(3).collect());
    }
    out
}

/// Every `.rs` file under `dir`.
fn rust_files(dir: &Path, out: &mut Vec<PathBuf>) {
    for e in std::fs::read_dir(dir).unwrap().flatten() {
        let p = e.path();
        if p.is_dir() {
            rust_files(&p, out);
        } else if p.extension().is_some_and(|x| x == "rs") {
            out.push(p);
        }
    }
}

/// The files that are test modules as a whole: those a `#[cfg(test)]` declares (`#[cfg(test)] mod name;`).
fn test_module_files(files: &[PathBuf]) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for f in files {
        let text = std::fs::read_to_string(f).unwrap();
        let lines: Vec<&str> = text.lines().map(str::trim).collect();
        let dir = match f.file_stem().and_then(|s| s.to_str()) {
            Some("main" | "lib" | "mod") => f.parent().unwrap().to_path_buf(),
            Some(stem) => f.parent().unwrap().join(stem),
            None => continue,
        };
        for (k, l) in lines.iter().enumerate() {
            let Some(rest) = l.strip_prefix("#[cfg(test)]") else { continue };
            // the declaration on the attribute's line, or on the next
            let decl = if rest.contains("mod ") { rest } else { lines.get(k + 1).copied().unwrap_or("") };
            let Some(name) = decl.split("mod ").nth(1).filter(|_| decl.contains(';')).and_then(|r| r.split(';').next()).map(str::trim) else { continue };
            out.push(dir.join(format!("{name}.rs")));
            out.push(dir.join(name).join("mod.rs"));
        }
    }
    out
}

#[test]
fn the_editor_names_no_camera() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let files: Vec<String> = std::fs::read_dir(root.join("definitions")).unwrap().flatten()
        .filter_map(|e| e.path().file_stem().and_then(|s| s.to_str()).map(str::to_string)).collect();
    let mut sources = Vec::new();
    rust_files(&root.join("src"), &mut sources);
    let tests = test_module_files(&sources);
    let mut found: Vec<String> = Vec::new();
    let mut allowed_seen = vec![false; ALLOWED.len()];
    let mut check = |path: &Path, lines: Vec<Line>| {
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        for l in lines {
            let mut hits: Vec<String> = keys_in(&l.code).into_iter().chain(ids_in(&l.code)).chain(camera_names_in(&l.code, &files)).collect();
            for s in &l.strings {
                hits.extend(keys_in(s).into_iter().chain(camera_names_in(s, &files)));
            }
            for h in hits {
                match ALLOWED.iter().position(|(f, text, _)| *f == name && *text == h) {
                    Some(k) => allowed_seen[k] = true,
                    None => found.push(format!("{}:{}: {h}", path.strip_prefix(root).unwrap_or(path).display(), l.no)),
                }
            }
        }
    };
    for f in sources.iter().filter(|f| f.file_name().is_some_and(|n| n != "test_support.rs") && !tests.contains(f)) {
        check(f, outside_tests(rust_lines(&std::fs::read_to_string(f).unwrap())));
    }
    for e in std::fs::read_dir(root.join("web")).unwrap().flatten() {
        let p = e.path();
        if p.extension().is_some_and(|x| x == "js" || x == "html") {
            check(&p, web_lines(&std::fs::read_to_string(&p).unwrap()));
        }
    }
    assert!(found.is_empty(), "the editor's code names a camera's records, models or definition files (decision 20); take them from the definition:\n{}", found.join("\n"));
    // an allowance nothing needs any more goes, so the list stays short and true
    let stale: Vec<&str> = ALLOWED.iter().zip(&allowed_seen).filter(|(_, seen)| !**seen).map(|(a, _)| a.1).collect();
    assert!(stale.is_empty(), "allowed but no longer found, so take them out of ALLOWED: {stale:?}");
}

/// The guard's own reading: what it must catch in code and strings, and what it must leave (comments, test modules).
#[test]
fn the_guard_reads_code_strings_and_comments_apart() {
    let src = "// global:0x0334 in a comment is an example\nlet k = \"global:0x0334\"; /* ILCE-1M2 */\nif r.id == 0x02cf { }\nlet s = r#\"the a1 II\"#;\n#[cfg(test)]\nmod tests {\n    const K: &str = \"set:0x0100\";\n}\nlet t = 'x'; fn f<'a>() {}\n";
    let lines = outside_tests(rust_lines(src));
    let files = vec!["ILCE-1M2_fw4.00".to_string()];
    let keys: Vec<String> = lines.iter().flat_map(|l| l.strings.iter().flat_map(|s| keys_in(s)).chain(keys_in(&l.code))).collect();
    assert_eq!(keys, vec!["global:0x0334"]);
    let ids: Vec<(usize, String)> = lines.iter().flat_map(|l| ids_in(&l.code).into_iter().map(move |i| (l.no, i))).collect();
    assert_eq!(ids, vec![(3, "0x02cf".to_string())]);
    let names: Vec<String> = lines.iter().flat_map(|l| l.strings.iter().flat_map(|s| camera_names_in(s, &files)).chain(camera_names_in(&l.code, &files))).collect();
    assert_eq!(names, vec!["a1 II"], "the comment's model is left, the raw string's caught");
    let web = web_lines("// ILCE in a comment\nconst a = \"global:0x0df4\"; /* α1 */ const u = \"https://x\";\n<!-- ILME -->");
    let keys: Vec<String> = web.iter().flat_map(|l| l.strings.iter().flat_map(|s| keys_in(s))).collect();
    assert_eq!(keys, vec!["global:0x0df4"]);
    assert!(web.iter().all(|l| camera_names_in(&l.code, &files).is_empty() && l.strings.iter().all(|s| camera_names_in(s, &files).is_empty())));
}
