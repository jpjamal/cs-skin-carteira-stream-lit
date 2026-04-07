"""Provider de preco via Steam Community Market."""

from __future__ import annotations

import logging
import re

import requests

from services.price_providers.base import PriceProvider, PriceResult

logger = logging.getLogger(__name__)

STEAM_URL = "https://steamcommunity.com/market/priceoverview/"
APPID_CS2 = 730
CURRENCY_BRL = 7


def _parse_brl(valor_str: str) -> float:
    """Converte 'R$ 1.234,56' para float."""
    limpo = re.sub(r"[^\d,.]", "", valor_str)
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


class SteamMarketProvider(PriceProvider):
    """Busca precos no Steam Community Market (sem API key)."""

    nome = "Steam Market"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "CS2-Item-Tracker/1.0",
                "Accept": "application/json",
            }
        )

    def esta_configurado(self) -> bool:
        return True

    def buscar_preco(self, market_hash_name: str, float_value: float = 0.0, margem: float = 0.01, paint_seed: str = "") -> PriceResult:
        if not market_hash_name:
            return PriceResult.falha(self.nome, "market_hash_name vazio")

        params = {
            "appid": APPID_CS2,
            "currency": CURRENCY_BRL,
            "market_hash_name": market_hash_name,
        }

        try:
            resp = self._session.get(STEAM_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                return PriceResult.falha(self.nome, f"Item nao encontrado: {market_hash_name}")

            preco_str = data.get("lowest_price") or data.get("median_price", "0")
            preco = _parse_brl(preco_str)

            if preco <= 0:
                return PriceResult.falha(self.nome, "Preco retornado invalido")

            metodo = "lowest_price" if data.get("lowest_price") else "median_price"
            return PriceResult(
                preco=preco,
                moeda="BRL",
                provider=self.nome,
                metodo=metodo,
                amostra=1,
                confianca="Baixa",
            )

        except requests.exceptions.Timeout:
            return PriceResult.falha(self.nome, "Timeout na requisicao")
        except requests.exceptions.RequestException as e:
            return PriceResult.falha(self.nome, f"Erro HTTP: {e}")
        except Exception as e:
            logger.exception("Erro inesperado Steam Market")
            return PriceResult.falha(self.nome, str(e))


