# Planejamento do Sistema de Bridge e Administração de APIs

## 1. Visão Geral

Este sistema será uma plataforma web para:

- cadastrar APIs próprias ou de terceiros;
- expor essas APIs para clientes finais por meio de chaves individuais;
- centralizar autenticação, controle de acesso, observabilidade, métricas e cobrança;
- funcionar como uma bridge entre os usuários finais e as APIs cadastradas pelo administrador.

Em termos práticos, o administrador registra uma API informando dados principais como URL base, chave mestre, nome, descrição e documentação. A plataforma então passa a intermediar o consumo dessa API pelos clientes, gerando chaves por usuário, contabilizando uso, registrando erros e apresentando dashboards operacionais e financeiros.

## 2. Objetivo do Projeto

Construir um produto que permita transformar APIs cadastradas manualmente em produtos consumíveis por clientes, com:

- catálogo de APIs disponíveis;
- criação de chaves por cliente;
- controle de uso por chave;
- relatórios de sucesso, erro, custo e volume;
- documentação acessível por API;
- camada de administração centralizada.

## 3. Premissas Iniciais

Estas premissas foram assumidas para montar o planejamento inicial:

- o sistema começará como um produto único, com painel administrativo e painel do cliente;
- o cadastro de novas APIs será feito manualmente pelo administrador;
- a primeira versão suportará apenas APIs REST sobre HTTP/HTTPS;
- a plataforma atuará como gateway/proxy das APIs cadastradas;
- o administrador cadastrará cada API e também seus endpoints;
- cada cliente acessará a API por uma chave gerada dentro da plataforma, e não diretamente pela chave mestre do provedor original;
- o consumo das APIs será feito por rotas da bridge com token de acesso do cliente;
- o token do cliente permanecerá na URL pública da bridge por decisão de produto, mesmo com risco operacional maior;
- a bridge irá repassar a chamada para a API upstream e devolver a resposta, sem transformação de payload, headers ou response body na primeira fase;
- o primeiro foco deve ser estabilidade operacional, controle de uso e capacidade de adicionar novas APIs sem alterar a arquitetura principal;
- o custo será apenas informativo no dashboard;
- respostas com erro não gerarão custo, mas deverão ser contabilizadas como consultas não cobradas;
- o acesso às APIs será liberado individualmente pelo administrador para cada cliente;
- APIs desativadas devem continuar visíveis com indicador de status e histórico preservado;
- o sistema deverá armazenar logs completos, metadados e erros resumidos;
- os logs completos terão retenção configurável em horas, com padrão inicial de 24 horas;
- dados sensíveis em logs deverão ser mascarados antes da persistência;
- o custo informativo será configurado por API;
- o rate limit será configurado por chave e por API, com valores configuráveis;
- chamadas bloqueadas por rate limit não serão cobradas;
- o status operacional da API poderá ser definido manualmente pelo administrador e também por mecanismos automáticos;
- a primeira fase não terá e-mail de ativação nem recuperação de senha;
- o PostgreSQL será o banco principal das funcionalidades transacionais da aplicação;
- o MongoDB será usado para armazenamento de logs completos, metadados e erros resumidos;
- a primeira versão pode nascer como um monólito modular, sem microserviços.

## 4. Escopo Inicial

### Dentro do escopo da primeira fase

- autenticação de administradores e clientes;
- solicitação de cadastro de novos clientes;
- aprovação de clientes pelo administrador;
- cadastro e gestão de APIs pelo administrador;
- cadastro e gestão de endpoints por API;
- cadastro de documentação de uso por API;
- listagem de APIs disponíveis para clientes;
- liberação de APIs por cliente;
- criação, nomeação, ativação e desativação de chaves pelos clientes;
- proxy de requisições para APIs upstream;
- registro de métricas por requisição;
- dashboard por cliente e por chave;
- logs completos, metadados, erros resumidos e histórico de consumo;
- cálculo de custo por consulta;
- cálculo de custo médio por período;
- base para regras de limite e cobrança.

### Fora do escopo da primeira fase

- marketplace público com auto cadastro de provedores externos;
- billing completo com emissão fiscal;
- engine avançada de planos comerciais;
- suporte nativo a múltiplos tipos de protocolos além de HTTP/HTTPS;
- automação completa de leitura de documentação externa.

## 5. Perfis de Usuário

