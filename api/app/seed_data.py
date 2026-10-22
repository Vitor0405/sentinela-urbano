"""Reference data: the eight risk types from the original project and the risk coefficients.

Weights and coefficients are starting values; change them in the database, not here.
The seed only inserts missing rows, so later adjustments are never overwritten.
"""

from decimal import Decimal

# The catch-all type the resident picks when nothing else fits.
OTHER_TYPE_CODE = "other"

# code, name, description, weight, department, is_breeding_site
OCCURRENCE_TYPES: list[tuple[str, str, str, str, str, bool]] = [
    (
        "standing_water",
        "Água parada",
        "Pneu, vaso, garrafa, calha, caixa d'água destampada, piscina abandonada ou "
        "qualquer recipiente acumulando água.",
        "5",
        "Vigilância em Saúde – Controle de Endemias",
        True,
    ),
    (
        "trash_rubble",
        "Lixo e entulho",
        "Lixo acumulado ou entulho em calçada, terreno ou via pública. Recipientes "
        "descartados acumulam água da chuva.",
        "3",
        "Limpeza Urbana",
        True,
    ),
    (
        "water_leak",
        "Vazamento de água",
        "Vazamento na rede ou em imóvel formando poça ou acúmulo de água.",
        "3",
        "Saneamento – Abastecimento de Água",
        True,
    ),
    (
        "vacant_lot",
        "Terreno baldio abandonado",
        "Terreno sem manutenção, com mato alto, lixo ou recipientes expostos.",
        "2",
        "Fiscalização de Posturas",
        False,
    ),
    (
        "open_sewage",
        "Esgoto a céu aberto",
        "Esgoto correndo pela rua, vala ou córrego.",
        "2",
        "Saneamento – Esgotamento Sanitário",
        False,
    ),
    (
        "dead_animal",
        "Animal morto",
        "Animal morto em via pública ou terreno.",
        "1",
        "Vigilância em Saúde – Zoonoses",
        False,
    ),
    (
        "rodents_scorpions",
        "Foco de roedores ou escorpiões",
        "Presença frequente de ratos ou escorpiões.",
        "1",
        "Vigilância em Saúde – Zoonoses",
        False,
    ),
    (
        "waste_burning",
        "Queima de resíduos",
        "Queima de lixo, entulho ou mato.",
        "1",
        "Meio Ambiente",
        False,
    ),
    # Always last. Moderate weight: unknown until someone from the team looks at it.
    (
        OTHER_TYPE_CODE,
        "Outro risco",
        "Não encontrou na lista? Descreva o risco em poucas palavras; a equipe classifica.",
        "2",
        "Vigilância em Saúde – Triagem",
        False,
    ),
]

# key, value, description (pt-BR, shown to managers)
RISK_SETTINGS: list[tuple[str, str, str]] = [
    ("min_days_open", "1", "Valor mínimo de dias em aberto na fórmula de risco."),
    (
        "recurrence_increment",
        "0.5",
        "Fator de reincidência = 1 + este valor × ocorrências já resolvidas no mesmo ponto.",
    ),
    (
        "recurrence_radius_m",
        "30",
        "Raio, em metros, que define 'mesmo ponto' para reincidência.",
    ),
    (
        "chronic_radius_m",
        "30",
        "Nova ocorrência a até este raio (m) de uma já resolvida é marcada como ponto crônico.",
    ),
    (
        "chronic_owner_notice_threshold",
        "3",
        "A partir deste número de reincidências, recomenda 'notificar proprietário'.",
    ),
    (
        "sensitive_proximity_factor",
        "1.5",
        "Fator aplicado quando há escola, creche ou unidade de saúde dentro do raio.",
    ),
    ("sensitive_radius_m", "200", "Raio, em metros, da busca por pontos sensíveis."),
    (
        "unconfirmed_risk_cap",
        "15",
        "Sem confirmação de outro morador ('eu também vi'), o risco não passa deste valor.",
    ),
    (
        "cluster_radius_m",
        "150",
        "Raio, em metros, do alerta de acúmulo de registros do mesmo tipo.",
    ),
    (
        "cluster_min_count",
        "3",
        "Quantidade de ocorrências ativas do mesmo tipo que dispara o alerta.",
    ),
    ("cluster_window_days", "7", "Período, em dias, considerado no alerta de acúmulo."),
    (
        "messaging_immediate_risk",
        "7.5",
        "Risco inicial a partir do qual o grupo de mensagens é avisado na hora "
        "(o resto vai no resumo diário).",
    ),
    ("route_max_stops", "12", "Número máximo de paradas na rota sugerida ao agente."),
    (
        "liraa_window_days",
        "60",
        "Janela, em dias antes da data do LIRAa, das ocorrências comparadas com o levantamento.",
    ),
    (
        "response_deadline_days",
        "15",
        "Prazo, em dias, para resposta da prefeitura antes de liberar o documento à ouvidoria.",
    ),
]


