"""Provider de preco via CSFloat API — baseado em listings ativos."""

from __future__ import annotations

import logging
import time
from statistics import median

import requests

from config import CSFLOAT_DELAY_SECONDS, FX_CACHE_TTL_SECONDS
from services.price_providers.base import PriceProvider, PriceResult
from services.runtime_state import build_fx_cache_key, get_cached_price, set_cached_price

logger = logging.getLogger(__name__)

CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"
USD_BRL_FALLBACK = 5.80
LISTINGS_LIMIT = 50
MIN_RELIABLE_LISTINGS = 3
PREFERRED_LISTINGS = 10
FLOAT_NARROW_MARGIN = 0.02
FLOAT_WIDE_MARGIN = 0.05
STEAM_IMAGE_BASE_URL = "https://community.cloudflare.steamstatic.com/economy/image"


class CSFloatProvider(PriceProvider):
    """Busca precos via CSFloat API usando listings ativos."""

    nome = "CSFloat"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._last_request: float = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "CS2-Item-Tracker/1.0",
                "Accept": "application/json",
            }
        )

    def esta_configurado(self) -> bool:
        return bool(self._api_key)

    def set_api_key(self, key: str) -> None:
        self._api_key = key

    def buscar_preco(
        self,
        market_hash_name: str,
        float_value: float = 0.0,
        margem: float = 0.01,
        paint_seed: str = "",
    ) -> PriceResult:
        if not self._api_key:
            return PriceResult.falha(self.nome, "API key nao configurada")

        if not market_hash_name:
            return PriceResult.falha(self.nome, "market_hash_name vazio")

        try:
            listings = self._buscar_listings(market_hash_name)

            # Fallback para Title Case se falhou com Tudo Maiusculo ou Tudo Minusculo
            if not listings and (market_hash_name.isupper() or market_hash_name.islower()):
                fallback_name = market_hash_name.title().replace(" | ", " | ")
                if fallback_name != market_hash_name:
                    logger.info("Retrying CSFloat with Title Case: %s", fallback_name)
                    listings = self._buscar_listings(fallback_name)

            if not listings:
                return PriceResult.falha(
                    self.nome,
                    f"Nenhum listing encontrado para '{market_hash_name}'. Tente o nome exato do Steam.",
                )

            imagem_url = self._extrair_imagem_url_listings(listings)

            if float_value > 0:
                preco_usd, usados, metodo = self._estimar_por_float(
                    listings, float_value, margem,
                )
                if preco_usd > 0:
                    return self._build_success_result(
                        preco_usd, metodo, usados, imagem_url,
                    )

            preco_usd, usados = self._estimar_geral(listings)
            if preco_usd > 0:
                return self._build_success_result(
                    preco_usd, "mediana listings", usados, imagem_url,
                )

            return PriceResult.falha(
                self.nome,
                f"Listings sem preco valido: {market_hash_name}",
            )

        except requests.exceptions.Timeout:
            return PriceResult.falha(self.nome, "Timeout na requisicao")
        except requests.exceptions.RequestException as e:
            return PriceResult.falha(self.nome, f"Erro HTTP: {e}")
        except Exception as e:
            logger.exception("Erro inesperado CSFloat")
            return PriceResult.falha(self.nome, str(e))

    def _buscar_listings(self, market_hash_name: str) -> list[dict]:
        self._rate_limit()

        params = {
            "market_hash_name": market_hash_name,
            "sort_by": "lowest_price",
            "limit": LISTINGS_LIMIT,
        }

        resp = self._session.get(
            CSFLOAT_LISTINGS_URL,
            params=params,
            headers={"Authorization": self._api_key},
            timeout=15,
        )

        if resp.status_code == 401:
            raise requests.exceptions.RequestException("API key invalida")
        if resp.status_code == 429:
            raise requests.exceptions.RequestException("Rate limit excedido")

        resp.raise_for_status()
        data = resp.json()
        listings = data if isinstance(data, list) else data.get("data", [])
        return listings if isinstance(listings, list) else []

    def _extrair_listings_validos(self, listings: list[dict]) -> list[tuple[float, float | None]]:
        """Extrai (preco_usd, float_value) de cada listing valido."""
        resultado: list[tuple[float, float | None]] = []
        for listing in listings:
            price_cents = listing.get("price", 0)
            price_usd = price_cents / 100.0 if price_cents > 0 else 0.0
            if price_usd <= 0:
                continue

            item = listing.get("item") or {}
            listing_float = item.get("float_value")
            if not isinstance(listing_float, (int, float)):
                listing_float = None

            resultado.append((price_usd, listing_float))
        return resultado

    def _estimar_por_float(
        self,
        listings: list[dict],
        target_float: float,
        margem: float,
    ) -> tuple[float, int, str]:
        """Estima preco filtrando listings por proximidade de float."""
        itens = self._extrair_listings_validos(listings)
        com_float = [(p, f) for p, f in itens if f is not None]

        if not com_float:
            return 0.0, 0, ""

        # 1) Margem estreita (parametro do usuario)
        narrow = [(p, f) for p, f in com_float if abs(f - target_float) <= margem]
        if len(narrow) >= MIN_RELIABLE_LISTINGS:
            narrow.sort(key=lambda x: abs(x[1] - target_float))
            selecionados = narrow[:PREFERRED_LISTINGS]
            precos = [p for p, _ in selecionados]
            return round(float(median(precos)), 2), len(precos), f"listings float ±{margem}"

        # 2) Margem narrow padrao
        if margem < FLOAT_NARROW_MARGIN:
            narrow2 = [(p, f) for p, f in com_float if abs(f - target_float) <= FLOAT_NARROW_MARGIN]
            if len(narrow2) >= MIN_RELIABLE_LISTINGS:
                narrow2.sort(key=lambda x: abs(x[1] - target_float))
                selecionados = narrow2[:PREFERRED_LISTINGS]
                precos = [p for p, _ in selecionados]
                return round(float(median(precos)), 2), len(precos), f"listings float ±{FLOAT_NARROW_MARGIN}"

        # 3) Margem ampla
        wide = [(p, f) for p, f in com_float if abs(f - target_float) <= FLOAT_WIDE_MARGIN]
        if len(wide) >= MIN_RELIABLE_LISTINGS:
            wide.sort(key=lambda x: abs(x[1] - target_float))
            selecionados = wide[:PREFERRED_LISTINGS]
            precos = [p for p, _ in selecionados]
            return round(float(median(precos)), 2), len(precos), f"listings float ±{FLOAT_WIDE_MARGIN}"

        # 4) Poucos listings com float proximo — usa os mais proximos disponiveis
        com_float.sort(key=lambda x: abs(x[1] - target_float))
        selecionados = com_float[:PREFERRED_LISTINGS]
        if selecionados:
            precos = [p for p, _ in selecionados]
            return round(float(median(precos)), 2), len(precos), "listings float mais proximo"

        return 0.0, 0, ""

    def _estimar_geral(self, listings: list[dict]) -> tuple[float, int]:
        """Mediana de todos os listings, sem filtro de float."""
        itens = self._extrair_listings_validos(listings)
        if not itens:
            return 0.0, 0
        precos = [p for p, _ in itens[:PREFERRED_LISTINGS]]
        return round(float(median(precos)), 2), len(precos)

    def _build_success_result(
        self,
        preco_usd: float,
        metodo: str,
        usados: int,
        imagem_url: str = "",
    ) -> PriceResult:
        taxa = self._buscar_cambio()
        preco_brl = round(preco_usd * taxa, 2)
        return PriceResult(
            preco=preco_brl,
            moeda="BRL",
            provider=self.nome,
            metodo=metodo,
            amostra=usados,
            imagem_url=imagem_url,
        )

    @staticmethod
    def _extrair_imagem_url_listings(listings: list[dict]) -> str:
        for listing in listings:
            item = listing.get("item") or {}
            icon_url = item.get("icon_url")
            if icon_url:
                return f"{STEAM_IMAGE_BASE_URL}/{icon_url}/160fx160f"
        return ""

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < CSFLOAT_DELAY_SECONDS:
            time.sleep(CSFLOAT_DELAY_SECONDS - elapsed)
        self._last_request = time.time()

    @staticmethod
    def _buscar_cambio() -> float:
        """Tenta buscar cambio USD/BRL; usa fallback se falhar."""
        cache_key = build_fx_cache_key("USD", "BRL")
        cache = get_cached_price(cache_key)
        if cache and cache.preco > 0:
            return cache.preco

        try:
            resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            if resp.ok:
                rates = resp.json().get("rates", {})
                taxa = rates.get("BRL", USD_BRL_FALLBACK)
                set_cached_price(
                    cache_key,
                    preco=taxa,
                    provider="fx",
                    ttl_seconds=FX_CACHE_TTL_SECONDS,
                )
                return taxa
        except Exception:
            pass
        return USD_BRL_FALLBACK
