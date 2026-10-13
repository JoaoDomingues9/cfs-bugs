#!/usr/bin/env bash
# Reproduz os 40 bugs com um compilador, num clone de trabalho novo: os 32 com os testes
# originais (bugs-reproduzir.py) e os 8 recuperados na triagem, com o patch de cada um
# (triagem-clang.py, que com BUGS_CC/IMAGEM serve também para o GCC). É o procedimento da
# reprodução independente D2 do piloto (2026-10-12), sem os caminhos da ThinkStation.
#   scripts/reproduzir-todos.sh gcc|clang <pasta de saída>
# Variáveis: IMAGEM (obrigatória), JOBS, MEMORIA (ver bugs-reproduzir.py).
set -euo pipefail
cd "$(dirname "$0")/.."
comp=$1
saida=$2
: "${IMAGEM:?defina IMAGEM (imagem construída a partir de docker/Dockerfile)}"
case $comp in
  gcc)   export BUGS_CC=/w/scripts/gcc-sem-werror ;;
  clang) export BUGS_CC=/w/scripts/clang-bin/clang-18-sem-werror ;;
  *) echo "compilador: gcc ou clang" >&2; exit 2 ;;
esac
export BUGS_TRAB=trabalho/ci-$comp
rm -rf "$BUGS_TRAB"
mkdir -p "$saida"

# os 32 reproduzidos com GCC e os testes originais; os 8 da triagem (repo:issue:tentativa)
C32=$(python3 -c "
import csv
print(','.join(f\"{l['repo']}:{l['issue']}\" for l in csv.DictReader(open('resultados/bugs-reproducao.csv')) if l['estado']=='reproduzido'))")
C8="osal:453:2,cFE:1952:1,cFE:494:2,CF:118:1,CF:123:1,CF:473:1,CF:117:1,CS:71:1"
# CASOS=repo:issue,... restringe a corrida a esses bugs (vazio = os 40)
if [ -n "${CASOS:-}" ]; then
  filtro() { python3 -c "
import sys
q = set(sys.argv[2].split(','))
print(','.join(c for c in sys.argv[1].split(',') if ':'.join(c.split(':')[:2]) in q))" "$1" "$CASOS"; }
  C32=$(filtro "$C32"); C8=$(filtro "$C8")
fi

if [ -n "$C32" ]; then
  echo "== $comp: com os testes originais ($(date -Is))"
  python3 scripts/bugs-reproduzir.py resultados/2026-10-04-cfs-bugs-candidatos.csv \
    --casos "$C32" --saida "$saida/$comp-32.csv"
  cp "$(ls -d resultados/brutos/bugs-* | tail -1)/tempos.tsv" "$saida/$comp-32-tempos.tsv"
fi

if [ -n "$C8" ]; then
  echo "== $comp: da triagem ($(date -Is))"
  python3 scripts/triagem-clang.py "$C8" "$saida/$comp-8.csv"
  cp "$(ls -d resultados/brutos/triagem-clang-* | tail -1)/tempos.tsv" "$saida/$comp-8-tempos.tsv"
fi
echo "== $comp: fim ($(date -Is))"
