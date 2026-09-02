ObraVigia

Planejamento inteligente de rotas para inspeção de obras públicas com reúso de dados abertos.

🔗 Aplicação pública: https://obravigia.streamlit.app

O ObraVigia é uma aplicação web criada para apoiar o planejamento de jornadas de inspeção de obras públicas. A ferramenta combina dados abertos, critérios transparentes de priorização, localização geográfica e otimização de rotas para selecionar e ordenar visitas compatíveis com o tempo disponível.

A versão atual opera com projetos localizados em Santa Catarina e foi estruturada de forma a permitir adaptação para outros recortes territoriais.

Problema público

Bases governamentais abertas disponibilizam milhares de registros de obras e projetos, mas transformar esses dados em uma jornada operacional de fiscalização exige responder, ao mesmo tempo, a perguntas como:

quais obras devem receber maior prioridade de visita;

quais são viáveis dentro de uma jornada de trabalho;

em que ordem devem ser visitadas;

quanto tempo e deslocamento a rota exige;

quais informações públicas justificam a priorização.

O ObraVigia transforma esses registros em um planejamento operacional de inspeções, sem substituir a análise técnica do fiscal.

O que a ferramenta entrega

A partir de um endereço de partida informado pelo usuário, o sistema:

localiza a origem em Santa Catarina;

identifica projetos individualmente viáveis para a jornada;

considera prioridade e custo de deslocamento de forma conjunta;

seleciona um conjunto de inspeções compatível com o tempo disponível;

otimiza a ordem das visitas;

calcula distâncias e tempos pela malha rodoviária;

apresenta a rota, as paradas selecionadas e as demais candidatas viáveis em mapa interativo.

Funcionalidades

busca de endereço de origem;

recálculo automático da jornada ao escolher um novo endereço;

seleção de obras candidatas;

otimização da ordem de visita;

visualização da rota rodoviária;

visualização das demais candidatas viáveis;

tratamento visual de obras com coordenadas sobrepostas;

consulta de informações públicas da obra diretamente no mapa;

cronograma estimado da jornada;

exportação das paradas planejadas em CSV;

sinalização de registros com informação financeira insuficiente.

Informações mostradas para cada obra

O mapa apresenta, quando disponíveis na fonte:

situação atual;

órgão responsável;

investimento previsto;

valor pago registrado;

período previsto.

Dados ausentes são apresentados como “Não informado na fonte”. O sistema não converte informação ausente em zero.

Dados abertos reutilizados

ObrasGov.br — Governo Federal

A principal fonte do ObraVigia é a API Pública do ObrasGov.br, utilizada para obter informações de projetos de investimento, situação, datas, valores, localização e registros financeiros associados.

API pública: https://api-publica.obrasgov.gestao.gov.br

Essa é a fonte federal central reutilizada para construir a priorização e caracterizar os projetos apresentados pela aplicação.

IBGE

Dados oficiais de municípios são utilizados como apoio à padronização e à validação territorial.

OpenStreetMap

O OpenStreetMap fornece a base aberta da rede viária utilizada na visualização cartográfica e nos serviços geográficos associados.

Photon

A busca textual do endereço de origem utiliza o Photon, serviço de geocodificação baseado em dados do OpenStreetMap.

OSRM

Distâncias, tempos e geometrias rodoviárias são calculados por serviço compatível com OSRM — Open Source Routing Machine.

Os tempos são estimativas de planejamento e não representam trânsito em tempo real.

Metodologia

O planejamento combina duas decisões:

seleção das obras que cabem na jornada;

definição da ordem de visita.

A ferramenta utiliza internamente um Índice de Prioridade de Inspeção (IPI) construído a partir de informações públicas. Na configuração atual, o índice considera componentes de situação, temporal e financeiro com pesos equilibrados.

O IPI serve exclusivamente como instrumento de priorização relativa de visita. Ele não constitui prova de fraude, irregularidade, má gestão ou responsabilidade de qualquer órgão, entidade ou agente público.

Para o planejamento diário, o ObraVigia trata o problema como uma variante do Orienteering Problem: procura acumular a maior prioridade possível sem ultrapassar o orçamento de tempo da jornada, considerando deslocamento e tempo de atendimento em cada inspeção.

