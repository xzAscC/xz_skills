# Branches and worktrees

Adapted from obra/superpowers (`using-git-worktrees`,
`finishing-a-development-branch`).

## Start

1. Check whether you are already isolated:

   ```bash
   GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
   GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
   git rev-parse --show-superproject-working-tree   # a path means submodule, not worktree
   ```

   If `GIT_DIR != GIT_COMMON` and you are not in a submodule, you are already
   in a linked worktree. Do not create another one.
2. Work directly on the current branch when the project does that (for
   example a personal notes repository). Otherwise, for feature work on the
   default branch, ask once: "Work on a new branch, a worktree, or in
   place?" Respect a preference already stated in the instructions.
3. For a worktree, use the harness's native tool first (for example
   `EnterWorktree`). Use `git worktree add` only when there is none. Then put
   it under `.worktrees/`, and run `git check-ignore -q .worktrees/` first
   (keep the trailing slash: without it, a `.worktrees/` pattern does not
   match a directory that does not exist yet). If the directory is not
   ignored, add it to `.gitignore` before you create it.
4. Run the tests once before you change anything. If they fail, report the
   failures and ask whether to continue.

## Finish

1. Run the full test suite on the tree you will integrate. A green run from
   earlier proves nothing about this tree. If tests fail, report and stop.
2. Find the base branch from the plan, the conversation or the upstream. If
   it is not certain, ask: "This branch split from <guess> — correct?"
3. Present exactly these options and wait. The decision belongs to the user:

   ```
   Work is complete. What next?
   1. Merge into <base> locally
   2. Push and open a pull request
   3. Keep the branch as it is
   ```

   On a detached HEAD, offer only 2 (push as a new branch) and 3.
4. Execute the choice:
   - **Merge**: go to the main checkout, `git checkout <base>`, `git pull`,
     `git merge <branch>`, run the tests on the merged result. If they fail,
     stop and leave branch and worktree in place. If they pass, remove the
     worktree, then `git branch -d <branch>`.
   - **PR**: when the `pr-review` skill is installed, follow it instead: it
     opens a draft PR, reviews it and writes a report for the user. Otherwise
     `git push -u origin <branch>`, open the PR with the forge CLI
     (for example `gh pr create`) using the repository's PR template, report
     the URL. Keep the worktree for review fixes.
   - **Keep**: report the branch name and worktree path.
5. **Discard** only when the user asks for it explicitly. List the branch,
   its commits and the worktree path, then ask the user to type `discard`.
   "Yeah, get rid of it" is not the confirmation. After `discard`, remove the
   worktree and `git branch -D <branch>`.

## Cleanup rules

- Remove only worktrees that you created under `.worktrees/`. Other
  worktrees belong to the user or the harness.
- Run `git worktree remove` from outside the worktree. If git refuses
  because of modified or untracked files, never use `--force`. Show
  `git -C <path> status --porcelain -uall` and ask: commit them, move them,
  or delete them.
- A rejected push means the remote moved. Investigate. Force-push only when
  the user asks for it.
