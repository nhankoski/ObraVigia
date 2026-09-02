
from pathlib import Path
from datetime import date, datetime, timedelta, time as dt_time

import math
import json
import html
import threading
import time

import requests

import folium
from branca.element import Element
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from streamlit_folium import st_folium

from dados_publicos_257 import (
    carregar_candidatos_padrao,
    ids_alertas,
    montar_alertas_contexto,
    montar_candidatos_contexto,
    obter_valores_pagos_lote,
    popup_publico,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="ObraVigia",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)


BASE_DIR = Path(__file__).resolve().parent

DADOS = BASE_DIR / "dados"


# ============================================================
# CARREGAMENTO
# ============================================================

@st.cache_data
def carregar_dados():

    projetos = pd.read_csv(
        DADOS / "projetos_rota.csv"
    )

    arcos = pd.read_csv(
        DADOS / "arcos_rota.csv"
    )

    revisao = pd.read_csv(
        DADOS / "projetos_revisao_espacial.csv"
    )

    nos = pd.read_csv(
        DADOS / "nos_operacionais.csv"
    )

    with open(
        DADOS / "resumo_rota.json",
        "r",
        encoding="utf-8"
    ) as arquivo:

        resumo = json.load(
            arquivo
        )

    with open(
        DADOS / "rota.geojson",
        "r",
        encoding="utf-8"
    ) as arquivo:

        geojson = json.load(
            arquivo
        )

    return (
        projetos,
        arcos,
        revisao,
        nos,
        resumo,
        geojson
    )


(
    projetos,
    arcos,
    revisao,
    nos,
    resumo,
    geojson
) = carregar_dados()


# ============================================================
# NORMALIZAÇÃO
# ============================================================

projetos[
    "sequencia"
] = pd.to_numeric(
    projetos[
        "sequencia"
    ],
    errors="coerce"
)


projetos = (
    projetos
    .sort_values(
        "sequencia"
    )
    .reset_index(
        drop=True
    )
)


origens = nos.loc[
    nos[
        "tipo_no"
    ]
    .eq(
        "origem"
    )
]


if len(
    origens
) != 1:

    st.error(
        "Não foi possível identificar a origem operacional."
    )

    st.stop()


origem = origens.iloc[
    0
]


NOME_ORIGEM = str(
    origem[
        "nome"
    ]
)


LAT_ORIGEM = float(
    origem[
        "latitude"
    ]
)


LON_ORIGEM = float(
    origem[
        "longitude"
    ]
)


# ============================================================
# FUNÇÕES DE FORMATAÇÃO
# ============================================================

def minutos_para_texto(
    minutos
):

    minutos = float(
        minutos
    )

    horas = int(
        minutos
        //
        60
    )

    restante = int(
        round(
            minutos
            -
            60
            *
            horas
        )
    )

    if horas == 0:

        return (
            f"{restante} min"
        )

    return (
        f"{horas}h {restante:02d}min"
    )


def horario_por_minutos(
    inicio,
    minutos
):

    instante = (
        inicio
        +
        timedelta(
            minutes=float(
                minutos
            )
        )
    )

    return instante.strftime(
        "%H:%M"
    )



# ============================================================
# INTERPRETAÇÃO VISUAL DO IPI
# ============================================================

def normalizar_ipi_visual(
    valor
):

    try:

        valor = float(
            valor
        )

    except Exception:

        return 0.0


    return max(
        0.0,
        min(
            100.0,
            valor
        )
    )


def cor_ipi(
    valor
):

    valor = normalizar_ipi_visual(
        valor
    )

    # 0 -> 120 graus = verde
    # 100 -> 0 graus = vermelho
    #
    # A passagem natural pelo círculo HSL produz:
    # verde -> amarelo -> laranja -> vermelho.

    matiz = (
        120.0
        -
        (
            120.0
            *
            valor
            /
            100.0
        )
    )

    return (
        f"hsl({matiz:.0f}, 72%, 40%)"
    )


def cor_texto_ipi(
    valor
):

    valor = normalizar_ipi_visual(
        valor
    )

    # Amarelos precisam de texto escuro
    # para manter contraste.

    if 30 <= valor <= 65:

        return "#111111"

    return "#ffffff"


def prioridade_rotulo(
    valor
):

    valor = normalizar_ipi_visual(
        valor
    )

    if valor < 20:

        return "Baixa"

    if valor < 40:

        return "Moderada"

    if valor < 60:

        return "Intermediária"

    if valor < 80:

        return "Alta"

    return "Muito alta"




# ============================================================
# TREVO DE MARCADORES — VERSÃO VISUAL DINÂMICA
# ============================================================


