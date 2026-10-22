# Decisões de projeto

Registro das decisões tomadas onde os documentos (`originais/`) e o prompt de desenvolvimento divergiam ou eram omissos. Ordem de precedência: **melhorias > prompt > projeto original/backlog**.

## Stack

O projeto original define apenas PWA, API REST, PostgreSQL + PostGIS e Leaflet + OpenStreetMap. A stack do prompt (FastAPI, React + Vite, PostGIS 3, Docker Compose) é compatível, então não há divergência.

## Tipos de ocorrência e pesos

Ficam os oito tipos do original (backlog, história 3). Pela melhoria 6, o produto é apresentado como vigilância de **arbovirose** e os demais tipos aparecem como fatores de risco ambiental associados. O campo `is_breeding_site` marca os tipos que são criadouro em potencial.

| Código | Tipo | Peso inicial | Setor de destino |
|---|---|---|---|
| standing_water | Água parada | 5 | Vigilância em Saúde – Controle de Endemias |
| trash_rubble | Lixo e entulho | 3 | Limpeza Urbana |
| water_leak | Vazamento de água | 3 | Saneamento – Abastecimento de Água |
| vacant_lot | Terreno baldio abandonado | 2 | Fiscalização de Posturas |
| open_sewage | Esgoto a céu aberto | 2 | Saneamento – Esgotamento Sanitário |
| dead_animal | Animal morto | 1 | Vigilância em Saúde – Zoonoses |
| rodents_scorpions | Foco de roedores ou escorpiões | 1 | Vigilância em Saúde – Zoonoses |
| waste_burning | Queima de resíduos | 1 | Meio Ambiente |

Os pesos e os setores ficam no banco (`occurrence_types`). O seed só insere o que falta, então ajustes feitos depois não são sobrescritos. **Validar os pesos com a vigilância municipal antes do piloto.**

## Identidade do morador: modelo híbrido

- O backlog (histórias 1 e 4) pede registro **sem conta**, com opção anônima e acompanhamento pelo protocolo.
- O prompt pede e-mail + senha.
- As melhorias exigem "uma confirmação por usuário" e uma pergunta ao "morador que registrou".

Decisão:

- **Registro sem conta** é permitido. A pessoa escolhe entre anônimo ou informar só nome e contato (LGPD). Ela recebe o **protocolo** e um **link privado de acompanhamento**: o token vai no fragmento `#t=`, que o navegador nunca envia ao servidor, e só o hash SHA-256 fica no banco. Esse link é o que permite responder "o problema foi realmente resolvido?" (fase 2).
- **Conta** (e-mail + senha, JWT) é opcional para o morador e obrigatória para agente e gestor. **"Eu também vi" exige conta**, para garantir uma confirmação por usuário (mitigação de denúncia falsa).
- Com conta, o morador também pode marcar a ocorrência como anônima: ela fica vinculada à conta, mas agente e gestor não veem quem registrou.
- Agentes e gestores são criados pela CLI (`create-user`). O cadastro público sempre cria o perfil morador.

## Status

O fluxo é o do prompt: `aberta → em_atendimento → resolvida_pelo_agente → confirmada | contestada`, e a contestada volta para a fila.

O estado "encaminhada" do original não virou status. Ele virou duas colunas:

- `notified_at`: quando o e-mail à prefeitura foi enviado.
- `first_response_at`: a primeira ação de um agente ou gestor.

O contador público "X dias sem resposta" (fase 3) é calculado a partir delas.

## Notificação à prefeitura

A notificação por e-mail entrou já na **fase 1**: o item 4 do prompt a exige, mas ela não aparecia em nenhuma fase. Funciona com uma tabela `notifications` (padrão outbox):

- O registro da notificação é criado na mesma transação da ocorrência.
- O envio acontece em background.
- Falhas ficam gravadas, e `python -m app.cli retry-notifications` reenvia (backlog, história 9).

O e-mail leva a coordenada **exata**, porque a prefeitura é o órgão que vai agir. O envio por WhatsApp/Telegram do original ficou fora do escopo atual.

## Privacidade no mapa público

