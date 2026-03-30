from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models import Skin

API_ROOT_ENV = "CS2_API_ROOT"
CURRENT_SKINS_FILE_ENV = "CS2_CURRENT_SKINS_FILE"
OUTPUT_FILE_ENV = "CS2_CATALOG_OUTPUT_FILE"

API_ROOT = Path(".")
CURRENT_SKINS_FILE = Path(os.getenv(CURRENT_SKINS_FILE_ENV, "tmp/current_skins.json"))
OUTPUT_FILE = Path(os.getenv(OUTPUT_FILE_ENV, "data/current_skin_catalog.json"))

SOURCE_FILES = [
    "skins_not_grouped.json",
    "stickers.json",
    "keychains.json",
    "agents.json",
    "graffiti.json",
    "patches.json",
    "music_kits.json",
    "crates.json",
    "tools.json",
    "collectibles.json",
]

COLOR_SUFFIXES = {
    "(Roxo)",
    "(Azul)",
    "(Rosa)",
    "(Vermelho)",
    "(Dourado)",
    "(Verde)",
    "(Laranja)",
    "(Amarelo)",
    "(Branco)",
    "(Preto)",
}


def strip_color_suffixes(name: str) -> str:
    text = (name or "").strip()
    changed = True
    while changed:
        changed = False
        for suffix in COLOR_SUFFIXES:
            token = f" {suffix}"
            if text.endswith(token):
                text = text[: -len(token)].strip()
                changed = True
    return text


def lookup_candidates(raw_skin: dict) -> list[str]:
    allowed_fields = {k: v for k, v in raw_skin.items() if k in Skin.model_fields}
    skin = Skin(**allowed_fields)
    base_name = strip_color_suffixes(skin.nome)
    candidates: list[str] = []

    if skin.market_hash_name:
        candidates.append(skin.market_hash_name.strip())

    generated = skin.gerar_market_hash_name().strip()
    if generated:
        candidates.append(generated)

    if skin.tipo == "Adesivo":
        candidates.append(f"Sticker | {base_name}")
    elif skin.tipo == "Charm":
        candidates.append(f"Charm | {base_name}")
    else:
        candidates.append(base_name)

    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def load_catalog_items() -> list[dict]:
    items: list[dict] = []
    for file_name in SOURCE_FILES:
        path = API_ROOT / file_name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for item in data:
            item["_source_file"] = file_name
            items.append(item)
    return items


def build_indexes(items: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    by_lookup: dict[str, dict] = {}
    by_name: dict[str, dict] = {}

    for item in items:
        market_hash_name = (item.get("market_hash_name") or "").strip()
        if market_hash_name and market_hash_name not in by_lookup:
            by_lookup[market_hash_name] = item

        name = (item.get("name") or "").strip()
        if name and name not in by_name:
            by_name[name] = item

    return by_lookup, by_name


def select_item(item: dict) -> dict:
    collections = [{"id": entry.get("id", ""), "name": entry.get("name", "")} for entry in item.get("collections", [])]
    crates = [{"id": entry.get("id", ""), "name": entry.get("name", "")} for entry in item.get("crates", [])]
    return {
        "market_hash_name": item.get("market_hash_name", ""),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "image": item.get("image", ""),
        "rarity": item.get("rarity", {}),
        "weapon": item.get("weapon", {}),
        "category": item.get("category", {}),
        "pattern": item.get("pattern", {}),
        "wear": item.get("wear", {}),
        "team": item.get("team", {}),
        "collections": collections,
        "crates": crates,
        "stattrak": item.get("stattrak", False),
        "souvenir": item.get("souvenir", False),
        "paint_index": item.get("paint_index", ""),
        "source_file": item.get("_source_file", ""),
    }


def main() -> None:
    api_root_value = os.getenv(API_ROOT_ENV, "").strip()
    if not api_root_value:
        raise SystemExit(
            f"Defina a variavel de ambiente {API_ROOT_ENV} apontando para a pasta da API local, por exemplo a pasta public/api/pt-BR."
        )

    api_root = Path(api_root_value)
    raw_skins = json.loads(CURRENT_SKINS_FILE.read_text(encoding="utf-8")).get("skins", [])
    global API_ROOT
    API_ROOT = api_root
    items = load_catalog_items()
    by_lookup, by_name = build_indexes(items)

    items_by_skin_id: dict[str, dict] = {}
    items_by_lookup: dict[str, dict] = {}
    unmatched: list[str] = []

    for raw_skin in raw_skins:
        match = None
        for candidate in lookup_candidates(raw_skin):
            match = by_lookup.get(candidate) or by_name.get(candidate)
            if match:
                break

        if not match:
            unmatched.append(raw_skin.get("nome", ""))
            continue

        selected = select_item(match)
        items_by_skin_id[raw_skin["id"]] = selected

        for candidate in lookup_candidates(raw_skin):
            items_by_lookup.setdefault(candidate, selected)

    payload = {
        "catalog_version": 1,
        "total_current_skins": len(raw_skins),
        "matched_skins": len(items_by_skin_id),
        "unmatched_skins": unmatched,
        "items_by_skin_id": items_by_skin_id,
        "items_by_lookup": items_by_lookup,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Snapshot gerado em {OUTPUT_FILE} com {len(items_by_skin_id)} skins casadas.")
    if unmatched:
        print("Sem match:")
        for name in unmatched:
            print(name)


if __name__ == "__main__":
    main()
