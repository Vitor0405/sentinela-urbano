# Apresentação v2

> Texto extraído de `originais/Sentinela Urbano v2.pptx`.

## slide1

PROJETO INTEGRADOR  
Sentinela Urbano  
Vigilância comunitária de risco de arbovirose, construída sobre registros feitos pelo próprio morador.  
INTEGRANTES  
João Vitor Rodrigues Alves Medeiros  
Israel Rodrigues de Souza Teles  
Luiz Gustavo Andrade França  
Samuel Silva Santos  
Vinicius Carvalho Fonseca  

## slide2

01 — INTRODUÇÃO  
Um risco que o morador vê antes de todo mundo  
O grupo escolheu a ODS 3, Saúde e Bem-Estar, e adotou a meta 3.3, que trata do combate às doenças tropicais negligenciadas e às doenças transmitidas pela água.  
Identificamos que quem enxerga primeiro o pneu com água, o terreno virando depósito de entulho ou o esgoto na rua é o próprio morador, mas essa informação raramente chegava ao poder público de forma utilizável.  
Os canais existentes exigiam ligação em horário comercial e não geravam registro com foto, coordenada ou protocolo.  
O agente de endemias fazia varredura por rotina, quarteirão por quarteirão, sem saber de antemão onde estavam os focos.  
Em 2024 o Brasil registrou cerca de 6,6 milhões de casos prováveis de dengue e 6.022 mortes, o pior resultado da série histórica.  

## slide3

02 — OBJETIVO  
O que será desenvolvido  
OBJETIVO GERAL  
Desenvolver uma aplicação web e mobile, no formato PWA, para registro colaborativo de riscos ambientais à saúde, com índice de risco por ocorrência, mapa público e alerta automático ao órgão responsável.  
Registrar a ocorrência com foto, coordenada e data em menos de um minuto.  
Calcular um índice de risco por ocorrência, em vez de simples densidade.  
Encaminhar o alerta ao setor competente e acompanhar o caso por protocolo.  
Validar o índice gerado pela comunidade contra o LIRAa do mesmo setor.  

## slide4

03 — JUSTIFICATIVA  
Por que o problema não é falta de informação  
A informação existe, mas dispersa  
Ela está com os moradores e não é coletada de forma organizada.  
Registro sem coordenada não vira rota  
O que existe hoje fica em papel ou planilha e por isso não vira mapa nem prioridade de visita.  
Sem retorno, o morador desiste  
Cada pessoa que avisa e não vê providência é uma pessoa a menos avisando no ano seguinte.  
A resposta reativa custa mais caro que a prevenção, em internação, em afastamento e em mutirão emergencial.  

## slide5

04 — METODOLOGIA  
Como o sistema será construído  
01  
Diagnóstico  
Conversas com agentes de endemias e com a Secretaria de Saúde.  
02  
Requisitos  
Tipos de ocorrência, protótipo de telas e modelagem do banco.  
03  
Desenvolvimento  
Formulário, mapa, painel do agente e módulo de alerta.  
04  
Validação  
Testes com moradores e agentes, com ajuste do que travar no uso.  
05  
Piloto  
Aplicação em área delimitada, com divulgação junto à escola, à UBS e à associação de moradores.  
STACK TÉCNICA  
PWA com registro offline, API REST, PostgreSQL com PostGIS, Leaflet sobre OpenStreetMap, notificação por SMTP e por API de mensagens.  

## slide6

05 — CRONOGRAMA  
Quando cada etapa acontece  
ETAPA  
PERÍODO  
ENTREGA  
Diagnóstico  
Fevereiro  
Relatório de levantamento  
Requisitos  
Março  
Protótipo e modelo de dados  
Desenvolvimento  
Abril a maio  
Versão mínima funcional  
Validação  
Junho  
Registro de ajustes  
Piloto  
Julho  
Área delimitada em operação  
Divulgação  
Agosto  
Material educativo aplicado  

## slide7

06 — ORÇAMENTO  
Quanto custa manter o sistema no ar  
CUSTO ZERO  
PostgreSQL e PostGIS  
Leaflet  
OpenStreetMap  
Dados do LIRAa  
Envio de mensagens  
CUSTO PREVISTO  
VALOR  
Hospedagem e banco, US$ 5 por mês em 12 meses  
R$ 330,00  
Domínio e material do piloto  
R$ 100,00  
Total  
R$ 430,00  

## slide8

07 — REFERENCIAL  
Referencial  
NAÇÕES UNIDAS BRASIL. Objetivo de Desenvolvimento Sustentável 3: Saúde e Bem-Estar. Disponível em: brasil.un.org/pt-br/sdgs/3.  
BRASIL. Ministério da Saúde. Levantamento Rápido de Índices para Aedes aegypti (LIRAa). Disponível em: gov.br/saude.  
PODER360. Dengue bate recorde em 2024 com 6,6 mi de casos e 6.022 mortes. Dados do Ministério da Saúde.  
AGÊNCIA BRASIL. Casos de dengue no Brasil caem 75% em 2026. Publicado em 15 abr. 2026. Dados do Ministério da Saúde.  