def renderizar_mapa_leaflet_trevo(
    origem_lat,
    origem_lon,
    origem_nome,
    projetos_mapa,
    candidatos_contexto=None,
    alertas_contexto=None,
    rota_geojson=None,
    altura=650
):

    # ========================================================
    # NORMALIZAÇÃO DOS DADOS
    # ========================================================

    projetos_normalizados = []


    for item in projetos_mapa:

        projetos_normalizados.append(
            {
                "lat":
                    float(
                        item[
                            "lat"
                        ]
                    ),

                "lng":
                    float(
                        item[
                            "lng"
                        ]
                    ),

                "numero":
                    int(
                        item[
                            "numero"
                        ]
                    ),

                "cor":
                    str(
                        item[
                            "cor"
                        ]
                    ),

                "cor_texto":
                    str(
                        item.get(
                            "cor_texto",
                            "#111827"
                        )
                    ),

                "tooltip":
                    str(
                        item.get(
                            "tooltip",
                            ""
                        )
                    ),

                "popup":
                    str(
                        item.get(
                            "popup",
                            ""
                        )
                    )
            }
        )


    candidatos_normalizados = []


    if candidatos_contexto is not None:

        for item in candidatos_contexto:

            candidatos_normalizados.append(
                {
                    "lat":
                        float(
                            item[
                                "lat"
                            ]
                        ),

                    "lng":
                        float(
                            item[
                                "lng"
                            ]
                        ),

                    "tooltip":
                        str(
                            item.get(
                                "tooltip",
                                ""
                            )
                        ),

                    "popup":
                        str(
                            item.get(
                                "popup",
                                ""
                            )
                        )
                }
            )


    alertas_normalizados = []


    if alertas_contexto is not None:

        for item in alertas_contexto:

            alertas_normalizados.append(
                {
                    "lat":
                        float(
                            item[
                                "lat"
                            ]
                        ),

                    "lng":
                        float(
                            item[
                                "lng"
                            ]
                        ),

                    "tooltip":
                        str(
                            item.get(
                                "tooltip",
                                ""
                            )
                        ),

                    "popup":
                        str(
                            item.get(
                                "popup",
                                ""
                            )
                        )
                }
            )


    payload = {
        "origem": {
            "lat":
                float(
                    origem_lat
                ),

            "lng":
                float(
                    origem_lon
                ),

            "nome":
                str(
                    origem_nome
                )
        },

        "projetos":
            projetos_normalizados,

        "candidatos_contexto":
            candidatos_normalizados,

        "alertas_contexto":
            alertas_normalizados,

        "rota":
            rota_geojson
    }


    # Evita que eventual </script> em texto dos dados
    # encerre prematuramente o script HTML.

    payload_json = (
        json.dumps(
            payload,
            ensure_ascii=False
        )
        .replace(
            "</",
            "<\\/"
        )
    )


    pagina = r"""
<!DOCTYPE html>

<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
>

<style>

    html,
    body {

        margin: 0;
        padding: 0;

        width: 100%;
        height: 100%;

        overflow: hidden;

        background:
            #f7f7f7;
    }


    #obravigia-map {

        width: 100%;
        height: __ALTURA__px;

        border-radius:
            8px;
    }


    /* ======================================================
       MARCADOR DAS OBRAS
       ====================================================== */

    .obravigia-marker {

        background:
            transparent !important;

        border:
            none !important;

        overflow:
            visible !important;

        pointer-events:
            none !important;
    }


    .petala {

        position:
            relative;

        width:
            46px;

        height:
            30px;

        overflow:
            visible;

        cursor:
            pointer;

        pointer-events:
            auto !important;

        transition:
            transform
            140ms
            ease-out;

        will-change:
            transform;
    }


    .petala-forma {

        position:
            absolute;

        left:
            0;

        top:
            0;

        width:
            46px;

        height:
            30px;

        transform-origin:
            23px
            15px;

        transition:
            transform
            140ms
            ease-out;

        z-index:
            1;

        pointer-events:
            none;
    }


    .petala-numero {

        position:
            absolute;

        left:
            8px;

        top:
            4px;

        width:
            30px;

        height:
            21px;

        display:
            flex;

        align-items:
            center;

        justify-content:
            center;

        font-family:
            Arial,
            sans-serif;

        font-size:
            13px;

        font-weight:
            900;

        line-height:
            1;

        text-align:
            center;

        z-index:
            20;

        pointer-events:
            none;
    }


    /* ======================================================
       ORIGEM
       ====================================================== */

    .origem-container {

        background:
            transparent !important;

        border:
            none !important;
    }


    .origem-pin {

        width:
            38px;

        height:
            38px;

        border-radius:
            50%;

        display:
            flex;

        align-items:
            center;

        justify-content:
            center;

        background:
            #38a6dc;

        border:
            3px
            solid
            white;

        box-shadow:
            0
            2px
            5px
            rgba(
                0,
                0,
                0,
                0.32
            );

        color:
            white;

        font-family:
            Arial,
            sans-serif;

        font-size:
            22px;

        font-weight:
            700;
    }

</style>

</head>


<body>

<div id="obravigia-map"></div>


<script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">
</script>


<script>

(function () {

    const payload =
        __PAYLOAD__;


    // ======================================================
    // MAPA
    // ======================================================

    const map =
        L.map(
            "obravigia-map",
            {
                zoomControl:
                    true,

                preferCanvas:
                    false
            }
        );


    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom:
                19,

            attribution:
                "&copy; OpenStreetMap"
        }
    ).addTo(
        map
    );


    L.control.scale(
        {
            imperial:
                false
        }
    ).addTo(
        map
    );


    // ======================================================
    // DEMAIS CANDIDATOS INDIVIDUALMENTE VIÁVEIS
    //
    // Apenas contexto visual.
    // Não participam dos trevos.
    // ======================================================

    const candidatosContexto =
        (
            payload.candidatos_contexto
            ||
            []
        );


    const camadaCandidatos =
        L.layerGroup();


    candidatosContexto.forEach(
        function (
            item
        ) {

            const ponto =
                L.circleMarker(
                    [
                        item.lat,
                        item.lng
                    ],
                    {
                        radius:
                            5,

                        color:
                            "#ffffff",

                        weight:
                            1.1,

                        opacity:
                            0.95,

                        fillColor:
                            "#7d858d",

                        fillOpacity:
                            0.72,

                        bubblingMouseEvents:
                            false
                    }
                );


            if (
                item.tooltip
            ) {

                ponto.bindTooltip(
                    item.tooltip,
                    {
                        direction:
                            "top"
                    }
                );
            }


            if (
                item.popup
            ) {

                ponto.bindPopup(
                    item.popup,
                    {
                        maxWidth:
                            390
                    }
                );
            }


            ponto.addTo(
                camadaCandidatos
            );
        }
    );


    camadaCandidatos.addTo(
        map
    );


    // ======================================================
    // ATENÇÃO CADASTRAL
    //
    // Registros públicos mantidos no mapa,
    // mas não utilizados automaticamente pelo componente
    // financeiro da priorização.
    // ======================================================

    const alertasContexto =
        (
            payload.alertas_contexto
            ||
            []
        );


    const camadaAlertas =
        L.layerGroup();


    alertasContexto.forEach(
        function (
            item
        ) {

            const ponto =
                L.circleMarker(
                    [
                        item.lat,
                        item.lng
                    ],
                    {
                        radius:
                            5,

                        color:
                            "#d97706",

                        weight:
                            1.7,

                        opacity:
                            0.95,

                        fillColor:
                            "#9ca3af",

                        fillOpacity:
                            0.78,

                        bubblingMouseEvents:
                            false
                    }
                );


            if (
                item.tooltip
            ) {

                ponto.bindTooltip(
                    item.tooltip,
                    {
                        direction:
                            "top"
                    }
                );
            }


            if (
                item.popup
            ) {

                ponto.bindPopup(
                    item.popup,
                    {
                        maxWidth:
                            390
                    }
                );
            }


            ponto.addTo(
                camadaAlertas
            );
        }
    );


    camadaAlertas.addTo(
        map
    );


    // ======================================================
    // CONTROLE ÚNICO DAS CAMADAS DE CONTEXTO
    //
    // Um único botão permite ligar/desligar:
    //
    // - demais candidatas viáveis;
    // - registros de atenção cadastral.
    // ======================================================

    const overlaysContexto =
        {};


    if (
        candidatosContexto.length
        >
        0
    ) {

        overlaysContexto[
            (
                "Demais candidatas viáveis ("
                +
                candidatosContexto.length
                +
                ")"
            )
        ] =
            camadaCandidatos;
    }


    if (
        alertasContexto.length
        >
        0
    ) {

        overlaysContexto[
            (
                "Atenção cadastral ("
                +
                alertasContexto.length
                +
                ")"
            )
        ] =
            camadaAlertas;
    }


    if (
        Object.keys(
            overlaysContexto
        ).length
        >
        0
    ) {

        L.control.layers(
            {},
            overlaysContexto,
            {
                collapsed:
                    true,

                position:
                    "topright"
            }
        ).addTo(
            map
        );
    }


    // ======================================================
    // ROTA
    // ======================================================

    if (
        payload.rota
    ) {

        try {

            L.geoJSON(
                payload.rota,
                {
                    style:
                        function () {

                            return {
                                color:
                                    "#4285F4",

                                weight:
                                    5,

                                opacity:
                                    0.88
                            };
                        }
                }
            ).addTo(
                map
            );

        } catch (
            erro
        ) {

            console.warn(
                "Não foi possível desenhar a rota:",
                erro
            );
        }
    }


    // ======================================================
    // ORIGEM
    // ======================================================

    const origemIcon =
        L.divIcon(
            {
                className:
                    "origem-container",

                html:
                    '<div class="origem-pin">⌂</div>',

                iconSize:
                    [
                        44,
                        44
                    ],

                iconAnchor:
                    [
                        22,
                        22
                    ]
            }
        );


    const origem =
        L.marker(
            [
                payload.origem.lat,
                payload.origem.lng
            ],
            {
                icon:
                    origemIcon,

                zIndexOffset:
                    4000
            }
        );


    origem.bindTooltip(
        "Ponto de partida"
    );


    origem.bindPopup(
        "<b>Ponto de partida</b><br>"
        +
        payload.origem.nome
    );


    origem.addTo(
        map
    );


    // ======================================================
    // CONFIGURAÇÃO DAS PÉTALAS
    // ======================================================

    const ICON_W =
        46;


    const ICON_H =
        30;


    const COLLISION_MARGIN =
        2;


    const SAME_POINT_PX =
        0.8;


    const markers =
        [];


    // ======================================================
    // ÍCONE
    // ======================================================

    function criarIcone(
        item
    ) {

        const conteudo = `

            <div
                class="petala"
                data-numero="${item.numero}"
            >

                <div
                    class="petala-forma"
                >

                    <svg
                        width="46"
                        height="30"
                        viewBox="0 0 46 30"
                        xmlns="http://www.w3.org/2000/svg"
                        style="
                            overflow:visible;
                            filter:
                                drop-shadow(
                                    0px 2px 2px
                                    rgba(0,0,0,0.30)
                                );
                        "
                    >

                        <path
                            d="
                                M23 28
                                C18 25 7 23 5 15
                                C4 7 12 2 23 2
                                C34 2 42 7 41 15
                                C39 23 28 25 23 28
                                Z
                            "
                            fill="${item.cor}"
                            stroke="white"
                            stroke-width="2.3"
                            stroke-linejoin="round"
                        />

                    </svg>

                </div>


                <div
                    class="petala-numero"
                    style="
                        color:${item.cor_texto};
                    "
                >
                    ${item.numero}
                </div>

            </div>
        `;


        return L.divIcon(
            {
                className:
                    "obravigia-marker",

                html:
                    conteudo,

                iconSize:
                    [
                        ICON_W,
                        ICON_H
                    ],

                iconAnchor:
                    [
                        ICON_W / 2,
                        ICON_H / 2
                    ]
            }
        );
    }


    // ======================================================
    // CRIAR MARKERS
    // ======================================================

    payload.projetos.forEach(
        function (
            item
        ) {

            const marker =
                L.marker(
                    [
                        item.lat,
                        item.lng
                    ],
                    {
                        icon:
                            criarIcone(
                                item
                            ),

                        title:
                            String(
                                item.numero
                            ),

                        riseOnHover:
                            true
                    }
                );


            marker.__original =
                L.latLng(
                    item.lat,
                    item.lng
                );


            marker.__numero =
                item.numero;


            marker.bindTooltip(
                item.tooltip
            );


            marker.bindPopup(
                item.popup,
                {
                    maxWidth:
                        420
                }
            );


            // Clique diretamente na pétala,
            // inclusive quando ela estiver visualmente
            // deslocada para formar o trevo.

            marker.on(
                "add",
                function () {

                    window.setTimeout(
                        function () {

                            const elemento =
                                marker.getElement();


                            if (!elemento) {

                                return;
                            }


                            const petala =
                                elemento.querySelector(
                                    ".petala"
                                );


                            if (
                                petala
                                &&
                                !petala.__obravigiaClick
                            ) {

                                petala.__obravigiaClick =
                                    true;


                                petala.addEventListener(
                                    "click",
                                    function (
                                        evento
                                    ) {

                                        evento.stopPropagation();


                                        marker.openPopup();
                                    }
                                );
                            }
                        },
                        0
                    );
                }
            );


            marker.addTo(
                map
            );


            markers.push(
                marker
            );
        }
    );


    // ======================================================
    // UTILITÁRIOS
    // ======================================================

    function clamp(
        valor,
        minimo,
        maximo
    ) {

        return Math.max(
            minimo,
            Math.min(
                maximo,
                valor
            )
        );
    }


    // ======================================================
    // RESET VISUAL
    //
    // IMPORTANTE:
    //
    // NÃO existe setLatLng().
    //
    // A latitude/longitude da obra nunca muda.
    // ======================================================

    function resetarMarker(
        marker
    ) {

        marker.setZIndexOffset(
            0
        );


        const elemento =
            marker.getElement();


        if (!elemento) {

            return;
        }


        const petala =
            elemento.querySelector(
                ".petala"
            );


        const forma =
            elemento.querySelector(
                ".petala-forma"
            );


        const numero =
            elemento.querySelector(
                ".petala-numero"
            );


        if (petala) {

            petala.style.transform =
                "translate(0px, 0px)";
        }


        if (forma) {

            forma.style.transform =
                "rotate(0deg)";
        }


        if (numero) {

            numero.style.zIndex =
                "20";

            numero.style.opacity =
                "1";

            numero.style.visibility =
                "visible";
        }
    }


    // ======================================================
    // POSIÇÕES REAIS NA TELA
    // ======================================================

    function medirPosicoesReais() {

        return markers.map(
            function (
                marker,
                indice
            ) {

                const point =
                    map.latLngToContainerPoint(
                        marker.__original
                    );


                return {

                    marker:
                        marker,

                    numero:
                        marker.__numero,

                    indice:
                        indice,

                    x:
                        point.x,

                    y:
                        point.y
                };
            }
        );
    }


    // ======================================================
    // COLISÃO
    // ======================================================

    function colidem(
        a,
        b
    ) {

        const dx =
            Math.abs(
                a.x
                -
                b.x
            );


        const dy =
            Math.abs(
                a.y
                -
                b.y
            );


        return (
            dx
            <
            (
                ICON_W
                +
                COLLISION_MARGIN
            )
            &&
            dy
            <
            (
                ICON_H
                +
                COLLISION_MARGIN
            )
        );
    }


    function distancia(
        a,
        b
    ) {

        const dx =
            a.x
            -
            b.x;


        const dy =
            a.y
            -
            b.y;


        return Math.sqrt(
            dx * dx
            +
            dy * dy
        );
    }


    // ======================================================
    // GRUPOS DE COLISÃO
    // ======================================================

    function construirGrupos(
        dados
    ) {

        const n =
            dados.length;


        const visitado =
            new Array(
                n
            ).fill(
                false
            );


        const grupos =
            [];


        for (
            let inicio = 0;
            inicio < n;
            inicio++
        ) {

            if (
                visitado[
                    inicio
                ]
            ) {

                continue;
            }


            const fila = [
                inicio
            ];


            const indices =
                [];


            visitado[
                inicio
            ] =
                true;


            while (
                fila.length
                >
                0
            ) {

                const atual =
                    fila.shift();


                indices.push(
                    atual
                );


                for (
                    let j = 0;
                    j < n;
                    j++
                ) {

                    if (
                        visitado[
                            j
                        ]
                    ) {

                        continue;
                    }


                    if (
                        colidem(
                            dados[
                                atual
                            ],
                            dados[
                                j
                            ]
                        )
                    ) {

                        visitado[
                            j
                        ] =
                            true;


                        fila.push(
                            j
                        );
                    }
                }
            }


            grupos.push(
                indices.map(
                    function (
                        indice
                    ) {

                        return dados[
                            indice
                        ];
                    }
                )
            );
        }


        return grupos;
    }


    // ======================================================
    // CENTRO
    // ======================================================

    function centroGrupo(
        grupo
    ) {

        let x =
            0;


        let y =
            0;


        grupo.forEach(
            function (
                item
            ) {

                x +=
                    item.x;


                y +=
                    item.y;
            }
        );


        return {

            x:
                x
                /
                grupo.length,

            y:
                y
                /
                grupo.length
        };
    }


    function dispersaoGrupo(
        grupo
    ) {

        let maior =
            0;


        for (
            let i = 0;
            i < grupo.length;
            i++
        ) {

            for (
                let j = i + 1;
                j < grupo.length;
                j++
            ) {

                maior =
                    Math.max(
                        maior,
                        distancia(
                            grupo[
                                i
                            ],
                            grupo[
                                j
                            ]
                        )
                    );
            }
        }


        return maior;
    }


    // ======================================================
    // RAIO COMPACTO
    // ======================================================

    function raioCompacto(
        quantidade
    ) {

        if (
            quantidade === 2
        ) {

            return 9.5;
        }


        if (
            quantidade === 3
        ) {

            return 10.0;
        }


        if (
            quantidade === 4
        ) {

            return 10.5;
        }


        if (
            quantidade === 5
        ) {

            return 11.0;
        }


        return Math.min(
            18,
            11
            +
            (
                quantidade
                -
                5
            )
            *
            1.2
        );
    }


    // ======================================================
    // ORIENTAÇÃO
    //
    // A folha gira.
    // O número não gira.
    // ======================================================

    function orientarFolha(
        marker,
        angulo
    ) {

        const elemento =
            marker.getElement();


        if (!elemento) {

            return;
        }


        const forma =
            elemento.querySelector(
                ".petala-forma"
            );


        const numero =
            elemento.querySelector(
                ".petala-numero"
            );


        if (forma) {

            const rotacao =
                angulo
                +
                90;


            forma.style.transform =
                `rotate(${rotacao}deg)`;
        }


        if (numero) {

            numero.style.zIndex =
                "20";

            numero.style.opacity =
                "1";

            numero.style.visibility =
                "visible";
        }
    }


    // ======================================================
    // APLICAR TREVO
    // ======================================================

    function aplicarTrevo(
        grupo
    ) {

        if (
            grupo.length
            <=
            1
        ) {

            return;
        }


        grupo.sort(
            function (
                a,
                b
            ) {

                return (
                    a.numero
                    -
                    b.numero
                );
            }
        );


        const quantidade =
            grupo.length;


        const centro =
            centroGrupo(
                grupo
            );


        const dispersao =
            dispersaoGrupo(
                grupo
            );


        const zoom =
            map.getZoom();


        const base =
            raioCompacto(
                quantidade
            );


        const mesmoPonto =
            dispersao
            <=
            SAME_POINT_PX;


        let raio;


        // --------------------------------------------------
        // MESMA COORDENADA
        //
        // Zoom out -> fecha.
        // Zoom in  -> abre.
        // --------------------------------------------------

        if (
            mesmoPonto
        ) {

            raio =
                base
                +
                (
                    zoom
                    -
                    11
                )
                *
                3.3;


            raio =
                clamp(
                    raio,
                    base
                    *
                    0.78,
                    44
                );

        } else {

            raio =
                base;
        }


        grupo.forEach(
            function (
                item,
                indice
            ) {

                const angulo =
                    -90
                    +
                    (
                        indice
                        *
                        360
                        /
                        quantidade
                    );


                const rad =
                    angulo
                    *
                    Math.PI
                    /
                    180;


                const trevoX =
                    centro.x
                    +
                    Math.cos(
                        rad
                    )
                    *
                    raio;


                const trevoY =
                    centro.y
                    +
                    Math.sin(
                        rad
                    )
                    *
                    raio;


                let alvoX;

                let alvoY;


                if (
                    mesmoPonto
                ) {

                    alvoX =
                        trevoX;


                    alvoY =
                        trevoY;

                } else {

                    // --------------------------------------
                    // Coordenadas diferentes.
                    //
                    // Quanto mais próximas visualmente,
                    // mais forte o trevo.
                    //
                    // Ao aproximar o mapa, a dispersão
                    // cresce e o deslocamento cai.
                    // --------------------------------------

                    const pesoTrevo =
                        clamp(
                            (
                                54
                                -
                                dispersao
                            )
                            /
                            42,
                            0,
                            1
                        );


                    alvoX =
                        item.x
                        *
                        (
                            1
                            -
                            pesoTrevo
                        )
                        +
                        trevoX
                        *
                        pesoTrevo;


                    alvoY =
                        item.y
                        *
                        (
                            1
                            -
                            pesoTrevo
                        )
                        +
                        trevoY
                        *
                        pesoTrevo;
                }


                // ==========================================
                // ÚNICO DESLOCAMENTO:
                // representação visual em pixels.
                //
                // O L.Marker permanece na coordenada real.
                // ==========================================

                const dxVisual =
                    alvoX
                    -
                    item.x;


                const dyVisual =
                    alvoY
                    -
                    item.y;


                const elemento =
                    item.marker.getElement();


                if (elemento) {

                    const petala =
                        elemento.querySelector(
                            ".petala"
                        );


                    if (petala) {

                        petala.style.transform =
                            `translate(
                                ${dxVisual.toFixed(1)}px,
                                ${dyVisual.toFixed(1)}px
                            )`;
                    }
                }


                item.marker.setZIndexOffset(
                    1000
                    +
                    indice
                );


                orientarFolha(
                    item.marker,
                    angulo
                );
            }
        );
    }


    // ======================================================
    // ATUALIZAÇÃO
    // ======================================================

    let atualizacaoPendente =
        false;


    function executarAtualizacao() {

        atualizacaoPendente =
            false;


        markers.forEach(
            resetarMarker
        );


        window.requestAnimationFrame(
            function () {

                const dadosReais =
                    medirPosicoesReais();


                const grupos =
                    construirGrupos(
                        dadosReais
                    );


                grupos.forEach(
                    aplicarTrevo
                );
            }
        );
    }


    function solicitarAtualizacao() {

        if (
            atualizacaoPendente
        ) {

            return;
        }


        atualizacaoPendente =
            true;


        window.requestAnimationFrame(
            executarAtualizacao
        );
    }


    // ======================================================
    // EVENTOS
    // ======================================================

    map.on(
        "zoom",
        solicitarAtualizacao
    );


    map.on(
        "zoomend",
        solicitarAtualizacao
    );


    map.on(
        "moveend",
        solicitarAtualizacao
    );


    map.on(
        "resize",
        solicitarAtualizacao
    );


    // ======================================================
    // ENQUADRAMENTO
    // ======================================================

    const pontos =
        [
            [
                payload.origem.lat,
                payload.origem.lng
            ]
        ];


    payload.projetos.forEach(
        function (
            item
        ) {

            pontos.push(
                [
                    item.lat,
                    item.lng
                ]
            );
        }
    );


    candidatosContexto.forEach(
        function (
            item
        ) {

            pontos.push(
                [
                    item.lat,
                    item.lng
                ]
            );
        }
    );


    if (
        pontos.length
        >
        1
    ) {

        map.fitBounds(
            pontos,
            {
                padding:
                    [
                        35,
                        35
                    ]
            }
        );

    } else {

        map.setView(
            [
                payload.origem.lat,
                payload.origem.lng
            ],
            12
        );
    }


    window.setTimeout(
        solicitarAtualizacao,
        450
    );

})();

</script>

</body>

</html>
"""


    pagina = (
        pagina
        .replace(
            "__PAYLOAD__",
            payload_json
        )
        .replace(
            "__ALTURA__",
            str(
                int(
                    altura
                )
            )
        )
    )


    components.html(
        pagina,
        height=int(
            altura
        ),
        scrolling=False
    )




