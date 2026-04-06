"""Provider de preco via CSFloat API — baseado em historico de vendas."""

from __future__ import annotations

import logging
import time
from statistics import median

import requests

from config import CSFLOAT_DELAY_SECONDS, FX_CACHE_TTL_SECONDS
from services.price_providers.base import PriceProvider, PriceResult
from services.runtime_state import build_fx_cache_key, get_cached_price, set_cached_price

logger = logging.getLogger(__name__)

CSFLOAT_SALES_URL = "https://csfloat.com/api/v1/history/{market_hash_name}/sales"
CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"
USD_BRL_FALLBACK = 5.80
SALES_LIMIT = 50
MIN_RELIABLE_SALES = 3
PREFERRED_SALES = 10
FLOAT_NARROW_MARGIN = 0.02
FLOAT_WIDE_MARGIN = 0.05
STEAM_IMAGE_BASE_URL = "https://community.cloudflare.steamstatic.com/economy/image"


class CSFloatProvider(PriceProvider):
    """Busca precos via CSFloat API usando historico de vendas."""

    nome = "CSFloat"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._last_request: float = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "CS2-Skin-Tracker/1.0",
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
            sales = self._buscar_historico_vendas(market_hash_name)
            if not sales:
                return PriceResult.falha(
                    self.nome,
                    f"Nenhuma venda encontrada: {market_hash_name}",
                )

            imagem_url = self._extrair_imagem_url_sales(sales)

            if float_value > 0:
                preco_usd, usados, metodo = self._estimar_por_float(
                    sales, float_value, margem,
                )
                if preco_usd > 0:
                    return self._build_success_result(
                        preco_usd, metodo, usados, imagem_url,
                    )

            preco_usd, usados = self._estimar_geral(sales)
            if preco_usd > 0:
                return self._build_success_result(
                    preco_usd, "mediana historico geral", usados, imagem_url,
                )

            return PriceResult.falha(
                self.nome,
                f"Vendas sem preco valido: {market_hash_name}",
            )

        except requests.exceptions.Timeout:
            return PriceResult.falha(self.nome, "Timeout na requisicao")
        except requests.exceptions.RequestException as e:
            return PriceResult.falha(self.nome, f"Erro HTTP: {e}")
        except Exception as e:
            logger.exception("Erro inesperado CSFloat")
            return PriceResult.falha(self.nome, str(e))

    def _buscar_historico_vendas(self, market_hash_name: str) -> list[dict]:
        self._rate_limit()
        url = CSFLOAT_SALES_URL.format(market_hash_name=requests.utils.quote(market_hash_name))

        resp = self._session.get(
            url,
            headers={"Authorization": self._api_key},
            timeout=15,
        )

        if resp.status_code == 401:
            raise requests.exceptions.RequestException("API key invalida")
        if resp.status_code == 429:
            raise requests.exceptions.RequestException("Rate limit excedido")

        resp.raise_for_status()
        data = resp.json()
        sales = data if isinstance(data, list) else data.get("data", [])
        return sales if isinstance(sales, list) else []

    def _extrair_vendas_validas(self, sales: list[dict]) -> list[tuple[float, float | None]]:
        """Extrai (preco_usd, float_value) de cada venda valida."""
        resultado: list[tuple[float, float | None]] = []
        for sale in sales:
            price_cents = sale.get("price", 0)
            price_usd = price_cents / 100.0 if price_cents > 0 else 0.0
            if price_usd <= 0:
                continue

            item = sale.get("item") or {}
            sale_float = item.get("float_value")
            if not isinstance(sale_float, (int, float)):
                sale_float = None

            resultado.append((price_usd, sale_float))
        return resultado

    def _estimar_por_float(
        self,
        sales: list[dict],
        target_float: float,
        margem: float,
    ) -> tuple[float, int, str]:
        """Estima preco filtrando vendas por proximidade de float."""
        vendas = self._extrair_vendas_validas(sales)
        com_float = [(p, f) for p, f in vendas if f is not None]

        if not com_float:
            return 0.0, 0, ""

        # 1) Margem estreita (parametro do usuario)
        narrow = [(p, f) for p, f in com_float if abs(f - target_float) <= margem]
        if len(narrow) >= MIN_RELIABLE_SALES:
            narrow.sort(key=lambda x: abs(x[1] - target_float))
            selecionados = narrow[:PREFERRED_SALES]
            precos = [p for p, _ in selecionados]
            return round(float(median(precos)), 2), len(precos), f"historico float ±{margem}"

        # 2) Margem narrow padrao
        if margem < FLOAT_NARROW_MARGIN:
            narrow2 = [(p, f) for p, f in com_float if abs(f - target_float) <= FLOAT_NARROW_MARGIN]
            if len(narrow2) >= MIN_RELIABLE_SALES:
                narrow2.sort(key=lambda x: abs(x[1] - target_float))
                selecionados = narrow2[:PREFERRED_SALES]
                precos = [p for p, _ in selecionados]
                return round(float(median(precos)), 2), len(precos), f"historico float ±{FLOAT_NARROW_MARGIN}"

        # 3) Margem ampla
        wide = [(p, f) for p, f in com_float if abs(f - target_float) <= FLOAT_WIDE_MARGIN]
        if len(wide) >= MIN_RELIABLE_SALES:
            wide.sort(key=lambda x: abs(x[1] - target_float))
            selecionados = wide[:PREFERRED_SALES]
            precos = [p for p, _ in selecionados]
            return round(float(median(precos)), 2), len(precos), f"historico float ±{FLOAT_WIDE_MARGIN}"

        # 4) Poucas vendas com float proximo — usa as mais proximas disponiveis
        com_float.sort(key=lambda x: abs(x[1] - target_float))
        selecionados = com_float[:PREFERRED_SALES]
        if selecionados:
            precos = [p for p, _ in selecionados]
            return round(float(median(precos)), 2), len(precos), "historico float mais proximo"

        return 0.0, 0, ""

    def _estimar_geral(self, sales: list[dict]) -> tuple[float, int]:
        """Mediana de todas as vendas recentes, sem filtro de float."""
        vendas = self._extrair_vendas_validas(sales)
        if not vendas:
            return 0.0, 0
        precos = [p for p, _ in vendas[:PREFERRED_SALES]]
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
    def _extrair_imagem_url_sales(sales: list[dict]) -> str:
        for sale in sales:
            item = sale.get("item") or {}
            icon_url = item.get("icon_url")
            if icon_url:
                return f"{STEAM_IMAGE_BASE_URL}/{icon_url}/160fx160f"
        return ""

    def _extrair_imagem_url(self, listings: list[dict]) -> str:
        return self._extrair_imagem_url_sales(listings)

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