### Administrador

Responsável por:

- aprovar solicitações de cadastro de clientes;
- cadastrar APIs;
- cadastrar e manter endpoints por API;
- definir disponibilidade das APIs;
- configurar custos, limites e regras de acesso;
- revisar métricas globais;
- consultar erros operacionais;
- manter documentação e exemplos.

### Cliente

Responsável por:

- solicitar cadastro e aguardar aprovação;
- visualizar APIs liberadas para sua conta;
- consultar documentação;
- gerar e nomear chaves;
- acompanhar consumo e custos;
- investigar falhas de integração por meio de logs e dashboards.

## 6. Proposta de Lógica de Negócio

### 6.1 Cadastro de APIs

O administrador deve conseguir cadastrar uma API com, no mínimo:

- nome;
- descrição curta;
- URL base;
- chave mestre;
- tipo de autenticação upstream;
- status;
- documentação de uso;
- exemplos de código;
- política de cobrança;
- política de limite;
- categoria ou tags;
- versão da API cadastrada.

Status operacionais mínimos da API:

- disponível;
- erro;
- indisponível.

Além do cadastro da API, o administrador deve cadastrar os endpoints associados, com:

- nome do endpoint;
- método HTTP;
- path relativo;
- descrição funcional;
- status do endpoint;
- documentação específica;
- exemplos de request;
- exemplos de response;
- regra de custo informativo;
- visibilidade para clientes autorizados.

Cada endpoint deve herdar ou respeitar o status operacional da API pai.

### 6.2 Disponibilização para clientes

Nem toda API cadastrada deve, obrigatoriamente, ficar disponível para todos os clientes. O sistema deve prever:

- APIs liberadas individualmente por cliente;
- fluxo de aprovação de cadastro do cliente pelo administrador;
- possibilidade de concessão e revogação manual de acesso por API;
- possibilidade de ativar ou desativar uma API sem apagar o cadastro.

Quando uma API for desativada:

- ela não deve aceitar novas consultas;
- ela deve continuar visível para o cliente com indicador de desativada;
- o histórico de uso, custos e erros deve continuar disponível.

### 6.3 Criação de chaves do cliente

Cada cliente pode criar uma ou mais chaves para cada API liberada. Cada chave deve ter:

- nome amigável;
- identificador único;
- segredo real exibido apenas no momento de criação;
- status ativo, inativo ou revogado;
- data de criação;
- último uso;
- escopo da chave, se houver separação por permissões no futuro.

A criação de chave deve respeitar a lista de APIs liberadas pelo administrador para aquele cliente.

### 6.4 Processamento da requisição

Fluxo esperado:

1. o cliente envia uma requisição para a bridge usando sua chave;
2. a bridge valida se a chave existe, está ativa e tem acesso à API;
3. a bridge valida se a API e o endpoint estão ativos e liberados para aquele cliente;
4. a bridge aplica regras de segurança, limite e autorização;
5. a bridge resolve a rota pública da API, identifica o token do cliente e os parâmetros da chamada;
6. a bridge encaminha a chamada REST para a API upstream usando a chave mestre armazenada;
7. a bridge recebe a resposta da API upstream;
8. a bridge registra métricas técnicas, financeiras e logs;
9. a bridge devolve o resultado ao cliente sem transformação funcional na primeira fase.

### 6.5 Métricas e observabilidade

Para cada requisição, o sistema deve poder registrar:

- cliente;
- chave utilizada;
- API consumida;
- endpoint lógico;
- método HTTP;
- data e hora;
- latência;
- status final;
- código HTTP retornado;
- tamanho da resposta, se relevante;
- custo calculado;
- indicador de consulta cobrada ou não cobrada;
- mensagem de erro resumida, quando existir;
- request completo;
- response completa;
- identificador de correlação para rastreamento.

### 6.6 Custos

O sistema precisa tratar custo como conceito de negócio central. O ideal é suportar, no mínimo:

- custo fixo por requisição;
- custo variável por endpoint;
- custo médio por período;
- soma de custo por chave;
- soma de custo por API;
- soma de custo por cliente.

Na lógica atual definida:

- o custo é informativo e não representa cobrança financeira automática;
- o custo informativo será configurado por API;
- consultas com sucesso podem gerar custo informativo;
- consultas com erro não geram custo;
- timeouts, indisponibilidade upstream e cancelamentos entram como consultas não cobradas;
- consultas com erro devem aparecer separadamente como consultas não cobradas;
- o dashboard deve permitir diferenciar volume total de volume cobrado.

### 6.7 Dashboard do cliente

O dashboard deve permitir visualizar:

- total de requisições por período;
- total de sucessos;
- total de erros;
- total de consultas cobradas;
- total de consultas não cobradas;
- taxa de erro;
- latência média;
- custo total;
- custo médio por requisição;
- status operacional atual da API;
- comparação por chave;
- comparação por API;
- evolução temporal em gráfico.

O dashboard também deve separar dois conceitos diferentes:

- tipologia técnica dos erros;
- classificação financeira e operacional de requisições não cobradas.

As categorias mínimas de erro devem ser:

- erro da bridge;
- indisponibilidade da API;
- bloqueio por rate limit;
- erro na requisição.

Além disso, deve existir uma aba ou visão separada para exibir a quantidade de requisições não cobradas, independentemente do tipo técnico do erro.

## 7. Buracos de Lógica Já Identificados

Estes pontos ainda seguem abertos ou precisam de decisão detalhada para evitar retrabalho:

### 7.1 Modelo de integração das APIs cadastradas

Já foi definido que:

- todas as integrações da primeira fase serão REST sobre HTTP/HTTPS;
- o administrador cadastrará a API e seus endpoints;
- a bridge fará apenas repasse da chamada e retorno da resposta.

O que ainda falta fechar:

- se query params e headers sensíveis precisarão de tratamento especial;
- se haverá timeout padrão por API ou por endpoint.

### 7.2 Controle de cobrança

Já foi definido que:

- o custo é apenas informativo;
- erros não são cobrados;
- erros contam como consultas não cobradas.

O que ainda falta fechar:

- apenas o detalhamento final dos códigos e rótulos internos de erro.

### 7.3 Limites e proteção contra abuso

Ainda falta definir:

- política exata de rate limit por chave e por API;
- limite mensal por cliente;
- bloqueio automático por excesso;
- alertas para uso anormal;
- política de revogação de chave comprometida.

### 7.4 Privacidade e logs

Como o sistema armazenará requests e responses completos, surgem riscos e decisões obrigatórias sobre:

- dados sensíveis de clientes;
- credenciais enviadas em payload;
- LGPD e retenção de logs;
- exposição de erros internos da API upstream.

Já foi definido que:

- dados sensíveis serão mascarados;
- a retenção de logs completos será configurável em horas;
- o tempo padrão inicial será de 24 horas.

### 7.5 Multitenancy

Esta decisão impacta modelagem de dados, permissões e operação. A terminologia correta para o que estamos desenhando é a seguinte:

#### Opção A: Multi-tenant com isolamento lógico

Todos os clientes usam a mesma aplicação e o mesmo banco, com separação por `client_id` ou `tenant_id`.

Vantagens:

- implementação mais simples;
- menor custo operacional;
- mais rápido para lançar o MVP;
- consultas e manutenção mais diretas no início.

Riscos:

- exige muito cuidado para não vazar dados entre clientes por erro de consulta;
- menor isolamento estrutural;
- clientes grandes podem querer separação mais forte no futuro.

#### Opção B: Multi-tenant com schemas separados por tenant

Cada cliente ou grupo de clientes pode ter um schema próprio dentro do mesmo banco.

Vantagens:

- isolamento mais forte do que o lógico simples;
- facilita operações de manutenção por tenant;
- reduz risco de mistura acidental de dados.

Riscos:

- aumenta complexidade de migração e manutenção;
- cresce pior quando há muitos tenants;
- complica analytics globais.

#### Opção C: Single-tenant por cliente

Cada cliente relevante tem sua própria instância da aplicação e sua própria infraestrutura ou banco dedicado.

Vantagens:

- isolamento muito mais forte;
- melhor para clientes enterprise com exigência contratual;
- facilita backup, retenção e políticas específicas por cliente.

Riscos:

- custo operacional muito maior;
- implantação e observabilidade mais complexas;
- mais difícil para começar pequeno.

#### Recomendação inicial

Para o seu cenário atual, a recomendação mais equilibrada é:

- começar com **multi-tenant com isolamento lógico forte**;
- modelar tudo com `client_id` desde o início;
- preparar o sistema para permitir evolução futura para tenants mais isolados, se necessário.

Isso entrega velocidade no MVP sem fechar a porta para um modelo mais robusto depois.

### 7.6 Fluxo de cadastro de cliente

Agora existe um fluxo novo de entrada no sistema, mas ainda faltam detalhes sobre:

- quais dados o cliente informa na solicitação de cadastro;
- se haverá e-mail de ativação;
- se o cliente pode existir sem nenhuma API liberada inicialmente.

Já foi definido que:

- o cliente informará nome, e-mail, empresa e senha;
- a aprovação do admin será manual;
- o cliente pode ser aprovado sem nenhuma API liberada inicialmente;
- a primeira fase não terá e-mail de ativação nem recuperação de senha.

### 7.7 Exposição do token na URL

Você definiu que o consumo pode seguir um formato como:

- `bridgeapi.meudominio.com/consulta/TOKEN/CONSULTADOUSUARIO`

Esse modelo simplifica o consumo, mas cria um risco importante:

- tokens em URL tendem a aparecer em logs, histórico, analytics, proxies e caches.

Antes de fechar a arquitetura, esse ponto precisa de validação explícita.

Já foi definido que:

- o produto manterá o token na URL pública por decisão de negócio.

## 8. Arquitetura Recomendada

### 8.1 Estratégia geral

Recomendação inicial: começar com um **monólito modular**, organizado por domínios, para reduzir complexidade operacional e acelerar a primeira entrega.

Domínios sugeridos:

- autenticação e autorização;
- onboarding de clientes;
- catálogo de APIs;
- catálogo de endpoints;
- chaves de acesso;
- proxy/gateway;
- métricas e analytics;
- billing/custos;
- mascaramento e retenção de logs;
- documentação;
- administração.

Essa abordagem atende bem a fase inicial e permite extrair serviços separados mais tarde, se o volume justificar.

### 8.2 Backend: síncrono ou assíncrono

### Recomendação inicial

Para este produto, a recomendação mais forte é usar um backend **assíncrono**.

### Motivo

O ponto central do sistema é receber uma requisição e repassá-la para outra API externa. Isso é altamente dependente de I/O de rede, e não de processamento pesado interno. Um backend assíncrono tende a se encaixar melhor porque:

- lida melhor com muitas conexões simultâneas;
- reduz desperdício de threads aguardando respostas de APIs externas;
- combina melhor com gateway, proxy, métricas e observabilidade em tempo real;
- facilita crescimento do throughput sem aumentar tanto o custo de infraestrutura.

### Framework backend recomendado

**FastAPI** é a recomendação inicial mais equilibrada.

Pontos fortes:

- ecossistema maduro em Python;
- ótima compatibilidade com rotas assíncronas;
- documentação automática útil para a área administrativa;
- boa produtividade;
- forte adoção de Pydantic para validação;
- adequado para painéis administrativos e APIs de produto.

### Alternativas

- **Django + Django Rest Framework**: excelente para backoffice e administração, mas menos natural para uma bridge intensiva em I/O.
- **Flask**: simples, porém pode exigir mais decisões estruturais cedo.
- **Litestar / Starlite**: opção moderna, mas com menos adoção que FastAPI.

Conclusão: para este caso, **FastAPI assíncrono** parece o melhor ponto de partida.

Bibliotecas e componentes que combinam bem com esse cenário:

- `httpx` para chamadas HTTP assíncronas às APIs upstream;
- `SQLAlchemy` com suporte assíncrono para persistência;
- `Alembic` para migrações;
- `Pydantic` para contratos internos e validação.

Estratégia inicial recomendada para a bridge:

- rota pública versionada por API;
- resolução interna do endpoint cadastrado;
- token validado antes do encaminhamento;
- path params repassados para a API upstream;
- suporte a métodos REST configurados por endpoint.

### 8.3 Frontend web

### Recomendação inicial

Para a interface web, a recomendação inicial é:

- **Next.js com React** para o frontend;
- backend separado em API.

### Motivo

- facilita dashboards, autenticação e páginas de documentação;
- possui ecossistema maduro para interfaces administrativas;
- permite SSR quando for útil para performance e SEO da documentação;
- oferece boa base para páginas internas e componentes de gráficos.

### Alternativas