def indicador_prioridade_html(
    valor
):

    valor = normalizar_ipi_visual(
        valor
    )

    cor = cor_ipi(
        valor
    )

    cor_texto = cor_texto_ipi(
        valor
    )

    rotulo = prioridade_rotulo(
        valor
    )

    return f"""
    <div
        style="
            display:flex;
            align-items:center;
            gap:10px;
            padding:10px 14px;
            border-radius:10px;
            background:{cor};
            color:{cor_texto};
            font-weight:600;
            margin-top:4px;
            margin-bottom:12px;
        "
    >
        Prioridade de visita: {rotulo}
        &nbsp;•&nbsp;
        IPI {valor:.2f}
    </div>
    """


def legenda_gradiente_ipi_html():

    return """
    <div style="margin-top:8px; margin-bottom:14px;">

        <div
            style="
                width:100%;
                height:18px;
                border-radius:9px;
                background:
                    linear-gradient(
                        90deg,
                        hsl(120,72%,40%) 0%,
                        hsl(90,72%,40%) 25%,
                        hsl(60,72%,45%) 50%,
                        hsl(30,78%,48%) 75%,
                        hsl(0,72%,42%) 100%
                    );
                border:1px solid rgba(0,0,0,0.15);
            "
        ></div>

        <div
            style="
                display:flex;
                justify-content:space-between;
                font-size:0.85rem;
                margin-top:5px;
            "
        >
            <span>Menor prioridade de visita</span>
            <span>Maior prioridade de visita</span>
        </div>

    </div>
    """




