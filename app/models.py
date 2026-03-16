"""Modelos de dados da aplicação CS2 Skin Tracker."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class TipoItem(StrEnum):
    ARMA = "Arma"
    FACA = "Faca"
    LUVA = "Luva"
    ADESIVO = "Adesivo"
    AGENTE = "Agente"
    CHARM = "Charm"
    GRAFITE = "Grafite"
    PATCH = "Patch"
    MUSIC_KIT = "Music Kit"
    CAIXA = "Caixa"
    OUTRO = "Outro"


class Desgaste(StrEnum):
    FN = "Factory New (FN)"
    MW = "Minimal Wear (MW)"
    FT = "Field-Tested (FT)"
    WW = "Well-Worn (WW)"
    BS = "Battle-Scarred (BS)"
    NA = "N/A"


DESGASTE_STEAM_MAP: dict[str, str] = {
    "Factory New (FN)": "Factory New",
    "Minimal Wear (MW)": "Minimal Wear",
    "Field-Tested (FT)": "Field-Tested",
    "Well-Worn (WW)": "Well-Worn",
    "Battle-Scarred (BS)": "Battle-Scarred",
}


class Skin(BaseModel):
    """Representa uma skin comprada pelo usuário."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    nome: str
    tipo: str = TipoItem.ARMA
    desgaste: str = Desgaste.NA
    float_value: float = 0.0
    stattrak: str = "Não"
    pattern_seed: str = ""
    plataforma: str = ""
    preco_compra: float = 0.0
    iof_aplicavel: bool = False
    preco_atual: float = 0.0
    notas: str = ""
    market_hash_name: str = ""
    criado_em: str = Field(default_factory=lambda: datetime.now().isoformat())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_com_iof(self) -> float:
        if self.iof_aplicavel and self.preco_compra > 0:
            return round(self.preco_compra * 1.0638, 2)
        return self.preco_compra

    @computed_field  # type: ignore[prop-decorator]
    @property
    def lucro(self) -> float:
        if self.preco_atual > 0 and self.total_com_iof > 0:
            return round(self.preco_atual - self.total_com_iof, 2)
        if self.preco_atual > 0 and self.total_com_iof == 0:
            return self.preco_atual
        return 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def variacao_pct(self) -> float:
        if self.total_com_iof > 0 and self.preco_atual > 0:
            return round((self.preco_atual - self.total_com_iof) / self.total_com_iof, 4)
        return 0.0

    def gerar_market_hash_name(self) -> str:
        """Gera o market_hash_name para busca de preço nas APIs."""
        if self.market_hash_name:
            return self.market_hash_name

        nome_base = re.sub(r"\s*\([^)]*\)\s*$", "", self.nome).strip()

        if self.tipo == TipoItem.ADESIVO:
            if not nome_base.lower().startswith("sticker"):
                return f"Sticker | {nome_base}"
            return nome_base

        if self.tipo == TipoItem.CHARM:
            if not nome_base.lower().startswith("charm"):
                return f"Charm | {nome_base}"
            return nome_base

        desgaste_steam = DESGASTE_STEAM_MAP.get(self.desgaste, "")
        if desgaste_steam:
            prefixo = "StatTrak™ " if self.stattrak == "Sim" else ""
            return f"{prefixo}{nome_base} ({desgaste_steam})"

        return nome_base


class ApiConfig(BaseModel):
    """Configurações de API keys."""

    csfloat_api_key: str = ""
    steam_enabled: bool = True
    iof_percentual: float = 6.38
    provider_preferido: str = "steam"


class AppData(BaseModel):
    """Dados completos da aplicação."""

    skins: list[Skin] = Field(default_factory=list)
    config: ApiConfig = Field(default_factory=ApiConfig)
