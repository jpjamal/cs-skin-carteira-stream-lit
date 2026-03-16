# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CS2 Skin Tracker — a Streamlit app for tracking CS2 skin inventory and profit/loss. Fetches prices from Steam Market and CSFloat APIs, persists data in JSON files. Written in Portuguese (BR).

## Commands

```bash
# Run locally (Python 3.12, pyenv virtualenv "cs-skin-carteira-3.12")
pip install -r requirements.txt
streamlit run app/main.py

# Run with Docker (recommended)
docker compose up --build -d
# App at http://localhost:8501
```

No tests or linter configured.

## Architecture

**Entry point:** `app/main.py` — sets up Streamlit page config, imports seed data on first run, renders sidebar navigation that lazy-imports UI pages.

**Models** (`app/models.py`): Pydantic models — `Skin` (with computed fields `total_com_iof`, `lucro`, `variacao_pct`), `ApiConfig`, `AppData`. `Skin.gerar_market_hash_name()` builds the API lookup key from skin metadata.

**Price providers** (`app/services/price_providers/`): Strategy pattern — abstract `PriceProvider` base class, concrete `SteamMarketProvider` (no auth, BRL) and `CSFloatProvider` (API key required, USD→BRL conversion). Each returns a `PriceResult` dataclass.

**Price service** (`app/services/price_service.py`): `PriceService` orchestrates providers with preferred-provider + fallback logic and batch price updates with progress callback.

**Storage** (`app/services/storage.py`): JSON file persistence at `/app/data/skins.json` (Docker volume). CRUD operations load/save full `AppData` on every call.

**UI pages** (`app/ui/`): `carteira.py` (portfolio view), `adicionar.py` (add skin form), `configuracoes.py` (API keys, IOF rate, provider selection).

## Key Details

- Data path is hardcoded to `/app/data/` in `app/config.py` (Docker path). For local dev, create a `data/` directory or adjust `DATA_DIR`.
- IOF rate (6.38% default) is applied to purchase price when `iof_aplicavel` is True on a skin.
- Rate limits: Steam ~3.5s delay between requests, CSFloat ~1.0s (constants in `app/config.py`).
- All UI text, field names, and model attributes are in Portuguese.