# ============================================================
# MOTOR DINÂMICO
# ============================================================

from motor_dinamico import planejar_rota


# ============================================================
# GEOCODIFICAÇÃO DO PONTO DE PARTIDA
# ============================================================

ENDERECO_PADRAO_ORIGEM = (
    "Rua Joaquim Garcia, s/n, "
    "Camboriú, SC, 88340-055"
)


PHOTON_URL = (
    "https://photon.komoot.io/api/"
)


PHOTON_USER_AGENT = (
    "ObraVigia/1.0 "
    "(https://github.com/nhankoski/ObraVigia)"
)


# Limites aproximados de Santa Catarina:
# minLon,minLat,maxLon,maxLat
SC_BBOX = (
    "-53.9,-29.5,-48.2,-25.8"
)


@st.cache_data(
    ttl=86400,
    show_spinner=False
)
def buscar_enderecos_em_sc(
    consulta
):

    consulta = str(
        consulta
    ).strip()


    if len(
        consulta
    ) < 4:

        return []


    resposta = requests.get(
        PHOTON_URL,
        params={
            "q":
                consulta,

            "limit":
                5,
        
            "lang":
                "pt",

            "countrycode":
                "BR",
        
            "lat":
                -27.3,
        
            "lon":
                -50.2,
        
            "zoom":
                6,
        
            "location_bias_scale":
                0.15
        },
        headers={
            "User-Agent":
                PHOTON_USER_AGENT
        },
        timeout=15
    )


    resposta.raise_for_status()


    dados = (
        resposta.json()
        or
        {}
    )


    candidatos_sc = []


    for item in dados.get(
        "features",
        []
    ):

        geometria = (
            item.get(
                "geometry",
                {}
            )
            or
            {}
        )


        coordenadas = geometria.get(
            "coordinates",
            []
        )


        if (
            not isinstance(
                coordenadas,
                list
            )
            or
            len(
                coordenadas
            ) < 2
        ):

            continue


        try:

            longitude = float(
                coordenadas[
                    0
                ]
            )

            latitude = float(
                coordenadas[
                    1
                ]
            )

        except Exception:

            continue


        # Segunda barreira:
        # garante que o resultado continue dentro
        # da área territorial aproximada de SC.

        dentro_sc = (
            -53.9 <= longitude <= -48.2
            and
            -29.5 <= latitude <= -25.8
        )


        if not dentro_sc:

            continue


        propriedades = (
            item.get(
                "properties",
                {}
            )
            or
            {}
        )


        estado = str(
            propriedades.get(
                "state",
                ""
            )
            or
            ""
        ).strip()


        # Se o Photon informar o estado explicitamente,
        # ele precisa ser Santa Catarina.
        # Alguns registros menores não trazem "state";
        # nesses casos, a bbox continua sendo a validação.

        if (
            estado
            and
            "santa catarina"
            not in
            estado.casefold()
        ):

            continue


        partes_nome = []


        for chave in [
            "name",
            "street",
            "housenumber",
            "district",
            "city",
            "county",
            "state",
            "postcode",
            "country"
        ]:

            valor = str(
                propriedades.get(
                    chave,
                    ""
                )
                or
                ""
            ).strip()


            if (
                valor
                and
                valor not in partes_nome
            ):

                partes_nome.append(
                    valor
                )


        nome = (
            ", ".join(
                partes_nome
            )
            if partes_nome
            else consulta
        )


        candidatos_sc.append(
            {
                "nome":
                    nome,

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "estado":
                    (
                        estado
                        or
                        "Santa Catarina"
                    ),

                "codigo_estado":
                    "BR-SC"
            }
        )


    return candidatos_sc
# ============================================================
# SIDEBAR
# ============================================================

# ------------------------------------------------------------
# Estado inicial:
# mantém exatamente a origem do cenário IFC.
# ------------------------------------------------------------

if (
    "origem_selecionada_lat"
    not in
    st.session_state
):

    st.session_state[
        "origem_selecionada_lat"
    ] = LAT_ORIGEM


if (
    "origem_selecionada_lon"
    not in
    st.session_state
):

    st.session_state[
        "origem_selecionada_lon"
    ] = LON_ORIGEM


if (
    "origem_selecionada_nome"
    not in
    st.session_state
):

    st.session_state[
        "origem_selecionada_nome"
    ] = (
        "Instituto Federal Catarinense "
        "— Campus Camboriú"
    )


if (
    "origem_selecionada_endereco"
    not in
    st.session_state
):

    st.session_state[
        "origem_selecionada_endereco"
    ] = ENDERECO_PADRAO_ORIGEM


if (
    "candidatos_origem"
    not in
    st.session_state
):

    st.session_state[
        "candidatos_origem"
    ] = []


if (
    "erro_busca_origem"
    not in
    st.session_state
):

    st.session_state[
        "erro_busca_origem"
    ] = None


