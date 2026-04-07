"""Interface base para provedores de preco."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceResult:
    """Resultado de uma consulta de preco."""

    preco: float
    moeda: str = "BRL"
    provider: str = ""
    sucesso: bool = True
    erro: str = ""
    cache_hit: bool = False
    stale: bool = False
    metodo: str = ""
    amostra: int = 0
    confianca: str = ""
    atualizado_em: str = ""
    imagem_url: str = ""

    def __post_init__(self) -> None:
        if not self.atualizado_em:
            self.atualizado_em = datetime.now().isoformat()

    @classmethod
    def falha(cls, provider: str, erro: str, cache_hit: bool = False, stale: bool = False) -> PriceResult:
        return cls(
            preco=0.0,
            provider=provider,
            sucesso=False,
            erro=erro,
            cache_hit=cache_hit,
            stale=stale,
        )


class PriceProvider(ABC):
    """Interface para provedores de preco de items."""

    nome: str = ""

    @abstractmethod
    def buscar_preco(self, market_hash_name: str, float_value: float = 0.0, margem: float = 0.01, paint_seed: str = "") -> PriceResult:
        """Busca o preco atual de uma item pelo market_hash_name."""

    @abstractmethod
    def esta_configurado(self) -> bool:
        """Verifica se o provider esta pronto para uso."""
