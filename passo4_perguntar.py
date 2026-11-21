"""
PASSO 4 – Faz uma pergunta e compara as respostas SEM RAG e COM RAG.

Uso:
  python passo4_perguntar.py "Qual o prazo para trancar o curso em 2026.2?"
  python passo4_perguntar.py                      (modo interativo: várias perguntas)
  python passo4_perguntar.py --so-busca "..."     (só mostra os trechos recuperados)
  python passo4_perguntar.py --modelo claude "..."  (usa outro LLM do config.py)
  python passo4_perguntar.py --mostrar-prompt "..." (mostra o prompt enviado)

Cada consulta é registrada em resultados/consultas.jsonl (pergunta, trechos,
resposta, modelo, tokens, tempo), que depois serve para o experimento.
"""
import argparse
import json
import sys
from datetime import datetime

import config
from rag.embeddings import Embedder
from rag.indice import Buscador
from rag.llm import gerar
from rag.prompt import VERSAO_PROMPT, montar_mensagens

sys.stdout.reconfigure(encoding="utf-8")


def registrar(registro: dict) -> None:
    config.PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    with open(config.PASTA_RESULTADOS / "consultas.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def responder(pergunta: str, buscador: Buscador, args) -> None:
    trechos = buscador.buscar(pergunta, args.k)
    print("\n=== TRECHOS RECUPERADOS ===")
    for n, t in enumerate(trechos, 1):
        print(f"[{n}] {t['id']}  similaridade {t['similaridade']:.3f}  |  {t['codigo']} – {t['secao'][:70]}")
        print(f"    {t['texto'][:200].replace(chr(10), ' ')}...")
    if args.so_busca:
        return

    for condicao, contexto in (("SEM RAG", None), ("COM RAG", trechos)):
        mensagens = montar_mensagens(pergunta, contexto)
        if args.mostrar_prompt:
            print(f"\n--- prompt {condicao} ---")
            for m in mensagens:
                print(f"<{m['role']}>\n{m['content']}\n")
        saida = gerar(mensagens, args.modelo)
        print(f"\n=== {condicao} ({saida['modelo']}, {saida['segundos']}s) ===\n{saida['resposta']}")
        registrar({
            "data_hora": datetime.now().isoformat(timespec="seconds"),
            "pergunta": pergunta,
            "condicao": condicao,
            "versao_prompt": VERSAO_PROMPT,
            "temperatura": config.TEMPERATURA,
            "modelo_embeddings": config.MODELO_EMBEDDINGS,
            "k": args.k,
            "trechos": [{"id": t["id"], "similaridade": t["similaridade"]} for t in contexto or []],
            **saida,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pergunta", nargs="?")
    parser.add_argument("--modelo", default=config.MODELO_PADRAO, choices=list(config.MODELOS_LLM))
    parser.add_argument("--k", type=int, default=config.K)
    parser.add_argument("--embeddings", default=config.MODELO_EMBEDDINGS)
    parser.add_argument("--so-busca", action="store_true")
    parser.add_argument("--mostrar-prompt", action="store_true")
    args = parser.parse_args()
    config.MODELO_EMBEDDINGS = args.embeddings

    embedder = Embedder(config.MODELO_EMBEDDINGS, config.PREFIXO_CONSULTA, config.PREFIXO_DOCUMENTO)
    buscador = Buscador(embedder)

    if args.pergunta:
        responder(args.pergunta, buscador, args)
        return
    print("Modo interativo. Digite uma pergunta (ou ENTER vazio para sair).")
    while True:
        pergunta = input("\nPergunta: ").strip()
        if not pergunta:
            break
        responder(pergunta, buscador, args)


if __name__ == "__main__":
    main()
