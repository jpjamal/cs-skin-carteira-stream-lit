"""Pagina Inventario - lista de itens cadastradas com detalhes em dialog."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from config import CATALOG_SNAPSHOT_FILE, PRICE_STALE_AFTER_HOURS
from models import Item, TipoItem
from services.catalog_sync import sync_catalog_snapshot
from services.catalog_service import get_catalog_entry_for_item, hydrate_app_data_from_catalog
from data_manager import carregar_dados, salvar_dados
from services.thumbnail_service import ThumbnailService

THUMBNAIL_SERVICE = ThumbnailService()
DETAIL_IMAGE_WIDTH = 160


def _format_datetime(value: str) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def _thumbnail_path(item: Item) -> str | None:
    image_url = item.imagem_url
    if not image_url:
        entry = get_catalog_entry_for_item(item)
        image_url = entry.get("image", "") if entry else ""
    if not image_url:
        return None
    local_path = THUMBNAIL_SERVICE.get_local_path(image_url)
    return str(local_path) if local_path else None


def _sync_catalog() -> None:
    try:
        result = sync_catalog_snapshot(force_refresh=False)
    except Exception as exc:
        st.error(f"Nao foi possivel sincronizar o catalogo local: {exc}")
        return

    if result.total_current_items == 0:
        st.info("Nao ha itens cadastradas para montar um catalogo local.")
        return

    if result.matched_items == 0:
        st.warning("O catalogo foi sincronizado, mas nenhuma item atual encontrou correspondencia.")
        return

    st.success(
        f"Catalogo sincronizado com sucesso. "
        f"{result.matched_items}/{result.total_current_items} item(s) casadas usando {len(result.source_files)} fonte(s)."
    )
    if result.hydrated_items > 0:
        st.caption(f"{result.hydrated_items} item(s) foram enriquecidas com market hash e miniaturas.")
    elif result.unmatched_items:
        st.caption("As itens restantes continuam operando sem catalogo local, sem bloquear o app.")
    else:
        st.caption("Os dados locais ja estavam alinhados com o catalogo salvo.")


@st.dialog("Detalhes do Item", width="large")
def _dialog_detalhes(item: Item, iof_percentual: float) -> None:
    catalog_entry = get_catalog_entry_for_item(item) or {}

    col_img, col_info = st.columns([1, 2])
    with col_img:
        image_path = _thumbnail_path(item)
        if image_path:
            st.image(image_path, width=DETAIL_IMAGE_WIDTH)
        else:
            st.caption("Sem miniatura")
    with col_info:
        qtd_badge = f" [x{item.quantidade}]" if item.quantidade > 1 else ""
        st.subheader(f"{item.nome}{qtd_badge}")
        st.caption(f"{item.tipo} | {item.desgaste}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Compra Total", f"R$ {item.preco_compra * item.quantidade:.2f}")
        m2.metric("Atual Total", f"R$ {item.preco_atual * item.quantidade:.2f}")
        m3.metric(
            "Lucro",
            f"R$ {item.lucro_com_taxa(iof_percentual):.2f}",
            delta=f"{item.variacao_pct_com_taxa(iof_percentual):+.1%}",
        )

    tab1, tab2 = st.tabs(["Mercado", "Cadastro"])

    with tab1:
        st.write(f"Provider: **{item.preco_provider or '-'}**")
        st.write(f"Metodo: **{item.preco_metodo or '-'}**")
        st.write(f"Amostra: **{item.preco_amostra or '-'}**")
        st.write(f"Atualizado: **{_format_datetime(item.preco_atualizado_em)}**")
        st.write(f"Market Hash Name: **{item.gerar_market_hash_name()}**")
        st.write(f"Raridade: **{catalog_entry.get('rarity', {}).get('name', '-')}**")
        st.write(f"Categoria CS2: **{catalog_entry.get('category', {}).get('name', '-')}**")
        st.write(f"Pintura / Pattern: **{catalog_entry.get('pattern', {}).get('name', '-')}**")

    with tab2:
        st.write(f"Plataforma de compra: **{item.plataforma or '-'}**")
        st.write(f"Float: **{item.float_value:.6f}**")
        st.write(f"StatTrak: **{item.stattrak}**")
        st.write(f"Pattern / Seed: **{item.pattern_seed or '-'}**")
        st.write(f"IOF aplicavel: **{'Sim' if item.iof_aplicavel else 'Nao'}**")
        st.write(f"Criado em: **{_format_datetime(item.criado_em)}**")
        st.write(f"Notas: **{item.notas or '-'}**")
        st.write(f"Nome no catalogo: **{catalog_entry.get('name', '-')}**")
        st.write(f"Arquivo de origem: **{catalog_entry.get('source_file', '-')}**")

    if catalog_entry.get("description"):
        st.caption(catalog_entry["description"])


def _render_lista(itens: list[Item], iof_percentual: float) -> None:
    if not itens:
        st.info("Nenhum item corresponde aos filtros.")
        return

    for item in itens:
        lucro = item.lucro_com_taxa(iof_percentual)
        variacao = item.variacao_pct_com_taxa(iof_percentual)
        with st.container(border=True):
            col_info, col_precos, col_acao = st.columns([2.0, 2.5, 0.7])
            with col_info:
                qtd_badge = f" `x{item.quantidade}`" if item.quantidade > 1 else ""
                st.markdown(f"**{item.nome}**{qtd_badge}")
                st.caption(f"{item.tipo} | {item.desgaste} | Float: {item.float_value:.4f}")
            with col_precos:
                m1, m2, m3 = st.columns(3)
                m1.metric("Compra", f"R$ {item.preco_compra * item.quantidade:.2f}")
                m2.metric("Atual", f"R$ {item.preco_atual * item.quantidade:.2f}")
                m3.metric("Lucro", f"R$ {lucro:.2f}", delta=f"{variacao:+.1%}")
            with col_acao:
                if st.button("Detalhes", key=f"det_{item.id}", use_container_width=True):
                    _dialog_detalhes(item, iof_percentual)


# ── Page ──────────────────────────────────────────────────────────────────

data = carregar_dados()
if hydrate_app_data_from_catalog(data):
    salvar_dados(data)

st.header("Inventario")
st.caption(f"{len(data.itens)} item(ns) cadastrado(s)")

controles_1, controles_2 = st.columns([2.0, 1.0])
busca = controles_1.text_input("Buscar item", placeholder="Nome, tipo, plataforma ou market hash")
apenas_stale = controles_2.toggle("Somente precos antigos", value=False)

acao_1, acao_2 = st.columns([1.3, 2.7])
with acao_1:
    if st.button("Atualizar catalogo local", type="primary", use_container_width=True):
        _sync_catalog()
        data = carregar_dados()
with acao_2:
    if CATALOG_SNAPSHOT_FILE.exists():
        st.caption("Catalogo local sincronizado. Clique em 'Detalhes' para ver miniatura e dados extras.")
    else:
        st.caption("Sem catalogo local. Clique em 'Atualizar catalogo local' para baixar miniaturas e dados extras.")

busca_normalizada = busca.strip().lower()
filtradas = []
for item in data.itens:
    bucket = " ".join(
        [
            item.nome,
            item.tipo,
            item.plataforma,
            item.market_hash_name,
            item.gerar_market_hash_name(),
        ]
    ).lower()
    if busca_normalizada and busca_normalizada not in bucket:
        continue
    if apenas_stale and item.preco_atualizado_em:
        try:
            atualizado = datetime.fromisoformat(item.preco_atualizado_em)
            stale = (datetime.now() - atualizado).total_seconds() >= PRICE_STALE_AFTER_HOURS * 3600
            if not stale:
                continue
        except ValueError:
            pass
    filtradas.append(item)

_render_lista(filtradas, data.config.iof_percentual)
