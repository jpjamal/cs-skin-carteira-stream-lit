"""Serviço de persistência em JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import DATA_DIR, DATA_FILE
from app.models import AppData, Skin

logger = logging.getLogger(__name__)


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def carregar_dados() -> AppData:
    """Carrega os dados do arquivo JSON. Retorna dados vazios se não existir."""
    _ensure_dir()
    if not DATA_FILE.exists():
        return AppData()
    try:
        raw = DATA_FILE.read_text(encoding="utf-8")
        return AppData.model_validate_json(raw)
    except Exception:
        logger.exception("Erro ao carregar %s", DATA_FILE)
        return AppData()


def salvar_dados(data: AppData) -> None:
    """Salva os dados no arquivo JSON."""
    _ensure_dir()
    DATA_FILE.write_text(
        data.model_dump_json(indent=2),
        encoding="utf-8",
    )


def adicionar_skin(skin: Skin) -> AppData:
    """Adiciona uma skin e persiste."""
    data = carregar_dados()
    data.skins.append(skin)
    salvar_dados(data)
    return data


def remover_skin(skin_id: str) -> AppData:
    """Remove uma skin pelo ID e persiste."""
    data = carregar_dados()
    data.skins = [s for s in data.skins if s.id != skin_id]
    salvar_dados(data)
    return data


def atualizar_skin(skin: Skin) -> AppData:
    """Atualiza uma skin existente."""
    data = carregar_dados()
    data.skins = [skin if s.id == skin.id else s for s in data.skins]
    salvar_dados(data)
    return data


def salvar_config(data: AppData) -> None:
    """Salva apenas as configurações."""
    salvar_dados(data)


def importar_seed_data(seed_path: Path) -> AppData:
    """Importa dados iniciais de um JSON seed se o data file não existir."""
    _ensure_dir()
    if DATA_FILE.exists():
        return carregar_dados()

    if not seed_path.exists():
        return AppData()

    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        skins = [Skin.model_validate(s) for s in raw.get("skins", [])]
        data = AppData(skins=skins)
        salvar_dados(data)
        return data
    except Exception:
        logger.exception("Erro ao importar seed %s", seed_path)
        return AppData()
