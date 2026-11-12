# Releasing

This page is how a release is made: what can be released and how, Sony's SDK terms and the rules the project
follows under them, what is fine to publish, and how the installers are built and released. What is kept out of
the repository, and why, is in [decision 18](decisions/0018-one-public-codebase-with-a-private-overlay.md).

## What can be released, and how

The project splits into three parts (agreed 2026-10-22):

1. **The editor** (`editor/`), for anyone with a camera. It needs no Sony software: it reads and writes the settings files the camera saves to a card (MENU > Setup > Reset/Save Settings > Save/Load Settings). The camera definitions (`editor/definitions/`, one per model and firmware, each with its sample) ship beside the program, never compiled into it: inside the macOS app, next to the program in the Windows zip, in the Linux tarball. A camera mapped later needs no new release: its definition is added in the editor (Settings > Camera support & web page > Add definition…).
2. **The mapping kit** (`kit/`), for contributors who want to map another body or firmware. It drives the camera through the Sony Camera Remote SDK, which each contributor downloads from Sony themselves.
3. **The definition per model and firmware** (`editor/definitions/<model>_fw<fw>.json`, [decision 19](decisions/0019-definitions-are-files-one-per-model-and-firmware.md); today the ILCE-1M2's at firmware 4.00), which `kit/schema_update.py --write` writes from `data/<model>_fw<fw>/`, that camera's proof runs in `runs/<model>_fw<fw>/` and, for the ILCE-1M2, its own tables. This is the contract between the two. Its sample (`editor/definitions/<model>_fw<fw>.DAT`) is a download the camera wrote right after Initialize, scrubbed by `kit/tools/make_sample.py`; of the records Initialize leaves as they were, only the Picture Profile parameters are checked so far, and the sample takes their values after each offered profile's own Reset in Stills and in Movie (`kit/provers/pp_reset_run.py`, then `make_sample.py --take "Picture Profile PP" --from` both results); a profile no menu offers (the ILCE-1M2's PP7-PP9) cannot be reset by a menu and keeps what the base file held, which is said plainly.

## Sony Camera Remote SDK terms (read 2026-10-29, again 2026-11-04 and 2026-11-05)

Source: the licence agreement at <https://support.d-imaging.sony.co.jp/app/sdk/licenseagreement/en.html>, linked from the SDK page <https://support.d-imaging.sony.co.jp/app/sdk/l/index.php>. The SDK is free; access is by application to Sony. This summary is for planning and is not legal advice.

- **Apps built with the SDK may be distributed.** The SDK page says developers may sell them; the grant does not separate free from paid.
- **The SDK's library may ship only inside an app,** "in a binary form ... in an inseparable way". The SDK itself (headers, samples, documents) may not be shared or published.
- **End users of an SDK-based app must be told, and must consent,** before they are licensed to use it: the agreement says to "explain to and obtain a consent from the END-USERS" that "the DEVICE will be out of such manufacturer-warranty", except in the countries it lists. This applies to any release that includes the camera helper, not to the editor on its own.
- **The grant has a purpose:** the SDK is licensed "solely for the purposes to remotely control or use the DEVICE in a normal usage".
- **Reverse engineering is barred for the "SOFTWARE",** and the agreement defines that to include "any data files created by operation of such software".
- **The agreement has no confidentiality clause, but its definition of "SOFTWARE" includes the documentation.**
- **The public SDK page lists the supported models but no per-function matrix,** so that matrix exists only in the API Reference.
- Other terms: Japanese law, Tokyo District Court; export rules; a list of prohibited uses (weapons, military surveillance); no removing Sony's notices.

What the project does under these terms:

- **It decodes the settings files the camera itself writes,** the file Save/Load Settings saves to a card.
- **The repository holds no SDK code and none of its documents.** Everything in `kit/sdk/` but its README, and `kit/CrSDK_*.zip`, is git-ignored, and `kit/tools/check_public.py` refuses a commit or pull request that carries an SDK file, known by its names and folders wherever it sits (run on every pull request by `.github/workflows/kit-ci.yml`); contributors get the SDK from Sony and build the camera link and the camera helper themselves (`kit/setup.py`).
- **The packages hold no binary built with the SDK.** The editor's packages carry the editor alone (the README, "The camera helper").
  The owner's internal macOS build (`CAMSET_INTERNAL=1`, with the camera helper and the camera's own help text) is
  built into `editor/target/dist-internal`, never `editor/target/dist`, and `build_macos_app.sh` refuses it in CI.
- **Sony's help text stays out.** The camera's In-Camera Guide text, read off one's own camera, is kept in one's own
  `private/help/`; the published definitions carry only the project's own help
  ([decision 13](decisions/0013-sony-s-help-text-stays-private.md)), and `kit/tools/check_public.py` refuses a
  commit whose help text stays too close to Sony's.
- **The docs hold nothing taken from Sony's documents** (decided 2026-11-04): only what the project observed itself or what Sony publishes openly. `docs/CAMERA_SUPPORT.md` names no model's SDK functions and says how to check one's own body; `kit/tools/sdk_support.py --json` builds the model × function table from one's own SDK into one's own `private/data/`.

## Fine to publish

- `docs/formats/sony_camset.ksy` and `docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`: the format, and each
  definition's record names, groups and value labels.
- `data/*/`: what is the same for any owner of the model and firmware; the menu tree, the accepted rulings and the
  record shapes stay in the mapper's `private/evidence/`.

None of them holds help text or a value from anyone's camera.

## Installers

