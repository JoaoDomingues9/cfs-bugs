#!/usr/bin/env python3
"""Reprodução dos bugs candidatos do cFS (issues com a etiqueta bug + commit "Fix #N").

Para cada candidato com tem_teste = sim:
  - "antes"  = pai do commit mais antigo de commits_todos, com os ficheiros de teste da
               versão "depois" por cima (só os que a correção mudou);
  - "depois" = commit_correcao.
Compila cada versão (build oficial do cFS, GCC, na imagem do piloto) e corre o ctest desse
submódulo. Classifica:
  - reproduzido           : há pelo menos um teste do submódulo que falha antes e passa depois;
  - nao_reproduzido       : os testes unitários existem e correm, mas nenhum distingue as versões;
  - so_teste_funcional    : a correção só trouxe testes funcionais (cfe_testcase/cfe_assert),
                            que não fazem parte do ctest; não se compila nada;
  - erro_build_teste_novo : "depois" compila e "antes" não. Como as duas versões só diferem no
                            código não-teste do submódulo, o erro vem de os testes novos usarem
                            algo criado (ou mudado) pela própria correção. Também quando o
                            "antes" só compila por se ter retirado o -Werror: há avisos em
                            ficheiros de teste que só aparecem no "antes" (por exemplo
                            int-conversion: o teste chama uma função com a assinatura nova);
  - erro_build            : outra falha de compilação (não conta como reprodução).
Coluna tipo_assercao (só nos reproduzidos): o que falha no "antes" nos testes que revelam:
  stub (contagens de chamadas a stubs), comportamento (retorno, estado, saída), misto (ambos)
  ou crash (o teste rebenta sem asserção a falhar).

Compilador: GCC 13 da imagem através de scripts/gcc-sem-werror, que retira o -Werror
genérico (avisos novos do GCC 13 em código antigo); igual em "antes" e "depois".
Correções de ambiente: defeitos conhecidos dos próprios testes que rebentam nesta plataforma
são corrigidos com o commit upstream, nas duas versões (ver CORRECOES_AMBIENTE).

Versões do pacote: nos candidatos de 2026 tenta primeiro com o nasa/cFS fixado no submódulo
cFS/ (v7.0.1), só com o submódulo do candidato recuado; se alguma build falhar (e, nos mais
antigos, logo à partida), usa com o commit do nasa/cFS da
época: primeiro o mais recente cujo ponteiro para o submódulo é antepassado de "antes" (os
outros submódulos ficam um pouco mais antigos); se falhar, o mais antigo cujo ponteiro já
contém "depois" (os outros ficam um pouco mais recentes). Se o submódulo ainda não estava no
pacote, usa o último commit anterior à data de "antes", com a app acrescentada à mão.

Nada disto toca no submódulo cFS/ do piloto: trabalha-se num clone em trabalho/bugs/cFS
(outro diretório com BUGS_TRAB=trabalho/<nome>, para correr duas coisas ao mesmo tempo).
Uso:
  scripts/bugs-reproduzir.py CSV [--casos cFE:2516,CF:392] [--saida resultados/x.csv]
"""
import argparse, csv, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IMAGEM = os.environ.get("IMAGEM", "piloto-cfs:0.2")
JOBS = os.environ.get("JOBS", "12")
# Limite de memória do contentor (32g na ThinkStation; menos nos runners do GitHub Actions).
MEMORIA = os.environ.get("MEMORIA", "32g")
GITDIR_CFS = REPO / ".git/modules/cFS"
TRAB = REPO / os.environ.get("BUGS_TRAB", "trabalho/bugs")
BUNDLE = TRAB / "cFS"
BUNDLE_C = "/w/" + str(BUNDLE.relative_to(REPO))   # o mesmo caminho dentro do contentor

# repo do CSV -> caminho do submódulo no pacote nasa/cFS
CAMINHO = {"cFE": "cfe", "osal": "osal", "PSP": "psp", "CF": "apps/cf", "CS": "apps/cs",
           "DS": "apps/ds", "FM": "apps/fm", "HK": "apps/hk", "HS": "apps/hs",
           "LC": "apps/lc", "MD": "apps/md", "MM": "apps/mm", "SC": "apps/sc",
           "sample_app": "apps/sample_app", "sample_lib": "libs/sample_lib"}