- A coordenada é ajustada para o centro de uma **grade determinística de ~100 m**. Ruído aleatório permitiria tirar a média de vários registros do mesmo ponto e chegar perto da posição real; a grade revela sempre a mesma célula.
- A grade usa uma latitude de referência fixa (`PRIVACY_GRID_REF_LAT`), para não "andar" com o tempo.
- O **filtro por bbox** do endpoint público trabalha sobre a coordenada **já ajustada**. Filtrar pela coordenada exata deixaria bboxes minúsculos revelarem o ponto real. Há teste cobrindo isso.
- O mapa público **não mostra foto, descrição nem autor**: uma fachada ou um texto livre pode identificar o endereço. Fotos só vão para agente, gestor e quem registrou (por conta ou pelo link).
- Fotos são decodificadas e regravadas como JPEG novo. Todo o EXIF (GPS, aparelho, data) é descartado depois de aplicar a rotação.
- Geocodificação reversa (Nominatim) **não é usada**, porque o sistema não exibe endereço. Se vier a ser usada, deve ter cache, limite de 1 requisição/s e User-Agent identificado.

## Município do piloto

De início, o sistema atende **apenas Montes Claros (MG)** (decisão da equipe em 2026-10-07).

- **Área atendida:** retângulo envolvente do município no OpenStreetMap (relação 314620, distritos rurais incluídos): `-44.2107,-17.1458,-43.6665,-16.0845`, em `SERVICE_AREA_BBOX` / `SERVICE_AREA_NAME`.
  - A API recusa registros fora dela.
  - O formulário avisa antes do envio, inclusive quando o GPS indica um ponto fora da cidade.
  - O mapa fica preso à região.
  - O frontend lê a área em `GET /api/meta`, então a API é a fonte única.
- **Limitação:** o retângulo inclui pedaços dos municípios vizinhos nas bordas. Quando a tabela `sectors` chegar (fase 3), a verificação pode passar a usar o polígono real do município.
- **Centro do mapa e seed fictício:** Praça Doutor Chaves, no Centro (`-16.7207,-43.8660`).
- **Grade de privacidade:** `PRIVACY_GRID_REF_LAT=-16.72`.
- **Para levar a outro município:** basta trocar essas variáveis, sem mudar código.

## Do backlog original, fora das três fases

Ficaram de fora:

- Registro offline com sincronização (história 11).
- Sugestão de rota (13).
- Alerta de acúmulo por área (10).
- Conteúdo de prevenção (14).
- Restrição de tipos e região por agente (6).
- Exportação CSV (12).
- Envio por API de mensagens.

O PWA já é instalável e guarda o shell em cache, mas não enfileira registros offline. Esses itens podem entrar depois da fase 3, se aprovado.

## Coeficientes (tabela `risk_settings`)

| Chave | Valor | Uso |
|---|---|---|
| min_days_open | 1 | dias mínimos na fórmula |
| recurrence_increment | 0,5 | fator de reincidência = 1 + 0,5 × resolvidas no mesmo ponto |
| recurrence_radius_m | 30 | raio de "mesmo ponto" |
| chronic_radius_m | 30 | raio do ponto crônico |
| chronic_owner_notice_threshold | 3 | a partir daqui, "notificar proprietário" |
| sensitive_proximity_factor | 1,5 | fator de proximidade |
| sensitive_radius_m | 200 | raio de busca de pontos sensíveis |
| unconfirmed_risk_cap | 15 | teto de risco sem "eu também vi" (provisório, revisar na fase 2) |
| response_deadline_days | 15 | prazo para a prefeitura (fase 3) |

## Fase 2: risco, pontos crônicos e confirmação

