# Melhorias propostas

> Transcrição automática de `originais/melhorias_sentinela_urbano.pdf` (pdftotext). Em caso de dúvida, o PDF é a fonte.

```text
                                      Sentinela Urbano

                                                Melhorias propostas ao projeto

Integrantes:
    João Vitor Rodrigues Alves Medeiros
    Luiz Gustavo Andrade França
    Vinicius Carvalho Fonseca
    Israel Rodrigues de Souza Teles
    Samuel Silva Santos

Seis ajustes que aumentam a qualidade técnica do projeto sem ampliar o escopo. Todos
utilizam dados que o sistema já vai coletar e nenhum exige módulo novo.

1. Substituir densidade por índice de risco
O mapa de calor previsto mostra a quantidade de registros por área. Quantidade, porém, não
é risco: um foco de água parada ao lado de uma creche representa perigo maior do que um
terreno baldio em rua sem circulação. A proposta é calcular um score por ocorrência:

    risco = peso_do_tipo x dias_em_aberto
                  x reincidencia_do_ponto x proximidade_de_ponto_sensivel

O peso do tipo vem de uma tabela fixa, na qual água parada pesa mais que entulho. Os
pontos sensíveis (escolas, creches e unidades de saúde) podem ser obtidos gratuitamente do
OpenStreetMap, que já será usado como base cartográfica. As demais variáveis o banco já
possui.
 Custo: uma tabela de pesos e uma fórmula aplicada na consulta.
 Ganho: a fila do agente deixa de ser cronológica e passa a ser ordenada por risco real, o que
 diferencia o sistema de um simples cadastro com mapa.

2. Identificação de pontos crônicos
Quando um local volta a gerar registro depois de ter sido resolvido, ele é marcado
automaticamente como ponto crônico e ganha prioridade na fila de atendimento.

 Custo: uma consulta espacial no PostGIS, recurso que já será utilizado para agrupar registros
 próximos.
 Ganho: atende uma necessidade concreta da vigilância que nenhum canal atual cobre. Um
 terreno que reincide três vezes não é caso de nova visita, e sim de notificação ao proprietário.

3. Confirmação da resolução pelo morador
Na versão atual, apenas o agente encerra a ocorrência, anexando foto. A proposta é consultar
também o morador que registrou, com uma única pergunta após a conclusão: o problema foi
realmente resolvido?

 Custo: uma tela e um campo adicional no banco.
 Ganho: gera dois indicadores novos, taxa de resolução confirmada e taxa de fechamento
 contestado, e reduz o risco de encerramento administrativo sem ação efetiva, que é o vício mais
 comum em sistemas desse tipo.

4. Alternativa para a ausência de resposta da prefeitura
Esta é a maior fragilidade do projeto. Se o e-mail institucional não for aberto, todo o sistema se
reduz a um repositório de fotos. Duas medidas de baixo custo resolvem:
 - Contador público de dias sem resposta, exibido junto à ocorrência no mapa. O silêncio

                                                                                         1
     passa a ser um dado visível.
 - Ultrapassado o prazo, o sistema gera automaticamente um documento com protocolo,

     foto, coordenada e data, que o próprio morador encaminha à ouvidoria municipal.
 Custo: um modelo de documento e uma regra de prazo.
 Ganho: o sistema funciona desde o primeiro dia em qualquer município, sem depender de
 contrato ou integração, e a equipe passa a ter resposta pronta para a pergunta sobre o que
 acontece se a prefeitura não colaborar.

5. Comparação com o LIRAa desde o início
O documento atual trata essa comparação como resultado de médio prazo. A proposta é
trazê-la para o centro do projeto: o Sentinela Urbano gera um índice próprio por setor e esse
índice é confrontado com o Levantamento Rápido de Índices para Aedes aegypti do mesmo
setor.

 Custo: os dados do LIRAa são públicos e a agregação por setor já faz parte do sistema.
 Ganho: o projeto deixa de afirmar que contribui e passa a demonstrar, com validação
 mensurável. É o que distingue um trabalho de curso de um projeto com resultado verificável.

6. Estreitamento do posicionamento
O documento inicia em arboviroses e depois amplia para lixo, entulho e esgoto, acionando
também as metas 3.9 e 3.d. Essa abertura enfraquece o posicionamento e aproxima a solução
de plataformas genéricas de denúncia urbana já existentes no mercado.
A sugestão é manter os oito tipos de risco no formulário, porém apresentar o produto como
vigilância comunitária de risco de arbovirose, tratando os demais tipos como fatores de risco
ambiental associados. O escopo técnico permanece idêntico e o posicionamento fica muito
mais preciso.

O que não deve ser acrescentado
Previsão por aprendizado de máquina, integração com aplicativos de trânsito, chat entre
morador e agente, versão nativa para iOS e ranking de usuários. Todos ampliam o escopo e
nenhum resolve a fragilidade central do projeto, que é a resposta do poder público.

Seção ausente no documento: limitações e riscos
O projeto não apresenta análise de limitações. Três itens ocupam meia página e melhoram
consideravelmente a avaliação:

Registro fotográfico de propriedade alheia
 Fotografar o quintal do vizinho tem implicação legal. Mitigação: orientar o registro a partir da
 via pública e não exibir o endereço exato no mapa público.

Denúncia falsa motivada por conflito de vizinhança
 Mitigação: exigir confirmação de outro morador antes de elevar a prioridade da ocorrência.

Viés de quem denuncia
 Bairros com maior acesso a smartphone geram mais registros, e o recurso público pode
 acabar direcionado a quem já é melhor atendido. Mitigação: normalizar o índice pela
 população do setor, em vez de utilizar o valor absoluto de ocorrências.

Impacto no backlog
As melhorias 1, 2 e 3 entram como ajuste de critérios de aceitação em histórias que já existem,

                                                                                         2
sem criar itens novos. A melhoria 4 acrescenta uma história de prioridade média. As melhorias
5 e 6 não alteram o backlog, pois dizem respeito à análise de resultados e ao posicionamento
do produto.

                                                                                         3
```