URL = {"cfe": "cFE", "osal": "osal", "psp": "PSP"}

# Ficheiros de teste: qualquer caminho com um destes segmentos.
SEG_TESTE = {"unit-test", "unit-tests", "ut-coverage", "unit-test-coverage", "ut-stubs",
             "ut_assert", "tests", "test", "cfe_testcase", "cfe_assert", "stubs"}

# Testes do OSAL que não correm em aarch64 (ver NOTAS.md, 2026-10-02).
EXCLUIR = ["bin-sem-timeout-test", "condvar-test", "count-sem-timeout-test", "mutex-test",
           "rwlock-test", "timer-test", "osal-core-test", "queue-test", "osal_core_UT",
           "network-api-test"]
TIMEOUT_TESTE = 120
SEG_FUNCIONAL = {"cfe_testcase", "cfe_assert"}   # testes funcionais: fora do ctest
# Compilador (wrapper sem -Werror). BUGS_CC=/w/scripts/clang-bin/clang-18-sem-werror para Clang
# (com IMAGEM=piloto-cfs:0.3).
CC_WRAPPER = os.environ.get("BUGS_CC", "/w/scripts/gcc-sem-werror")

# (submódulo, commit que introduziu, commit upstream que corrigiu, descrição)
CORRECOES_AMBIENTE = [
    ("cfe", "b40a340f", "9fd5a13c",
     "cFE #2553: es_UT.c passava NULL como formato ao vsnprintf (SEGFAULT do coverage-es-ALL "
     "com esta glibc)"),
]

# Só nas builds Clang: correções upstream (por commit, como CORRECOES_AMBIENTE) de ferramentas
# de build que não funcionavam com objetos do Clang.
CORRECOES_AMBIENTE_CLANG = [
    ("tools/elf2cfetbl", "e511e193dc", "d6b7568",   # aplica-se desde a raiz (testado 2019-10 a 2020-06)
     "elf2cfetbl #48: identificação da tabela de strings (o LLVM junta .strtab e .shstrtab; "
     "sem isto não encontra o CFE_TBL_FileDef e as tabelas não são geradas)"),
]

# Só nas builds Clang: correções upstream do sistema de build que o cFE antigo não tem.
# (submódulo, ficheiro, texto antigo, texto novo, commit upstream, descrição)
CORRECOES_CLANG = [
    ("cfe", "cmake/target/CMakeLists.txt",
     'if ("${CMAKE_C_COMPILER_ID}" STREQUAL "GNU")',
     'if (("${CMAKE_C_COMPILER_ID}" STREQUAL "GNU") OR ("${CMAKE_C_COMPILER_ID}" STREQUAL "Clang"))',
     "76446971", "cFE #2120: --whole-archive também com Clang (sem isto o core-cpu1 não liga)"),
]

RE_ERRO = re.compile(rf"^({re.escape(BUNDLE_C)}/\S+?):\d+(?::\d+)?: (?:fatal )?error: (.*)$")
RE_FALHA = re.compile(r"\[ ?(FAIL|TSF|TTF|ABORT)\] (.*)")
RE_STUB = re.compile(r"CallCount|UT_GetStubCount|STUB_COUNT|StubCount")


def git(d, *a, check=True):
    r = subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)} em {d}: {r.stderr.strip()}")
    return r.stdout.strip()


def eh_teste(caminho):
    return bool(SEG_TESTE & set(caminho.split("/")[:-1]))


def no_contentor(p):
    return "/w/" + str(Path(p).relative_to(REPO))


