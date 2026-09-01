
from __future__ import annotations

import math
import random
import time

from pathlib import Path

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIGURAÇÃO
# ============================================================

OSRM_BASE_URL = (
    "https://router.project-osrm.org"
)

USER_AGENT = (
    "ObraVigia/0.1 "
    "(reuso de dados abertos para planejamento de inspecoes)"
)

JORNADA_PADRAO_MIN = 480.0

SERVICO_PADRAO_MIN = 45.0

TAMANHO_SHORTLIST = 79

TAMANHO_VIZINHANCA = 400

LIMITE_SNAP_PROJETO_M = 500.0

FATOR_PROXY_MIN_POR_KM = 1.42


# ============================================================
# HAVERSINE
# ============================================================

def haversine_vetorizado(
    lat0,
    lon0,
    lat,
    lon
):

    raio = 6371.0088

    lat0_rad = np.radians(
        float(
            lat0
        )
    )

    lon0_rad = np.radians(
        float(
            lon0
        )
    )

    lat_rad = np.radians(
        np.asarray(
            lat,
            dtype=float
        )
    )

    lon_rad = np.radians(
        np.asarray(
            lon,
            dtype=float
        )
    )

    dlat = (
        lat_rad
        -
        lat0_rad
    )

    dlon = (
        lon_rad
        -
        lon0_rad
    )

    a = (
        np.sin(
            dlat
            /
            2.0
        )
        **
        2

        +

        np.cos(
            lat0_rad
        )
        *
        np.cos(
            lat_rad
        )
        *
        np.sin(
            dlon
            /
            2.0
        )
        **
        2
    )

    c = (
        2.0
        *
        np.arctan2(
            np.sqrt(
                a
            ),
            np.sqrt(
                1.0
                -
                a
            )
        )
    )

    return (
        raio
        *
        c
    )


# ============================================================
# CARREGAR BASE
# ============================================================

def carregar_base(
    caminho_csv
):

    df = pd.read_csv(
        caminho_csv,
        encoding="utf-8-sig"
    )

    df.columns = [
        str(
            coluna
        )
        .replace(
            "\ufeff",
            ""
        )
        .strip()

        for coluna
        in df.columns
    ]


    colunas = [
        "id_projeto",
        "desc_nome",
        "situacao",
        "sistema_resp",
        "ipi_final",
        "posicao_ipi_final",
        "latitude_representativa",
        "longitude_representativa",
        "tempo_servico_min"
    ]


    ausentes = [
        coluna

        for coluna
        in colunas

        if coluna
        not in
        df.columns
    ]


    if ausentes:

        raise ValueError(
            "Colunas ausentes na base: "
            +
            ", ".join(
                ausentes
            )
        )


    df[
        "ipi_final"
    ] = pd.to_numeric(
        df[
            "ipi_final"
        ],
        errors="coerce"
    )


    df[
        "latitude_representativa"
    ] = pd.to_numeric(
        df[
            "latitude_representativa"
        ],
        errors="coerce"
    )


    df[
        "longitude_representativa"
    ] = pd.to_numeric(
        df[
            "longitude_representativa"
        ],
        errors="coerce"
    )


    df[
        "tempo_servico_min"
    ] = pd.to_numeric(
        df[
            "tempo_servico_min"
        ],
        errors="coerce"
    ).fillna(
        SERVICO_PADRAO_MIN
    )


    df = (
        df
        .dropna(
            subset=[
                "ipi_final",
                "latitude_representativa",
                "longitude_representativa"
            ]
        )
        .drop_duplicates(
            subset=[
                "id_projeto"
            ]
        )
        .reset_index(
            drop=True
        )
    )


    return df


# ============================================================
# TRIAGEM ESPACIAL
# ============================================================

