"""
Passo 1 – Extração do texto dos PDFs.

Usa a PyMuPDF para ler o texto de cada página e faz uma limpeza básica:
- troca ligaduras tipográficas ("ﬁ" -> "fi");
- remove caracteres invisíveis que alguns PDFs carregam;
- remove cabeçalhos e rodapés que se repetem em várias páginas
  (endereço do campus, nome da instituição etc.) e números de página.

O texto de imagens (prints de tela) NÃO é extraído: ele precisa ser
transcrito à mão no arquivo de texto final (passo 2).
"""
import re
from collections import Counter

import pymupdf

LIGATURAS = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
INVISIVEIS = re.compile("[­​-‏‪-‮⁠-⁤﻿]")
BORDA = 3  # quantas linhas do topo e do fim de cada página contam como cabeçalho/rodapé


def limpar_linha(linha: str) -> str:
    for antigo, novo in LIGATURAS.items():
        linha = linha.replace(antigo, novo)
    linha = INVISIVEIS.sub("", linha).replace(" ", " ")
    return re.sub(r"[ \t]+", " ", linha).strip()


def extrair_pdf(caminho) -> tuple[str, list[str]]:
    """Retorna (texto, linhas_removidas_como_cabecalho_ou_rodape)."""
    with pymupdf.open(caminho) as doc:
        paginas = []
        for pagina in doc:
            linhas = [limpar_linha(l) for l in pagina.get_text("text").splitlines()]
            paginas.append([l for l in linhas if l])

    # Cabeçalho/rodapé: linha que aparece nas bordas de pelo menos metade das páginas
    # (e em no mínimo 3 páginas, para não apagar frases comuns como "do SIGAA.").
    removidas = set()
    if len(paginas) >= 3:
        bordas = Counter(l for pg in paginas for l in set(pg[:BORDA] + pg[-BORDA:]))
        minimo = max(3, len(paginas) // 2)
        removidas = {l for l, n in bordas.items() if n >= minimo}

    saida = []
    for pg in paginas:
        for i, linha in enumerate(pg):
            e_borda = i < BORDA or i >= len(pg) - BORDA
            if e_borda and linha in removidas:
                continue
            # número de página solto na primeira ou na última linha
            if (i == 0 or i == len(pg) - 1) and re.fullmatch(r"\d{1,3}", linha):
                continue
            saida.append(linha)
    return "\n".join(saida) + "\n", sorted(removidas)
