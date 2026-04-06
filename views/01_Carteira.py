"""Pagina Carteira - exibe o portfolio completo de skins."""

from __future__ import annotations

import streamlit as st

from config import DESGASTES, PLATAFORMAS, PRICE_PROVIDERS, TIPOS_ITEM
from models import Skin
from services.catalog_service import hydrate_app_data_from_catalog
from services.price_service import PriceService
from data_manager import adicionar_skin, atualizar_skin, carregar_dados, remover_skin, salvar_dados

PROVIDER_LABELS = {
    "steam": "Steam Market",
    "csfloat": "CSFloat",
}

def _aplicar_resultado_preco(skin: Skin, result) -> None:
    if result.sucesso and result.preco > 0:
        skin.preco_atual = result.preco
    skin.preco_atualizado_em = result.atualizado_em
    if result.imagem_url:
        skin.imagem_url = result.imagem_url


def _hero(data) -> None:
    sem_preco = sum(1 for skin in data.skins if skin.preco_atual <= 0)
    st.header("Resumo da carteira")
    st.caption(f"{len(data.skins)} skin(s) | IOF: {data.config.iof_percentual:.2f}% | Sem preco: {sem_preco}")


def _metricas_resumo(skins: list[Skin], iof_percentual: float) -> None:
    if not skins:
        st.info("Nenhuma skin cadastrada. Adicione uma skin para comecar.")
        return

    total_investido = sum(s.total_com_iof_com_taxa(iof_percentual) for s in skins)
    valor_atual = sum(s.preco_atual for s in skins)
    lucro_total = valor_atual - total_investido
    variacao = (lucro_total / total_investido * 100) if total_investido > 0 else 0.0
    skins_com_preco = [s for s in skins if s.preco_atual > 0]
    preco_medio = (
        sum(s.preco_atual for s in skins_com_preco) / len(skins_com_preco)
        if skins_com_preco
        else 0.0
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Itens", len(skins))
    c2.metric("Investido", f"R$ {total_investido:,.2f}")
    c3.metric("Valor Atual", f"R$ {valor_atual:,.2f}")
    c4.metric("Lucro / Prejuizo", f"R$ {lucro_total:,.2f}", delta=f"{variacao:+.1f}%")
    c5.metric("Preco Medio", f"R$ {preco_medio:,.2f}")


def _atualizar_precos(
    data,
    provider_escolhido: str,
    considerar_float: bool = False,
    margem_float: float = 0.01,
    considerar_pattern: bool = False,
) -> None:
    if not data.skins:
        st.warning("Nenhuma skin para atualizar.")
        return

    skins_alvo = [s for s in data.skins if s.preco_atual <= 0]
    if not skins_alvo:
        skins_alvo = data.skins

    config_busca = data.config.model_copy(update={"provider_preferido": provider_escolhido})
    svc = PriceService(
        config_busca,
        considerar_float=considerar_float,
        margem_float=margem_float,
        considerar_pattern=considerar_pattern,
    )

    if not svc.providers_disponiveis:
        st.error("Nenhum provider de preco disponivel. Configure uma API key em Configuracoes.")
        return

    st.info(f"Atualizando {len(skins_alvo)} item(ns)...")
    progress = st.progress(0, text="Iniciando...")
    erros = []

    def on_progress(atual: int, total: int, nome: str) -> None:
        progress.progress(atual / total, text=f"({atual}/{total}) {nome}")

    resultados = svc.buscar_precos_lote(skins_alvo, on_progress=on_progress)

    atualizados = 0
    for skin in data.skins:
        result = resultados.get(skin.id)
        if result:
            _aplicar_resultado_preco(skin, result)
            if result.sucesso and result.preco > 0:
                atualizados += 1
            elif not result.sucesso:
                erros.append(f"**{skin.nome}**: {result.erro}")

    salvar_dados(data)
    progress.empty()

    if atualizados > 0:
        st.success(f"{atualizados} preco(s) atualizados com sucesso.")

    if erros:
        with st.expander(f"{len(erros)} erro(s) na busca", expanded=False):
            for erro in erros:
                st.write(f"- {erro}")


# ── Dialogs ──────────────────────────────────────────────────────────


@st.dialog("Adicionar Skin", width="large")
def _dialog_adicionar() -> None:
    data = carregar_dados()
    st.subheader("Informacoes do Item")

    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome do Item *", placeholder="Ex: AK-47 | Slate", key="add_nome")
    tipo = col2.selectbox("Tipo *", TIPOS_ITEM, key="add_tipo")

    col3, col4, col5 = st.columns(3)
    desgaste = col3.selectbox("Desgaste", DESGASTES, index=5, key="add_desgaste")
    float_val = col4.number_input("Float Value", min_value=0.0, max_value=1.0, value=0.0, format="%.6f", key="add_float")
    stattrak = col5.selectbox("StatTrak", ["Nao", "Sim", "N/A"], key="add_stattrak")

    col6, col7 = st.columns(2)
    pattern = col6.text_input("Pattern / Seed", placeholder="Ex: 661, N/A", key="add_pattern")
    market_hash = col7.text_input(
        "Market Hash Name (opcional)",
        placeholder="Nome exato no marketplace",
        help="Se vazio, sera gerado automaticamente a partir do nome e desgaste.",
        key="add_market_hash",
    )

    st.divider()
    st.subheader("Informacoes de Compra")

    col8, col9, col10 = st.columns(3)
    plataforma = col8.selectbox("Plataforma de Compra", PLATAFORMAS, key="add_plataforma")
    preco_compra = col9.number_input("Preco de Compra (R$)", min_value=0.0, value=0.0, format="%.2f", key="add_preco")
    iof = col10.selectbox("IOF Aplicavel?", ["Sim", "Nao"], index=0, key="add_iof")

    notas = st.text_area("Notas", placeholder="Observacoes opcionais", key="add_notas")
    buscar_preco = st.checkbox("Buscar preco atual automaticamente apos salvar", value=True, key="add_buscar")

    col_cancel, col_save = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key="add_cancel"):
            st.rerun()
    with col_save:
        salvar = st.button("Salvar Skin", type="primary", use_container_width=True, key="add_salvar")

    if salvar:
        if not nome.strip():
            st.error("O nome do item e obrigatorio.")
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

        if buscar_preco:
            with st.spinner("Buscando preco atual..."):
                svc = PriceService(data.config)
                resultado = svc.buscar_preco(skin)
                if resultado.sucesso:
                    skin.preco_atual = resultado.preco
                    skin.preco_provider = resultado.provider
                    skin.preco_metodo = resultado.metodo
                    skin.preco_amostra = resultado.amostra
                    skin.preco_confianca = resultado.confianca
                    skin.preco_cache_hit = resultado.cache_hit
                    skin.preco_stale = resultado.stale
                    skin.preco_atualizado_em = resultado.atualizado_em
                    if resultado.imagem_url:
                        skin.imagem_url = resultado.imagem_url

        adicionar_skin(skin)
        st.success(f"**{skin.nome}** adicionada com sucesso!")
        st.rerun()