def criar_shortlist(
    base,
    origem_lat,
    origem_lon,
    tamanho_shortlist=TAMANHO_SHORTLIST
):

    df = base.copy()


    df[
        "distancia_haversine_origem_km"
    ] = haversine_vetorizado(
        origem_lat,
        origem_lon,
        df[
            "latitude_representativa"
        ].to_numpy(),
        df[
            "longitude_representativa"
        ].to_numpy()
    )


    # --------------------------------------------------------
    # Proxy de uma visita isolada.
    #
    # Não é usado como distância operacional final.
    # Serve SOMENTE para reduzir o universo antes do OSRM.
    # --------------------------------------------------------

    df[
        "tempo_proxy_solo_min"
    ] = (
        df[
            "tempo_servico_min"
        ]
        +
        (
            2.0
            *
            FATOR_PROXY_MIN_POR_KM
            *
            df[
                "distancia_haversine_origem_km"
            ]
        )
    )


    df[
        "eficiencia_proxy"
    ] = (
        df[
            "ipi_final"
        ]
        /
        df[
            "tempo_proxy_solo_min"
        ]
    )


    # --------------------------------------------------------
    # Vizinhança ampla:
    #
    # os 400 projetos mais próximos em linha reta.
    #
    # Isso mantém a triagem escalável e não força
    # projetos do litoral quando a origem estiver
    # no oeste do estado, por exemplo.
    # --------------------------------------------------------

    qtd_vizinhanca = min(
        TAMANHO_VIZINHANCA,
        len(
            df
        )
    )


    vizinhanca = (
        df
        .nsmallest(
            qtd_vizinhanca,
            "distancia_haversine_origem_km"
        )
        .copy()
    )


    # --------------------------------------------------------
    # Três canais obrigatórios:
    #
    # A) proximidade;
    # B) maior IPI;
    # C) eficiência prioridade/tempo proxy.
    #
    # Nenhum desses critérios substitui o OSRM.
    # --------------------------------------------------------

    ids_proximidade = set(
        vizinhanca
        .nsmallest(
            min(
                15,
                len(
                    vizinhanca
                )
            ),
            "distancia_haversine_origem_km"
        )[
            "id_projeto"
        ]
        .astype(
            str
        )
        .tolist()
    )


    ids_ipi = set(
        vizinhanca
        .nlargest(
            min(
                25,
                len(
                    vizinhanca
                )
            ),
            "ipi_final"
        )[
            "id_projeto"
        ]
        .astype(
            str
        )
        .tolist()
    )


    ids_eficiencia = set(
        vizinhanca
        .nlargest(
            min(
                25,
                len(
                    vizinhanca
                )
            ),
            "eficiencia_proxy"
        )[
            "id_projeto"
        ]
        .astype(
            str
        )
        .tolist()
    )


    obrigatorios = (
        ids_proximidade
        |
        ids_ipi
        |
        ids_eficiencia
    )


    # --------------------------------------------------------
    # Ranking agregado para completar a shortlist.
    # --------------------------------------------------------

    vizinhanca[
        "rank_distancia"
    ] = vizinhanca[
        "distancia_haversine_origem_km"
    ].rank(
        method="min",
        ascending=True
    )


    vizinhanca[
        "rank_ipi"
    ] = vizinhanca[
        "ipi_final"
    ].rank(
        method="min",
        ascending=False
    )


    vizinhanca[
        "rank_eficiencia"
    ] = vizinhanca[
        "eficiencia_proxy"
    ].rank(
        method="min",
        ascending=False
    )


    n_viz = max(
        1,
        len(
            vizinhanca
        )
    )


    vizinhanca[
        "score_triagem"
    ] = (
        0.30
        *
        (
            vizinhanca[
                "rank_distancia"
            ]
            /
            n_viz
        )
        +
        0.35
        *
        (
            vizinhanca[
                "rank_ipi"
            ]
            /
            n_viz
        )
        +
        0.35
        *
        (
            vizinhanca[
                "rank_eficiencia"
            ]
            /
            n_viz
        )
    )


    obrigatorios_df = (
        vizinhanca[
            vizinhanca[
                "id_projeto"
            ]
            .astype(
                str
            )
            .isin(
                obrigatorios
            )
        ]
        .copy()
    )


    restantes = (
        vizinhanca[
            ~
            vizinhanca[
                "id_projeto"
            ]
            .astype(
                str
            )
            .isin(
                obrigatorios
            )
        ]
        .sort_values(
            [
                "score_triagem",
                "distancia_haversine_origem_km"
            ],
            ascending=[
                True,
                True
            ]
        )
    )


    faltam = max(
        0,
        tamanho_shortlist
        -
        len(
            obrigatorios_df
        )
    )


    shortlist = pd.concat(
        [
            obrigatorios_df,
            restantes.head(
                faltam
            )
        ],
        ignore_index=True
    )


    # Se os canais obrigatórios ultrapassarem o limite,
    # usar ranking agregado para desempatar.
    if len(
        shortlist
    ) > tamanho_shortlist:

        shortlist = (
            shortlist
            .sort_values(
                [
                    "score_triagem",
                    "distancia_haversine_origem_km"
                ]
            )
            .head(
                tamanho_shortlist
            )
            .copy()
        )


    shortlist[
        "canal_proximidade"
    ] = shortlist[
        "id_projeto"
    ].astype(
        str
    ).isin(
        ids_proximidade
    )


    shortlist[
        "canal_ipi"
    ] = shortlist[
        "id_projeto"
    ].astype(
        str
    ).isin(
        ids_ipi
    )


    shortlist[
        "canal_eficiencia"
    ] = shortlist[
        "id_projeto"
    ].astype(
        str
    ).isin(
        ids_eficiencia
    )


    shortlist = (
        shortlist
        .sort_values(
            [
                "score_triagem",
                "distancia_haversine_origem_km"
            ]
        )
        .reset_index(
            drop=True
        )
    )


    return shortlist