def ancestral(d, a, b):
    return subprocess.run(["git", "-C", str(d), "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def docker(cmd, log, nome, env=()):
    """Corre cmd (bash) na imagem, em BUNDLE_C. Devolve (rc, segundos)."""
    t0 = time.time()
    with open(log, "w") as f:
        rc = subprocess.run(
            ["docker", "run", "--rm", "--name", nome, "--user", f"{os.getuid()}:{os.getgid()}",
             "--cpus", JOBS, "--memory", MEMORIA, "--network", "none",
             *[x for e in env for x in ("-e", e)],
             "-v", f"{REPO}:/w", "-w", BUNDLE_C, IMAGEM, "bash", "-c", cmd],
            stdout=f, stderr=subprocess.STDOUT).returncode
    return rc, round(time.time() - t0, 1)


# ---------- clone de trabalho ----------

def url_origem(caminho):
    nome = URL.get(caminho, caminho.split("/")[-1].upper())
    return f"https://github.com/nasa/{nome}.git"


def garantir_sub(caminho, sha, url=None):
    """Garante um clone em BUNDLE/caminho no commit sha (do repo local do piloto ou da rede)."""
    d = BUNDLE / caminho
    if not (d / ".git").exists():
        if d.exists():
            shutil.rmtree(d)
        local = GITDIR_CFS / "modules" / caminho
        origem = str(local) if local.exists() else (url or url_origem(caminho))
        subprocess.run(["git", "clone", "-q", "--no-checkout", origem, str(d)], check=True)
    if subprocess.run(["git", "-C", str(d), "cat-file", "-e", sha + "^{commit}"],
                      capture_output=True).returncode:
        git(d, "fetch", "-q", url or url_origem(caminho), sha)
    git(d, "checkout", "-q", "-f", "--detach", sha)
    git(d, "clean", "-q", "-ffdx")


def gitlinks(commit):
    """{caminho: sha} dos submódulos do pacote nesse commit, e urls do .gitmodules."""
    out = git(BUNDLE, "ls-tree", "-r", commit)
    links = {l.split("\t")[1]: l.split()[2] for l in out.splitlines() if l.split()[1] == "commit"}
    urls = {}
    gm = git(BUNDLE, "show", f"{commit}:.gitmodules", check=False)
    cur = None
    for l in gm.splitlines():
        l = l.strip()
        if l.startswith("path"):
            cur = l.split("=", 1)[1].strip()
        elif l.startswith("url") and cur:
            urls[cur] = l.split("=", 1)[1].strip()
    return links, urls


def preparar(pacote, alvo, sha_alvo, sobrepor=None):
    """Pacote no commit `pacote`, todos os submódulos no ponteiro dele, e o submódulo `alvo`
    em sha_alvo. sobrepor = (sha, [ficheiros]) a copiar dessa versão do alvo por cima.
    Devolve notas sobre adaptações feitas."""
    notas = []
    if not (BUNDLE / ".git").exists():
        TRAB.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--no-checkout", str(GITDIR_CFS), str(BUNDLE)],
                       check=True)
    git(BUNDLE, "checkout", "-q", "-f", "--detach", pacote)
    # Limpa tudo o que não é do pacote (builds, Makefile/sample_defs copiados), mas mantém
    # os clones dos submódulos para não os refazer.
    links, urls = gitlinks(pacote)
    todos = set(links) | set(CAMINHO.values())
    git(BUNDLE, "clean", "-q", "-ffdx", *[f"--exclude=/{p}" for p in todos])
    for p in list(BUNDLE.glob("apps/*")) + list(BUNDLE.glob("libs/*")):
        rel = str(p.relative_to(BUNDLE))
        if rel not in links and rel != alvo and p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)   # app que não pertence a este commit do pacote
    for p, sha in links.items():
        if p == alvo:
            continue
        garantir_sub(p, sha, urls.get(p))
    garantir_sub(alvo, sha_alvo, urls.get(alvo))
    if sobrepor:
        sha_dep, fich = sobrepor
        d = BUNDLE / alvo
        for f in fich:
            existe = subprocess.run(["git", "-C", str(d), "cat-file", "-e", f"{sha_dep}:{f}"],
                                    capture_output=True).returncode == 0
            if existe:
                (d / f).parent.mkdir(parents=True, exist_ok=True)
                (d / f).write_bytes(subprocess.run(["git", "-C", str(d), "show", f"{sha_dep}:{f}"],
                                                   capture_output=True, check=True).stdout)
            elif (d / f).exists():
                (d / f).unlink()
    for p, intro, fix, desc in CORRECOES_AMBIENTE + (CORRECOES_AMBIENTE_CLANG
                                                     if "clang" in CC_WRAPPER else []):
        d = BUNDLE / p
        if not (d / ".git").exists() or not ancestral(d, intro, "HEAD") or \
                ancestral(d, fix, "HEAD"):
            continue
        patch = subprocess.run(["git", "-C", str(REPO / "cFS" / p), "show", fix],
                               capture_output=True, check=True).stdout
        ok = lambda *a: subprocess.run(["git", "-C", str(d), "apply", *a], input=patch,
                                       capture_output=True).returncode == 0
        if ok("--check"):
            ok()
            notas.append(f"correção de ambiente {fix} ({desc.split(':')[0]})")
        elif not ok("-R", "--check"):   # se -R aplica, os testes de "depois" já a trazem
            notas.append(f"correção de ambiente {fix} NÃO aplicada (conflito)")
    if "clang" in CC_WRAPPER:
        for sub, fich, antigo, novo, fix, desc in CORRECOES_CLANG:
            f = BUNDLE / sub / fich
            if f.exists() and antigo in f.read_text():
                f.write_text(f.read_text().replace(antigo, novo))
                notas.append(f"correção Clang {fix} ({desc.split(':')[0]})")
    # Pacotes antigos (antes de ~2023) não traziam Makefile nem sample_defs na raiz:
    # copiavam-se do cFE, como dizia o README da época.
    if not (BUNDLE / "Makefile").exists():
        shutil.copy(BUNDLE / "cfe/cmake/Makefile.sample", BUNDLE / "Makefile")
        notas.append("Makefile.sample do cFE")
    if not (BUNDLE / "sample_defs").exists():
        shutil.copytree(BUNDLE / "cfe/cmake/sample_defs", BUNDLE / "sample_defs")
        notas.append("sample_defs do cFE")
    # App que não estava no pacote nesta época: acrescentar à lista de apps da missão.
    if alvo not in links and alvo.startswith(("apps/", "libs/")):
        nome = alvo.split("/")[-1]
        tc = BUNDLE / "sample_defs/targets.cmake"
        txt = tc.read_text()
        if not re.search(rf"APPLIST[^)]*\b{nome}\b", txt):
            tc.write_text(txt + f"\nlist(APPEND MISSION_GLOBAL_APPLIST {nome})\n")
            notas.append(f"{nome} acrescentada ao MISSION_GLOBAL_APPLIST")
    return notas


