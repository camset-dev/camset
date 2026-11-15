# 24. A look lap opens every row to look at

- **Date:** 2026-11-15
- **Status:** accepted
- **Rule:** A `--network` run looks at any row but what never opens, what acts as it opens and an unseen format,
  delete or reset, and chooses only what a decision names.

## Context

A word list cannot know another camera's row names: the never-open list refused harmless rows (a Custom Key showing
"Voice Memo") and cannot name a new body's own.

## Decision

`kit/crawl_run.py` and `kit/drive.py` given `--network` open every row to look at, no decision naming it, but what
`safety.OWNER_NEVER` names and the Screen Reader, never; a row whose opening acts (`safety.acts_on_open`), only by the
owner's own run; Format, Delete or a reset the never-open list names, by the owner's own run until this body's records
show it opened. A row not yet seen opened goes under the first-open procedure. Inside, the run sends up, down and MENU,
chooses only an option a dated owner decision names, asks local readers only and keeps no screen's text; what the
owner route blanks is saved black. Ordinary runs refuse what they refused, judging the row, never a known value beside
it (`safety.row_judged`).

## Consequences

This cannot protect against a row that acts on being opened where no record changes and no link drops, nor a list
where choosing is the act, which is why choosing stays closed. Nor do the lists tell a misread name from another row:
an action's name read with other text after it ("Format  Slot 1") or with a letter dropped ("SSID/PW Rset") opens as
any row does. There the first-open procedure, the blank cards and sending no Enter are what protect.
