# Sentinela Urbano

Plataforma de **vigilância comunitária de risco de arbovirose** (dengue, zika e chikungunya). Moradores registram focos com foto e localização; agentes de saúde atendem uma fila priorizada por risco real; a prefeitura é notificada e, quando não responde, o silêncio fica visível.

Projeto Integrador de Engenharia da Computação (ODS 3, meta 3.3). Os documentos-fonte estão em `docs/originais/`, com transcrições em `docs/transcricoes/`. **Em conflitos, prevalece `melhorias_sentinela_urbano`**. As decisões tomadas estão em `docs/decisoes.md`: leia esse arquivo antes de mudar regras de domínio.

## Stack

- **Web** (`web/`): React 19 + Vite + TypeScript, PWA (`vite-plugin-pwa`). Mapa com Leaflet 1.9 + react-leaflet 5 sobre OpenStreetMap; `leaflet.markercluster` para os pontos; `leaflet.heat` para o calor (fase 2). Testes com Vitest.
- **API** (`api/`): Python 3.12 + FastAPI + SQLAlchemy 2 + GeoAlchemy2 + Alembic, gerenciada com `uv`. Testes com pytest.
- **Banco**: PostgreSQL 16 + PostGIS 3. Pontos em `geography(Point, 4326)`; distâncias em metros via `geography` (`ST_DWithin`, `ST_Distance`).
- **Dev**: Docker Compose com `db`, `api`, `web` e `mailpit`.
- **Proibido**: Google Maps, Mapbox, app nativo.

## Comandos

```bash
docker compose up --build                                   # tudo; migra e faz o seed (dev) ao subir
docker compose exec api pytest                              # todos os testes da API (inclui PostGIS)
docker compose exec api alembic revision -m "descricao"     # nova migration (escrever à mão, revisar)
docker compose exec api alembic upgrade head
docker compose exec api python -m app.cli seed --dev --fake 60
docker compose exec api python -m app.cli create-user --name "Fulana" --email f@x.gov --role agente
docker compose exec api python -m app.cli retry-notifications
docker compose exec api python -m app.cli import-sensitive-points [--dry-run]   # agendável
docker compose exec api python -m app.cli import-sectors docs/exemplos/setores_exemplo.geojson [--replace]
docker compose exec api python -m app.cli import-liraa docs/exemplos/liraa_exemplo.csv
docker compose exec api python -m app.cli send-digest            # resumo diário ao grupo (agendável)
docker compose up -d --build --renew-anon-volumes web   # após adicionar dependência npm
```

