---
name: git-workflow
description: How to commit, group changes, write commit messages, and start or finish a branch or worktree. Use before any git commit, whenever a project asks you to commit your work, and when the user says 提交, commit, 开分支, 合并, 开 PR, push, or asks to finish, merge or discard a branch or worktree.
---

# Git Workflow

Adapted from three sources: the seven rules in Chris Beams, "How to Write a
Git Commit Message"; the safety gates and batch grouping of
mustafakbaser/claude-commit-skill; and the branch finishing flow of
obra/superpowers. Commits are hard to take back once pushed. The expensive
mistakes are content nobody reviewed, leaked secrets and broken merges, not
bad wording. Check safety first, then write a good message.

## 1. When to commit

- One commit is one logical change, not one user message. Five small
  follow-up edits on the same topic make one commit.
- While a topic is still active, keep its changes uncommitted. Commit when
  the topic is finished, before you start a different topic, or when the user
  says 提交 / commit. If a project instruction says "commit after work", read
  it as "commit when the task or topic is finished".
- For code: commit when one step is complete and its tests pass. Do not commit
  a broken tree to "save progress".
- At the end of a reply that leaves changes uncommitted, say so in one line.
- Do not push unless the user asks or the project instructions say to push.

## 2. Preflight

```bash
git status --short                 # what changed; did I make each change?
git diff --stat HEAD               # size of each change
git log --oneline -15              # the repository's message convention
git rev-parse -q --verify MERGE_HEAD; ls "$(git rev-parse --git-dir)" | grep -E '^(rebase-|CHERRY_PICK_HEAD|REVERT_HEAD)'
git branch --show-current          # empty output means detached HEAD
```

Read the diff of every file you will commit before you write its message.

## 3. Safety gates

Each gate is a stop. Do not continue and report the problem afterwards.

| Condition | Action |
|---|---|
| Merge, rebase, cherry-pick or revert in progress | Do not split or re-stage. Offer only a plain `git commit` that keeps the operation. |
| Unresolved conflicts | Stop. Resolve them first. |
| Detached HEAD | Stop. Ask before you commit, because these commits are lost at the next checkout. |
| Possible secret (`.env`, keys, tokens, `credentials*`) | Stop and list the files. Stage one only when the user names it. Offer `.gitignore` instead. |
| File larger than 5 MB, or binary media | Stop and confirm. History keeps every blob forever. |
| A file you did not change | Do not stage it. It is the user's work in progress. |
| A file you changed that also has hunks you did not write (another session or the user) | Stop. Show those hunks and ask: commit them together, or wait. |
| File with hand-picked hunks (staged and unstaged parts) | Do not commit the whole file. Ask first. |

Never, unless the user asks for it explicitly: `--no-verify`, `--force` or
`--force-with-lease`, `git reset --hard`, `git clean`, `git stash pop`,
`--amend` on a pushed commit, `git config` changes, history rewrites.

## 4. Group the changes

1. Bind files that must ship together: code and its tests, a manifest and its
   lock file, a source and its generated output, both paths of a rename, a
   note and the metadata file that changed with it.
2. Group by intent (feature, fix, refactor, docs, deps, cleanup). Then group
   by what owns the change: the feature, the package or the topic, not the
   directory depth.
3. Aim for 2–5 commits. More than 7 is too fine. One group means one commit.
   If changes are truly tangled, make one honest commit, not an artificial
   split.
4. Order: dependencies and build, then refactor, then feature, then fix,
   then docs and cleanup.
5. If there is more than one group, show the plan (each group, its files and
   its subject line) and wait for approval. Tell the user that intermediate
   commits may not build. A single group needs no approval.

## 5. Write the message

The repository's convention comes first: a `commit-msg` hook, a commitlint
config, or the pattern in `git log` (for example `area: description`, or
Conventional Commits `type(scope): description`). Use the scopes that history
already uses. When there is no convention, use the seven rules:

1. Separate the subject from the body with a blank line.
2. Limit the subject to about 50 characters (hard limit 72).
3. Capitalize the subject line.
4. Do not end the subject with a period.
5. Use the imperative mood: "Add", "Fix", not "Added", "Fixes".
6. Wrap the body at 72 characters.
7. Use the body to explain what and why, not how.

The diff shows what changed. Only the conversation shows why: the bug you
reproduced, the constraint you found, the option you rejected. Put that in the
body. If the subject needs "and", it is two commits. Add the attribution
trailer that your instructions require.

## 6. Execute and verify

Other sessions may work in the same tree and share its index, so a plain
`git commit` can take what they staged, and theirs can take yours. Commit
with `--only`: git builds a temporary index from HEAD plus the paths you
name, holds the index lock, and ignores everything else that is staged.

1. Write the message to a file in the scratchpad. Do not use `-m` with a
   heredoc, because a body line that reads `EOF` cuts the message.
2. For each untracked path (a new file, or the new path of a rename done
   with plain `mv`), run `git add -N -- <path>`. This records only the
   path, so no other commit can take its content. Never `git add -A` or
   `git add .`.
3. `git commit --only -F <message-file> -- <path> <path>` with every path
   of the commit (both paths of a rename), then check the exit code. A
   clean `git status` does not prove success (signing and hook failures
   look the same). During a merge, rebase or cherry-pick, git refuses a
   partial commit: use plain `git commit -F <message-file>` (section 3).
4. If git says `index.lock` exists, another git command is running. Wait a
   few seconds and retry, at most three times. Never delete `index.lock`.
5. `git show --stat --format='%h %s' HEAD` to see what landed (hooks can
   rewrite the message). It must hold only your paths and files that a
   hook adds. Record the short SHA.
6. `git status --short`: if a hook rewrote files after the snapshot, stop and
   report. Do not sweep them into the next commit. A file shown as `MM`
   that a pre-commit hook stages went only into the temporary index; run
   `git reset -q -- <path>`, unless a post-commit hook already does.
7. If a hook rejects the commit, report its output, fix the cause and make a
   new commit. Do not amend and do not retry with `--no-verify`.
8. In batch mode, stop at the first failure and report what was committed
   and what remains. Unstage only your own paths with
   `git restore --staged -- <paths>`, never a blanket `git reset`.

To fix an older unpushed commit, use `git commit --fixup=<sha>`. Squash it
with `git rebase --autosquash` only after the user approves the rewrite.

## 7. Branches and worktrees

Read `branches.md` in this directory when you start feature work that may
need its own branch or worktree, or when the work on a branch is finished
and must be merged, opened as a PR, kept, or discarded.