# ---------- build e ctest ----------

def comandos_build():
    if (BUNDLE / "target-configs.mk").exists():
        return (f"make native_std.prep && make -j{JOBS} native_std.install", "build-native_std")
    return ("make SIMULATION=native ENABLE_UNIT_TESTS=true prep && "
            f"make -j{JOBS} && make install", "build")


def avisos(log):
    """{(ficheiro, aviso): n} dos avisos do gcc registados pelo wrapper (compilações que tinham
    -Werror). O ficheiro é relativo ao pacote."""
    c = {}
    if log.exists():
        # Só linhas completas de um ficheiro .c/.h: com -j as mensagens de compilações
        # paralelas podem misturar-se no log e produzir caminhos cortados (falsos "só no antes").
        for m in re.finditer(r"^(/w/[^\s:]+\.[ch]):\d+:\d+: warning: [^\n]*\[-W([\w=+-]+)\]$",
                             log.read_text(errors="replace"), re.M):
            k = (m.group(1).removeprefix(BUNDLE_C + "/"), m.group(2))
            c[k] = c.get(k, 0) + 1
    return c


def por_tipo(av):
    t = {}
    for (_, k), n in av.items():
        t[k] = t.get(k, 0) + n
    return t


def erros_build(log):
    """Lista de (ficheiro relativo ao pacote, mensagem) dos erros de compilação e de ligação."""
    erros, ant = [], ""
    linhas = log.read_text(errors="replace").splitlines()
    for i, l in enumerate(linhas):
        if l.startswith("CMake Error at "):
            msg = linhas[i + 1].strip() if i + 1 < len(linhas) else ""
            erros.append((l[15:].split(":")[0].removeprefix(BUNDLE_C + "/"),
                          f"CMake: {msg}"))
            continue
        m = RE_ERRO.match(l)
        if m:
            erros.append((m.group(1).removeprefix(BUNDLE_C + "/"), m.group(2)))
        elif "undefined reference to" in l:
            # "<fonte>:<linha>:(.text...): undefined reference" ou, sem debug info, a linha
            # anterior do ld ("/usr/bin/ld: <objeto>: in function ...")
            onde = l.split(":")[0]
            if not onde.startswith("/w/"):
                onde = ant.split(":")[1].strip() if ant.count(":") > 1 else ant
            erros.append((onde.removeprefix(BUNDLE_C + "/"),
                          "undefined reference" + l.split("undefined reference")[1]))
        if l.startswith("/usr/bin/ld:") and "undefined reference" not in l:
            ant = l
    return erros


