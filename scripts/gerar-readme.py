#!/usr/bin/env python3
"""Gera o README.md a partir de bugs-cfs.csv (contagens e tabela de bugs sempre coerentes)."""
import csv
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
bugs = list(csv.DictReader(open(RAIZ / "bugs-cfs.csv")))
n = len(bugs)
orig = sum(b["tests"] == "original" for b in bugs)
core = sum(b["core"] == "yes" for b in bugs)
rep = lambda col: sum(b[col] == "reproduced" for b in bugs)
so_gcc = [b["bug_id"] for b in bugs if "only with GCC" in b["notes"]]
comp = Counter(b["repo"] for b in bugs)

linhas = "\n".join(
    f"| `{b['bug_id']}` | {b['component']} | {b['fix_year']} | {b['tests']} | {b['assertion_type']} | "
    f"{b['core']} | `scripts/reproduce.sh {b['bug_id']}` |" for b in bugs)

texto = f"""# cfs-bugs: reproducible bugs from NASA's core Flight System

Dataset and reproduction package of **{n} real bugs** from NASA's core Flight System (cFS),
each revealed by a unit test that fails before the fix and passes after it. Companion
artifact of *Reproducible Bugs in NASA's core Flight System: A Dataset and Challenges for
Test Oracles* (João Domingues and Nuno Pombo, Universidade da Beira Interior; CASE2Space
2027 @ ICSE, under review).

- {orig} bugs reproduce with the developers' own tests and {n - orig} with tests minimally
  adapted to the pre-fix API (constants and names only).
- Components: {", ".join(f"{k} ({v})" for k, v in comp.most_common())}.
- **Core set** ({core} bugs): revealed by behaviour assertions only, excluding the weak cases
  (column `core`).

## How a bug is replayed

For each bug the scripts build two versions of the affected component: *pre-fix* (the parent
of the earliest fix commit, with the fix's test files overlaid) and *post-fix* (the fix
commit). Each version is built inside the cFS bundle of its time (the bundle commit whose
submodule pointer is the closest ancestor of the pre-fix version), in a Docker image pinned by
digest, and the component's unit tests run with `ctest`. A bug is **reproduced** when at
least one test fails before the fix and all tests pass after it; a build failure never counts.
The generic `-Werror` flag is removed identically on both sides (old code raises new warnings
with today's compilers), and three upstream fixes that only affect the build environment are
applied to both versions (see `NOTICE`).

## Contents

| Path | What |
|---|---|
| `bugs-cfs.csv` | one row per bug (columns below) |
| `docker/Dockerfile` | Ubuntu 24.04 pinned by digest, GCC 13.3.0, Clang 18.1.3, CMake 3.28, lcov 2.0 |
| `cFS/` | the cFS bundle at `v7.0.1` (git submodule; the full history of every component is needed) |
| `scripts/reproduce.sh` | replays one bug (or all) |
| `scripts/bugs-reproduzir.py`, `scripts/triagem-clang.py` | replay logic for original and adapted tests |
| `scripts/gcc-sem-werror`, `scripts/clang-bin/` | compiler wrappers that drop the generic `-Werror` |
| `resultados/triagem/*.patch` | test adaptations for the {n - orig} recovered bugs |
| `resultados/*.csv` | candidate list and reference results (aarch64) |
| `.github/workflows/reproduzir.yml` | replay of all bugs on GitHub-hosted runners |

Script comments and internal column names are in Portuguese; this README and `bugs-cfs.csv`
are in English.

## Requirements

Linux with Docker, git and Python 3 (standard library only); about 2 GB of disk for the image
and 2 GB for the cFS clones. Tested on aarch64 (reference machine) and on x86_64 (GitHub
Actions, `ubuntu-24.04`).

## Quick start

    git clone https://github.com/JoaoDomingues9/cfs-bugs && cd cfs-bugs
    git submodule update --init --recursive        # cFS v7.0.1 with full history
    docker build -t cfs-bugs docker/
    scripts/reproduce.sh cfs-cfe-2436              # one bug, GCC
    scripts/reproduce.sh cfs-cfe-2436 --clang      # same bug, Clang
    scripts/reproduce.sh --all                     # all {n} bugs, GCC

A single bug takes from about 20 seconds to a few minutes (OSAL functional tests run in real
time). All {n} take about 50 minutes per compiler on 12 cores and about 1.5 hours on a 2-core
GitHub runner. Variables: `IMAGEM` (image tag), `JOBS` (parallel build jobs), `MEMORIA`
(container memory limit).

## Reproduction results

| Platform | GCC | Clang |
|---|---|---|
| aarch64 (reference) | {rep('gcc_aarch64')}/{n} | {rep('clang_aarch64')}/{n} |
| x86_64 (GitHub Actions) | {rep('gcc_x86_64')}/{n} | {rep('clang_x86_64')}/{n} |

## One command per bug

| bug_id | Component | Year | Tests | Failing assertion | Core | Command |
|---|---|---|---|---|---|---|
{linhas}

## Columns of `bugs-cfs.csv`

| Column | Meaning |
|---|---|
| `bug_id`, `repo`, `issue`, `issue_url` | identifier and GitHub issue (`nasa/<repo>`) |
| `fix_year`, `component` | year of the fix commit; module of the flight code changed |
| `commit_before`, `commit_after`, `fix_commits` | pre-fix commit, fix commit, all fix commits |
| `tests`, `triage_patch` | `original` or `adapted`, and the adaptation patch |
| `revealing_test` | `ctest` executable that reveals the bug |
| `assertion_type` | `behaviour`, `stub` (call counts on stubs), `crash`, `behaviour+crash`, `mixed` |
| `event_oracle` | whether the revealing oracle inspects event messages |
| `requirement_cited` | requirement named in the issue or fix (or a requirements file edited by the fix) |
| `requirement_link`, `requirement_ids` | manual link to the requirements of release v7.0.1: `cited`, `specifies`, `partial`, `none`, `no_document` |
| `odc_type` | Orthogonal Defect Classification type of the fix |
| `fix_flight_lines`, `fix_flight_files`, `fix_flight_hunks`, `fix_test_lines` | size of the fix (lines added + removed) in flight code and in test files |
| `days_to_close` | days from the opening to the closing of the issue |
| `gcc_aarch64`, `clang_aarch64`, `gcc_x86_64`, `clang_x86_64` | replay outcome per compiler and platform |
| `core`, `judgement` | core set membership; `solid`, `weak` or `events_only` |
| `notes` | caveats |

## Known limitations

- {len(so_gcc)} bugs reproduce reliably only with GCC (undefined behaviour): {", ".join(f"`{b}`" for b in so_gcc)}.
  Under Clang their outcome can vary from run to run.
- 10 OSAL tests that cannot run on aarch64 are excluded on every platform (list in
  `scripts/bugs-reproduzir.py`, `EXCLUIR`).
- Requirement links are judged against release v7.0.1; labels were reviewed by a second rater
  on a sample (see the paper).
- The open-source cFS bundle is not a flight distribution.

## Licenses

Scripts: MIT (`LICENSE`). Dataset and documentation: CC BY 4.0 (`LICENSE-data`). The test
adaptation patches derive from cFS and are under Apache 2.0 (`NOTICE`).

## How to cite

See `CITATION.cff`. A DOI (Zenodo) will be added for the camera-ready version.
"""
(RAIZ / "README.md").write_text(texto)
print(f"README.md: {n} bugs, {core} core")
