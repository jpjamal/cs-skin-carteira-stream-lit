"""Pagina Rentabilidade - Dashboard com comparativos de mercado."""

from __future__ import annotations

import datetime
from io import StringIO
import json

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from data_manager import carregar_dados


@st.cache_data(ttl=3600)
def _get_benchmark_data(period: str = "5y") -> dict[str, float]:
    """Retorna o percentual de crescimento no periodo selecionado (ex: '1y', '3y', '5y')."""
    resultados = {"IBOV": 0.0, "IFIX": 0.0, "CDI": 0.0, "Poupanca (Estimada)": 0.0}

    # Calcula as datas
    end_date = datetime.datetime.now()
    years = int(period.replace("y", ""))
    start_date = end_date - datetime.timedelta(days=365 * years)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    start_str_br = start_date.strftime("%d/%m/%Y")
    end_str_br = end_date.strftime("%d/%m/%Y")

    # Ibovespa e IFIX usando yfinance
    try:
        tickers = yf.download(["^BVSP", "IFIX.SA"], start=start_str, end=end_str, progress=False)
        if not tickers.empty and "Close" in tickers:
            df_close = tickers["Close"]
            
            # IBOV
            if "^BVSP" in df_close.columns:
                series_ibov = df_close["^BVSP"].dropna()
                if len(series_ibov) > 0:
                    val_init = series_ibov.iloc[0]
                    val_end = series_ibov.iloc[-1]
                    resultados["IBOV"] = (val_end - val_init) / val_init * 100

            # IFIX
            if "IFIX.SA" in df_close.columns:
                series_ifix = df_close["IFIX.SA"].dropna()
                if len(series_ifix) > 0:
                    val_init = series_ifix.iloc[0]
                    val_end = series_ifix.iloc[-1]
                    resultados["IFIX"] = (val_end - val_init) / val_init * 100
    except Exception as e:
        st.warning(f"Aviso: Nao foi possivel buscar indicadores do Yahoo Finance: {e}")

    # CDI (Serie 12 BCB)
    try:
        url_cdi = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial={start_str_br}&dataFinal={end_str_br}"
        resp_cdi = requests.get(url_cdi, timeout=10)
        if resp_cdi.status_code == 200:
            dados_cdi = resp_cdi.json()
            acumulado = 1.0
            for row in dados_cdi:
                valor = float(row["valor"]) / 100.0  # O valor e em percentual ao dia (0.04% = 0.0004) 
                acumulado *= (1 + valor)
            resultados["CDI"] = (acumulado - 1) * 100
            
            # Poupança conservadora na Nova Regra: geralmente é 70% da Selic se Selic <= 8.5%, ou 0.5% a.m + TR. 
            # A grosso modo no longo prazo rende perto de 70% do CDI, de forma super simplificada para o dashboard:
            resultados["Poupanca (Estimada)"] = resultados["CDI"] * 0.70
    except Exception as e:
        st.warning(f"Aviso: Nao foi possivel buscar dados do Banco Central: {e}")

    return resultados


def _render_rentabilidade_view() -> None:
    st.header("Rentabilidade da Carteira vs Mercado")
    st.markdown("Compare o retorno atual da sua carteira de itens com indicadores financeiros.")

    data = carregar_dados()
    itens = data.itens
    iof_percentual = data.config.iof_percentual

    if not itens:
        st.info("Sua carteira está vazia. Adicione itens para visualizar a rentabilidade.")
        return

    # Calculo da carteira CS
    total_investido = sum(s.total_com_iof_com_taxa(iof_percentual) for s in itens)
    valor_atual = sum(s.preco_atual * s.quantidade for s in itens)
    lucro_total = valor_atual - total_investido
    carteira_pct = (lucro_total / total_investido * 100) if total_investido > 0 else 0.0

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Filtro de Comparação")
        anos = st.radio(
            "Selecione o horizonte de tempo para os benchmarks (Ibovespa, CDI, etc):", 
            options=["1y", "2y", "3y", "5y"], 
            format_func=lambda x: f"Últimos {x.replace('y','')} Ano(s)",
            help="Como o app não tem o histórico temporal exato dos seus itens na plataforma, selecionando um horizonte de tempo você pode comparar a sua 'Rentabilidade Geral Real' contra quanto a bolsa gerou nos últimos N anos."
        )

        st.metric("📦 Retorno da sua Carteira CS2", f"R$ {lucro_total:,.2f}", delta=f"{carteira_pct:+.2f}%", delta_color="normal")
        st.caption("A rentabilidade carteira é a diferença entre os preços de compra (com taxas) e o valor de mercado atual de todos os itens listados juntos.")

    with col2:
        with st.spinner("Carregando indicadores do mercado..."):
            resultados = _get_benchmark_data(period=anos)
        
        # Merge para plotagem
        resultados["Carteira CS2 (Global)"] = carteira_pct

        # Montagem do dataframe grafico
        df = pd.DataFrame(
            list(resultados.items()), 
            columns=["Ativo / Indicador", "Rentabilidade (%)"]
        )
        
        # Define as cores baseado em se e positivo ou negativo ou CS
        def get_color(row):
            if row["Ativo / Indicador"] == "Carteira CS2 (Global)":
                return "#d8b65c" # Dourado CS!
            return "#4ade80" if row["Rentabilidade (%)"] >= 0 else "#f87171"
        
        df["Color"] = df.apply(get_color, axis=1)

        st.subheader(f"Rentabilidade: Carteira vs Benchmark ({anos.replace('y','')} anos)")
        st.bar_chart(
            data=df,
            x="Ativo / Indicador",
            y="Rentabilidade (%)",
            color="Color",
            use_container_width=True
        )

_render_rentabilidade_view()