- **Vue + Nuxt**: excelente opção, especialmente se você preferir a ergonomia do Vue;
- **Django templates + HTMX**: válido se você quiser simplificar o stack e aceitar um frontend menos rico no início.

Se a prioridade for produto com dashboard mais moderno e escalável, **Next.js** tende a ser a melhor escolha.

### 8.4 Banco de dados

Recomendação inicial:

- **PostgreSQL** como banco principal da aplicação;
- **MongoDB** para logs completos, metadados e erros resumidos;
- **Redis** para cache, rate limit, filas leves e dados temporários.

### Dados que devem ficar no PostgreSQL

- usuários;
- clientes;
- APIs cadastradas;
- chaves;
- permissões;
- registros agregados de uso;
- custos;
- documentação e exemplos.
- permissões de API por cliente;
- histórico de aprovação e status do cliente.
- configuração de retenção de logs em horas.

### Dados que devem ficar no MongoDB

- request completa;
- response completa;
- erro resumido;
- metadados técnicos da chamada;
- status final da consulta;
- indicadores de mascaramento;
- referência de cliente, chave, API e endpoint para rastreabilidade.

### Dados que podem passar por Redis

- sessões;
- rate limit counters por chave e por API;
- cache de catálogo;
- filas curtas para processamento assíncrono;
- buffering de métricas antes de consolidação.

### Dados que podem migrar no crescimento

- bodies completos de request;
- bodies completos de response;
- snapshots expurgados do MongoDB após o prazo quente;
- anexos futuros de auditoria ou exportação para object storage, se o volume justificar.

### 8.5 Processamento assíncrono interno

Mesmo com backend assíncrono, ainda será importante ter tarefas em background para:

- agregação periódica de métricas;
- consolidação de custos;
- limpeza e retenção de logs;
- mascaramento ou saneamento de dados sensíveis em logs;
- envio de alertas;
- rotinas administrativas.

Opções:

- Celery;
- RQ;
- Dramatiq.

Para a primeira fase, **Celery** ou **Dramatiq** são opções adequadas. Se quiser reduzir complexidade, algumas rotinas podem começar em jobs simples agendados.

### 8.6 Observabilidade

Desde o início, vale prever:

- logs estruturados;
- correlation id por requisição;
- métricas técnicas;
- monitoramento de latência;
- health checks automáticos para compor o status operacional;
- alertas de falha da API upstream;
- rastreabilidade de aprovação e alteração de permissões por cliente;
- trilha de auditoria para ações administrativas.

## 9. Modelo Conceitual de Entidades

Entidades principais:

- usuário;
- organização ou cliente;
- administrador;
- solicitação de cadastro;
- API cadastrada;
- versão da API;
- endpoint catalogado;
- chave do cliente;
- permissão de acesso;
- requisição processada;
- log de erro;
- regra de custo;
- regra de limite;
- configuração de retenção;
- evento de auditoria.

## 10. Fluxos Principais do Sistema

### 10.1 Fluxo administrativo

1. administrador cadastra API;
2. cadastra endpoints, documentação, custo informativo, disponibilidade e status;
3. aprova cadastro de clientes;
4. libera APIs específicas para cada cliente;
5. publica API no catálogo daquele cliente;
6. monitora uso, erros e status operacional manual ou automático.

### 10.2 Fluxo do cliente

1. cliente faz login;
2. visualiza APIs disponíveis para sua conta;
3. abre detalhes, endpoints e documentação;
4. cria uma chave para uma API liberada;
5. usa a bridge para consumir os endpoints disponíveis por token;
6. acompanha consumo, custo informativo e erros no dashboard.

### 10.3 Fluxo de processamento

1. bridge recebe chamada autenticada;
2. extrai o token da rota pública;
3. valida chave, permissão e limites;
4. valida se a API e o endpoint continuam ativos;
5. resolve qual API upstream deve ser chamada;
6. adiciona credencial mestre da integração;
7. encaminha a requisição REST;
8. captura resultado;
9. registra telemetria, logs completos mascarados e classificação de custo;
10. responde ao cliente.

## 11. Plano de Execução do Projeto

### Fase 1: Descoberta e definição

- fechar regras de negócio pendentes;
- definir escopo da primeira entrega;
- padronizar como uma API é cadastrada;
- padronizar como endpoints são cadastrados;
- definir fluxo de solicitação e aprovação de cliente;
- definir padrão exato das rotas públicas da bridge;
- definir requisitos mínimos de segurança.