# ============================================================
# OSRM TABLE
# ============================================================

def consultar_matriz_osrm(
    shortlist,
    origem_lat,
    origem_lon,
    timeout=60
):

    coordenadas = [
        (
            float(
                origem_lon
            ),
            float(
                origem_lat
            )
        )
    ]


    coordenadas.extend(
        [
            (
                float(
                    linha.longitude_representativa
                ),
                float(
                    linha.latitude_representativa
                )
            )

            for linha
            in shortlist.itertuples(
                index=False
            )
        ]
    )


    texto_coords = ";".join(
        (
            f"{lon:.6f},{lat:.6f}"
        )

        for lon, lat
        in coordenadas
    )


    url = (
        OSRM_BASE_URL
        +
        "/table/v1/driving/"
        +
        texto_coords
    )


    inicio = time.perf_counter()


    resposta = requests.get(
        url,
        params={
            "annotations":
                "duration,distance"
        },
        headers={
            "User-Agent":
                USER_AGENT
        },
        timeout=timeout
    )


    tempo_http = (
        time.perf_counter()
        -
        inicio
    )


    resposta.raise_for_status()


    dados = resposta.json()


    if dados.get(
        "code"
    ) != "Ok":

        raise RuntimeError(
            "OSRM Table retornou código: "
            +
            str(
                dados.get(
                    "code"
                )
            )
        )


    duracoes = np.asarray(
        dados[
            "durations"
        ],
        dtype=float
    )


    distancias = np.asarray(
        dados[
            "distances"
        ],
        dtype=float
    )


    # segundos -> minutos
    duracoes = (
        duracoes
        /
        60.0
    )


    # metros -> quilômetros
    distancias = (
        distancias
        /
        1000.0
    )


    sources = (
        dados.get(
            "sources",
            []
        )
        or
        []
    )


    snap_m = np.full(
        len(
            coordenadas
        ),
        np.nan,
        dtype=float
    )


    for indice, waypoint in enumerate(
        sources
    ):

        try:

            snap_m[
                indice
            ] = float(
                waypoint.get(
                    "distance"
                )
            )

        except Exception:

            pass


    return {
        "duracoes_min":
            duracoes,

        "distancias_km":
            distancias,

        "snap_m":
            snap_m,

        "tempo_http_s":
            tempo_http,

        "status_http":
            resposta.status_code,

        "quantidade_nos":
            len(
                coordenadas
            )
    }


# ============================================================
# FILTRAR PROJETOS OPERACIONALMENTE VIÁVEIS
# ============================================================

def filtrar_viaveis(
    shortlist,
    matriz,
    jornada_min=JORNADA_PADRAO_MIN
):

    dur = matriz[
        "duracoes_min"
    ]


    snap = matriz[
        "snap_m"
    ]


    registros = []


    for indice, linha in shortlist.iterrows():

        no = (
            indice
            +
            1
        )


        ida = dur[
            0,
            no
        ]


        volta = dur[
            no,
            0
        ]


        snap_projeto = (
            snap[
                no
            ]
            if no
            <
            len(
                snap
            )
            else
            np.nan
        )


        conectado = bool(
            np.isfinite(
                ida
            )
            and
            np.isfinite(
                volta
            )
        )


        snap_ok = bool(
            np.isnan(
                snap_projeto
            )
            or
            snap_projeto
            <=
            LIMITE_SNAP_PROJETO_M
        )


        tempo_solo = (
            float(
                ida
            )
            +
            float(
                linha[
                    "tempo_servico_min"
                ]
            )
            +
            float(
                volta
            )

            if conectado

            else

            np.inf
        )


        viavel = bool(
            conectado
            and
            snap_ok
            and
            tempo_solo
            <=
            jornada_min
        )


        registros.append(
            {
                "indice_shortlist":
                    indice,

                "id_projeto":
                    linha[
                        "id_projeto"
                    ],

                "osrm_ida_min":
                    ida,

                "osrm_volta_min":
                    volta,

                "tempo_solo_min":
                    tempo_solo,

                "snap_m":
                    snap_projeto,

                "conectado":
                    conectado,

                "snap_ok":
                    snap_ok,

                "viavel_individual":
                    viavel
            }
        )


    diagnostico = pd.DataFrame(
        registros
    )


    indices_viaveis = (
        diagnostico.loc[
            diagnostico[
                "viavel_individual"
            ],
            "indice_shortlist"
        ]
        .astype(
            int
        )
        .tolist()
    )


    return (
        diagnostico,
        indices_viaveis
    )


