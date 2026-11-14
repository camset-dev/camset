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