def build_e_testes(alvo, logdir, rot, nome):
    """Compila e corre o ctest do submódulo alvo. Devolve dict com rc, tempos e resultados."""
    cmd, O = comandos_build()
    res = {}
    wlog = logdir / f"{rot}-werror.log"
    rc, res["t_build"] = docker(cmd, logdir / f"{rot}-build.log", f"{nome}-{rot}-build",
                                env=(f"CC={CC_WRAPPER}", f"WERROR_LOG={no_contentor(wlog)}"))
    res["build_ok"] = rc == 0
    res["avisos"] = avisos(wlog)
    if rc:
        res["erros"] = erros_build(logdir / f"{rot}-build.log")
        return res
    # Raiz da build da arquitetura = a pasta com o CMakeCache.txt: build/native/ nos pacotes
    # de 2019-20, build*/native/<plataforma>/ depois. (Não basta o primeiro CTestTestfile:
    # nos pacotes antigos isso apanhava uma subpasta e só corria os testes dela.)
    raiz = [c.parent / "CTestTestfile.cmake" for c in
            sorted((BUNDLE / O / "native").glob("CMakeCache.txt")) +
            sorted((BUNDLE / O / "native").glob("*/CMakeCache.txt"))
            if (c.parent / "CTestTestfile.cmake").exists()]
    if not raiz:
        res["build_ok"] = False
        res["erro"] = "sem CTestTestfile"
        return res
    dir_ct = "/w/" + str(raiz[0].parent.relative_to(REPO))
    # Testes do submódulo: aqueles cujo primeiro CMakeLists.txt na pilha do add_test está
    # dentro dele (o add_test em si costuma estar numa função do cfe/cmake).
    rc, _ = docker(f"cd {dir_ct} && ctest --show-only=json-v1 > ctest-lista.json",
                   logdir / f"{rot}-lista.log", f"{nome}-{rot}-lista")
    info = json.loads((raiz[0].parent / "ctest-lista.json").read_text())
    fich = info["backtraceGraph"]["files"]
    prefixo = f"{BUNDLE_C}/{alvo}/"
    testes = []
    for t in info["tests"]:
        nos = info["backtraceGraph"]["nodes"]
        n, origem = t.get("backtrace"), ""
        while n is not None:
            if fich[nos[n]["file"]].endswith("CMakeLists.txt"):
                origem = fich[nos[n]["file"]]
                break
            n = nos[n].get("parent")
        if origem.startswith(prefixo) and t["name"] not in EXCLUIR:
            testes.append(t["name"])
    res["testes"] = testes
    if not testes:
        res["resultados"] = {}
        res["t_ctest"] = 0
        return res
    regex = "^(" + "|".join(re.escape(t) for t in testes) + ")$"
    rc, res["t_ctest"] = docker(
        f"cd {dir_ct} && ctest --timeout {TIMEOUT_TESTE} --output-junit ctest-junit.xml "
        f"-R '{regex}'", logdir / f"{rot}-ctest.log", f"{nome}-{rot}-ctest")
    import xml.etree.ElementTree as ET
    junit = raiz[0].parent / "ctest-junit.xml"
    resultados, saidas = {}, {}
    if junit.exists():
        for tc in ET.parse(junit).getroot().iter("testcase"):
            f = tc.find("failure")
            resultados[tc.get("name")] = tc.get("status") == "run" and \
                f is None and tc.find("error") is None
            out = tc.findtext("system-out") or ""
            saidas[tc.get("name")] = (out, f.get("message", "") if f is not None else "")
    res["resultados"] = resultados
    res["saidas"] = saidas
    shutil.copy(junit, logdir / f"{rot}-junit.xml") if junit.exists() else None
    return res


# ---------- escolha do commit do pacote ----------

