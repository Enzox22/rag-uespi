"""
Índice vetorial (ChromaDB): guarda os vetores dos chunks no disco e
encontra os k chunks mais próximos de uma pergunta (similaridade de cosseno).
"""
import json

import chromadb

import config


def _cliente():
    return chromadb.PersistentClient(path=str(config.PASTA_INDICE / "chroma"))


def criar_indice(chunks: list[dict], vetores) -> None:
    cliente = _cliente()
    try:
        cliente.delete_collection(config.NOME_COLECAO)   # recria do zero a cada indexação
    except Exception:
        pass
    colecao = cliente.create_collection(
        config.NOME_COLECAO,
        metadata={"hnsw:space": "cosine", "modelo_embeddings": config.MODELO_EMBEDDINGS},
    )
    colecao.add(
        ids=[c["id"] for c in chunks],
        embeddings=[list(map(float, v)) for v in vetores],
        documents=[c["texto"] for c in chunks],
        metadatas=[{"codigo": c["codigo"], "documento": c["documento"], "secao": c["secao"]}
                   for c in chunks],
    )
    with open(config.ARQ_CHUNKS, "w", encoding="utf-8") as f:   # cópia legível dos chunks
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


class Buscador:
    def __init__(self, embedder):
        self.embedder = embedder
        self.colecao = _cliente().get_collection(config.NOME_COLECAO)
        modelo_indice = (self.colecao.metadata or {}).get("modelo_embeddings")
        if modelo_indice and modelo_indice != embedder.nome:
            raise RuntimeError(f"O índice foi criado com '{modelo_indice}', mas o config usa "
                               f"'{embedder.nome}'. Rode o passo 3 de novo.")

    def buscar(self, pergunta: str, k: int) -> list[dict]:
        vetor = self.embedder.consulta(pergunta)
        r = self.colecao.query(query_embeddings=[list(map(float, vetor))], n_results=k)
        trechos = []
        for i in range(len(r["ids"][0])):
            meta = r["metadatas"][0][i]
            trechos.append({
                "id": r["ids"][0][i],
                "codigo": meta["codigo"],
                "documento": meta["documento"],
                "secao": meta["secao"],
                "texto": r["documents"][0][i],
                "similaridade": round(1 - r["distances"][0][i], 4),   # cosseno
            })
        return trechos
