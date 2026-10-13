#!/usr/bin/env bash
# Replay one bug of the dataset (or all of them) in the Docker image.
#   scripts/reproduce.sh <bug_id> [--clang]     e.g. scripts/reproduce.sh cfs-cfe-2436
#   scripts/reproduce.sh --all [--clang]
# Environment: IMAGEM (image tag, default cfs-bugs), JOBS (default: nproc), MEMORIA (default 8g).
# Prints the outcome (reproduced / not_reproduced / ...) and where the CSV and the logs are.
set -euo pipefail
cd "$(dirname "$0")/.."
export IMAGEM=${IMAGEM:-cfs-bugs}
export JOBS=${JOBS:-$(nproc)}
export MEMORIA=${MEMORIA:-8g}

alvo=${1:?usage: scripts/reproduce.sh <bug_id>|--all [--clang]}
comp=gcc
[ "${2:-}" = "--clang" ] && comp=clang
case $comp in
  gcc)   export BUGS_CC=/w/scripts/gcc-sem-werror ;;
  clang) export BUGS_CC=/w/scripts/clang-bin/clang-18-sem-werror ;;
esac

if [ "$alvo" = "--all" ]; then
  exec scripts/reproduzir-todos.sh "$comp" "resultados/local-$comp"
fi

read -r repo issue tests patch < <(python3 -c "
import csv, sys
for r in csv.DictReader(open('bugs-cfs.csv')):
    if r['bug_id'] == sys.argv[1]:
        print(r['repo'], r['issue'], r['tests'], r['triage_patch'] or '-')
        break
else:
    sys.exit('unknown bug_id: ' + sys.argv[1])" "$alvo")

export BUGS_TRAB=trabalho/$alvo-$comp
mkdir -p resultados/local
saida=resultados/local/$alvo-$comp.csv
if [ "$tests" = "adapted" ]; then
  tent=$(echo "$patch" | sed -E 's/.*tentativa([0-9]+)\.patch/\1/')
  python3 scripts/triagem-clang.py "$repo:$issue:$tent" "$saida"
else
  python3 scripts/bugs-reproduzir.py resultados/2026-10-04-cfs-bugs-candidatos.csv \
    --casos "$repo:$issue" --saida "$saida"
fi
python3 -c "
import csv, sys
r = next(csv.DictReader(open(sys.argv[1])))
print(f\"{sys.argv[2]} ({sys.argv[3]}): {r['estado']} {r.get('tipo_assercao', '')}\")" "$saida" "$alvo" "$comp"
echo "CSV: $saida (column 'notas' has the failing assertions); logs: resultados/brutos/"