# ============================================================
# EXTRAIR SUBMATRIZ
# ============================================================

def preparar_subproblema(
    shortlist,
    matriz,
    indices_viaveis
):

    if not indices_viaveis:

        raise RuntimeError(
            "Nenhum projeto é viável individualmente "
            "para a jornada informada."
        )


    indices_tabela = (
        [
            0
        ]
        +
        [
            indice
            +
            1

            for indice
            in indices_viaveis
        ]
    )


    dur = matriz[
        "duracoes_min"
    ][
        np.ix_(
            indices_tabela,
            indices_tabela
        )
    ]


    dist = matriz[
        "distancias_km"
    ][
        np.ix_(
            indices_tabela,
            indices_tabela
        )
    ]


    candidatos = (
        shortlist
        .iloc[
            indices_viaveis
        ]
        .reset_index(
            drop=True
        )
        .copy()
    )


    return (
        candidatos,
        dur,
        dist
    )


# ============================================================
# TEMPO E DISTÂNCIA DE UMA ROTA
#
# A rota contém índices 0..n-1 dos projetos.
# Na matriz:
#
# nó 0 = origem
# nó projeto i = i + 1
# ============================================================

def avaliar_rota(
    rota,
    duracoes,
    distancias,
    servicos
):

    if not rota:

        return {
            "tempo_viagem_min":
                0.0,

            "tempo_servico_min":
                0.0,

            "tempo_total_min":
                0.0,

            "distancia_km":
                0.0
        }


    atual = 0

    viagem = 0.0

    distancia = 0.0

    servico = 0.0


    for indice in rota:

        no = (
            int(
                indice
            )
            +
            1
        )


        trecho_tempo = duracoes[
            atual,
            no
        ]


        trecho_dist = distancias[
            atual,
            no
        ]


        if not (
            np.isfinite(
                trecho_tempo
            )
            and
            np.isfinite(
                trecho_dist
            )
        ):

            return {
                "tempo_viagem_min":
                    np.inf,

                "tempo_servico_min":
                    np.inf,

                "tempo_total_min":
                    np.inf,

                "distancia_km":
                    np.inf
            }


        viagem += float(
            trecho_tempo
        )


        distancia += float(
            trecho_dist
        )


        servico += float(
            servicos[
                indice
            ]
        )


        atual = no


    volta_tempo = duracoes[
        atual,
        0
    ]


    volta_dist = distancias[
        atual,
        0
    ]


    if not (
        np.isfinite(
            volta_tempo
        )
        and
        np.isfinite(
            volta_dist
        )
    ):

        return {
            "tempo_viagem_min":
                np.inf,

            "tempo_servico_min":
                np.inf,

            "tempo_total_min":
                np.inf,

            "distancia_km":
                np.inf
        }


    viagem += float(
        volta_tempo
    )


    distancia += float(
        volta_dist
    )


    return {
        "tempo_viagem_min":
            viagem,

        "tempo_servico_min":
            servico,

        "tempo_total_min":
            (
                viagem
                +
                servico
            ),

        "distancia_km":
            distancia
    }


# ============================================================
# DECODIFICADOR DO CROMOSSOMO
# ============================================================

def decodificar_permutacao(
    permutacao,
    duracoes,
    servicos,
    jornada_min
):

    rota = []

    atual = 0

    tempo_consumido = 0.0


    for indice in permutacao:

        indice = int(
            indice
        )


        no = (
            indice
            +
            1
        )


        ida = duracoes[
            atual,
            no
        ]


        volta = duracoes[
            no,
            0
        ]


        if not (
            np.isfinite(
                ida
            )
            and
            np.isfinite(
                volta
            )
        ):

            continue


        projetado_com_retorno = (
            tempo_consumido
            +
            float(
                ida
            )
            +
            float(
                servicos[
                    indice
                ]
            )
            +
            float(
                volta
            )
        )


        if (
            projetado_com_retorno
            <=
            jornada_min
            +
            1e-9
        ):

            rota.append(
                indice
            )

            tempo_consumido += (
                float(
                    ida
                )
                +
                float(
                    servicos[
                        indice
                    ]
                )
            )

            atual = no


    return rota


# ============================================================
# SCORE LEXICOGRÁFICO
# ============================================================

