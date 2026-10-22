// Must match TERMS_VERSION in the API; registration is refused when they differ.
export const TERMS_VERSION = '2026-10'

export const TERMS_SECTIONS: { title: string; body: string[] }[] = [
  {
    title: 'O que é o Sentinela Urbano',
    body: [
      'Plataforma de vigilância comunitária de risco de arbovirose (dengue, zika e chikungunya). Moradores registram focos de risco com foto e localização; agentes de saúde atendem as ocorrências; a prefeitura é avisada automaticamente.',
    ],
  },
  {
    title: 'Quais dados coletamos',
    body: [
      'Na conta: nome, e-mail e senha (guardada de forma irreversível). Não pedimos CPF, telefone nem endereço.',
      'Em cada ocorrência: tipo de risco, foto(s), coordenada do local, descrição opcional e, se você quiser se identificar sem conta, nome e um contato.',
      'Removemos automaticamente das fotos os metadados (EXIF), que podem conter a posição do celular, modelo do aparelho e data.',
    ],
  },
  {
    title: 'O que fica público',
    body: [
      'No mapa público aparecem apenas o tipo, a situação, a data e uma localização aproximada (grade de cerca de 100 metros). Nunca mostramos endereço, fotos, descrição nem quem registrou.',
      'A localização exata e as fotos são vistas somente por agentes de saúde e gestores da prefeitura, e por você.',
    ],
  },
  {
    title: 'Como registrar com responsabilidade',
    body: [
      'Fotografe a partir da via pública. Não entre em imóveis, não fotografe o interior de casas ou quintais alheios e evite que pessoas apareçam na foto.',
      'Registre apenas situações reais. Denúncias falsas prejudicam o atendimento de quem precisa e podem ter consequências legais.',
    ],
  },
  {
    title: 'Para que usamos os dados',
    body: [
      'Para encaminhar a ocorrência ao setor responsável, priorizar o atendimento, acompanhar a resolução e produzir indicadores por região, sempre normalizados pela população.',
      'Não vendemos nem compartilhamos dados com terceiros para fins comerciais.',
    ],
  },
  {
    title: 'Seus direitos (LGPD)',
    body: [
      'Você pode pedir acesso, correção ou exclusão dos seus dados pessoais e revogar este consentimento a qualquer momento, nos termos do art. 18 da Lei 13.709/2018.',
      'As ocorrências em si (local, tipo, fotos sem identificação) podem ser mantidas para fins de saúde pública.',
    ],
  },
]

export const TERMS_DRAFT_NOTICE =
  'Versão preliminar para o piloto. Antes do uso real, revisar com o encarregado de dados (DPO) do município e incluir o contato oficial para solicitações.'
