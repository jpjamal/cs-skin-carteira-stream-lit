"""Pagina Carteira - exibe o portfolio completo de itens."""

from __future__ import annotations

import streamlit as st

from config import DESGASTES, PLATAFORMAS, PRICE_PROVIDERS, TIPOS_ITEM
from models import Item, TipoItem
from services.catalog_service import hydrate_app_data_from_catalog
from services.price_service import PriceService
from data_manager import adicionar_item, atualizar_item, carregar_dados, exportar_seed, remover_item, salvar_dados

PROVIDER_LABELS = {
    "steam": "Steam Market",
    "csfloat": "CSFloat",
}

def _aplicar_resultado_preco(item: Item, result) -> None:
    if result.sucesso and result.preco > 0:
        item.preco_atual = result.preco
    item.preco_atualizado_em = result.atualizado_em
    if result.imagem_url:
        item.imagem_url = result.imagem_url


def _hero(data) -> None:
    sem_preco = sum(1 for item in data.itens if item.preco_atual <= 0)
    st.header("Resumo da carteira")
    st.caption(f"{len(data.itens)} item(s) | IOF: {data.config.iof_percentual:.2f}% | Sem preco: {sem_preco}")


def _metricas_resumo(itens: list[Item], iof_percentual: float) -> None:
    if not itens:
        st.info("Nenhum item cadastrada. Adicione uma item para comecar.")
        return

    total_investido = sum(s.total_com_iof_com_taxa(iof_percentual) for s in itens)
    valor_atual = sum(s.preco_atual for s in itens)
    lucro_total = valor_atual - total_investido
    variacao = (lucro_total / total_investido * 100) if total_investido > 0 else 0.0
    itens_com_preco = [s for s in itens if s.preco_atual > 0]
    preco_medio = (
        sum(s.preco_atual for s in itens_com_preco) / len(itens_com_preco)
        if itens_com_preco
        else 0.0
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Itens", len(itens))
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
    if not data.itens:
        st.warning("Nenhum item para atualizar.")
        return

    itens_alvo = [i for i in data.itens if i.preco_atual <= 0]
    if not itens_alvo:
        itens_alvo = data.itens

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

    st.info(f"Atualizando {len(itens_alvo)} item(ns)...")
    progress = st.progress(0, text="Iniciando...")
    erros = []

    def on_progress(atual: int, total: int, nome: str) -> None:
        progress.progress(atual / total, text=f"({atual}/{total}) {nome}")

    resultados = svc.buscar_precos_lote(itens_alvo, on_progress=on_progress)

    atualizados = 0
    for item in data.itens:
        result = resultados.get(item.id)
        if result:
            _aplicar_resultado_preco(item, result)
            if result.sucesso and result.preco > 0:
                atualizados += 1
            elif not result.sucesso:
                erros.append(f"**{item.nome}**: {result.erro}")

    salvar_dados(data)
    progress.empty()

    if atualizados > 0:
        st.success(f"{atualizados} preco(s) atualizados com sucesso.")

    if erros:
        with st.expander(f"{len(erros)} erro(s) na busca", expanded=False):
            for erro in erros:
                st.write(f"- {erro}")


# ── Dialogs ──────────────────────────────────────────────────────────


@st.dialog("Adicionar Item", width="large")
def _dialog_adicionar() -> None:
    data = carregar_dados()
    
    # --- Buscador de Itens do Catalogo ---
    with st.expander("🔍 Procurar no Catálogo", expanded=False):
        search_query = st.text_input("Pesquisar item:", key="diag_add_catalog_search")
        if search_query:
            client = ByMykelCatalogClient()
            search_results = client.search_items(search_query)
            if search_results:
                options = {f"{r.get('name')} ({r.get('_source_file', 'catalog').replace('.json', '')})": r for r in search_results}
                selected_label = st.selectbox("Selecione o item oficial:", options.keys(), key="diag_add_sel")
                if selected_label and st.button("Usar este item", key="diag_add_use"):
                    st.session_state["diag_nome_pre"] = options[selected_label].get("name")
                    src = options[selected_label].get("_source_file", "")
                    if "crates" in src: st.session_state["diag_tipo_pre"] = "Caixa"
                    elif "stickers" in src: st.session_state["diag_tipo_pre"] = "Adesivo"
                    elif "agents" in src: st.session_state["diag_tipo_pre"] = "Agente"
                    elif "items_not_grouped" in src:
                        w = options[selected_label].get("name", "").lower()
                        if "gloves" in w or "wraps" in w: st.session_state["diag_tipo_pre"] = "Luva"
                        elif "knife" in w or "bayonet" in w or "karambit" in w or "daggers" in w: st.session_state["diag_tipo_pre"] = "Faca"
                        else: st.session_state["diag_tipo_pre"] = "Arma"
                    st.rerun()

    st.subheader("Informações do Item")


    col1, col2 = st.columns(2)
    def_nome = st.session_state.get("diag_nome_pre", "")
    nome = col1.text_input("Nome do Item *", value=def_nome, placeholder="Ex: AK-47 | Slate", key="add_nome")
    
    def_tipo = st.session_state.get("diag_tipo_pre", TIPOS_ITEM[0])
    try:
        tipo_idx = TIPOS_ITEM.index(def_tipo)
    except:
        tipo_idx = 0
    tipo = col2.selectbox("Tipo *", TIPOS_ITEM, index=tipo_idx, key="add_tipo")

    is_lote = tipo not in [TipoItem.ARMA, TipoItem.FACA, TipoItem.LUVA]

    col3, col4 = st.columns(2)
    if is_lote:
        quantidade = col3.number_input("Quantidade", min_value=1, value=1, step=1, key="add_quantidade")
        desgaste = "N/A"
        float_val = 0.0
        pattern = "N/A"
        stattrak = "N/A"
        col4.selectbox("Desgaste", ["N/A"], index=0, disabled=True, key="add_desgaste_dis")
    else:
        quantidade = 1
        col3.number_input("Quantidade (Fixo em 1 para Armas)", min_value=1, max_value=1, value=1, disabled=True, key="add_quantidade_dis")
        desgaste = col4.selectbox("Desgaste", DESGASTES, index=5, key="add_desgaste")

        c_float, c_pat, c_st = st.columns(3)
        float_val = c_float.number_input("Float Value", min_value=0.0, max_value=1.0, value=0.0, format="%.6f", key="add_float")
        stattrak = c_st.selectbox("StatTrak", ["Não", "Sim", "N/A"], key="add_stattrak")
        pattern = c_pat.text_input("Pattern / Seed", placeholder="Ex: 661", key="add_pattern")

    col7 = st.columns(1)[0]
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
    preco_compra = col9.number_input("Preco de Compra Unitario (R$)", min_value=0.0, value=0.0, format="%.2f", key="add_preco")
    iof = col10.selectbox("IOF Aplicavel?", ["Sim", "Nao"], index=0, key="add_iof")

    notas = st.text_area("Notas", placeholder="Observacoes opcionais", key="add_notas")
    buscar_preco = st.checkbox("Buscar preco atual automaticamente apos salvar", value=True, key="add_buscar")

    col_cancel, col_save = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key="add_cancel"):
            st.rerun()
    with col_save:
        salvar = st.button("Salvar Item", type="primary", use_container_width=True, key="add_salvar")

    if salvar:
        if not nome.strip():
            st.error("O nome do item e obrigatorio.")
            return

        item = Item(
            nome=nome.strip(),
            tipo=tipo,
            desgaste=desgaste,
            float_value=float_val,
            quantidade=quantidade,
            stattrak=stattrak,
            pattern_seed=pattern.strip() if not is_lote else "N/A",
            plataforma=plataforma,
            preco_compra=preco_compra,
            iof_aplicavel=(iof == "Sim"),
            notas=notas.strip(),
            market_hash_name=market_hash.strip(),
        )

        if buscar_preco:
            with st.spinner("Buscando preco atual..."):
                svc = PriceService(data.config)
                resultado = svc.buscar_preco(item)
                if resultado.sucesso:
                    item.preco_atual = resultado.preco
                    item.preco_provider = resultado.provider
                    item.preco_metodo = resultado.metodo
                    item.preco_amostra = resultado.amostra
                    item.preco_confianca = resultado.confianca
                    item.preco_cache_hit = resultado.cache_hit
                    item.preco_stale = resultado.stale
                    item.preco_atualizado_em = resultado.atualizado_em
                    if resultado.imagem_url:
                        item.imagem_url = resultado.imagem_url

        adicionar_item(item)
        st.success(f"**{item.nome}** (Qtd: {item.quantidade}) adicionado com sucesso!")
        st.rerun()