@st.dialog("Editar Skin", width="large")
def _dialog_editar(skin_id: str) -> None:
    data = carregar_dados()
    skin = next((s for s in data.skins if s.id == skin_id), None)
    if not skin:
        st.error("Skin nao encontrada.")
        return

    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome", value=skin.nome, key=f"edit_nome_{skin_id}")
    tipo = col2.selectbox(
        "Tipo", TIPOS_ITEM,
        index=TIPOS_ITEM.index(skin.tipo) if skin.tipo in TIPOS_ITEM else 0,
        key=f"edit_tipo_{skin_id}",
    )

    col3, col4, col5 = st.columns(3)
    desgaste = col3.selectbox(
        "Desgaste", DESGASTES,
        index=DESGASTES.index(skin.desgaste) if skin.desgaste in DESGASTES else 0,
        key=f"edit_desgaste_{skin_id}",
    )
    float_val = col4.number_input(
        "Float Value", min_value=0.0, max_value=1.0,
        value=skin.float_value, format="%.6f",
        key=f"edit_float_{skin_id}",
    )
    stattrak = col5.selectbox(
        "StatTrak", ["Nao", "Sim", "N/A"],
        index=["Nao", "Sim", "N/A"].index(skin.stattrak) if skin.stattrak in ["Nao", "Sim", "N/A"] else 0,
        key=f"edit_stattrak_{skin_id}",
    )

    col6, col7 = st.columns(2)
    pattern = col6.text_input("Pattern / Seed", value=skin.pattern_seed, key=f"edit_pattern_{skin_id}")
    market_hash = col7.text_input("Market Hash Name", value=skin.market_hash_name, key=f"edit_hash_{skin_id}")

    col8, col9, col10 = st.columns(3)
    plataforma = col8.selectbox(
        "Plataforma", PLATAFORMAS,
        index=PLATAFORMAS.index(skin.plataforma) if skin.plataforma in PLATAFORMAS else 0,
        key=f"edit_plataforma_{skin_id}",
    )
    preco_compra = col9.number_input(
        "Preco de Compra (R$)", min_value=0.0,
        value=skin.preco_compra, format="%.2f",
        key=f"edit_preco_{skin_id}",
    )
    iof = col10.selectbox(
        "IOF Aplicavel?", ["Sim", "Nao"],
        index=0 if skin.iof_aplicavel else 1,
        key=f"edit_iof_{skin_id}",
    )

    notas = st.text_area("Notas", value=skin.notas, key=f"edit_notas_{skin_id}")

    col_cancel, col_save = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key=f"edit_cancel_{skin_id}"):
            st.rerun()
    with col_save:
        salvar = st.button("Salvar Alteracoes", type="primary", use_container_width=True, key=f"edit_salvar_{skin_id}")

    if salvar:
        skin.nome = nome.strip()
        skin.tipo = tipo
        skin.desgaste = desgaste
        skin.float_value = float_val
        skin.stattrak = stattrak
        skin.pattern_seed = pattern.strip()
        skin.market_hash_name = market_hash.strip()
        skin.plataforma = plataforma
        skin.preco_compra = preco_compra
        skin.iof_aplicavel = iof == "Sim"
        skin.notas = notas.strip()
        atualizar_skin(skin)
        st.success(f"{skin.nome} atualizada com sucesso.")
        st.rerun()


