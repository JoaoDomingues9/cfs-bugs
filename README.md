# cfs-bugs: reproducible bugs from NASA's core Flight System

Dataset and reproduction package of **40 real bugs** from NASA's core Flight System (cFS),
each revealed by a unit test that fails before the fix and passes after it. Companion
artifact of *Reproducible Bugs in NASA's core Flight System: A Dataset and Challenges for
Test Oracles* (João Domingues and Nuno Pombo, Universidade da Beira Interior; CASE2Space
2027 @ ICSE, under review).

- 32 bugs reproduce with the developers' own tests and 8 with tests minimally
  adapted to the pre-fix API (constants and names only).
- Components: cFE (16), osal (11), CF (10), CS (1), MM (1), SC (1).
- **Core set** (28 bugs): revealed by behaviour assertions only, excluding the weak cases
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
| `resultados/triagem/*.patch` | test adaptations for the 8 recovered bugs |
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
    scripts/reproduce.sh --all                     # all 40 bugs, GCC

A single bug takes from about 20 seconds to a few minutes (OSAL functional tests run in real
time). All 40 take about 50 minutes per compiler on 12 cores and about 1.5 hours on a 2-core
GitHub runner. Variables: `IMAGEM` (image tag), `JOBS` (parallel build jobs), `MEMORIA`
(container memory limit).

## Reproduction results

| Platform | GCC | Clang |
|---|---|---|
| aarch64 (reference) | 40/40 | 37/40 |
| x86_64 (GitHub Actions) | 40/40 | 38/40 |

## One command per bug

| bug_id | Component | Year | Tests | Failing assertion | Core | Command |
|---|---|---|---|---|---|---|
| `cfs-cf-117` | CF | 2022 | adapted | mixed | no | `scripts/reproduce.sh cfs-cf-117` |
| `cfs-cf-118` | CF | 2022 | adapted | behaviour | yes | `scripts/reproduce.sh cfs-cf-118` |
| `cfs-cf-123` | CF | 2022 | adapted | behaviour | yes | `scripts/reproduce.sh cfs-cf-123` |
| `cfs-cf-125` | CF | 2022 | original | behaviour | yes | `scripts/reproduce.sh cfs-cf-125` |
| `cfs-cf-131` | CF | 2022 | original | behaviour | yes | `scripts/reproduce.sh cfs-cf-131` |
| `cfs-cf-172` | CF | 2022 | original | behaviour | yes | `scripts/reproduce.sh cfs-cf-172` |
| `cfs-cf-184` | CF | 2022 | original | behaviour | yes | `scripts/reproduce.sh cfs-cf-184` |
| `cfs-cf-377` | CF | 2023 | original | stub | no | `scripts/reproduce.sh cfs-cf-377` |
| `cfs-cf-392` | CF | 2023 | original | stub | no | `scripts/reproduce.sh cfs-cf-392` |
| `cfs-cf-473` | CF | 2025 | adapted | behaviour | no | `scripts/reproduce.sh cfs-cf-473` |
| `cfs-cfe-101` | SB | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-101` |
| `cfs-cfe-274` | ES | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-274` |
| `cfs-cfe-297` | CCSDS headers | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-297` |
| `cfs-cfe-494` | SB | 2020 | adapted | behaviour | yes | `scripts/reproduce.sh cfs-cfe-494` |
| `cfs-cfe-862` | SB | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-862` |
| `cfs-cfe-915` | ES | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-915` |
| `cfs-cfe-952` | ES | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-952` |
| `cfs-cfe-986` | TBL | 2021 | original | stub | no | `scripts/reproduce.sh cfs-cfe-986` |
| `cfs-cfe-996` | SB | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-996` |
| `cfs-cfe-1004` | ES | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-1004` |
| `cfs-cfe-1071` | ES | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-1071` |
| `cfs-cfe-1505` | ES | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-1505` |
| `cfs-cfe-1672` | ES | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-1672` |
| `cfs-cfe-1952` | SB | 2021 | adapted | behaviour | yes | `scripts/reproduce.sh cfs-cfe-1952` |
| `cfs-cfe-2067` | SB | 2022 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-2067` |
| `cfs-cfe-2436` | SB | 2023 | original | behaviour | yes | `scripts/reproduce.sh cfs-cfe-2436` |
| `cfs-cs-71` | CS | 2023 | adapted | mixed | no | `scripts/reproduce.sh cfs-cs-71` |
| `cfs-mm-22` | MM | 2022 | original | behaviour | no | `scripts/reproduce.sh cfs-mm-22` |
| `cfs-osal-445` | osal | 2020 | original | crash | no | `scripts/reproduce.sh cfs-osal-445` |
| `cfs-osal-453` | osal | 2020 | adapted | behaviour | yes | `scripts/reproduce.sh cfs-osal-453` |
| `cfs-osal-506` | osal | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-osal-506` |
| `cfs-osal-544` | osal | 2020 | original | behaviour+crash | no | `scripts/reproduce.sh cfs-osal-544` |
| `cfs-osal-580` | osal | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-osal-580` |
| `cfs-osal-664` | osal | 2020 | original | behaviour+crash | no | `scripts/reproduce.sh cfs-osal-664` |
| `cfs-osal-708` | osal | 2020 | original | behaviour | yes | `scripts/reproduce.sh cfs-osal-708` |
| `cfs-osal-808` | osal | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-osal-808` |
| `cfs-osal-921` | osal | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-osal-921` |
| `cfs-osal-1087` | osal | 2021 | original | behaviour | yes | `scripts/reproduce.sh cfs-osal-1087` |
| `cfs-osal-1222` | osal | 2022 | original | crash | no | `scripts/reproduce.sh cfs-osal-1222` |
| `cfs-sc-118` | SC | 2023 | original | crash | no | `scripts/reproduce.sh cfs-sc-118` |

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
| `gcc_aarch64`, `clang_aarch64`, `gcc_x86_64`, `clang_x86_64` | replay outcome per compiler and platform |
| `core`, `judgement` | core set membership; `solid`, `weak` or `events_only` |
| `notes` | caveats |

## Known limitations

- 3 bugs reproduce reliably only with GCC (undefined behaviour): `cfs-cf-123`, `cfs-cf-125`, `cfs-cfe-1071`.
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
