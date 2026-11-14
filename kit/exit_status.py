"""The exit statuses the kit's runners and kit/tools/chain.py share. It imports nothing, so chain.py takes it without
the camera code kit/runner.py brings along."""

EXIT_UNRESTORED = 4     # a run's exit when the camera is not known to be as its start file: a chain stops there
# a run's exit when its last press, which an owner decision allowed with "link_loss" (kit/drive.py --owner), may have
# dropped the link, or left a question open that MENU did not cancel, or when the restore after it did not check out:
# the camera's runs/<model>_fw<fw>/RESTORE_BY_HAND.json names the start file, and no link opens until
# kit/tools/upload_check.py has put it back (camkit.runs); a chain stops there and uploads no end file
EXIT_RESTORE_BY_HAND = 5
# a run's exit when that last press only brought up the row's own question, which the run cancelled with MENU and then
# restored its start file, checked: nothing was confirmed, and drive.jsonl keeps the question's frame as the evidence
# that the row opens to a question; a chain stops there, as after status 4 (its end file is uploaded)
EXIT_NOT_CONFIRMED = 6
# a run's exit when a refusal (camkit.safety.Refused: a press the kit's guards would not send) stopped its work part way
# (kit/crawl_run.py: after a press on a row, or on the way to one; a row whose opening alone is refused is skipped and the
# lap goes on), its start file then put back and checked: the camera is as it was, but what the run was asked to do is not
# done; a chain stops there, as after status 4 (its end file is uploaded). When the restore did not check out, the run
# exits 4 instead
EXIT_REFUSED = 7
# a run's exit when anything but a refusal stopped its work short (kit/crawl_run.py: an error, a screen the scan does not
# know, the start label not reached, the crawl lost or off the scan; kit/drive.py: its --path's first row not reached by
# the scan, none of its presses sent), its start file then put back and checked; a STOP, a complete lap or --limit
# reached exit 0; a chain stops there, as after status 4 (its end file is uploaded)
EXIT_INCOMPLETE = 8
