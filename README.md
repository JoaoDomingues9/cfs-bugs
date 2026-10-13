# Reproducible bugs in NASA's core Flight System (cFS)

Reproduction package for the cFS bug dataset (João Domingues and Nuno Pombo, Universidade da
Beira Interior). **Work in progress:** the dataset CSV, licences and the full documentation
are not final yet.

Each bug is replayed as two versions of its component: *pre-fix* (parent of the earliest fix
commit, with the fix's test files overlaid) and *post-fix* (the fix commit), each built inside
the cFS bundle of its time, in a Docker image pinned by digest. A bug is reproduced when at
least one unit test fails before the fix and all tests pass after it.

## Contents

| Path | What |
|---|---|
| `cFS/` | the cFS bundle at `v7.0.1` (submodule; full history of every component is needed) |
| `docker/Dockerfile` | Ubuntu 24.04, GCC 13.3, Clang 18.1.3 |
| `scripts/bugs-reproduzir.py` | replays bugs with the developers' original tests |
| `scripts/triagem-clang.py` | replays the 8 bugs recovered with minimally adapted tests (`resultados/triagem/*.patch`); works for GCC and Clang |
| `scripts/reproduzir-todos.sh` | replays all 40 bugs with one compiler |
| `scripts/comparar-ci.py` | compares a replay with the reference results |
| `resultados/` | candidate list and reference results (aarch64) |
| `.github/workflows/reproduzir.yml` | the replay on GitHub-hosted runners (x86_64 and aarch64) |

## Quick start

    git clone https://github.com/<owner>/cfs-bugs && cd cfs-bugs
    git submodule update --init --recursive
    docker build -t cfs-bugs docker/
    IMAGEM=cfs-bugs JOBS=8 MEMORIA=16g scripts/reproduzir-todos.sh gcc resultados/ci
    python3 scripts/comparar-ci.py resultados/ci-local   # see the script for the expected layout

Requirements: Linux, Docker, git, Python 3 (standard library only). Replaying all 40 bugs
takes about 50 minutes per compiler on 12 cores.