with st.sidebar:

    st.header(
        "Planejamento"
    )


    st.subheader(
        "Ponto de partida"
    )


    endereco_digitado = st.text_input(
        "Digite o endereço",
        value=ENDERECO_PADRAO_ORIGEM,
        placeholder=(
            "Ex.: Rua 1000, 123, "
            "Balneário Camboriú, SC"
        ),
        help=(
            "Informe rua, número e município. "
            "Somente endereços localizados em "
            "Santa Catarina serão aceitos."
        )
    )


    if st.button(
        "Localizar endereço",
        type="primary",
        width="stretch"
    ):

        st.session_state[
            "erro_busca_origem"
        ] = None


        try:

            with st.spinner(
                "Localizando endereço..."
            ):

                resultados_busca = (
                    buscar_enderecos_em_sc(
                        endereco_digitado
                    )
                )


            st.session_state[
                "candidatos_origem"
            ] = resultados_busca


            if not resultados_busca:

                st.session_state[
                    "erro_busca_origem"
                ] = (
                    "Não encontrei esse endereço em "
                    "Santa Catarina. Confira rua, número "
                    "e município."
                )


        except Exception as erro:

            print(
                "ERRO_GEOCODIFICACAO:",
                type(erro).__name__,
                str(erro),
                flush=True
            )

            st.session_state[
                "candidatos_origem"
            ] = []


            st.session_state[
                "erro_busca_origem"
            ] = (
                "Não foi possível consultar o endereço "
                "neste momento. Tente novamente."
            )


    if st.session_state[
        "erro_busca_origem"
    ]:

        st.error(
            st.session_state[
                "erro_busca_origem"
            ]
        )


    candidatos = st.session_state[
        "candidatos_origem"
    ]


    if candidatos:

        indice_candidato = st.selectbox(
            "Confirme o endereço encontrado",
            options=list(
                range(
                    len(
                        candidatos
                    )
                )
            ),
            format_func=lambda indice: (
                candidatos[
                    indice
                ][
                    "nome"
                ]
            )
        )


        if st.button(
            "Usar este endereço",
            width="stretch"
        ):

            candidato = candidatos[
                indice_candidato
            ]


            nova_lat = float(
                candidato[
                    "latitude"
                ]
            )


            nova_lon = float(
                candidato[
                    "longitude"
                ]
            )


            novo_nome = candidato[
                "nome"
            ]


            try:

                with st.spinner(
                    "Calculando a nova rota a partir "
                    "do endereço selecionado..."
                ):

                    resultado_dinamico = planejar_rota(
                        caminho_base=(
                            Path(__file__).resolve().parent
                            /
                            "dados"
                            /
                            "base_sc_rota_automatica_2703.csv"
                        ),
                        origem_lat=nova_lat,
                        origem_lon=nova_lon,
                        jornada_min=480.0,
                        servico_padrao_min=45.0,
                        seed=20260901,
                        gerar_geometria=True
                    )


                st.session_state[
                    "origem_selecionada_lat"
                ] = nova_lat


                st.session_state[
                    "origem_selecionada_lon"
                ] = nova_lon


                st.session_state[
                    "origem_selecionada_nome"
                ] = novo_nome


                st.session_state[
                    "origem_selecionada_endereco"
                ] = endereco_digitado


                st.session_state[
                    "planejamento_dinamico"
                ] = resultado_dinamico


                st.session_state[
                    "planejamento_dinamico_origem"
                ] = {
                    "nome":
                        novo_nome,

                    "endereco":
                        endereco_digitado,

                    "latitude":
                        nova_lat,

                    "longitude":
                        nova_lon
                }


                st.session_state[
                    "candidatos_origem"
                ] = []


                st.session_state[
                    "erro_busca_origem"
                ] = None


                st.rerun()


            except Exception:

                st.error(
                    "O endereço foi localizado, mas não foi "
                    "possível calcular a rota neste momento."
                )

                st.caption(
                    "O planejamento anterior foi preservado. "
                    "Tente novamente em alguns instantes."
                )


    st.success(
        "Origem selecionada:\n\n"
        +
        st.session_state[
            "origem_selecionada_nome"
        ]
    )


    st.caption(
        "Somente endereços geocodificados em "
        "Santa Catarina são aceitos."
    )


    st.caption(
        "Ao clicar em “Localizar endereço”, "
        "a consulta é enviada ao serviço de "
        "geocodificação Nominatim/OpenStreetMap."
    )


    if st.button(
        "Gerar planejamento",
        type="primary",
        width="stretch"
    ):

        try:

            with st.spinner(
                "Analisando as obras e calculando "
                "uma nova rota..."
            ):

                resultado_dinamico = planejar_rota(
                    caminho_base=(
                        Path(__file__).resolve().parent
                        /
                        "dados"
                        /
                        "base_sc_rota_automatica_2703.csv"
                    ),
                    origem_lat=float(
                        st.session_state[
                            "origem_selecionada_lat"
                        ]
                    ),
                    origem_lon=float(
                        st.session_state[
                            "origem_selecionada_lon"
                        ]
                    ),
                    jornada_min=480.0,
                    servico_padrao_min=45.0,
                    seed=20260901,
                    gerar_geometria=True
                )


            st.session_state[
                "planejamento_dinamico"
            ] = resultado_dinamico


            st.session_state[
                "planejamento_dinamico_origem"
            ] = {
                "nome":
                    st.session_state[
                        "origem_selecionada_nome"
                    ],

                "endereco":
                    st.session_state[
                        "origem_selecionada_endereco"
                    ],

                "latitude":
                    float(
                        st.session_state[
                            "origem_selecionada_lat"
                        ]
                    ),

                "longitude":
                    float(
                        st.session_state[
                            "origem_selecionada_lon"
                        ]
                    )
            }


            st.rerun()


        except Exception as erro:

            st.error(
                "Não foi possível gerar o planejamento "
                "neste momento."
            )

            st.caption(
                "O serviço de roteamento pode estar "
                "temporariamente indisponível. "
                "Tente novamente em alguns instantes."
            )


    st.divider()


    st.write(
        "**Jornada disponível:** 8 horas"
    )


    st.write(
        "**Tempo estimado por inspeção:** 45 min"
    )


    st.divider()


    horario_saida = st.time_input(
        "Horário de saída",
        value=dt_time(
            8,
            0
        ),
        help=(
            "Altera somente os horários exibidos "
            "no cronograma."
        )
    )


    st.divider()




# ============================================================
# A origem já pode ser escolhida pelo usuário.
#
# Nesta etapa, verificamos se ela é diferente da origem
# do cenário demonstrativo.
# ============================================================

origem_diferente_exemplo = bool(
    abs(
        float(
            st.session_state[
                "origem_selecionada_lat"
            ]
        )
        -
        LAT_ORIGEM
    )
    >
    0.00001

    or

    abs(
        float(
            st.session_state[
                "origem_selecionada_lon"
            ]
        )
        -
        LON_ORIGEM
    )
    >
    0.00001
)



# ============================================================
# RESULTADO DE UM PLANEJAMENTO DINÂMICO
# ============================================================

