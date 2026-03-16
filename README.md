# 🎮 CS2 Skin Tracker

Aplicação para controle de inventário e valorização de skins do CS2.
Busca preços automaticamente via **Steam Market** e **CSFloat**.

## Funcionalidades

- **Carteira** — visualiza todas as skins com lucro/prejuízo e variação %
- **Adicionar Skin** — cadastra novas skins com busca automática de preço
- **Configurações** — gerencia API keys, IOF e provider preferido
- **Atualização em lote** — atualiza preços de todas as skins com um clique
- **Persistência em JSON** — dados salvos em volume Docker

## Estrutura do Projeto

```
cs2-skin-tracker/
├── app/
│   ├── data/
│   │   └── seed.json              # Dados iniciais (sua planilha)
│   ├── services/
│   │   ├── price_providers/
│   │   │   ├── base.py            # Interface abstrata
│   │   │   ├── steam_market.py    # Provider Steam Market
│   │   │   └── csfloat.py         # Provider CSFloat
│   │   ├── price_service.py       # Orquestrador de providers
│   │   └── storage.py             # Persistência JSON
│   ├── ui/
│   │   ├── carteira.py            # Página da carteira
│   │   ├── adicionar.py           # Página de adicionar skin
│   │   └── configuracoes.py       # Página de configurações
│   ├── config.py                  # Constantes
│   ├── models.py                  # Modelos Pydantic
│   └── main.py                    # Entry point Streamlit
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
streamlit run app/main.py
```

## Providers de Preço

| Provider       | API Key? | Moeda | Rate Limit    |
|----------------|----------|-------|---------------|
| Steam Market   | Não      | BRL   | ~20 req/min   |
| CSFloat        | Sim      | USD→BRL | ~60 req/min |

### Steam Market
Funciona sem configuração. Os preços incluem a taxa de 15% do Steam,
então podem ser um pouco mais altos que no BUFF163/CSFloat.

### CSFloat
Requer API key gratuita. Obtenha em [csfloat.com/developers](https://csfloat.com/developers).
Preços em USD são convertidos para BRL automaticamente.

## IOF

A taxa IOF padrão é **6.38%** (compras internacionais com cartão).
Pode ser alterada em **Configurações → Taxa IOF**.