| Platform | Build | State |
|---|---|---|
| macOS | `sh packaging/build_macos_app.sh` (from `editor/`): `Camset Editor.app` and a `.dmg` in `editor/target/dist`, with only the tools macOS ships; the bundle identifier is `app.camset.editor` (`CAMSET_BUNDLE_ID` overrides it) | Built and launched by Finder's route (`open`) on the Mac that built it, 2026-10-29: Apple silicon, ad-hoc signed. A downloaded copy, which macOS marks as from the internet, not yet tried. |
| Linux | `sh packaging/build_linux.sh` (from `editor/`): a tarball with the program, a menu entry, the icon and `install.sh` (per user, no root) | `build_linux.sh` written, not yet run. The editor itself was built and run on Ubuntu 26.04 (`PORTING.md`, "Seen on Windows / Linux"). |
| Windows | The workflow zips `camset_editor.exe`; the release build has no console window | Not yet built. The exe has no embedded icon yet (the window and taskbar show it). |

**Cutting a release.** Set `version` in `editor/Cargo.toml` (0.2.0 now), add the release's section to `CHANGELOG.md`,
commit, then tag that commit `v<version>` (for example `v0.2.0`) and push the tag to GitHub only. The release is
0.2.0, tagged on 2026-11-11 on the single commit that replaced the public history; 0.1.0 was withdrawn then, its tag
and its GitHub Release deleted, because its packages carried a definition in the older form. Pushing the tag starts
`.github/workflows/editor-release.yml` (which runs the same, without the release, when run by hand with
workflow_dispatch):

1. **test:** the kit's tests, `kit/tools/check_public.py --all` and the editor's tests, on Linux: the gate before any
   package is built (pull requests and main are checked by `kit-ci.yml` and `editor-ci.yml`);
2. **build:** on macOS and Linux (Windows once its package has been checked), the editor's tests, its third-party licences page (`cargo about`: the
   crates, and the fonts egui builds in, from `editor/about.hbs`), and the package for that system, which carries the
   project's `LICENSE` and that page, kept as a build artifact;
3. **release:** on a version tag pushed to GitHub only, a GitHub Release for the tag with the packages attached
   (`softprops/action-gh-release`). Run by hand, or on Gitea, which has no GitHub Releases API, this job skips itself.

Each action the workflow uses is pinned to a full commit, with its version in a comment, and `cargo-about` to a
version, so a tag moved upstream cannot change what builds or publishes a release.

The workflow ran on GitHub for 0.1.0: a build job that GitHub's macOS runner cancelled before any step was rebuilt
with Re-run failed jobs on the run's page, and the release job, which waits for every build, ran after it. It has not
been run on Gitea, whose Actions needs runners for each system and a recent version for the pinned `upload-artifact`.

**Replacing a withdrawn release** (0.1.0 by 0.2.0): the maintainer commits the tree as one fresh commit on `main`
and force-pushes it to both remotes, tags that commit `v0.2.0` and pushes the tag to GitHub only, which starts the
workflow above, then deletes the `v0.1.0` tag on both remotes and its GitHub Release, and pastes 0.2.0's section of
`CHANGELOG.md` onto the new Release. A clone made earlier keeps its own `v0.1.0` tag until its owner removes it
([UPDATING](UPDATING.md#packages-and-tags)).

**The docs site** is built and published to GitHub Pages by `.github/workflows/docs.yml`, on each push to main that
touches what the site is built from (or run by hand), once Pages is enabled for the repository (Settings → Pages →
Source: GitHub Actions); on Gitea its deploy job skips itself. Written 2026-11-04, not yet run.

**Statistics:** `.github/workflows/stats.yml` runs daily (03:17 UTC, or by hand) and appends to CSV files on the `stats` branch, an orphan branch it creates on the first run: `stats/summary.csv` (stars, forks, watchers, open issues, total downloads), `stats/downloads.csv` (each release asset's download count) and, for what GitHub's Insights page keeps only 14 days, `stats/traffic.csv` (views and clones, by day), `stats/referrers.csv` and `stats/paths.csv`. The traffic series need the `STATS_TOKEN` secret, a fine-grained token for this repository only with Administration: read, set under Settings > Secrets and variables > Actions; without it the workflow skips them and says so in its log.

**Sign-offs:** `.github/workflows/dco.yml` runs `dco-check --verbose` on each pull request and fails it when a commit
is not signed off (`git commit -s`; the repository's CONTRIBUTING.md). Written 2026-11-04, not yet run.

Not yet done for a public release:
- **macOS:** the app is ad-hoc signed only: no Developer ID signature, no notarization (both need an Apple Developer account), and no universal (Intel + Apple silicon) build.
- **Windows:** no icon resource in the exe, and no code signing. What users meet until then is in the README, "Use the editor".
- **Proper installers** (`.msi`/NSIS, `.deb`, AppImage), for example with cargo-packager, once the plain packages work.
- **File types:** none are claimed. `.DAT` is used by many apps (decided 2026-10-22).
- **The docs site's links to the README, CONTRIBUTING and the Releases page.** `repo_url` and `site_url` in
  `mkdocs.yml` point at github.com/camset-dev/camset since 2026-11-09, so the site's header links back to the repository.
- **Release notes on GitHub:** the workflow attaches the packages and writes no notes. A release's notes are its
  section of `CHANGELOG.md` (its "Read first" repeats the README's warning, says that the camera helper is not
  included and, for 0.2.0, that 0.1.0 is withdrawn and its definitions do not open in 0.2.0), copied onto the Release
  by hand.
- **The camera helper is not in these packages** (the README, "The camera helper"). If an SDK build is ever shipped, it must carry the warranty notice above.