@st.dialog("Confirmar Remocao")
def _dialog_remover(skin_id: str, skin_nome: str) -> None:
    st.warning(f"Tem certeza que deseja remover **{skin_nome}**?")
    st.caption("Esta acao nao pode ser desfeita.")

    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key=f"rm_cancel_{skin_id}"):
            st.rerun()
    with col_confirm:
        if st.button("Remover", type="primary", use_container_width=True, key=f"rm_confirm_{skin_id}"):
            remover_skin(skin_id)
            st.success(f"**{skin_nome}** removida!")
            st.rerun()


# ── Listagem de skins em cards ───────────────────────────────────────


def _render_skin_card(skin: Skin, iof_percentual: float) -> None:
    """Renderiza um card individual para uma skin."""
    lucro = skin.lucro_com_taxa(iof_percentual)
    variacao = skin.variacao_pct_com_taxa(iof_percentual)
    total_iof = skin.total_com_iof_com_taxa(iof_percentual)

    cor_lucro = "green" if lucro > 0 else ("red" if lucro < 0 else "gray")

    with st.container(border=True):
        col_nome, col_compra, col_atual, col_lucro, col_acoes = st.columns([3, 1.5, 1.5, 2, 0.8])
        
        with col_nome:
            badges = []
            if skin.tipo:
                badges.append(f"`{skin.tipo}`")
            if skin.desgaste and skin.desgaste != "N/A":
                badges.append(f"`{skin.desgaste}`")
            if skin.stattrak == "Sim":
                badges.append("`StatTrak™`")
            st.markdown(f"**{skin.nome}**  {' '.join(badges)}")
            
            info_parts = []
            if skin.float_value > 0: info_parts.append(f"🎯 Float: {skin.float_value:.5f}")
            if skin.status_preco() != "Ao vivo": info_parts.append(f"⏱️ {skin.status_preco()}")
            if skin.plataforma: info_parts.append(f"📦 {skin.plataforma}")
            if info_parts: st.caption(" · ".join(info_parts))
            
        with col_compra:
            st.metric("Compra", f"R$ {total_iof:,.2f}")
            
        with col_atual:
            st.metric("Atual", f"R$ {skin.preco_atual:,.2f}")
            
        with col_lucro:
            st.metric("Lucro", f"R$ {lucro:,.2f}", delta=f"{variacao:+.1%}", delta_color="normal" if lucro != 0 else "off")
            
        with col_acoes:
            if st.button("✏️", key=f"btn_edit_{skin.id}", help="Editar skin", use_container_width=True, type="primary"):
                _dialog_editar(skin.id)
            if st.button("🗑️", key=f"btn_del_{skin.id}", help="Remover skin", use_container_width=True, type="primary"):
                _dialog_remover(skin.id, skin.nome)