Pilha de produção local (`docker-compose.prod.yml`, projeto `sentinela-producao`, https://localhost:8443, Mailpit 8026):

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api python -m app.cli reset-demo --yes   # recusado em produção
MSYS_NO_PATHCONV=1 docker compose -f docker-compose.prod.yml exec backup sh /backup.sh once
MSYS_NO_PATHCONV=1 docker compose -f docker-compose.prod.yml exec backup sh /backup.sh verify /backups/<arquivo>.dump
cd docs/fontes-pdf && node verifica-fase5.mjs && node medicao-desempenho.mjs   # checagens no navegador
```

Sem Docker, os testes puros rodam localmente (os de banco são pulados):

```bash
cd api && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd web && npm test && npm run typecheck && npm run build
```

URLs no dev: web http://localhost:5173 · API http://localhost:8000/api/docs · Mailpit http://localhost:8025

## Convenções

- **Código, identificadores, nomes de tabelas e colunas em inglês.** Interface, mensagens de erro da API, textos, commits de documentação e `docs/` em **português do Brasil**.
- Os valores dos enums de domínio ficam em pt-BR, porque são os termos do negócio: status `aberta`, `em_atendimento`, `resolvida_pelo_agente`, `confirmada`, `contestada`; perfis `morador`, `agente`, `gestor`. Os membros Python são em inglês (`OccurrenceStatus.OPEN`).
- Toda mudança de schema passa por migration Alembic em `api/migrations/versions/`. Nada de `create_all`.
- Coeficientes do risco e pesos ficam no banco (`risk_settings`, `occurrence_types.weight`), nunca fixos no código. O seed só insere o que falta.
- Python formatado pelo `ruff format` (linha de 100). TypeScript no modo `strict`.
- Os popups do Leaflet são montados com DOM/`textContent`, nunca com HTML vindo da API.
- `TERMS_VERSION` em `web/src/content/terms.ts` deve ser igual a `terms_version` em `api/app/config.py`.
- Arquivos com quebra de linha LF (`.gitattributes`). No Windows, evite gravar arquivos com `Path.write_text` do Python, que converte para CRLF.
- O container `web` tem `node_modules` próprio: depois de `npm install` de um pacote novo, rode o comando `--renew-anon-volumes` acima.
- Regras de transição de status ficam em `api/app/domain/status.py`; não mude `status` direto, use `app/services/workflow.py`.

## Regras do domínio

### Índice de risco (feito na fase 2: view `occurrence_risk`, migration 0002)
`risk = type_weight × days_open × recurrence_factor × proximity_factor`
- `days_open`: dias desde a abertura, mínimo `min_days_open` (1).
- `recurrence_factor = 1 + recurrence_increment (0,5) × ocorrências já resolvidas a até recurrence_radius_m (30 m)`.
- `proximity_factor = sensitive_proximity_factor (1,5)` se houver ponto sensível a até `sensitive_radius_m` (200 m) (`ST_DWithin`), senão 1.
- **Calcular na consulta** (view ou função SQL). Não persistir: o valor envelhece.
- A fila do agente é ordenada por risco, não por data. O mapa de calor é ponderado pelo risco, não pela contagem.
- **Denúncia falsa**: sem confirmação ("eu também vi") de **outro** morador com conta, o risco fica limitado a `unconfirmed_risk_cap`. Uma confirmação por usuário; o autor não confirma a própria; agente e gestor não confirmam.
- "Resolvida" (para reincidência e ponto crônico) = `resolvida_pelo_agente` ou `confirmada`. Contestada não conta.
- Desempate da fila: `risk` desc → `raw_risk` desc → mais antiga. Assim, as ocorrências presas no teto não ficam ordenadas só por data.
- O calor público soma o risco por célula da grade de privacidade (`/api/heatmap/public`), só das ocorrências ativas.

### Pontos crônicos (fase 2)
Uma nova ocorrência a até 30 m de outra já resolvida recebe `is_chronic` e alimenta o `recurrence_factor`. A partir de 3 reincidências, mostrar "notificar proprietário" em vez de "nova visita".

### Confirmação pelo morador (fase 2)
O agente encerra com **foto obrigatória**. Quem registrou (pela conta ou pelo link com token) responde uma única pergunta: "O problema foi realmente resolvido?" (sim → `confirmada`; não → `contestada`, que volta para a fila). Indicadores: taxa de resolução confirmada e taxa de fechamento contestado.

### Ausência de resposta da prefeitura (feito na fase 3)
E-mail ao endereço institucional (desde a fase 1). Contador público "X dias sem resposta" (`app/services/deadlines.py`), contado de `COALESCE(notified_at, created_at)` até `first_response_at`. Prazo `response_deadline_days` (15). Vencido o prazo e sem resposta, quem registrou (pela conta ou pelo token) baixa o PDF da ouvidoria (`app/services/ouvidoria_pdf.py`).

### Setores e LIRAa (feito na fase 3)
- Tabela `sectors` (MultiPolygon 4326 + população), importada por GeoJSON. As ocorrências entram nos setores por `ST_Covers` **na consulta**, sem guardar o setor na ocorrência.
- Todo índice por setor é **por 1.000 habitantes** (`app/services/indicators.py`). Nunca mostre contagem absoluta como ranking.
- O índice comunitário para o LIRAa é a soma dos pesos do tipo das ocorrências na janela `liraa_window_days` antes da data do levantamento. A concordância é medida por Spearman.
- A importação do CSV do LIRAa é tudo ou nada; o envio pela tela é só para o gestor.
- Os setores e o LIRAa do seed são **fictícios** (fonte "ficticio (seed)", período "…-fictício"); as telas avisam.

### Privacidade e LGPD (sempre)
- O mapa público recebe só a coordenada ajustada à grade de ~100 m (`app/services/privacy.py`), nunca endereço, foto, descrição ou autor. Filtros espaciais públicos operam sobre a coordenada **ajustada**.
- Coordenada exata: só agente, gestor e o próprio autor (conta ou token).
- Remover o EXIF de toda foto (`app/services/photos.py`). O formulário orienta a fotografar da via pública.
- Dados mínimos: conta = nome, e-mail, senha; registro sem conta = nome e contato opcionais. Termo de uso com versão aceita no cadastro.
- O token de acompanhamento vai no fragmento da URL (`#t=`) e no header `X-Tracking-Token`, nunca em query string. No banco fica só o hash.

### Área atendida
De início, **apenas Montes Claros (MG)**: `SERVICE_AREA_BBOX` (bbox do município, relação OSM 314620) e `SERVICE_AREA_NAME`. A API recusa pontos fora; o web lê a área em `GET /api/meta` para prender o mapa e validar o formulário. Centro padrão: Praça Doutor Chaves (`-16.7207,-43.8660`). Não fixar coordenadas de cidade no código fora dos padrões de configuração.

### OpenStreetMap
- A atribuição "© OpenStreetMap contributors" aparece sempre (`ensureOsmAttribution`).
- `VITE_TILE_URL` em variável de ambiente; `tile.openstreetmap.org` só no dev.
- Centro e zoom iniciais via `VITE_MAP_CENTER` e `VITE_MAP_ZOOM`.
- Pontos sensíveis vêm da Overpass (`amenity=school|kindergarten|hospital|clinic|doctors` e `healthcare=*`), importados para `sensitive_points` por comando agendável (fase 2). **Nunca consultar a Overpass por requisição.**
- Nominatim, se usado: cache, 1 req/s, User-Agent identificado.

### Fase 4 (feita): ampliações do backlog
- **Offline** (`web/src/lib/outbox.ts`): registro sem sinal fica no IndexedDB, com as fotos, e é enviado ao voltar a conexão. Cada envio leva `client_submission_id` (UUID gerado no aparelho; só o hash vai para o banco) e `observed_at`. Reenviar o mesmo id devolve o protocolo já criado, com token novo (`replayed: true`), sem duplicar. Registros guardados há mais de `OFFLINE_MAX_AGE_DAYS` (7) são recusados. Tipos e área atendida ficam em cache (`offlineCache.ts`).
- **Rota** (`/api/route`, `app/services/route.py`): pega as `route_max_stops` (12) de maior risco da fila do agente, já com o escopo aplicado, e as ordena pelo menor caminho a partir da posição dele (vizinho mais próximo + 2-opt, em linha reta).
- **Alerta de acúmulo** (`app/services/alerts.py`): `cluster_min_count` (3) ocorrências ativas do mesmo tipo a até `cluster_radius_m` (150 m) em `cluster_window_days` (7) → um alerta (e-mail aos gestores + grupo). Não repete na mesma área dentro da janela.
- **Prevenção**: `occurrence_types.prevention_tips`, preenchido pelo seed só quando vazio (o município pode reescrever). Aparece após o registro e em `/prevencao`.
- **Escopo do agente** (`app/services/scope.py`, tabelas `agent_sectors`/`agent_types`): vazio = sem restrição. Vale para fila, rota e mapa da equipe; o detalhe continua acessível pelos links dos e-mails. O gestor define na tela **Equipe**.
- **Grupo de mensagens** (`app/services/messaging.py`): `MESSAGING_PROVIDER` = none | telegram | email (no dev, simula o grupo no Mailpit). Na hora só se o risco inicial for ≥ `messaging_immediate_risk` (7,5); o resto vai no resumo diário (`send-digest`). O texto fica em `notifications.body` para o reenvio ser idêntico. Erros do Telegram nunca registram o token.

### Fase 5 (parte local feita): preparação para o piloto
- **`APP_ENV`** = development | demo | production. Em `production`, a API não sobe com configuração insegura (`production_problems` em `app/config.py`), esconde `/api/docs` e bloqueia `reset-demo`. Detalhes em `docs/PUBLICACAO.md`.
- **Contas** (`app/services/accounts.py`, migration 0005): redefinição de senha e convite por link de uso único (`password_tokens`, só o hash; link `/nova-senha#t=...`). `users.token_version` vai no JWT (`tv`): trocar a senha ou desativar a conta derruba as sessões. "Esqueci minha senha" responde igual exista ou não a conta.
- **LGPD**: `GET /api/me/data` (exportação) e `POST /api/me/delete` (só morador; as ocorrências ficam anonimizadas).
- **Limite de uso** (`app/ratelimit.py`): janela deslizante em memória, por IP, com 429 + `Retry-After`. Exige **um** processo da API. Desligado nos testes pelo fixture `settings`.
- **Configurações** (`/configuracoes`, só gestor): pesos e coeficientes com faixas validadas no servidor.
- **Caddy** (`deploy/Caddyfile`): HTTPS, proxy de `/api`, CSP e demais cabeçalhos. A API também envia cabeçalhos básicos (middleware `security_headers`).
- **Backup** (`deploy/backup.sh`): só considera pronto o dump completo e não vazio (grava `.part` e renomeia).

### Tipo "Outro risco"
- Tipo fixo com `occurrence_types.is_other` (código `other`, peso 2, último na lista). O morador descreve o risco em `occurrences.custom_type_label` (3 a 60 caracteres, sem telefone, e-mail ou link: `clean_custom_label`).
- A descrição **nunca** vai ao mapa público. Equipe e autor veem `Occurrence.type_label` ("Outro risco: …").
- Agente ou gestor reclassifica com `PUT /api/occurrences/{id}/type`, que apaga a descrição. O gestor vê as descrições agrupadas (`GET /api/settings/custom-labels`) e cria tipos oficiais (`POST /api/settings/types`, com `from_label` para mover os registros).
- "Outro" não gera alerta de acúmulo e não pode ser desativado. Testes: `test_custom_type.py`.

### Fora de escopo, não implementar
Aprendizado de máquina, integração com apps de trânsito, chat morador–agente, app nativo iOS, ranking/gamificação.

## Fases

- **Fase 1 (feita)**: monorepo, Compose, modelo e migrations, seed, API de ocorrências, mapa com cluster, formulário de registro, e-mail à prefeitura.
- **Fase 2 (feita)**: fila por risco, pontos crônicos, encerramento com foto, confirmação do morador, "eu também vi", mapa de calor por risco, importação de pontos sensíveis.
- **Fase 3 (feita)**: prazos, contador de dias sem resposta, PDF para a ouvidoria, setores, comparação com o LIRAa, painel de indicadores.
- **Fase 4 (feita)**: registro offline, rota de visita, alerta de acúmulo, prevenção, escopo do agente, grupo de mensagens (Telegram).
- **Fase 5 (parte local feita)**: pilha de produção com HTTPS e backup, limite de uso, contas (senha, convite, desativação), LGPD (exportar e excluir), configurações, guia de publicação. Falta o que depende de contratação: servidor, domínio, SMTP institucional, bot do Telegram, servidor de mapas.

Ao fim de cada fase: parar, listar o que foi feito e como testar, e esperar aprovação.

Testes obrigatórios: fórmula de risco e detecção de ponto crônico (`api/tests/test_risk.py`), ofuscação de coordenadas (`api/tests/test_privacy.py`). Fase 3: `test_phase3_pure.py` e `test_phase3_db.py`. Fase 4: `test_phase4_pure.py`, `test_phase4_db.py` e `web/src/lib/outbox.test.ts`. Fase 5: `test_phase5.py`. Tipo "Outro": `test_custom_type.py`.
