# 🎮 CS2 Skin Tracker

Aplicação para controle de inventário e valorização de skins do CS2.
Busca preços automaticamente via **Steam Market** e **CSFloat**.

## Funcionalidades

- **Carteira** — visualiza todas as skins com lucro/prejuízo e variação %
- **Inventário** — lista detalhada com busca, filtros e dialog de detalhes
- **Adicionar Skin** — cadastra novas skins com busca automática de preço
- **Configurações** — gerencia API keys, IOF e provider preferido
- **Atualização em lote** — atualiza preços de todas as skins com um clique
- **Catálogo local** — sincroniza dados extras e miniaturas do ByMykel/CSGO-API
- **Persistência em JSON** — dados salvos em volume Docker

## Estrutura do Projeto

```
cs2-skin-tracker/
├── app.py                         # Entry point Streamlit
├── config.py                      # Constantes e configurações
├── models.py                      # Modelos Pydantic
├── data_manager.py                # Persistência JSON com backup
├── views/
│   ├── 01_Carteira.py             # Página da carteira
│   ├── 02_Inventario.py           # Página do inventário
│   ├── 03_Adicionar_Skin.py       # Página de adicionar skin
│   └── 04_Configuracoes.py        # Página de configurações
├── services/
│   ├── price_service.py           # Orquestrador de providers
│   ├── runtime_state.py           # Cache de preços e estado
│   ├── catalog_service.py         # Catálogo local enxuto
│   ├── catalog_sync.py            # Sincronização do catálogo
│   ├── bymykel_catalog.py         # Cliente ByMykel/CSGO-API
│   ├── thumbnail_service.py       # Cache de miniaturas
│   └── price_providers/
│       ├── base.py                # Interface abstrata
│       ├── steam_market.py        # Provider Steam Market
│       └── csfloat.py             # Provider CSFloat
├── data/
│   └── seed.json                  # Dados iniciais
├── tests/
│   └── test_core.py               # Testes unitários
├── tools/
│   ├── build_current_skin_catalog.py
│   └── fetch_current_skin_images.py
├── .streamlit/
│   └── config.toml                # Tema e configuração do Streamlit
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Como Rodar

### Com Docker (recomendado)

```bash
# Build e start
docker compose up --build -d

# Acessar
# http://localhost:8501
```

### Sem Docker

```bash
# Criar virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt

# Criar diretório de dados
mkdir -p data

# Rodar
streamlit run app.py
```

## Providers de Preço

| Provider       | API Key? | Moeda | Rate Limit    |
|----------------|----------|-------|---------------|
| Steam Market   | Não      | BRL   | ~10 req/min   |
| CSFloat        | Sim      | USD→BRL | ~40 req/min |

### Steam Market
Funciona sem configuração. Os preços incluem a taxa de 15% do Steam,
então podem ser um pouco mais altos que no BUFF163/CSFloat.

### CSFloat
Requer API key gratuita. Obtenha em [csfloat.com/developers](https://csfloat.com/developers).
Preços em USD são convertidos para BRL automaticamente.

## IOF

A taxa IOF padrão é **6.38%** (compras internacionais com cartão).
Pode ser alterada em **Configurações → Taxa IOF**.