def risk_setting_defaults() -> dict[str, Decimal]:
    return {key: Decimal(value) for key, value, _ in RISK_SETTINGS}


# Short prevention advice per type, in plain language (backlog story 14). Filled into
# occurrence_types.prevention_tips only when empty, so the municipality can rewrite them.
PREVENTION_TIPS: dict[str, str] = {
    "standing_water": (
        "Reserve 10 minutos por semana para procurar água parada em casa. Tampe bem caixas "
        "d'água, tonéis e cisternas. Guarde pneus em local coberto e garrafas de boca para "
        "baixo. Coloque areia nos pratos de vasos de planta e mantenha calhas desentupidas. "
        "Os ovos do mosquito resistem meses no seco: esfregue as paredes dos recipientes."
    ),
    "trash_rubble": (
        "Guarde o lixo em sacos fechados e coloque para fora só no dia da coleta. Não jogue "
        "lixo nem entulho em terrenos ou na rua: tampas, copos e embalagens viram criadouro "
        "com a chuva. Para entulho e objetos grandes, use o serviço de recolhimento da "
        "prefeitura."
    ),
    "water_leak": (
        "Avise a companhia de saneamento sobre vazamentos na rua. Em casa, conserte "
        "torneiras e canos que pingam e não deixe poças se formarem: água parada e limpa é "
        "o lugar preferido do Aedes aegypti."
    ),
    "vacant_lot": (
        "A limpeza do terreno é responsabilidade do proprietário. Não descarte lixo ou "
        "entulho no local. Se o terreno acumula recipientes com água, registre de novo: "
        "pontos que voltam a ter problema recebem prioridade e podem gerar notificação ao "
        "dono."
    ),
    "open_sewage": (
        "Evite contato com a água do esgoto e mantenha crianças e animais longe: ela "
        "transmite doenças como a leptospirose. Não tente desentupir a rede por conta "
        "própria; aguarde o serviço de saneamento."
    ),
    "dead_animal": (
        "Não toque no animal com as mãos e não o jogue no lixo comum ou em terrenos. "
        "Mantenha crianças e animais de estimação afastados até a remoção pelo serviço de "
        "zoonoses."
    ),
    "rodents_scorpions": (
        "Mantenha quintal e entulho limpos, vede ralos e frestas, e guarde alimentos e "
        "ração em potes fechados. Sacuda roupas, toalhas e calçados antes de usar. Em caso "
        "de picada de escorpião, procure atendimento de saúde imediatamente."
    ),
    "waste_burning": (
        "Não queime lixo, folhas ou entulho: a fumaça faz mal à saúde, principalmente de "
        "crianças e idosos, e a queima é infração ambiental. Use a coleta regular e os "
        "pontos de descarte da prefeitura."
    ),
    "other": (
        "Qualquer objeto que junte água da chuva pode virar criadouro: vire, tampe, fure ou "
        "descarte. Uma volta de 10 minutos por semana pela casa e pelo quintal elimina a "
        "maioria dos focos. A equipe de saúde vai avaliar o risco que você descreveu."
    ),
}
