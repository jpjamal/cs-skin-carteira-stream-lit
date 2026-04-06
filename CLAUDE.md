# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CS2 Skin Tracker — a Streamlit app for tracking CS2 skin inventory and profit/loss. Fetches prices from Steam Market and CSFloat APIs, persists data in JSON files. Written in Portuguese (BR).

## Commands

```bash
# Run locally (Python 3.12)
pip install -r requirements.txt
streamlit run app.py

# Run with Docker
docker compose up --build -d
# App at http://localhost:8501

# Run tests
python -m pytest tests/ -v
```

No linter configured.

## Architecture

Flat structure following Streamlit Community Cloud conventions. Entry point at root, pages in `views/`.

**Entry point:** `app.py` — sets up Streamlit page config, imports seed data on first run, renders `st.navigation()` with `st.Page()` for multipage navigation.

**Models** (`models.py`): Pydantic models — `Skin` (with computed fields `total_com_iof`, `lucro`, `variacao_pct`), `ApiConfig`, `AppData`. `Skin.gerar_market_hash_name()` builds the API lookup key from skin metadata.

**Data manager** (`data_manager.py`): JSON file persistence at `data/skins.json`. CRUD operations load/save full `AppData` on every call. Atomic writes with backup fallback.

**Config** (`config.py`): All constants, paths (relative to project root via `Path(__file__)`), rate limits, cache TTLs.

**Price providers** (`services/price_providers/`): Strategy pattern — abstract `PriceProvider` base class, concrete `SteamMarketProvider` (no auth, BRL) and `CSFloatProvider` (API key required, USD→BRL conversion). Each returns a `PriceResult` dataclass.

**Price service** (`services/price_service.py`): `PriceService` orchestrates providers with preferred-provider + fallback logic and batch price updates with progress callback.

**Views** (`views/`): `01_Carteira.py` (portfolio view), `02_Inventario.py` (inventory gallery), `03_Adicionar_Skin.py` (add skin form), `04_Configuracoes.py` (API keys, IOF rate, provider selection).

## Key Details

- Data path uses `Path(__file__).parent / "data"` — works both locally and on Streamlit Cloud.
- IOF rate (6.38% default) is applied to purchase price when `iof_aplicavel` is True on a skin.
- Rate limits: Steam ~6s delay between requests, CSFloat ~1.5s (constants in `config.py`).
- All UI text, field names, and model attributes are in Portuguese.
- Deploy to Streamlit Cloud: just point to `app.py` — no special config needed.