def _render_listagem(skins: list[Skin], iof_percentual: float) -> None:
    """Renderiza a listagem completa de skins com botao de adicionar."""
    if not skins:
        st.info("Nenhuma skin corresponde aos filtros.")
        return

    for skin in skins:
        _render_skin_card(skin, iof_percentual)


# ── Main ─────────────────────────────────────────────────────────────

data = carregar_dados()
if hydrate_app_data_from_catalog(data):
    salvar_dados(data)

_hero(data)

# Botao de adicionar no topo
if st.button("➕ Adicionar Skin", type="primary", use_container_width=True, key="btn_adicionar_topo"):
    _dialog_adicionar()

st.divider()

# Controles de atualizacao de precos
row1_col1, row1_col2, row1_col3 = st.columns([1.8, 1.2, 1.2])
with row1_col1:
    provider_escolhido = st.selectbox(
        "Fonte principal de preco",
        options=PRICE_PROVIDERS,
        index=PRICE_PROVIDERS.index(data.config.provider_preferido)
        if data.config.provider_preferido in PRICE_PROVIDERS
        else 0,
        format_func=lambda x: PROVIDER_LABELS.get(x, x),
    )
with row1_col2:
    considerar_float = st.toggle("Considerar float", value=False)
with row1_col3:
    considerar_pattern = st.toggle("Considerar pattern", value=False)

row2_col1, row2_col2 = st.columns([1.8, 1.2])
with row2_col1:
    margem_float = (
        st.number_input("Margem float", min_value=0.001, max_value=0.5, value=0.01, step=0.005, format="%.3f")
        if considerar_float
        else 0.01
    )
with row2_col2:
    if st.button("Atualizar valores", type="primary", use_container_width=True):
        _atualizar_precos(data, provider_escolhido, considerar_float, margem_float, considerar_pattern)
        data = carregar_dados()

# Filtros e listagem
if data.skins:
    filtradas = list(data.skins)

    with st.expander("Filtros da carteira", expanded=False):
        fc1, fc2 = st.columns(2)
        tipos = sorted({s.tipo for s in data.skins})
        tipo_filtro = fc1.multiselect("Tipo", tipos, default=tipos)
        plataformas = sorted({s.plataforma for s in data.skins if s.plataforma})
        plat_filtro = fc2.multiselect("Plataforma", plataformas, default=plataformas)

        filtradas = [
            s
            for s in data.skins
            if s.tipo in tipo_filtro
            and s.plataforma in plat_filtro
        ]

    st.divider()
    _metricas_resumo(filtradas, data.config.iof_percentual)
    st.divider()
    _render_listagem(filtradas, data.config.iof_percentual)
else:
    st.divider()
    _metricas_resumo(data.skins, data.config.iof_percentual)