### Fase 2: Arquitetura e modelagem

- modelar entidades principais;
- definir contratos internos;
- desenhar fluxo do proxy;
- definir estratégia de autenticação;
- definir como compor status manual com health check automático;
- definir política de mascaramento de logs;
- definir política de armazenamento de logs completos;
- definir estratégia de métricas e retenção de logs;
- definir padrão da documentação por API.

### Fase 3: MVP administrativo

- autenticação;
- tela de aprovação de cadastro de cliente;
- cadastro de APIs;
- cadastro de endpoints;
- gestão de disponibilidade;
- liberação de APIs por cliente;
- cadastro de custo informativo e limite;
- configuração de status operacional da API;
- cadastro de documentação e exemplos.

### Fase 4: MVP do cliente

- solicitação de cadastro;
- login do cliente aprovado;
- catálogo de APIs;
- detalhe das APIs e endpoints;
- criação e gestão de chaves;
- painel inicial de uso.

### Fase 5: Núcleo de bridge

- validação de chaves;
- encaminhamento para API upstream;
- tratamento de timeout, erro e retry;
- registro de métricas por chamada;
- armazenamento de request/response completos;
- controle de rate limit por chave e por API.

### Fase 6: Analytics e operação

- gráficos;
- filtros por período;
- custo por consulta;
- custo médio;
- consultas cobradas versus não cobradas;
- consultas barradas por rate limit como não cobradas;
- categorização visual de erros por tipo;
- aba separada para requisições não cobradas;
- logs de falha;
- visualização de request/response completos;
- auditoria administrativa.

### Fase 7: Evolução comercial

- planos por cliente;
- limites mensais;
- alertas de consumo;
- billing avançado;
- versionamento de APIs;
- regras por endpoint.

## 12. Riscos Técnicos e de Produto

- cadastro genérico de APIs pode ficar simples demais para integrações mais complexas;
- APIs externas podem ter autenticações e formatos muito diferentes entre si;
- logs detalhados podem gerar custo alto de armazenamento;
- retenção de logs completos pode gerar risco jurídico e de segurança;
- dashboards em tempo real podem aumentar bastante o volume de escrita;
- vazamento de chave mestre é risco crítico;
- sem política clara de mascaramento, logs podem armazenar segredos e dados sensíveis;
- token na URL pode vazar por trilhas externas de observabilidade e infraestrutura;
- aprovação manual de clientes pode virar gargalo operacional se o volume crescer;
- ausência inicial de recuperação de senha exigirá suporte manual.

## 13. Recomendações Estratégicas

- começar com suporte explícito a APIs HTTP REST;
- exigir padrão mínimo de autenticação nas integrações da primeira fase;
- não tentar suportar todos os formatos de API no MVP;
- tratar chave mestre como segredo criptografado;
- separar métricas transacionais de métricas agregadas;
- separar metadados de uso dos bodies completos de request/response;
- registrar erro técnico detalhado internamente e mostrar erro sanitizado ao cliente;
- manter custo apenas como indicador operacional na primeira fase;
- definir desde cedo retenção, mascaramento e consulta segura dos logs completos;
- para o MVP, preferir multi-tenant com isolamento lógico forte e evolução planejada.

## 14. Perguntas Que Precisam de Resposta

No momento, não há perguntas críticas em aberto para o planejamento macro.

Os pontos restantes são de detalhamento operacional, como:

- códigos internos e rótulos padronizados de erro;
- timeout padrão por API ou por endpoint;
- política de limite mensal por cliente;
- regras de bloqueio automático e alertas.

## 15. Próximo Passo Recomendado

Antes de qualquer escolha final de stack ou modelagem detalhada, o ideal é fechar as respostas da seção anterior. Essas respostas definem:

- o modelo de segurança;
- o formato seguro da autenticação pública da bridge;
- o modelo de dados;
- o fluxo de onboarding do cliente;
- a política de retenção e consulta de logs;
- a granularidade do custo informativo;
- a necessidade de arquitetura mais genérica ou mais opinativa.

Com as definições atuais, o planejamento macro já está consistente o suficiente para avançar para a próxima etapa de detalhamento funcional e modelagem estrutural.
