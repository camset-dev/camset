# Updating your clone

This page is for someone mapping their own camera with a clone of this repository. Every clone takes the steps under
[Every clone: moving to the lean files](#every-clone-moving-to-the-lean-files). A clone made before the history was
replaced takes the steps of the first part before them. The commands are for a Mac or Linux terminal; on Windows run
the git commands in Git Bash (it comes with Git for Windows) and the kit's with `.venv\Scripts\python` where they say
`.venv/bin/python`, as [QUICKSTART](QUICKSTART.md) does. In Git Bash a path takes forward slashes
(`.venv/Scripts/python`).

## If your clone was made before the history was replaced

### What happened

The public history was replaced by a single commit of the current tree. Your clone's history and the new one share no
commit, so do not use `git pull` to update: depending on your git settings it stops with an error ("refusing to merge
unrelated histories", "divergent branches", "Not possible to fast-forward"), or, set to rebase, it stops half way
with conflicts, or seems to work and leaves your branch on the new commit with your commits replayed on top. The
steps below end in the right place from any of these. Nothing you made is lost: your runs and your own files stay on
your computer. You move your clone onto the new commit, bring your own files across, and write your report and
definition again with the updated kit.

### Why update before going further

- **The camera's safety.** The older kit could send a key other than MENU on the shooting screen, where the camera
  does whatever its owner assigned to that key. The updated kit refuses that unless the run names the key
  ([decision 21](decisions/0021-on-the-shooting-screen-no-key-but-menu-unless-it-is-named.md)).
- **Your own settings.** A definition written by the older kit can tell what your camera was set to when the
  mapping started: which value a row started on, which records each choice wrote together, a state the camera was
  found in. The updated writer leaves those out
  ([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)), and you write your
  definition afresh with it rather than over the older one. Do not send a definition the older kit wrote.

### Move your clone onto the new commit

Run these from the top of your clone. Replace `<model>_fw<fw>` with your camera's, for example `ILCE-7M4_fw3.01`.

1. Look at where you are: `git status`. If it says a rebase is in progress (an earlier `git pull` stopped half way),
   run `git rebase --abort`; if it says you are merging or have unmerged paths, run `git merge --abort`. Then
   `git status` again: it names the branch you are on. Also run `git stash list`. If it lists a stash, leave it where it
   is for now: it is applied at the very end, after [Every clone](#every-clone-moving-to-the-lean-files) step 5
   (its step 6 says how).

2. Commit everything you have not committed, on the branch you are on:

   ```sh
   git add -A
   git status
   git commit -s -m "My work before the update"
   git status --short --untracked-files=no
   ```

   `git add -A` adds every file you made or changed that git does not ignore; `runs/`, `private/`, Sony's SDK in
   `kit/sdk/`, `.venv/` and the builds are ignored and stay out on their own. If `git status` then lists a file that
   is not part of your mapping (your agent's own settings in `.claude/`, say), take it out before committing
   with `git restore --staged <path>`; it stays on your computer. If `git commit` says there is nothing to commit,
   your work was already committed. The last command must print nothing: every change is now in a commit.

3. Fetch the new commit, and find the last commit of the old history your work started from:

   ```sh
   git fetch origin --tags --force
   old=$(git merge-base HEAD origin/main || git merge-base HEAD 'origin/main@{1}')
   git log -1 --oneline "$old"
   ```

   The first `merge-base` finds nothing (the two histories share no commit) and the second finds where `main` stood
   before the fetch. If `git remote -v` shows that `origin` is your own fork, run
   `git fetch https://github.com/camset-dev/camset.git main` after `git fetch origin`, and in step 5 reset to
   `FETCH_HEAD` instead of `origin/main`. If neither `merge-base` finds a commit (`git log` says `$old` is empty), use
   `old=40446ca41c495596567391b3b7efc1b69130b14c`, the last commit of the old history, or `old=839689a` if your
   clone is from its first commit.

4. Keep every branch that has commits of your own under a new name, `main` among them. List your branches, then each
   one's own commits:

   ```sh
   git branch -vv
   git log --oneline "$old"..main
   git log --oneline "$old"..my-camera
   ```

   Run the `git log` line for each branch `git branch -vv` lists (its "ahead" and "behind" counts do not tell, as the
   two histories share nothing). A branch whose line prints nothing has no commit of its own: leave it, or delete it
   with `git branch -D <branch>`. Keep each one that prints commits: `main` under a copy, since step 5 moves `main`
   itself, and every other one renamed, so its name is free for the new history:

   ```sh
   git branch my-main-old main
   git branch -m my-camera my-camera-old
   git branch -vv
   ```

   (one `git branch -m <branch> <branch>-old` per other branch with commits of its own; if a name is taken already,
   choose another). `git branch -vv` then shows each `-old` branch on your last commit.

5. Move `main` onto the new commit, and start a branch for your camera from it:

   ```sh
   git switch main
   git reset --hard origin/main
   git switch -c my-camera
   ```

6. Bring your own files back from each branch you kept. List what each one added, changed or deleted:

   ```sh
   git diff --name-status "$old"...my-camera-old
   git diff --name-status "$old"...my-main-old
   ```

   and bring back each camera's folder, its page and its sample from the branch that holds its latest version:

   ```sh
   git checkout my-camera-old -- data/<model>_fw<fw> docs/models/<model>_fw<fw>.md
   git checkout my-main-old -- data/<other model>_fw<fw>
   git status --short
   ```

   Name only paths the lists showed: if git answers that a path "did not match", it restored nothing at all from that
   command; run it again without that path. Bring back a definition's sample (`editor/definitions/<model>_fw<fw>.DAT`,
   made by `kit/tools/make_sample.py`) the same way, but not your definition (`editor/definitions/<model>_fw<fw>.json`),
   your record names file (`docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`) or `mkdocs.yml`: they are written
   again below, a second camera's definition with `--camera <other model>_fw<fw>`. Never copy a kit or docs file of
   an old branch over the new one either: many changed in this update. Where a list shows one you changed (the
   never-open list in `kit/camkit/safety.py`, say), see what you changed with
   `git diff "$old"...my-camera-old -- kit/camkit/safety.py` and make the same change by hand in the new file. Do not
   commit yet: [Every clone](#every-clone-moving-to-the-lean-files) step 7 commits it all, the files
   `kit/tools/move_evidence.py` moves out of `data/` already gone.

`git reset --hard` changes only the files git tracks. These stay as they were: `runs/` (your frames, downloads,
`downloads.jsonl`, proofs, attempts and scans), `private/` (your config and camera files), `kit/sdk/` (Sony's SDK and
its builds), the built camera helper and the other builds, `.venv/`, and your stashes.

You need not run `python3 kit/setup.py` again for the kit: the camera helper's source, the kit's Python requirements
and the setup itself are as they were. If you built the editor from your clone, build it again, as its code changed:
`python3 kit/setup.py --editor` (on Windows `py kit\setup.py --editor` in a Command Prompt or PowerShell, or
`py kit/setup.py --editor` in Git Bash).

Keep the `-old` branches until your pull request is in; `git branch -D my-camera-old my-main-old` removes them after.
Never open a pull request from one of them, nor from a branch they are merged into: their commits hold the files that
are private now ([Your pull request](#your-pull-request-one-commit-on-a-fresh-branch)).

### Packages and tags

The release is `v0.2.0`, on the new commit. 0.1.0 is withdrawn: its tag and its packages are gone from GitHub, and
its editor does not open a definition the updated kit writes, nor the 0.2.0 editor one the older kit wrote. If you
downloaded a 0.1.0 package, take 0.2.0 from the Releases page instead.

A clone made earlier still has a `v0.1.0` tag of its own, on the old history; a plain fetch, or step 3's, neither moves
nor removes it. Remove it with `git tag -d v0.1.0`. (`git fetch --prune --prune-tags origin` removes it too, but also
every other tag in your clone that `origin` does not have, your own among them.)

### What changed for a mapper since the older kit

- **Keys on the shooting screen.** Only MENU goes out there unless the run names the key
  (`kit/drive.py --on-shooting KEY`), given only with your owner's word for that key.
- **The owner's word, per run.** `afreg_run.py`, `customshoot_run.py`, `customshoot_values.py`, `mymenu_run.py` and
  `card_actions.py` refuse to start without their `--allow` words, and `kit/drive.py` sends C4 as Focus Area's SET or
  a Creative Look's Reset only with `--c4-press c4set` or `--c4-press c4reset`. A command line from your notes may be
  refused: add the words only when your owner has said yes.
- **A slider inside a panel.** `kit/provers/scale_run.py --panel-row` needs the panel's setup row among its `--set`
  rows (`--set "ROW > SETUP=Manual"`; the refusal prints the one to add). Prove again a slider you proved without it.
- **The report.** `kit/pass2_report.py` leaves out proofs that only show where the camera stood, so your counts may be
  lower than the older kit's. No proof is thrown away from `runs/`.

### Your definition, written afresh

Now take the steps of [Every clone](#every-clone-moving-to-the-lean-files) below, from its step 2. Your definition is
not there after step 6 above, so at its steps 4 and 5 run these instead, with your camera the one the kit works on
(`"camera"` in `private/config.json`, or `--camera <model>_fw<fw>`): the first report takes `--no-schema`, and the
writer starts the definition from your `data/` folder.

```sh
.venv/bin/python kit/pass2_report.py --no-schema
.venv/bin/python kit/schema_update.py            # a dry run: read what it would write
.venv/bin/python kit/schema_update.py --write
git add editor/definitions/<model>_fw<fw>.json
.venv/bin/python kit/pass2_report.py && .venv/bin/python kit/schema_update.py --write
git diff --exit-code editor/definitions/<model>_fw<fw>.json
.venv/bin/python kit/tools/build_docs.py         # the record names and the model page's nav entry
```

The `git diff` must print nothing: a second write gives the same file. Send only the definition the updated kit wrote.

## Every clone: moving to the lean files

The definition and `data/` now hold only what is the same for every owner of a model and firmware; how each thing was
proved, and your own mapping's files, stay in `private/evidence/`, which is never committed. Run these from the top
of your clone, in this order. Replace `<model>_fw<fw>` with your camera's.

1. **Update.** Commit your work first (`git status` must list nothing you want to keep uncommitted:
   `git add -A` and `git commit -s -m "My camera before the update"` on your camera's branch). Then bring `main` and
   your camera's branch up to date from the project:

   ```sh
   git fetch origin
   git switch main
   git merge --no-edit origin/main
   git switch my-camera
   git merge --no-edit origin/main
   ```

   Use `git fetch` and `git merge` rather than `git pull`: if you ever committed on `main`, `git pull` stops with
   "Need to specify how to reconcile divergent branches", and the merge is what it would have done. If `origin` is your
   own fork, fetch the project instead (`git fetch https://github.com/camset-dev/camset.git main`, then
   `git merge --no-edit FETCH_HEAD`). A clone made before the history was replaced takes
   [the first part](#if-your-clone-was-made-before-the-history-was-replaced) instead of this step.

   If a merge stops with "CONFLICT", `git status` lists the paths under "Unmerged paths". In a merge, "ours" is your
   branch, the one you are on, and "theirs" is what you merge in, the project's `origin/main` (in a stash, step 6,
   it is the other way round). Keep your own version of your camera's files and the project's of everything else:

   ```sh
   git checkout --ours -- data/<model>_fw<fw>/<the file>
   git checkout --theirs -- <any other path, a kit or docs file>
   git add <each path you settled>
   git status
   git commit --no-edit
   ```

   Where you had changed a kit or docs file (the never-open list in `kit/camkit/safety.py`, say), make your change
   again by hand in the project's version before its `git add`. Commit once `git status` lists no unmerged path. Your
   definition is written again at step 5, so take the project's version of it or yours, as you like.

2. **Move your private files, once.** Your menu tree, your accepted rulings and your record shapes are kept in
   `private/evidence/<model>_fw<fw>/` now, and the kit no longer reads them in `data/<model>_fw<fw>/`. If they are
   still there, move them with

   ```sh
   .venv/bin/python kit/tools/move_evidence.py
   ```

   (`.venv\Scripts\python kit\tools\move_evidence.py` on Windows; `--camera <model>_fw<fw>` for a camera other than
   the one `private/config.json` names). It prints one line per file. What `git status --short` then shows depends on
   how your clone came to this update, and either is right:

   - updated by the merge above (your files were committed in `data/`): ` D` before each moved file (`git status`
     says "deleted"), and ` M` before your reset file if it was made lean; your next commit takes the change.
   - made before the history was replaced ([the first part](#if-your-clone-was-made-before-the-history-was-replaced),
     its step 6 brought your camera's folder back with `git checkout`, which stages it as new): `AD` before each moved
     file, added and then deleted (`git status` lists it as "new file" to be committed and again as "deleted" not
     staged), and `AM` before a reset file made lean; `git add -A` at step 7 leaves the moved files out of the commit
     altogether, and commits the lean reset file.

   If a file is in both places and the two differ, or
   one is not readable, it stops, moves nothing and names the files: keep the one you want, delete the other, and run
   it again. Until you do, the commands that read or write these files stop and print this command:
   `kit/pass2_report.py`, `kit/schema_update.py --write`, `kit/tools/menu_tree.py`, `kit/tools/set_twins.py` and
   `kit/provers/mymenu_run.py`; the other provers and `kit/drive.py` do not read them and go on. The same command
   makes your reset file lean, when it is in the older whole shape (the tests' own words and dates in it): it keeps
   the whole file in `private/evidence/<model>_fw<fw>/`, which the kit never reads again, and writes the lean one in
   `data/`, saying so in one line. From then on you edit the reset file in `data/` itself
   ([DATA_CONTRACTS](DATA_CONTRACTS.md#the-reset-file-what-each-reset-puts-back)). If `CAMSET_EVIDENCE_DIR` is set,
   it says so: the files go into this clone's own `private/evidence/`, so point `CAMSET_EVIDENCE_DIR` there, or copy
   them into the folder it names.

3. **Record each page scan's mode, once.** A command takes a page scan by default only when the scan says which
   shooting mode it was made in. For each scan you made before this update, say it once, only for a scan you know
   was made in that mode (its own run log or frames say it):

   ```sh
   .venv/bin/python kit/page_model.py --mode Stills kit2_page_scan
   .venv/bin/python kit/page_model.py --mode Movie kit2_page_scan_movie
   .venv/bin/python kit/page_model.py --mode "S&Q" kit2_page_scan_sq
   ```

   Use your own scans' run names. Until a scan records its mode, a command takes it only when `--scan <run>` names
   it. A new scan takes the mode on its command line (`kit/page_scan.py --mode Stills --run <a new run>`), and becomes
   the default only once its lap is whole and `kit/page_model.py` has built its page model after it. If a command
   stops on a mode switch waiting from an earlier session, read what it prints, and look at the camera's screen (or
   ask its owner) which mode it shows: a record left over after the camera was put back is removed with
   `kit/provers/mode_switch.py --forget --shows <the mode it shows> --run <run>` (the family first, then the exposure
   mode when you say one: `--shows Movie`, `--shows "Stills M"`), which sends nothing and refuses while the screen
   shows the mode the switch went to.

4. **The report.** `.venv/bin/python kit/pass2_report.py`

5. **The definition.** `.venv/bin/python kit/schema_update.py --write`. It rewrites
   `editor/definitions/<model>_fw<fw>.json` in the lean form (definition format 2, which this editor needs), with no
   run names, dates or per-proof menu rows, and writes the evidence it left out to
   `private/evidence/<model>_fw<fw>.json`. In your reset file it only brings each setting's name and tab in line with
   the definition. Your `runs/` are not changed. If it stops because evidence went stale (a setting's key renamed in
   this update, say), read the settings it lists; when the definition is right, run it again with `--accept-stale`,
   and later `kit/schema_update.py --drop-stale` lists what is kept aside and `--drop-stale --write` removes it. If it
   says the last write was cut short, run the `--finish-write` it names, then `--write` again. If the report says
   table rows the kit renamed need walking again, prove them with `kit/prove_run.py --tables ...` only then; the
   playbook's [Phase 2](REMAPPING_PLAYBOOK.md#phase-2-prove) has the command, under "Assignment screens".

6. **A stash from before the update.** If `git stash list` lists one you want, apply it now, with nothing committed
   since step 5:

   ```sh
   git add -A
   git stash pop
   ```

   `git add -A` first, as `git stash pop` refuses to start while a file it changes has changes you have not staged.
   If it prints "CONFLICT", `git status` lists the paths under "Unmerged paths". In a stash, "ours" is your branch as
   it is now, updated, and "theirs" is the stash (the other way round from a merge, step 1). Settle each path:

   - your definition, `editor/definitions/<model>_fw<fw>.json`: keep the one step 5 wrote,
     `git checkout --ours -- editor/definitions/<model>_fw<fw>.json`;
   - your other camera files in `data/<model>_fw<fw>/` (the reset file among them): keep the stash's, your later
     work, `git checkout --theirs -- data/<model>_fw<fw>/<the file>`;
   - a menu tree, accepted file or record shapes git says was "deleted by us" (step 2 moved it): the stash's is your
     later copy; put it where the kit keeps it, over the older one, and take it out of git:
     `git checkout --theirs -- data/<model>_fw<fw>/<the file>`, then
     `mv data/<model>_fw<fw>/<the file> private/evidence/<model>_fw<fw>/` and
     `git rm -q --cached data/<model>_fw<fw>/<the file>`;
   - a kit or docs file: keep the updated one, `git checkout --ours -- <path>`, and make your change again by hand.

   Then `git add` the paths you kept, and once `git status` lists no unmerged path, `git stash drop` (a stash that
   conflicted is kept until you drop it). Run steps 2 and 5 again: the stash may have brought back a reset file in the
   older shape, or changed what the definition is written from.

7. **The checks.** Commit, then run the checks a pull request needs
   ([CONTRIBUTING](https://github.com/camset-dev/camset/blob/main/CONTRIBUTING.md), "What a contribution must keep"):

   ```sh
   git add -A
   git commit -s -m "<model>_fw<fw>: data and definition"
   .venv/bin/python kit/tools/check_public.py --all
   .venv/bin/pre-commit run --all-files
   ```

   On Windows: `.venv\Scripts\python` and `.venv\Scripts\pre-commit`. `--all` reads every tracked file, as the pull
   request's own check does; it refuses the three private files in `data/` and a reset file that is not lean. Then
   search your diff (`git diff origin/main my-camera`) for your name, your camera's serial number and your network
   addresses, which the check may not know.

### Your pull request: one commit on a fresh branch

The last step, only if you will send your camera back. The older commits of your branch still hold files that are
private now (your menu tree, your accepted rulings, your record shapes, a reset file with the tests' words, a
definition with its evidence), and a pull request publishes its branch's whole history, not only its last files; the
pull request's own check (`check_public.py --commits`) holds every file each commit adds or changes to the rules
`--all` holds your files to, and refuses any commit that added one, though a later commit took it out. So open it from a fresh branch cut from the updated
`main`, with one commit of your final files:

```sh
git fetch origin
git switch --no-track -c my-camera-pr origin/main
git checkout my-camera -- data/<model>_fw<fw> editor/definitions/<model>_fw<fw>.json docs/models/<model>_fw<fw>.md docs/formats/sony_camset_ids_<model>_fw<fw>.ksy
.venv/bin/python kit/tools/build_docs.py --no-viewer
git add mkdocs.yml docs/formats/sony_camset_ids_<model>_fw<fw>.ksy
git status --short
.venv/bin/python kit/tools/check_public.py --all
git commit -s -m "<model>_fw<fw>: data and definition"
git log --oneline origin/main..my-camera-pr
git push -u origin my-camera-pr
```

Add your definition's sample (`editor/definitions/<model>_fw<fw>.DAT`) to the `git checkout` line if you made one.
On Windows the Python lines are `.venv\Scripts\python kit\tools\build_docs.py --no-viewer` and
`.venv\Scripts\python kit\tools\check_public.py --all`. `build_docs.py` writes your model page's entry in
`mkdocs.yml`'s nav and your record names; `git status --short` must list only your camera's files and
`mkdocs.yml`, and `git log` exactly one commit. Push to your own fork if `origin` is the project's, and open the
pull request from `my-camera-pr`. Keep mapping on `my-camera`; for a later pull request, make a new fresh branch
the same way.

### Commands whose arguments changed

A command line from your notes may need these:

- `kit/page_scan.py` needs `--mode Stills`, `Movie` or `S&Q`, the mode the camera is in.
- `kit/tools/set_twins.py` needs `--evidenced <run>`, the run whose registration of the memory slot is evidence
  already, or `--evidenced ''` for none.
- `kit/provers/filter_run.py`, `kit/provers/mymenu_run.py` and `kit/provers/mode_switch.py` take `--in MODE`, the
  shooting mode the camera is in (Stills unless you say; `mode_switch.py --set` takes the mode its waiting switch
  left), and by default the latest page scan of that mode.
- `kit/provers/mode_switch.py --forget --shows` takes the family first (Stills, Movie or S&Q) and, as a second word,
  the exposure mode the screen shows (P, A, S, M or Auto): `--shows Movie`, `--shows "Stills M"`, `--shows "Movie
  Auto"`. A letter alone (`--shows M`) is refused, since Movie's and S&Q's screens show one too.
- `kit/schema_update.py --drop-stale` only lists the evidence kept aside; `--drop-stale --write` removes it.
