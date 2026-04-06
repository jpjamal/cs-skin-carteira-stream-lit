"""Pagina Configuracoes - gerencia API keys e preferencias."""

from __future__ import annotations

import streamlit as st

from config import PRICE_PROVIDERS
from models import AppData
from services.runtime_state import get_provider_state, load_price_cache
from data_manager import carregar_dados, salvar_dados

st.header("Preferencias")

data = carregar_dados()
cfg = data.config

st.subheader("API Keys")

with st.form("form_api_keys"):
    st.markdown("Configure as chaves e o comportamento seguro de busca de precos.")

    csfloat_key = st.text_input(
        "CSFloat API Key",
        value=cfg.csfloat_api_key,
        type="password",
        help="Obtenha em: https://csfloat.com/developers",
    )

    submitted_keys = st.form_submit_button("Salvar API Keys", type="primary")

if submitted_keys:
    cfg.csfloat_api_key = csfloat_key.strip()
    cfg.steam_enabled = False
    cfg.provider_preferido = "csfloat"
    salvar_dados(data)
    st.success("API Keys salvas com sucesso.")

st.divider()

st.subheader("Taxa IOF")

with st.form("form_iof"):
    iof = st.number_input(
        "IOF (%)",
        min_value=0.0,
        max_value=50.0,
        value=cfg.iof_percentual,
        step=0.01,
        format="%.2f",
        help="Taxa IOF para compras internacionais com cartao.",
    )

    submitted_iof = st.form_submit_button("Salvar IOF")

if submitted_iof:
    cfg.iof_percentual = iof
    salvar_dados(data)
    st.success(f"IOF atualizado para {iof:.2f}%")

st.divider()

st.subheader("Status dos Providers")

col1 = st.columns(1)[0]
with col1:
    st.markdown("**CSFloat**")
    if cfg.csfloat_api_key:
        st.markdown("Configurado")
    else:
        st.markdown("API key nao configurada")
    st.caption("Unica fonte de preco disponivel.")

st.divider()

with st.expander("Como funciona o modo seguro", expanded=False):
    st.markdown(
        """
- O app utiliza exclusivamente a API do CSFloat para busca de precos.
- Precos ficam em cache persistente para evitar chamadas repetidas e rate limit.
- O cambio USD/BRL tambem fica em cache para otimizar velocidade.
        """
    )

st.divider()
st.subheader("Dados")

col_a, col_b = st.columns(2)
with col_a:
    st.metric("Skins cadastradas", len(data.skins))

with col_b:
    total = sum(s.total_com_iof_com_taxa(data.config.iof_percentual) for s in data.skins)
    st.metric("Investimento total", f"R$ {total:,.2f}")

st.caption(f"Entradas no cache persistente: {len(load_price_cache())}")

if "confirmar_limpar" not in st.session_state:
    st.session_state.confirmar_limpar = False

if st.session_state.confirmar_limpar:
    st.warning("Tem certeza? Esta acao e irreversivel.")
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Confirmar exclusao total", type="primary"):
            st.session_state.confirmar_limpar = False
            salvar_dados(AppData(config=cfg))
            st.success("Todos os dados foram removidos.")
            st.rerun()
    with col_cancel:
        if st.button("Cancelar", type="secondary"):
            st.session_state.confirmar_limpar = False
            st.rerun()
else:
    if st.button("Limpar TODOS os dados", type="secondary"):
        st.session_state.confirmar_limpar = True
        st.rerun()
