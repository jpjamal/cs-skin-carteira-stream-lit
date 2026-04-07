"""Pagina Adicionar Item - formulario para cadastro de novos itens."""

from __future__ import annotations

import streamlit as st

from config import DESGASTES, PLATAFORMAS, TIPOS_ITEM
from models import Item, TipoItem
from services.price_service import PriceService
from services.bymykel_catalog import ByMykelCatalogClient
from data_manager import adicionar_item, carregar_dados

st.header("Adicionar Item")

data = carregar_dados()

# --- Buscador de Itens do Catalogo ---
with st.expander("🔍 Não sabe o nome exato? Procure no Catálogo", expanded=False):
    st.markdown("Pesquise por parte do nome (ex: 'Fever', 'Kilowatt', 'Glove') para encontrar o nome oficial do Steam.")
    search_query = st.text_input("Pesquisar item:", key="catalog_search_query")
    
    if search_query:
        client = ByMykelCatalogClient()
        search_results = client.search_items(search_query)
        
        if search_results:
            options = {f"{r.get('name')} ({r.get('_source_file').replace('.json', '')})": r for r in search_results}
            selected_label = st.selectbox("Selecione o item oficial:", options.keys())
            
            if selected_label:
                selected_item = options[selected_label]
                if st.button("Usar este item"):
                    st.session_state["nome_preenchido"] = selected_item.get("name")
                    # Mapeamento de tipo baseado no arquivo fonte
                    src = selected_item.get("_source_file")
                    if "crates" in src: st.session_state["tipo_preenchido"] = "Caixa"
                    elif "stickers" in src: st.session_state["tipo_preenchido"] = "Adesivo"
                    elif "agents" in src: st.session_state["tipo_preenchido"] = "Agente"
                    elif "items_not_grouped" in src:
                        # Inferir se e arma, faca ou luva pela imagem ou nome
                        w = selected_item.get("name", "").lower()
                        if "gloves" in w or "wraps" in w: st.session_state["tipo_preenchido"] = "Luva"
                        elif "knife" in w or "bayonet" in w or "karambit" in w or "daggers" in w: st.session_state["tipo_preenchido"] = "Faca"
                        else: st.session_state["tipo_preenchido"] = "Arma"
                    st.rerun()
        else:
            st.warning("Nenhum item encontrado com esse termo.")

# --- Formulario ---
st.divider()


st.subheader("Informações do Item")

col1, col2 = st.columns(2)
def_nome = st.session_state.get("nome_preenchido", "")
nome = col1.text_input("Nome do Item *", value=def_nome, placeholder="Ex: AK-47 | Slate")

def_tipo = st.session_state.get("tipo_preenchido", TIPOS_ITEM[0])
try:
    tipo_idx = TIPOS_ITEM.index(def_tipo)
except:
    tipo_idx = 0

tipo = col2.selectbox("Tipo *", TIPOS_ITEM, index=tipo_idx)

is_lote = tipo not in [TipoItem.ARMA, TipoItem.FACA, TipoItem.LUVA]

col3, col4 = st.columns(2)
if is_lote:
    quantidade = col3.number_input("Quantidade", min_value=1, value=1, step=1)
    desgaste = col4.selectbox("Desgaste", ["N/A"], index=0, disabled=True)
    float_val = 0.0
    pattern = "N/A"
    stattrak = "N/A"
else:
    quantidade = col3.number_input("Quantidade (Fixo em 1 para Armas)", min_value=1, max_value=1, value=1, disabled=True)
    desgaste = col4.selectbox("Desgaste", DESGASTES, index=5)
    
    c_float, c_pat, c_st = st.columns(3)
    float_val = c_float.number_input("Float Value", min_value=0.0, max_value=1.0, value=0.0, format="%.6f")
    stattrak = c_st.selectbox("StatTrak", ["Não", "Sim", "N/A"])
    pattern = c_pat.text_input("Pattern / Seed", placeholder="Ex: 661")

col7 = st.columns(1)[0]
market_hash = col7.text_input(
    "Market Hash Name (opcional)",
    placeholder="Nome exato no marketplace",
    help="Se vazio, será gerado automaticamente a partir do nome e desgaste.",
)

st.divider()
st.subheader("Informações de Compra")

col8, col9, col10 = st.columns(3)
plataforma = col8.selectbox("Plataforma de Compra", PLATAFORMAS)
preco_unit = col9.number_input("Preço de Compra Unitário (R$)", min_value=0.0, value=0.0, format="%.2f")
iof = col10.selectbox("IOF Aplicável?", ["Sim", "Não"], index=0)

notas = st.text_area("Notas", placeholder="Observações opcionais")
buscar_preco = st.checkbox("Buscar preço atual unitário após salvar", value=True)

if st.button("Salvar Item", type="primary", use_container_width=True):
    if not nome.strip():
        st.error("O nome do item é obrigatório.")
    else:
        item = Item(
            nome=nome.strip(),
            tipo=tipo,
            desgaste=desgaste,
            float_value=float_val,
            quantidade=quantidade,
            stattrak=stattrak,
            pattern_seed=pattern.strip() if not is_lote else "N/A",
            plataforma=plataforma,
            preco_compra=preco_unit,
            iof_aplicavel=(iof == "Sim"),
            notas=notas.strip(),
            market_hash_name=market_hash.strip(),
        )

        if buscar_preco:
            with st.spinner("Buscando preço atual unitário..."):
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

                    st.success(f"Preço encontrado via **{resultado.provider}**: R$ {resultado.preco:.2f}")
                else:
                    st.warning(f"Não foi possível buscar o preço: {resultado.erro}")

        adicionar_item(item)
        st.success(f"**{item.nome}** (Qtd: {item.quantidade}) salvo com sucesso!")
        st.balloons()

with st.expander("Dicas de preenchimento", expanded=False):
    st.markdown(
        """
**Market Hash Name** e o nome exato do item no marketplace.
Se voce nao preencher, o sistema gera automaticamente baseado no nome e desgaste.

**Pattern / Seed** faz mais diferenca em items especiais. Em itens comuns, o app tende a confiar mais no float e nos comparaveis de mercado.

**IOF** pode ser alterado em Configuracoes e a exibicao da carteira usa o valor configurado.
        """
    )
