"""
Divisão do texto final em chunks.

Regra: cada seção "## ..." de corpus/texto/<código>.md vira um chunk.
Se a seção passar de MAX_PALAVRAS_CHUNK, ela é dividida por parágrafos
em partes menores, e cada parte repete o título da seção (para não
perder o contexto).

O texto que vai para o embedding inclui o nome do documento e da seção,
o que ajuda a busca (ex.: "Calendário Acadêmico ... | 10/08/2026 ...").
"""
import re


def _contar(texto: str) -> int:
    return len(texto.split())


def _dividir(paragrafos: list[str], maximo: int) -> list[str]:
    partes, atual = [], []
    for p in paragrafos:
        if atual and _contar(" ".join(atual + [p])) > maximo:
            partes.append("\n".join(atual))
            atual = []
        if _contar(p) > maximo:                      # parágrafo gigante: corta por palavras
            palavras = p.split()
            for i in range(0, len(palavras), maximo):
                partes.append(" ".join(palavras[i:i + maximo]))
        else:
            atual.append(p)
    if atual:
        partes.append("\n".join(atual))
    # sobras muito pequenas (ex.: "pesquisa.") são juntadas à parte anterior
    juntas = []
    for parte in partes:
        if juntas and _contar(parte) < 30:
            juntas[-1] += "\n" + parte
        else:
            juntas.append(parte)
    return juntas


def chunks_do_documento(markdown: str, doc: dict, maximo: int, minimo: int) -> list[dict]:
    secoes = re.split(r"(?m)^## ", markdown)[1:]   # o que vem antes do 1º "## " é cabeçalho
    chunks = []
    for secao in secoes:
        titulo, _, corpo = secao.partition("\n")
        corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S).strip()
        if _contar(corpo) < minimo:
            continue
        paragrafos = [p.strip() for p in corpo.split("\n") if p.strip()]
        partes = _dividir(paragrafos, maximo)
        for n, parte in enumerate(partes, 1):
            sufixo = f" (parte {n}/{len(partes)})" if len(partes) > 1 else ""
            chunks.append({
                "id": f"{doc['codigo']}-{len(chunks) + 1:03d}",
                "codigo": doc["codigo"],
                "documento": doc["titulo"],
                "secao": titulo.strip() + sufixo,
                "texto": parte,
                "palavras": _contar(parte),
            })
    return chunks


def texto_para_embedding(chunk: dict) -> str:
    return f"{chunk['documento']} | {chunk['secao']}\n{chunk['texto']}"
