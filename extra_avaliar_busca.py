"""
EXTRA – Mede a qualidade da recuperação usando o banco de perguntas.

Para cada pergunta (exceto "Sem resposta" e "Excluída"), verifica se algum
dos k chunks recuperados contém o trecho-fonte do gabarito. Não chama o LLM,
então é rápido e gratuito: use para ajustar chunking e k ANTES do experimento.

Uso:  python extra_avaliar_busca.py caminho/banco_perguntas_uespi_rag.xlsx
      python extra_avaliar_busca.py banco.xlsx --k 6

Saída: resultados/avaliacao_busca.csv + resumo no terminal (hit rate e MRR).
"""
import argparse
import csv
import re
import sys

from openpyxl import load_workbook

import config
from rag.embeddings import Embedder
from rag.indice import Buscador

sys.stdout.reconfigure(encoding="utf-8")


def palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[0-9a-zà-ú]+", texto.lower()) if len(p) >= 3}


def fragmentos(trecho: str) -> list[set[str]]:
    """O trecho-fonte pode ter cortes '[...]' e marcas '[D5]'. Usa os pedaços com 6+ palavras."""
    partes = re.split(r"\[\.\.\.\]|\[D\d+\]", trecho)
    return [palavras(p) for p in partes if len(p.split()) >= 6]


def contem(chunk: dict, frag: set[str], minimo: float = 0.85) -> bool:
    """Considera que o chunk contém o fragmento se tiver 85%+ das palavras dele
    (tolera diferenças de formatação, como a data ir para o título da seção)."""
    return len(frag & palavras(chunk["secao"] + " " + chunk["texto"])) / len(frag) >= minimo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("planilha")
    parser.add_argument("--k", type=int, default=config.K)
    parser.add_argument("--embeddings", default=config.MODELO_EMBEDDINGS)
    args = parser.parse_args()
    config.MODELO_EMBEDDINGS = args.embeddings

    aba = load_workbook(args.planilha, read_only=True)["Perguntas"]
    linhas = list(aba.iter_rows(values_only=True))
    col = {nome: i for i, nome in enumerate(linhas[0])}
    perguntas = [l for l in linhas[1:] if l[col["ID"]]
                 and l[col["Tipo"]] != "Sem resposta" and l[col["Status"]] != "Excluída"]

    buscador = Buscador(Embedder(config.MODELO_EMBEDDINGS, config.PREFIXO_CONSULTA,
                                 config.PREFIXO_DOCUMENTO))
    resultados, acertos, soma_rr, sem_fragmento = [], 0, 0.0, 0
    for l in perguntas:
        frags = fragmentos(l[col["Trecho-fonte"]] or "")
        if not frags:
            sem_fragmento += 1
            continue
        trechos = buscador.buscar(l[col["Pergunta"]], args.k)
        posicao = next((n for n, t in enumerate(trechos, 1)
                        if any(contem(t, f) for f in frags)), None)
        acertos += posicao is not None
        soma_rr += 1 / posicao if posicao else 0
        resultados.append({"id": l[col["ID"]], "categoria": l[col["Categoria"]], "tipo": l[col["Tipo"]],
                           "encontrou": "Sim" if posicao else "Não", "posicao": posicao or "",
                           "recuperados": " ".join(t["id"] for t in trechos),
                           "pergunta": l[col["Pergunta"]]})

    config.PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    saida = config.PASTA_RESULTADOS / "avaliacao_busca.csv"
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=list(resultados[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(resultados)

    n = len(resultados)
    print(f"\nPerguntas avaliadas: {n} (k = {args.k}, embeddings = {config.MODELO_EMBEDDINGS})")
    if sem_fragmento:
        print(f"Puladas por não ter trecho-fonte em texto: {sem_fragmento}")
    print(f"Hit rate@{args.k}: {acertos / n:.1%}   (trecho certo entre os {args.k} recuperados)")
    print(f"MRR@{args.k}:      {soma_rr / n:.3f}  (1 = sempre em 1º lugar)")
    falhas = [r for r in resultados if r["encontrou"] == "Não"]
    if falhas:
        print("\nPerguntas em que a busca NÃO trouxe o trecho certo:")
        for r in falhas:
            print(f"  {r['id']}: {r['pergunta'][:90]}")
    print(f"\nDetalhes em {saida}")


if __name__ == "__main__":
    main()