O motor utiliza estratégias exatas quando o tamanho do subproblema permite e procedimentos heurísticos/meméticos em instâncias maiores. A solução heurística não possui garantia de ótimo global.

Por que não basta visitar as obras com maior prioridade?

Uma lista ordenada por prioridade ignora a geografia. Duas obras muito prioritárias podem estar distantes entre si e tornar a jornada inviável.

O ObraVigia considera prioridade e deslocamento simultaneamente, buscando uma combinação de visitas que faça sentido dentro do tempo operacional disponível.

Benefício público

O projeto busca transformar dados já disponíveis ao cidadão em uma ferramenta de apoio à decisão que pode contribuir para:

planejamento mais eficiente de jornadas de fiscalização;

redução de deslocamentos desnecessários;

melhor aproveitamento do tempo operacional disponível;

transparência sobre os critérios utilizados na seleção das visitas;

aproximação entre dados públicos abertos e decisões concretas de gestão;

ampliação do potencial de controle e acompanhamento de obras públicas.

Inovação

O diferencial do ObraVigia não é apenas exibir obras em um mapa. A ferramenta integra, em um mesmo fluxo:

dados públicos + priorização + restrição de jornada + custos rodoviários + otimização combinatória + visualização interativa.

O usuário deixa de receber apenas uma lista de registros e passa a obter uma proposta operacional de jornada, com seleção e ordem de visitas explicáveis.

Replicabilidade e escalabilidade

O código-fonte está aberto sob licença MIT.

A arquitetura separa dados, motor de planejamento e interface. A versão publicada utiliza uma base preparada para Santa Catarina, mas o método pode ser adaptado para outras unidades da federação mediante:

coleta e preparação da base territorial correspondente;

ajuste dos limites de geocodificação e validação espacial;

geração das informações auxiliares necessárias ao roteamento;

manutenção dos mesmos princípios de priorização e otimização.

Essa separação também permite substituir serviços externos de geocodificação ou roteamento sem alterar o princípio central da solução.

Atenção cadastral

Registros cujo único investimento disponível na fonte é R$ 0,01 são mantidos para consulta, mas tratados como informação financeira insuficiente para o componente financeiro da priorização automática.

Essa classificação é uma regra de tratamento de dados e não afirma que o cadastro esteja incorreto.

Limitações

a qualidade do resultado depende da disponibilidade e atualização dos dados de origem;

informações ausentes não são inferidas;

os tempos rodoviários são estimativas;

trânsito em tempo real, interdições temporárias e imprevistos locais não são incorporados;

serviços públicos de geocodificação e roteamento podem possuir limites de utilização e disponibilidade;

soluções heurísticas não possuem garantia de ótimo global;

a ferramenta apoia a decisão, mas não substitui a avaliação profissional de um fiscal.

Executar localmente

Recomenda-se Python 3.13.

Instale as dependências:

pip install -r requirements.txt

Depois execute:

streamlit run app.py

Estrutura do repositório

ObraVigia/
├── .streamlit/
│   └── config.toml
├── dados/
├── app.py
├── dados_publicos_257.py
├── motor_dinamico.py
├── requirements.txt
├── LICENSE
└── README.md

Transparência e reprodutibilidade

O repositório mantém os arquivos de dados necessários para reproduzir o cenário publicado, além do código da interface e do motor de planejamento.

A aplicação informa suas limitações, preserva valores ausentes como ausentes e distingue explicitamente prioridade de visita de qualquer conclusão sobre irregularidade.

Licença

Código disponibilizado sob a licença MIT, permitindo uso, cópia, modificação e redistribuição nos termos do arquivo LICENSE.

Autor

Jackson de Oliveira

Finalidade

O ObraVigia foi desenvolvido como ferramenta de reúso de dados abertos para apoio ao planejamento, à transparência pública e ao uso operacional de informações governamentais abertas.

Projeto desenvolvido no contexto do 2º Concurso de Reúso de Dados Abertos da Controladoria-Geral da União — CGU (2026).
