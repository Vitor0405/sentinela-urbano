# Sentinela Urbano

Vigilância comunitária de risco de arbovirose (dengue, zika e chikungunya). Moradores registram focos com foto e localização, agentes de saúde atendem uma fila priorizada por risco e a prefeitura é avisada automaticamente.

Projeto Integrador de Engenharia da Computação (ODS 3, meta 3.3). Documentos em [`docs/`](docs/); decisões em [`docs/decisoes.md`](docs/decisoes.md).

## Como rodar

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (no Windows, com WSL 2).

```bash
docker compose up --build
```

Na primeira subida, a API aplica as migrations e cria os dados de desenvolvimento: tipos, pesos, usuários de teste e 60 ocorrências fictícias em Montes Claros (MG). De início, o sistema atende só Montes Claros: registros fora do município são recusados (veja `SERVICE_AREA_BBOX` no `.env.example`).

| Serviço | Endereço |
|---|---|
| Aplicativo (PWA) | http://localhost:5173 |
| API (documentação interativa) | http://localhost:8000/api/docs |
| Mailpit (e-mails enviados à "prefeitura") | http://localhost:8025 |

Usuários de teste: `morador@sentinela.test`, `agente@sentinela.test`, `gestor@sentinela.test` e os vizinhos `vizinho1@sentinela.test` / `vizinha2@sentinela.test`, que confirmam algumas ocorrências ("eu também vi"). A senha está em `SEED_PASSWORD`, no [`.env.example`](.env.example).

Para mudar configurações (centro do mapa, provedor de tiles, e-mail da prefeitura), copie `.env.example` para `.env`.

### Testar no celular

Câmera e GPS exigem conexão segura. Com o celular na mesma rede:

```bash
cd web && npm install && npm run dev:https
```

Abra `https://<ip-do-computador>:5173` e aceite o certificado de desenvolvimento. A API precisa estar no ar (`docker compose up db api mailpit`).

Para instalar o app e testar o modo offline no celular, use a pilha de produção local com o certificado instalado no aparelho (seção 5 de [`docs/PUBLICACAO.md`](docs/PUBLICACAO.md)).

## Pilha de produção local (demonstração)

Versão compilada, instalável e com HTTPS, igual à que vai para um servidor, rodando na própria máquina:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

| Serviço | Endereço |
|---|---|
| Aplicativo (PWA com HTTPS local) | https://localhost:8443 |
| Mailpit desta pilha | http://localhost:8026 |

- Caddy serve o app, faz o HTTPS e envia os cabeçalhos de segurança.
- O serviço `backup` grava o banco e as fotos em `./backups/` todo dia.
- `APP_ENV=demo` traz os mesmos usuários de teste.
- Para recomeçar a demonstração: `docker compose -f docker-compose.prod.yml exec api python -m app.cli reset-demo --yes`.

Roteiro de apresentação: [`docs/DEMONSTRACAO.md`](docs/DEMONSTRACAO.md). Publicação num servidor, celular na rede local e backups: [`docs/PUBLICACAO.md`](docs/PUBLICACAO.md).

## Pontos sensíveis (escolas, creches, unidades de saúde)

O índice de risco multiplica por 1,5 as ocorrências a até 200 m desses pontos. Eles vêm do OpenStreetMap (Overpass) e são importados por comando, nunca a cada requisição:

```bash
docker compose exec api python -m app.cli import-sensitive-points
```

O comando pode ser agendado, por exemplo semanalmente. No Linux, com cron:

```
0 3 * * 1  cd /caminho/sentinela-urbano && docker compose exec -T api python -m app.cli import-sensitive-points
```

No Windows, use o Agendador de Tarefas com o mesmo comando.

## Setores e LIRAa

O índice por setor (sempre por 1.000 habitantes) e a comparação com o LIRAa precisam dos setores com população e dos resultados do levantamento. O ambiente de desenvolvimento já vem com **setores e LIRAa fictícios**, avisados nas telas. Para os dados reais da vigilância:

```bash
docker compose exec api python -m app.cli import-sectors setores.geojson --code-field codigo --name-field nome --population-field populacao
docker compose exec api python -m app.cli import-liraa liraa.csv
```

Modelos em [`docs/exemplos/`](docs/exemplos/). O gestor também pode enviar o CSV do LIRAa pela tela **LIRAa**.

## Grupo de mensagens (Telegram)

Além do e-mail, o setor recebe os avisos num grupo do Telegram: **na hora** para os casos de maior risco e num **resumo diário** para o restante, para o canal não virar spam. No desenvolvimento, o grupo é simulado no Mailpit (`MESSAGING_PROVIDER=email`).

Para usar o Telegram de verdade:

1. No Telegram, fale com o **@BotFather**, crie um bot (`/newbot`) e copie o token.
2. Adicione o bot ao grupo do setor e descubra o id do grupo (por exemplo, encaminhando uma mensagem do grupo para o @RawDataBot; o id começa com `-100`).
3. No `.env`: `MESSAGING_PROVIDER=telegram`, `TELEGRAM_BOT_TOKEN=...` e `MESSAGING_CHAT_ID=-100...`. Reinicie a API.
4. Agende o resumo diário, por exemplo às 7h: `docker compose exec -T api python -m app.cli send-digest`.

## Testes

```bash
docker compose exec api pytest
docker compose exec web npm test
```

## Estrutura

```
api/        FastAPI, modelos, migrations (Alembic), CLI e testes
web/        PWA React + Leaflet
db/init/    script que cria o banco de testes
docs/       documentos originais, transcrições e decisões
```
