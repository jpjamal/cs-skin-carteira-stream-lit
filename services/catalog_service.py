"""Catalogo local enxuto para enriquecer as skins existentes."""

from __future__ import annotations

import json
from functools import lru_cache

from config import CATALOG_SNAPSHOT_FILE
from models import AppData, Skin
from services.bymykel_catalog import lookup_candidates


def _lookup_candidates(skin: Skin) -> list[str]:
    """Adapter: converte Skin para dict e delega ao bymykel_catalog.lookup_candidates."""
    allowed_fields = {key: value for key, value in skin.model_dump().items() if key in Skin.model_fields}
    return lookup_candidates(allowed_fields)


@lru_cache(maxsize=1)
def load_catalog_snapshot() -> dict:
    if not CATALOG_SNAPSHOT_FILE.exists():
        return {"items_by_skin_id": {}, "items_by_lookup": {}}
    return json.loads(CATALOG_SNAPSHOT_FILE.read_text(encoding="utf-8"))


def get_catalog_entry_for_skin(skin: Skin) -> dict | None:
    snapshot = load_catalog_snapshot()
    direct = snapshot.get("items_by_skin_id", {}).get(skin.id)
    if direct:
        return direct

    by_lookup = snapshot.get("items_by_lookup", {})
    for candidate in _lookup_candidates(skin):
        entry = by_lookup.get(candidate)
        if entry:
            return entry
    return None


def hydrate_skin_from_catalog(skin: Skin) -> bool:
    entry = get_catalog_entry_for_skin(skin)
    if not entry:
        return False

    changed = False
    if not skin.market_hash_name and entry.get("market_hash_name"):
        skin.market_hash_name = entry["market_hash_name"]
        changed = True
    catalog_image = entry.get("image", "")
    if catalog_image and (
        not skin.imagem_url
        or "raw.githubusercontent.com/ByMykel/counter-strike-image-tracker/" in skin.imagem_url
    ):
        if skin.imagem_url != catalog_image:
            skin.imagem_url = catalog_image
            changed = True
    if not skin.imagem_url and catalog_image:
        skin.imagem_url = entry["image"]
        changed = True
    return changed


def hydrate_app_data_from_catalog(data: AppData) -> int:
    changes = 0
    for skin in data.skins:
        if hydrate_skin_from_catalog(skin):
            changes += 1
    return changes