if (
    "planejamento_dinamico"
    in
    st.session_state
):

    planejamento = (
        st.session_state[
            "planejamento_dinamico"
        ]
    )

    origem_planejamento = (
        st.session_state[
            "planejamento_dinamico_origem"
        ]
    )

    resumo_dinamico = (
        planejamento[
            "resumo"
        ]
    )

    projetos_dinamicos = (
        planejamento[
            "selecionados"
        ].copy()
    )

    candidatos_dinamicos = (
        planejamento[
            "candidatos"
        ].copy()
    )


    geometria_dinamica = (
        planejamento[
            "geometria"
        ]
    )


    # ========================================================
    # CABEÇALHO
    # ========================================================

    st.title(
        "ObraVigia"
    )

    st.write(
        "Prioridade e rota em uma única ferramenta "
        "para apoiar o planejamento de inspeções "
        "de obras públicas."
    )

    st.caption(
        "Planejamento gerado a partir de um endereço "
        "informado pelo usuário • Santa Catarina • "
        "dados públicos processados em 31/08/2026"
    )


    st.success(
        "Ponto de partida utilizado: "
        +
        origem_planejamento[
            "nome"
        ]
    )


    # ========================================================
    # RESUMO
    # ========================================================

    st.write(
        "Neste planejamento, o sistema selecionou "
        f"{int(resumo_dinamico['quantidade_projetos'])} "
        "inspeções para uma jornada de 8 horas, buscando "
        "acumular a maior prioridade possível sem "
        "ultrapassar o tempo disponível."
    )


    linha_metricas_1 = st.columns(
        3
    )


    linha_metricas_1[
        0
    ].metric(
        "Inspeções planejadas",
        int(
            resumo_dinamico[
                "quantidade_projetos"
            ]
        )
    )


    linha_metricas_1[
        1
    ].metric(
        "Candidatas viáveis",
        int(
            len(
                candidatos_dinamicos
            )
        )
    )


    linha_metricas_1[
        2
    ].metric(
        "Distância total",
        f"{float(resumo_dinamico['distancia_km']):.1f} km"
    )


    linha_metricas_2 = st.columns(
        3
    )


    minutos_deslocamento = int(
        round(
            float(
                resumo_dinamico[
                    "tempo_viagem_min"
                ]
            )
        )
    )


    horas_deslocamento = (
        minutos_deslocamento
        //
        60
    )

    resto_deslocamento = (
        minutos_deslocamento
        %
        60
    )


    minutos_total = int(
        round(
            float(
                resumo_dinamico[
                    "tempo_total_min"
                ]
            )
        )
    )


    horas_total = (
        minutos_total
        //
        60
    )

    resto_total = (
        minutos_total
        %
        60
    )


    linha_metricas_2[
        0
    ].metric(
        "Tempo em deslocamento",
        (
            f"{horas_deslocamento}h "
            f"{resto_deslocamento:02d}min"
        )
    )


    linha_metricas_2[
        1
    ].metric(
        "Tempo total da jornada",
        (
            f"{horas_total}h "
            f"{resto_total:02d}min"
        )
    )


    linha_metricas_2[
        2
    ].metric(
        "Tempo ainda disponível",
        (
            f"{int(round(float(resumo_dinamico['folga_min'])))} min"
        )
    )


    # ========================================================
    # ABAS
    # ========================================================

    (
        aba_mapa_dinamico,
        aba_paradas_dinamica,
        aba_jornada_dinamica,
        aba_metodo_dinamica,
        aba_dados_dinamica
    ) = st.tabs(
        [
            "Mapa da rota",
            "Paradas",
            "Jornada",
            "Como funciona",
            "Dados e transparência"
        ]
    )


    # ========================================================
    # MAPA
    # ========================================================

    with aba_mapa_dinamico:

        st.subheader(
            "Rota sugerida"
        )

        st.write(
            "Os números mostram a ordem das inspeções. "
            "A cor representa a prioridade de visita. "
            "Quando os marcadores das obras se sobrepõem, "
            "eles formam um trevo compacto. Ao aproximar "
            "o mapa, retornam às posições reais sempre que possível."
        )

        st.html(
            legenda_gradiente_ipi_html()
        )


        dados_mapa_dinamico = []


        ids_selecionados_publicos_257 = set(
            projetos_dinamicos[
                "id_projeto"
            ]
            .astype(
                str
            )
            .tolist()
        )


        ids_financeiros_publicos_257 = set(
            candidatos_dinamicos[
                "id_projeto"
            ]
            .astype(
                str
            )
            .tolist()
        )


        ids_financeiros_publicos_257.update(
            ids_selecionados_publicos_257
        )


        ids_financeiros_publicos_257.update(
            ids_alertas()
        )


        pagamentos_dinamicos_257 = (
            obter_valores_pagos_lote(
                ids_financeiros_publicos_257
            )
        )


        dados_candidatos_dinamicos = (
            montar_candidatos_contexto(
                candidatos_dinamicos,
                ids_selecionados_publicos_257,
                pagamentos_dinamicos_257
            )
        )


        dados_alertas_dinamicos_257 = (
            montar_alertas_contexto(
                pagamentos_dinamicos_257
            )
        )


        for linha in projetos_dinamicos.itertuples(
            index=False
        ):

            sequencia = int(
                linha.sequencia
            )


            ipi = float(
                linha.ipi_final
            )


            nome_projeto = html.escape(
                str(
                    linha.desc_nome
                )
            )


            situacao_projeto = html.escape(
                str(
                    linha.situacao
                )
            )


            popup = (
                f"<b>Parada {sequencia}</b><br><br>"
                f"<b>Projeto:</b> {nome_projeto}<br>"
                f"<b>IPI:</b> {ipi:.2f}<br>"
                f"<b>Prioridade:</b> "
                f"{prioridade_rotulo(ipi)}<br>"
                f"<b>Situação:</b> {situacao_projeto}<br><br>"
                "<span style='font-size:11px;color:#555;'>"
                "O IPI representa prioridade relativa de visita "
                "e não constitui, por si só, conclusão sobre "
                "irregularidade."
                "</span>"
            )


            popup = popup_publico(
            str(
                linha.id_projeto
            ),
            pagamentos_dinamicos_257
        )


            dados_mapa_dinamico.append(
                {
                    "lat":
                        float(
                            linha.latitude_representativa
                        ),

                    "lng":
                        float(
                            linha.longitude_representativa
                        ),

                    "numero":
                        sequencia,

                    "cor":
                        cor_ipi(
                            ipi
                        ),

                    "cor_texto":
                        cor_texto_ipi(
                            ipi
                        ),

                    "tooltip":
                        (
                            f"{sequencia}. "
                            +
                            str(
                                linha.desc_nome
                            )
                        ),

                    "popup":
                        popup
                }
            )


        rota_geojson_dinamica = None


        if (
            geometria_dinamica
            and
            geometria_dinamica.get(
                "geojson"
            )
        ):

            rota_geojson_dinamica = (
                geometria_dinamica[
                    "geojson"
                ]
            )


        renderizar_mapa_leaflet_trevo(
            origem_lat=float(
                origem_planejamento[
                    "latitude"
                ]
            ),
            origem_lon=float(
                origem_planejamento[
                    "longitude"
                ]
            ),
            origem_nome=str(
                origem_planejamento[
                    "nome"
                ]
            ),
            projetos_mapa=dados_mapa_dinamico,
            candidatos_contexto=dados_candidatos_dinamicos,
            alertas_contexto=dados_alertas_dinamicos_257,
            rota_geojson=rota_geojson_dinamica,
            altura=650
        )

        with st.expander(
            "Como ler o mapa"
        ):

            st.write(
                "**Casa:** ponto de partida informado "
                "pelo usuário."
            )

            st.write(
                "**Números:** ordem sugerida das inspeções."
            )

            st.write(
                "**Cores:** prioridade relativa de visita, "
                "do verde ao vermelho."
            )

            st.write(
                "**Pétalas agrupadas:** quando duas ou mais "
                "paradas ficam muito próximas na tela, "
                "as gotas se distribuem como um pequeno "
                "trevo ou uma flor. Cada obra mantém "
                "seu número, sua cor e seu clique."
            )

            st.caption(
                "A separação das pétalas é apenas visual. "
                "A localização usada no cálculo da rota "
                "permanece inalterada."
            )

            st.write(
                "**Linha:** percurso calculado pela "
                "malha rodoviária."
            )


    # ========================================================
    # PARADAS
    # ========================================================

    with aba_paradas_dinamica:

        st.subheader(
            "Inspeções selecionadas"
        )


        tabela_dinamica = (
            projetos_dinamicos[
                [
                    "sequencia",
                    "desc_nome",
                    "ipi_final",
                    "posicao_ipi_final",
                    "situacao",
                    "sistema_resp"
                ]
            ]
            .copy()
        )


        tabela_dinamica[
            "Prioridade de visita"
        ] = tabela_dinamica[
            "ipi_final"
        ].apply(
            prioridade_rotulo
        )


        tabela_dinamica = tabela_dinamica.rename(
            columns={
                "sequencia":
                    "Ordem",

                "desc_nome":
                    "Projeto",

                "ipi_final":
                    "IPI",

                "posicao_ipi_final":
                    "Posição no ranking estadual",

                "situacao":
                    "Situação",

                "sistema_resp":
                    "Sistema de origem"
            }
        )


        tabela_dinamica = tabela_dinamica[
            [
                "Ordem",
                "Projeto",
                "IPI",
                "Prioridade de visita",
                "Posição no ranking estadual",
                "Situação",
                "Sistema de origem"
            ]
        ]


        st.dataframe(
            tabela_dinamica,
            hide_index=True,
            width="stretch"
        )


        st.download_button(
            "Baixar paradas em CSV",
            data=tabela_dinamica.to_csv(
                index=False
            ).encode(
                "utf-8-sig"
            ),
            file_name=(
                "obravigia_planejamento.csv"
            ),
            mime="text/csv",
            width="stretch"
        )


    # ========================================================
    # JORNADA
    # ========================================================

    with aba_jornada_dinamica:

        st.subheader(
            "Resumo da jornada"
        )


        col_j1, col_j2 = st.columns(
            2
        )


        col_j1.metric(
            "Tempo em inspeções",
            (
                f"{int(resumo_dinamico['tempo_servico_min'])} min"
            )
        )


        col_j2.metric(
            "Tempo em deslocamentos",
            (
                f"{int(round(resumo_dinamico['tempo_viagem_min']))} min"
            )
        )


        st.write(
            f"**Tempo total previsto:** "
            f"{float(resumo_dinamico['tempo_total_min']):.1f} minutos."
        )

        st.write(
            f"**Folga estimada:** "
            f"{float(resumo_dinamico['folga_min']):.1f} minutos."
        )

        st.caption(
            "Os tempos são estimativas rodoviárias e "
            "não incorporam trânsito em tempo real, "
            "interdições temporárias ou tempo adicional "
            "não previsto em cada inspeção."
        )


    # ========================================================
    # COMO FUNCIONA
    # ========================================================

    with aba_metodo_dinamica:

        st.subheader(
            "Como o planejamento foi produzido"
        )


        st.markdown(
            """
            1. **Origem:** o endereço informado foi
            transformado em coordenadas geográficas.

            2. **Base estadual:** o sistema parte de
            2.703 projetos com localização adequada
            ao roteamento automático.

            3. **Triagem:** proximidade, IPI e eficiência
            são utilizados para formar uma shortlist.

            4. **Rede rodoviária:** tempos e distâncias
            são calculados pelo OSRM sobre dados do
            OpenStreetMap.

            5. **Otimização:** um algoritmo memético
            seleciona as visitas e organiza sua ordem
            respeitando a jornada disponível.
            """
        )


        st.info(
            "A solução é aproximada e não possui "
            "garantia de ótimo global."
        )


        with st.expander(
            "Detalhes técnicos"
        ):

            st.write(
                f"Shortlist analisada: "
                f"{int(resumo_dinamico['shortlist_total'])} projetos."
            )

            st.write(
                f"Candidatos individualmente viáveis: "
                f"{int(resumo_dinamico['candidatos_viaveis'])}."
            )

            st.write(
                "Objetivo lexicográfico: maximizar o "
                "IPI acumulado e, em caso de empate, "
                "minimizar o tempo total."
            )

            st.write(
                "Distâncias e tempos são direcionados: "
                "A→B pode ser diferente de B→A."
            )

            st.write(
                f"Tempo de otimização nesta execução: "
                f"{float(resumo_dinamico['tempo_otimizacao_s']):.2f} s."
            )


    # ========================================================
    # DADOS E TRANSPARÊNCIA
    # ========================================================

    with aba_dados_dinamica:

        st.subheader(
            "Dados e transparência"
        )


        st.markdown(
            """
            **ObrasGov.br — Governo Federal**  
            Fonte principal das informações públicas
            utilizadas para caracterizar e priorizar
            os projetos.

            **IBGE**  
            Apoio à padronização e validação territorial
            dos municípios.

            **OpenStreetMap**  
            Base aberta da malha viária.

            **Nominatim**  
            Localização do endereço informado pelo usuário.

            **OSRM**  
            Cálculo das distâncias, tempos e geometria
            rodoviária da rota.
            """
        )


        st.warning(
            "O IPI é um instrumento de priorização relativa "
            "de visitas. Ele não constitui prova de fraude, "
            "irregularidade ou má gestão."
        )


        st.caption(
            "ObraVigia • reúso de dados públicos para "
            "apoio ao planejamento de inspeções."
        )

        st.caption(
            "Dados viários © OpenStreetMap contributors."
        )


    # Impede a renderização simultânea do antigo
    # cenário demonstrativo.
    st.stop()


# ============================================================
# CABEÇALHO
# ============================================================

st.title(
    "ObraVigia"
)


st.write(
    "Prioridade e rota em uma única ferramenta "
    "para apoiar o planejamento de inspeções de obras públicas."
)


st.caption(
    "Cenário demonstrativo de Santa Catarina • "
    "dados públicos processados em 31/08/2026"
)