@st.dialog("Editar Item", width="large")
def _dialog_editar(item_id: str) -> None:
    data = carregar_dados()
    item = next((s for s in data.itens if s.id == item_id), None)
    if not item:
        st.error("Item nao encontrado.")
        return

    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome", value=item.nome, key=f"edit_nome_{item_id}")
    tipo = col2.selectbox(
        "Tipo", TIPOS_ITEM,
        index=TIPOS_ITEM.index(item.tipo) if item.tipo in TIPOS_ITEM else 0,
        key=f"edit_tipo_{item_id}",
    )

    is_lote = tipo not in [TipoItem.ARMA, TipoItem.FACA, TipoItem.LUVA]

    col3, col4 = st.columns(2)
    if is_lote:
        quantidade = col3.number_input("Quantidade", min_value=1, value=item.quantidade, step=1, key=f"edit_qtd_{item_id}")
        desgaste = "N/A"
        float_val = 0.0
        pattern = "N/A"
        stattrak = "N/A"
        col4.selectbox("Desgaste", ["N/A"], index=0, disabled=True, key=f"edit_desgaste_dis_{item_id}")
    else:
        quantidade = 1
        col3.number_input("Quantidade (Fixo em 1 para Armas)", min_value=1, max_value=1, value=1, disabled=True, key=f"edit_qtd_dis_{item_id}")
        desgaste = col4.selectbox(
            "Desgaste", DESGASTES,
            index=DESGASTES.index(item.desgaste) if item.desgaste in DESGASTES else 0,
            key=f"edit_desgaste_{item_id}",
        )
        c_float, c_pat, c_st = st.columns(3)
        float_val = c_float.number_input(
            "Float Value", min_value=0.0, max_value=1.0,
            value=item.float_value, format="%.6f",
            key=f"edit_float_{item_id}",
        )
        stattrak = c_st.selectbox(
            "StatTrak", ["Não", "Sim", "N/A"],
            index=["Não", "Sim", "N/A"].index(item.stattrak) if item.stattrak in ["Não", "Sim", "N/A"] else 0,
            key=f"edit_stattrak_{item_id}",
        )
        pattern = c_pat.text_input("Pattern / Seed", value=item.pattern_seed, key=f"edit_pattern_{item_id}")

    col7 = st.columns(1)[0]
    market_hash = col7.text_input("Market Hash Name", value=item.market_hash_name, key=f"edit_hash_{item_id}")

    col8, col9, col10 = st.columns(3)
    plataforma = col8.selectbox(
        "Plataforma", PLATAFORMAS,
        index=PLATAFORMAS.index(item.plataforma) if item.plataforma in PLATAFORMAS else 0,
        key=f"edit_plataforma_{item_id}",
    )
    preco_compra = col9.number_input(
        "Preco de Compra Unitario (R$)", min_value=0.0,
        value=item.preco_compra, format="%.2f",
        key=f"edit_preco_{item_id}",
    )
    iof = col10.selectbox(
        "IOF Aplicavel?", ["Sim", "Nao"],
        index=0 if item.iof_aplicavel else 1,
        key=f"edit_iof_{item_id}",
    )

    notas = st.text_area("Notas", value=item.notas, key=f"edit_notas_{item_id}")

    col_cancel, col_save = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key=f"edit_cancel_{item_id}"):
            st.rerun()
    with col_save:
        salvar = st.button("Salvar Alteracoes", type="primary", use_container_width=True, key=f"edit_salvar_{item_id}")

    if salvar:
        item.nome = nome.strip()
        item.tipo = tipo
        item.desgaste = desgaste
        item.float_value = float_val
        item.quantidade = quantidade
        item.stattrak = stattrak
        item.pattern_seed = pattern.strip() if not is_lote else "N/A"
        item.market_hash_name = market_hash.strip()
        item.plataforma = plataforma
        item.preco_compra = preco_compra
        item.iof_aplicavel = iof == "Sim"
        item.notas = notas.strip()
        atualizar_item(item)
        st.success(f"{item.nome} atualizado com sucesso.")
        st.rerun()


