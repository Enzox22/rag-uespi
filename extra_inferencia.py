"""
EXTRA – Inferência coerente: cada valor-p e seu IC 95% vêm do MESMO procedimento.

- Proporções pareadas (resposta correta, alucinação): teste exato de McNemar
  (binomial nos pares discordantes) e IC exato condicional da diferença,
  obtido do IC de Clopper-Pearson da fração de discordantes a favor do RAG.
  O IC exclui zero se, e somente se, p < 0,05.
- Escalas ordinais (acurácia, completude, rastreabilidade): teste de permutação
  pareado (troca de sinais) para a diferença de médias; IC 95% por inversão
  do mesmo teste (conjunto dos deslocamentos não rejeitados).
- Ganho institucional x geral: teste de permutação de dois grupos e IC por inversão.
- Correção de Holm sobre os 16 testes.

Uso: python extra_inferencia.py banco_final_consenso.xlsx
Saída: resultados/analise/inferencia.csv
"""
import csv, itertools, sys
import numpy as np
from scipy.stats import binomtest, beta
from passo7_analise import ler_pontuacao, pares, PASTA, I, G

sys.stdout.reconfigure(encoding="utf-8")
R, SEMENTE, ALFA = 20_000, 2026, 0.05
rng = np.random.default_rng(SEMENTE)


def mcnemar(p):
    n = len(p)
    b = sum(1 for s, c in p if s and not c)      # só sem RAG certo
    c = sum(1 for s, c in p if c and not s)      # só com RAG certo
    m = b + c
    if m == 0:
        return 0.0, 0.0, 0.0, 1.0
    pv = binomtest(c, m, 0.5).pvalue
    lo = beta.ppf(ALFA / 2, c, m - c + 1) if c > 0 else 0.0
    hi = beta.ppf(1 - ALFA / 2, c + 1, m - c) if c < m else 1.0
    f = lambda t: m / n * (2 * t - 1)
    return (c - b) / n, f(lo), f(hi), pv


def limites(p_de, centro, baixo, alto, it=30):
    """Inverte o teste: menor e maior deslocamento com p >= ALFA (bissecção)."""
    def busca(fora, dentro):
        for _ in range(it):
            meio = (fora + dentro) / 2
            if p_de(meio) >= ALFA: dentro = meio
            else: fora = meio
        return dentro
    return busca(baixo, centro), busca(alto, centro)


def sinais(n):
    if n <= 14:
        return np.array(list(itertools.product([-1, 1], repeat=n)), float)
    return rng.choice([-1.0, 1.0], size=(R, n))


def perm_pareado(d):
    d = np.asarray(d, float)
    S = sinais(len(d))
    def p_de(delta):
        x = d - delta
        obs = abs(x.mean())
        return np.mean(np.abs((S * x).mean(1)) >= obs - 1e-12)
    return d.mean(), *limites(p_de, d.mean(), d.min() - 1, d.max() + 1), p_de(0.0)


def perm_dois(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    tudo, na = np.concatenate([a, b]), len(a)
    idx = np.array([rng.permutation(len(tudo)) for _ in range(R)])
    def p_de(delta):
        z = np.concatenate([a - delta, b])
        obs = abs(z[:na].mean() - z[na:].mean())
        zz = z[idx]
        return np.mean(np.abs(zz[:, :na].mean(1) - zz[:, na:].mean(1)) >= obs - 1e-12)
    est = a.mean() - b.mean()
    return est, *limites(p_de, est, est - 3, est + 3), p_de(0.0)


linhas = ler_pontuacao(sys.argv[1])
res = []
for nome, cat in (("Todas", None), ("Institucional", I), ("Geral", G)):
    res.append((nome, "Respostas corretas (p.p.)", "McNemar exato", 100, mcnemar(pares(linhas, "correta", cat))))
    res.append((nome, "Alucinação (p.p.)", "McNemar exato", 100,
                mcnemar(pares(linhas, "alucinou", cat, incluir_sem_resposta=True))))
    for campo, rot, esc in (("acuracia", "Acurácia (0-2)", 1), ("completude", "Completude (p.p.)", 100),
                            ("rastreab", "Rastreabilidade (0-2)", 1)):
        res.append((nome, rot, "Permutação pareada", esc, perm_pareado([c - s for s, c in pares(linhas, campo, cat)])))
gi = [c - s for s, c in pares(linhas, "acuracia", I)]
gg = [c - s for s, c in pares(linhas, "acuracia", G)]
res.append(("Institucional − Geral", "Diferença no ganho de acurácia", "Permutação 2 grupos", 1, perm_dois(gi, gg)))

ordem = sorted(range(len(res)), key=lambda i: res[i][4][3])
m, aj, mx = len(res), [0] * len(res), 0
for r, i in enumerate(ordem):
    mx = max(mx, min(1, (m - r) * res[i][4][3])); aj[i] = mx
with open(PASTA / "inferencia.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["grupo", "medida", "teste", "diferenca", "ic95_inf", "ic95_sup", "p", "p_holm"])
    for (g, med, t, e, (d, lo, hi, p)), a in zip(res, aj):
        w.writerow([g, med, t, f"{e*d:.2f}", f"{e*lo:.2f}", f"{e*hi:.2f}", f"{p:.4f}", f"{a:.4f}"])
        print(f"{g} | {med} | {t} | {e*d:.2f} ({e*lo:.2f} a {e*hi:.2f}) | p {p:.4f} | holm {a:.4f}")
