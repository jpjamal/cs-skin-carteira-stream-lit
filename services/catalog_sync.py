"""Sincronizacao segura do catalogo local usado pelo inventario."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config import CATALOG_SNAPSHOT_FILE
from services.bymykel_catalog import (
    ByMykelCatalogClient,
    build_indexes,
    infer_required_sources,
    lookup_candidates,
    select_catalog_item,
)
from services.catalog_service import hydrate_app_data_from_catalog, load_catalog_snapshot
from data_manager import carregar_dados, salvar_dados


@dataclass(slots=True)
class CatalogSyncResult:
    snapshot_path: Path
    source_files: list[str]
    total_current_items: int
    matched_items: int
    unmatched_items: list[str]
    hydrated_items: int
    mode: str


def _write_snapshot_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def sync_catalog_snapshot(
    force_refresh: bool = False,
    client: ByMykelCatalogClient | None = None,
) -> CatalogSyncResult:
    """Gera o snapshot enxuto do catalogo e hidrata os itens locais."""
    data = carregar_dados()
    raw_items = [item.model_dump() for item in data.itens]

    catalog_client = client or ByMykelCatalogClient()
    source_files = infer_required_sources(raw_items)
    items = catalog_client.load_catalog_items(source_files, force_refresh=force_refresh) if source_files else []
    by_lookup, by_name = build_indexes(items)

    items_by_item_id: dict[str, dict] = {}
    items_by_lookup: dict[str, dict] = {}
    unmatched: list[str] = []

    for raw_item in raw_items:
        match = None
        for candidate in lookup_candidates(raw_item):
            match = by_lookup.get(candidate) or by_name.get(candidate)
            if match:
                break

        if not match:
            unmatched.append(raw_item.get("nome", ""))
            continue

        selected = select_catalog_item(match)
        items_by_item_id[raw_item["id"]] = selected
        for candidate in lookup_candidates(raw_item):
            items_by_lookup.setdefault(candidate, selected)

    payload = {
        "catalog_version": 1,
        "source": {
            "provider": "ByMykel/CSGO-API",
            "language": getattr(catalog_client, "_language", "en"),
            "mode": "remote-cached" if getattr(catalog_client, "_local_api_root", None) is None else "local",
            "source_files": source_files,
        },
        "total_current_items": len(raw_items),
        "matched_items": len(items_by_item_id),
        "unmatched_items": unmatched,
        "items_by_item_id": items_by_item_id,
        "items_by_lookup": items_by_lookup,
    }
    _write_snapshot_atomic(CATALOG_SNAPSHOT_FILE, payload)

    load_catalog_snapshot.cache_clear()
    hydrated_items = hydrate_app_data_from_catalog(data)
    if hydrated_items:
        salvar_dados(data)

    return CatalogSyncResult(
        snapshot_path=CATALOG_SNAPSHOT_FILE,
        source_files=source_files,
        total_current_items=len(raw_items),
        matched_items=len(items_by_item_id),
        unmatched_items=unmatched,
        hydrated_items=hydrated_items,
        mode=payload["source"]["mode"],
    )