- **Onde o risco é calculado:** na view SQL `occurrence_risk` (migration 0002), a cada consulta. Nada é gravado. Os coeficientes vêm de `risk_settings`, com os padrões do seed como reserva.
- **O que conta como "resolvida"** na reincidência e no ponto crônico: `resolvida_pelo_agente` e `confirmada`. Contestada não conta (o morador disse que não foi resolvido). Uma ocorrência aberta vizinha também não conta: ela é duplicada, não reincidência.
- **Desempate da fila:** a ordem é risco, depois risco bruto (sem o teto), depois a mais antiga. Sem esse desempate, como quase tudo começa sem confirmação e fica preso no teto, a fila viraria uma lista por data.
- **Teto sem confirmação:** `unconfirmed_risk_cap` = 15 (equivale a água parada há 3 dias). O valor é provisório e deve ser calibrado com a vigilância durante o piloto.
- **"Eu também vi":** exige conta de morador, vale uma vez por pessoa e por ocorrência, e não vale para quem registrou. Agentes e gestores não confirmam. Só ocorrências ativas podem ser confirmadas.
- **Encerramento:**
  - Foto obrigatória. O agente pode encerrar a partir de `aberta`, `em_atendimento` ou `contestada`, para quando resolve na própria visita.
  - Qualquer ação da equipe preenche `first_response_at`, que será a "resposta da prefeitura" na fase 3.
- **Pergunta ao morador** ("o problema foi realmente resolvido?"):
  - Fica sempre na página de acompanhamento.
  - Também vai por e-mail quando há um endereço: o da conta, ou o contato informado por um visitante.
  - O e-mail do visitante leva um **segundo token** (`feedback_token_hash`), porque o token original não fica guardado em texto. O link com esse token fica na fila de envio só até o e-mail sair e depois é apagado.
  - Quem registrou anonimamente e sem contato vê a pergunta apenas pelo link guardado.
  - A resposta é única por encerramento. Se for contestada, a ocorrência volta para a fila; ao ser encerrada de novo, a pergunta é feita outra vez.
- **Indicadores** (`/api/stats/resolution`): taxa de resolução confirmada = confirmações ÷ encerramentos; taxa de fechamento contestado = contestações ÷ encerramentos. São contados sobre as transições do histórico. O painel completo fica para a fase 3.
- **Mapa de calor:** soma o risco das ocorrências ativas por célula da grade de 100 m, então segue a mesma regra de privacidade do mapa público.
- **Pontos sensíveis:**
  - Importados da Overpass pela **área do município** (relação OSM 314620), que é mais leve e mais exata que o retângulo. O retângulo fica como alternativa.
  - Usa tags exatas, tenta de novo quando recebe 429/5xx e identifica a aplicação no User-Agent.
  - Uma resposta vazia não apaga nada.
  - Atenção: `healthcare=*` (pedido no prompt) também traz farmácias e consultórios odontológicos. Na primeira importação foram 15 farmácias e 2 dentistas, de 148 pontos. Se a vigilância achar que farmácia não deve pesar no risco, basta filtrar esses valores no import.

## Fase 3: prazos, ouvidoria, setores e LIRAa

- **"Dias sem resposta":**
  - O contador começa no aviso por e-mail à prefeitura (`notified_at`). Se o e-mail ainda não saiu, começa no registro, porque a ocorrência já é pública desde então.
  - Ele para na primeira ação de um agente ou gestor (`first_response_at`).
  - Passado `response_deadline_days` (15), a ocorrência fica **vencida**: o número aparece em vermelho no mapa público e na página de acompanhamento.
  - "Resposta" é a primeira ação da equipe, não a resolução. Uma prefeitura que inicia o atendimento e o abandona aparece pelos indicadores de tempo até a resolução, não pelo contador.
- **PDF para a ouvidoria** (`/api/tracking/{protocolo}/ouvidoria.pdf`):
  - É gerado no servidor com reportlab e liberado **só para quem registrou** (pela conta ou pelo link), **só com o prazo vencido e só se não houve resposta**.
  - Traz protocolo, tipo, setor responsável, datas, coordenada exata com link do OpenStreetMap, até 3 fotos, histórico e um texto de solicitação, com espaço para nome e assinatura. O nome vem preenchido se a pessoa se identificou.
  - Não é gravado em lugar nenhum.
