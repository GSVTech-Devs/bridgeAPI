# Deploy — Bridge API (VPS única, AlmaLinux)

Topologia: tudo numa VPS. Backend + bancos em **Docker Compose**, frontend
compilado (Next.js standalone) também em container, e **nginx no host** fazendo
proxy reverso com TLS (Let's Encrypt).

```
                            VPS (AlmaLinux)
  bridgeapi.gsvtech.com.br      ──► nginx :443 ──► 127.0.0.1:3000  (frontend)
  bridgeapiback.gsvtech.com.br  ──► nginx :443 ──► 127.0.0.1:8000  (backend)

  containers (rede compose interna): postgres · mongo · redis · backend · frontend
```

Os containers escutam **só em 127.0.0.1** (`BIND_IP=127.0.0.1`); o tráfego
externo entra exclusivamente pelo nginx.

---

## 0. Pré-requisitos (DNS)

Antes de tudo, crie os registros **A** apontando para o IP da VPS:

```
bridgeapi.gsvtech.com.br        A   <IP_DA_VPS>
bridgeapiback.gsvtech.com.br    A   <IP_DA_VPS>
```

O certbot só emite o certificado depois que o DNS resolver para a VPS.

---

## 1. Pacotes do sistema (como root)

```bash
# Docker + plugin compose
dnf -y install dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin git
systemctl enable --now docker

# nginx + certbot
dnf -y install nginx certbot python3-certbot-nginx
systemctl enable --now nginx
```

### SELinux (AlmaLinux vem com SELinux enforcing)

Para o nginx do host conseguir fazer proxy para as portas locais:

```bash
setsebool -P httpd_can_network_connect 1
```

### firewalld — abrir só 80/443 (NUNCA 3000/8000)

```bash
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

---

## 2. Código e variáveis de ambiente

```bash
mkdir -p /opt/bridge
git clone <URL_DO_REPO> /opt/bridge
cd /opt/bridge

cp .env.production.example .env
```

Edite `/opt/bridge/.env` e preencha os segredos. Gere valores fortes:

```bash
openssl rand -hex 32       # APP_SECRET_KEY
openssl rand -hex 32       # ENCRYPTION_KEY  (64 chars hex obrigatórios)
openssl rand -base64 24    # senhas de postgres/mongo/redis
```

Confirme que estão setados:

- `APP_ENV=production`
- `BIND_IP=127.0.0.1`
- `NEXT_PUBLIC_API_URL=https://bridgeapiback.gsvtech.com.br`
- `CORS_ORIGINS=https://bridgeapi.gsvtech.com.br`
- `DATABASE_URL` / `MONGO_URL` / `REDIS_URL` com as **mesmas senhas** e host =
  nome do container (`postgres` / `mongo` / `redis`).

> `NEXT_PUBLIC_API_URL` é assada no bundle do front no momento do build. Se mudar
> o domínio do backend depois, tem que **rebuildar o frontend** (passo 3).

---

## 3. Subir a stack (build de produção)

```bash
cd /opt/bridge
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile db --profile app up -d --build
```

O serviço `migrator` roda `alembic upgrade head` automaticamente antes do backend
subir (o backend depende de `migrator` completar com sucesso).

Verifique:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -s http://127.0.0.1:8000/health      # {"status":"ok"}
curl -sI http://127.0.0.1:3000            # 200
```

### Criar o primeiro admin

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  python scripts/create_admin.py --email admin@gsvtech.com.br --password 'SUA_SENHA_FORTE'
```

---

## 4. nginx + TLS

Copie as configs do repo e valide:

```bash
cp /opt/bridge/deploy/nginx/bridgeapi.gsvtech.com.br.conf      /etc/nginx/conf.d/
cp /opt/bridge/deploy/nginx/bridgeapiback.gsvtech.com.br.conf  /etc/nginx/conf.d/
nginx -t && systemctl reload nginx
```

Emita os certificados (o plugin injeta o bloco 443 + redirect 80→443 sozinho):

```bash
certbot --nginx -d bridgeapi.gsvtech.com.br
certbot --nginx -d bridgeapiback.gsvtech.com.br
nginx -t && systemctl reload nginx
```

Renovação automática já vem ativa via timer do systemd. Teste com:

```bash
certbot renew --dry-run
```

---

## 5. Verificação final

```bash
curl -s https://bridgeapiback.gsvtech.com.br/health     # {"status":"ok"}
```

Abra `https://bridgeapi.gsvtech.com.br` no navegador, faça login e confirme no
DevTools (aba Network) que as chamadas vão para `https://bridgeapiback...` sem
erro de CORS.

---

## 6. Atualizar (deploy de nova versão)

```bash
cd /opt/bridge
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile db --profile app up -d --build
```

O `--build` reconstrói backend e frontend. Migrations rodam de novo via
`migrator`. Se só mudou backend, o front não precisa rebuildar (mas `up -d --build`
reaproveita cache, então é seguro rodar sempre).

---

## 7. Operação

```bash
# logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend

# restart de um serviço
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# backup do postgres
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
  pg_dump -U bridge bridgeapi > backup-$(date +%F).sql
```

Os dados persistem nos volumes `postgres_data`, `mongo_data`, `redis_data`
(sobrevivem a `up`/`down`; só somem com `down -v`).
