# Code signing policy

**Status: not accepted.** SignPath Foundation declined the project's application for free code signing for now
(2026-11: the project is too new), and the project will apply again later. No Camset program is signed; this page says
what would apply once an application is accepted.

<!-- maintainer, once accepted: make the status line "Status: accepted on <date>; signed from <version>." and the line
below "Free code signing provided by SignPath.io, certificate by SignPath Foundation." -->
Free code signing would be provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

## What is signed

Two Windows files of each release on the project's [Releases page](https://github.com/camset-dev/camset/releases):

- the editor's program, `camset_editor.exe`, which the Windows zip (`camset-editor-<version>-windows-x64.zip`) holds
  and the installer installs;
- the installer, `camset-editor-<version>-windows-x64-setup.exe`, which releases carry from the one after 0.2.1.

Both would be signed only when the release workflow,
[`.github/workflows/editor-release.yml`](https://github.com/camset-dev/camset/blob/main/.github/workflows/editor-release.yml),
built them on GitHub's own runners from a version tag (`v<version>`), after that workflow's tests passed. The
workflow refuses a pushed tag whose commit is not on `main`, before it builds anything; that check is against
mistakes, and a run started by hand skips it (such a run publishes nothing). Signing itself would be limited, in the
project's SignPath settings, to this repository's release workflow run on a version tag.

Nothing else is signed: no program built on anyone's own computer, not the macOS or Linux packages, not the
definition viewer file, and not the mapping kit, nor its camera link and the editor's camera helper, which each person
builds on their own computer from Sony's Camera Remote SDK and which no package carries. The Windows downloads hold the
program, the camera definitions (each with its sample), the project's licence and the third-party licences page:
nothing from Sony's SDK, and the program in them is the one the workflow built from this repository's source.

## How a signed release is built

A release is cut as [Releasing](RELEASING.md#installers) says: the version set and the changelog written, the commit
pushed to `main`, then tagged, and the tag pushed to GitHub. The tag starts the release workflow, which first refuses
a tag whose commit is not on `main`, then runs the kit's and the editor's tests, builds the packages from the source at
that tag, with the Rust crates `editor/Cargo.lock` fixes (every build and test takes `--locked`) and every action
pinned to a commit, and attaches them to the release. Nothing is built or changed by hand in between. Anyone can build
the same program from the tag, with that workflow or with `cargo build --release --locked` in `editor/`; the bytes can
differ from the released program, as the workflow builds with the Rust release that is current when it runs.

Every signing request is approved by hand, by an approver, before anything is signed.

## Team roles

- Committers and reviewers: the maintainer account [camset-dev](https://github.com/camset-dev) on GitHub. Changes
  from anyone else come as pull requests, which are reviewed before they are merged
  ([CONTRIBUTING](https://github.com/camset-dev/camset/blob/main/CONTRIBUTING.md)).
- Approvers: the maintainer account [camset-dev](https://github.com/camset-dev).

## Privacy

Camset Editor will not transfer any information to other networked systems unless specifically requested by the user
or the person installing or operating it.

It has no account, sends no usage data or crash reports and looks for no updates. It talks to a camera only when you
ask it to (Search for cameras, Read, Write), over USB or your own network, through the camera helper you built
yourself. Its web page for a phone or tablet is off until you turn it on, and then answers only browsers that enter
its access code ([The web page](EDITOR.md#the-web-page)). A link in the editor opens in your browser only when you
click it. What it keeps on your computer, and where, is in
[What the editor keeps on this computer](EDITOR.md#what-the-editor-keeps-on-this-computer).

## Reporting a problem

A signed program that does something this page does not say, or a security problem in it: the repository's
[security policy](https://github.com/camset-dev/camset/blob/main/SECURITY.md) says how to report it privately.
