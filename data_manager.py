"""Camada central de persistencia JSON com escrita atomica e fallback por backup."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config import DATA_DIR, DATA_FILE, DATA_FILE_BACKUP, SEED_FILE
from models import AppData, Item, TipoItem

logger = logging.getLogger(__name__)
_APP_DATA_CACHE: dict[Path, tuple[float, AppData]] = {}


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_app_data(path: Path) -> AppData:
    raw = path.read_text(encoding="utf-8")
    data_dict = json.loads(raw)
    if "items" in data_dict and "itens" not in data_dict:
        data_dict["itens"] = data_dict.pop("items")
        # Migrate old items to have quantidade=1 via Pydantic default
    return AppData.model_validate(data_dict)


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


def adicionar_item(item: Item) -> AppData:
    """Adiciona um item, realizando fusao e media ponderada se agrupavel."""
    data = carregar_dados()
    
    # Itens agrupaveis nao sao armas/facas/luvas
    if item.tipo not in [TipoItem.ARMA, TipoItem.FACA, TipoItem.LUVA]:
        existente = next((i for i in data.itens if i.nome == item.nome and i.id != item.id), None)
        if existente:
            total_gasto = (existente.preco_compra * existente.quantidade) + (item.preco_compra * item.quantidade)
            nova_qtd = existente.quantidade + item.quantidade
            existente.preco_compra = round(total_gasto / nova_qtd, 2)
            existente.quantidade = nova_qtd
            salvar_dados(data)
            return data

    data.itens.append(item)
    salvar_dados(data)
    return data


def remover_item(item_id: str, qtd_remover: int = 0) -> AppData:
    """Remove um item ou subtrai sua quantidade e persiste."""
    data = carregar_dados()
    for item in data.itens:
        if item.id == item_id:
            if qtd_remover > 0 and item.quantidade > qtd_remover:
                item.quantidade -= qtd_remover
            else:
                data.itens.remove(item)
            break
    salvar_dados(data)
    return data


def atualizar_item(item: Item) -> AppData:
    """Atualiza um item existente."""
    data = carregar_dados()
    data.itens = [item if i.id == item.id else i for i in data.itens]
    salvar_dados(data)
    return data


def salvar_config(data: AppData) -> None:
    """Salva apenas as configuracoes."""
    salvar_dados(data)


def exportar_seed(data: AppData) -> None:
    """Exporta os dados atuais para o arquivo seed.json."""
    _ensure_dir()
    content = data.model_dump_json(indent=2)
    _atomic_write(SEED_FILE, content)
    logger.info("Dados exportados para %s", SEED_FILE)


def importar_seed_data(seed_path: Path | None = None) -> AppData:
    """Importa dados iniciais de um JSON seed se nao houver itens cadastrados."""
    _ensure_dir()
    if DATA_FILE.exists():
        data = carregar_dados()
        if data.itens:
            return data

    seed = seed_path or SEED_FILE
    if not seed.exists():
        return carregar_dados() if DATA_FILE.exists() else AppData()

    try:
        raw = json.loads(seed.read_text(encoding="utf-8"))
        items_raw = raw.get("itens", raw.get("items", raw.get("skins", [])))
        itens = [Item.model_validate(s) for s in items_raw]
        if not itens:
            return carregar_dados() if DATA_FILE.exists() else AppData()
        data = carregar_dados() if DATA_FILE.exists() else AppData()
        data.itens = itens
        salvar_dados(data)
        return data
    except Exception:
        logger.exception("Erro ao importar seed %s", seed)
        return AppData()