if origem_diferente_exemplo:

    st.info(
        "Novo ponto de partida selecionado. "
        "Clique em “Gerar planejamento” na barra lateral "
        "para calcular uma nova rota a partir dele."
    )


# ============================================================
# RESUMO EM LINGUAGEM SIMPLES
# ============================================================

st.info(
    "Neste planejamento, o sistema selecionou "
    f"{int(resumo['projetos'])} inspeções para uma jornada "
    "de 8 horas, procurando acumular a maior prioridade "
    "possível sem ultrapassar o tempo disponível."
)


# ============================================================
# INDICADORES
#
# Usamos duas linhas para evitar truncamento
# em telas e impressões mais estreitas.
# ============================================================

linha1_col1, linha1_col2, linha1_col3 = st.columns(
    3
)


linha1_col1.metric(
    "Inspeções planejadas",
    int(
        resumo[
            "projetos"
        ]
    )
)


linha1_col2.metric(
    "Candidatas viáveis",
    int(
        len(
            carregar_candidatos_padrao()
        )
    )
)


linha1_col3.metric(
    "Distância total",
    f"{float(resumo['distancia_table_km']):.1f} km"
)


linha2_col1, linha2_col2, linha2_col3 = st.columns(
    3
)


linha2_col1.metric(
    "Tempo em deslocamento",
    minutos_para_texto(
        resumo[
            "tempo_viagem_table_min"
        ]
    )
)


linha2_col2.metric(
    "Tempo total da jornada",
    minutos_para_texto(
        resumo[
            "tempo_total_otimizacao_min"
        ]
    )
)


linha2_col3.metric(
    "Tempo ainda disponível",
    minutos_para_texto(
        resumo[
            "folga_min"
        ]
    )
)


# ============================================================
# ABAS
# ============================================================

(
    aba_mapa,
    aba_paradas,
    aba_jornada,
    aba_funciona,
    aba_dados
) = st.tabs(
    [
        "Mapa da rota",
        "Paradas",
        "Jornada",
        "Como funciona",
        "Dados e transparência"
    ]
)


# ============================================================
# MAPA
# ============================================================

with aba_mapa:

    st.subheader(
        "Rota sugerida"
    )

    st.write(
        "Os números mostram a ordem das inspeções. "
        "A cor representa a prioridade de visita. "
        "Quando os marcadores das obras se sobrepõem, "
        "eles formam um trevo compacto. Ao aproximar "
        "o mapa, retornam às posições reais sempre que possível."
    )

    st.html(
        legenda_gradiente_ipi_html()
    )


    candidatos_iniciais_257 = (
        carregar_candidatos_padrao()
    )


    ids_selecionados_iniciais_257 = set(
        projetos[
            "id_projeto"
        ]
        .astype(
            str
        )
        .tolist()
    )


    ids_financeiros_iniciais_257 = set(
        candidatos_iniciais_257[
            "id_projeto"
        ]
        .astype(
            str
        )
        .tolist()
    )


    ids_financeiros_iniciais_257.update(
        ids_selecionados_iniciais_257
    )


    ids_financeiros_iniciais_257.update(
        ids_alertas()
    )


    pagamentos_iniciais_257 = (
        obter_valores_pagos_lote(
            ids_financeiros_iniciais_257
        )
    )


    dados_candidatos_iniciais_257 = (
        montar_candidatos_contexto(
            candidatos_iniciais_257,
            ids_selecionados_iniciais_257,
            pagamentos_iniciais_257
        )
    )


    dados_alertas_iniciais_257 = (
        montar_alertas_contexto(
            pagamentos_iniciais_257
        )
    )


    dados_mapa_inicial = []


    for linha in projetos.itertuples(
        index=False
    ):

        sequencia = int(
            linha.sequencia
        )


        ipi = float(
            linha.ipi_final
        )


        nome = html.escape(
            str(
                linha.nome
            )
        )


        id_projeto = html.escape(
            str(
                linha.id_projeto
            )
        )


        popup = (
            f"<b>Inspeção {sequencia}</b><br><br>"
            f"<b>Projeto:</b> {id_projeto}<br>"
            f"<b>Nome:</b> {nome}<br><br>"
            f"<b>IPI:</b> {ipi:.2f}<br>"
            f"<b>Prioridade de visita:</b> "
            f"{prioridade_rotulo(ipi)}<br>"
            f"<b>Posição no ranking:</b> "
            f"{int(linha.posicao_ipi_final)}<br><br>"
            "<span style='font-size:11px;color:#555;'>"
            "O IPI representa prioridade relativa de visita "
            "e não constitui, por si só, conclusão sobre "
            "irregularidade."
            "</span>"
        )


        popup = popup_publico(
            str(
                linha.id_projeto
            ),
            pagamentos_iniciais_257
        )


        dados_mapa_inicial.append(
            {
                "lat":
                    float(
                        linha.latitude
                    ),

                "lng":
                    float(
                        linha.longitude
                    ),

                "numero":
                    sequencia,

                "cor":
                    cor_ipi(
                        ipi
                    ),

                "cor_texto":
                    cor_texto_ipi(
                        ipi
                    ),

                "tooltip":
                    (
                        f"{sequencia}. "
                        +
                        str(
                            linha.id_projeto
                        )
                    ),

                "popup":
                    popup
            }
        )


    renderizar_mapa_leaflet_trevo(
        origem_lat=float(
            LAT_ORIGEM
        ),
        origem_lon=float(
            LON_ORIGEM
        ),
        origem_nome=str(
            NOME_ORIGEM
        ),
        projetos_mapa=dados_mapa_inicial,
        candidatos_contexto=dados_candidatos_iniciais_257,
        alertas_contexto=dados_alertas_iniciais_257,
        rota_geojson=geojson,
        altura=650
    )

    with st.expander(
        "Como ler o mapa"
    ):

        st.write(
            "**Casa:** ponto de partida e retorno."
        )

        st.write(
            "**Números 1, 2, 3...:** ordem sugerida "
            "das inspeções."
        )

        st.write(
            "**Cor do marcador:** prioridade relativa "
            "de visita. Verde indica menor prioridade "
            "e vermelho indica maior prioridade."
        )

        st.write(
            "**Linha da rota:** caminho rodoviário "
            "considerado no planejamento."
        )

        st.write(
            "A rota é uma estimativa de planejamento e "
            "não considera trânsito em tempo real."
        )


# ============================================================
# PARADAS
# ============================================================

with aba_paradas:

    st.subheader(
        "Obras selecionadas para a jornada"
    )

    st.write(
        "A lista está na mesma ordem mostrada no mapa."
    )


    tabela = projetos.copy()

    tabela[
        "prioridade_visual"
    ] = tabela[
        "ipi_final"
    ].apply(
        prioridade_rotulo
    )


    tabela = tabela.rename(
        columns={
            "sequencia":
                "Ordem",

            "id_projeto":
                "ID",

            "nome":
                "Projeto",

            "ipi_final":
                "IPI",

            "prioridade_visual":
                "Prioridade de visita",

            "posicao_ipi_final":
                "Posição no ranking"
        }
    )


    colunas_tabela = [
        coluna

        for coluna in [
            "Ordem",
            "ID",
            "Projeto",
            "IPI",
            "Prioridade de visita",
            "Posição no ranking"
        ]

        if coluna
        in tabela.columns
    ]


    tabela = tabela[
        colunas_tabela
    ]


    if "IPI" in tabela.columns:

        tabela[
            "IPI"
        ] = pd.to_numeric(
            tabela[
                "IPI"
            ],
            errors="coerce"
        ).round(
            2
        )


    st.dataframe(
        tabela,
        width="stretch",
        hide_index=True
    )


    st.divider()


    st.subheader(
        "Detalhes de uma parada"
    )


    opcoes = {
        (
            f"{int(linha.sequencia)}. "
            f"{linha.id_projeto} — "
            f"{linha.nome}"
        ):
            indice

        for indice, linha
        in projetos.iterrows()
    }


    escolha = st.selectbox(
        "Selecione uma inspeção",
        options=list(
            opcoes.keys()
        )
    )


    linha_escolhida = projetos.iloc[
        opcoes[
            escolha
        ]
    ]


    detalhe1, detalhe2, detalhe3 = st.columns(
        3
    )


    detalhe1.metric(
        "IPI",
        f"{float(linha_escolhida['ipi_final']):.2f}"
    )


    detalhe2.metric(
        "Posição no ranking",
        int(
            linha_escolhida[
                "posicao_ipi_final"
            ]
        )
    )


    detalhe3.metric(
        "Tempo previsto no local",
        "45 min"
    )


    st.html(
        indicador_prioridade_html(
            linha_escolhida[
                "ipi_final"
            ]
        )
    )


    st.write(
        f"**Projeto:** {linha_escolhida['nome']}"
    )

    st.write(
        f"**ID no ObrasGov:** "
        f"{linha_escolhida['id_projeto']}"
    )


    csv_projetos = projetos.to_csv(
        index=False
    ).encode(
        "utf-8-sig"
    )


    st.download_button(
        "Baixar lista das inspeções (CSV)",
        data=csv_projetos,
        file_name="obravigia_inspecoes.csv",
        mime="text/csv",
        width="stretch"
    )


# ============================================================
# JORNADA
# ============================================================

