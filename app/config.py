"""Constantes e configurações da aplicação."""

from pathlib import Path

APP_NAME = "CS2 Skin Tracker"
APP_ICON = "🎮"

DATA_DIR = Path("/app/data")
DATA_FILE = DATA_DIR / "skins.json"

TIPOS_ITEM = [
    "Arma", "Faca", "Luva", "Adesivo", "Agente",
    "Charm", "Grafite", "Patch", "Music Kit", "Caixa", "Outro",
]

DESGASTES = [
    "Factory New (FN)", "Minimal Wear (MW)", "Field-Tested (FT)",
    "Well-Worn (WW)", "Battle-Scarred (BS)", "N/A",
]

PLATAFORMAS = [
    "CSFloat", "BUFF163", "Steam Market", "DMarket", "CS.Money",
    "Skinport", "BitSkins", "Tradeit.gg", "SkinBaron",
    "DashSkins", "BleikStore", "NeshaStore", "BRSkins",
    "White Market", "Trade P2P", "Drop in-game", "Outro",
]

PRICE_PROVIDERS = ["steam", "csfloat"]

# Rate limiting
STEAM_DELAY_SECONDS = 3.5
CSFLOAT_DELAY_SECONDS = 1.0