def score_rota(
    rota,
    premios,
    duracoes,
    distancias,
    servicos,
    jornada_min
):

    avaliacao = avaliar_rota(
        rota,
        duracoes,
        distancias,
        servicos
    )


    if (
        not np.isfinite(
            avaliacao[
                "tempo_total_min"
            ]
        )
        or
        avaliacao[
            "tempo_total_min"
        ]
        >
        jornada_min
        +
        1e-9
    ):

        return (
            -1e30,
            -1e30,
            -1e30
        )


    premio = float(
        np.sum(
            premios[
                rota
            ]
        )
        if rota
        else
        0.0
    )


    return (
        premio,

        -
        float(
            avaliacao[
                "tempo_total_min"
            ]
        ),

        len(
            rota
        )
    )


# ============================================================
# ORDER CROSSOVER
# ============================================================

def crossover_ox(
    pai1,
    pai2,
    rng
):

    n = len(
        pai1
    )


    if n < 2:

        return pai1.copy()


    a, b = sorted(
        rng.sample(
            range(
                n
            ),
            2
        )
    )


    if a == b:

        return pai1.copy()


    # intervalo [a, b]
    b += 1


    filho = [
        None
    ] * n


    filho[
        a:b
    ] = pai1[
        a:b
    ]


    usados = set(
        filho[
            a:b
        ]
    )


    restantes = [
        gene

        for gene
        in pai2

        if gene
        not in usados
    ]


    posicoes = (
        list(
            range(
                b,
                n
            )
        )
        +
        list(
            range(
                0,
                a
            )
        )
    )


    for posicao, gene in zip(
        posicoes,
        restantes
    ):

        filho[
            posicao
        ] = gene


    return filho


# ============================================================
# MUTAÇÃO
# ============================================================

def mutar(
    individuo,
    rng,
    taxa_swap=0.15,
    taxa_inversao=0.05
):

    individuo = individuo.copy()

    n = len(
        individuo
    )


    if n < 2:

        return individuo


    if rng.random() < taxa_swap:

        a, b = rng.sample(
            range(
                n
            ),
            2
        )

        individuo[
            a
        ], individuo[
            b
        ] = (
            individuo[
                b
            ],
            individuo[
                a
            ]
        )


    if rng.random() < taxa_inversao:

        a, b = sorted(
            rng.sample(
                range(
                    n
                ),
                2
            )
        )

        individuo[
            a:b+1
        ] = reversed(
            individuo[
                a:b+1
            ]
        )


    return individuo


# ============================================================
# BUSCA LOCAL SOBRE ROTA DECODIFICADA
# ============================================================

