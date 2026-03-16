"""Ponto de entrada da aplicação CS2 Skin Tracker."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.config import APP_ICON, APP_NAME
from app.services.storage import importar_seed_data


def _setup_page() -> None:
    """Configurações iniciais do Streamlit."""
    st.set_page_config(
        page_title=APP_NAME,
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Importar seed data na primeira execução
    seed = Path(__file__).parent / "data" / "seed.json"
    importar_seed_data(seed)


def _sidebar_nav() -> str:
    """Renderiza o menu lateral e retorna a página selecionada."""
    with st.sidebar:
        st.title(f"{APP_ICON} {APP_NAME}")
        st.divider()

        pagina = st.radio(
            "Navegação",
            options=["💼 Carteira", "➕ Adicionar Skin", "⚙️ Configurações"],
            label_visibility="collapsed",
        )

        st.divider()
        st.caption("CS2 Skin Tracker v1.0")
        st.caption("Preços via Steam Market / CSFloat")

    return pagina


def main() -> None:
    """Função principal da aplicação."""
    _setup_page()
    pagina = _sidebar_nav()

    if pagina == "💼 Carteira":
        from app.ui.carteira import render
        render()
    elif pagina == "➕ Adicionar Skin":
        from app.ui.adicionar import render
        render()
    elif pagina == "⚙️ Configurações":
        from app.ui.configuracoes import render
        render()


if __name__ == "__main__":
    main()
