# Projeto original (ODS 3)

> Transcrição automática de `originais/ODS3_Sentinela_Urbano.pdf` (pdftotext). Em caso de dúvida, o PDF é a fonte.

```text
                                                                PROJETO INTEGRADOR

                          Sentinela Urbano

                Registro colaborativo de riscos ambientais à saúde, com mapa de calor
                                        e alerta automático à prefeitura

                                          Engenharia da Computação

                                          João Vitor Rodrigues Alves Medeiros
                                               Luiz Gustavo Andrade França
                                                 Vinicius Carvalho Fonseca
                                              Israel Rodrigues de Souza Teles
                                                     Samuel Silva Santos

1 ODS e meta escolhidas

O grupo escolheu a ODS 3, Saúde e Bem-Estar, cujo enunciado é assegurar uma vida saudável e
promover o bem-estar para todos, em todas as idades. A meta que orienta o trabalho é a 3.3:

             “Até 2030, acabar com as epidemias de AIDS, tuberculose, malária e doenças tropicais
             negligenciadas, e combater a hepatite, doenças transmitidas pela água, e outras doenças
             transmissíveis.”
Dengue, zika e chikungunya entram nessa meta como doenças tropicais negligenciadas, e a
leptospirose como doença transmitida pela água. Todas têm em comum o fato de dependerem de
condições ambientais do próprio bairro para acontecer, o que abre espaço para uma intervenção
local.
       Como decidimos ampliar o escopo para além dos criadouros do mosquito, duas metas
aparecem em segundo plano. A meta 3.9, que trata de reduzir mortes e doenças causadas por
contaminação e poluição do ar, da água e do solo, cobre os registros de lixo acumulado, entulho e
esgoto a céu aberto. A meta 3.d, que fala em reforçar a capacidade de alerta precoce e de
gerenciamento de riscos de saúde, descreve bem o que o sistema faz: avisar antes, e não depois.

2 O problema

Qual o problema concreto identificado?
Quem enxerga primeiro o pneu com água no quintal do vizinho, o terreno baldio virando depósito
de entulho ou o esgoto correndo na rua é o morador. Essa informação, porém, raramente chega ao
poder público de um jeito que possa ser usado. Os canais existentes hoje (telefone da ouvidoria,
atendimento presencial na secretaria, visita eventual do agente de endemias) exigem ligar em
horário comercial, descrever o endereço de viva-voz e confiar que alguém vai anotar. Não fica
registro com localização exata, não há foto, não há protocolo e o morador nunca sabe se o caso foi
atendido.

                                                                      1
        Do outro lado, o agente de combate a endemias faz varredura por rotina, quarteirão por
quarteirão, sem saber de antemão onde estão os focos. Ele passa por dezenas de casas sem problema
algum e só chega ao terreno crítico semanas depois, quando o criadouro já produziu várias gerações
de mosquito. O problema, portanto, não é falta de informação: é que a informação existe espalhada
entre os moradores e não é coletada de forma organizada.

Quem é afetado?
A população do bairro em primeiro lugar, com peso maior sobre crianças, idosos, gestantes e
pessoas com doenças crônicas, que são justamente quem evolui para os quadros graves de dengue.
Também são afetados os agentes de endemias e os agentes comunitários de saúde, que gastam
tempo e deslocamento em áreas sem foco; a rede pública de atendimento, que lota nos meses de
pico; e a gestão municipal, que acaba investindo em campanha genérica por não ter dado fino sobre
onde agir. O impacto é maior em bairros com coleta de lixo irregular e abastecimento de água
intermitente, onde guardar água em casa é necessidade e não descuido.

Quais são as causas?
Há causas estruturais que fogem ao alcance de um projeto de curso: saneamento precário, coleta de
resíduos irregular, abastecimento de água interrompido, equipes de endemias em número
insuficiente e uma mobilização social que só aparece quando a epidemia já começou.

        Existe, porém, um conjunto de causas ligadas à informação, e é sobre elas que temos
condição de atuar:
• não há um canal digital simples de denúncia, com foto e localização;
• os registros que existem ficam em papel ou planilha, sem coordenadas, e por isso não viram

    mapa nem viram prioridade de rota;
• o cidadão não recebe retorno, então desiste de denunciar da segunda vez em diante;
• os dados ficam separados entre saúde, limpeza urbana e meio ambiente, sem conversarem entre

    si.

Quais as consequências?
A consequência mais direta é gente adoecendo e morrendo por uma causa evitável. Em 2024 o
Brasil registrou cerca de 6,6 milhões de casos prováveis de dengue e 6.022 mortes, o pior resultado
da série histórica. Nos picos, as unidades de pronto atendimento ficam lotadas e equipes precisam
ser deslocadas de outras frentes. Há ainda o custo econômico do afastamento do trabalho e da
escola, e o custo público das internações e dos mutirões emergenciais, sempre mais caro do que teria
sido prevenir. Fora isso, parte dos casos deixa sequela: a síndrome congênita associada ao zika, a
dor articular persistente da chikungunya, os quadros renais e hepáticos da leptospirose.

O que pode acontecer se nada mudar?
O ciclo se repete a cada verão. Os números mostram bem isso: depois do recorde de 2024, o país
teve cerca de 1,7 milhão de casos em 2025 e uma queda forte no começo de 2026, com 227,5 mil
casos prováveis até 11 de abril, contra 916,4 mil no mesmo período do ano anterior. A queda é boa
notícia, mas ela veio de condições climáticas favoráveis, da vacinação em grupos específicos e de
campanhas pontuais, e não de uma vigilância que funcione o ano inteiro. Mantida a resposta reativa,
a expectativa é de um novo pico quando outro sorotipo passar a circular em uma população menos

                                                                       2
imunizada, ainda mais com o mosquito ocupando áreas novas. Some-se a isso o desgaste do canal
de denúncia: cada morador que avisa e não vê nada acontecer é um morador a menos avisando no
próximo ano.

Como o conhecimento do curso pode contribuir com a mudança?
A Engenharia da Computação entra exatamente onde o processo trava. Nenhum de nós vai resolver
o saneamento do município nem contratar agentes, mas sabemos construir o sistema que pega a
observação solta do morador e devolve para a prefeitura como dado com coordenada, foto, data e
prioridade. Modelagem de banco de dados, desenvolvimento web e mobile, geoprocessamento,
integração entre sistemas por API e análise de dados são conteúdos do curso e são o que está
faltando na ponta.

3 A intervenção

Nossa proposta é o Sentinela Urbano, um aplicativo web e mobile em que qualquer morador registra
um risco ambiental à saúde em menos de um minuto, com foto e localização automática. Cada
registro alimenta um mapa de calor público e dispara uma notificação para o setor responsável da
prefeitura, por e-mail e por mensagem. O agente de endemias acompanha tudo por um painel,
atualiza o status da ocorrência e o morador vê o andamento pelo número de protocolo.

Quais conhecimentos técnicos nosso curso pode aplicar?
O aplicativo será feito como PWA, para funcionar no celular sem depender de loja de aplicativos e
para permitir registro offline, já que em muitos pontos o sinal é ruim; o envio acontece quando a
conexão volta. No servidor usaremos uma API REST e banco PostgreSQL com a extensão PostGIS,
que permite consultar ocorrências por raio, agrupar registros próximos e calcular densidade por
setor. O mapa será montado com Leaflet sobre OpenStreetMap, com a camada de calor gerada a
partir dessa densidade.

       A notificação à prefeitura sai do mesmo backend, por SMTP para o e-mail institucional e por
API de mensagens (WhatsApp Business ou bot de Telegram) para o grupo do setor, com regra de
disparo configurável: aviso imediato para casos críticos e resumo diário para o restante, evitando
que o canal vire spam e seja ignorado.

       Além disso, aplicamos engenharia de software na condução do projeto, com levantamento de
requisitos, casos de uso, diagramas UML, versionamento em Git e trabalho em sprints; segurança e
LGPD no controle de acesso por perfil, na opção de denúncia anônima e na minimização dos dados
pessoais coletados; e interação humano-computador no desenho da interface, que precisa ser usável
por pessoa idosa e por quem tem pouca familiaridade com celular. A análise de dados aparece nos
indicadores por setor e, se houver tempo, em um modelo simples de previsão de áreas de risco a
partir do histórico de registros.

Qual mudança concreta queremos produzir?
Queremos que a prefeitura deixe de agir depois do caso confirmado e passe a agir sobre o foco, com
endereço na mão. Do lado do morador, a mudança é ele ter um canal que funciona às onze da noite,
leva quinze segundos e devolve resposta. Do lado do agente, é chegar ao trabalho com uma rota já
ordenada por onde há mais registros abertos, em vez de bater quarteirão inteiro no escuro.

                                                                      3
Quais ações executaremos?
Começamos por um diagnóstico no bairro escolhido, conversando com agentes de endemias e com a
Secretaria Municipal de Saúde para entender como as denúncias chegam hoje e quais dados já
existem. Em seguida escrevemos os requisitos, definimos os tipos de ocorrência que o formulário
vai aceitar, prototipamos as telas e modelamos o banco.

        A terceira etapa é o desenvolvimento do formulário, do mapa, do painel do agente e do
módulo de notificação, com testes. Em paralelo fazemos o contato formal com a prefeitura para
acertar por qual canal os alertas devem chegar, porque de nada adianta o sistema enviar para um
e-mail que ninguém abre. Depois vem a validação com usuários reais, moradores e agentes, o ajuste
do que travar no uso e um piloto em uma área delimitada. Por último, a divulgação junto à escola, à
unidade básica de saúde e à associação de moradores, com o material educativo sobre prevenção
dentro do próprio aplicativo.

Que produto geraremos?
O produto é um sistema funcional em versão mínima viável, dividido em quatro partes.
• Registro do cidadão. Formulário com tipo de risco (água parada, lixo e entulho, esgoto a céu

    aberto, terreno baldio abandonado, animal morto, foco de roedores ou escorpiões, queima de
    resíduos, vazamento de água), foto, descrição curta, localização por GPS ou pino no mapa e
    opção de envio anônimo. Ao final o morador recebe um protocolo.
• Mapa público. Mapa de calor por densidade de registros, com filtro por tipo de risco, período e
    situação, aberto a qualquer pessoa que queira ver como está o bairro.
• Painel do agente. Lista de ocorrências ordenada por criticidade e proximidade, sugestão de rota
    de visita, atualização de status com foto da resolução e indicadores por setor.
• Alerta à prefeitura. Envio automático de e-mail e mensagem a cada novo registro, ou quando
    vários registros se acumulam na mesma área, contendo protocolo, tipo, endereço, coordenadas,
    foto e link para o ponto no mapa.
Acompanham o sistema a documentação técnica, o repositório de código versionado e o material
educativo usado na divulgação.

Quais resultados queremos alcançar?
No curto prazo, esperamos ter moradores registrando ocorrências durante o ano todo e não apenas
no verão, e uma redução no tempo entre o registro e a resolução, que é o indicador que melhor
mostra se o canal está funcionando. Do lado da prefeitura, esperamos aumentar a proporção de
visitas em que o agente encontra de fato um foco, comparada à varredura atual.

        No médio prazo, o mapa deve apontar as áreas críticas que se repetem, o que pode ser
comparado com os índices oficiais do LIRAa e com os casos notificados pela Secretaria de Saúde
para verificar se o que os moradores registram bate com o que a vigilância mede. O resultado final
que perseguimos, ainda que dependa de outros fatores, é queda na incidência de arboviroses na área
do piloto em relação a áreas parecidas sem o aplicativo.

                                                                       4
4 Referências

AGÊNCIA BRASIL. Casos de dengue no Brasil caem 75% em 2026. Publicado em 15 abr. 2026. Dados do
       Ministério da Saúde.

BRASIL. Ministério da Saúde. Levantamento Rápido de Índices para Aedes aegypti (LIRAa). Disponível em:
       gov.br/saude.

NAÇÕES UNIDAS BRASIL. Objetivo de Desenvolvimento Sustentável 3: Saúde e Bem-Estar. Disponível em:
       brasil.un.org/pt-br/sdgs/3.

PODER360. Dengue bate recorde em 2024 com 6,6 mi de casos e 6.022 mortes. Dados do Ministério da Saúde.

                                                                      5
```
