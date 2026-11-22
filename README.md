# RAG UESPI

Software desenvolvido como parte do Trabalho de Conclusão de Curso de **Enzo Damasceno Falcão**, no Curso Superior de Tecnologia em Sistemas de Computação da Universidade Estadual do Piauí (UESPI), Campus Prof. Alexandre Alves de Oliveira, Parnaíba-PI, sob orientação do **Prof. Dr. Átila Rabelo Lopes** (2026).

O sistema implementa um pipeline de Geração Aumentada por Recuperação (RAG) que responde a dúvidas acadêmicas com base em sete documentos oficiais e públicos da UESPI, e foi usado para comparar as respostas do LLM gpt-oss-120b sem e com RAG em 74 perguntas.

- **Site do projeto:** https://enzox22.github.io/rag-uespi/ (pasta `docs/`)
- **Material didático:** [Como construir um assistente RAG em Python](docs/material/Tutorial_RAG_Python.pdf) (PDF, com o código de apoio em `docs/material/codigo/mini_rag.py`)
- **Tecnologias:** Python, PyMuPDF, sentence-transformers (BAAI/bge-m3), ChromaDB, API da Groq, NumPy e SciPy.
- **Corpus:** `corpus/pdf/` (originais), `corpus/bruto/` (texto extraído) e `corpus/texto/` (texto revisado usado no índice).
- **Banco de perguntas:** `banco_perguntas_uespi_rag.xlsx` (perguntas, gabarito, rubrica e modelo da planilha de pontuação).
- Os scripts `extra_ic_holm.py` e `extra_inferencia.py` (análise estatística) dependem do módulo `passo7_analise.py`, que não faz parte desta versão do repositório.

---

## Guia passo a passo

Pipeline de RAG (*Retrieval-Augmented Generation*) do TCC "LLM com e sem RAG
sobre documentos da UESPI". Cada etapa é um script separado, para que você
possa rodar, inspecionar o resultado e explicar cada decisão na metodologia.

```
PDFs ─► passo 1: extrair ─► passo 2: organizar em seções ─► passo 3: chunks + embeddings + índice
                                   (você revisa aqui)                          │
pergunta ─► embedding ─► busca dos k chunks mais parecidos ─► prompt ─► LLM ─► resposta   (passo 4)
                                                                ▲
                                          sem RAG: o bloco de trechos não entra
```

## Estrutura do projeto

| Caminho | O que é |
|---|---|
| `config.py` | Todos os parâmetros (tamanho do chunk, k, modelos, temperatura). Relate-os no artigo. |
| `documentos.json` | Catálogo do corpus: código, título, arquivo e tipo de cada documento. |
| `corpus/pdf/` | PDFs originais (os 7 documentos já estão aqui). |
| `corpus/bruto/` | Texto extraído dos PDFs (gerado no passo 1). |
| `corpus/texto/` | **Texto final que vai para o RAG** (passo 2). É aqui que você revisa e transcreve prints. |
| `indice/` | Banco vetorial (ChromaDB) e `chunks.jsonl`, lista legível de todos os chunks (passo 3). |
| `resultados/` | Registro de cada consulta e avaliação da busca. |
| `rag/` | O código de cada etapa (extração, preparo, chunking, embeddings, índice, prompt, LLM). |

---

## 0. Preparar o ambiente (uma vez só)

**Requisitos:** Python 3.11 ou 3.12 (o 3.13 também deve funcionar), cerca de 5 GB livres
(PyTorch + modelo de embeddings) e internet na primeira execução.

Abra o terminal **dentro da pasta do projeto** e crie um ambiente virtual:

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Com o ambiente ativo (aparece `(.venv)` no início da linha), instale as bibliotecas:

```bash
pip install -r requirements.txt
```

> **Linux sem placa de vídeo NVIDIA:** antes do comando acima, rode
> `pip install torch --index-url https://download.pytorch.org/whl/cpu`
> para não baixar a versão com CUDA (cerca de 2 GB a mais).
> No Windows e no macOS, o `pip` já instala a versão adequada.

