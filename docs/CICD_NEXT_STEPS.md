# Próximos passos — CI/CD

O ambiente local está funcionando. O que falta para completar o pipeline.

---

## 1. GitHub — branch protection e staging

```bash
# Criar a branch staging
git checkout -b staging
git push -u origin staging
```

No GitHub → Settings → Branches → Add rule, configurar para `staging` e `master`:
- [x] Require status checks to pass before merging
- Marcar os checks: `Backend — Lint`, `Backend — Unit Tests`, `Backend — Integration Tests`, `Frontend — Lint`, `Frontend — Tests`
- [x] Require a pull request before merging

---

## 2. GitHub — Environment de produção (aprovação manual)

No GitHub → Settings → Environments → New environment:
- Nome: `production`
- Adicionar Required reviewers (seu usuário)

Isso faz o deploy de prod pausar e aguardar aprovação antes de executar.

---

## 3. GitHub — Secrets

No GitHub → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Valor |
|---|---|
| `VPS_STAGING_HOST` | IP da VPS app staging |
| `VPS_STAGING_USER` | usuário SSH (ex: `deploy`) |
| `VPS_STAGING_SSH_KEY` | conteúdo da chave privada SSH |
| `VPS_PROD_HOST` | IP da VPS app prod |
| `VPS_PROD_USER` | usuário SSH |
| `VPS_PROD_SSH_KEY` | conteúdo da chave privada SSH |
| `GHCR_READ_TOKEN` | GitHub PAT com escopo `read:packages` (para o docker pull nas VPS) |

---

## 4. Provisionar VPS DB (staging e prod)

Em cada VPS DB:

```bash
mkdir -p /opt/bridge
# copiar docker-compose.yml e docker-compose.staging.yml (ou prod)
# copiar .env com as credenciais reais dos bancos

docker compose -f docker-compose.yml -f docker-compose.staging.yml --profile db up -d
```

---

## 5. Provisionar VPS APP (staging e prod)

Em cada VPS APP:

```bash
mkdir -p /opt/bridge
# copiar docker-compose.yml e docker-compose.staging.yml (ou prod)
# criar .env com:
#   POSTGRES_HOST=<IP interno da VPS DB>
#   MONGO_HOST=<IP interno da VPS DB>
#   REDIS_HOST=<IP interno da VPS DB>
#   + todas as credenciais e secrets de produção
#   BACKEND_IMAGE e FRONTEND_IMAGE serão definidos pelo CD na hora do deploy

# Instalar Docker na VPS
curl -fsSL https://get.docker.com | sh
```

---

## 6. Nginx (VPS separada)

Configurar o reverse proxy para apontar:
- `api.yourdomain.com` → VPS APP:8000 (backend)
- `app.yourdomain.com` → VPS APP:3000 (frontend)

SSL via Certbot/Let's Encrypt.

Definir `NEXT_PUBLIC_API_URL=https://api.yourdomain.com` no `.env` da VPS APP
(e no `docker-compose.staging/prod.yml` como build arg do frontend).

---

## 7. Testar o pipeline completo

```bash
git checkout -b feature/test-pipeline
# fazer qualquer mudança pequena
git commit -m "test: pipeline smoke test"
git push

# 1. Abrir PR feature/test-pipeline → staging no GitHub
# 2. Verificar que o CI roda e fica verde
# 3. Mergear → verificar deploy automático no staging
# 4. Acessar o staging e validar
# 5. Abrir PR staging → master
# 6. Mergear → aprovar no GitHub Environments → verificar deploy em prod
```

---

## Checklist resumido

- [ ] Branch `staging` criada e pushed
- [ ] Branch protection rules configuradas no GitHub (staging + master)
- [ ] Environment `production` criado com reviewer obrigatório
- [ ] Secrets configurados no GitHub (7 secrets)
- [ ] VPS DB staging provisionada e bancos rodando
- [ ] VPS APP staging provisionada com `.env` correto
- [ ] VPS DB prod provisionada e bancos rodando
- [ ] VPS APP prod provisionada com `.env` correto
- [ ] Nginx configurado com SSL
- [ ] Pipeline testado end-to-end
