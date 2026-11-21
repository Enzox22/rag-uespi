"""
Embeddings: transformam texto em vetores numéricos que representam o
significado. Textos com sentido parecido ficam com vetores próximos.

O mesmo modelo é usado para os chunks (na indexação) e para a pergunta
(na consulta). Os vetores são normalizados, então a similaridade de
cosseno é o produto escalar entre eles.
"""
import hashlib
import re

import numpy as np


class Embedder:
    def __init__(self, nome_modelo: str, prefixo_consulta: str = "", prefixo_documento: str = ""):
        self.nome = nome_modelo
        self.prefixo_consulta = prefixo_consulta
        self.prefixo_documento = prefixo_documento
        if nome_modelo == "teste":
            self._modelo = None
        else:
            from sentence_transformers import SentenceTransformer  # importa só quando precisa
            print(f"Carregando modelo de embeddings {nome_modelo} (na 1ª vez ele é baixado)...")
            self._modelo = SentenceTransformer(nome_modelo)

    def _codificar(self, textos: list[str]) -> np.ndarray:
        if self._modelo is None:
            return np.vstack([_embedding_teste(t) for t in textos])
        return self._modelo.encode(textos, normalize_embeddings=True,
                                   batch_size=16, show_progress_bar=len(textos) > 16)

    def documentos(self, textos: list[str]) -> np.ndarray:
        return self._codificar([self.prefixo_documento + t for t in textos])

    def consulta(self, texto: str) -> np.ndarray:
        return self._codificar([self.prefixo_consulta + texto])[0]


def _embedding_teste(texto: str, dim: int = 512) -> np.ndarray:
    """Embedder SIMPLIFICADO (saco de palavras com hashing). Serve só para testar
    o código sem baixar o modelo. NÃO usar no experimento."""
    v = np.zeros(dim)
    for palavra in re.findall(r"\w+", texto.lower()):
        if len(palavra) > 2:
            v[int(hashlib.md5(palavra.encode()).hexdigest(), 16) % dim] += 1
    norma = np.linalg.norm(v)
    return v / norma if norma else v
