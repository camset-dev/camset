<!-- Sending a camera back: CONTRIBUTING.md says what is checked and why. Tick each line, or say why not. -->
**Camera and firmware:** <!-- model number and firmware, for example ILCE-7M4, firmware 3.01 -->
**How the files were made:** <!-- which of the kit's runs, and what was written or fixed by hand -->
**The pass-2 report:** <!-- kit/pass2_report.py's counts and its conflicts, pasted (it never prints the camera's start values) -->
**The writer's gate:** <!-- the "gate: … open questions …" line kit/schema_update.py prints without --write, pasted -->

- [ ] `data/<model>_fw<fw>/` holds the files docs/DATA_CONTRACTS.md, "What a mapping delivers", marks as needed (`camera_…json`), with the optional ones the mapping made; the menu tree, the accepted rulings and the record shapes stay in `private/evidence/`.
- [ ] The definition, `editor/definitions/<model>_fw<fw>.json`, as `kit/schema_update.py --write` wrote it (lean, never edited by hand), and no other camera's definition changed (CONTRIBUTING.md, "What a contribution must keep").
- [ ] The model's page, `docs/models/<model>_fw<fw>.md`, with its entry in `mkdocs.yml`'s nav.
- [ ] The definition's record names, `docs/formats/sony_camset_ids_<model>_fw<fw>.ksy` (docs/DATA_CONTRACTS.md, "What a mapping delivers", says what writes it).
- [ ] No help text copied from the camera or from Sony's Help Guide: only your own words (decision 13).
- [ ] No personal values: no settings file but a definition's scrubbed sample beside it (`editor/definitions/<model>_fw<fw>.DAT`, made by `kit/tools/make_sample.py`), and no value from the owner's files (decision 16); `.venv/bin/python kit/tools/check_public.py` exits 0, and the diff was searched for the camera's serial number, the owner's name and their network addresses, which it may not know (CONTRIBUTING.md).
- [ ] The definition and the data files match their schemas: `.venv/bin/pre-commit run --all-files` passes.
- [ ] Nothing from `private/` (the evidence file `private/evidence/<model>_fw<fw>.json` among it), `runs/` or Sony's SDK (`kit/sdk/`) is in the pull request.
- [ ] The pull request is one commit of the final files on a fresh branch cut from the updated `main`, so no older commit of your branch publishes a now-private file (docs/UPDATING.md, "Your pull request").
- [ ] Every commit is signed off (`git commit -s`; CONTRIBUTING.md, "Sign off every commit").
