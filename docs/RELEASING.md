# Releasing

How a release is made and checked, how the dependencies are kept, and what Sony's SDK terms allow. What stays out of
the repository is in [decision 18](decisions/0018-one-public-codebase-with-a-private-overlay.md).

## What is released

1. **The editor** (`editor/`), for anyone with a camera. It needs no Sony software. The camera definitions
   (`editor/definitions/`, each with its sample) ship beside the program, never compiled into it, so a camera mapped
   later needs no new release: its definition is added in the editor (Settings > Camera support & web page > Add
   definition…).
2. **The mapping kit** (`kit/`), for contributors. It drives the camera through Sony's Camera Remote SDK, which each
   contributor downloads from Sony.
3. **A definition per model and firmware** (`editor/definitions/<model>_fw<fw>.json`,
   [decision 19](decisions/0019-definitions-are-files-one-per-model-and-firmware.md)), the contract between the two,
   written by `kit/schema_update.py --write`. Its sample is a download the camera wrote right after Initialize,
   scrubbed by `kit/tools/make_sample.py`, whose notes say what the sample holds.

## Sony Camera Remote SDK terms

Read 2026-10-29, again 2026-11-04 and 2026-11-05. Source: the licence agreement at <https://support.d-imaging.sony.co.jp/app/sdk/licenseagreement/en.html>, linked from the SDK page <https://support.d-imaging.sony.co.jp/app/sdk/l/index.php>. The SDK is free; access is by application to Sony. This summary is for planning and is not legal advice.

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
- **The docs hold nothing taken from Sony's documents** (decided 2026-11-04): only what the project observed itself or what Sony publishes openly. The docs carry no model-by-function table from Sony's reference; `kit/tools/sdk_support.py --json` builds the model × function table from one's own SDK into one's own `private/data/`.
- **If an SDK build is ever shipped,** it must carry the warranty notice above.

## Fine to publish

- `docs/formats/sony_camset.ksy` and `docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`: the format, and each
  definition's record names, groups and value labels.
- `data/*/`: what is the same for any owner of the model and firmware; the menu tree, the accepted rulings and the
  record shapes stay in the mapper's `private/evidence/`.

None of them holds help text or a value from anyone's camera.

## Installers

Each package carries the project's `LICENSE` and the third-party licences page (`cargo about`, from
`editor/about.hbs`), and the definitions beside the program.

| Platform | Build (from `editor/`) | State |
|---|---|---|
| macOS | `sh packaging/build_macos_app.sh`: `Camset Editor.app` and a `.dmg` in `target/dist`, with only the tools macOS ships; bundle identifier `app.camset.editor` (`CAMSET_BUNDLE_ID` overrides it) | Apple silicon, ad-hoc signed; launched on the Mac that built it. A downloaded copy not yet tried. |
| Linux | `sh packaging/build_linux.sh`: a tarball with the program, a menu entry, the icon and `install.sh` (per user, no root) | Built by the release workflow. The editor itself built and ran on Ubuntu 26.04 ([PORTING](PORTING.md)). A downloaded tarball and its `install.sh` not yet tried. |
| Windows | The workflow's `Windows zip` step: `camset_editor.exe`, `definitions/`, `LICENSE.txt` and the licences page in one folder, zipped. Its `Windows installer` step: Inno Setup builds `camset-editor-<version>-windows-x64-setup.exe` from that folder with `packaging/windows/installer.iss` (`ISCC.exe /DAppVersion=<version> "/DAppCopyright=<copyright sentence>" packaging\windows\installer.iss`), whose notes say what it installs and what it never touches. Its `AppId` must never change: an upgrade finds the earlier install by it. | The editor built, tested and used on a Windows 11 PC (2026-11-12). The zip first shipped with 0.2.1; a downloaded zip not yet tried. The installer, tried on a Windows 11 PC on 2026-11-13, ships from 0.3.0; `editor-ci.yml` compiles it on every pull request. Neither is signed. |

Both Windows steps check the built file's version details (product name, version, description) and fail without them.

## Cutting a release

