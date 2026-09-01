
import concurrent.futures
import html
import math

from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests


PASTA_APP = Path(
    __file__
).resolve().parent


PASTA_DADOS = (
    PASTA_APP
    /
    "dados"
)


CATALOGO = (
    PASTA_DADOS
    /
    "catalogo_publico_sc_257A.csv"
)


CANDIDATOS_PADRAO = (
    PASTA_DADOS
    /
    "candidatos_padrao_257A.csv"
)


ALERTAS = (
    PASTA_DADOS
    /
    "atencao_cadastral_257A.csv"
)


PAGAMENTOS = (
    PASTA_DADOS
    /
    "pagamentos_precalculados_257A.csv"
)


URL_EMPENHO = (
    "https://api-publica.obrasgov.gestao.gov.br/"
    "obras/empenho"
)


HEADERS = {
    "User-Agent":
        (
            "ObraVigia/0.257B "
            "(prototipo academico de reuso de dados abertos)"
        )
}


# ============================================================
# CARREGAMENTO
# ============================================================

@lru_cache(
    maxsize=1
)
def carregar_catalogo():

    df = pd.read_csv(
        CATALOGO,
        low_memory=False
    )


    df[
        "id_projeto"
    ] = (
        df[
            "id_projeto"
        ]
        .astype(
            str
        )
    )


    return (
        df
        .drop_duplicates(
            subset=[
                "id_projeto"
            ],
            keep="first"
        )
        .set_index(
            "id_projeto",
            drop=False
        )
    )


@lru_cache(
    maxsize=1
)
def carregar_candidatos_padrao():

    df = pd.read_csv(
        CANDIDATOS_PADRAO,
        low_memory=False
    )


    df[
        "id_projeto"
    ] = (
        df[
            "id_projeto"
        ]
        .astype(
            str
        )
    )


    return df


@lru_cache(
    maxsize=1
)
def carregar_alertas():

    df = pd.read_csv(
        ALERTAS,
        low_memory=False
    )


    df[
        "id_projeto"
    ] = (
        df[
            "id_projeto"
        ]
        .astype(
            str
        )
    )


    return df


@lru_cache(
    maxsize=1
)
def carregar_pagamentos():

    df = pd.read_csv(
        PAGAMENTOS,
        low_memory=False
    )


    df[
        "id_projeto"
    ] = (
        df[
            "id_projeto"
        ]
        .astype(
            str
        )
    )


    return df


# ============================================================
# TEXTO
# ============================================================

def texto_seguro_publico(
    valor
):

    if valor is None:

        return "Não informado na fonte"


    try:

        if pd.isna(
            valor
        ):

            return "Não informado na fonte"


    except Exception:

        pass


    texto = str(
        valor
    ).strip()


    if (
        not texto
        or
        texto.lower()
        in {
            "nan",
            "none",
            "null"
        }
    ):

        return "Não informado na fonte"


    return html.escape(
        texto
    )


# ============================================================
# MOEDA
# ============================================================

def formatar_moeda(
    valor
):

    if valor is None:

        return "Não informado na fonte"


    try:

        if pd.isna(
            valor
        ):

            return "Não informado na fonte"


        numero = float(
            valor
        )


        if not math.isfinite(
            numero
        ):

            return "Não informado na fonte"


    except Exception:

        return "Não informado na fonte"


    texto = (
        f"{numero:,.2f}"
        .replace(
            ",",
            "X"
        )
        .replace(
            ".",
            ","
        )
        .replace(
            "X",
            "."
        )
    )


    return (
        "R$ "
        +
        texto
    )


# ============================================================
# DATA
# ============================================================

def formatar_data(
    valor
):

    if valor is None:

        return "Não informado"


    try:

        data = pd.to_datetime(
            valor,
            errors="coerce"
        )


        if pd.isna(
            data
        ):

            return "Não informado"


        return data.strftime(
            "%d/%m/%Y"
        )


    except Exception:

        return "Não informado"


# ============================================================
# PAGAMENTO PRÉ-CARREGADO
# ============================================================

