"""Página Carteira — exibe o portfólio completo de skins."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from app.config import DESGASTES, PLATAFORMAS, PRICE_PROVIDERS, TIPOS_ITEM
from app.models import AppData, Skin
from app.services.price_service import PriceService
from app.services.storage import atualizar_skin, carregar_dados, salvar_dados, remover_skin

PROVIDER_LABELS = {
    "steam": "Steam Market",
    "csfloat": "CSFloat",
}


def _metricas_resumo(skins: list) -> None:
    """Exibe KPIs no topo da página."""
    if not skins:
        st.info("Nenhuma skin cadastrada. Vá em **Adicionar Skin** para começar.")
        return

    total_investido = sum(s.total_com_iof for s in skins)
    valor_atual = sum(s.preco_atual for s in skins)
    lucro_total = valor_atual - total_investido
    variacao = (lucro_total / total_investido * 100) if total_investido > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Itens", len(skins))
    c2.metric("Investido (c/ IOF)", f"R$ {total_investido:,.2f}")
    c3.metric("Valor Atual", f"R$ {valor_atual:,.2f}")
    c4.metric(
        "Lucro / Prejuízo",
        f"R$ {lucro_total:,.2f}",
        delta=f"{variacao:+.1f}%",
    )


def _tabela_skins(skins: list) -> None:
    """Monta a tabela com todas as skins."""
    if not skins:
        return

    rows = []
    for s in skins:
        rows.append({
            "ID": s.id,
            "Nome": s.nome,
            "Tipo": s.tipo,
            "Desgaste": s.desgaste,
            "StatTrak": s.stattrak,
            "Plataforma": s.plataforma,
            "Compra (R$)": s.preco_compra,
            "c/ IOF (R$)": s.total_com_iof,
            "Atual (R$)": s.preco_atual,
            "Lucro (R$)": s.lucro,
            "Variação": s.variacao_pct,
        })

    df = pd.DataFrame(rows)

    def _color_lucro(val):
        if isinstance(val, (int, float)):
            if val < 0:
                return "color: #D32F2F; font-weight: bold"
            if val > 0:
                return "color: #2E7D32; font-weight: bold"
        return ""

    def _color_variacao(val):
        if isinstance(val, (int, float)):
            if val < 0:
                return "color: #D32F2F; font-weight: bold"
            if val > 0:
                return "color: #2E7D32; font-weight: bold"
        return ""

    styled = (
        df.drop(columns=["ID"])
        .style
        .format({
            "Compra (R$)": "R$ {:.2f}",
            "c/ IOF (R$)": "R$ {:.2f}",
            "Atual (R$)": "R$ {:.2f}",
            "Lucro (R$)": "R$ {:.2f}",
            "Variação": "{:.1%}",
        })
        .map(_color_lucro, subset=["Lucro (R$)"])
        .map(_color_variacao, subset=["Variação"])
    )

    st.dataframe(styled, use_container_width=True, hide_index=True, height=600)

    return df


def _atualizar_precos(data: AppData, provider_escolhido: str, considerar_float: bool = False, margem_float: float = 0.01, considerar_pattern: bool = False) -> None:
    """Atualiza preços via API usando o provider escolhido."""
    if not data.skins:
        st.warning("Nenhuma skin para atualizar.")
        return

    # Aplica o provider escolhido na busca
    config_busca = data.config.model_copy(update={"provider_preferido": provider_escolhido})
    svc = PriceService(config_busca, considerar_float=considerar_float, margem_float=margem_float, considerar_pattern=considerar_pattern)
    disponiveis = svc.providers_disponiveis

    if not disponiveis:
        st.error("Nenhum provider de preço disponível. Configure uma API key em **Configurações**.")
        return

    provider_label = provider_escolhido.upper()
    float_msg = " | filtro por float ativado" if considerar_float else ""
    st.info(f"🔍 Buscando preços via **{provider_label}** (com fallback){float_msg}...")

    progress = st.progress(0, text="Iniciando...")
    erros = []

    def on_progress(atual: int, total: int, nome: str) -> None:
        progress.progress(atual / total, text=f"({atual}/{total}) {nome}")

    resultados = svc.buscar_precos_lote(data.skins, on_progress=on_progress)

    atualizados = 0
    for skin in data.skins:
        res = resultados.get(skin.id)
        if res and res.sucesso and res.preco > 0:
            skin.preco_atual = res.preco
            atualizados += 1
        elif res and not res.sucesso:
            erros.append(f"**{skin.nome}**: {res.erro}")

    salvar_dados(data)
    progress.empty()

    if atualizados > 0:
        st.success(f"✅ {atualizados} preço(s) atualizado(s) com sucesso!")

    if erros:
        with st.expander(f"⚠️ {len(erros)} erro(s) na busca", expanded=False):
            for e in erros:
                st.write(f"- {e}")


def _secao_editar(data: AppData) -> None:
    """Seção para editar skins existentes."""
    if not data.skins:
        return

    opcoes = {f"{s.nome} ({s.desgaste}) - R$ {s.preco_compra:.2f}": s.id for s in data.skins}

    with st.expander("✏️ Editar skin", expanded=False):
        escolha = st.selectbox("Selecione a skin para editar:", list(opcoes.keys()), key="edit_select")
        skin_id = opcoes[escolha]
        skin = next(s for s in data.skins if s.id == skin_id)

        with st.form("form_edit_skin"):
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome", value=skin.nome)
            tipo = col2.selectbox("Tipo", TIPOS_ITEM, index=TIPOS_ITEM.index(skin.tipo) if skin.tipo in TIPOS_ITEM else 0)

            col3, col4, col5 = st.columns(3)
            desgaste = col3.selectbox("Desgaste", DESGASTES, index=DESGASTES.index(skin.desgaste) if skin.desgaste in DESGASTES else 0)
            float_val = col4.number_input("Float Value", min_value=0.0, max_value=1.0, value=skin.float_value, format="%.6f")
            stattrak = col5.selectbox("StatTrak™", ["Não", "Sim", "N/A"], index=["Não", "Sim", "N/A"].index(skin.stattrak) if skin.stattrak in ["Não", "Sim", "N/A"] else 0)

            col6, col7 = st.columns(2)
            pattern = col6.text_input("Pattern / Seed", value=skin.pattern_seed)
            market_hash = col7.text_input("Market Hash Name", value=skin.market_hash_name)

            col8, col9, col10 = st.columns(3)
            plataforma = col8.selectbox("Plataforma", PLATAFORMAS, index=PLATAFORMAS.index(skin.plataforma) if skin.plataforma in PLATAFORMAS else 0)
            preco_compra = col9.number_input("Preço de Compra (R$)", min_value=0.0, value=skin.preco_compra, format="%.2f")
            iof = col10.selectbox("IOF Aplicável?", ["Sim", "Não"], index=0 if skin.iof_aplicavel else 1)

            notas = st.text_area("Notas", value=skin.notas)

            submitted = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)

        if submitted:
            skin.nome = nome.strip()
            skin.tipo = tipo
            skin.desgaste = desgaste
            skin.float_value = float_val
            skin.stattrak = stattrak
            skin.pattern_seed = pattern.strip()
            skin.market_hash_name = market_hash.strip()
            skin.plataforma = plataforma
            skin.preco_compra = preco_compra
            skin.iof_aplicavel = (iof == "Sim")
            skin.notas = notas.strip()
            atualizar_skin(skin)
            st.success(f"✅ **{skin.nome}** atualizada com sucesso!")
            st.rerun()


def _secao_remover(data: AppData) -> None:
    """Seção para remover skins."""
    opcoes = {f"{s.nome} ({s.desgaste}) - R$ {s.preco_compra:.2f}": s.id for s in data.skins}
    if not opcoes:
        return

    with st.expander("🗑️ Remover skin", expanded=False):
        escolha = st.selectbox("Selecione a skin para remover:", list(opcoes.keys()), key="remove_select")
        if st.button("Remover", type="secondary"):
            remover_skin(opcoes[escolha])
            st.success(f"Skin '{escolha}' removida!")
            st.rerun()


def render() -> None:
    """Renderiza a página Carteira."""
    st.header("💼 Carteira de Skins")

    data = carregar_dados()

    col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 2, 2])
    with col1:
        provider_escolhido = st.selectbox(
            "Provider de preço",
            options=PRICE_PROVIDERS,
            index=PRICE_PROVIDERS.index(data.config.provider_preferido)
            if data.config.provider_preferido in PRICE_PROVIDERS
            else 0,
            format_func=lambda x: PROVIDER_LABELS.get(x, x),
        )
    with col2:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        considerar_float = st.toggle(
            "Considerar float",
            value=False,
            help="Filtra por faixa de float na busca CSFloat. Steam Market não suporta.",
        )
    with col3:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        considerar_pattern = st.toggle(
            "Considerar pattern",
            value=False,
            help="Filtra por pattern/seed cadastrado na busca CSFloat. Steam Market não suporta.",
        )
    with col4:
        if considerar_float:
            margem_float = st.number_input(
                "Margem float (±)",
                min_value=0.001,
                max_value=0.5,
                value=0.01,
                step=0.005,
                format="%.3f",
                help="Ex: 0.01 busca listings com float entre (seu_float - 0.01) e (seu_float + 0.01)",
            )
        else:
            margem_float = 0.01
    with col5:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar Preços", type="primary", use_container_width=True):
            _atualizar_precos(data, provider_escolhido, considerar_float, margem_float, considerar_pattern)
            data = carregar_dados()

    st.divider()
    _metricas_resumo(data.skins)
    st.divider()

    # Filtros
    if data.skins:
        with st.expander("🔎 Filtros", expanded=False):
            fc1, fc2 = st.columns(2)
            tipos = sorted({s.tipo for s in data.skins})
            tipo_filtro = fc1.multiselect("Tipo", tipos, default=tipos)
            plataformas = sorted({s.plataforma for s in data.skins if s.plataforma})
            plat_filtro = fc2.multiselect("Plataforma", plataformas, default=plataformas)

            filtradas = [
                s for s in data.skins
                if s.tipo in tipo_filtro and s.plataforma in plat_filtro
            ]
        _tabela_skins(filtradas)

    _secao_editar(data)
    _secao_remover(data)
