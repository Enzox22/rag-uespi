"""
PASSO 1 – Extrai o texto de todos os PDFs listados em documentos.json.

Uso:  python passo1_extrair.py

Entrada: corpus/pdf/*.pdf
Saída:   corpus/bruto/<código>.txt  (pode ser sobrescrito sem problema)
"""
import json
import sys

import config
from rag.extracao import extrair_pdf

sys.stdout.reconfigure(encoding="utf-8")


def main():
    config.PASTA_BRUTO.mkdir(parents=True, exist_ok=True)
    documentos = json.loads(config.CATALOGO.read_text(encoding="utf-8"))
    for doc in documentos:
        pdf = config.PASTA_PDF / doc["arquivo"]
        if not pdf.exists():
            print(f"[{doc['codigo']}] ARQUIVO NÃO ENCONTRADO: {pdf.name} (pulei)")
            continue
        texto, removidas = extrair_pdf(pdf)
        destino = config.PASTA_BRUTO / f"{doc['codigo']}.txt"
        destino.write_text(texto, encoding="utf-8")
        palavras = len(texto.split())
        print(f"[{doc['codigo']}] {pdf.name}: {palavras} palavras -> {destino.name}")
        for linha in removidas:
            print(f"      cabeçalho/rodapé removido: {linha[:80]}")
        if palavras < 50:
            print("      ATENÇÃO: pouco texto. O conteúdo deve estar em imagens; transcreva no passo 2.")


if __name__ == "__main__":
    main()