@st.dialog("Confirmar Remocao")
def _dialog_remover(item_id: str, item_nome: str) -> None:
    data = carregar_dados()
    item = next((s for s in data.itens if s.id == item_id), None)
    
    st.warning(f"Tem certeza que deseja remover **{item_nome}**?")
    
    qtd_remover = 1
    if item and item.quantidade > 1:
        st.info(f"Voce possui {item.quantidade} unidades deste item. Quantos deseja remover?")
        qtd_remover = st.number_input("Quantidade a remover", min_value=1, max_value=item.quantidade, value=item.quantidade, step=1)
    else:
        st.caption("Esta acao nao pode ser desfeita.")

    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key=f"rm_cancel_{item_id}"):
            st.rerun()
    with col_confirm:
        if st.button("Remover", type="primary", use_container_width=True, key=f"rm_confirm_{item_id}"):
            remover_item(item_id, qtd_remover)
            st.success(f"**{item_nome}** removido(a)!")
            st.rerun()


# ── Listagem de itens em cards ───────────────────────────────────────


def _render_item_card(item: Item, iof_percentual: float) -> None:
    """Renderiza um card individual para uma item."""
    lucro = item.lucro_com_taxa(iof_percentual)
    variacao = item.variacao_pct_com_taxa(iof_percentual)
    total_iof = item.total_com_iof_com_taxa(iof_percentual)

    cor_lucro = "green" if lucro > 0 else ("red" if lucro < 0 else "gray")

    with st.container(border=True):
        col_nome, col_compra, col_atual, col_lucro, col_acoes = st.columns([3, 1.5, 1.5, 2, 0.8])
        
        with col_nome:
            badges = []
            if item.quantidade > 1:
                badges.append(f"`x{item.quantidade}`")
            if item.tipo:
                badges.append(f"`{item.tipo}`")
            if item.desgaste and item.desgaste != "N/A":
                badges.append(f"`{item.desgaste}`")
            if item.stattrak == "Sim":
                badges.append("`StatTrak™`")
            st.markdown(f"**{item.nome}**  {' '.join(badges)}")
            
            info_parts = []
            if item.float_value > 0: info_parts.append(f"🎯 Float: {item.float_value:.5f}")
            if item.status_preco() != "Ao vivo": info_parts.append(f"⏱️ {item.status_preco()}")
            if item.plataforma: info_parts.append(f"📦 {item.plataforma}")
            if info_parts: st.caption(" · ".join(info_parts))
            
        with col_compra:
            st.metric("Compra", f"R$ {total_iof:,.2f}")
            
        with col_atual:
            total_atual = item.preco_atual * item.quantidade
            st.metric("Atual", f"R$ {total_atual:,.2f}")
            
        with col_lucro:
            st.metric("Lucro", f"R$ {lucro:,.2f}", delta=f"{variacao:+.1%}", delta_color="normal" if lucro != 0 else "off")
            
        with col_acoes:
            if st.button("✏️", key=f"btn_edit_{item.id}", help="Editar item", use_container_width=True, type="primary"):
                _dialog_editar(item.id)
            if st.button("🗑️", key=f"btn_del_{item.id}", help="Remover item", use_container_width=True, type="primary"):
                _dialog_remover(item.id, item.nome)


