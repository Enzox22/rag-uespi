"""
Chamada ao LLM. Todos os provedores recebem as mesmas mensagens, com a
mesma temperatura e o mesmo limite de tokens (definidos em config.py).

As chaves de API ficam no arquivo .env (nunca no código):
    GROQ_API_KEY=...   OPENAI_API_KEY=...   ANTHROPIC_API_KEY=...
"""
import os
import re
import time

from dotenv import load_dotenv

import config

load_dotenv(config.RAIZ / ".env")


class LimiteDiario(Exception):
    """A cota DIÁRIA do plano gratuito acabou: só volta no dia seguinte."""


def _espera_sugerida(mensagem: str):
    """A Groq informa quanto esperar: 'Please try again in 1m2.5s' / '8.2s' / '350ms'."""
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", mensagem)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2)) + 1
    m = re.search(r"try again in ([\d.]+)ms", mensagem)
    return float(m.group(1)) / 1000 + 1 if m else None


def _com_tentativas(funcao, tentativas: int = 8):
    """Repete a chamada se a API recusar por excesso de requisições (erro 429)."""
    for n in range(tentativas):
        try:
            return funcao()
        except Exception as erro:
            mensagem = str(erro)
            limite = "429" in mensagem or "rate limit" in mensagem.lower()
            if not limite or n == tentativas - 1:
                raise
            if "per day" in mensagem.lower():
                raise LimiteDiario(mensagem) from erro
            espera = _espera_sugerida(mensagem) or 2 ** n * 5
            print(f"   limite por minuto atingido; aguardando {espera:.0f}s...")
            time.sleep(espera)


def gerar(mensagens: list[dict], chave_modelo: str) -> dict:
    cfg = config.MODELOS_LLM[chave_modelo]
    provedor, modelo = cfg["provedor"], cfg["modelo"]
    inicio = time.perf_counter()

    if provedor == "nenhum":                      # modo de teste: não chama API nenhuma
        resposta, t_in, t_out = "(modo 'nenhum': nenhum LLM foi chamado)", 0, 0

    elif provedor in ("groq", "openai"):          # a Groq usa a mesma interface da OpenAI
        from openai import OpenAI
        if provedor == "groq":
            cliente = OpenAI(api_key=os.environ["GROQ_API_KEY"],
                             base_url="https://api.groq.com/openai/v1")
        else:
            cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        r = _com_tentativas(lambda: cliente.chat.completions.create(
            model=modelo, messages=mensagens,
            temperature=config.TEMPERATURA, max_tokens=config.MAX_TOKENS_RESPOSTA,
            **cfg.get("parametros", {})))
        resposta = r.choices[0].message.content or ""
        if r.choices[0].finish_reason == "length":
            resposta += "\n[AVISO: resposta cortada pelo limite MAX_TOKENS_RESPOSTA]"
        t_in, t_out = r.usage.prompt_tokens, r.usage.completion_tokens

    elif provedor == "anthropic":                 # a Anthropic recebe o "system" separado
        import anthropic
        cliente = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        sistema = "\n".join(m["content"] for m in mensagens if m["role"] == "system")
        outras = [m for m in mensagens if m["role"] != "system"]
        r = _com_tentativas(lambda: cliente.messages.create(
            model=modelo, system=sistema, messages=outras,
            temperature=config.TEMPERATURA, max_tokens=config.MAX_TOKENS_RESPOSTA))
        resposta = "".join(b.text for b in r.content if b.type == "text")
        t_in, t_out = r.usage.input_tokens, r.usage.output_tokens

    else:
        raise ValueError(f"Provedor desconhecido: {provedor}")

    return {
        "resposta": resposta,
        "provedor": provedor,
        "modelo": modelo,
        "parametros": cfg.get("parametros", {}),
        "tokens_entrada": t_in,
        "tokens_saida": t_out,
        "segundos": round(time.perf_counter() - inicio, 2),
    }
