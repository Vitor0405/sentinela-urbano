# Guia de publicação

Este guia leva o Sentinela Urbano do computador de desenvolvimento para um servidor de verdade. Tudo o que está aqui já roda **localmente** com `docker-compose.prod.yml`; para o piloto, falta só o que depende de contratação ou de autorização (servidor, domínio, e-mail institucional, bot do Telegram).

## 1. As duas pilhas

| | Desenvolvimento | Produção (ou demonstração) |
|---|---|---|
| Arquivo | `docker-compose.yml` | `docker-compose.prod.yml` (projeto `sentinela-producao`) |
| Endereço | http://localhost:5173 | https://localhost:8443 |
| Web | Vite com recarga automática | PWA compilado, servido pelo Caddy |
| HTTPS | não (ou `npm run dev:https`) | sim (Caddy: certificado local ou Let's Encrypt) |
| API | porta 8000 aberta, recarga automática | sem porta pública, só atrás do Caddy, 1 processo |
| Documentação da API | `/api/docs` | escondida quando `APP_ENV=production` |
| Backup | não | serviço `backup` (diário, guarda 14) |
| E-mails | Mailpit em 8025 | Mailpit em 8026 (demo) ou SMTP real |

As duas pilhas têm containers e volumes próprios e podem rodar ao mesmo tempo.

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml down          # para (os dados ficam nos volumes)
```

## 2. `APP_ENV`

| Valor | Uso | Comportamento |
|---|---|---|
| `development` | pilha de dev | tudo liberado |
| `demo` | apresentações | usuários de teste e dados fictícios (`SEED_DEMO=true`), e-mails no Mailpit |
| `production` | piloto | **a API se recusa a subir** se alguma configuração for insegura; sem dados fictícios; `/api/docs` desligado; `reset-demo` bloqueado |

A checagem fica em `production_problems()` (`api/app/config.py`). Ela recusa:

- `JWT_SECRET` padrão ou com menos de 32 caracteres;
- `ALLOW_TEST_EMAIL_DOMAINS=true`;
- `PUBLIC_WEB_URL` sem `https://`;
- `CORS_ORIGINS` com `localhost`;
- `PREFECTURE_EMAIL` terminando em `.test`;
- `SMTP_HOST` igual a `localhost` ou `mailpit`.

## 3. Checklist do `.env` de produção

Crie um `.env` na raiz (nunca versione esse arquivo):

```ini
APP_ENV=production
SEED_DEMO=false

# Segredos: gere valores aleatórios, por exemplo com
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=<48+ caracteres aleatórios>
POSTGRES_PASSWORD=<senha forte>

# Endereço público
SITE_ADDRESS=sentinela.exemplo.gov.br
TLS_DIRECTIVE=
PUBLIC_WEB_URL=https://sentinela.exemplo.gov.br
CORS_ORIGINS=["https://sentinela.exemplo.gov.br"]

# E-mail institucional (SMTP da prefeitura ou serviço transacional)
SMTP_HOST=smtp.exemplo.gov.br
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
MAIL_FROM=Sentinela Urbano <nao-responda@exemplo.gov.br>
PREFECTURE_EMAIL=vigilancia.ambiental@exemplo.gov.br
ALLOW_TEST_EMAIL_DOMAINS=false

# Grupo de mensagens (opcional)
MESSAGING_PROVIDER=telegram
TELEGRAM_BOT_TOKEN=<token do @BotFather>
MESSAGING_CHAT_ID=<id do grupo, número negativo>

# Mapa: servidor de tiles próprio ou contratado (a política do OSM proíbe uso intenso do tile.openstreetmap.org)
VITE_TILE_URL=https://tiles.exemplo.gov.br/{z}/{x}/{y}.png
VITE_TILE_ATTRIBUTION=© OpenStreetMap contributors
CSP_TILE_HOSTS=https://tiles.exemplo.gov.br
```

Na produção, remova o serviço `mailpit` do compose (ou não o publique) e crie o primeiro gestor pela linha de comando:

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.cli create-user --name "Fulana" --email fulana@exemplo.gov.br --role gestor
```

Depois disso, o gestor convida os agentes pela tela **Gestão → Equipe**. O convite chega por e-mail, com um link de uso único válido por 3 dias.

## 4. Domínio e HTTPS

- No servidor, aponte o DNS do domínio (registro A/AAAA) para o IP da máquina e libere as portas 80 e 443.
- Troque a porta publicada do serviço `web` para `"80:80"` e `"443:443"`.
- Com `SITE_ADDRESS` igual ao domínio e `TLS_DIRECTIVE` vazio, o Caddy obtém e renova sozinho o certificado do Let's Encrypt.
- Os cabeçalhos de segurança já saem do `deploy/Caddyfile`:
  - HSTS, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` (os servidores de tiles do OSM bloqueiam pedidos sem `Referer`; só a origem do site é enviada, nunca o caminho);
  - `Permissions-Policy` só com câmera e localização;
  - **Content-Security-Policy** que só aceita o código do próprio site e o servidor de tiles de `CSP_TILE_HOSTS`.

## 5. Testar no celular sem publicar (rede local)

Câmera, GPS, instalação do PWA e modo offline só funcionam em HTTPS **confiável**. Na mesma rede Wi-Fi:

1. Descubra o IP do computador (`ipconfig`, por exemplo `192.168.0.10`).
2. No `.env`, defina:
   - `SITE_ADDRESS=https://localhost:8443, https://192.168.0.10:8443`
   - `PUBLIC_WEB_URL=https://192.168.0.10:8443`
   - `CORS_ORIGINS=["https://localhost:8443","https://192.168.0.10:8443"]`
3. Suba a pilha de novo e copie o certificado raiz da autoridade local do Caddy:
   ```bash
   docker compose -f docker-compose.prod.yml cp web:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
   ```
4. Instale `caddy-root.crt` no celular:
   - **Android:** Configurações → Segurança → Criptografia e credenciais → Instalar certificado → Certificado de CA.
   - **iPhone:** abra o arquivo, instale o perfil e ative em Ajustes → Geral → Sobre → Ajustes de Confiança de Certificados.
5. Abra `https://192.168.0.10:8443` no celular e instale o app ("Adicionar à tela inicial").
6. Se o celular não abrir a página, libere a porta 8443 no Firewall do Windows (rede privada).

Remova o certificado do celular depois da apresentação. Ele só vale para esta máquina.

## 6. Backups

O serviço `backup` faz um backup ao subir e depois a cada `BACKUP_INTERVAL_HOURS` (24). Ele guarda os `BACKUP_KEEP` (14) mais recentes em `./backups/`:

- `sentinela-AAAAMMDD-HHMMSS.dump`: banco inteiro, formato do `pg_restore`.
- `fotos-AAAAMMDD-HHMMSS.tgz`: fotos enviadas, que ficam fora do banco.

Um arquivo só aparece quando o backup terminou e não está vazio. Até lá, ele é gravado como `.part`.

```bash
# backup agora
docker compose -f docker-compose.prod.yml exec backup sh /backup.sh once
# testar a restauração (num banco à parte, que é apagado no fim): mostra as contagens
docker compose -f docker-compose.prod.yml exec backup sh /backup.sh verify /backups/sentinela-AAAAMMDD-HHMMSS.dump
```

No Git Bash do Windows, prefixe com `MSYS_NO_PATHCONV=1` para o caminho `/backup.sh` não ser convertido.

**Restaurar de verdade** (perde os dados atuais):

```bash
docker compose -f docker-compose.prod.yml stop api backup
docker compose -f docker-compose.prod.yml exec db dropdb -U sentinela sentinela
docker compose -f docker-compose.prod.yml exec db createdb -U sentinela sentinela
docker compose -f docker-compose.prod.yml cp backups/sentinela-AAAAMMDD-HHMMSS.dump db:/tmp/r.dump
docker compose -f docker-compose.prod.yml exec db pg_restore -U sentinela --no-owner -d sentinela /tmp/r.dump
docker compose -f docker-compose.prod.yml start api backup
```

As fotos voltam extraindo o `.tgz` no volume `uploads`.

Copie a pasta `backups/` para **fora do servidor** (outro disco ou nuvem da prefeitura). Um backup na mesma máquina não protege contra perda do disco.

## 7. Limites de uso

A API limita, por IP, numa janela deslizante em memória (`app/ratelimit.py`). Acima do limite, responde 429 com `Retry-After`.

| Ação | Limite |
|---|---|
| Registro de ocorrência | 20 por hora |
| "Eu também vi" | 30 por hora |
| Cadastro | 5 por hora |
| Login | 10 a cada 5 minutos |
| "Esqueci minha senha" | 5 por hora (resposta igual exista ou não a conta) |
| Criar senha pelo link (redefinição ou convite) | 10 por hora |

O limite vive na memória do processo, por isso a API roda com **um** processo (`--workers 1`), o que basta para o piloto. Para escalar em várias máquinas, troque o armazenamento por Redis.

## 8. LGPD na conta do usuário

- **Minha conta → Baixar meus dados:** JSON com a conta, as ocorrências registradas e as confirmações ("eu também vi").
- **Minha conta → Excluir conta** (moradores): pede a senha. A conta é apagada; as ocorrências ficam, anonimizadas (sem nome, contato ou vínculo), porque continuam sendo um foco real de risco na cidade.
- Ao trocar a senha ou ser desativado pelo gestor, todas as sessões abertas caem na hora (`token_version`).
- Antes do piloto, o termo de uso (`web/src/content/terms.ts`) precisa de revisão jurídica e da indicação do encarregado de dados da prefeitura.

## 9. Mapa base

O `tile.openstreetmap.org` serve para testes, mas sua política de uso não permite uso intenso em produção. Opções para o piloto:

- **Servidor próprio:** recorte de Minas Gerais do Geofabrik + [tileserver-gl](https://github.com/maptiler/tileserver-gl) ou PMTiles estático. Sem custo de licença; precisa de disco e baixar os dados.
- **Provedor contratado** com tiles do OSM (há planos gratuitos com limite).

Em qualquer caso, ajuste `VITE_TILE_URL`, `VITE_TILE_ATTRIBUTION` e `CSP_TILE_HOSTS`. A atribuição "© OpenStreetMap contributors" continua obrigatória.

## 10. Tarefas agendadas

No servidor, agende pelo cron do host (ou um container com cron):

```cron
# resumo diário ao grupo, 7h
0 7 * * *  cd /srv/sentinela && docker compose -f docker-compose.prod.yml exec -T api python -m app.cli send-digest
# reenvio de e-mails que falharam, a cada 15 min
*/15 * * * *  cd /srv/sentinela && docker compose -f docker-compose.prod.yml exec -T api python -m app.cli retry-notifications
# pontos sensíveis (escolas, unidades de saúde) do OSM, 1x por mês
0 3 1 * *  cd /srv/sentinela && docker compose -f docker-compose.prod.yml exec -T api python -m app.cli import-sensitive-points
```

## 11. Antes de abrir para o público

- [ ] `.env` de produção preenchido; a API sobe com `APP_ENV=production`.
- [ ] Domínio com HTTPS válido; https://seu-dominio/api/health responde `ok`.
- [ ] E-mail de teste chega ao endereço institucional (não cai no spam).
- [ ] Primeiro gestor criado; agentes convidados; escopos definidos.
- [ ] Setores reais (`import-sectors`) e LIRAa real (`import-liraa`) no lugar dos fictícios.
- [ ] Pesos, coeficientes e textos de prevenção revisados com a vigilância (**Gestão → Configurações**).
- [ ] Termo de uso revisado (jurídico + encarregado de dados) e `TERMS_VERSION` atualizado.
- [ ] Servidor de tiles definido.
- [ ] Backup copiado para fora do servidor e uma restauração testada.
- [ ] Cron das tarefas agendadas ativo.
