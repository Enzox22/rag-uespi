"""
PASSO 5 – Roda o experimento: todas as perguntas do banco, SEM RAG e COM RAG.

Uso:
  python passo5_experimento.py banco_perguntas_uespi_rag.xlsx --limite 2   (teste com 2 perguntas)
  python passo5_experimento.py banco_perguntas_uespi_rag.xlsx              (experimento completo)
  python passo5_experimento.py banco_perguntas_uespi_rag.xlsx --repeticoes 3
  python passo5_experimento.py banco_perguntas_uespi_rag.xlsx --so-planilha (só regera a planilha)

O que faz:
1. Lê a aba Perguntas (ignora as marcadas como "Excluída").
2. Para cada pergunta: busca os k trechos e chama o LLM nas duas condições,
   com o mesmo prompt (só o bloco de trechos muda).
3. Grava cada resposta em resultados/experimento.jsonl, NA HORA. Se a internet
   cair ou a cota da API acabar, é só rodar de novo: ele continua de onde parou.
4. No fim, cria uma CÓPIA da planilha (..._respostas.xlsx) com a aba Pontuação
   preenchida: "Resposta do modelo" e "Recuperação" (Sim/Não, calculada
   automaticamente). A pontuação humana continua sendo sua.

A planilha original nunca é alterada.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

import config
from extra_avaliar_busca import contem, fragmentos
from rag.embeddings import Embedder
from rag.indice import Buscador
from rag.llm import LimiteDiario, gerar
from rag.prompt import VERSAO_PROMPT, montar_mensagens

sys.stdout.reconfigure(encoding="utf-8")
ARQ_SAIDA = config.PASTA_RESULTADOS / "experimento.jsonl"
CONDICOES = ("Sem RAG", "Com RAG")
PAUSA_ENTRE_CHAMADAS = 2   # segundos; ajuda a não estourar o limite por minuto


def ler_perguntas(planilha: str) -> list[dict]:
    aba = load_workbook(planilha, read_only=True)["Perguntas"]
    linhas = list(aba.iter_rows(values_only=True))
    col = {nome: i for i, nome in enumerate(linhas[0])}
    perguntas = []
    for l in linhas[1:]:
        if not l[col["ID"]] or l[col["Status"]] == "Excluída":
            continue
        perguntas.append({campo: l[col[campo]] for campo in
                          ("ID", "Pergunta", "Categoria", "Tipo", "Trecho-fonte")})
    return perguntas


def ja_feitos() -> set:
    if not ARQ_SAIDA.exists():
        return set()
    with open(ARQ_SAIDA, encoding="utf-8") as f:
        return {(r["id"], r["condicao"], r["repeticao"]) for r in map(json.loads, f)}


def recuperacao_correta(pergunta: dict, trechos: list[dict]) -> str:
    """Sim/Não: algum trecho recuperado contém o trecho-fonte do gabarito?"""
    if pergunta["Tipo"] == "Sem resposta":
        return "N/A"
    frags = fragmentos(pergunta["Trecho-fonte"] or "")
    if not frags:
        return ""
    return "Sim" if any(contem(t, f) for t in trechos for f in frags) else "Não"


def rodar(perguntas: list[dict], args) -> None:
    feitos = ja_feitos()
    tarefas = [(p, c, r) for p in perguntas for r in range(1, args.repeticoes + 1) for c in CONDICOES
               if (p["ID"], c, r) not in feitos]
    total = len(perguntas) * len(CONDICOES) * args.repeticoes
    print(f"{total - len(tarefas)} de {total} chamadas já feitas; faltam {len(tarefas)}.")
    if not tarefas:
        return

    buscador = Buscador(Embedder(config.MODELO_EMBEDDINGS, config.PREFIXO_CONSULTA,
                                 config.PREFIXO_DOCUMENTO))
    config.PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    cache_busca = {}
    for n, (p, condicao, rep) in enumerate(tarefas, 1):
        if p["ID"] not in cache_busca:                  # mesma busca para todas as repetições
            cache_busca[p["ID"]] = buscador.buscar(p["Pergunta"], config.K)
        trechos = cache_busca[p["ID"]]
        contexto = trechos if condicao == "Com RAG" else None
        mensagens = montar_mensagens(p["Pergunta"], contexto)
        try:
            saida = gerar(mensagens, args.modelo)
        except LimiteDiario:
            print("\nA COTA DIÁRIA da API acabou. O progresso está salvo.")
            print("Rode o mesmo comando amanhã (ou com outra chave) para continuar de onde parou.")
            break
        registro = {
            "id": p["ID"], "condicao": condicao, "repeticao": rep,
            "pergunta": p["Pergunta"], "categoria": p["Categoria"], "tipo": p["Tipo"],
            "data_hora": datetime.now().isoformat(timespec="seconds"),
            "versao_prompt": VERSAO_PROMPT, "temperatura": config.TEMPERATURA,
            "modelo_embeddings": config.MODELO_EMBEDDINGS, "k": config.K,
            "max_palavras_chunk": config.MAX_PALAVRAS_CHUNK,
            "trechos": [{"id": t["id"], "secao": t["secao"], "similaridade": t["similaridade"]}
                        for t in contexto or []],
            "recuperacao": recuperacao_correta(p, trechos) if condicao == "Com RAG" else "N/A",
            "prompt_usuario": mensagens[-1]["content"],
            **saida,
        }
        with open(ARQ_SAIDA, "a", encoding="utf-8") as f:   # grava na hora
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        print(f"[{n}/{len(tarefas)}] {p['ID']} {condicao} rep{rep} "
              f"({saida['segundos']}s, {saida['tokens_entrada']}+{saida['tokens_saida']} tokens)")
        time.sleep(PAUSA_ENTRE_CHAMADAS)


def preencher_planilha(planilha: str) -> None:
    if not ARQ_SAIDA.exists():
        print("Ainda não há respostas registradas.")
        return
    with open(ARQ_SAIDA, encoding="utf-8") as f:
        respostas = {(r["id"], r["condicao"], r["repeticao"]): r for r in map(json.loads, f)}

    livro = load_workbook(planilha)
    aba = livro["Pontuação"]
    cab = {c.value: c.column for c in aba[1]}
    preenchidas = 0
    for linha in range(2, aba.max_row + 1):
        chave = (aba.cell(linha, cab["ID pergunta"]).value,
                 aba.cell(linha, cab["Condição"]).value,
                 aba.cell(linha, cab["Repetição"]).value or 1)
        r = respostas.get(chave)
        if not r:
            continue
        aba.cell(linha, cab["Resposta do modelo"]).value = r["resposta"]
        if r["condicao"] == "Com RAG":
            aba.cell(linha, cab["Recuperação"]).value = r["recuperacao"] or None
        preenchidas += 1
    destino = Path(planilha).with_name(Path(planilha).stem + "_respostas.xlsx")
    livro.save(destino)
    print(f"\n{preenchidas} respostas copiadas para a aba Pontuação de: {destino}")
    print("(Repetições extras, se houver, ficam só em resultados/experimento.jsonl.)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("planilha")
    parser.add_argument("--modelo", default=config.MODELO_PADRAO, choices=list(config.MODELOS_LLM))
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--limite", type=int, help="usa só as N primeiras perguntas (teste)")
    parser.add_argument("--so-planilha", action="store_true")
    parser.add_argument("--embeddings", default=config.MODELO_EMBEDDINGS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    config.MODELO_EMBEDDINGS = args.embeddings

    perguntas = ler_perguntas(args.planilha)
    if args.limite:
        perguntas = perguntas[:args.limite]
    cfg = config.MODELOS_LLM[args.modelo]
    print(f"Perguntas: {len(perguntas)} | modelo: {cfg['modelo']} {cfg.get('parametros', '')} | "
          f"k = {config.K} | chunks até {config.MAX_PALAVRAS_CHUNK} palavras | prompt {VERSAO_PROMPT}")
    if not args.so_planilha:
        rodar(perguntas, args)
    preencher_planilha(args.planilha)


if __name__ == "__main__":
    main()
