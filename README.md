# ObraVigia

**Planejamento inteligente de rotas para inspeção de obras públicas.**

O ObraVigia é uma aplicação web que reutiliza dados públicos para apoiar o
planejamento de jornadas de inspeção de obras. A ferramenta combina critérios
de priorização, localização geográfica e otimização de rotas para selecionar e
ordenar visitas compatíveis com o tempo disponível.

## Funcionalidades

- busca de endereço de origem;
- recálculo automático da jornada;
- seleção de obras candidatas;
- otimização da ordem de visita;
- visualização da rota rodoviária;
- visualização das demais candidatas viáveis;
- tratamento visual de obras com coordenadas sobrepostas;
- consulta de informações públicas da obra diretamente no mapa;
- sinalização de registros com informação financeira insuficiente.

## Informações mostradas para cada obra

O mapa apresenta, quando disponíveis na fonte:

- situação atual;
- órgão responsável;
- investimento previsto;
- valor pago registrado;
- período previsto.

Dados ausentes são apresentados como **“Não informado na fonte”**.

## Fontes de dados e serviços

### Obras públicas

API Pública do **ObrasGov.br**, do Governo Federal.

O projeto utiliza dados de projetos de investimento e dados financeiros
associados aos registros públicos.

### Dados geográficos

O mapa utiliza dados do **OpenStreetMap**.

### Roteamento

As matrizes e geometrias rodoviárias utilizadas pelo protótipo são obtidas
por serviço compatível com **OSRM – Open Source Routing Machine**.

### Busca de endereço

A localização textual utiliza serviço baseado em dados do OpenStreetMap.

## Metodologia

O ObraVigia possui duas etapas distintas:

1. **seleção das obras compatíveis com a jornada disponível**;
2. **otimização da ordem de visita**.

Para conjuntos de tamanho adequado, o motor pode utilizar método exato.
Nos demais casos, utiliza procedimento heurístico/memético.

A ferramenta utiliza internamente um índice de prioridade construído a partir
de informações públicas. Esse índice serve ao planejamento computacional e não
constitui conclusão sobre irregularidade, fraude ou responsabilidade dos
órgãos ou entidades envolvidos.

## Atenção cadastral

Registros cujo único investimento disponível na fonte é R$ 0,01 são mantidos
para consulta, mas tratados como informação financeira insuficiente para o
componente financeiro da priorização automática.

Essa classificação não afirma que o cadastro esteja incorreto.

## Limitações

- a qualidade do resultado depende da disponibilidade e atualização dos dados
  de origem;
- informações ausentes não são inferidas;
- tempos rodoviários são estimativas;
- serviços públicos de geocodificação e roteamento podem possuir limites de
  utilização e disponibilidade;
- soluções heurísticas não possuem garantia de ótimo global.

## Executar localmente

Instale as dependências:

~~~bash
pip install -r requirements.txt
~~~

Depois execute:

~~~bash
streamlit run app.py
~~~

## Estrutura

~~~text
obravigia/
├── .streamlit/
│   └── config.toml
├── dados/
├── app.py
├── dados_publicos_257.py
├── motor_dinamico.py
├── requirements.txt
├── LICENSE
└── README.md
~~~

## Licença

Código disponibilizado sob a licença **MIT**.

## Finalidade

O ObraVigia foi desenvolvido como ferramenta de reúso de dados abertos para
apoio ao planejamento e à transparência pública.