1. Set `version` in `editor/Cargo.toml` (three numbers, nothing more: the Windows installer's details take it), add
   the release's section to `CHANGELOG.md` and commit it to `main`.
2. Push `main` to GitHub, then tag that commit `v<version>` and push the tag to GitHub only (or both at once:
   `git push <GitHub's remote> main v<version>`). A tag on a commit GitHub's `main` does not hold stops the workflow before
   anything is built: push `main`, then Re-run jobs on the run's page.
3. The tag starts `.github/workflows/editor-release.yml` (run by hand, it builds but publishes nothing):
   1. **test:** the tag's commit is on `main`; the kit's tests, `kit/tools/check_public.py --all` and the editor's
      tests; and the definition viewer as one file, `camset-viewer.html`, from the public definitions only
      (`kit/tools/proof_viewer.py --public --single`).
   2. **build:** on macOS, Linux and Windows, the editor's tests, its licences page and the package (on Windows the zip
      and the installer).
   3. **attest:** `SHA256SUMS`, the checksum of every file the release attaches, and GitHub's build provenance for
      each (`actions/attest-build-provenance`, signed through Sigstore). Only this job may ask for the signing
      identity and store attestations. It first runs for 0.3.0.
   4. **release:** a GitHub Release for the tag with the packages, `camset-viewer.html` (always under that name, so
      <https://github.com/camset-dev/camset/releases/latest/download/camset-viewer.html> is the latest) and
      `SHA256SUMS`, once the files checksum to exactly its bytes.

   Every action is pinned to a full commit, and every `cargo build`, `cargo test` and `cargo about` takes `--locked`.
   A build job the runner cancelled is rebuilt with Re-run failed jobs. On Gitea the attest and release jobs skip
   themselves.
4. Paste the release's `CHANGELOG.md` section onto the GitHub Release as its notes (the workflow writes none), with a
   link named "Code signing policy" to the [policy page](CODE_SIGNING_POLICY.md), which SignPath's terms ask for on
   the download pages.
5. Check one download as a user would, with the README's
   [Check a download](https://github.com/camset-dev/camset#check-a-download): `SHA256SUMS` matches it and
   `gh attestation verify <file> --repo camset-dev/camset --signer-workflow camset-dev/camset/.github/workflows/editor-release.yml`
   passes (`--source-ref refs/tags/v<version>` also requires that release's tag). `--signer-workflow` matters:
   `--repo` alone accepts an attestation made by any of the repository's workflows.

## Dependencies

`.github/workflows/audit.yml` checks the editor's crates and the kit's Python packages against the public lists of
known vulnerabilities: every Monday, by hand, and on a pull request or push to `main` that changes `editor/Cargo.lock`,
`editor/Cargo.toml`, `editor/.cargo/audit.toml` or `kit/requirements.txt`. `cargo audit` (0.22.2) fails on a known
vulnerability and only warns of a crate that is unmaintained, unsound or yanked; `pip-audit` (2.10.1) checks
`kit/requirements.txt` on Python 3.11 and 3.14 (the two numpy pins). An advisory is set aside in
`editor/.cargo/audit.toml` only with what it is, where it comes from and what clears it. By hand, from `editor/`:
`cargo install --locked cargo-audit --version 0.22.2`, then `cargo audit`.

`.github/dependabot.yml` proposes newer versions every Monday, one pull request each for the workflows' actions, the
editor's crates and the kit's packages, with three exceptions moved by hand: `dtolnay/rust-toolchain` (pinned to its
stable branch, which has no release tags), eframe from 0.32 (egui 0.32 rewrote the menus and popups the editor uses,
so it does not build unchanged) and numpy (pinned twice by Python version; an update could break the pin Python 3.11
needs). A pin is raised only when its pull request is merged, after CI. Dependabot's commits carry no sign-off, so the
maintainer takes a bump over in a signed-off commit of their own.

## Other workflows

- **The docs site:** `.github/workflows/docs.yml` builds and publishes it to GitHub Pages on a push to `main` that
  touches its sources, once Pages is enabled (Settings > Pages > Source: GitHub Actions). It is live at
  <https://camset-dev.github.io/camset/>.
- **Statistics:** `.github/workflows/stats.yml` appends the repository's numbers to CSV files on the `stats` branch
  daily. The traffic series need the `STATS_TOKEN` secret: a fine-grained token for this repository only, with
  Administration: read, set under Settings > Secrets and variables > Actions.

## Not yet done

- **macOS:** no Developer ID signature or notarization (both need an Apple Developer account), and no universal
  (Intel and Apple silicon) build.
- **Windows:** no code signing, so SmartScreen warns and Smart App Control may refuse the program. SignPath Foundation
  declined the project for now; what would be signed, and by whom, is the [code signing policy](CODE_SIGNING_POLICY.md),
  and the workflow gets its signing step once an application is accepted.
- **Linux:** no `.deb` or AppImage yet.
- **File types:** none are claimed; `.DAT` is used by many apps.
