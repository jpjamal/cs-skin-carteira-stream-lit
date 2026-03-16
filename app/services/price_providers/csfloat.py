"""Provider de preço via CSFloat API."""

from __future__ import annotations

import logging
import time

import requests

from app.config import CSFLOAT_DELAY_SECONDS
from app.services.price_providers.base import PriceProvider, PriceResult

logger = logging.getLogger(__name__)

CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"
# Taxa de câmbio padrão USD→BRL (atualizar conforme necessário)
USD_BRL_FALLBACK = 5.80


class CSFloatProvider(PriceProvider):
    """Busca preços via CSFloat Marketplace API."""

    nome = "CSFloat"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._last_request: float = 0.0

    def esta_configurado(self) -> bool:
        return bool(self._api_key)

    def set_api_key(self, key: str) -> None:
        self._api_key = key

    def buscar_preco(self, market_hash_name: str, float_value: float = 0.0, margem: float = 0.01, paint_seed: str = "") -> PriceResult:
        if not self._api_key:
            return PriceResult.falha(self.nome, "API key não configurada")

        if not market_hash_name:
            return PriceResult.falha(self.nome, "market_hash_name vazio")

        self._rate_limit()

        headers = {"Authorization": self._api_key}
        params: dict = {
            "market_hash_name": market_hash_name,
            "sort_by": "lowest_price",
            "type": "buy_now",
            "limit": 1,
        }

        if float_value > 0:
            params["min_float"] = max(0.0, round(float_value - margem, 4))
            params["max_float"] = min(1.0, round(float_value + margem, 4))

        if paint_seed:
            params["paint_seed"] = paint_seed

        try:
            resp = requests.get(
                CSFLOAT_LISTINGS_URL,
                headers=headers,
                params=params,
                timeout=15,
            )

            if resp.status_code == 401:
                return PriceResult.falha(self.nome, "API key inválida")
            if resp.status_code == 429:
                return PriceResult.falha(self.nome, "Rate limit excedido")

            resp.raise_for_status()
            data = resp.json()

            listings = data if isinstance(data, list) else data.get("data", [])
            if not listings:
                return PriceResult.falha(
                    self.nome, f"Nenhum listing encontrado: {market_hash_name}"
                )

            # CSFloat retorna preço em centavos de USD — já vem o mais barato (sort_by=lowest_price, limit=1)
            price_cents = listings[0].get("price", 0)
            price_usd = price_cents / 100.0 if price_cents > 0 else 0.0

            if price_usd <= 0:
                return PriceResult.falha(self.nome, "Preço retornado inválido")

            # Converter USD → BRL
            taxa = self._buscar_cambio()
            preco_brl = round(price_usd * taxa, 2)

            return PriceResult(preco=preco_brl, moeda="BRL", provider=self.nome)

        except requests.exceptions.Timeout:
            return PriceResult.falha(self.nome, "Timeout na requisição")
        except requests.exceptions.RequestException as e:
            return PriceResult.falha(self.nome, f"Erro HTTP: {e}")
        except Exception as e:
            logger.exception("Erro inesperado CSFloat")
            return PriceResult.falha(self.nome, str(e))

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < CSFLOAT_DELAY_SECONDS:
            time.sleep(CSFLOAT_DELAY_SECONDS - elapsed)
        self._last_request = time.time()

    @staticmethod
    def _buscar_cambio() -> float:
        """Tenta buscar câmbio USD/BRL; usa fallback se falhar."""
        try:
            resp = requests.get(
                "https://open.er-api.com/v6/latest/USD",
                timeout=5,
            )
            if resp.ok:
                rates = resp.json().get("rates", {})
                return rates.get("BRL", USD_BRL_FALLBACK)
        except Exception:
            pass
        return USD_BRL_FALLBACK