def caminho_no_pacote(pacote, alvo):
    """Caminho do submódulo nesse commit do pacote, procurado pelo nome do repositório no
    .gitmodules (o sample_lib estava em apps/ em 2020 e passou para libs/). Se o submódulo
    não estava no pacote, fica o caminho atual."""
    links, urls = gitlinks(pacote)
    nome = alvo.split("/")[-1].lower()
    for p, u in urls.items():
        if p in links and u.rstrip("/").removesuffix(".git").split("/")[-1].lower() == \
                (URL.get(alvo, nome)).lower():
            return p
    return alvo


def pacote_da_epoca(alvo, sha_antes, posterior=None):
    """Sem posterior: o commit mais recente do pacote cujo ponteiro é antepassado de antes.
    posterior=<sha depois>: o mais antigo cujo ponteiro já contém depois. None se não houver."""
    d = REPO / "cFS" / alvo   # histórico completo do submódulo (o clone de trabalho pode não existir)
    if not (BUNDLE / ".git").exists():
        TRAB.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--no-checkout", str(GITDIR_CFS), str(BUNDLE)],
                       check=True)
    ordem = ["--reverse"] if posterior else []
    for c in git(BUNDLE, "rev-list", "--first-parent", *ordem, PACOTE_REF).split():
        ls = git(BUNDLE, "ls-tree", c, alvo, check=False)
        if not ls:
            continue
        ptr = ls.split()[2]
        if posterior and ancestral(d, posterior, ptr):
            return c, f"pacote da época, posterior {c[:10]} (ponteiro {alvo} {ptr[:10]})"
        if not posterior and ancestral(d, ptr, sha_antes):
            return c, f"pacote da época {c[:10]} (ponteiro {alvo} {ptr[:10]})"
    if posterior:
        return None
    data = git(d, "show", "-s", "--format=%cI", sha_antes)
    c = git(BUNDLE, "rev-list", "-1", "--first-parent", f"--before={data}", PACOTE_REF)
    return c, f"pacote da época {c[:10]} (por data; {alvo} ainda não estava no pacote)"


def correr_versoes(caso, pacote, alvo, antes, depois, fich_teste, logdir, nome):
    r = {"pacote": pacote, "notas": [], "alvo": alvo, "fich_teste": fich_teste}
    na = preparar(pacote, alvo, antes, (depois, fich_teste))
    r["antes"] = build_e_testes(alvo, logdir, "antes", nome)
    nd = preparar(pacote, alvo, depois)
    r["depois"] = build_e_testes(alvo, logdir, "depois", nome)
    r["notas"] = [n for n in na if n in nd] + [f"só antes: {n}" for n in na if n not in nd] + \
                 [f"só depois: {n}" for n in nd if n not in na]
    return r


def tipo_assercao(saida, mensagem):
    """Classifica as asserções que falham na saída de um teste UT-Assert."""
    falhas = [m.group(2).strip() for m in RE_FALHA.finditer(saida)]
    if not falhas:
        return "crash", [mensagem or "sem asserção a falhar"]
    tipos = {"stub" if RE_STUB.search(f) else "comportamento" for f in falhas}
    return ("misto" if len(tipos) > 1 else tipos.pop()), falhas


def resumo_erros(erros, n=2):
    return "; ".join(f"{f}: {m}" for f, m in erros[:n]) or "sem linha de erro reconhecida"


