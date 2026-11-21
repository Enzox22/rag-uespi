"""
Configuração central do RAG.

Todos os parâmetros que precisam ser relatados na metodologia do artigo
ficam aqui, num só lugar. Se mudar algum, rode de novo os passos 3 e 4.
"""
from pathlib import Path

# ---------------------------------------------------------------- pastas
RAIZ = Path(__file__).resolve().parent
PASTA_PDF = RAIZ / "corpus" / "pdf"          # PDFs originais (entrada)
PASTA_BRUTO = RAIZ / "corpus" / "bruto"      # texto extraído dos PDFs (passo 1)
PASTA_TEXTO = RAIZ / "corpus" / "texto"      # texto final, organizado em seções (passo 2)
PASTA_INDICE = RAIZ / "indice"               # banco vetorial + lista de chunks (passo 3)
PASTA_RESULTADOS = RAIZ / "resultados"       # registro de cada consulta (passo 4)
CATALOGO = RAIZ / "documentos.json"          # lista dos documentos do corpus
ARQ_CHUNKS = PASTA_INDICE / "chunks.jsonl"
NOME_COLECAO = "corpus_uespi"

# ---------------------------------------------------------------- chunking
# Cada seção do texto final ("## ...") vira um chunk. Seções maiores que
# MAX_PALAVRAS_CHUNK são divididas em partes; menores que MIN são descartadas.
MAX_PALAVRAS_CHUNK = 180
MIN_PALAVRAS_CHUNK = 3

# ---------------------------------------------------------------- embeddings
# BGE-M3: multilíngue, bom em português, ~2,3 GB (baixado na 1ª execução).
# Alternativa mais leve: "intfloat/multilingual-e5-base" (exige os prefixos
# PREFIXO_CONSULTA = "query: " e PREFIXO_DOCUMENTO = "passage: ").
# "teste" usa um embedder simplificado SÓ para testar o código sem internet.
MODELO_EMBEDDINGS = "BAAI/bge-m3"
PREFIXO_CONSULTA = ""
PREFIXO_DOCUMENTO = ""

# ---------------------------------------------------------------- recuperação
K = 6  # nº de chunks recuperados por pergunta

# ---------------------------------------------------------------- LLM
# provedor: "groq", "openai", "anthropic" ou "nenhum" (só mostra o prompt).
# "parametros": opções extras enviadas à API, iguais nas duas condições.
# Para ver os modelos disponíveis na sua conta Groq, veja o README.
MODELOS_LLM = {
    # gpt-oss-120b: pesos abertos (Apache 2.0). É um modelo de raciocínio;
    # o nível de raciocínio fica fixo no mínimo ("low") em todas as chamadas.
    "gpt-oss": {"provedor": "groq", "modelo": "openai/gpt-oss-120b",
                "parametros": {"reasoning_effort": "low"}},
    "qwen":   {"provedor": "groq",      "modelo": "qwen/qwen3.8-27b"},
    "claude": {"provedor": "anthropic", "modelo": "claude-haiku-5-5"},
    "gpt":    {"provedor": "openai",    "modelo": "PREENCHER-com-o-modelo-escolhido"},
    "nenhum": {"provedor": "nenhum",    "modelo": "-"},
}
MODELO_PADRAO = "gpt-oss"
TEMPERATURA = 0.0
MAX_TOKENS_RESPOSTA = 2000  # inclui os tokens de raciocínio do gpt-oss
