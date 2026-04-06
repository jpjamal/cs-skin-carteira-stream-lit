"""Camada central de persistencia JSON com escrita atomica e fallback por backup."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config import DATA_DIR, DATA_FILE, DATA_FILE_BACKUP, SEED_FILE
from models import AppData, Skin

logger = logging.getLogger(__name__)
_APP_DATA_CACHE: dict[Path, tuple[float, AppData]] = {}


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_app_data(path: Path) -> AppData:
    raw = path.read_text(encoding="utf-8")
    return AppData.model_validate_json(raw)


def _get_cached_app_data(path: Path) -> AppData | None:
    if not path.exists():
        _APP_DATA_CACHE.pop(path, None)
        return None

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    cached = _APP_DATA_CACHE.get(path)
    if not cached or cached[0] != mtime:
        return None

    return cached[1].model_copy(deep=True)


def _set_cached_app_data(path: Path, data: AppData) -> None:
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        _APP_DATA_CACHE.pop(path, None)
        return

    _APP_DATA_CACHE[path] = (mtime, data.model_copy(deep=True))


def _atomic_write(path: Path, content: str) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def carregar_dados() -> AppData:
    """Carrega os dados do arquivo JSON. Usa backup se o principal falhar."""
    _ensure_dir()
    if not DATA_FILE.exists():
        return AppData()

    cached = _get_cached_app_data(DATA_FILE)
    if cached is not None:
        return cached

    try:
        data = _read_app_data(DATA_FILE)
        _set_cached_app_data(DATA_FILE, data)
        return data
    except Exception:
        logger.exception("Erro ao carregar %s", DATA_FILE)

    if DATA_FILE_BACKUP.exists():
        try:
            logger.warning("Tentando recuperar dados do backup %s", DATA_FILE_BACKUP)
            data = _read_app_data(DATA_FILE_BACKUP)
            salvar_dados(data)
            return data
        except Exception:
            logger.exception("Erro ao carregar backup %s", DATA_FILE_BACKUP)

    return AppData()


def salvar_dados(data: AppData) -> None:
    """Salva os dados com escrita atomica e backup do ultimo estado valido."""
    _ensure_dir()
    content = data.model_dump_json(indent=2)

    if DATA_FILE.exists():
        try:
            _atomic_write(DATA_FILE_BACKUP, DATA_FILE.read_text(encoding="utf-8"))
            _APP_DATA_CACHE.pop(DATA_FILE_BACKUP, None)
        except Exception:
            logger.exception("Nao foi possivel atualizar backup %s", DATA_FILE_BACKUP)

    _atomic_write(DATA_FILE, content)
    _set_cached_app_data(DATA_FILE, data)


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
    """Salva apenas as configuracoes."""
    salvar_dados(data)


def importar_seed_data(seed_path: Path | None = None) -> AppData:
    """Importa dados iniciais de um JSON seed se o arquivo principal nao existir."""
    _ensure_dir()
    if DATA_FILE.exists():
        return carregar_dados()

    seed = seed_path or SEED_FILE
    if not seed.exists():
        return AppData()

    try:
        raw = json.loads(seed.read_text(encoding="utf-8"))
        skins = [Skin.model_validate(s) for s in raw.get("skins", [])]
        data = AppData(skins=skins)
        salvar_dados(data)
        return data
    except Exception:
        logger.exception("Erro ao importar seed %s", seed)
        return AppData()