**Chave de API.** Copie `.env.example` para `.env` e cole sua chave
(a da Groq é gratuita: crie em console.groq.com → API Keys).
O `.env` nunca deve ser enviado para o GitHub nem anexado ao artigo.

---

## 1. Extrair o texto dos PDFs

```bash
python passo1_extrair.py
```

Lê cada PDF de `corpus/pdf/` e grava o texto em `corpus/bruto/`. Também limpa
ligaduras ("ﬁ" → "fi"), caracteres invisíveis, cabeçalhos/rodapés repetidos
(endereço do campus, nome da instituição) e números de página.

**O que conferir:** a saída lista o que foi removido como cabeçalho/rodapé.
Documentos com pouquíssimas palavras (o D1, por exemplo) têm conteúdo em imagens:
isso será resolvido no passo 2.

## 2. Organizar o texto em seções (onde se decide o chunking)

```bash
python passo2_preparar.py
```

Gera `corpus/texto/<código>.md`. **Cada linha que começa com `## ` inicia um chunk.**
A divisão depende do tipo do documento em `documentos.json`:

| Tipo | Como divide | Documentos |
|---|---|---|
| `tutorial` | o tutorial inteiro é uma seção | D1 a D4 |
| `calendario` | um evento por seção, com a data completa (`10/08/2026 a 10/09/2026`) | D5 |
| `ppc` | uma seção por item do sumário listado em `"secoes"`; nos apêndices, um capítulo por seção | D6 |
| `edital` | uma seção por item numerado (`6. DA SELEÇÃO`) | D7 |
| `generico` | documento inteiro (dividido depois por tamanho) | novos documentos simples |

**Esta é a etapa de revisão manual.** Abra os `.md` num editor de texto e:
- **transcreva o conteúdo dos prints** (ex.: no `D1.md`, os três documentos exigidos para o diploma);
- **corrija trechos quebrados** (o `D4.md`, feito de slides, precisa de uma boa revisão);
- se quiser dividir uma seção em duas, basta inserir outra linha `## Título`.

O script **não sobrescreve** arquivos que já existem, para proteger suas edições.
Para regerar um documento do zero (perdendo as edições dele): `python passo2_preparar.py --forcar D5`.

## 3. Criar o índice

```bash
python passo3_indexar.py
```

1. Lê os `.md` e cria os chunks (seções maiores que 180 palavras são divididas).
2. Gera os embeddings com o **BGE-M3** (baixado automaticamente na 1ª vez, ~2,3 GB; demora alguns minutos).
3. Grava tudo no ChromaDB, em `indice/`.

**O que conferir:** a quantidade de chunks por documento e o arquivo
`indice/chunks.jsonl`, com o texto exato de cada chunk. Rode este passo de novo
**sempre que editar** algum arquivo em `corpus/texto/`.

## 4. Fazer perguntas

```bash
python passo4_perguntar.py --so-busca "Qual o valor da bolsa de monitoria?"
python passo4_perguntar.py "Qual o prazo para trancar o curso em 2026.2?"
python passo4_perguntar.py                       # modo interativo
python passo4_perguntar.py --mostrar-prompt "..."  # mostra o prompt exato enviado
python passo4_perguntar.py --modelo claude "..."   # outro LLM configurado no config.py
```

Mostra os trechos recuperados (com a similaridade), depois a resposta **sem RAG**
e a resposta **com RAG**. Comece com `--so-busca`, que não gasta chamadas de API.
Cada consulta fica registrada em `resultados/consultas.jsonl`.

## 5. Rodar o experimento

```bash
python passo5_experimento.py banco_perguntas_uespi_rag.xlsx --limite 2   # teste rápido com 2 perguntas
python passo5_experimento.py banco_perguntas_uespi_rag.xlsx              # experimento completo
```

