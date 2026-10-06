---
name: osc-run
description: Run research experiments on OSC (Ohio Supercomputer Center) through SLURM — sync code, preflight the sbatch script, smoke-test on Pitzer, submit the full job, monitor it, fix failures, and report results. Use when the user asks to 跑实验, 提交到 OSC, submit or debug an sbatch/SLURM job, or run something on Pitzer, Ascend or Cardinal for a research repo. Not for course homework (that is the course-homework skill).
---

# OSC Run

Research experiments go to OSC as SLURM jobs. Most failures seen so far were environment problems a short job would have caught: a working directory that did not resolve under SLURM, a Hugging Face dataset ID without its namespace, a missing log directory. So every run goes small → smoke → full.

## Clusters and accounts

| Host | ssh | Used for |
|------|-----|----------|
| Pitzer | `ssh xzascc3944@pitzer.osc.edu` | Smoke tests (short debug jobs) |
| Ascend | `ssh osc` (`ascend.osc.edu`) | Full GPU runs, e.g. PostDyn: `--account=PAS2324 --partition=nextgen` |
| Cardinal | `ssh cardinal` | Full GPU runs |

Take the account, partition and repo path on OSC from the repo's existing `*_osc.sh` / `*.sbatch` scripts. If none exist or the account is unclear, ask. PAS2386 is the course project; do not use it for research.

## 1. Follow the repo's rules first

Read the repo's `AGENTS.md`, `AGENTS.local.md`, `CLAUDE.md` and `CLAUDE.local.md`. They override this skill. PostDyn, for example, requires passing local tests and a small end-to-end run on the local RTX 4090 before any OSC submission.

## 2. Sync code

Commit and push, then update the checkout on OSC (or rsync if the repo is not on git there). Check that `git rev-parse HEAD` on OSC matches the local commit before submitting.

## 3. Preflight the job script

Check each item before `sbatch`:

- **Working directory:** an absolute path or `cd "$SLURM_SUBMIT_DIR"`. Never `cd "$(dirname "$0")"`: SLURM runs a copy of the script from its spool directory.
- **Log directories:** the directories in `--output` / `--error` exist before submission. SLURM does not create them, and the job dies without a log.
- **Dataset and model IDs:** fully namespaced (`Salesforce/wikitext`, not `wikitext`). The smoke job must load every dataset and model the full job uses.
- **Partition and account:** the partition exists on that cluster (`sinfo -s`) and the account is right. On Pitzer, `batch` and `debug` show `INACTIVE` but are routing partitions.
- **Environment:** `module load` lines, `uv sync`, `HF_HOME` on a filesystem with enough space.
- **Resources:** `--time`, `--mem` and GPU count fit the job; incremental results are written as the job runs (most repos require this).

## 4. Smoke test on Pitzer

Submit the same script on Pitzer with a tiny size (small `--n`, one model, one condition) and a short limit (`--time=00:15:00` or less, debug partition). It must finish, write the expected result files and logs, and load every dataset and model. Fix anything it shows before going on.

## 5. Submit the full job

If the run is large (a sweep of many jobs or many GPU hours), state the job count and estimated GPU hours and wait for the user's OK. Then submit and record the job IDs.

## 6. Monitor

Watch with `squeue -u xzascc3944`, `sacct -j <id> --format=JobID,State,Elapsed,ExitCode` and `tail` on the `.out` / `.err` files. Use a background Monitor rather than repeated sleeps.

On failure: read the `.err` file, fix the root cause (not the symptom), and resubmit. If the cause is a new kind of environment problem, add it to the preflight list in step 3. If the same job fails 3 times, stop and ask the user.

## 7. Report

In Chinese: cluster and job IDs, what failed and how it was fixed, where the results are, and the key numbers as a short table. Do not edit the manuscript with the results unless the repo's rules let Claude do so and the user asks.