def classificar(r):
    """Devolve (estado, nota, tipo_assercao)."""
    a, d = r["antes"], r["depois"]
    if not a["build_ok"] or not d["build_ok"]:
        q = [v for v, x in (("antes", a), ("depois", d)) if not x["build_ok"]]
        if d["build_ok"]:
            return ("erro_build_teste_novo",
                    f"antes não compila nos testes: {resumo_erros(a['erros'])}", "")
        det = "; ".join(f"{v}: {resumo_erros(x.get('erros', []))}"
                        for v, x in (("antes", a), ("depois", d)) if not x["build_ok"])
        return "erro_build", f"não compila ({', '.join(q)}) — {det}", ""
    so_antes = {k: n for k, n in a["avisos"].items() if k not in d["avisos"]}
    # Só os ficheiros de teste que a correção trouxe (sobrepostos no "antes"): avisos noutros
    # ficheiros não têm a ver com a correção, e com -j um aviso pode perder-se num dos logs.
    trazidos = {f"{r['alvo']}/{f}" for f in r.get("fich_teste", [])}
    em_testes = {k: n for k, n in so_antes.items() if k[0] in trazidos}
    if em_testes:
        det = "; ".join(f"{f} [-W{w}]×{n}" for (f, w), n in sorted(em_testes.items())[:3])
        return ("erro_build_teste_novo",
                f"com -Werror o antes não compilaria: avisos nos testes só no antes: {det}", "")
    ra, rd = a["resultados"], d["resultados"]
    if so_antes:
        r["notas"].append("avisos no código só no antes: " + "; ".join(
            f"{f} [-W{w}]×{n}" for (f, w), n in sorted(so_antes.items())[:3]))
    reveladores = sorted(t for t in ra if not ra[t] and rd.get(t))
    falham_dep = sorted(t for t in rd if not rd[t])
    extra = f"; falham também depois: {' '.join(falham_dep)}" if falham_dep else ""
    if reveladores:
        tipos, detalhe = set(), []
        for t in reveladores:
            tp, falhas = tipo_assercao(*a["saidas"].get(t, ("", "")))
            tipos.add(tp)
            detalhe.append(f"{t} [{tp}]: " + " || ".join(falhas[:3]) +
                           (f" (+{len(falhas) - 3})" if len(falhas) > 3 else ""))
        tipo = tipos.pop() if len(tipos) == 1 else ("misto" if tipos <= {"stub", "comportamento",
                                                                        "misto"} else "+".join(sorted(tipos)))
        return "reproduzido", f"testes que revelam: {' / '.join(detalhe)}{extra}", tipo
    if not ra:
        return "nao_reproduzido", "o ctest não tem testes deste submódulo" + extra, ""
    falham_ant = sorted(t for t in ra if not ra[t])
    return "nao_reproduzido", (f"{len(ra)} testes do submódulo; falham antes: "
                               f"{' '.join(falham_ant) or 'nenhum'}{extra}"), ""


