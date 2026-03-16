"""Serviço de busca de preços — orquestra os providers."""

from __future__ import annotations

import logging
from typing import Callable

from app.models import ApiConfig, Skin
from app.services.price_providers import (
    CSFloatProvider,
    PriceResult,
    SteamMarketProvider,
)

logger = logging.getLogger(__name__)


class PriceService:
    """Busca preços usando os providers configurados, com fallback."""

    def __init__(self, config: ApiConfig, considerar_float: bool = False, margem_float: float = 0.01, considerar_pattern: bool = False) -> None:
        self._steam = SteamMarketProvider()
        self._csfloat = CSFloatProvider(api_key=config.csfloat_api_key)
        self._config = config
        self._considerar_float = considerar_float
        self._margem_float = margem_float
        self._considerar_pattern = considerar_pattern

    def atualizar_config(self, config: ApiConfig) -> None:
        self._config = config
        self._csfloat.set_api_key(config.csfloat_api_key)

    @property
    def providers_disponiveis(self) -> list[str]:
        disponiveis = []
        if self._steam.esta_configurado():
            disponiveis.append("steam")
        if self._csfloat.esta_configurado():
            disponiveis.append("csfloat")
        return disponiveis

    def buscar_preco(self, skin: Skin) -> PriceResult:
        """Busca preço com fallback entre providers."""
        market_name = skin.gerar_market_hash_name()
        if not market_name:
            return PriceResult.falha("", "Não foi possível gerar market_hash_name")

        float_val = skin.float_value if self._considerar_float else 0.0
        margem = self._margem_float
        seed = skin.pattern_seed if self._considerar_pattern else ""
        preferido = self._config.provider_preferido

        if preferido == "csfloat" and self._csfloat.esta_configurado():
            resultado = self._csfloat.buscar_preco(market_name, float_val, margem, seed)
            if resultado.sucesso:
                return resultado
            logger.info("CSFloat falhou, tentando Steam: %s", resultado.erro)
            return self._steam.buscar_preco(market_name)

        # Steam como padrão ou fallback
        resultado = self._steam.buscar_preco(market_name)
        if resultado.sucesso:
            return resultado

        if self._csfloat.esta_configurado():
            logger.info("Steam falhou, tentando CSFloat: %s", resultado.erro)
            return self._csfloat.buscar_preco(market_name, float_val, margem, seed)

        return resultado

    def buscar_precos_lote(
        self,
        skins: list[Skin],
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, PriceResult]:
        """Busca preços para várias skins com callback de progresso."""
        resultados: dict[str, PriceResult] = {}
        total = len(skins)

        for i, skin in enumerate(skins):
            if on_progress:
                on_progress(i + 1, total, skin.nome)

            resultado = self.buscar_preco(skin)
            resultados[skin.id] = resultado

        return resultados
