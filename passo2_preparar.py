"""
PASSO 2 – Organiza o texto de cada documento em seções (uma seção = um chunk).

Uso:  python passo2_preparar.py            (não sobrescreve arquivos já existentes)
      python passo2_preparar.py --forcar   (regera todos, APAGANDO edições manuais)
      python passo2_preparar.py --forcar D5 (regera só o D5)

Entrada: corpus/bruto/<código>.txt
Saída:   corpus/texto/<código>.md   <- REVISE estes arquivos. É aqui que se
         corrige texto quebrado e se transcreve o conteúdo dos prints.
"""
import argparse
import json
import sys

import config
from rag.preparo import preparar

sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--forcar", action="store_true", help="sobrescreve arquivos existentes")
    parser.add_argument("codigos", nargs="*", help="só estes documentos (ex.: D5 D6)")
    args = parser.parse_args()

    config.PASTA_TEXTO.mkdir(parents=True, exist_ok=True)
    documentos = json.loads(config.CATALOGO.read_text(encoding="utf-8"))
    for doc in documentos:
        if args.codigos and doc["codigo"] not in args.codigos:
            continue
        origem = config.PASTA_BRUTO / f"{doc['codigo']}.txt"
        destino = config.PASTA_TEXTO / f"{doc['codigo']}.md"
        if not origem.exists():
            print(f"[{doc['codigo']}] sem texto bruto: rode o passo 1 antes (pulei)")
            continue
        if destino.exists() and not args.forcar:
            print(f"[{doc['codigo']}] {destino.name} já existe (mantido; use --forcar para regerar)")
            continue
        texto = preparar(origem.read_text(encoding="utf-8"), doc)
        destino.write_text(texto, encoding="utf-8")
        n_secoes = texto.count("\n## ")
        print(f"[{doc['codigo']}] {n_secoes} seções -> {destino.name}")


if __name__ == "__main__":
    main()