def main():
    global PACOTE_REF
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--casos", help="lista repo:issue separada por vírgulas")
    ap.add_argument("--saida", default=None)
    ap.add_argument("--substituir-em", default=None,
                    help="no fim, substitui as linhas destes casos neste CSV (mesma ordem)")
    ap.add_argument("--retomar", action="store_true",
                    help="acrescenta à --saida existente, saltando os casos que já lá estão")
    args = ap.parse_args()

    linhas = [l for l in csv.DictReader(open(args.csv)) if l["tem_teste"] == "sim"]
    if args.casos:
        q = [tuple(c.split(":")) for c in args.casos.split(",")]
        linhas = [l for c in q for l in linhas if (l["repo"], l["issue"]) == c]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    brutos = REPO / f"resultados/brutos/bugs-{stamp}"
    brutos.mkdir(parents=True)
    saida = Path(args.saida or REPO / f"resultados/bugs-reproducao-{stamp}.csv")
    campos = list(linhas[0].keys()) + ["estado", "tipo_assercao", "notas"]
    tempos = open(brutos / "tempos.tsv", "w")
    tempos.write("repo\tissue\ttentativa\tbuild_antes\tctest_antes\tbuild_depois\tctest_depois\ttotal\n")
    PACOTE_REF = git(REPO / "cFS", "rev-parse", "HEAD")   # v7.0.1 fixado no piloto
    todos_avisos = {}   # aviso -> casos em que deixou de bloquear

    feitos = set()
    if args.retomar and saida.exists():
        feitos = {(x["repo"], x["issue"]) for x in csv.DictReader(open(saida))}
        print(f"a retomar: {len(feitos)} casos já feitos em {saida}", flush=True)
    with open(saida, "a" if feitos else "w", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=campos)
        if not feitos:
            w.writeheader()
        for i, l in enumerate(linhas, 1):
            if (l["repo"], l["issue"]) in feitos:
                continue
            t0 = time.time()
            alvo = CAMINHO[l["repo"]]
            commits = l["commits_todos"].split(";")
            d_sub = REPO / "cFS" / alvo
            # o mais antigo: o que tem menos antepassados
            mais_antigo = min(commits, key=lambda c: int(git(d_sub, "rev-list", "--count", c)))
            antes = git(d_sub, "rev-parse", mais_antigo + "^")
            depois = l["commit_correcao"]
            mudados = git(d_sub, "diff", "--name-only", antes, depois).splitlines()
            fich_teste = [f for f in mudados if eh_teste(f)]
            nome = f"piloto-cfs-bugs-{l['repo'].lower()}-{l['issue']}"
            logdir = brutos / f"{l['repo']}-{l['issue']}"
            logdir.mkdir()
            print(f"[{i}/{len(linhas)}] {l['repo']} #{l['issue']} antes={antes[:10]} "
                  f"depois={depois[:10]} ({len(fich_teste)} ficheiros de teste)", flush=True)
            notas = [f"antes={antes[:10]}", f"testes sobrepostos: {' '.join(fich_teste) or 'nenhum'}"]
            unitarios = [f for f in fich_teste if not SEG_FUNCIONAL & set(f.split("/"))]
            if fich_teste and not unitarios:
                estado = "so_teste_funcional"
                notas.append("a correção só traz testes funcionais (fora do ctest); não se compilou")
                w.writerow({**l, "estado": estado, "tipo_assercao": "", "notas": " | ".join(notas)})
                fo.flush()
                print(f"    => {estado}", flush=True)
                continue
            if not fich_teste:
                notas.append("AVISO: nenhum ficheiro de teste reconhecido no diff")
            if l["data"] >= "2026":
                tentativas = [(PACOTE_REF, "pacote v7.0.1")]
            else:
                tentativas = [pacote_da_epoca(alvo, antes)]
            r = None
            for n, (pac, desc) in enumerate(tentativas):
                ld = logdir / f"t{n}"
                ld.mkdir()
                alvo_p = caminho_no_pacote(pac, alvo)
                r = correr_versoes(l, pac, alvo_p, antes, depois, fich_teste, ld, nome)
                if alvo_p != alvo:
                    r["notas"].append(f"submódulo em {alvo_p} neste pacote")
                estado, nota, tipo = classificar(r)
                for v in ("antes", "depois"):
                    av = por_tipo(r[v].get("avisos", {}))
                    for k in av:
                        todos_avisos.setdefault(k, set()).add(f"{l['repo']}#{l['issue']}")
                    if av:
                        nota += f"; avisos sem -Werror ({v}): " + ", ".join(
                            f"{k}×{c}" for k, c in sorted(av.items()))
                tempos.write(f"{l['repo']}\t{l['issue']}\t{desc}\t{r['antes'].get('t_build','')}\t"
                             f"{r['antes'].get('t_ctest','')}\t{r['depois'].get('t_build','')}\t"
                             f"{r['depois'].get('t_ctest','')}\t\n")
                tempos.flush()
                notas.append(f"[{desc}{'; ' + '; '.join(r['notas']) if r['notas'] else ''}] {nota}")
                print(f"    {desc}: {estado} — {nota}", flush=True)
                if estado == "erro_build" and n == len(tentativas) - 1:
                    ja = {t[0] for t in tentativas}
                    for prox in (pacote_da_epoca(alvo, antes), pacote_da_epoca(alvo, antes, depois)):
                        if prox and prox[0] not in ja:
                            tentativas.append(prox)
                            break
            total = round(time.time() - t0, 1)
            tempos.write(f"{l['repo']}\t{l['issue']}\ttotal\t\t\t\t\t{total}\n")
            w.writerow({**l, "estado": estado, "tipo_assercao": tipo, "notas": " | ".join(notas)})
            fo.flush()
            print(f"    => {estado} ({total} s)", flush=True)
    if args.substituir_em:
        novos = {(x["repo"], x["issue"]): x for x in csv.DictReader(open(saida))}
        antigos = list(csv.DictReader(open(args.substituir_em)))
        with open(args.substituir_em, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for x in antigos:
                w.writerow(novos.get((x["repo"], x["issue"]), x))
        print(f"substituídas {len(novos)} linhas em {args.substituir_em}")
    with open(brutos / "avisos-sem-werror.tsv", "w") as fa:
        fa.write("aviso\tn_casos\tcasos\n")
        for k, cs in sorted(todos_avisos.items(), key=lambda x: -len(x[1])):
            fa.write(f"{k}\t{len(cs)}\t{' '.join(sorted(cs))}\n")
    print(f"CSV: {saida}\nlogs e tempos: {brutos}")


if __name__ == "__main__":
    main()
