"""Página Adicionar Skin — formulário para cadastro de novas skins."""

from __future__ import annotations

import streamlit as st

from app.config import DESGASTES, PLATAFORMAS, TIPOS_ITEM
from app.models import Skin
from app.services.price_service import PriceService
from app.services.storage import adicionar_skin, carregar_dados


def render() -> None:
    """Renderiza o formulário de adição de skin."""
    st.header("➕ Adicionar Skin")

    data = carregar_dados()

    with st.form("form_add_skin", clear_on_submit=True):
        st.subheader("Informações do Item")

        col1, col2 = st.columns(2)

        nome = col1.text_input(
            "Nome do Item *",
            placeholder="Ex: AK-47 | Slate, Sticker | Battle Scarred (Holo)",
        )
        tipo = col2.selectbox("Tipo *", TIPOS_ITEM)

        col3, col4, col5 = st.columns(3)
        desgaste = col3.selectbox("Desgaste", DESGASTES, index=5)
        float_val = col4.number_input("Float Value", min_value=0.0, max_value=1.0, value=0.0, format="%.6f")
        stattrak = col5.selectbox("StatTrak™", ["Não", "Sim", "N/A"])

        col6, col7 = st.columns(2)
        pattern = col6.text_input("Pattern / Seed", placeholder="Ex: 661, N/A")
        market_hash = col7.text_input(
            "Market Hash Name (opcional)",
            placeholder="Nome exato no Steam Market",
            help="Se vazio, será gerado automaticamente a partir do nome e desgaste.",
        )

        st.divider()
        st.subheader("Informações de Compra")

        col8, col9, col10 = st.columns(3)
        plataforma = col8.selectbox("Plataforma de Compra", PLATAFORMAS)
        preco_compra = col9.number_input("Preço de Compra (R$)", min_value=0.0, value=0.0, format="%.2f")
        iof = col10.selectbox("IOF Aplicável?", ["Sim", "Não"], index=0)

        notas = st.text_area("Notas", placeholder="Observações opcionais")

        buscar_preco = st.checkbox("🔍 Buscar preço atual automaticamente após salvar", value=True)

        submitted = st.form_submit_button("💾 Salvar Skin", type="primary", use_container_width=True)

    if submitted:
        if not nome.strip():
            st.error("O nome do item é obrigatório.")
            return

        skin = Skin(
            nome=nome.strip(),
            tipo=tipo,
            desgaste=desgaste,
            float_value=float_val,
            stattrak=stattrak,
            pattern_seed=pattern.strip(),
            plataforma=plataforma,
            preco_compra=preco_compra,
            iof_aplicavel=(iof == "Sim"),
            notas=notas.strip(),
            market_hash_name=market_hash.strip(),
        )

        # Buscar preço antes de salvar
        if buscar_preco:
            with st.spinner("Buscando preço atual..."):
                svc = PriceService(data.config)
                resultado = svc.buscar_preco(skin)

                if resultado.sucesso:
                    skin.preco_atual = resultado.preco
                    st.success(f"Preço encontrado via **{resultado.provider}**: R$ {resultado.preco:.2f}")
                else:
                    st.warning(f"Não foi possível buscar o preço: {resultado.erro}")

        adicionar_skin(skin)
        st.success(f"✅ **{skin.nome}** adicionada com sucesso!")

        total_iof = skin.total_com_iof
        st.info(
            f"Compra: R$ {skin.preco_compra:.2f} → "
            f"c/ IOF: R$ {total_iof:.2f} → "
            f"Atual: R$ {skin.preco_atual:.2f}"
        )

    # Dica de preenchimento
    with st.expander("💡 Dicas de preenchimento", expanded=False):
        st.markdown("""
**Market Hash Name** — é o nome exato que aparece no Steam Community Market.
Se você não preencher, o sistema gera automaticamente baseado no nome + desgaste.

Exemplos:
- `AK-47 | Slate (Factory New)`
- `StatTrak™ Desert Eagle | Corinthian (Minimal Wear)`
- `Sticker | Battle Scarred (Holo)`
- `Charm | Die-cast AK`

**IOF** — marque "Sim" se comprou com cartão de crédito internacional
(a taxa padrão de 6.38%% é aplicada). Pode alterar em **Configurações**.
        """)
