"""Catalogo local enxuto para enriquecer as items existentes."""

from __future__ import annotations

import json
from functools import lru_cache

from config import CATALOG_SNAPSHOT_FILE
from models import AppData, Item
from services.bymykel_catalog import lookup_candidates


def _lookup_candidates(item: Item) -> list[str]:
    """Adapter: converte Item para dict e delega ao bymykel_catalog.lookup_candidates."""
    allowed_fields = {key: value for key, value in item.model_dump().items() if key in Item.model_fields}
    return lookup_candidates(allowed_fields)


@lru_cache(maxsize=1)
def load_catalog_snapshot() -> dict:
    if not CATALOG_SNAPSHOT_FILE.exists():
        return {"items_by_item_id": {}, "items_by_lookup": {}}
    return json.loads(CATALOG_SNAPSHOT_FILE.read_text(encoding="utf-8"))


def get_catalog_entry_for_item(item: Item) -> dict | None:
    snapshot = load_catalog_snapshot()
    direct = snapshot.get("items_by_item_id", {}).get(item.id)
    if direct:
        return direct

    by_lookup = snapshot.get("items_by_lookup", {})
    for candidate in _lookup_candidates(item):
        entry = by_lookup.get(candidate)
        if entry:
            return entry
    return None


def hydrate_item_from_catalog(item: Item) -> bool:
    entry = get_catalog_entry_for_item(item)
    if not entry:
        return False

    changed = False
    if not item.market_hash_name and entry.get("market_hash_name"):
        item.market_hash_name = entry["market_hash_name"]
        changed = True
    catalog_image = entry.get("image", "")
    if catalog_image and (
        not item.imagem_url
        or "raw.githubusercontent.com/ByMykel/counter-strike-image-tracker/" in item.imagem_url
    ):
        if item.imagem_url != catalog_image:
            item.imagem_url = catalog_image
            changed = True
    if not item.imagem_url and catalog_image:
        item.imagem_url = entry["image"]
        changed = True
    return changed


def hydrate_app_data_from_catalog(data: AppData) -> int:
    changes = 0
    for item in data.itens:
        if hydrate_item_from_catalog(item):
            changes += 1
    return changes
