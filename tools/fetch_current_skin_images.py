from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_FILE = ROOT_DIR / "data" / "current_skin_catalog.json"
TMP_DIR = ROOT_DIR / "tmp" / "counter-strike-image-tracker"
REPO_URL = "https://github.com/ByMykel/counter-strike-image-tracker.git"


def run_git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, check=True)


def ensure_repo() -> None:
    if TMP_DIR.exists():
        run_git("fetch", "--depth", "1", "origin", "main", cwd=TMP_DIR)
        run_git("checkout", "main", cwd=TMP_DIR)
        run_git("pull", "--ff-only", cwd=TMP_DIR)
        return

    TMP_DIR.parent.mkdir(parents=True, exist_ok=True)
    run_git("clone", "--depth", "1", REPO_URL, str(TMP_DIR))


def load_images_index() -> dict[str, str]:
    raw = subprocess.check_output(["git", "-C", str(TMP_DIR), "show", "HEAD:static/images.json"])
    return json.loads(raw.decode("utf-8"))


def build_image_key(url: str) -> str:
    marker = "/static/panorama/images/"
    if marker not in url:
        return ""
    path = url.split(marker, 1)[1]
    if path.endswith("_png.png"):
        path = path[: -len("_png.png")]
    return path


def resolve_url(url: str, images_index: dict[str, str]) -> str:
    key = build_image_key(url)
    if not key:
        return url
    return images_index.get(key, url)


def main() -> None:
    ensure_repo()
    images_index = load_images_index()
    snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))

    resolved = 0
    unresolved = 0

    for item in snapshot.get("items_by_skin_id", {}).values():
        original = item.get("image", "")
        updated = resolve_url(original, images_index)
        item["image"] = updated
        item.pop("local_image", None)
        if updated != original:
            resolved += 1
        else:
            unresolved += 1

    for item in snapshot.get("items_by_lookup", {}).values():
        original = item.get("image", "")
        item["image"] = resolve_url(original, images_index)
        item.pop("local_image", None)

    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"URLs resolvidas: {resolved}")
    print(f"URLs sem resolucao: {unresolved}")


if __name__ == "__main__":
    main()
