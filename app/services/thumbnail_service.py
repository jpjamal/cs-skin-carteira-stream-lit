"""Cache local e seguro para miniaturas de skins."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.config import (
    THUMBNAIL_ALLOWED_SOURCES,
    THUMBNAIL_ERROR_COOLDOWN_SECONDS,
    THUMBNAIL_MAX_BYTES,
    THUMBNAIL_STATE_FILE,
    THUMBNAIL_TIMEOUT_SECONDS,
    THUMBNAIL_TTL_SECONDS,
    THUMBNAILS_DIR,
)

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ThumbnailService:
    """Baixa miniaturas permitidas com cache em disco e backoff simples."""

    def __init__(
        self,
        cache_dir: Path = THUMBNAILS_DIR,
        state_file: Path = THUMBNAIL_STATE_FILE,
        ttl_seconds: int = THUMBNAIL_TTL_SECONDS,
        timeout_seconds: int = THUMBNAIL_TIMEOUT_SECONDS,
        max_bytes: int = THUMBNAIL_MAX_BYTES,
        error_cooldown_seconds: int = THUMBNAIL_ERROR_COOLDOWN_SECONDS,
    ) -> None:
        self._cache_dir = cache_dir
        self._state_file = state_file
        self._ttl_seconds = ttl_seconds
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._error_cooldown_seconds = error_cooldown_seconds
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "CS2-Skin-Tracker/1.0"})

    def get_local_path(self, image_url: str, refresh: bool = False) -> Path | None:
        """Retorna o caminho local da miniatura, baixando quando necessario."""
        if not self.is_allowed_url(image_url):
            return None

        self._ensure_dirs()
        base_name = self._build_cache_name(image_url)
        existing = self._find_existing_file(base_name)

        if existing and not refresh and not self._is_stale(existing):
            return existing

        if not self._should_retry(image_url):
            return existing if existing and existing.exists() else None

        downloaded = self._download(image_url, base_name)
        if downloaded:
            self._clear_error(image_url)
            return downloaded

        return existing if existing and existing.exists() else None

    @staticmethod
    def is_allowed_url(image_url: str) -> bool:
        if not image_url:
            return False

        parsed = urlparse(image_url.strip())
        if parsed.scheme != "https":
            return False
        allowed_prefixes = THUMBNAIL_ALLOWED_SOURCES.get(parsed.netloc)
        if not allowed_prefixes:
            return False
        return any(parsed.path.startswith(prefix) for prefix in allowed_prefixes)

    def _download(self, image_url: str, base_name: str) -> Path | None:
        temp_path = self._cache_dir / f"{base_name}.tmp"
        try:
            response = self._session.get(image_url, timeout=self._timeout_seconds, stream=True)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            extension = ALLOWED_CONTENT_TYPES.get(content_type)
            if not extension:
                self._record_error(image_url, f"content-type nao permitido: {content_type or 'desconhecido'}")
                return None

            content_length = response.headers.get("Content-Length", "").strip()
            if content_length.isdigit() and int(content_length) > self._max_bytes:
                self._record_error(image_url, "imagem maior que o limite permitido")
                return None

            total = 0
            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self._max_bytes:
                        self._record_error(image_url, "imagem excedeu o limite permitido")
                        temp_path.unlink(missing_ok=True)
                        return None
                    handle.write(chunk)

            final_path = self._cache_dir / f"{base_name}{extension}"
            self._delete_existing_variants(base_name)
            temp_path.replace(final_path)
            return final_path
        except requests.RequestException as exc:
            self._record_error(image_url, str(exc))
            logger.info("Falha ao baixar miniatura: %s", exc)
            temp_path.unlink(missing_ok=True)
            return None
        except OSError as exc:
            self._record_error(image_url, str(exc))
            logger.info("Falha ao salvar miniatura: %s", exc)
            temp_path.unlink(missing_ok=True)
            return None
        except Exception as exc:
            self._record_error(image_url, str(exc))
            logger.info("Falha inesperada ao processar miniatura: %s", exc)
            temp_path.unlink(missing_ok=True)
            return None

    def _is_stale(self, path: Path) -> bool:
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return True
        return age > self._ttl_seconds

    def _find_existing_file(self, base_name: str) -> Path | None:
        for extension in ALLOWED_CONTENT_TYPES.values():
            candidate = self._cache_dir / f"{base_name}{extension}"
            if candidate.exists():
                return candidate
        return None

    def _delete_existing_variants(self, base_name: str) -> None:
        for extension in ALLOWED_CONTENT_TYPES.values():
            candidate = self._cache_dir / f"{base_name}{extension}"
            candidate.unlink(missing_ok=True)

    def _build_cache_name(self, image_url: str) -> str:
        return hashlib.sha256(image_url.strip().encode("utf-8")).hexdigest()

    def _ensure_dirs(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict[str, dict]:
        self._ensure_dirs()
        if not self._state_file.exists():
            return {}
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception:
            logger.info("Estado de miniaturas invalido; recriando arquivo")
            return {}

    def _save_state(self, data: dict[str, dict]) -> None:
        temp_file = self._state_file.with_suffix(self._state_file.suffix + ".tmp")
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(self._state_file)

    def _should_retry(self, image_url: str) -> bool:
        state = self._load_state()
        entry = state.get(self._build_cache_name(image_url), {})
        retry_after_ts = entry.get("retry_after_ts", 0.0)
        return time.time() >= retry_after_ts

    def _record_error(self, image_url: str, message: str) -> None:
        state = self._load_state()
        state[self._build_cache_name(image_url)] = {
            "retry_after_ts": time.time() + self._error_cooldown_seconds,
            "last_error": message[:200],
        }
        self._save_state(state)

    def _clear_error(self, image_url: str) -> None:
        state = self._load_state()
        key = self._build_cache_name(image_url)
        if key in state:
            del state[key]
            self._save_state(state)
