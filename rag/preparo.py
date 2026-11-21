"""
Passo 2 – Preparação do texto final de cada documento.

Transforma o texto bruto (passo 1) num arquivo Markdown simples, em que
cada seção começa com "## Título da seção". No passo 3, cada seção vira
um chunk. Ou seja: AQUI se decide a divisão do corpus em trechos.

Cada tipo de documento tem uma estratégia própria (campo "tipo" em
documentos.json):

- tutorial:   o tutorial inteiro vira uma seção só (são curtos);
- calendario: um evento por seção, com a data completa (dd/mm/aaaa);
- ppc:        uma seção por item do sumário (ex.: 16.1), mantendo só as
              seções listadas em "secoes"; nos apêndices, um capítulo por seção;
- edital:     uma seção por item numerado em maiúsculas (ex.: "6. DA SELEÇÃO");
- generico:   o documento inteiro, dividido depois por tamanho.
"""
import re

MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6,
         "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}
NOME_MES = {v: k.capitalize() for k, v in MESES.items()}


# ---------------------------------------------------------------- utilidades
def unir(a: str, b: str) -> str:
    """Une duas linhas; se a primeira termina em hífen colado ("e-"), não põe espaço."""
    return a + b if re.search(r"\w-$", a) else a + " " + b


def juntar_linhas(linhas: list[str]) -> str:
    """Junta linhas quebradas pelo PDF em parágrafos.
    Começa linha nova quando a linha seguinte parece início de item
    (1., a), Art., PASSO, ATENÇÃO...)."""
    inicio_item = re.compile(r"^(\d+(\.\d+)*\.?\s|\d+\.(?=\S)|[a-z]\)\s|Art\.|§|Parágrafo|PASSO|Passo|ATENÇÃO|[IVX]+\s*[-–])")
    paragrafos = []
    for linha in linhas:
        if paragrafos and not inicio_item.match(linha):
            paragrafos[-1] = unir(paragrafos[-1], linha)
        else:
            paragrafos.append(linha)
    return "\n".join(paragrafos)


def normalizar_espacos(texto: str) -> str:
    texto = re.sub(r"“\s+", "“", texto)
    texto = re.sub(r"\s+”", "”", texto)
    texto = re.sub(r"(?m)^(\d+)\.(?=[A-Za-zÀ-ú])", r"\1. ", texto)   # "4.Serão" -> "4. Serão"
    return re.sub(r"[ \t]+", " ", texto)


def aplicar_substituicoes(texto: str, substituicoes) -> str:
    for antigo, novo in substituicoes or []:
        texto = texto.replace(antigo, novo)
    return texto


# ---------------------------------------------------------------- tutorial
def preparar_tutorial(bruto: str, doc: dict) -> str:
    linhas = [l for l in bruto.splitlines() if l.strip()]
    return f"## {doc['titulo']}\n{juntar_linhas(linhas)}\n"


# ---------------------------------------------------------------- calendário
RE_MES = re.compile(r"^(" + "|".join(MESES) + r")\s*[-–]\s*(\d{4})")
RE_DATA = re.compile(r"^(Até\s+)?(\d{1,2})(?:/(\d{2}))?(?:\s*(a|e)\s*(\d{1,2})(?:/(\d{2}))?)?$")


def _data_completa(m, mes: int, ano: int) -> str:
    """'05 a 17' em janeiro de 2026 -> '05/01/2026 a 17/01/2026'."""
    ate, d1, m1, conector, d2, m2 = m.groups()
    m1 = int(m1) if m1 else mes
    texto = f"{int(d1):02d}/{m1:02d}/{ano}"
    if conector:
        m2 = int(m2) if m2 else m1
        ano2 = ano + 1 if m2 < m1 else ano          # ex.: 23/12 a 01/01 vira o ano
        texto += f" {conector} {int(d2):02d}/{m2:02d}/{ano2}"
    return ("Até " if ate else "") + texto


def preparar_calendario(bruto: str, doc: dict) -> str:
    linhas = [l.strip() for l in bruto.splitlines() if l.strip()]
    secoes = []                       # lista de (titulo, [linhas])
    preambulo, mes, ano = [], None, None
    data_pendente = None              # data lida que espera a descrição na linha seguinte

    atual = None                      # evento aberto (recebe as linhas de continuação)
    avulso = re.compile(r"(PERÍODO DE FÉRIAS|^\d{2}/\d{2} a \d{2}/\d{2}\b|RECESSO)")

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        i += 1
        if linha.startswith("Documento assinado eletronicamente"):
            break
        m_mes = RE_MES.match(linha)
        if m_mes:                                     # novo mês: "AGOSTO – 2026 – ..."
            mes, ano = MESES[m_mes.group(1)], int(m_mes.group(2))
            atual = data_pendente = None
            continue
        if mes is None:                               # texto antes do 1º mês (a resolução)
            preambulo.append(linha)
            continue
        contexto = f"{NOME_MES[mes]} de {ano}"
        m_data = RE_DATA.match(linha)
        if m_data:                                    # linha só com a data: "05 a 17"
            data_pendente, atual = _data_completa(m_data, mes, ano), None
        elif linha == "Segunda" and i < len(linhas) and linhas[i] == "quinzena":
            data_pendente, atual = f"Segunda quinzena de {contexto.lower()}", None
            i += 1
        elif data_pendente:                           # descrição do evento recém-datado
            atual = [f"{data_pendente} – {contexto}", [linha]]
            secoes.append(atual)
            data_pendente = None
        elif avulso.search(linha):                    # evento com a data no próprio texto
            secoes.append([contexto, [linha]])
            atual = None
        elif atual:                                   # continuação da descrição
            atual[1].append(linha)
        else:
            atual = [contexto, [linha]]
            secoes.append(atual)

    partes = [f"## Apresentação do calendário\n{juntar_linhas(preambulo)}\n"]
    for titulo, corpo in secoes:
        texto = corpo[0]
        for linha in corpo[1:]:
            texto = unir(texto, linha)
        partes.append(f"## {titulo}\n{texto}\n")
    return "\n".join(partes)


