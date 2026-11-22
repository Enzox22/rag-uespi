"""
mini_rag.py – versão didática, em um único arquivo, do pipeline RAG do projeto.

Acompanha o tutorial "Como construir um assistente RAG em Python".
O projeto completo (com avaliação e experimento) está em
https://github.com/Enzox22/rag-uespi

Uso:
  python mini_rag.py indexar  pasta_dos_pdfs/          -> cria o índice
  python mini_rag.py perguntar "Quando começam as aulas de 2026.2?"
  python mini_rag.py perguntar "..." --sem-llm          -> só mostra a busca e o prompt
  Acrescente --teste para usar um embedder simplificado (sem baixar o modelo).
"""
import hashlib
import os
import re
import sys
from pathlib import Path

import numpy as np

PASTA_INDICE = "indice_mini"
COLECAO = "documentos"
MAX_PALAVRAS = 180   # tamanho máximo de cada trecho
K = 6                # quantos trechos recuperar por pergunta
MODELO_EMBEDDINGS = "BAAI/bge-m3"
MODELO_LLM = "openai/gpt-oss-120b"   # via API da Groq


# ------------------------------------------------------------ 1. extração
def extrair_texto(caminho_pdf: str) -> str:
    """Lê o texto de todas as páginas de um PDF e faz uma limpeza básica."""
    import pymupdf
    linhas = []
    with pymupdf.open(caminho_pdf) as doc:
        for pagina in doc:
            for linha in pagina.get_text("text").splitlines():
                linha = re.sub(r"\s+", " ", linha.replace("ﬁ", "fi").replace("ﬂ", "fl")).strip()
                if linha and not re.fullmatch(r"\d{1,3}", linha):   # descarta nº de página
                    linhas.append(linha)
    return "\n".join(linhas)


# ------------------------------------------------------------ 2. trechos (chunks)
def dividir_em_trechos(texto: str, maximo: int = MAX_PALAVRAS) -> list[str]:
    """Junta parágrafos até chegar perto de `maximo` palavras por trecho."""
    trechos, atual = [], []
    for paragrafo in texto.split("\n"):
        palavras = paragrafo.split()
        if not palavras:
            continue
        if atual and len(atual) + len(palavras) > maximo:
            trechos.append(" ".join(atual))
            atual = []
        atual.extend(palavras)
        while len(atual) > maximo:                 # parágrafo gigante: corta no limite
            trechos.append(" ".join(atual[:maximo]))
            atual = atual[maximo:]
    if atual:
        trechos.append(" ".join(atual))
    return trechos


# ------------------------------------------------------------ 3. embeddings
class Embedder:
    def __init__(self, teste: bool = False):
        self.teste = teste
        if not teste:
            from sentence_transformers import SentenceTransformer
            self.modelo = SentenceTransformer(MODELO_EMBEDDINGS)

    def codificar(self, textos: list[str]) -> np.ndarray:
        if self.teste:
            return np.vstack([embedding_teste(t) for t in textos])
        return self.modelo.encode(textos, normalize_embeddings=True)


def embedding_teste(texto: str, dim: int = 512) -> np.ndarray:
    """Embedder SIMPLIFICADO (contagem de palavras com hashing), só para testes."""
    v = np.zeros(dim)
    for palavra in re.findall(r"\w+", texto.lower()):
        if len(palavra) > 2:
            v[int(hashlib.md5(palavra.encode()).hexdigest(), 16) % dim] += 1
    norma = np.linalg.norm(v)
    return v / norma if norma else v


# ------------------------------------------------------------ 4. índice vetorial
def colecao(recriar: bool = False):
    import chromadb
    cliente = chromadb.PersistentClient(path=PASTA_INDICE)
    if recriar:
        try:
            cliente.delete_collection(COLECAO)
        except Exception:
            pass
        return cliente.create_collection(COLECAO, metadata={"hnsw:space": "cosine"})
    return cliente.get_collection(COLECAO)


def indexar(pasta_pdfs: str, embedder: Embedder) -> None:
    ids, textos, fontes = [], [], []
    for pdf in sorted(Path(pasta_pdfs).glob("*.pdf")):
        for n, trecho in enumerate(dividir_em_trechos(extrair_texto(str(pdf))), 1):
            ids.append(f"{pdf.stem}-{n:03d}")
            textos.append(trecho)
            fontes.append({"documento": pdf.stem})
    vetores = embedder.codificar([f"{f['documento']} | {t}" for f, t in zip(fontes, textos)])
    colecao(recriar=True).add(ids=ids, documents=textos, metadatas=fontes,
                              embeddings=[list(map(float, v)) for v in vetores])
    print(f"{len(ids)} trechos indexados em {PASTA_INDICE}/")


# ------------------------------------------------------------ 5. busca
def buscar(pergunta: str, embedder: Embedder, k: int = K) -> list[dict]:
    vetor = embedder.codificar([pergunta])[0]
    r = colecao().query(query_embeddings=[list(map(float, vetor))], n_results=k)
    return [{"id": r["ids"][0][i],
             "documento": r["metadatas"][0][i]["documento"],
             "texto": r["documents"][0][i],
             "similaridade": round(1 - r["distances"][0][i], 3)}
            for i in range(len(r["ids"][0]))]


# ------------------------------------------------------------ 6. prompt e resposta
INSTRUCOES = ("Você é um assistente que responde dúvidas de estudantes universitários. "
              "Responda em português, de forma objetiva. Baseie sua resposta nos trechos "
              "fornecidos. Se a informação não estiver nos trechos, diga claramente que "
              "não sabe. Indique a fonte da informação.")


def montar_mensagens(pergunta: str, trechos: list[dict]) -> list[dict]:
    blocos = "\n\n".join(f"[{n}] Fonte: {t['documento']}\n{t['texto']}"
                         for n, t in enumerate(trechos, 1))
    return [{"role": "system", "content": INSTRUCOES},
            {"role": "user", "content": f"Trechos de documentos:\n\n{blocos}\n\nPergunta: {pergunta}"}]


def gerar_resposta(mensagens: list[dict]) -> str:
    from openai import OpenAI          # a Groq usa a mesma interface da OpenAI
    cliente = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
    r = cliente.chat.completions.create(model=MODELO_LLM, messages=mensagens,
                                        temperature=0, max_tokens=2000)
    return r.choices[0].message.content


# ------------------------------------------------------------ uso pela linha de comando
if __name__ == "__main__":
    args = sys.argv[1:]
    teste, sem_llm = "--teste" in args, "--sem-llm" in args
    args = [a for a in args if not a.startswith("--")]
    if len(args) != 2 or args[0] not in ("indexar", "perguntar"):
        sys.exit(__doc__)
    embedder = Embedder(teste)
    if args[0] == "indexar":
        indexar(args[1], embedder)
    else:
        trechos = buscar(args[1], embedder)
        for n, t in enumerate(trechos, 1):
            print(f"[{n}] {t['documento']} (similaridade {t['similaridade']}): {t['texto'][:90]}...")
        mensagens = montar_mensagens(args[1], trechos)
        print("\n" + (mensagens[1]["content"][-300:] if sem_llm else gerar_resposta(mensagens)))
