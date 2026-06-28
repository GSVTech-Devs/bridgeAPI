# Manual de Padronização das APIs Downstream — BridgeAPI

> **Para quem refatora uma API para rodar na plataforma Bridge.**
> Este documento define **o contrato obrigatório**, o **schema padrão da consulta de
> débitos**, **como adotar a `bridge-sdk`**, a **dockerização padrão** e um **passo a
> passo de refatoração**. No fim há um **checklist de "pronta para o Bridge"** e um
> **apêndice com notas específicas** das 7 APIs de referência.

Documentos relacionados:
- `REQUISITOS_REFATORACAO_APIS.md` — requisitos/roadmap da plataforma.
- `ESTADO_REFATORACAO_APIS.md` — o que já está pronto na plataforma.
- `bridge-sdk/README.md` — guia da SDK (atenção: a seção de captcha do README está
  desatualizada; o pacote **já exporta** `CaptchaClient`/`CaptchaProvider`, ver §6.6).

---

## Índice

1. [Como a sua API se encaixa no Bridge](#1-como-a-sua-api-se-encaixa-no-bridge)
2. [Decisões de padronização (fixadas)](#2-decisões-de-padronização-fixadas)
3. [Requisitos obrigatórios (resumo)](#3-requisitos-obrigatórios-resumo)
4. [Contrato HTTP padrão](#4-contrato-http-padrão)
5. [Schema padrão da consulta de débitos](#5-schema-padrão-da-consulta-de-débitos)
6. [Adoção da bridge-sdk](#6-adoção-da-bridge-sdk)
7. [Configuração e segredos](#7-configuração-e-segredos)
8. [Dockerização padrão](#8-dockerização-padrão)
9. [Execução, timeouts e idempotência](#9-execução-timeouts-e-idempotência)
10. [Manual de refatoração (passo a passo)](#10-manual-de-refatoração-passo-a-passo)
11. [Checklist "pronta para o Bridge"](#11-checklist-pronta-para-o-bridge)
12. [Apêndice A — notas por API](#apêndice-a--notas-por-api)

---

## 1. Como a sua API se encaixa no Bridge

```
cliente ──POST──▶ Bridge (gateway) ──POST /consultar──▶ SUA API ──▶ proxy/captcha ──▶ alvo (DETRAN/SEFAZ)
                  │  gera correlation_id           │  SDK lê X-Correlation-Id e X-Bridge-Client
                  │  autentica X-Bridge-Key        │  SDK busca proxy/captcha da plataforma
                  │  injeta headers, cobra, loga   │  SDK envia logs/status sob o mesmo cid
                  └──────────────── tudo correlacionado por um único correlation_id ───────────────┘
```

O que **o gateway faz por você** (não reimplemente):
- **Autenticação do cliente** (`X-Bridge-Key`), **rate limit**, **billing** e **request log**.
- **Geração e propagação** do `correlation_id` (header `X-Correlation-Id`).
- **Identificação do cliente** (header `X-Bridge-Client`, com proteção anti-spoof).
- **Execução híbrida**: se sua API demorar além de `sync_timeout_s` (90s), o gateway
  transforma a chamada em **job assíncrono** (`202 + job_id`), com polling/SSE/webhook.
  Sua API **não precisa** implementar jobs (ver §9).

O que **a sua API faz**:
- Expõe **`POST /consultar`** (consulta de débitos) + **`GET /health`** + **`GET /status`**.
- **Valida o token de entrada do gateway** (segredo compartilhado vindo do `.env`) para
  garantir que só a Bridge chama a sua API (ver §4.4).
- Resolve proxy e captcha **pela SDK** (config vinda da plataforma, sem segredo hardcoded).
- Emite **logs estruturados** e **heartbeat de status** pela SDK.
- Devolve dados no **schema padrão** (§5) e erros na **taxonomia padrão** (§6.7).

> **Regra de ouro:** a sua API confia no gateway para **autenticação do cliente, rate limit
> e billing** (não reimplemente nada disso). Mas ela **autentica que o chamador É a Bridge**:
> valida um **token de entrada** (segredo compartilhado no `.env`) em todo endpoint de
> negócio, recusando `401` quem não apresentar o token. Não confunda: o `X-Bridge-Key` do
> cliente é problema do gateway; o token de entrada da Bridge é problema da sua API.

---

## 2. Decisões de padronização (fixadas)

| Tema | Decisão |
|---|---|
| **Framework / runtime** | **Sync e async são igualmente suportados pela SDK.** FastAPI (async) via `install()`; Flask/workers (sync) via `bridge_sdk.integrations.flask.install()` / `SyncBridge`. A escolha **não é default**: cada API é **analisada antes** da refatoração e o runtime é decidido pelos critérios da §2.1. |
| **Endpoint de consulta** | **`POST /consultar` com corpo JSON.** Os GET com path-params (`/debitos/<placa>/<renavam>/<token>`) são **descontinuados**. |
| **Schema de resposta** | **Rígido e canônico** (§5). **Exceções são previstas** e tratadas por mecanismos explícitos (`dados_especificos`, `extra`, endpoints de tipo `documento`). |
| **Captcha** | Solver externo (CapMonster/2Captcha/etc.) **via `CaptchaClient` da SDK**. PoW local, Playwright e cookie-service externo ficam **dentro da API**, mas **reportam status/saldo/erros pela SDK** (§6.6). |
| **Proxy** | **Sempre via `ProxyClient` da SDK.** Zero credencial de proxy hardcoded. |
| **Segredos** | Tudo por variável de ambiente / config da plataforma. **Nenhum segredo no código** (§7). |
| **Docker** | Obrigatório: `Dockerfile` + `docker-compose.yml` com healthcheck no `/health` (§8). |

### 2.1 Analise a API ANTES de refatorar: sync ou async?

**Passo zero, obrigatório.** Antes de escrever qualquer código, analise a API e **decida e
registre** o runtime. A SDK suporta os dois de forma equivalente, então a escolha é técnica,
guiada pela natureza do trabalho, não por preferência.

Itens a levantar na análise: framework atual; bibliotecas de I/O (requests/httpx/navegador);
se há libs **sync-only ou thread-unsafe** (ex.: Playwright sync API); perfil do trabalho
(I/O-bound vs CPU-bound vs browser); volume/concorrência esperada; tamanho e risco de portar.

**Escolha ASYNC (FastAPI + uvicorn) quando:**
- O trabalho é I/O-bound e dá para expressar com `httpx.AsyncClient` (a maioria dos scrapers HTTP).
- Quer alta concorrência num único processo.
- Não depende de lib sync-only. (CPU-bound, como PoW, ainda cabe: rode em executor.)

**Escolha SYNC (Flask + gunicorn, multiprocesso) quando:**
- Usa lib **sync-only / não thread-safe** sem equivalente async (ex.: **Playwright sync**).
- É **automação de navegador** ou trabalho pesado por request, onde **isolamento de processo +
  cap fixo de concorrência (workers) + reciclagem de worker** (memory leak de browser) são
  operacionalmente melhores.
- O código existente é grande, sync e portar para async é alto risco / baixo valor.

Regra prática: scraper HTTP puro → **async**; scraper com **navegador** → **sync**. Em dúvida,
async. **Documente a decisão e o porquê** no README/PR da API antes de codar.

| Runtime | Bootstrap da SDK | Proxy/captcha | Heartbeat/health |
|---|---|---|---|
| **async** (FastAPI) | `logger = install(app, config, checks=...)` (§6.3) | `await proxy_client.with_failover(fn)` / `await proxy_client.acquire()` | automático no lifespan |
| **sync** (Flask/workers) | `bridge = install(app, config, checks=...)` de `integrations.flask`, ou `SyncBridge` (§6.4) | `bridge.proxy.acquire()` / `bridge.proxy.with_failover(fn)` com `fn` **síncrono** | loop de fundo da SDK (automático) |

> **Sobre failover:** na prática quase sempre há **um** proxy/captcha configurado (no máximo
> dois). Então o caminho normal é `acquire()` (pega o único disponível). `with_failover` só
> agrega valor quando há mais de um; não otimize para ele.

---

## 3. Requisitos obrigatórios (resumo)

Uma API só é considerada **"pronta para o Bridge"** quando cumpre **todos**:

1. **Endpoints**: `POST /consultar`, `GET /health` (liveness), `GET /status` (readiness). Ver §4.
2. **Validação do token de entrada do gateway**: todo endpoint de negócio exige um token
   (definido no `.env`) que a Bridge envia; sem ele → `401`. Ver §4.4.
3. **Schema padrão** de request e response na consulta de débitos. Ver §5.
4. **SDK adotada**: correlation_id propagado, logging estruturado com eventos canônicos,
   erros da taxonomia `BridgeError`. Ver §6.
5. **Proxy via SDK** (`ProxyClient`), sem proxy hardcoded. Ver §6.5.
6. **Captcha via SDK quando externo**; casos especiais reportam pela SDK. Ver §6.6.
7. **Heartbeat de status** ligado, com checks de readiness reais (proxy, captcha/saldo,
   alvo alcançável). Ver §6.8.
8. **Zero segredo/credencial hardcoded no código.** O que a Bridge gerencia
   (proxy/captcha) vai para a **plataforma**; **toda outra credencial hardcoded que não
   é editada nem configurada na Bridge vai obrigatoriamente para um `.env`**. Ver §7.
9. **Dockerizada** com healthcheck. Ver §8.
10. **Service token** configurado (`BRIDGE_SERVICE_TOKEN`) e API registrada na plataforma. Ver §6.9.
11. **Testes** mínimos (validação de input, parse do alvo, mapeamento de erros). Ver §10.

---

## 4. Contrato HTTP padrão

### 4.1 Endpoints obrigatórios

| Método | Rota | Para quê | Origem |
|---|---|---|---|
| `POST` | `/consultar` | Consulta de débitos (endpoint de negócio principal) | sua API |
| `GET`  | `/health` | Liveness (processo de pé) — rápido, sem checar deps | **SDK** (`install()`) |
| `GET`  | `/status` | Readiness profundo (consigo atender?) — roda os checks | **SDK** (`install()`) |

### 4.2 Endpoints opcionais (quando o domínio exige)

| Método | Rota | Para quê |
|---|---|---|
| `POST` | `/pagamento` | Emitir boleto/PIX/guia a partir de débitos selecionados (ver §5.5) |
| `POST` | `/documento` | Documento que **não é** consulta de débitos (ex.: CRLV em PDF) — **exceção** ao schema (§5.6) |

> Mantenha **um recurso por endpoint**. Não misture "consultar débitos" com "emitir boleto"
> no mesmo endpoint: o gateway cobra/loga por chamada, então a separação deixa billing e
> debug limpos.

### 4.3 Headers que o gateway envia (a SDK lê por você)

| Header | Significado |
|---|---|
| `X-Correlation-Id` | ID único da cadeia. **Nunca gere o seu**; a SDK lê e injeta em todo log. |
| `X-Bridge-Client` | Conta do cliente. A SDK usa para resolver proxy/captcha do cliente. |
| `Idempotency-Key` | (Quando presente) chave de idempotência tratada pelo gateway. |
| `Authorization` / `X-Api-Key` | **Token de entrada da Bridge** (segredo compartilhado). A sua API **valida** (ver §4.4). |

A resposta **deve** devolver `X-Correlation-Id` (a SDK já faz isso no middleware).

### 4.4 Autenticação de entrada (gateway → sua API) — obrigatória

A sua API fica exposta na rede; sem isso, qualquer um que descobrir a URL consulta de graça
(gastando proxy/captcha/saldo). Por isso **todo endpoint de negócio valida um token de
entrada** que **só a Bridge conhece** e envia em cada request.

**Como funciona (segredo compartilhado):**
- O token fica no **`.env`** da sua API (ex.: `BRIDGE_INBOUND_TOKEN`). A sua API valida cada
  request contra ele.
- O **mesmo valor** é cadastrado na Bridge como a **credencial da API** (campo de chave/
  `master_key` no `/admin/apis`), com um `auth_type`. O gateway então o envia em cada forward:
  - `auth_type=bearer` → header **`Authorization: Bearer <token>`** (recomendado);
  - `auth_type=api_key` → header **`X-Api-Key: <token>`**;
  - `auth_type=basic` → header **`Authorization: Basic <token>`**.
- Escolha **um** mecanismo e valide exatamente ele. Recomendado: **bearer**.

**Regras:**
- Sem token, ou token diferente → responda **`401`** (não vaze detalhe).
- **`GET /health` e `GET /status` ficam de fora** (liveness/readiness precisam ser públicos
  para load balancer e para o coletor da plataforma). Todo o resto exige o token.
- Comparação **constante** (`hmac.compare_digest`) para evitar timing attack.
- Esse token **não é** o `X-Bridge-Key` do cliente (esse é validado pelo gateway) nem o
  `BRIDGE_SERVICE_TOKEN` (esse a sua API **envia** para a plataforma, §6.9). São três coisas
  distintas — ver a tabela em §6.2.

Implementação em §6.10 (FastAPI e Flask).

---

## 5. Schema padrão da consulta de débitos

Esta seção é o coração da padronização. O schema é **rígido** (mesmos nomes de campos,
mesmos tipos, mesma estrutura em todas as APIs), com **mecanismos de exceção explícitos**
para o que não couber.

### 5.1 Request — `POST /consultar`

```json
{
  "placa": "ABC1D23",
  "renavam": "12345678901",
  "documento": "00000000000",
  "opcoes": { "incluir_pagamento": false }
}
```

| Campo | Tipo | Obrig. | Regras |
|---|---|---|---|
| `placa` | string | sim* | 7 caracteres, maiúsculo. Formato antigo `AAA9999` ou Mercosul `AAA9A99`. |
| `renavam` | string | sim | só dígitos; normalizar com `zfill(11)`. |
| `documento` | string | não | CPF (11) ou CNPJ (14); só dígitos. Algumas UFs exigem (ex.: SEFAZ-MT). |
| `opcoes` | object | não | flags específicas; documente as suportadas. Default = consulta simples. |

\* Quando a UF consulta por documento em vez de placa, `placa` pode ser opcional e
`documento` obrigatório. **Documente a regra da sua API**, mas mantenha os nomes de campo.

### 5.2 Response de sucesso (envelope canônico)

```json
{
  "status": "success",
  "correlation_id": "0f8c1a2b-...",
  "fonte": { "uf": "PA", "orgao": "DETRAN", "sistema": "DETRAN-PA Renavam" },
  "veiculo": {
    "placa": "ABC1D23",
    "renavam": "12345678901",
    "chassi": "9BWZZZ...",
    "marca_modelo": "VW/GOL 1.0",
    "ano_fabricacao": "2020",
    "ano_modelo": "2021",
    "cor": "PRATA",
    "especie": "PASSAGEIRO",
    "combustivel": "FLEX",
    "municipio": "BELEM",
    "uf": "PA",
    "proprietario": { "nome": "FULANO DE TAL", "documento": "***" }
  },
  "debitos": [
    {
      "id": "ipva-2025",
      "tipo": "ipva",
      "descricao": "IPVA 2025",
      "exercicio": "2025",
      "vencimento": "2025-05-31",
      "situacao": "em_aberto",
      "valores": {
        "nominal": 1000.00,
        "desconto": 0.00,
        "juros": 12.34,
        "multa": 20.00,
        "taxa": 0.00,
        "atualizado": 1032.34
      },
      "pagamento": {
        "linha_digitavel": "12345.67890 ...",
        "codigo_barras": "8581000001...",
        "pix_copia_cola": "00020101...",
        "parcela": null,
        "validade": "2025-06-30"
      },
      "extra": {}
    }
  ],
  "totais": {
    "quantidade": 1,
    "valor_total": 1032.34,
    "valor_com_desconto": 1032.34
  },
  "dados_especificos": {}
}
```

### 5.3 Dicionário de campos

**`fonte`** — origem do dado.

| Campo | Tipo | Notas |
|---|---|---|
| `uf` | string(2) | UF do órgão. |
| `orgao` | string | `DETRAN`, `SEFAZ`, `SERPRO`, etc. |
| `sistema` | string | nome livre do sistema consultado. |

**`veiculo`** — todos os campos opcionais (a UF pode não fornecer todos), mas **os nomes
são fixos**. Campos sem dado vêm `null`, não omitidos.

| Campo | Tipo |
|---|---|
| `placa`, `renavam`, `chassi` | string \| null |
| `marca_modelo`, `cor`, `especie`, `combustivel` | string \| null |
| `ano_fabricacao`, `ano_modelo` | string \| null |
| `municipio`, `uf` | string \| null |
| `proprietario` | objeto `{nome, documento}` \| null (mascare o documento) |

**`debitos[]`** — lista de débitos. **Cada item** segue:

| Campo | Tipo | Valores / notas |
|---|---|---|
| `id` | string | identificador estável do débito (use o do alvo; senão derive de tipo+exercício). |
| `tipo` | enum | `ipva` \| `licenciamento` \| `multa` \| `taxa` \| `dpvat` \| `seguro` \| `divida_ativa` \| `outro` |
| `descricao` | string | texto humano. |
| `exercicio` | string \| null | ano de referência. |
| `vencimento` | string(date) \| null | ISO `YYYY-MM-DD`. |
| `situacao` | enum | `em_aberto` \| `pago` \| `parcelado` \| `divida_ativa` \| `em_processamento` |
| `valores` | objeto | ver abaixo. |
| `pagamento` | objeto \| null | instrumento de pagamento do débito (quando disponível). |
| `extra` | objeto | **escape hatch por item** para campos específicos da UF. |

**`valores`** — sempre número (float, 2 casas). Use `0.0` quando não houver, **nunca** string.

| Campo | Tipo | Notas |
|---|---|---|
| `nominal` | float | valor base. |
| `desconto` | float | desconto aplicado. |
| `juros` | float | juros. |
| `multa` | float | multa por atraso. |
| `taxa` | float | taxas/encargos. |
| `atualizado` | float | **valor a pagar hoje** (campo que o cliente realmente usa). |

**`pagamento`** — instrumento de pagamento (no item ou em `/pagamento`, ver §5.5).

| Campo | Tipo |
|---|---|
| `linha_digitavel` | string \| null |
| `codigo_barras` | string \| null |
| `pix_copia_cola` | string \| null |
| `pix_qrcode_base64` | string \| null |
| `boleto_pdf_base64` | string \| null |
| `parcela` | string \| null (ex.: `"4/6"`) |
| `validade` | string(date) \| null |

**`totais`** — `quantidade` (int), `valor_total` (float, soma de `atualizado`),
`valor_com_desconto` (float).

### 5.4 Response de erro (envelope canônico)

```json
{
  "status": "error",
  "correlation_id": "0f8c1a2b-...",
  "erro": {
    "error_code": "TARGET_TIMEOUT",
    "message": "O DETRAN-PA não respondeu no tempo.",
    "detalhe": null
  }
}
```

`error_code` vem da taxonomia da SDK (§6.7). O HTTP status segue o sugerido pela classe
do erro. **Sempre** inclua `correlation_id`.

### 5.5 Pagamento (boleto/PIX/guia) — `POST /pagamento`

Quando a emissão é um passo separado da consulta (caso comum: SEFAZ-MT com parcelamento):

```json
// request
{
  "placa": "ABC1D23",
  "renavam": "12345678901",
  "documento": "00000000000",
  "selecao": ["ipva-2025", "licenciamento-2025"]
}
// response: mesmo envelope, com os débitos selecionados preenchendo `pagamento`
{
  "status": "success",
  "correlation_id": "...",
  "veiculo": { ... },
  "debitos": [ { "id": "ipva-2025", "situacao": "parcelado",
                 "pagamento": { "pix_copia_cola": "...", "codigo_barras": "...", "parcela": "4/6" },
                 "extra": {} } ],
  "totais": { ... },
  "dados_especificos": {
    "opcoes_parcelamento": [
      { "selecao": "ipva-2025:cota", "descricao": "Cota única", "total": 980.00 },
      { "selecao": "ipva-2025:4/6", "descricao": "Parcela 4/6", "vencimento": "2026-07-31", "total": 154.19 }
    ]
  }
}
```

### 5.6 Exceções ao schema (mecanismos explícitos)

O schema é rígido, mas a realidade dos dados não é uniforme. **Use exatamente estes três
mecanismos** para o que não couber — não invente campos top-level novos:

1. **`debitos[].extra` (objeto)** — campos específicos de **um débito** (ex.: `orgao_autuador`
   de uma multa, `cota_parcelamento`, `inscricao_divida_ativa`). É o lugar padrão para o
   detalhe que só aquela UF tem.

2. **`dados_especificos` (objeto, top-level)** — informação que **não é um débito**, mas
   acompanha a consulta: opções de parcelamento, links de negociação de dívida ativa,
   avisos do portal, históricos (autuações, recursos, impedimentos, recall). Exemplo
   (DETRAN-MT, que tem muitos blocos): `historico_autuacoes`, `recursos_infracao`,
   `ultimo_processo`, `recall`, `historico_impedimentos` vão aqui.

3. **Endpoint de tipo `documento`** — recursos que **não são consulta de débitos**
   (ex.: **CRLV em PDF** do `docmt`/`detranmt`). Não force no envelope de débitos; exponha
   `POST /documento` com:
   ```json
   // request
   { "placa": "ABC1D23", "renavam": "12345678901", "tipo": "crlv" }
   // response
   { "status": "success", "correlation_id": "...",
     "documento": { "tipo": "crlv", "mime": "application/pdf", "conteudo_base64": "JVBERi0..." } }
   ```

> **Regra:** se você precisar de um campo que não está no schema, ele vai para `extra`
> (por débito) ou `dados_especificos` (por consulta). Top-level só muda com revisão do
> contrato neste documento.

### 5.7 Models de referência (Pydantic) — cole na sua API

```python
# bridge_contract.py — modelos canônicos compartilhados pelas APIs downstream.
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ConsultaRequest(BaseModel):
    placa: Optional[str] = None
    renavam: str
    documento: Optional[str] = None
    opcoes: dict[str, Any] = Field(default_factory=dict)


class TipoDebito(str, Enum):
    ipva = "ipva"; licenciamento = "licenciamento"; multa = "multa"
    taxa = "taxa"; dpvat = "dpvat"; seguro = "seguro"
    divida_ativa = "divida_ativa"; outro = "outro"


class Situacao(str, Enum):
    em_aberto = "em_aberto"; pago = "pago"; parcelado = "parcelado"
    divida_ativa = "divida_ativa"; em_processamento = "em_processamento"


class Valores(BaseModel):
    nominal: float = 0.0; desconto: float = 0.0; juros: float = 0.0
    multa: float = 0.0; taxa: float = 0.0; atualizado: float = 0.0


class Pagamento(BaseModel):
    linha_digitavel: Optional[str] = None
    codigo_barras: Optional[str] = None
    pix_copia_cola: Optional[str] = None
    pix_qrcode_base64: Optional[str] = None
    boleto_pdf_base64: Optional[str] = None
    parcela: Optional[str] = None
    validade: Optional[str] = None


class Debito(BaseModel):
    id: str
    tipo: TipoDebito
    descricao: str
    exercicio: Optional[str] = None
    vencimento: Optional[str] = None
    situacao: Situacao = Situacao.em_aberto
    valores: Valores = Field(default_factory=Valores)
    pagamento: Optional[Pagamento] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Veiculo(BaseModel):
    placa: Optional[str] = None; renavam: Optional[str] = None
    chassi: Optional[str] = None; marca_modelo: Optional[str] = None
    ano_fabricacao: Optional[str] = None; ano_modelo: Optional[str] = None
    cor: Optional[str] = None; especie: Optional[str] = None
    combustivel: Optional[str] = None; municipio: Optional[str] = None
    uf: Optional[str] = None; proprietario: Optional[dict[str, Any]] = None


class Fonte(BaseModel):
    uf: str; orgao: str; sistema: str


class Totais(BaseModel):
    quantidade: int = 0; valor_total: float = 0.0; valor_com_desconto: float = 0.0


class ConsultaResponse(BaseModel):
    status: str = "success"
    correlation_id: str
    fonte: Fonte
    veiculo: Veiculo
    debitos: list[Debito] = Field(default_factory=list)
    totais: Totais = Field(default_factory=Totais)
    dados_especificos: dict[str, Any] = Field(default_factory=dict)


class Erro(BaseModel):
    error_code: str; message: str; detalhe: Optional[Any] = None


class ErroResponse(BaseModel):
    status: str = "error"
    correlation_id: str
    erro: Erro
```

---

## 6. Adoção da bridge-sdk

### 6.1 Instalação

```bash
# FastAPI (recomendado):
pip install "bridge-sdk[fastapi]"
# núcleo (workers/Flask):
pip install bridge-sdk
# em desenvolvimento, do diretório do monorepo:
pip install -e "../bridgeAPI/bridge-sdk[fastapi]"
```

### 6.2 Configuração da SDK (env)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `BRIDGE_PLATFORM_URL` | sim | base da Bridge, ex.: `https://bridge.example.com` |
| `BRIDGE_SERVICE_TOKEN` | sim | token de serviço da API (`brgsvc_...`), ver §6.9 |
| `BRIDGE_INBOUND_TOKEN` | sim | token que o gateway envia e a sua API **valida** (§4.4) |
| `BRIDGE_API_VERSION` | não | versão da sua API (carimbada em cada log) |

```python
from bridge_sdk import SDKConfig
config = SDKConfig.from_env(api_version="2.3.1")
```

**Três tokens, não confunda:**

| Token | Direção | Quem valida | Onde fica na sua API |
|---|---|---|---|
| `X-Bridge-Key` (chave do cliente) | cliente → gateway | **o gateway** | não é problema da sua API |
| `BRIDGE_INBOUND_TOKEN` (entrada) | gateway → **sua API** | **a sua API** (§4.4) | `.env` (e cadastrado na Bridge como chave da API) |
| `BRIDGE_SERVICE_TOKEN` (serviço) | sua API → plataforma | a plataforma | `.env` (a sua API o **envia** nos logs/status/proxy/captcha) |

### 6.3 Bootstrap FastAPI (caminho automático)

`install()` registra o middleware de `correlation_id` + `X-Bridge-Client`, liga o logger e
o heartbeat de status no lifespan, e expõe `/health` e `/status`.

```python
from fastapi import FastAPI, Request
from bridge_sdk import SDKConfig, ProxyClient, CaptchaClient, events, errors
from bridge_sdk.integrations.fastapi import install
from bridge_contract import ConsultaRequest, ConsultaResponse
from bridge_sdk import context

app = FastAPI()
config = SDKConfig.from_env(api_version="2.3.1")

# checks de readiness reais (ver §6.8):
logger = install(app, config, checks={
    "captcha": check_captcha_balance,
    "alvo": check_target_reachable,
})

proxy_client = ProxyClient(config, logger=logger)
captcha_client = CaptchaClient(config, logger=logger)


@app.post("/consultar", response_model=ConsultaResponse)
async def consultar(req: ConsultaRequest):
    logger.info(events.REQUEST_RECEIVED, "consulta recebida", placa=req.placa)
    # ... lógica: proxy_client.with_failover(...), captcha_client.with_failover(...) ...
    logger.info(events.REQUEST_COMPLETED, "ok", duration_ms=812.4)
    return montar_resposta(...)  # ConsultaResponse com correlation_id=context.get_correlation_id()
```

### 6.4 Bootstrap Flask (caminho sync — suportado)

A SDK tem um `install()` para Flask (extra `bridge-sdk[flask]`). Ele cria um **`SyncBridge`**
(que roda um event loop num thread de fundo: flusher de log + heartbeat de status), liga o
`correlation_id`/`X-Bridge-Client` por request, e expõe `/health` e `/status`. Você **não**
escreve event loop nenhum.

```python
from flask import Flask
from bridge_sdk import SDKConfig, events
from bridge_sdk.integrations.flask import install

app = Flask(__name__)
config = SDKConfig.from_env(api_version="2.3.1")

# cria o SyncBridge, inicia logger+heartbeat, registra /health e /status:
bridge = install(app, config, checks={
    "captcha": check_captcha_balance,   # checks sync ou async; sync roda em executor
    "alvo": check_target_reachable,
})

@app.post("/consultar")
def consultar():
    bridge.logger.info(events.REQUEST_RECEIVED, "consulta recebida")
    proxy = bridge.proxy.acquire()                      # SÍNCRONO (1 proxy = caminho comum)
    # ... seu scraping sync usando proxy.url (requests/httpx.Client/Playwright sync) ...
    bridge.logger.info(events.REQUEST_COMPLETED, "ok", duration_ms=812.4)
    return montar_resposta(...)

# no encerramento do processo (drena os logs):
import atexit; atexit.register(bridge.close)
```

- `bridge.logger` — mesmo `BridgeLogger`; `log()` é não-bloqueante, chamável de qualquer
  worker thread.
- `bridge.proxy` / `bridge.captcha` — fachadas **sync**: `acquire()`, `report_failure()`,
  e `with_failover(fn)` com `fn` **síncrono** (o seu scraping roda no thread do worker e pode
  bloquear; só a I/O interna da SDK vai para o loop de fundo).
- `bridge.register_check(nome, fn)` e `bridge.status_report()` (usado pela rota `/status`).
- Heartbeat de status: **automático** (roda no loop de fundo). Não precisa fazer mais nada.

> **Workers/sem Flask:** use `SyncBridge` direto (`bridge = SyncBridge(config, checks=...);
> bridge.start(); ...; bridge.close()`).

> **Flask com Playwright (caso `detranmtsefaz`):** rode em `gunicorn` multiprocesso
> (um navegador por worker, `--max-requests` para reciclar e conter vazamento de memória). O
> Playwright sync roda no thread do worker; a SDK roda no seu próprio thread de fundo, sem
> conflito.

### 6.5 Proxy (sempre via SDK)

Remova **todo** proxy hardcoded. O `ProxyClient` busca o proxy que a plataforma atribuiu à
sua API (e ao cliente, via `X-Bridge-Client`), seleciona por prioridade e reporta falhas —
**trocar proxy na plataforma reflete sem deploy**. Como quase sempre há **um** proxy, o caminho
normal é `acquire()`; `with_failover` só importa com mais de um.

**Async (FastAPI):**
```python
import httpx
from bridge_sdk import errors, events

proxy = await proxy_client.acquire()                 # caminho comum (1 proxy)
if proxy is None:
    raise errors.ProxyUnavailable("sem proxy configurado")
async with httpx.AsyncClient(proxy=proxy.url, verify=False, timeout=30) as http:
    r = await http.get(alvo)
    if r.status_code == 407:
        await proxy_client.report_failure(proxy, error_code="PROXY_AUTH_FAILED")
        raise errors.ProxyAuthFailed("login do proxy recusado")
# com mais de um proxy: resp = await proxy_client.with_failover(async_fn)
```

**Sync (Flask/workers):** use `bridge.proxy`, com `fn` síncrono:
```python
proxy = bridge.proxy.acquire()
if proxy is None:
    raise errors.ProxyUnavailable("sem proxy configurado")
with httpx.Client(proxy=proxy.url, verify=False, timeout=30) as http:   # ou requests
    r = http.get(alvo)
    if r.status_code == 407:
        bridge.proxy.report_failure(proxy, error_code="PROXY_AUTH_FAILED")
        raise errors.ProxyAuthFailed("login recusado")
# com mais de um proxy: resp = bridge.proxy.with_failover(fn_sync)
```

> `proxy.url` já vem com credenciais URL-encoded. **Não** chame `asyncio.run(...)` por request:
> no sync, use as fachadas `bridge.proxy` (elas marshalam para o loop de fundo da SDK).

### 6.6 Captcha

**Caso 1 — solver externo (CapMonster, 2Captcha, AntiCaptcha, CapSolver):** use o
`CaptchaClient`. Ele busca os provedores da plataforma, **pula os sem saldo**, faz failover
e reporta falha/saldo (alimenta o monitoramento e os alertas de saldo baixo).

```python
async def solve(provider):  # provider.api_key, provider.name, provider.provider
    token = await chamar_solver(provider, sitekey=SITEKEY, url=PAGEURL)
    if not token:
        raise errors.CaptchaFailed("solver não resolveu")
    logger.info(events.CAPTCHA_SOLVED, captcha_provider=provider.name)
    return token

provider = await captcha_client.acquire()           # caminho comum (1 provedor com saldo)
if provider is None:
    raise errors.CaptchaBalanceExhausted("sem provedor com saldo")
token = await solve(provider)
# com mais de um provedor: token = await captcha_client.with_failover(solve)
```

**Sync (Flask/workers):** idêntico via `bridge.captcha` com `solve` síncrono:
`provider = bridge.captcha.acquire()`; `bridge.captcha.report_failure(provider, balance_usd=...)`;
`bridge.captcha.with_failover(solve_sync)`.

A API key **não fica no seu código** — vem de `provider.api_key` (config da plataforma).
Após gastar, informe o saldo de volta no `report_failure(..., balance_usd=...)` quando souber.

**Caso 2 — captcha não é um solver externo:** mantenha a lógica **dentro da sua API**, mas
**reporte pela SDK**:
- **PoW local (mCaptcha, `DETRANPA`):** resolva localmente como hoje, mas **logue** os
  eventos canônicos (`CAPTCHA_REQUESTED`/`CAPTCHA_SOLVED`/`CAPTCHA_FAILED` com `duration_ms`)
  e exponha um **check de readiness** (ex.: a instância mCaptcha está respondendo?).
- **Playwright/Turnstile no navegador (`detranmtsefaz`):** idem — se você usa CapMonster
  por trás do Playwright, **mova a chave para o `CaptchaClient`**; se é resolução no
  browser, logue os eventos e exponha o check.
- **Cookie-service externo (`detranrs`):** trate como dependência — logue
  `CAPTCHA_REQUESTED`/`CAPTCHA_FAILED`, exponha check de readiness do serviço, e em falha
  levante `errors.CaptchaFailed` / `errors.TargetBlocked` conforme o caso.

> Objetivo do Caso 2: mesmo sem usar o `CaptchaClient`, o painel `/admin/status` e os
> alertas enxergam o captcha da sua API (saúde, falhas e, quando aplicável, saldo).

### 6.7 Erros padronizados

Levante a subclasse de `BridgeError` certa; o gateway mapeia `error_code` → HTTP + mensagem.

| Classe | `error_code` | HTTP | Quando |
|---|---|---|---|
| `ProxyAuthFailed` | `PROXY_AUTH_FAILED` | 502 | login do proxy falhou |
| `ProxyUnavailable` | `PROXY_UNAVAILABLE` | 503 | nenhum proxy disponível |
| `CaptchaFailed` | `CAPTCHA_FAILED` | 502 | solver não resolveu |
| `CaptchaBalanceExhausted` | `CAPTCHA_BALANCE_EXHAUSTED` | 503 | sem saldo |
| `TargetBlocked` | `TARGET_BLOCKED` | 502 | alvo bloqueou (403/captcha wall) |
| `TargetTimeout` | `TARGET_TIMEOUT` | 504 | alvo não respondeu |
| `InvalidQuery` | `INVALID_QUERY` | 400 | placa/renavam/documento inválidos |

Handler único (FastAPI) que devolve o envelope de erro (§5.4):

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from bridge_sdk import BridgeError, context

@app.exception_handler(BridgeError)
async def bridge_error_handler(request: Request, exc: BridgeError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"status": "error", "correlation_id": context.get_correlation_id() or "",
                 "erro": {"error_code": exc.error_code, "message": exc.message, "detalhe": None}},
    )
```

> "Veículo não encontrado", "acesso negado pelo portal" etc. **não** são `BridgeError` —
> são respostas de negócio. Devolva `200` com `debitos: []` e o aviso em
> `dados_especificos`, **ou** `InvalidQuery` (400) se a entrada é que está errada. Escolha
> e documente; não vaze um `500` opaco.

### 6.8 Checks de readiness (`/status`)

Cada check devolve `{"status": "healthy|degraded|down", ...campos}`. Exceção vira `down`.
`/status` agrega o pior. Registre **pelo menos**: proxy, captcha/saldo (quando houver),
alvo alcançável. **Checks podem ser sync ou async** — a SDK roda checks síncronos num executor,
então um check que bloqueia (ex.: `httpx.Client` ao alvo) não trava o loop, nos dois runtimes.
No sync, os checks vão em `install(..., checks=...)`/`bridge.register_check(...)` e a rota
`/status` (auto-registrada) chama `bridge.status_report()`.

```python
async def check_captcha_balance():
    # com CaptchaClient:
    provs = await captcha_client.get_providers()
    saldo = min([p.balance_usd for p in provs if p.balance_usd is not None], default=None)
    if saldo is None:
        return {"status": "healthy"}
    return {"status": "degraded" if saldo < 5 else "healthy", "balance_usd": saldo}

async def check_target_reachable():
    try:
        async with httpx.AsyncClient(timeout=5) as h:
            r = await h.get(HEALTHCHECK_URL_DO_ALVO)
        return {"status": "healthy", "latency_ms": r.elapsed.total_seconds() * 1000}
    except Exception as e:
        return {"status": "down", "error": str(e)}
```

### 6.9 Service token e registro na plataforma

1. Um **admin** gera o token: `POST /ingest/apis/{api_id}/token` → `brgsvc_...` (mostrado uma vez).
2. Guarde como `BRIDGE_SERVICE_TOKEN` (segredo, env). É **diferente** da chave de cliente.
3. Cadastre a API no `/admin/apis` apontando a `base_url` para a sua API, com
   `request_method=POST` e `request_body_template` renderizando `{query}`/`{token}` se
   necessário. Ligue `uses_proxy`/`uses_captcha` conforme o caso.
4. **Token de entrada (§4.4):** gere um segredo forte, coloque-o no `.env` da sua API como
   `BRIDGE_INBOUND_TOKEN` **e** cadastre o **mesmo valor** como a chave da API no
   `/admin/apis` (campo de credencial/`master_key`), com `auth_type=bearer` (recomendado).
   O gateway passa a enviá-lo em cada forward; a sua API valida (§6.10).

### 6.10 Validação do token de entrada (implementação)

**FastAPI** — uma dependency aplicada aos endpoints de negócio (não ao `/health`/`/status`):

```python
import hmac, os
from fastapi import Depends, Header, HTTPException

INBOUND_TOKEN = os.environ["BRIDGE_INBOUND_TOKEN"]

def require_bridge_token(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {INBOUND_TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="unauthorized")

@app.post("/consultar", response_model=ConsultaResponse,
          dependencies=[Depends(require_bridge_token)])
async def consultar(req: ConsultaRequest):
    ...
```

**Flask** — cheque no `before_request`, liberando os endpoints públicos:

```python
import hmac, os
from flask import request, jsonify

INBOUND_TOKEN = os.environ["BRIDGE_INBOUND_TOKEN"]
PUBLIC = {"/health", "/status"}

@app.before_request
def _require_bridge_token():
    if request.path in PUBLIC:
        return None
    expected = f"Bearer {INBOUND_TOKEN}"
    auth = request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth, expected):
        return jsonify({"erro": "unauthorized"}), 401
```

> Use `api_key` (`X-Api-Key`) em vez de `bearer` se preferir — só mantenha o `auth_type`
> cadastrado na Bridge igual ao header que você valida.

---

## 7. Configuração e segredos

**Regra absoluta: nenhum segredo no código.** As 7 APIs de referência hoje violam isso
(proxy BrightData/SOAX/pyproxy hardcoded, chaves CapMonster/2Captcha em `.env`/código,
`SECRET_KEY="GSVTECH"`, credenciais OAuth de DETRAN no `auth_manager.py`).

**Regra de decisão (obrigatória) — para onde vai cada credencial hardcoded:**

> A Bridge gerencia **proxy e captcha**: essas credenciais saem do código e passam a ser
> **configuradas/editadas na plataforma** (via `ProxyClient`/`CaptchaClient`).
> **Toda outra credencial ou segredo hoje hardcoded — que NÃO é editado nem configurado
> na Bridge — vai obrigatoriamente para um `.env`** (lido por variável de ambiente, nunca
> de volta para o código). Não há terceira opção: ou é gerenciado pela plataforma, ou está
> num `.env`. Nada de credencial literal no fonte.

Exemplos do que cai na regra do `.env` (não é gerenciado pela Bridge): credenciais de
**login no alvo** (OAuth/usuário/senha do DETRAN, ex.: `detrandf`), `SECRET_KEY` da app,
chaves de serviços externos próprios da API (ex.: cookie-service do `detranrs`),
`sitekey`/`pageurl` de captcha, URL base do alvo, tokens de terceiros. Se algum dia esse
valor passar a ser configurável na Bridge, ele migra para a plataforma; até lá, **`.env`**.

| O que era hardcoded | Para onde vai |
|---|---|
| URL/credencial de **proxy** | **Plataforma** (via `ProxyClient`). Remova do código. |
| Chave de **captcha solver** | **Plataforma** (via `CaptchaClient`, `provider.api_key`). |
| URL do **alvo** (DETRAN/SEFAZ) | env (`TARGET_BASE_URL`) — não é segredo, mas não hardcode. |
| `sitekey`/`pageurl` do captcha | env. |
| **Credenciais de login** no alvo (ex.: OAuth do `detrandf`) | env (`TARGET_USERNAME`/`TARGET_PASSWORD`/...). **Nunca** no código. |
| **Token de entrada do gateway** (§4.4) | env (`BRIDGE_INBOUND_TOKEN`) + mesmo valor cadastrado como chave da API na Bridge. |
| `BRIDGE_*` | env. |

Use `.env` **apenas em dev** (não commitado) e variáveis de ambiente reais em produção
(via `docker-compose` / orquestrador). Commit um `.env.example` sem valores.

---

## 8. Dockerização padrão

Toda API roda em Docker. Padrão FastAPI:

**`Dockerfile`**
```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Dependências de sistema conforme a API (ex.: PDF/barcode/Playwright):
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     libzbar0 poppler-utils libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`docker-compose.yml`**
```yaml
services:
  api:
    build: .
    container_name: detranXX-api
    restart: unless-stopped
    env_file: .env          # BRIDGE_PLATFORM_URL, BRIDGE_SERVICE_TOKEN, BRIDGE_INBOUND_TOKEN, TARGET_*, etc.
    ports:
      - "${PORT:-8000}:8000"
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else sys.exit(1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

Notas por tecnologia:
- **Playwright (`detranmtsefaz`):** use a imagem base `mcr.microsoft.com/playwright/python`
  ou instale os browsers (`playwright install --with-deps chromium`) no Dockerfile.
- **PDF/barcode (`detrandf`, `detranmt`, `radar`):** inclua `libzbar0`, `poppler-utils`,
  `libgl1`, `libglib2.0-0` (linhas comentadas no Dockerfile acima).
- **Flask sync:** troque o `CMD` por `gunicorn -k gthread -w 4 -t 240 -b 0.0.0.0:8000 app:app`.

---

## 9. Execução, timeouts e idempotência

- **Não implemente jobs.** O gateway corre sua resposta contra `sync_timeout_s` (90s).
  Dentro do limite → `200` normal. Excedeu → o gateway devolve `202 + job_id` ao cliente e
  finaliza em background. **Sua API só precisa responder** (rápido ou demorado).
- **Timeout interno:** configure o seu HTTP client do alvo abaixo do `upstream_timeout_s`
  (300s) da plataforma. Em estouro, levante `errors.TargetTimeout`.
- **Idempotência:** quando o gateway manda `Idempotency-Key`, a deduplicação é dele. Sua
  API deve ser **segura para repetir** (uma consulta repetida não pode causar efeito
  colateral). Consulta de débitos é naturalmente idempotente; emissão de guia, cuide para
  não duplicar.
- **Concorrência:** dimensione workers (`gunicorn -w`, ou uvicorn workers) sabendo que cada
  request pode segurar proxy+captcha por dezenas de segundos.

---

## 10. Manual de refatoração (passo a passo)

Siga nesta ordem para converter uma API existente. Faça por etapas, testando a cada uma.

1. **Inventário + decisão de runtime (passo zero).** Liste: framework, endpoints atuais, onde
   está o proxy, qual captcha, segredos hardcoded, formato de resposta atual, libs sync-only e
   perfil do trabalho. **Decida sync ou async pelos critérios da §2.1 e registre o porquê.**
   (Use o Apêndice A se for uma das 7.)
2. **Esqueleto novo.** Crie o `app` no runtime escolhido (FastAPI ou Flask). Adicione
   `bridge-sdk` ao `requirements.txt` (vendorizado ou pacote).
3. **Ligue a SDK.** `SDKConfig.from_env(...)` + `install(app, config, checks=...)`: de
   `integrations.fastapi` (async) ou `integrations.flask` (sync, retorna o `SyncBridge`).
   Confirme `/health` e `/status` respondendo.
4. **Valide o token de entrada (§4.4/§6.10).** Exija `BRIDGE_INBOUND_TOKEN` nos endpoints de
   negócio (deixe `/health` e `/status` públicos); cadastre o **mesmo valor** como chave da
   API na Bridge (`auth_type=bearer`). Confirme que sem token responde `401`.
5. **Migre o endpoint para `POST /consultar`** com `ConsultaRequest` (§5.7). Mantenha a
   lógica de scraping/consulta, mas **chame por dentro** os clientes da SDK.
6. **Proxy → SDK.** Remova o proxy hardcoded; use `proxy_client.with_failover(...)` (§6.5).
7. **Captcha → SDK (ou reporte).** Mova chave de solver para `CaptchaClient` (§6.6, caso 1),
   ou logue/checke o captcha especial (caso 2).
8. **Mapeie a resposta para o schema canônico** (§5). Veículo, débitos, valores numéricos,
   pagamento. O que não couber: `extra` / `dados_especificos`. CRLV/PDF: `POST /documento`.
9. **Erros → taxonomia.** Troque `502/500` opacos por `BridgeError` (§6.7) + handler do envelope.
10. **Logs → eventos canônicos.** Substitua `print`/`logging` ad-hoc por
    `logger.info(events.X, ...)` nos pontos do ciclo de vida.
11. **Segredos → env.** Zere hardcodes; crie `.env.example` (§7).
12. **Docker.** Adicione `Dockerfile` + `docker-compose.yml` com healthcheck (§8).
13. **Testes (Docker).** Crie testes unitários: validação de input (`InvalidQuery`), **token de
    entrada (401 sem token)**, parse do alvo → schema, mapeamento de erro → `error_code`. Rode
    **dentro do container** (padrão do ambiente, não use `py_compile`).
14. **Registre na plataforma.** Gere o service token, cadastre a API (com a chave de entrada),
    ligue `uses_proxy`/`uses_captcha`, configure proxies/captchas dela no `/admin/apis`.
15. **Verificação e2e.** Dispare uma consulta pelo gateway e recupere a timeline por
    `correlation_id` em `/admin/debug`; confirme status em tempo real no `/admin/status`.

---

## 11. Checklist "pronta para o Bridge"

Copie para a PR de cada API:

```
[ ] Runtime (sync/async) analisado e decidido pelos critérios da §2.1, com o porquê documentado
[ ] POST /consultar com ConsultaRequest (placa/renavam/documento/opcoes)
[ ] GET /health e GET /status respondendo (SDK, públicos)
[ ] Token de entrada validado nos endpoints de negócio (401 sem token); /health e /status livres
[ ] Resposta no schema canônico (veiculo, debitos[], valores numéricos, totais)
[ ] Exceções via extra / dados_especificos / POST /documento (nada de campo top-level novo)
[ ] correlation_id propagado (header devolvido na resposta)
[ ] Logs com events.* canônicos (request.received ... request.completed)
[ ] Proxy 100% via ProxyClient (zero proxy hardcoded)
[ ] Captcha externo via CaptchaClient; captcha especial reportando pela SDK
[ ] Heartbeat de status ligado + checks reais (proxy, captcha/saldo, alvo)
[ ] Erros via BridgeError + handler do envelope de erro
[ ] Zero credencial hardcoded: proxy/captcha na plataforma; todo o resto em .env (.env.example commitado)
[ ] Dockerfile + docker-compose.yml com healthcheck no /health
[ ] BRIDGE_PLATFORM_URL / BRIDGE_SERVICE_TOKEN / BRIDGE_INBOUND_TOKEN / BRIDGE_API_VERSION configurados
[ ] Testes (validação, parse, erros) rodando no container
[ ] API registrada no /admin/apis; e2e verificado por correlation_id
```

---

## Apêndice A — notas por API

Diagnóstico do estado atual e o que muda em cada uma. (Frameworks, segredos e endpoints
levantados na análise inicial.)

### A.1 `DETRANPA` (`~/trabalho/DETRANPA`)
- **Hoje:** Flask + gunicorn (`gthread`, timeout 240s). Endpoints `POST /licenciamento` e
  `POST /infracoes` (já são POST — bom). Proxy BrightData **hardcoded** em `conf.py`.
  Captcha **mCaptcha PoW local** (sem solver externo). `SECRET_KEY="GSVTECH"`. Sem Docker.
- **Muda:** unificar em **`POST /consultar`** (tipo via `opcoes` ou manter `/infracoes` como
  `tipo=multa`); mapear `cobrancas[]`/`infracoes[]` → `debitos[]` (boleto → `pagamento`);
  proxy → `ProxyClient`; **captcha PoW = caso 2** (logar eventos + check de readiness da
  instância mCaptcha); remover segredos; **adicionar Docker**. Pode ficar em Flask, mas é
  forte candidata a FastAPI por já ser stateless.

### A.2 `detrandf` (`~/trabalho/api/detrandf`)
- **Hoje:** Flask (dev server, `debug=True`). Endpoints **GET com path-params**
  (`/completa/<placa>/<renavam>/<token>`, etc.). Proxy BrightData/SOAX **hardcoded**
  (duas linhas, uma sobrescreve a outra). **Sem captcha** (usa **OAuth** no alvo via
  `auth_manager.py`, com **CPF/senha/secret hardcoded** + Redis). Tem Docker + Redis.
  Faz boleto com parse de PDF (pdfplumber/pyzbar).
- **Muda:** migrar para **`POST /consultar`** (corpo JSON); `debitos_atuais/anteriores/
  licenciamento` → `debitos[]` com `tipo`/`exercicio`; manter o paralelismo (ThreadPool)
  ou virar async; **credenciais OAuth → env** (crítico); proxy → `ProxyClient`; boleto →
  `POST /pagamento`; sair do `debug=True`/dev server (gunicorn). Sem captcha solver →
  `CaptchaClient` não se aplica; OAuth é dependência (check de readiness do token).

### A.3 `detranmt` (`~/trabalho/api/detranmt`)
- **Hoje:** Flask (`debug=True`, port 5011). **GET path-params**. Proxy BrightData via env
  (bom). Captcha **CapMonster Turnstile** (chave em `.env`). Muitos blocos extras
  (histórico de autuações, recursos, recall, impedimentos). Sem Docker. CORS `*`.
- **Muda:** **`POST /consultar`**; `debitos[]`+`multas[]` → `debitos[]` (multa = `tipo=multa`);
  os blocos de histórico → **`dados_especificos`**; CRLV (PDF) → **`POST /documento`**;
  boletos → `POST /pagamento`; captcha CapMonster → **`CaptchaClient`** (chave sai do `.env`,
  vai para a plataforma); adicionar Docker; tirar `debug=True`.

### A.4 `detranmtsefaz` (`~/trabalho/api/detranmtsefaz`)
- **Hoje:** Flask + **Playwright (sync)**, port 8044. Já é **POST JSON** (`/ipva/...`).
  Captcha **CapMonster Turnstile hardcoded no código** (crítico). **Parcelamento** (cotas
  1/6…6/6), **PIX+código de barras**, **dívida ativa** (link de negociação). Log já é
  JSON-ish (`print`). Sem Docker.
- **Muda:** `POST /ipva/...` → **`POST /consultar`** (IPVA) + **`POST /pagamento`** (emissão);
  `anos_referencia[].lancamentos[]` → `debitos[]` (`tipo=ipva`, `situacao=parcelado/
  divida_ativa`); **opções de parcelamento** e **links de dívida ativa** →
  `dados_especificos`; PIX/barcode → `pagamento`; **chave CapMonster → `CaptchaClient`**
  (mesmo atrás do Playwright); **Docker com Playwright** (imagem base com browsers);
  trocar `print` por `logger` + eventos. Fica em Flask sync (Playwright), gunicorn `gthread`.

### A.5 `detranrs` (`~/trabalho/api/detranrs`)
- **Hoje:** Flask (`debug=True`, port 5013). **GET path-params**. Proxy BrightData
  **hardcoded**. **Sem captcha próprio** — depende de **cookie-service externo** num IP
  hardcoded (`52.21.240.32:30000`). Tem `/debitos`, `/veiculo`, `/pix/*`, `/consulta-completa`.
- **Muda:** **`POST /consultar`** (consolidar `/debitos`/`/veiculo`/`simples` no envelope:
  débitos em `debitos[]`, dados do veículo em `veiculo`, simplificada em `dados_especificos`);
  `/pix/*` → `POST /pagamento`; proxy → `ProxyClient`; **cookie-service = caso 2 de captcha**
  (URL → env, logar `CAPTCHA_REQUESTED/FAILED`, check de readiness do serviço, `TargetBlocked`/
  `CaptchaFailed` em falha); adicionar Docker; tirar `debug=True`.

### A.6 `radar` (`~/trabalho/api/radar`)
- **Hoje:** **FastAPI + uvicorn** (já no padrão!), Docker + healthcheck, logging com
  request_id, auth por token próprio, **POST JSON**. Captcha **CapMonster/2Captcha HCaptcha**
  (chaves em `.env`). Sem proxy (chamada direta ao Serpro). Endpoints
  `/consulta`/`/pix`/`/boleto`/`/completo`.
- **Muda (menor esforço):** renomear `/consulta` → **`/consultar`** com `ConsultaRequest`;
  `multas[]` → `debitos[]` (`tipo=multa`); `/pix`+`/boleto` → `POST /pagamento` (PDF →
  `pagamento.boleto_pdf_base64`); **trocar auth próprio pelo modelo do gateway** (remover
  `require_api_token`/Swagger basic, confiar no gateway); captcha → **`CaptchaClient`**
  (chaves saem do `.env`); trocar o logger atual pelo **`BridgeLogger`**+`install()` (ganha
  correlation_id e heartbeat); proxy via `ProxyClient` **se** a plataforma exigir.
  **Referência boa de ponto de partida** para as outras.

### A.7 `docmt` (`~/trabalho/api/docmt`)
- **Hoje:** Flask (port 5000). Endpoint único **GET** `/CRLV/MT/<placa>/<renavam>/<token>`
  que retorna **PDF em base64**. Proxy pyproxy **hardcoded** (placeholder
  `# Substituir com o proxy real`). Sem captcha. Log em arquivo. Sem Docker.
- **Muda:** **não** é consulta de débitos — é **documento**. Exponha **`POST /documento`**
  (`tipo="crlv"`) com `{documento:{tipo, mime, conteudo_base64}}` (§5.6); proxy →
  `ProxyClient`; SDK (logs/health/status/erros); adicionar Docker. Provavelmente **a mais
  simples** de portar; bom primeiro exercício do padrão.

---

### Resumo do esforço

| API | Framework | Já POST? | Captcha | Esforço | Observação |
|---|---|---|---|---|---|
| radar | FastAPI ✅ | sim | CapMonster/2Captcha → SDK | **baixo** | referência |
| docmt | Flask | não (GET) | nenhum | **baixo** | vira `/documento` |
| DETRANPA | Flask | sim | mCaptcha PoW (caso 2) | médio | sem Docker |
| detranrs | Flask | não (GET) | cookie-service (caso 2) | médio | dep. externa |
| detranmt | Flask | não (GET) | CapMonster → SDK | médio-alto | muitos blocos extras |
| detrandf | Flask | não (GET) | OAuth (segredos!) | **alto** | credenciais hardcoded |
| detranmtsefaz | Flask+Playwright | sim | CapMonster → SDK | **alto** | Playwright + parcelamento |

> Sugestão de ordem de execução: **radar** (valida o padrão) → **docmt** (exercita
> `/documento`) → **DETRANPA** → **detranrs** → **detranmt** → **detrandf** → **detranmtsefaz**.
</content>
</invoke>