def busca_local(
    rota_inicial,
    premios,
    duracoes,
    distancias,
    servicos,
    jornada_min
):

    rota = list(
        rota_inicial
    )


    n_total = len(
        premios
    )


    def melhor_score(
        r
    ):

        return score_rota(
            r,
            premios,
            duracoes,
            distancias,
            servicos,
            jornada_min
        )


    # --------------------------------------------------------
    # 1. Melhorar a ordem sem alterar o conjunto.
    #    Swap + reversão.
    # --------------------------------------------------------

    melhorou = True


    while melhorou:

        melhorou = False

        score_atual = melhor_score(
            rota
        )


        for i in range(
            len(
                rota
            )
        ):

            for j in range(
                i + 1,
                len(
                    rota
                )
            ):

                # swap
                candidata = rota.copy()

                candidata[
                    i
                ], candidata[
                    j
                ] = (
                    candidata[
                        j
                    ],
                    candidata[
                        i
                    ]
                )


                score_cand = melhor_score(
                    candidata
                )


                if score_cand > score_atual:

                    rota = candidata

                    score_atual = score_cand

                    melhorou = True


                # reversão
                candidata = (
                    rota[
                        :i
                    ]
                    +
                    list(
                        reversed(
                            rota[
                                i:j+1
                            ]
                        )
                    )
                    +
                    rota[
                        j+1:
                    ]
                )


                score_cand = melhor_score(
                    candidata
                )


                if score_cand > score_atual:

                    rota = candidata

                    score_atual = score_cand

                    melhorou = True


        # evita ciclos longos
        if not melhorou:

            break


    # --------------------------------------------------------
    # 2. Inserir projetos ainda ausentes.
    # --------------------------------------------------------

    while True:

        usados = set(
            rota
        )


        ausentes = [
            indice

            for indice
            in range(
                n_total
            )

            if indice
            not in usados
        ]


        melhor_rota = None

        melhor_chave = None


        for candidato in ausentes:

            for posicao in range(
                len(
                    rota
                )
                +
                1
            ):

                teste = rota.copy()

                teste.insert(
                    posicao,
                    candidato
                )


                chave = melhor_score(
                    teste
                )


                if chave[
                    0
                ] < 0:

                    continue


                if (
                    melhor_chave is None
                    or
                    chave
                    >
                    melhor_chave
                ):

                    melhor_chave = chave

                    melhor_rota = teste


        score_atual = melhor_score(
            rota
        )


        if (
            melhor_rota is None
            or
            melhor_chave
            <=
            score_atual
        ):

            break


        rota = melhor_rota


    # --------------------------------------------------------
    # 3. Substituição 1 por 1.
    # --------------------------------------------------------

    melhorou = True


    while melhorou:

        melhorou = False

        score_atual = melhor_score(
            rota
        )

        usados = set(
            rota
        )


        ausentes = [
            indice

            for indice
            in range(
                n_total
            )

            if indice
            not in usados
        ]


        for candidato in ausentes:

            for posicao in range(
                len(
                    rota
                )
            ):

                removido = rota[
                    posicao
                ]


                # Sem ganho de IPI, não vale substituir.
                if (
                    premios[
                        candidato
                    ]
                    <=
                    premios[
                        removido
                    ]
                    +
                    1e-12
                ):

                    continue


                teste = rota.copy()

                teste[
                    posicao
                ] = candidato


                chave = melhor_score(
                    teste
                )


                if chave > score_atual:

                    rota = teste

                    score_atual = chave

                    melhorou = True

                    break


            if melhorou:

                break


    # --------------------------------------------------------
    # 4. Reordenação final.
    # --------------------------------------------------------

    melhorou = True


    while melhorou:

        melhorou = False

        score_atual = melhor_score(
            rota
        )


        for i in range(
            len(
                rota
            )
        ):

            for j in range(
                i + 1,
                len(
                    rota
                )
            ):

                teste = rota.copy()

                teste[
                    i
                ], teste[
                    j
                ] = (
                    teste[
                        j
                    ],
                    teste[
                        i
                    ]
                )


                chave = melhor_score(
                    teste
                )


                if chave > score_atual:

                    rota = teste

                    score_atual = chave

                    melhorou = True


    return rota


# ============================================================
# ALGORITMO MEMÉTICO
# ============================================================

