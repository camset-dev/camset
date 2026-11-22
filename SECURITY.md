# Security policy

## Report a vulnerability privately

Please do not describe a vulnerability in a public issue.

- Open the repository's [Security tab](https://github.com/camset-dev/camset/security) and choose Report a
  vulnerability. That sends the report to the maintainer alone.
- If that button is not there, open a Bug report titled "Security contact" and write no details in it at all. The
  maintainer then opens a private way for you to send them.

## What is in scope

- the Camset Editor (`editor/`), including its web page and the camera helper it starts;
- the mapping kit's helpers (`kit/`).

The Sony Camera Remote SDK is Sony's; report a problem in it to Sony. A camera's own firmware is Sony's too.

## What to expect

You get an acknowledgement within a week. A fix is made before anything is disclosed, and the report is credited if
you want it to be.

## Releases and dependencies

- From 0.3.0, every package of a release, and its definition viewer, has its SHA-256 checksum in
  the release's `SHA256SUMS` and GitHub build provenance, which says that the release workflow built it from this
  repository; the README's
  [Check a download](README.md#check-a-download) says how to check both.
- The editor's crates and the kit's Python packages are checked against the known vulnerabilities every week and
  whenever their pins change (`.github/workflows/audit.yml`; [Releasing](docs/RELEASING.md), "Dependencies").

## The project's own safety rules

- The kit never reads, types or stores a camera's credentials, and nothing it learns leaves the computer unless you
  send it ([decision 9](docs/decisions/0009-credentials-are-never-read-or-stored.md)).
- What the editor keeps on your computer is listed in
  [What the editor keeps on this computer](docs/EDITOR.md#what-the-editor-keeps-on-this-computer).