def _render_listagem(itens: list[Item], iof_percentual: float) -> None:
    """Renderiza a listagem completa de itens com botao de adicionar."""
    if not itens:
        st.info("Nenhum item corresponde aos filtros.")
        return

    for item in itens:
        _render_item_card(item, iof_percentual)


# ── Main ─────────────────────────────────────────────────────────────

# Injeta CSS da Steam na propria pagina para nao sumir com o st.navigation
st.markdown(
    """
    <style>
    button[data-testid="baseButton-primary"],
    div[data-testid="stButton"] button:first-child {
        background-color: #66c0f4 !important;
        border-color: #66c0f4 !important;
        color: #1b2838 !important;
    }
    button[data-testid="baseButton-primary"]:hover,
    div[data-testid="stButton"] button:first-child:hover {
        background-color: #3b9cd9 !important;
        border-color: #3b9cd9 !important;
        color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

data = carregar_dados()
if hydrate_app_data_from_catalog(data):
    salvar_dados(data)

_hero(data)

# Botoes de acao no topo
col_add, col_seed = st.columns([3, 1])
with col_add:
    if st.button("➕ Adicionar Item", type="primary", use_container_width=True, key="btn_adicionar_topo"):
        _dialog_adicionar()
with col_seed:
    if st.button("💾 Salvar Seed", use_container_width=True, key="btn_salvar_seed", help="Exporta os dados atuais para data/seed.json"):
        exportar_seed(data)
        st.toast("Dados exportados para seed.json com sucesso!")

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
if data.itens:
    filtradas = list(data.itens)

    with st.expander("Filtros da carteira", expanded=False):
        busca_termo = st.text_input("Buscar item por nome", placeholder="Ex: AK-47", key="busca_item_nome").strip().lower()
        
        fc1, fc2 = st.columns(2)
        tipos = sorted({s.tipo for s in data.itens})
        tipo_filtro = fc1.multiselect("Tipo", tipos, default=tipos)
        plataformas = sorted({s.plataforma for s in data.itens if s.plataforma})
        plat_filtro = fc2.multiselect("Plataforma", plataformas, default=plataformas)

        filtradas = [
            s
            for s in data.itens
            if s.tipo in tipo_filtro
            and s.plataforma in plat_filtro
            and (not busca_termo or busca_termo in s.nome.lower())
        ]

    st.divider()
    _metricas_resumo(filtradas, data.config.iof_percentual)
    st.divider()
    _render_listagem(filtradas, data.config.iof_percentual)
else:
    st.divider()
    _metricas_resumo(data.itens, data.config.iof_percentual)
