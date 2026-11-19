# 15. Every run starts from a known file and ends restoring it

- **Date:** 2026-10 (first kit); changed 2026-11-19
- **Status:** accepted
- **Never broken:** 12th in AGENTS.md's list
- **Rule:** Every run starts from a known file and ends restoring it: it downloads its start file first and, at its end,
  uploads it, waits for the camera's restart, downloads again and checks the records match, and live state the file does
  not hold is put back by hand and checked; a session ends with the owner's own file back, never a run's changes left on
  the camera but a user LUT, which stays until the owner deletes it by hand
  ([decision 26](0026-a-user-lut-reaches-the-camera-only-through-the-kit-s-import-tool.md)). A run is stopped with its STOP file (a file named `STOP` in the run's folder,
  `runs/<model>_fw<fw>/<run>/STOP`, which the run checks; `kit/camkit/runs.py` names wider ones; see the playbook's
  [section 10](../REMAPPING_PLAYBOOK.md#10-recovering-from-a-stopped-run)) or, once its link is open, one Ctrl-C, after
  which it cancels and restores (a second Ctrl-C stops it at once, which is not safe); a run is never killed, nor the
  camera disconnected, with a dialog open: a dropped session can apply it.

## Context

A run that crashes before its restore leaves the next run starting from its leftovers; some state lives outside the
file (the focus point, the zone's place); and a session dropped with a dialog open applies what the open dialog
shows.

## Decision

A run downloads a start file first and, at its end, uploads it and checks that 0 records differ; live state the file
does not hold is put back by hand and checked. A user LUT the kit imported is such state, left on the camera as its
owner allowed: they put it back by deleting it.

Before 2026-11-19 AGENTS.md and the playbook's rules 5 and 6 each stated the rule by hand beside a shorter Rule line,
and the Rule line allowed a run to leave nothing on the camera.

## Consequences

The owner's camera is as it was after every session, but for a user LUT imported on their word.
