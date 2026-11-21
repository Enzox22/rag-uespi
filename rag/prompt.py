"""
Montagem do prompt – o ponto mais importante para isolar a variável.

As DUAS condições usam exatamente as mesmas instruções (mensagem de
sistema) e o mesmo formato. A única diferença é o bloco de documentos:
- com RAG: os k trechos recuperados entram antes da pergunta;
- sem RAG: o bloco não existe.

Não altere as instruções no meio do experimento. Se alterar, registre a
versão (VERSAO_PROMPT) e rode tudo de novo.
"""
VERSAO_PROMPT = "v1"

INSTRUCOES = (
    "Você é um assistente que responde dúvidas de estudantes da Universidade "
    "Estadual do Piauí (UESPI). Responda em português, de forma objetiva. "
    "Se trechos de documentos oficiais forem fornecidos, baseie sua resposta neles. "
    "Se você não tiver a informação necessária para responder, diga claramente "
    "que não sabe, em vez de supor. Quando possível, indique a fonte da informação."
)


def formatar_trechos(trechos: list[dict]) -> str:
    blocos = []
    for n, t in enumerate(trechos, 1):
        blocos.append(f"[{n}] Fonte: {t['documento']} – {t['secao']}\n{t['texto']}")
    return "\n\n".join(blocos)


def montar_mensagens(pergunta: str, trechos: list[dict] | None) -> list[dict]:
    if trechos:
        conteudo = (f"Trechos de documentos oficiais da UESPI:\n\n{formatar_trechos(trechos)}"
                    f"\n\nPergunta: {pergunta}")
    else:
        conteudo = f"Pergunta: {pergunta}"
    return [{"role": "system", "content": INSTRUCOES},
            {"role": "user", "content": conteudo}]