- **Setores:**
  - Tabela `sectors` (polígono `MultiPolygon` em 4326, população > 0). A importação é feita por GeoJSON (`import-sectors`), com geometria corrigida por `ST_MakeValid`.
  - As ocorrências são atribuídas aos setores **na consulta** (`ST_Covers`), sem guardar o setor na ocorrência. Assim, trocar os setores não exige migrar dados.
  - Não existem setores reais de Montes Claros no repositório. O seed cria **16 setores fictícios** (grade de cerca de 10 km, códigos `F01` a `F16`, fonte "ficticio (seed)") e um ciclo de LIRAa fictício e aleatório. As telas avisam quando os dados são fictícios.
  - Para uso real, importe os estratos do LIRAa da vigilância ou os setores censitários do IBGE (Censo 2022) com a população.
- **Índices por setor** (sempre por 1.000 habitantes):
  - **Risco atual** (painel): soma do risco (view `occurrence_risk`) das ocorrências ativas.
  - **Índice comunitário** (comparação com o LIRAa): soma dos **pesos do tipo** das ocorrências registradas nos `liraa_window_days` (60) dias antes da data do levantamento. Usa a mesma janela de tempo do LIRAa e pondera pelo quanto cada tipo favorece o mosquito. O risco não é usado aqui porque depende de "dias em aberto", que não faz sentido para um levantamento passado.
  - **Concordância:** correlação de Spearman (postos), com interpretação em texto e aviso de cautela quando há menos de 10 setores. A tabela destaca os setores em que as posições divergem muito, candidatos a sub-registro.
- **CSV do LIRAa:**
  - Colunas `setor;periodo;data;iip;ib` (`ib` opcional), com `;` ou `,`, vírgula decimal, datas `dd/mm/aaaa` ou ISO, nomes de coluna sem diferenciar acento ou maiúsculas.
  - **Tudo ou nada**: qualquer linha com erro, ou setor não cadastrado, recusa o arquivo inteiro e lista os erros com o número da linha.
  - Reimportar o mesmo setor e período atualiza o registro, em vez de duplicar.
  - Classes do Ministério da Saúde: IIP < 1% satisfatório, de 1 a 3,9% alerta, ≥ 4% risco.
  - O envio pela tela é só para o **gestor**; a comparação pode ser vista por agentes e gestores.
- **Painel** (`/api/indicators`, padrão últimos 90 dias): registradas no período, por tipo e por situação; sem resposta além do prazo; mediana e média até a primeira resposta e até a resolução; taxas de resolução confirmada e de fechamento contestado; ranking dos setores por risco por 1.000 habitantes; exportação CSV (backlog, história 12).
- **Correções feitas nesta fase:**
  - Ao abrir um popup, o mapa se desloca, recarrega as ocorrências e recriava todos os marcadores, fechando o popup. O `ClusterLayer` agora atualiza só o que mudou.
  - O marcador aproximado usava borda tracejada, que parecia uma engrenagem; virou um halo suave.
  - O calor ficava fraco demais; ganhou raio e intensidade mínima maiores.

## Fase 4: ampliações do backlog

- **Registro offline (história 11):**
  - O registro sem sinal fica no IndexedDB do celular, com as fotos, e é enviado sozinho quando a conexão volta. O envio acontece no evento `online`, ao abrir o app e a cada 60 s enquanto houver pendências.
  - Para não duplicar quando a resposta se perde, cada registro leva um `client_submission_id` aleatório, gerado no aparelho. O banco guarda só o hash. Um reenvio com o mesmo id devolve o protocolo já criado, com um token de acompanhamento novo, porque o primeiro nunca chegou ao morador.
  - Erros de conexão ou do servidor (0, 408, 429, 5xx) deixam o registro pendente. Recusas definitivas (por exemplo, ponto fora do município) marcam como "não aceito", com o motivo e a opção de tentar de novo ou descartar.
  - O momento em que o morador viu o problema vai em `observed_at`; a contagem de dias continua a partir da chegada ao servidor (`created_at`), que é quando a prefeitura pode saber. Registros guardados há mais de 7 dias são recusados, para não acionar a equipe por uma foto velha.
  - Tipos de risco e área atendida ficam em cache para o formulário abrir sem sinal. O mapa base pode não carregar offline, mas o GPS e o toque no mapa continuam funcionando.