def otimizar_memetico(
    candidatos,
    duracoes,
    distancias,
    jornada_min,
    populacao=80,
    geracoes=70,
    torneio=4,
    elite=2,
    seed=20260901
):

    inicio = time.perf_counter()


    n = len(
        candidatos
    )


    if n == 0:

        raise RuntimeError(
            "Nenhum candidato disponível para otimização."
        )


    premios = candidatos[
        "ipi_final"
    ].to_numpy(
        dtype=float
    )


    servicos = candidatos[
        "tempo_servico_min"
    ].to_numpy(
        dtype=float
    )


    rng = random.Random(
        int(
            seed
        )
    )


    genes = list(
        range(
            n
        )
    )


    # --------------------------------------------------------
    # Sementes determinísticas úteis
    # --------------------------------------------------------

    solo = np.asarray(
        [
            (
                duracoes[
                    0,
                    i + 1
                ]
                +
                servicos[
                    i
                ]
                +
                duracoes[
                    i + 1,
                    0
                ]
            )

            for i
            in range(
                n
            )
        ],
        dtype=float
    )


    eficiencia = (
        premios
        /
        np.maximum(
            solo,
            1e-9
        )
    )


    radial = np.asarray(
        [
            (
                duracoes[
                    0,
                    i + 1
                ]
                +
                duracoes[
                    i + 1,
                    0
                ]
            )

            for i
            in range(
                n
            )
        ],
        dtype=float
    )


    sementes = [
        np.argsort(
            -
            premios
        ).tolist(),

        np.argsort(
            -
            eficiencia
        ).tolist(),

        np.argsort(
            solo
        ).tolist(),

        np.argsort(
            radial
        ).tolist()
    ]


    populacao_atual = [
        s.copy()
        for s
        in sementes
    ]


    while len(
        populacao_atual
    ) < populacao:

        individuo = genes.copy()

        rng.shuffle(
            individuo
        )

        populacao_atual.append(
            individuo
        )


    def avaliar_individuo(
        individuo
    ):

        rota = decodificar_permutacao(
            individuo,
            duracoes,
            servicos,
            jornada_min
        )


        score = score_rota(
            rota,
            premios,
            duracoes,
            distancias,
            servicos,
            jornada_min
        )


        return (
            score,
            rota
        )


    melhor_score_global = None

    melhor_rota_global = []

    melhor_individuo_global = None

    melhor_geracao = 0


    for geracao in range(
        geracoes
        +
        1
    ):

        avaliados = []


        for individuo in populacao_atual:

            score, rota = avaliar_individuo(
                individuo
            )


            avaliados.append(
                (
                    score,
                    individuo,
                    rota
                )
            )


            if (
                melhor_score_global is None
                or
                score
                >
                melhor_score_global
            ):

                melhor_score_global = score

                melhor_rota_global = rota.copy()

                melhor_individuo_global = individuo.copy()

                melhor_geracao = geracao


        if geracao == geracoes:

            break


        avaliados.sort(
            key=lambda x:
                x[
                    0
                ],
            reverse=True
        )


        nova_populacao = [
            item[
                1
            ].copy()

            for item
            in avaliados[
                :elite
            ]
        ]


        def selecionar_torneio():

            amostra = rng.sample(
                avaliados,
                k=min(
                    torneio,
                    len(
                        avaliados
                    )
                )
            )

            vencedor = max(
                amostra,
                key=lambda x:
                    x[
                        0
                    ]
            )

            return vencedor[
                1
            ]


        while len(
            nova_populacao
        ) < populacao:

            pai1 = selecionar_torneio()

            pai2 = selecionar_torneio()


            if rng.random() < 0.90:

                filho = crossover_ox(
                    pai1,
                    pai2,
                    rng
                )

            else:

                filho = pai1.copy()


            filho = mutar(
                filho,
                rng
            )


            nova_populacao.append(
                filho
            )


        populacao_atual = nova_populacao


    # --------------------------------------------------------
    # Busca local sobre:
    #
    # - melhor solução do GA;
    # - quatro sementes determinísticas.
    # --------------------------------------------------------

    rotas_para_refinar = [
        melhor_rota_global
    ]


    for semente in sementes:

        rotas_para_refinar.append(
            decodificar_permutacao(
                semente,
                duracoes,
                servicos,
                jornada_min
            )
        )


    melhor_rota_final = melhor_rota_global.copy()

    melhor_score_final = score_rota(
        melhor_rota_final,
        premios,
        duracoes,
        distancias,
        servicos,
        jornada_min
    )


    for rota_inicial in rotas_para_refinar:

        refinada = busca_local(
            rota_inicial,
            premios,
            duracoes,
            distancias,
            servicos,
            jornada_min
        )


        score_refinada = score_rota(
            refinada,
            premios,
            duracoes,
            distancias,
            servicos,
            jornada_min
        )


        if score_refinada > melhor_score_final:

            melhor_rota_final = refinada

            melhor_score_final = score_refinada


    avaliacao_final = avaliar_rota(
        melhor_rota_final,
        duracoes,
        distancias,
        servicos
    )


    tempo_execucao = (
        time.perf_counter()
        -
        inicio
    )


    return {
        "rota_indices":
            [
                int(
                    indice
                )

                for indice
                in melhor_rota_final
            ],

        "ipi_total":
            float(
                melhor_score_final[
                    0
                ]
            ),

        "tempo_viagem_min":
            float(
                avaliacao_final[
                    "tempo_viagem_min"
                ]
            ),

        "tempo_servico_min":
            float(
                avaliacao_final[
                    "tempo_servico_min"
                ]
            ),

        "tempo_total_min":
            float(
                avaliacao_final[
                    "tempo_total_min"
                ]
            ),

        "distancia_km":
            float(
                avaliacao_final[
                    "distancia_km"
                ]
            ),

        "folga_min":
            float(
                jornada_min
                -
                avaliacao_final[
                    "tempo_total_min"
                ]
            ),

        "quantidade_projetos":
            len(
                melhor_rota_final
            ),

        "melhor_geracao_ga":
            int(
                melhor_geracao
            ),

        "tempo_otimizacao_s":
            float(
                tempo_execucao
            ),

        "populacao":
            int(
                populacao
            ),

        "geracoes":
            int(
                geracoes
            ),

        "seed":
            int(
                seed
            )
    }


# ============================================================
# GEOMETRIA DA ROTA FINAL
# ============================================================

