#!/usr/bin/env python3
"""Compara as reproduções do GitHub Actions com as da máquina de referência (ThinkStation,
aarch64, 2026-10-06/10) e escreve um resumo em Markdown na saída padrão.

Cada pasta de entrada é um artefacto de um job de .github/workflows/reproduzir.yml
(ci-<runner>-<compilador>), com <comp>-32.csv, <comp>-8.csv, os tempos e versoes.txt
(a primeira linha é o `uname -m` do runner).

Estado de referência (o mesmo da D2 do piloto): GCC — resultados/bugs-reproducao.csv (32) e
"reproduzido" para os 8 recuperados na triagem (resultados/triagem/resultados-triagem.csv);
Clang — resultados/bugs-reproducao-clang.csv e resultados/triagem/resultados-triagem-clang.csv.

  scripts/comparar-ci.py <pasta> [<pasta> ...] [--csv resultados/ci-comparacao.csv]
"""
import argparse, csv
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def ler(p):
    p = Path(p)
    return {(l["repo"], l["issue"]): l for l in csv.DictReader(open(p))} if p.exists() else {}


def totais(p):
    t = {}
    if Path(p).exists():
        for l in open(p).read().splitlines()[1:]:
            c = l.split("\t")
            if len(c) > 7 and c[2] == "total" and c[7]:
                t[(c[0], c[1])] = float(c[7])
    return t


def referencia():
    ref = {"gcc": ler(REPO / "resultados/bugs-reproducao.csv"),
           "clang": ler(REPO / "resultados/bugs-reproducao-clang.csv")}
    for l in csv.DictReader(open(REPO / "resultados/triagem/resultados-triagem.csv")):
        if l["resultado"] == "recuperado":
            ref["gcc"][(l["repo"], l["issue"])] = {"estado": "reproduzido",
                                                    "tipo_assercao": l["tipo_assercao"]}
    ref["clang"].update(ler(REPO / "resultados/triagem/resultados-triagem-clang.csv"))
    return ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pastas", nargs="+")
    ap.add_argument("--csv", default=str(REPO / "resultados/ci-comparacao.csv"))
    args = ap.parse_args()
    ref = referencia()
    linhas, resumo = [], []
    for pasta in map(Path, sorted(args.pastas)):
        comp = "clang" if pasta.name.endswith("-clang") else "gcc"
        versoes = (pasta / "versoes.txt").read_text().splitlines() if (pasta / "versoes.txt").exists() else []
        arq = versoes[0].strip() if versoes else "?"
        novo = {**ler(pasta / f"{comp}-32.csv"), **ler(pasta / f"{comp}-8.csv")}
        seg = {**totais(pasta / f"{comp}-32-tempos.tsv"), **totais(pasta / f"{comp}-8-tempos.tsv")}
        n = iguais = 0
        difs = []
        for k, l in sorted(novo.items()):
            r = ref[comp].get(k, {})
            eo, en = r.get("estado", "?"), l["estado"]
            to, tn = r.get("tipo_assercao", ""), l.get("tipo_assercao", "")
            igual = eo == en
            n += 1
            iguais += igual
            if not igual:
                difs.append(f"{k[0]} #{k[1]}: {eo} → {en}")
            linhas.append({"arquitetura": arq, "runner": pasta.name, "compilador": comp,
                           "repo": k[0], "issue": k[1], "estado_referencia": eo, "estado_ci": en,
                           "igual": "sim" if igual else "nao", "tipo_referencia": to,
                           "tipo_ci": tn, "segundos": seg.get(k, "")})
        tempo = sum(seg.values()) / 60
        resumo.append(f"| {arq} | {comp} | {iguais}/{n} | {tempo:.0f} | "
                      f"{'; '.join(difs) or '—'} |")
    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["arquitetura", "runner", "compilador", "repo", "issue",
                                          "estado_referencia", "estado_ci", "igual",
                                          "tipo_referencia", "tipo_ci", "segundos"])
        w.writeheader()
        w.writerows(linhas)
    print("## Reprodução dos bugs do cFS: comparação com a referência (aarch64, ThinkStation)\n")
    print("| Arquitetura | Compilador | Igual à referência | Tempo (min) | Diferenças |")
    print("|---|---|---|---|---|")
    print("\n".join(resumo))
    difs_tipo = [x for x in linhas if x["igual"] == "sim" and x["estado_ci"] == "reproduzido"
                 and x["tipo_referencia"] and x["tipo_ci"] != x["tipo_referencia"]]
    if difs_tipo:
        print("\nMesmo estado, tipo de asserção diferente:\n")
        for x in difs_tipo:
            print(f"- {x['arquitetura']} {x['compilador']} {x['repo']} #{x['issue']}: "
                  f"{x['tipo_referencia']} → {x['tipo_ci']}")


if __name__ == "__main__":
    main()
