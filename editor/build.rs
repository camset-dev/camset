//! The build's git commit, for Settings and the web page ("0.2.0 (build 1a2b3c4)"): `git rev-parse --short HEAD` as
//! `CAMSET_GIT_HASH`, empty when the source is not a git checkout or git is not there. Built again when the commit
//! changes.
//!
//! On a Windows build, also the program's icon and version details (packaging/windows/resources.rs): Explorer, the
//! taskbar, shortcuts and Properties > Details show them. macOS and Linux builds do nothing more.

use std::process::Command;

// Compiled on a Windows computer only, where Cargo.toml gives build.rs the image crate it draws the icon with. The
// .ico writer in it is for the editor's tests.
#[cfg(windows)]
#[allow(dead_code)]
#[path = "packaging/windows/resources.rs"]
mod resources;

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
    if std::env::var("CARGO_CFG_TARGET_OS").is_ok_and(|os| os == "windows") {
        windows_resources();
    }
}

/// The Windows program's icon and version details, for a build for Windows: a .res file in OUT_DIR, which Microsoft's
/// linker (MSVC) takes as it is, so no resource compiler is needed. A build that cannot have them (another toolchain,
/// another computer, an unreadable icon) goes on without them and says so.
fn windows_resources() {
    let without = "camset_editor.exe is built without its icon and version details";
    if std::env::var("CARGO_CFG_TARGET_ENV").is_ok_and(|env| env != "msvc") {
        println!("cargo:warning={without}: they are linked with Microsoft's linker (the MSVC toolchain) only");
        return;
    }
    if !cfg!(windows) {
        // Cargo gives build.rs the image crate on a Windows computer only (Cargo.toml)
        println!("cargo:warning={without}: they can only be made on a Windows computer");
        return;
    }
    match windows_res() {
        Ok(res) => println!("cargo:rustc-link-arg-bins={}", res.display()),
        Err(e) => println!("cargo:warning={without}: {e}"),
    }
}

/// Elsewhere, never called (`windows_resources` stops first).
#[cfg(not(windows))]
fn windows_res() -> Result<std::path::PathBuf, String> {
    Err("not a Windows computer".to_string())
}

/// Writes the .res (the icon drawn from assets/icon.png, the version from Cargo.toml, the copyright line from LICENSE)
/// and gives its path.
#[cfg(windows)]
fn windows_res() -> Result<std::path::PathBuf, String> {
    for path in ["assets/icon.png", "../LICENSE", "packaging/windows/resources.rs"] {
        println!("cargo:rerun-if-changed={path}");
    }
    let dir = std::path::PathBuf::from(std::env::var_os("CARGO_MANIFEST_DIR").ok_or("Cargo gave no CARGO_MANIFEST_DIR")?);
    let png = std::fs::read(dir.join("assets/icon.png")).map_err(|e| format!("assets/icon.png: {e}"))?;
    let images = resources::icon_images(&png)?;
    let holders = std::fs::read_to_string(dir.join("../LICENSE")).ok().and_then(|l| resources::copyright_holders(&l));
    if holders.is_none() {
        println!("cargo:warning=LICENSE is missing or has no \"Copyright (c) ...\" line: camset_editor.exe's details name no copyright");
    }
    let version = std::env::var("CARGO_PKG_VERSION").map_err(|_| "Cargo gave no CARGO_PKG_VERSION")?;
    let info = resources::version_info(&version, holders.as_deref());
    let res = std::path::PathBuf::from(std::env::var_os("OUT_DIR").ok_or("Cargo gave no OUT_DIR")?).join("camset_editor.res");
    std::fs::write(&res, resources::res_file(&images, &info)).map_err(|e| format!("{}: {e}", res.display()))?;
    Ok(res)
}
