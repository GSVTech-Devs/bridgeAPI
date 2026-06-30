# Guia de Deploy na VPS (passo a passo)

Cenário: VPS **AlmaLinux**, repo **já clonado em `/opt/`**, backend + bancos em
Docker Compose, frontend compilado em container, **nginx no host** com TLS
(Let's Encrypt). Domínios:

- Frontend: `https://bridgeapi.gsvtech.com.br`
- Backend: `https://bridgeapiback.gsvtech.com.br`

Execute tudo como **root** (ou com `sudo`).

---

## 0. Entrar no diretório do projeto

Ajuste para o caminho real onde clonou:

```bash
cd /opt/bridgeAPI      # troque se o nome da pasta for outro
ls docker-compose.yml .env.production.example DEPLOY.md
```

---

## 1. DNS (faça primeiro, antes do certbot)

No provedor de DNS, crie dois registros **A** apontando para o IP da VPS:

```
bridgeapi.gsvtech.com.br        A   <IP_DA_VPS>
bridgeapiback.gsvtech.com.br    A   <IP_DA_VPS>
```

Valide a propagação (precisa retornar o IP da VPS):

```bash
dig +short bridgeapi.gsvtech.com.br
dig +short bridgeapiback.gsvtech.com.br
```

> O certbot (passo 6) falha se o DNS ainda não resolver para a VPS.

---

## 2. Instalar Docker, nginx e certbot

```bash
# Docker + plugin compose
dnf -y install dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

# nginx + certbot
dnf -y install nginx certbot python3-certbot-nginx
systemctl enable --now nginx
```

Confirme:

```bash
docker compose version
nginx -v
```

---

## 3. SELinux + firewall (AlmaLinux)

```bash
# deixa o nginx do host fazer proxy para as portas locais (127.0.0.1:3000/8000)
setsebool -P httpd_can_network_connect 1

# abre apenas 80 e 443 (NÃO abra 3000/8000)
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

---

## 4. Configurar o `.env` de produção

```bash
cd /opt/bridgeAPI
cp .env.production.example .env
```

Gere os segredos (rode cada comando e copie o valor):

```bash
openssl rand -hex 32       # APP_SECRET_KEY
openssl rand -hex 32       # ENCRYPTION_KEY  (precisa ter 64 chars hex)
openssl rand -base64 24    # senha do postgres
openssl rand -base64 24    # senha do mongo
openssl rand -base64 24    # senha do redis
```

Edite o arquivo:

```bash
nano .env      # ou vim
```

Trocando os `__TROCAR__`. Pontos críticos:

- `APP_ENV=production`
- `BIND_IP=127.0.0.1`
- `NEXT_PUBLIC_API_URL=https://bridgeapiback.gsvtech.com.br`
- `CORS_ORIGINS=https://bridgeapi.gsvtech.com.br`
- `APP_SECRET_KEY` e `ENCRYPTION_KEY` com os valores gerados
- **A senha do postgres precisa ser idêntica** em `POSTGRES_PASSWORD` e dentro de
  `DATABASE_URL`. Mesma regra para mongo (`MONGO_PASSWORD` + `MONGO_URL`) e redis
  (`REDIS_PASSWORD` + `REDIS_URL`).

> `NEXT_PUBLIC_API_URL` é "assada" no bundle do frontend no momento do build. Se
> mudar depois, é preciso rebuildar o frontend.

---

## 5. Subir a stack (build de produção)

```bash
cd /opt/bridgeAPI
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile db --profile app up -d --build
```

O serviço `migrator` roda as migrations (`alembic upgrade head`) automaticamente
antes do backend subir. O primeiro build demora alguns minutos.

Verifique:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -s http://127.0.0.1:8000/health        # esperado: {"status":"ok"}
curl -sI http://127.0.0.1:3000 | head -1     # esperado: HTTP/1.1 200 OK
```

Se algo falhar, veja os logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs migrator
```

### Criar o primeiro usuário admin

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  python scripts/create_admin.py --email admin@gsvtech.com.br --password 'SUA_SENHA_FORTE'
```

---

## 6. nginx + TLS (HTTPS)

Copie as configs do repo para o nginx e valide:

```bash
cp /opt/bridgeAPI/deploy/nginx/bridgeapi.gsvtech.com.br.conf      /etc/nginx/conf.d/
cp /opt/bridgeAPI/deploy/nginx/bridgeapiback.gsvtech.com.br.conf  /etc/nginx/conf.d/
nginx -t && systemctl reload nginx
```

Emita os certificados (o certbot edita os arquivos sozinho, adicionando o bloco
443 e o redirect 80 -> 443):

```bash
certbot --nginx -d bridgeapi.gsvtech.com.br
certbot --nginx -d bridgeapiback.gsvtech.com.br
```

Ele pergunta email e aceite dos termos. Depois:

```bash
nginx -t && systemctl reload nginx
certbot renew --dry-run     # confirma que a renovação automática funciona
```

---

## 7. Verificação final

```bash
curl -s https://bridgeapiback.gsvtech.com.br/health     # {"status":"ok"}
```

Abra **https://bridgeapi.gsvtech.com.br** no navegador, faça login com o admin
criado e, no DevTools (aba Network), confirme que as chamadas vão para
`https://bridgeapiback...` sem erro de CORS.

---

## Comandos do dia a dia

```bash
cd /opt/bridgeAPI

# atualizar versão (novo código)
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile db --profile app up -d --build

# logs ao vivo
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend

# reiniciar um serviço
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# backup do postgres
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
  pg_dump -U bridge bridgeapi > backup-$(date +%F).sql
```

---

## Avisos importantes

1. **Nunca rode `down -v` em produção.** O `-v` apaga os volumes
   (postgres/mongo/redis) e você perde todos os dados. `down` sozinho é seguro.
2. **`ENCRYPTION_KEY` não pode mudar** depois que houver segredos criptografados
   no banco: trocar a key = perder acesso a eles.
3. Os dados persistem nos volumes `postgres_data`, `mongo_data`, `redis_data`,
   sobrevivendo a `up`/`down` (só somem com `down -v`).
