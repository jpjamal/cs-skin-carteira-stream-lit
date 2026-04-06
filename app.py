"""
app.py — Entrypoint da aplicacao CS2 Skin Tracker.

Configura o tema, sidebar e navegacao multipage do Streamlit.
"""

import streamlit as st

from data_manager import importar_seed_data

st.set_page_config(
    page_title="CS2 Skin Tracker",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Seed data na primeira execucao ─────────────────────────────────────────
importar_seed_data()

# ── Forcar CSS Theme Steam (Ignora cache do restart Streamlit) ─────────────
st.markdown(
    """
    <style>
    /* Botoes Primarios no formato Steam */
    button[kind="primary"] {
        background-color: #66c0f4 !important;
        border-color: #66c0f4 !important;
        color: #1b2838 !important;
        font-weight: 600 !important;
    }
    button[kind="primary"]:hover {
        background-color: #3b9cd9 !important;
        border-color: #3b9cd9 !important;
        color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ── Navegacao ──────────────────────────────────────────────────────────────
paginas = st.navigation(
    [
        st.Page("views/01_Carteira.py",        title="Carteira",        icon="💼", default=True),
        st.Page("views/02_Inventario.py",       title="Inventario",      icon="🎒"),
        st.Page("views/03_Adicionar_Skin.py",   title="Adicionar Skin",  icon="➕"),
        st.Page("views/05_Rentabilidade.py",    title="Rentabilidade",   icon="📈"),
        st.Page("views/04_Configuracoes.py",    title="Configuracoes",   icon="⚙️"),
    ]
)

st.sidebar.markdown("---")
st.sidebar.caption("🎮 CS2 Skin Tracker · v1.0")

paginas.run()
