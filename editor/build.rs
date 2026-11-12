//! The build's git commit, for Settings and the web page ("0.2.0 (build 1a2b3c4)"): `git rev-parse --short HEAD` as
//! `CAMSET_GIT_HASH`, empty when the source is not a git checkout or git is not there. Built again when the commit
//! changes.

use std::process::Command;

/// A git command's first line of output, when it succeeds.
fn git(args: &[&str]) -> Option<String> {
    let out = Command::new("git").args(args).output().ok().filter(|o| o.status.success())?;
    let text = String::from_utf8(out.stdout).ok()?;
    Some(text.lines().next().unwrap_or("").trim().to_string()).filter(|t| !t.is_empty())
}

fn main() {
    let hash = git(&["rev-parse", "--short", "HEAD"]).unwrap_or_default();
    // only letters and digits reach the program, whatever git prints
    let hash: String = hash.chars().filter(char::is_ascii_alphanumeric).take(40).collect();
    println!("cargo:rustc-env=CAMSET_GIT_HASH={hash}");
    println!("cargo:rerun-if-changed=build.rs");
    // HEAD moves on a checkout; the branch's ref (loose or packed) on a commit. Only files that are there: one that
    // is not would run this script, and build the editor again, every time.
    let mut watch = vec!["HEAD".to_string(), "packed-refs".to_string()];
    watch.extend(git(&["symbolic-ref", "-q", "HEAD"]));
    for path in watch {
        if let Some(p) = git(&["rev-parse", "--git-path", &path]).filter(|p| std::path::Path::new(p).is_file()) {
            println!("cargo:rerun-if-changed={p}");
        }
    }
}
