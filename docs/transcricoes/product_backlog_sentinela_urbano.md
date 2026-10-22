# Product Backlog

> Transcrição automática de `originais/product_backlog_sentinela_urbano.pdf` (pdftotext). Em caso de dúvida, o PDF é a fonte.

```text
                           Construção do Product Backlog

                                      Projeto Integrador | Metodologia Ágil - Scrum

Nome do projeto: Sentinela Urbano
Curso: Engenharia da Computação
Integrantes:

    João Vitor Rodrigues Alves Medeiros
    Luiz Gustavo Andrade França
    Vinicius Carvalho Fonseca
    Israel Rodrigues de Souza Teles
    Samuel Silva Santos
Descrição da solução
O Sentinela Urbano é uma aplicação web e mobile, desenvolvida como PWA, para registro
colaborativo de riscos ambientais à saúde. Qualquer morador pode registrar em menos de um
minuto um foco de água parada, um acúmulo de lixo, um esgoto a céu aberto ou outro risco
presente no bairro, informando foto, descrição curta e localização obtida automaticamente por
GPS.
Cada registro alimenta um mapa de calor público, que mostra a densidade de ocorrências por
região, e dispara uma notificação automática ao setor responsável da prefeitura, por e-mail e
por mensagem. O agente de combate a endemias acompanha as ocorrências em um painel
próprio, com a fila ordenada por criticidade e proximidade, e atualiza o status de cada caso até
a conclusão. O morador acompanha o andamento pelo número de protocolo recebido no
momento do registro.
O projeto está vinculado ao ODS 3, Saúde e Bem-Estar, com foco na meta 3.3, e atua sobre a
lacuna de informação entre o que o morador enxerga no bairro e o que chega à vigilância
municipal em tempo de evitar o adoecimento.

Perfis de usuário considerados
Morador. Cidadão que identifica o risco no bairro. Pode ter pouca familiaridade com
aplicativos e usar celular simples, com conexão instável. É o perfil com maior volume de acesso
e o que exige menor atrito possível no registro.
Agente de endemias. Servidor que executa a visita de campo. Usa o painel para organizar a
rota do dia, registrar o que encontrou e encerrar a ocorrência com foto.
Gestor da vigilância. Coordenador do setor na Secretaria de Saúde. Usa os indicadores e o
mapa para decidir onde concentrar equipe e mutirão.

Product Backlog priorizado
O backlog reúne quatorze histórias de usuário, distribuídas entre os quatro módulos previstos
no projeto: registro do cidadão, mapa público, painel do agente e alerta à prefeitura. Cada
história possui critérios de aceitação, prioridade e estimativa de esforço em pontos, na escala 1,
2, 3, 5 e 8.

                                                                                          1
Nº           História de usuário                     Critérios de aceitação              Prio.  Est.

1 Como morador, quero registrar uma       O registro deve ser concluído sem              Alta   5

    ocorrência sem precisar criar conta,  cadastro prévio; deve haver opção de

    para que a denúncia não seja          envio anônimo; quando o morador optar

    abandonada por excesso de etapas.     por se identificar, apenas nome e

                                          contato devem ser solicitados.

2 Como morador, quero registrar a         O aplicativo deve capturar foto pela           Alta   8

    ocorrência com foto e localização     câmera ou galeria; deve obter latitude e

    automática, para comprovar o risco e longitude por GPS; deve permitir ajustar

    indicar o endereço exato.             o ponto no mapa quando o sinal estiver

                                          impreciso; o envio só é liberado com foto

                                          e coordenada preenchidas.

3 Como morador, quero classificar o tipo A lista deve conter água parada, lixo e         Alta   3

    de risco que estou registrando, para  entulho, esgoto a céu aberto, terreno

    que a ocorrência chegue ao setor      baldio abandonado, animal morto, foco

    correto da prefeitura.                de roedores ou escorpiões, queima de

                                          resíduos e vazamento de água; cada

                                          tipo deve estar associado a um setor de

                                          destino; o setor deve ser exibido antes

                                          do envio.

4 Como morador, quero receber um          O protocolo deve ser gerado no                 Alta   3

    número de protocolo e consultar o     momento do envio e exibido na tela; a

    andamento por ele, para saber se      consulta deve ser possível sem login,

    houve providência.                    apenas com o número; o status deve

                                          percorrer os estados registrada,

                                          encaminhada, em atendimento e

                                          concluída, com a data de cada

                                          mudança.

5 Como cidadão, quero visualizar um       O mapa deve exibir a densidade de              Alta   8

    mapa de calor público das ocorrências, registros por área; deve permitir filtro por

    para conhecer a situação do meu       tipo de risco, período e situação; deve

    bairro.                               estar acessível sem autenticação; o

                                          endereço exato e os dados do

                                          denunciante não devem ser exibidos

                                          publicamente.

6 Como agente de endemias, quero          O acesso deve exigir usuário e senha; o        Alta   3

    acessar o painel com login próprio,   perfil deve definir quais tipos de risco e

    para tratar apenas as ocorrências da qual região o agente enxerga; sessões

    minha competência.                    inativas devem ser encerradas

                                          automaticamente.

7 Como agente de endemias, quero ver a A lista deve trazer tipo, endereço, tempo         Alta   5

    fila de ocorrências ordenada por      em aberto e distância; deve permitir

    criticidade e proximidade, para       ordenar por criticidade ou por

    organizar a visita do dia.            proximidade; ocorrências agrupadas no

                                          mesmo ponto devem aparecer como

                                          um único item com o total de registros.

8 Como agente de endemias, quero          O agente deve poder alterar o status e         Alta   5

    atualizar o status da ocorrência com  inserir observação; a conclusão deve

    foto da resolução, para comprovar o   exigir foto do local após a ação; a

    atendimento realizado.                alteração deve ficar registrada com

                                          data, hora e identificação do agente.

9 Como setor responsável da prefeitura, O alerta deve ser enviado por e-mail             Alta   5

    quero receber alerta automático de    institucional e por mensagem; deve

    cada nova ocorrência, para agir sem conter protocolo, tipo, endereço,

    depender de consulta ao sistema.      coordenadas, foto e link para o ponto no

                                          mapa; falhas de envio devem ser

                                          registradas em log e reprocessadas.

                                          2
Nº               História de usuário                   Critérios de aceitação         Prio.  Est.

10 Como gestor da vigilância, quero ser   O sistema deve agrupar registros do         Média  5

    avisado quando vários registros se    mesmo tipo dentro de um raio

    acumularem na mesma área, para        configurável; ao ultrapassar o limite

    antecipar a formação de um ponto      definido, deve disparar alerta específico;

    crítico.                              o alerta deve informar a quantidade de

                                          registros e o período de acumulação.

11 Como morador, quero registrar a        O aplicativo deve armazenar o registro      Média  8

    ocorrência mesmo sem conexão, para localmente quando não houver rede;

    não perder o registro em áreas com    deve sincronizar automaticamente ao

    sinal ruim.                           restabelecer a conexão; deve informar

                                          ao usuário que o envio está pendente.

12 Como gestor da vigilância, quero       O painel deve exibir tempo médio entre      Média  5

    acompanhar indicadores por setor,     registro e conclusão, quantidade de

    para avaliar o desempenho do          ocorrências por tipo e por bairro e

    atendimento.                          proporção de visitas com foco

                                          confirmado; deve permitir filtro por

                                          período; deve permitir exportação em

                                          CSV.

13 Como agente de endemias, quero         A rota deve considerar as ocorrências       Média  8

    receber uma sugestão de rota de visita, abertas da região do agente; deve

    para reduzir deslocamento entre os    ordenar os pontos por proximidade a

    pontos.                               partir da posição atual; deve permitir

                                          remover pontos manualmente antes de

                                          iniciar.

14 Como morador, quero acessar            Ao concluir o registro, o sistema deve      Baixa  2

    orientações de prevenção dentro do    exibir orientação relacionada ao tipo

    aplicativo, para saber como evitar o  informado; o conteúdo deve ficar

    risco que acabei de registrar.        disponível em uma seção fixa do

                                          aplicativo; o texto deve ser curto e

                                          escrito em linguagem simples.

MVP definido pela equipe
Para a primeira versão funcional, a equipe priorizou as histórias 1 a 9:

- Registrar ocorrência sem criar conta, com opção de envio anônimo;
- Registrar com foto e localização automática;
- Classificar o tipo de risco e definir o setor de destino;
- Receber protocolo e consultar o andamento por ele;
- Visualizar o mapa de calor público com filtros;
- Acessar o painel do agente com login e perfil de acesso;
- Ver a fila de ocorrências ordenada por criticidade e proximidade;
- Atualizar o status da ocorrência com foto da resolução;
- Disparar o alerta automático à prefeitura a cada novo registro.

Essas nove histórias somam 45 pontos e cobrem o ciclo completo que dá sentido ao projeto: o
morador registra, a prefeitura é avisada, o agente atende e o resultado volta para o mapa.
Retirar qualquer uma delas interrompe esse ciclo. Sem o alerta, por exemplo, o sistema vira
apenas um repositório de denúncias, que é justamente o problema apontado no diagnóstico
do projeto.

As histórias 10 a 14 somam 28 pontos e ficam para as iterações seguintes. Elas aumentam a
eficiência do atendimento e a capacidade de análise, mas não impedem o funcionamento
inicial. O registro offline, apesar de importante em campo, foi classificado como média porque

                                                    3
exige sincronização e tratamento de conflito, e pode ser entregue logo após a validação do
fluxo principal.

Rastreabilidade com os módulos do projeto

Módulo previsto no projeto                       Histórias correspondentes
     Registro do cidadão
          Mapa público      1, 2, 3, 4, 11 e 14
       Painel do agente     5 e 10
      Alerta à prefeitura   6, 7, 8, 12 e 13
                            9 e 10

Critério de priorização adotado
Foram classificadas como prioridade alta apenas as histórias que compõem o caminho crítico
do produto, ou seja, aquelas sem as quais o ciclo registro, alerta, atendimento e retorno não se
fecha. Receberam prioridade média as histórias que otimizam esse ciclo já existente, e
prioridade baixa as de caráter complementar.

As estimativas consideraram complexidade técnica e incerteza. As histórias 2, 5, 11 e 13
receberam 8 pontos por envolverem, respectivamente, câmera e geolocalização, cálculo de
densidade espacial com PostGIS, sincronização offline e ordenação geográfica de rota. As
histórias de cadastro simples e de conteúdo estático receberam as menores pontuações.

Observação sobre a experiência do morador
Durante a construção do backlog, a equipe optou por não exigir criação de conta para registrar
uma ocorrência. A decisão parte de um dos objetivos declarados no projeto, que é permitir o
registro em cerca de quinze segundos, a qualquer hora. Exigir cadastro antes do primeiro
registro adicionaria etapas justamente no momento de maior chance de desistência, e entraria
em conflito com a possibilidade de denúncia anônima prevista no escopo. O
acompanhamento fica garantido pelo número de protocolo, e a autenticação passa a ser
exigida apenas para os perfis internos, agente e gestor, onde ela é de fato necessária.

                            4
```
