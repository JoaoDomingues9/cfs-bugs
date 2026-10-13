#!/usr/bin/env python3
"""Casos recuperados na triagem (testes adaptados), corridos com Clang.

Mesmo procedimento da corrida dos 32 com Clang (resultados/bugs-reproducao-clang.csv):
scripts/bugs-reproduzir.py com BUGS_CC=/w/scripts/clang-bin/clang-18-sem-werror e
IMAGEM=piloto-cfs:0.3 (correções de ambiente e as só do Clang aplicadas pelo preparar),
pacote da época com recurso ao anterior/posterior se não compilar. A diferença: o patch da
triagem (resultados/triagem/<repo>-<issue>-tentativa<N>.patch) é aplicado por cima dos testes
da correção nas duas versões; se não compilar no "depois", o "depois" corre com os testes
originais da correção, como no bugs-triagem.py testar.

  scripts/triagem-clang.py osal:453:2,cFE:1952:1,... resultados/triagem/x.csv
  (cada caso: repo:issue:tentativa do patch)
"""
import csv, os, re, subprocess, sys, time
from pathlib import Path

os.environ.setdefault("BUGS_TRAB", "trabalho/triagem-clang")
os.environ.setdefault("BUGS_CC", "/w/scripts/clang-bin/clang-18-sem-werror")
os.environ.setdefault("IMAGEM", "piloto-cfs:0.3")
import importlib.util
REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("br", REPO / "scripts/bugs-reproduzir.py")
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)
br.PACOTE_REF = br.git(REPO / "cFS", "rev-parse", "HEAD")


def aplicar(alvo, patch):
    return subprocess.run(["git", "-C", str(br.BUNDLE / alvo), "apply", str(patch)],
                          capture_output=True).returncode == 0


def correr(pac, alvo, antes, depois, fich, patch, logdir, nome):
    r = {"pacote": pac, "notas": [], "alvo": alvo, "fich_teste": fich}
    na = br.preparar(pac, alvo, antes, (depois, fich))
    if not aplicar(alvo, patch):
        r["notas"].append("patch da triagem NÃO aplicado no antes")
    r["antes"] = br.build_e_testes(alvo, logdir, "antes", nome)
    nd = br.preparar(pac, alvo, depois)
    ok = aplicar(alvo, patch)
    r["depois"] = br.build_e_testes(alvo, logdir, "depois", nome) if ok else {"build_ok": False}
    if not r["depois"]["build_ok"]:
        nd = br.preparar(pac, alvo, depois)
        r["depois"] = br.build_e_testes(alvo, logdir, "depois-original", nome)
        r["notas"].append("depois com os testes originais da correção (o teste adaptado não "
                          "compila na correção)" if ok else "patch não aplicável ao depois")
    else:
        r["notas"].append("depois com o mesmo teste adaptado")
    r["notas"] = [n for n in na if n in nd] + [f"só antes: {n}" for n in na if n not in nd] + \
        [f"só depois: {n}" for n in nd if n not in na] + r["notas"]
    return r


def main():
    casos = [c.split(":") for c in sys.argv[1].split(",")]
    saida = REPO / sys.argv[2]
    cand = {(l["repo"], l["issue"]): l for l in
            csv.DictReader(open(REPO / "resultados/2026-10-04-cfs-bugs-candidatos.csv"))}
    gcc = {(l["repo"], l["issue"]): l for l in csv.DictReader(open(REPO / "resultados/bugs-reproducao.csv"))}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    brutos = REPO / f"resultados/brutos/triagem-clang-{stamp}"
    brutos.mkdir(parents=True)
    if not (br.BUNDLE / ".git").exists():
        br.TRAB.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--no-checkout", str(br.GITDIR_CFS), str(br.BUNDLE)],
                       check=True)
    campos = list(next(iter(cand.values())).keys()) + ["estado", "tipo_assercao", "notas"]
    linhas = []
    # tempos como no bugs-reproduzir.py (faltavam na corrida de 2026-10-10; reconstruídos então
    # dos logs com scripts/tempos-dos-logs.py)
    tempos = open(brutos / "tempos.tsv", "w")
    tempos.write("repo\tissue\ttentativa\tbuild_antes\tctest_antes\tbuild_depois\tctest_depois\ttotal\n")
    for repo, issue, tent in casos:
        t_caso = time.time()
        l = cand[(repo, issue)]
        alvo = br.CAMINHO[repo]
        d_sub = REPO / "cFS" / alvo
        commits = l["commits_todos"].split(";")
        mais_antigo = min(commits, key=lambda c: int(br.git(d_sub, "rev-list", "--count", c)))
        antes = br.git(d_sub, "rev-parse", mais_antigo + "^")
        depois = l["commit_correcao"]
        fich = [f for f in br.git(d_sub, "diff", "--name-only", antes, depois).splitlines()
                if br.eh_teste(f)]
        patch = REPO / f"resultados/triagem/{repo}-{issue}-tentativa{tent}.patch"
        nome = f"piloto-cfs-trclang-{repo.lower()}-{issue}"
        logdir = brutos / f"{repo}-{issue}"
        logdir.mkdir()
        print(f"[{repo} #{issue}] antes={antes[:10]} depois={depois[:10]} patch={patch.name}", flush=True)
        notas = [f"antes={antes[:10]}", f"patch da triagem: {patch.relative_to(REPO)}"]
        # pacote: o do resultado com GCC (última tentativa), depois anterior/posterior da época
        t = re.findall(r"\[(pacote v7\.0\.1|pacote da época(?:, posterior)? ([0-9a-f]{10}))",
                       gcc[(repo, issue)]["notas"])
        p0 = br.PACOTE_REF if t[-1][0] == "pacote v7.0.1" else br.git(br.BUNDLE, "rev-parse", t[-1][1])
        tentativas = [(p0, t[-1][0] + " (o do GCC)")]
        for n, (pac, desc) in enumerate(tentativas):
            ld = logdir / f"t{n}"
            ld.mkdir()
            r = correr(pac, br.caminho_no_pacote(pac, alvo), antes, depois, fich, patch, ld, nome)
            estado, nota, tipo = br.classificar(r)
            tempos.write(f"{repo}\t{issue}\t{desc}\t{r['antes'].get('t_build', '')}\t"
                         f"{r['antes'].get('t_ctest', '')}\t{r['depois'].get('t_build', '')}\t"
                         f"{r['depois'].get('t_ctest', '')}\t\n")
            tempos.flush()
            notas.append(f"[{desc}; {'; '.join(r['notas'])}] {nota}")
            print(f"    {desc}: {estado} {tipo} — {nota[:300]}", flush=True)
            if estado == "erro_build" and n == len(tentativas) - 1:
                ja = {x[0] for x in tentativas}
                for prox in (br.pacote_da_epoca(alvo, antes), br.pacote_da_epoca(alvo, antes, depois)):
                    if prox and prox[0] not in ja:
                        tentativas.append(prox)
                        break
        tempos.write(f"{repo}\t{issue}\ttotal\t\t\t\t\t{time.time() - t_caso:.1f}\n")
        tempos.flush()
        linhas.append({**l, "estado": estado, "tipo_assercao": tipo, "notas": " | ".join(notas)})
        with open(saida, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(linhas)
    print(f"CSV: {saida.relative_to(REPO)}\nlogs: {brutos.relative_to(REPO)}")


if __name__ == "__main__":
    main()
