# Roteiro de demonstração

Apresentação de cerca de 15 minutos, usando a pilha de produção local (HTTPS, PWA compilado e backups) com dados fictícios de Montes Claros (MG).

## Antes de começar (5 minutos antes)

```bash
docker compose -f docker-compose.prod.yml up -d --build
# dados limpos: desfaz cadastros, senhas trocadas e registros de ensaios anteriores
docker compose -f docker-compose.prod.yml exec api python -m app.cli reset-demo --yes
```

Deixe abertas três janelas (uma anônima para cada perfil, para as sessões não se misturarem):

| Janela | Endereço | Quem |
|---|---|---|
| 1 | https://localhost:8443 | morador (`morador@sentinela.test`) |
| 2 | https://localhost:8443/entrar | agente (`agente@sentinela.test`) |
| 3 | https://localhost:8443/entrar | gestora (`gestor@sentinela.test`) |
| 4 | http://localhost:8026 | Mailpit: a "caixa de entrada" da prefeitura e dos usuários |

A senha de todos é `sentinela123` (`SEED_PASSWORD`). Na primeira abertura, o navegador avisa que o certificado é local. Aceite: ele é emitido pelo próprio Caddy, só para esta máquina.

Para mostrar no celular, siga a seção 5 de [`PUBLICACAO.md`](PUBLICACAO.md) antes.

## 1. O problema e o mapa público (2 min) · janela 1, sem login

- Mapa de Montes Claros com os focos agrupados. O mapa não sai do município.
- Clique num ponto: só aparecem o tipo, a situação e há quantos dias está sem resposta. Nunca aparecem endereço, foto ou autor.
- A posição é **aproximada** (grade de ~100 m), para proteger quem denunciou.
- Troque para **Calor**: a cor é ponderada pelo **risco**, não pela quantidade.

## 2. Registrar um foco (3 min) · janela 1, logado como morador

1. **Registrar** → foto → tipo (por exemplo, "Água parada") → "Usar minha localização" ou toque no mapa → enviar.
2. A tela mostra o protocolo, o link de acompanhamento e as **dicas de prevenção** daquele tipo.
3. No Mailpit (janela 4), aparece o e-mail para a vigilância da prefeitura. É ele que começa a contar os "dias sem resposta".
4. **Offline:** nas ferramentas do navegador (F12 → Rede → Offline), registre outro foco. Aparece o aviso "1 pendente" no topo (tela **Envios deste aparelho**) e o registro sobe sozinho quando a rede volta, sem duplicar.
5. **Prevenção:** a página fica disponível mesmo sem sinal.
6. **Risco fora da lista:** no passo 2, escolha **Outro risco** e escreva, por exemplo, "caixa de isopor com água". Sem descrição, o envio é recusado. No mapa público aparece só "Outro risco"; a descrição fica para a equipe.

## 3. O trabalho do agente (3 min) · janela 2

1. **Fila:** ordenada por **risco**, não por data. Mostre um item com selo "crônico" (ponto que já foi resolvido e voltou) e um perto de escola (fator 1,5).
2. Um registro sem confirmação de outro morador fica limitado no teto (proteção contra denúncia falsa). Com "eu também vi", ele sobe.
3. **Rota:** as 12 paradas de maior risco, na ordem do menor caminho a partir de onde o agente está.
4. Abra uma ocorrência → "Iniciar atendimento" → "Encerrar com foto": a foto é **obrigatória**. Quem registrou recebe a pergunta "O problema foi realmente resolvido?". Se responder não, a ocorrência volta para a fila.

## 4. A visão da gestão (3 min) · janela 3

1. **Painel:** registros por tipo e situação, prazos vencidos, tempo até a primeira resposta e até a resolução, taxa de resolução confirmada e o **alerta de acúmulo** (3 focos do mesmo tipo a até 150 m em 7 dias). O alerta também foi por e-mail e para o grupo (no Mailpit).
2. **LIRAa:** índice comunitário por setor, por 1.000 habitantes, comparado com o levantamento oficial (correlação de Spearman). Os setores e o LIRAa da demonstração são **fictícios**, e a tela avisa.
3. **Gestão → Equipe:**
   - convide um agente: o e-mail chega no Mailpit, com link de uso único para criar a senha;
   - defina setores e tipos de um agente;
   - desative alguém: a sessão dele cai na hora.
4. **Gestão → Configurações:** pesos dos tipos e coeficientes do risco, sem mexer no código.
5. **Riscos descritos pelos moradores** (fim de Configurações): as descrições de "Outro risco" agrupadas. Em "Criar tipo", a gestora transforma uma descrição recorrente em tipo oficial (nome, peso, setor) e move os registros para ele. O tipo novo aparece na hora no formulário. Na ocorrência, o agente também pode reclassificar um caso isolado (cartão **Classificação**).

## 5. Quando a prefeitura não responde (1 min)

Em **Acompanhar**, uma ocorrência com prazo vencido mostra o contador "X dias sem resposta" e o botão para baixar o **PDF para a ouvidoria**, já preenchido com protocolo, datas e fotos.

## 6. Privacidade e segurança (1 min) · janela 1

- **Minha conta:** trocar senha, **baixar meus dados** (JSON) e **excluir conta**. As ocorrências ficam anonimizadas, porque o foco continua existindo.
- "Esqueci minha senha": o link chega no Mailpit e vale uma vez só.
- A foto perde o EXIF (a localização gravada pelo celular).
- HTTPS com cabeçalhos de segurança e limite de tentativas no login e nos registros.

## Depois da apresentação

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.cli reset-demo --yes   # deixa pronto para a próxima
docker compose -f docker-compose.prod.yml down                                           # desliga (os dados ficam)
```

## Se algo der errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Página não abre em https://localhost:8443 | pilha desligada | `docker compose -f docker-compose.prod.yml up -d` |
| Login de um usuário de teste falha | senha trocada num ensaio | `reset-demo --yes` |
| "Muitas tentativas" (429) | limite de uso atingido nos ensaios | aguarde ou reinicie a API: `docker compose -f docker-compose.prod.yml restart api` |
| Mapa cinza, sem ruas | sem internet (os tiles vêm do OpenStreetMap) | os pontos e o registro continuam funcionando |
| E-mail não aparece | Mailpit errado | a pilha de produção usa a porta **8026**, não 8025 |
