"""
EXTRA – Intervalos de confiança de 95% (bootstrap pareado por pergunta) e
correção de Holm para os testes do passo 7.

Uso: python extra_ic_holm.py banco_final_consenso.xlsx
Saída: resultados/analise/ic95.csv e testes_holm.csv
"""
import csv, sys
import numpy as np
from passo7_analise import ler_pontuacao, pares, PASTA, I, G
from scipy.stats import binomtest, wilcoxon, mannwhitneyu

sys.stdout.reconfigure(encoding="utf-8")
B, SEMENTE = 10000, 2026
rng = np.random.default_rng(SEMENTE)

def boot(d):
    d = np.asarray(d, float)
    idx = rng.integers(0, len(d), (B, len(d)))
    m = d[idx].mean(axis=1)
    return d.mean(), np.percentile(m, 2.5), np.percentile(m, 97.5)

def boot2(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ma = a[rng.integers(0, len(a), (B, len(a)))].mean(1)
    mb = b[rng.integers(0, len(b), (B, len(b)))].mean(1)
    d = ma - mb
    return a.mean() - b.mean(), np.percentile(d, 2.5), np.percentile(d, 97.5)

linhas = ler_pontuacao(sys.argv[1])
ic, testes = [], []
for nome, cat in (("Todas", None), ("Institucional", I), ("Geral", G)):
    p = pares(linhas, "correta", cat)
    d = [int(c) - int(s) for s, c in p]
    ic.append((nome, "Respostas corretas (p.p.)", len(d), *[100 * x for x in boot(d)]))
    b, c_ = sum(1 for s, c in p if s and not c), sum(1 for s, c in p if c and not s)
    testes.append((nome, "Resposta correta", "McNemar", binomtest(min(b, c_), b + c_, 0.5).pvalue if b + c_ else 1.0))
    p = pares(linhas, "alucinou", cat, incluir_sem_resposta=True)
    d = [int(c) - int(s) for s, c in p]
    ic.append((nome, "Alucinação (p.p.)", len(d), *[100 * x for x in boot(d)]))
    b, c_ = sum(1 for s, c in p if s and not c), sum(1 for s, c in p if c and not s)
    testes.append((nome, "Alucinação", "McNemar", binomtest(min(b, c_), b + c_, 0.5).pvalue if b + c_ else 1.0))
    for campo, rot, esc in (("acuracia", "Acurácia (0-2)", 1), ("completude", "Completude (p.p.)", 100), ("rastreab", "Rastreabilidade (0-2)", 1)):
        p = pares(linhas, campo, cat)
        d = [c - s for s, c in p]
        ic.append((nome, rot, len(d), *[esc * x for x in boot(d)]))
        testes.append((nome, rot.split(" (")[0], "Wilcoxon", wilcoxon(d).pvalue if any(d) else 1.0))
gi = [c - s for s, c in pares(linhas, "acuracia", I)]
gg = [c - s for s, c in pares(linhas, "acuracia", G)]
ic.append(("Institucional − Geral", "Diferença no ganho de acurácia", f"{len(gi)} x {len(gg)}", *boot2(gi, gg)))
testes.append(("Institucional x Geral", "Ganho em acurácia", "Mann-Whitney", mannwhitneyu(gi, gg, alternative="two-sided").pvalue))

# Holm
ordem = sorted(range(len(testes)), key=lambda i: testes[i][3])
m, aj, maxv = len(testes), [None] * len(testes), 0
for r, i in enumerate(ordem):
    maxv = max(maxv, min(1, (m - r) * testes[i][3])); aj[i] = maxv
with open(PASTA / "ic95.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["grupo", "medida", "n", "diferenca_com_menos_sem", "ic95_inf", "ic95_sup"])
    for r in ic: w.writerow([r[0], r[1], r[2]] + [f"{x:.2f}" for x in r[3:]])
with open(PASTA / "testes_holm.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["grupo", "metrica", "teste", "p", "p_holm"])
    for t, a in zip(testes, aj): w.writerow([*t[:3], f"{t[3]:.4f}", f"{a:.4f}"])
for r in ic: print(r[0], "|", r[1], "|", r[2], "|", " ".join(f"{x:.2f}" for x in r[3:]))
print()
for t, a in zip(testes, aj): print(t[0], "|", t[1], "|", t[2], "| p", f"{t[3]:.4f}", "| holm", f"{a:.4f}")