# ---------------------------------------------------------------- PPC
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().upper()


def _sumario(linhas: list[str]) -> list[tuple[str, str]]:
    """Lê o sumário (linhas com '.....') e devolve [(numero, titulo)]."""
    itens = []
    for linha in linhas:
        if "...." in linha:
            texto = re.sub(r"\.{4,}.*$", "", linha).strip()
        elif linha.upper().startswith("APÊNDICE") and re.search(r"\s\d{1,3}$", linha):
            texto = re.sub(r"\s\d{1,3}$", "", linha).strip()   # item sem pontilhado
        else:
            continue
        m = re.match(r"^((?:\d+\.)*\d+\.?)\s+(.+)$", texto)
        if m:
            itens.append((m.group(1).rstrip("."), texto))
        elif texto.upper().startswith("APÊNDICE"):
            itens.append((re.match(r"APÊNDICE\s+\w", texto.upper()).group(0), texto))
    return itens


def _incluida(numero: str, secoes: list[str]) -> bool:
    return any(numero == s or numero.startswith(s + ".") for s in secoes)


def preparar_ppc(bruto: str, doc: dict) -> str:
    linhas = [l.strip() for l in bruto.splitlines() if l.strip()]
    sumario = _sumario(linhas)
    titulos = {_norm(t): (n, t) for n, t in sumario}
    secoes_alvo = [s.upper() for s in doc.get("secoes", [])]

    saida, atual, corpo, apendice = [], None, [], None

    def fechar():
        if atual and _incluida(atual[0], secoes_alvo) and corpo:
            saida.append(f"## {atual[1]}\n{juntar_linhas(corpo)}\n")

    for linha in linhas:
        if "...." in linha or (linha.upper().startswith("APÊNDICE") and re.search(r"\s\d{1,3}$", linha)):
            continue                              # linha do próprio sumário
        chave = _norm(linha)
        if chave in titulos:                      # início de uma seção do sumário
            numero, titulo = titulos[chave]
            nivel = numero.count(".") + 1
            if numero.startswith("APÊNDICE"):
                fechar(); apendice = titulo
                atual, corpo = (numero, titulo), []
            elif nivel <= 2:                      # 1.4, 16.1 ... viram seção própria
                fechar(); apendice = None
                atual, corpo = (numero, f"{numero}. {titulo.split(' ', 1)[1]}"), []
            else:                                 # 1.4.1 ... fica dentro da seção-mãe
                corpo.append(titulo)
            continue
        if apendice and re.match(r"^(CAPÍTULO\s+[IVXLC]+|ANEXO\s+[A-Z]\s*[-–])", linha):
            fechar()                              # nos apêndices: um capítulo por seção
            atual, corpo = (atual[0], f"{apendice} – {linha}"), []
            continue
        corpo.append(linha)
    fechar()
    return "\n".join(saida)


# ---------------------------------------------------------------- edital
RE_ITEM_EDITAL = re.compile(r"^(\d{1,2})\.\s+([A-ZÀ-Ú][A-ZÀ-Ú\s\-–/()]+)$")


def preparar_edital(bruto: str, doc: dict) -> str:
    linhas = [l.strip() for l in bruto.splitlines() if l.strip()]
    secoes, titulo, corpo = [], "Apresentação", []
    for linha in linhas:
        m = RE_ITEM_EDITAL.match(linha)
        if m:
            secoes.append((titulo, corpo))
            titulo, corpo = linha, []
        else:
            corpo.append(linha)
    secoes.append((titulo, corpo))
    return "\n".join(f"## {t}\n{juntar_linhas(c)}\n" for t, c in secoes if c)


# ---------------------------------------------------------------- genérico
def preparar_generico(bruto: str, doc: dict) -> str:
    linhas = [l for l in bruto.splitlines() if l.strip()]
    return f"## {doc['titulo']}\n{juntar_linhas(linhas)}\n"


ESTRATEGIAS = {
    "tutorial": preparar_tutorial,
    "calendario": preparar_calendario,
    "ppc": preparar_ppc,
    "edital": preparar_edital,
    "generico": preparar_generico,
}


def preparar(bruto: str, doc: dict) -> str:
    estrategia = ESTRATEGIAS[doc.get("tipo", "generico")]
    corpo = estrategia(bruto, doc)
    corpo = normalizar_espacos(corpo)
    corpo = aplicar_substituicoes(corpo, doc.get("substituicoes"))
    cabecalho = (f"# {doc['codigo']} – {doc['titulo']}\n"
                 f"<!-- Gerado pelo passo 2. Pode editar à mão (ex.: transcrever prints). "
                 f"Cada '## ' inicia um chunk. -->\n\n")
    return cabecalho + corpo