- **Rota de visita (história 13):** primeiro escolhe *quais* paradas (as 12 de maior risco da fila do agente) e depois *em que ordem* (menor caminho a partir da posição atual: vizinho mais próximo + 2-opt). Assim a proximidade nunca passa por cima do risco. As distâncias são em linha reta; um roteador de ruas (OSRM) fica como melhoria futura. Ao remover uma parada, a próxima de maior risco entra no lugar.
- **Alerta de acúmulo (história 10):** 3 ocorrências ativas do mesmo tipo a até 150 m, em 7 dias (configurável), geram um alerta com o centro do grupo, a quantidade e o período. Vai por e-mail a todos os gestores e ao grupo de mensagens, e aparece no painel. Enquanto houver um alerta recente do mesmo tipo cobrindo o ponto, novos registros ali não geram outro.
- **Prevenção (história 14):** texto curto por tipo, em linguagem simples, em `occurrence_types.prevention_tips`. O seed só preenche se estiver vazio, para o município poder reescrever. Aparece depois do registro (inclusive offline) e na seção fixa **Prevenção**, que também funciona sem sinal. **Revisar os textos com a vigilância antes do piloto.**
- **Escopo do agente (história 6):** o gestor marca setores e tipos por agente na tela **Equipe**. Sem marcação, o agente vê tudo, para um agente novo nunca ficar com a fila vazia por engano. O escopo vale para fila, rota e mapa da equipe. O detalhe de uma ocorrência continua acessível a qualquer agente, porque os e-mails e o grupo levam links diretos. O encerramento automático de sessões inativas já é coberto pela expiração do login (12 h).
- **Grupo de mensagens:**
  - O canal é o **Telegram**: o bot é gratuito e sai em minutos. O WhatsApp Business exige conta empresarial verificada e cobra por conversa. A estrutura (`MESSAGING_PROVIDER`) permite incluir outro canal depois.
  - Regra do projeto original para não virar spam: aviso **imediato** só quando o risco inicial for ≥ 7,5 (por exemplo, água parada perto de escola, ou num ponto que já foi resolvido); o restante vai no **resumo diário** (`send-digest`, agendável). Alertas de acúmulo também vão ao grupo.
  - Na migração, as ocorrências já existentes foram marcadas como enviadas, para o primeiro resumo não despejar o histórico.
  - O e-mail à prefeitura continua saindo para todas as ocorrências, porque é ele que inicia a contagem de "dias sem resposta".

## Fase 5: preparação para o piloto (parte local)

O que dá para fazer sem contratar nada foi feito e testado na própria máquina. O que depende de servidor, domínio ou contas externas ficou documentado em `docs/PUBLICACAO.md`.