@lru_cache(
    maxsize=1
)
def mapa_pagamentos_pre():

    df = carregar_pagamentos()


    saida = {}


    for linha in df.itertuples(
        index=False
    ):

        id_projeto = str(
            linha.id_projeto
        )


        valor = getattr(
            linha,
            "valor_pago",
            None
        )


        try:

            if pd.isna(
                valor
            ):

                valor = None


        except Exception:

            pass


        saida[
            id_projeto
        ] = valor


    return saida


# ============================================================
# CONSULTA SOB DEMANDA
# ============================================================

@lru_cache(
    maxsize=4096
)
def buscar_valor_pago(
    id_projeto
):

    pagina = 1

    soma = 0.0

    encontrou = False


    try:

        while True:

            resposta = requests.get(
                URL_EMPENHO,
                params={
                    "id_projeto_investimento":
                        str(
                            id_projeto
                        ),

                    "pagina":
                        pagina,

                    "tamanho_da_pagina":
                        100
                },
                headers=HEADERS,
                timeout=25
            )


            if resposta.status_code != 200:

                return None


            payload = resposta.json()


            for registro in payload.get(
                "data",
                []
            ):

                valor = registro.get(
                    "pago"
                )


                if valor is None:

                    continue


                try:

                    numero = float(
                        valor
                    )


                    if math.isfinite(
                        numero
                    ):

                        soma += numero

                        encontrou = True


                except Exception:

                    pass


            total_paginas = int(
                payload.get(
                    "total_pages",
                    1
                )
            )


            if pagina >= total_paginas:

                break


            pagina += 1


        return (
            soma
            if encontrou
            else None
        )


    except Exception:

        return None


# ============================================================
# PAGAMENTOS EM LOTE
# ============================================================

def obter_valores_pagos_lote(
    ids
):

    ids = sorted(
        {
            str(
                item
            )

            for item in ids

            if item is not None
        }
    )


    pre = mapa_pagamentos_pre()


    resultado = {}


    faltantes = []


    for id_projeto in ids:

        if id_projeto in pre:

            resultado[
                id_projeto
            ] = pre[
                id_projeto
            ]

        else:

            faltantes.append(
                id_projeto
            )


    if faltantes:

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=5
        ) as executor:

            valores = executor.map(
                buscar_valor_pago,
                faltantes
            )


            for par in zip(
                faltantes,
                valores
            ):

                id_projeto = par[
                    0
                ]

                valor = par[
                    1
                ]


                resultado[
                    id_projeto
                ] = valor


    return resultado


# ============================================================
# POPUP
# ============================================================

