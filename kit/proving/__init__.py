"""The prover's parts; kit/prove_run.py is the entry point and runs the session (docs/KIT_PLAN.md, pass 2).

    base        the run's places (pass 1's map, the table and axis walks), Failed and the other ends of a row, the
                proofs file (Tagged), the attempts file, pass 1's saved frames
    screens     what the screen shows: the label under the cursor, a carousel's title, notices after a choice
    nav         to a row and back, the short way round a list, out with MENU, back to the shooting screen
    options     which option the cursor is on (labels, stars, icons, a picker's place)
    putback     what a row's put-back may leave differing without failing
    jobs        what a run proves: pass 1's map in the reviewed scope, one job per row, and when a job is done
    fields      number fields          sidelists   Picture Profile's side lists     checklists  checkboxes
    looks       Creative Look panels   wbgrid      White Balance fine-tune grids    tables      tables, tiles, keys
    helptext    --help-text: the In-Camera Guide of each row and option

The list prover itself (prove_row, with its display proof), the carousels' second axes (prove_axis_row), the session
and main stay in kit/prove_run.py, which also gives every name here under its old place (prove_run.option_key), so
the walkers and provers that import them from there are unchanged.
"""