def consultar_geometria_rota(
    origem_lat,
    origem_lon,
    projetos_selecionados,
    timeout=45
):

    coordenadas = [
        (
            float(
                origem_lon
            ),
            float(
                origem_lat
            )
        )
    ]


    coordenadas.extend(
        [
            (
                float(
                    linha.longitude_representativa
                ),
                float(
                    linha.latitude_representativa
                )
            )

            for linha
            in projetos_selecionados.itertuples(
                index=False
            )
        ]
    )


    # retorno à origem
    coordenadas.append(
        (
            float(
                origem_lon
            ),
            float(
                origem_lat
            )
        )
    )


    texto_coords = ";".join(
        (
            f"{lon:.6f},{lat:.6f}"
        )

        for lon, lat
        in coordenadas
    )


    url = (
        OSRM_BASE_URL
        +
        "/route/v1/driving/"
        +
        texto_coords
    )


    resposta = requests.get(
        url,
        params={
            "overview":
                "full",

            "geometries":
                "geojson",

            "steps":
                "false",

            "continue_straight":
                "false"
        },
        headers={
            "User-Agent":
                USER_AGENT
        },
        timeout=timeout
    )


    resposta.raise_for_status()


    dados = resposta.json()


    if (
        dados.get(
            "code"
        )
        !=
        "Ok"
        or
        not dados.get(
            "routes"
        )
    ):

        raise RuntimeError(
            "OSRM Route não retornou uma rota válida."
        )


    rota = dados[
        "routes"
    ][
        0
    ]


    return {
        "geojson":
            rota[
                "geometry"
            ],

        "tempo_rota_min":
            float(
                rota[
                    "duration"
                ]
            )
            /
            60.0,

        "distancia_rota_km":
            float(
                rota[
                    "distance"
                ]
            )
            /
            1000.0,

        "quantidade_pernas":
            len(
                rota.get(
                    "legs",
                    []
                )
            )
    }


# ============================================================
# PIPELINE COMPLETO
# ============================================================

def planejar_rota(
    caminho_base,
    origem_lat,
    origem_lon,
    jornada_min=JORNADA_PADRAO_MIN,
    servico_padrao_min=SERVICO_PADRAO_MIN,
    seed=20260901,
    gerar_geometria=True
):

    inicio_total = time.perf_counter()


    base = carregar_base(
        caminho_base
    )


    shortlist = criar_shortlist(
        base,
        origem_lat,
        origem_lon
    )


    matriz = consultar_matriz_osrm(
        shortlist,
        origem_lat,
        origem_lon
    )


    (
        diagnostico,
        indices_viaveis
    ) = filtrar_viaveis(
        shortlist,
        matriz,
        jornada_min=jornada_min
    )


    candidatos, duracoes, distancias = (
        preparar_subproblema(
            shortlist,
            matriz,
            indices_viaveis
        )
    )


    # Garantir tempo de serviço definido.
    candidatos[
        "tempo_servico_min"
    ] = pd.to_numeric(
        candidatos[
            "tempo_servico_min"
        ],
        errors="coerce"
    ).fillna(
        float(
            servico_padrao_min
        )
    )


    resultado = otimizar_memetico(
        candidatos,
        duracoes,
        distancias,
        jornada_min=jornada_min,
        seed=seed
    )


    rota_indices = resultado[
        "rota_indices"
    ]


    selecionados = (
        candidatos
        .iloc[
            rota_indices
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )


    selecionados[
        "sequencia"
    ] = (
        np.arange(
            len(
                selecionados
            )
        )
        +
        1
    )


    geometria = None


    if (
        gerar_geometria
        and
        len(
            selecionados
        )
        >
        0
    ):

        geometria = consultar_geometria_rota(
            origem_lat,
            origem_lon,
            selecionados
        )


    resultado[
        "tempo_pipeline_total_s"
    ] = float(
        time.perf_counter()
        -
        inicio_total
    )


    resultado[
        "shortlist_total"
    ] = int(
        len(
            shortlist
        )
    )


    resultado[
        "candidatos_viaveis"
    ] = int(
        len(
            candidatos
        )
    )


    resultado[
        "osrm_table_http_s"
    ] = float(
        matriz[
            "tempo_http_s"
        ]
    )


    resultado[
        "osrm_table_nos"
    ] = int(
        matriz[
            "quantidade_nos"
        ]
    )


    resultado[
        "origem_snap_m"
    ] = (
        float(
            matriz[
                "snap_m"
            ][
                0
            ]
        )
        if (
            len(
                matriz[
                    "snap_m"
                ]
            )
            >
            0
            and
            np.isfinite(
                matriz[
                    "snap_m"
                ][
                    0
                ]
            )
        )
        else
        None
    )


    return {
        "resumo":
            resultado,

        "shortlist":
            shortlist,

        "diagnostico":
            diagnostico,

        "candidatos":
            candidatos,

        "selecionados":
            selecionados,

        "geometria":
            geometria,

        "duracoes_min":
            duracoes,

        "distancias_km":
            distancias
    }