Roda cada pergunta (exceto as marcadas como "Excluída") nas duas condições, com o
mesmo prompt. Cada resposta é gravada na hora em `resultados/experimento.jsonl`:
se a internet cair ou a cota da API acabar, **rode o mesmo comando de novo** e ele
continua de onde parou. No fim, cria `banco_perguntas_uespi_rag_respostas.xlsx`
(a original não é alterada), com a aba Pontuação já preenchida nas colunas
"Resposta do modelo" e "Recuperação". A pontuação humana continua sendo sua.

Para regerar só a planilha a partir do registro: `--so-planilha`.
Para repetir cada pergunta (medir consistência): `--repeticoes 3`.

## Retomar o trabalho depois de desligar o computador

Nada precisa ser reinstalado: ambiente, modelo de embeddings, índice e chave ficam salvos.
Abra o terminal na pasta do projeto e ative o ambiente:

```bash
.venv\Scripts\Activate.ps1      # Windows
source .venv/bin/activate        # Linux / macOS
```

Os passos 1 a 3 só precisam rodar de novo se algum documento do corpus mudar.

## Extra: medir a qualidade da busca (antes do experimento)

```bash
python extra_avaliar_busca.py caminho/para/banco_perguntas_uespi_rag.xlsx
```

Para cada pergunta do banco, verifica se o trecho-fonte do gabarito está entre os
k chunks recuperados. Mostra o **hit rate** e o **MRR** e lista as perguntas em que a
busca falhou. Use para ajustar o chunking (passo 2) e o `K` (config.py) **antes** de
rodar o experimento; depois disso, não mude mais nada.

---

## Testar sem internet

Para verificar se o código roda sem baixar o modelo nem gastar API:

```bash
python passo3_indexar.py --embeddings teste
python passo4_perguntar.py --embeddings teste --modelo nenhum --mostrar-prompt "pergunta"
```

O embedder `teste` é propositalmente simples (contagem de palavras) e **não deve ser
usado no experimento**.

## Parâmetros para a metodologia

| Parâmetro | Valor | Onde |
|---|---|---|
| Extração de texto | PyMuPDF + limpeza (ligaduras, cabeçalhos/rodapés) | `rag/extracao.py` |
| Unidade de chunk | seção estrutural do documento; máx. 180 palavras | `rag/preparo.py`, `config.py` |
| Modelo de embeddings | BAAI/bge-m3 (vetores normalizados) | `config.py` |
| Banco vetorial / métrica | ChromaDB, similaridade de cosseno | `rag/indice.py` |
| k | 6 | `config.py` |
| LLM | openai/gpt-oss-120b via Groq, reasoning_effort = low (padrão) | `config.py` |
| Temperatura / máx. tokens | 0 / 2000 | `config.py` |
| Prompt | mesmas instruções nas duas condições; só o bloco de trechos muda | `rag/prompt.py` |

## Ver os modelos disponíveis na Groq

A Groq aposenta modelos com frequência. Para listar os que a sua chave pode usar:

```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); from openai import OpenAI; c = OpenAI(api_key=os.environ['GROQ_API_KEY'], base_url='https://api.groq.com/openai/v1'); print('\n'.join(sorted(m.id for m in c.models.list().data)))"
```

Registre no artigo o identificador exato do modelo e as datas das execuções.

## Problemas comuns

- **`Error code: 404 - The model ... does not exist`**: o modelo saiu do ar na Groq.
  Liste os disponíveis (seção acima) e troque o nome em `MODELOS_LLM` no `config.py`.

- **`Activate.ps1 não pode ser carregado`** (Windows): rode
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` uma vez e tente de novo.
- **`KeyError: 'GROQ_API_KEY'`**: o arquivo `.env` não existe ou está sem a chave.
- **`O índice foi criado com 'teste'...`**: você indexou com o embedder de teste;
  rode `python passo3_indexar.py` de novo, sem `--embeddings teste`.
- **Erro 429 / rate limit**: o script espera e tenta de novo sozinho.
- **Acentos estranhos no terminal do Windows**: use o Windows Terminal ou rode `chcp 65001` antes.