- **Pilha de produção local** (`docker-compose.prod.yml`): PWA compilado servido pelo **Caddy**, que faz o HTTPS sozinho (certificado local agora, Let's Encrypt no domínio real) e a CSP. Foi escolhido no lugar do Nginx + Certbot por ter menos peças. A API não tem porta pública e roda com um processo só.
- **`APP_ENV`**: o modo `production` recusa subir com o segredo padrão do JWT, e-mails `.test`, endereço sem HTTPS, CORS em localhost ou SMTP do Mailpit. Erro de configuração vira falha na subida, não um sistema inseguro no ar.
- **Contas de equipe:** o gestor convida agentes por e-mail, e o link de uso único (3 dias) leva à criação da senha. A senha nunca passa pelo gestor. Desativar não apaga: preserva o histórico de atendimentos. Trocar a senha ou desativar a conta derruba todas as sessões, por meio de um contador no JWT, sem lista negra de tokens.
- **Esqueci minha senha:** link de uso único, no fragmento da URL (como o token de acompanhamento). A resposta é a mesma exista ou não a conta, para não revelar quem está cadastrado.
- **LGPD:** o morador baixa seus dados (JSON) e exclui a conta, com a senha. As ocorrências não são apagadas, e sim **anonimizadas**: o foco continua sendo um risco real na cidade e faz parte do histórico da vigilância. Agentes e gestores não se excluem pela tela; são desativados pelo gestor.
- **Limite de uso:** janela deslizante em memória, por IP, nos pontos abertos ao público (registro, "eu também vi", cadastro, login, senha). Sem Redis, porque o piloto roda num processo só. Ao escalar, trocar o armazenamento.
- **Configurações pela tela:** pesos e coeficientes podem ser ajustados pelo gestor dentro de faixas validadas no servidor, para a calibragem com a vigilância não depender de programador.
- **Backup:** `pg_dump` diário + fotos, guardando 14 cópias. Na primeira versão, um dump vazio feito antes de o banco ficar pronto foi registrado como sucesso. Corrigido: o script espera o banco, grava `.part` e só renomeia se o arquivo estiver completo. A restauração é testada num banco à parte (`verify`).
- **Mapa bloqueado na pilha de produção:** o Caddy mandava `Referrer-Policy: no-referrer`, e os servidores de tiles do OpenStreetMap trocam por uma imagem "Access blocked" todo pedido sem `Referer`. Agora é `strict-origin-when-cross-origin`: o OSM recebe só a origem do site (`https://dominio/`), nunca o caminho da página. A API continua com `no-referrer`, porque só devolve JSON.
- **Offline no primeiro uso:** se o morador nunca tivesse aberto o formulário com sinal, ele abria sem tipos de risco. O app agora carrega o cache de tipos e da área atendida ao iniciar.
- **Acessibilidade:** a medição automatizada (`docs/fontes-pdf/medicao-desempenho.mjs`) achou campos sem rótulo no registro e o mapa sem título de página; os dois foram corrigidos. O Lighthouse não pôde ser instalado nesta máquina (falha de certificado do npm) e fica para o servidor.
- **Fora do que dá para fazer localmente** (aguardando autorização ou contratação): túnel público para teste externo, download dos dados de mapa para um servidor de tiles próprio, bot real do Telegram (precisa do token do responsável), domínio, hospedagem e SMTP institucional.

## Tipo de risco "Outro" (pedido de 21/10/2026)

O morador precisava registrar um risco que não está na lista. A pergunta era como fazer isso sem deixar qualquer pessoa criar categorias no sistema.

- **O morador descreve; a equipe classifica.** Há um tipo fixo "Outro risco" (o último da lista). Ao escolhê-lo, o morador escreve o risco em até 60 caracteres. O morador não cria tipos oficiais, porque um tipo tem peso no índice e setor de destino na prefeitura, e categorias abertas virariam spam ou ofensa no mapa.
- **Peso 2 até alguém olhar.** É o peso de terreno baldio e esgoto: o registro entra na fila sem passar na frente da água parada. Vai para "Vigilância em Saúde – Triagem". Os dois valores podem ser ajustados em Configurações. O teto sem confirmação ("eu também vi") vale como para qualquer tipo.
- **Privacidade:**
  - a descrição não aparece no mapa público, que mostra só "Outro risco";
  - a equipe e o autor veem "Outro risco: caixa de isopor com água";
  - telefone, e-mail e link são recusados na descrição, no app e na API.
- **Reclassificação:** agente ou gestor escolhe o tipo certo na tela da ocorrência. O risco passa a usar o novo peso na hora, porque é calculado na consulta. A descrição é apagada, porque deixou de ser "Outro".
- **Novo tipo oficial:** em Configurações, as descrições aparecem agrupadas (sem diferenciar maiúsculas e espaços) com a contagem. A gestora cria o tipo a partir de uma delas e, se quiser, move de uma vez os registros descritos assim. O tipo novo entra antes de "Outro" no formulário. Nome e descrição podem ser corrigidos depois. Um tipo pode ser desativado: sai do formulário, mas os registros mantêm o tipo e o risco. "Outro risco" não pode ser desativado.
- **Alerta de acúmulo:** "Outro" não dispara. Três registros de "Outro" juntos podem ser coisas diferentes.
- **Contas novas são de morador.** O cadastro aberto ao público sempre cria morador. Agente e gestor entram por convite do gestor (Gestão → Equipe), para ninguém se dar acesso à fila, aos dados exatos e às configurações sozinho.