with aba_jornada:

    st.subheader(
        "Cronograma estimado"
    )

    st.write(
        "Escolha o horário de saída na barra lateral. "
        "Os horários abaixo são recalculados apenas para "
        "facilitar o planejamento; a rota permanece a mesma."
    )


    inicio_jornada = datetime.combine(
        date.today(),
        horario_saida
    )


    cronograma = arcos.copy()


    cronograma[
        "Chegada prevista"
    ] = cronograma[
        "tempo_acumulado_chegada_min"
    ].apply(
        lambda valor:
            horario_por_minutos(
                inicio_jornada,
                valor
            )
    )


    cronograma[
        "Fim da atividade"
    ] = cronograma[
        "tempo_acumulado_apos_servico_min"
    ].apply(
        lambda valor:
            horario_por_minutos(
                inicio_jornada,
                valor
            )
    )


    cronograma[
        "Deslocamento"
    ] = cronograma[
        "tempo_viagem_min"
    ].apply(
        lambda valor:
            f"{float(valor):.0f} min"
    )


    cronograma[
        "Distância"
    ] = cronograma[
        "distancia_km"
    ].apply(
        lambda valor:
            f"{float(valor):.1f} km"
    )


    cronograma[
        "Atividade"
    ] = cronograma[
        "tipo"
    ].map(
        {
            "visita":
                "Inspeção",

            "retorno":
                "Retorno à origem"
        }
    ).fillna(
        cronograma[
            "tipo"
        ]
    )


    cronograma_exibir = cronograma[
        [
            "sequencia",
            "Atividade",
            "de",
            "para",
            "Deslocamento",
            "Distância",
            "Chegada prevista",
            "Fim da atividade"
        ]
    ].rename(
        columns={
            "sequencia":
                "Etapa",

            "de":
                "De",

            "para":
                "Para"
        }
    )


    st.dataframe(
        cronograma_exibir,
        width="stretch",
        hide_index=True
    )


    fim_previsto = (
        inicio_jornada
        +
        timedelta(
            minutes=float(
                resumo[
                    "tempo_total_otimizacao_min"
                ]
            )
        )
    )


    resumo1, resumo2, resumo3 = st.columns(
        3
    )


    resumo1.metric(
        "Saída",
        inicio_jornada.strftime(
            "%H:%M"
        )
    )


    resumo2.metric(
        "Retorno previsto",
        fim_previsto.strftime(
            "%H:%M"
        )
    )


    resumo3.metric(
        "Duração total",
        minutos_para_texto(
            resumo[
                "tempo_total_otimizacao_min"
            ]
        )
    )


    st.warning(
        "Os tempos de deslocamento são estimativas "
        "rodoviárias e não representam trânsito em tempo real."
    )


# ============================================================
# COMO FUNCIONA
# ============================================================

with aba_funciona:

    st.subheader(
        "Como o ObraVigia toma a decisão"
    )


    with st.container(
        border=True
    ):

        st.markdown(
            "### 1. Organiza os dados"
        )

        st.write(
            "O sistema reúne informações públicas das obras, "
            "como situação, datas, valor planejado e localização."
        )


    with st.container(
        border=True
    ):

        st.markdown(
            "### 2. Calcula a prioridade"
        )

        st.write(
            "Quando há dados suficientes, cada projeto recebe "
            "um IPI de acordo com três componentes:"
        )

        st.write(
            "• situação do projeto;"
        )

        st.write(
            "• componente temporal;"
        )

        st.write(
            "• componente financeiro."
        )

        st.write(
            "Os três têm o mesmo peso."
        )

        st.caption(
            "O acompanhamento físico, quando disponível, "
            "é mostrado separadamente e não compõe o IPI "
            "desta versão."
        )


    with st.container(
        border=True
    ):

        st.markdown(
            "### 3. Verifica o que cabe na jornada"
        )

        st.write(
            "Uma obra não entra no planejamento diário "
            "se nem mesmo uma visita isolada permitir "
            "sair da origem, inspecionar e retornar "
            "dentro das 8 horas."
        )


    with st.container(
        border=True
    ):

        st.markdown(
            "### 4. Procura a melhor combinação"
        )

        st.write(
            "O algoritmo testa diferentes combinações de obras "
            "e diferentes ordens de visita."
        )

        st.write(
            "O objetivo é obter a maior soma de IPI possível "
            "sem ultrapassar a jornada."
        )


    with st.container(
        border=True
    ):

        st.markdown(
            "### 5. Organiza a rota pelas estradas"
        )

        st.write(
            "As viagens são calculadas sobre a malha rodoviária. "
            "O tempo de A para B pode ser diferente do tempo "
            "de B para A, e essa diferença é preservada."
        )


    st.info(
        "Por que não visitar simplesmente as obras com maior IPI? "
        "Porque duas obras muito prioritárias podem estar muito "
        "distantes entre si. O ObraVigia considera prioridade "
        "e deslocamento ao mesmo tempo."
    )


    with st.expander(
        "Detalhes técnicos da otimização"
    ):

        st.write(
            "**Tipo de problema:** orienteering."
        )

        st.write(
            "**Método:** algoritmo memético "
            "(algoritmo genético + busca local)."
        )

        st.write(
            "**Universo operacional deste cenário:** "
            "87 projetos."
        )

        st.write(
            "**Matriz rodoviária:** 88 × 88 "
            "(87 projetos + origem)."
        )

        st.write(
            "**Matriz direcionada:** sim."
        )

        st.write(
            "**População:** 200 indivíduos."
        )

        st.write(
            "**Gerações:** 150."
        )

        st.write(
            "**Réplicas independentes:** 3."
        )

        st.write(
            "**Resultado deste cenário:** "
            "8 projetos, IPI total 513,33."
        )

        st.write(
            "**Garantia de ótimo global:** não."
        )

        st.caption(
            "A solução é heurística: foi a melhor encontrada "
            "nas execuções realizadas, mas não há prova "
            "matemática de que nenhuma solução melhor exista."
        )


# ============================================================
# DADOS E TRANSPARÊNCIA
# ============================================================

with aba_dados:

    st.subheader(
        "De onde vêm os dados?"
    )


    with st.container(
        border=True
    ):

        st.markdown(
            "### ObrasGov.br"
        )

        st.write(
            "É a principal fonte dos dados de obras e projetos "
            "utilizados pelo ObraVigia."
        )

        st.write(
            "A aplicação usa informações públicas como "
            "identificação do projeto, situação, datas, "
            "valor planejado e geolocalização."
        )

        st.link_button(
            "Abrir API pública do ObrasGov.br",
            "https://api-publica.obrasgov.gestao.gov.br",
            width="stretch"
        )


    with st.container(
        border=True
    ):

        st.markdown(
            "### OpenStreetMap + Nominatim + OSRM"
        )

        st.write(
            "O OpenStreetMap fornece os dados da rede viária. "
            "O Nominatim é usado para localizar o endereço "
            "informado pelo usuário. O OSRM é o mecanismo "
            "usado para estimar distâncias e tempos "
            "pelas estradas."
        )

        st.write(
            "Esses tempos são usados para montar e avaliar "
            "as rotas."
        )

        coluna_osm, coluna_osrm = st.columns(
            2
        )

        coluna_osm.link_button(
            "OpenStreetMap",
            "https://www.openstreetmap.org/copyright",
            width="stretch"
        )

        coluna_osrm.link_button(
            "Projeto OSRM",
            "https://project-osrm.org/",
            width="stretch"
        )


    with st.container(
        border=True
    ):

        st.markdown(
            "### IBGE"
        )

        st.write(
            "Dados oficiais de municípios foram usados como "
            "apoio à padronização e à validação geográfica. "
            "Eles não alteram o valor do IPI."
        )


    st.divider()


    st.subheader(
        "O que acontece quando faltam dados?"
    )

    st.write(
        "O ObraVigia não transforma informação ausente em zero."
    )

    st.write(
        "Se não houver informação financeira suficiente "
        "para calcular o IPI, o projeto é identificado como "
        "não calculável, em vez de receber artificialmente "
        "uma prioridade baixa."
    )


    st.subheader(
        "Qualidade da localização"
    )

    st.write(
        "Projetos cuja coordenada não apresenta qualidade "
        "suficiente para roteamento automático permanecem "
        "nos dados, mas são separados para revisão."
    )


    if revisao.empty:

        st.success(
            "Nenhum projeto em revisão espacial "
            "neste cenário."
        )

    else:

        revisao_exibir = revisao.copy()

        colunas_revisao = [
            coluna

            for coluna in [
                "id_projeto",
                "nome",
                "ipi_final",
                "snap_max_m"
            ]

            if coluna
            in revisao_exibir.columns
        ]

        revisao_exibir = revisao_exibir[
            colunas_revisao
        ].rename(
            columns={
                "id_projeto":
                    "ID",

                "nome":
                    "Projeto",

                "ipi_final":
                    "IPI",

                "snap_max_m":
                    "Distância até a via usada pelo roteador (m)"
            }
        )

        st.dataframe(
            revisao_exibir,
            width="stretch",
            hide_index=True
        )


    st.divider()


    st.subheader(
        "Limitações"
    )

    st.write(
        "• O sistema apoia a decisão; ele não substitui "
        "a análise de um fiscal."
    )

    st.write(
        "• O IPI não identifica fraude ou irregularidade."
    )

    st.write(
        "• A qualidade depende da atualização dos dados "
        "fornecidos pelas fontes públicas."
    )

    st.write(
        "• Os tempos rodoviários não consideram trânsito "
        "em tempo real."
    )

    st.write(
        "• A otimização é heurística e não possui garantia "
        "de ótimo global."
    )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "ObraVigia • reúso de dados públicos para apoio "
    "ao planejamento de inspeções."
)

st.caption(
    "Dados viários © OpenStreetMap contributors."
)
