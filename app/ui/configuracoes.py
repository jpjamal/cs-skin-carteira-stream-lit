"""Página Configurações — gerencia API keys e preferências."""

from __future__ import annotations

import streamlit as st

from app.config import PRICE_PROVIDERS
from app.models import ApiConfig
from app.services.storage import carregar_dados, salvar_dados


def render() -> None:
    """Renderiza a página de configurações."""
    st.header("⚙️ Configurações")

    data = carregar_dados()
    cfg = data.config

    # --- API Keys ---
    st.subheader("🔑 API Keys")

    with st.form("form_api_keys"):
        st.markdown("Configure as chaves de API para buscar preços automaticamente.")

        csfloat_key = st.text_input(
            "CSFloat API Key",
            value=cfg.csfloat_api_key,
            type="password",
            help="Obtenha em: https://csfloat.com/developers",
        )

        provider = st.selectbox(
            "Provider preferido para busca de preços",
            options=PRICE_PROVIDERS,
            index=PRICE_PROVIDERS.index(cfg.provider_preferido)
            if cfg.provider_preferido in PRICE_PROVIDERS
            else 0,
            format_func=lambda x: {"steam": "Steam Market (sem API key)", "csfloat": "CSFloat (requer API key)"}[x],
        )

        submitted_keys = st.form_submit_button("💾 Salvar API Keys", type="primary")

    if submitted_keys:
        cfg.csfloat_api_key = csfloat_key.strip()
        cfg.provider_preferido = provider
        salvar_dados(data)
        st.success("✅ API Keys salvas com sucesso!")

    st.divider()

    # --- IOF ---
    st.subheader("💱 Taxa IOF")

    with st.form("form_iof"):
        iof = st.number_input(
            "IOF (%)",
            min_value=0.0,
            max_value=50.0,
            value=cfg.iof_percentual,
            step=0.01,
            format="%.2f",
            help="Taxa IOF para compras internacionais com cartão. Padrão: 6.38%%",
        )

        submitted_iof = st.form_submit_button("💾 Salvar IOF")

    if submitted_iof:
        cfg.iof_percentual = iof
        salvar_dados(data)
        st.success(f"✅ IOF atualizado para {iof:.2f}%")

    st.divider()

    # --- Status ---
    st.subheader("📊 Status dos Providers")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Steam Market**")
        st.markdown("🟢 Disponível (sem API key)")
        st.caption("Rate limit: ~20 req/min")

    with col2:
        st.markdown("**CSFloat**")
        if cfg.csfloat_api_key:
            st.markdown("🟢 Configurado")
        else:
            st.markdown("🔴 API key não configurada")
        st.caption("Rate limit: ~60 req/min")

    st.divider()

    # --- Info ---
    with st.expander("ℹ️ Como obter as API Keys", expanded=False):
        st.markdown("""
### CSFloat
1. Acesse [csfloat.com](https://csfloat.com)
2. Faça login com sua conta Steam
3. Vá em **Settings → Developer**
4. Gere uma nova API key
5. Cole aqui na configuração

### Steam Market
O Steam Market não requer API key. Os preços são buscados
pela API pública do Steam Community Market.
A limitação é o rate limit de ~20 requisições por minuto.

### Provider Preferido
- **Steam Market**: Preços em BRL direto, sem necessidade de key.
  Os valores incluem a taxa de 15%% do Steam.
- **CSFloat**: Preços reais do marketplace, geralmente mais baratos.
  Os valores são convertidos de USD para BRL automaticamente.
        """)

    # --- Dados ---
    st.divider()
    st.subheader("🗂️ Dados")

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Skins cadastradas", len(data.skins))

    with col_b:
        total = sum(s.total_com_iof for s in data.skins)
        st.metric("Investimento total", f"R$ {total:,.2f}")

    if st.button("🗑️ Limpar TODOS os dados", type="secondary"):
        st.warning("⚠️ Tem certeza? Esta ação é irreversível.")
        if st.button("Confirmar exclusão total", type="secondary"):
            from app.models import AppData
            salvar_dados(AppData(config=cfg))
            st.success("Todos os dados foram removidos.")
            st.rerun()