def popup_publico(
    id_projeto,
    valores_pagos=None
):

    id_projeto = str(
        id_projeto
    )


    catalogo = carregar_catalogo()


    if id_projeto not in catalogo.index:

        return (
            "<b>Projeto "
            +
            html.escape(
                id_projeto
            )
            +
            "</b><br><br>"
            "Informações detalhadas não encontradas "
            "no snapshot da fonte."
        )


    linha = catalogo.loc[
        id_projeto
    ]


    if isinstance(
        linha,
        pd.DataFrame
    ):

        linha = linha.iloc[
            0
        ]


    nome = texto_seguro_publico(
        linha.get(
            "desc_nome"
        )
    )


    situacao = texto_seguro_publico(
        linha.get(
            "situacao"
        )
    )


    orgao = texto_seguro_publico(
        linha.get(
            "organizacao_resp"
        )
    )


    investimento = formatar_moeda(
        linha.get(
            "valor_investimento_previsto"
        )
    )


    valor_pago = None


    if valores_pagos is not None:

        valor_pago = valores_pagos.get(
            id_projeto
        )


    if (
        valor_pago is None
        and
        id_projeto in mapa_pagamentos_pre()
    ):

        valor_pago = mapa_pagamentos_pre().get(
            id_projeto
        )


    pago = formatar_moeda(
        valor_pago
    )


    inicio = formatar_data(
        linha.get(
            "dt_inicial_prevista"
        )
    )


    fim = formatar_data(
        linha.get(
            "dt_final_prevista"
        )
    )


    periodo = (
        inicio
        +
        " → "
        +
        fim
    )


    residual = linha.get(
        "somente_investimento_001",
        False
    )


    try:

        residual = bool(
            residual
        )


    except Exception:

        residual = False


    alerta = ""


    if residual:

        alerta = """
        <div style="
            margin-top:10px;
            padding:8px 9px;
            border-radius:7px;
            background:#fff7ed;
            border:1px solid #fdba74;
            color:#9a3412;
            font-size:11px;
            line-height:1.35;
        ">
            <b>Atenção cadastral:</b>
            o investimento disponível na fonte é apenas
            R$ 0,01. O ObraVigia considera esse registro
            insuficiente para utilização automática do
            componente financeiro.
        </div>
        """


    return f"""
    <div style="
        width:330px;
        font-family:Arial,sans-serif;
        font-size:12px;
        line-height:1.45;
    ">

        <div style="
            font-size:15px;
            font-weight:700;
            margin-bottom:10px;
            line-height:1.25;
        ">
            {nome}
        </div>

        <div style="margin-bottom:4px;">
            <b>Situação atual:</b>
            {situacao}
        </div>

        <div style="margin-bottom:4px;">
            <b>Órgão responsável:</b>
            {orgao}
        </div>

        <div style="margin-bottom:4px;">
            <b>Investimento previsto:</b>
            {investimento}
        </div>

        <div style="margin-bottom:4px;">
            <b>Valor pago registrado:</b>
            {pago}
        </div>

        <div style="margin-bottom:4px;">
            <b>Período previsto:</b>
            {periodo}
        </div>

        {alerta}

        <div style="
            margin-top:10px;
            color:#6b7280;
            font-size:10px;
        ">
            Fonte: API Pública do ObrasGov.br.
        </div>

    </div>
    """


# ============================================================
# IDS DOS ALERTAS
# ============================================================

def ids_alertas():

    df = carregar_alertas()


    return (
        df[
            "id_projeto"
        ]
        .astype(
            str
        )
        .tolist()
    )


# ============================================================
# CANDIDATOS CINZA
# ============================================================

def montar_candidatos_contexto(
    candidatos,
    ids_selecionados,
    valores_pagos
):

    ids_selecionados = {
        str(
            item
        )

        for item in ids_selecionados
    }


    saida = []


    for linha in candidatos.itertuples(
        index=False
    ):

        id_projeto = str(
            linha.id_projeto
        )


        if id_projeto in ids_selecionados:

            continue


        lat = getattr(
            linha,
            "latitude_representativa",
            None
        )


        lon = getattr(
            linha,
            "longitude_representativa",
            None
        )


        try:

            lat = float(
                lat
            )

            lon = float(
                lon
            )


        except Exception:

            continue


        nome = getattr(
            linha,
            "desc_nome",
            id_projeto
        )


        saida.append(
            {
                "lat":
                    lat,

                "lng":
                    lon,

                "tooltip":
                    (
                        "Candidata viável — "
                        +
                        str(
                            nome
                        )
                    ),

                "popup":
                    popup_publico(
                        id_projeto,
                        valores_pagos
                    )
            }
        )


    return saida


# ============================================================
# ALERTAS CADASTRAIS
# ============================================================

def montar_alertas_contexto(
    valores_pagos
):

    df = carregar_alertas()


    saida = []


    for linha in df.itertuples(
        index=False
    ):

        disponivel = getattr(
            linha,
            "localizacao_disponivel",
            False
        )


        if not bool(
            disponivel
        ):

            continue


        try:

            lat = float(
                linha.latitude_representativa_publica
            )

            lon = float(
                linha.longitude_representativa_publica
            )


        except Exception:

            continue


        id_projeto = str(
            linha.id_projeto
        )


        nome = getattr(
            linha,
            "desc_nome",
            id_projeto
        )


        saida.append(
            {
                "lat":
                    lat,

                "lng":
                    lon,

                "tooltip":
                    (
                        "Atenção cadastral — "
                        +
                        str(
                            nome
                        )
                    ),

                "popup":
                    popup_publico(
                        id_projeto,
                        valores_pagos
                    )
            }
        )


    return saida
