"""
PASSO 3 – Divide os textos em chunks, gera os embeddings e cria o índice.

Uso:  python passo3_indexar.py
      python passo3_indexar.py --embeddings teste   (sem internet; só p/ testar o código)

Entrada: corpus/texto/*.md
Saída:   indice/chroma/       (banco vetorial)
         indice/chunks.jsonl  (lista legível de todos os chunks: confira!)

Rode de novo sempre que editar algum arquivo em corpus/texto/.
"""
import argparse
import json
import sys

import config
from rag.chunking import chunks_do_documento, texto_para_embedding
from rag.embeddings import Embedder
from rag.indice import criar_indice

sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--embeddings", default=config.MODELO_EMBEDDINGS)
    args = parser.parse_args()
    config.MODELO_EMBEDDINGS = args.embeddings
    config.PASTA_INDICE.mkdir(parents=True, exist_ok=True)

    documentos = json.loads(config.CATALOGO.read_text(encoding="utf-8"))
    chunks = []
    for doc in documentos:
        arquivo = config.PASTA_TEXTO / f"{doc['codigo']}.md"
        if not arquivo.exists():
            print(f"[{doc['codigo']}] sem texto final: rode o passo 2 antes (pulei)")
            continue
        novos = chunks_do_documento(arquivo.read_text(encoding="utf-8"), doc,
                                    config.MAX_PALAVRAS_CHUNK, config.MIN_PALAVRAS_CHUNK)
        tamanhos = [c["palavras"] for c in novos]
        print(f"[{doc['codigo']}] {len(novos)} chunks "
              f"(palavras: mín {min(tamanhos)}, máx {max(tamanhos)}, média {sum(tamanhos)//len(tamanhos)})")
        chunks.extend(novos)

    print(f"\nTotal: {len(chunks)} chunks. Gerando embeddings com '{config.MODELO_EMBEDDINGS}'...")
    embedder = Embedder(config.MODELO_EMBEDDINGS, config.PREFIXO_CONSULTA, config.PREFIXO_DOCUMENTO)
    vetores = embedder.documentos([texto_para_embedding(c) for c in chunks])
    criar_indice(chunks, vetores)
    print(f"Índice criado em {config.PASTA_INDICE} (dimensão dos vetores: {len(vetores[0])}).")
    print(f"Confira os chunks em {config.ARQ_CHUNKS}.")


if __name__ == "__main__":
    main()
