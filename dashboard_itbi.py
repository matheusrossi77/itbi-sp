"""
Dashboard ITBI São Paulo — consulta interativa.
Usa Turso (cloud) quando TURSO_URL está em st.secrets, caso contrário SQLite local.
"""
import sqlite3
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# ── Configuração de conexão ───────────────────────────────────────────────────

_LOCAL_DB = Path(r"C:\Users\mathe\itbi_sp\itbi_sp.db")
_USE_TURSO = "TURSO_URL" in st.secrets

st.set_page_config(
    page_title="Consulta de transações - Imóveis São Paulo",
    page_icon="🏠",
    layout="wide",
)

# ── Camada de acesso a dados ──────────────────────────────────────────────────

@st.cache_resource
def _sqlite_conn():
    return sqlite3.connect(str(_LOCAL_DB), check_same_thread=False)


def _run_sql(sql: str, params: list = []) -> pd.DataFrame:
    """Executa SQL e retorna DataFrame — Turso (cloud) ou SQLite (local)."""
    if _USE_TURSO:
        url = st.secrets["TURSO_URL"]
        token = st.secrets["TURSO_TOKEN"]

        args = []
        for p in params:
            if p is None:
                args.append({"type": "null", "value": None})
            elif isinstance(p, bool):
                args.append({"type": "integer", "value": "1" if p else "0"})
            elif isinstance(p, int):
                args.append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                args.append({"type": "float", "value": p})
            else:
                args.append({"type": "text", "value": str(p)})

        resp = requests.post(
            f"{url}/v2/pipeline",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"requests": [{"type": "execute", "stmt": {"sql": sql, "args": args}}]},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()["results"][0]["response"]["result"]
        cols = [c["name"] for c in result["cols"]]
        rows = [[v.get("value") for v in row] for row in result["rows"]]
        return pd.DataFrame(rows, columns=cols)
    else:
        conn = _sqlite_conn()
        return pd.read_sql_query(sql, conn, params=params)


def _scalar(sql: str, params: list = []):
    df = _run_sql(sql, params)
    return df.iloc[0, 0] if not df.empty else None


# ── Funções de consulta ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_distinct(col: str) -> list:
    df = _run_sql(
        f"SELECT DISTINCT {col} FROM itbi_transacoes "
        f"WHERE {col} IS NOT NULL AND TRIM({col}) != '' AND {col} != 'nan' "
        f"ORDER BY {col}"
    )
    return df.iloc[:, 0].tolist() if not df.empty else []


@st.cache_data(ttl=3600)
def db_overview() -> dict:
    total = int(_scalar("SELECT COUNT(*) FROM itbi_transacoes") or 0)
    anos_df = _run_sql("SELECT MIN(ano_referencia), MAX(ano_referencia) FROM itbi_transacoes")
    by_year = _run_sql(
        "SELECT ano_referencia, COUNT(*) as total FROM itbi_transacoes "
        "GROUP BY ano_referencia ORDER BY ano_referencia"
    )
    by_year["ano_referencia"] = pd.to_numeric(by_year["ano_referencia"])
    by_year["total"] = pd.to_numeric(by_year["total"])
    return {
        "total": total,
        "ano_min": anos_df.iloc[0, 0],
        "ano_max": anos_df.iloc[0, 1],
        "by_year": by_year,
    }


def build_where(f: dict) -> tuple[str, list]:
    clauses, params = [], []

    if f.get("anos"):
        ph = ",".join("?" * len(f["anos"]))
        clauses.append(f"ano_referencia IN ({ph})")
        params.extend(f["anos"])

    if f.get("data_pag_ini"):
        clauses.append("data_pagamento >= ?")
        params.append(str(f["data_pag_ini"]))

    if f.get("data_pag_fim"):
        clauses.append("data_pagamento <= ?")
        params.append(str(f["data_pag_fim"]))

    if f.get("natureza"):
        ph = ",".join("?" * len(f["natureza"]))
        clauses.append(f"natureza_transacao IN ({ph})")
        params.extend(f["natureza"])

    if f.get("tipo_imovel"):
        ph = ",".join("?" * len(f["tipo_imovel"]))
        clauses.append(f"tipo_imovel IN ({ph})")
        params.extend(f["tipo_imovel"])

    if f.get("subdistrito"):
        ph = ",".join("?" * len(f["subdistrito"]))
        clauses.append(f"subdistrito IN ({ph})")
        params.extend(f["subdistrito"])

    if f.get("bairro"):
        ph = ",".join("?" * len(f["bairro"]))
        clauses.append(f"bairro IN ({ph})")
        params.extend(f["bairro"])

    if f.get("logradouro"):
        clauses.append("nome_do_logradouro LIKE ?")
        params.append(f"%{f['logradouro'].upper()}%")

    if f.get("numero_endereco"):
        clauses.append("numero_endereco = ?")
        params.append(f["numero_endereco"])

    if f.get("cep"):
        cep_digits = f["cep"].replace("-", "").strip()
        clauses.append("CAST(cep_imovel AS INTEGER) = CAST(? AS INTEGER)")
        params.append(cep_digits)

    if f.get("valor_min"):
        clauses.append("valor_transacao >= ?")
        params.append(f["valor_min"])

    if f.get("valor_max"):
        clauses.append("valor_transacao <= ?")
        params.append(f["valor_max"])

    if f.get("area_min"):
        clauses.append("area_construida >= ?")
        params.append(f["area_min"])

    if f.get("area_max"):
        clauses.append("area_construida <= ?")
        params.append(f["area_max"])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def query_agg(where: str, params: list) -> dict:
    df = _run_sql(
        f"SELECT COUNT(*), SUM(valor_transacao), AVG(valor_transacao), AVG(area_construida) "
        f"FROM itbi_transacoes {where}",
        params,
    )
    row = df.iloc[0]
    return {
        "total": int(row.iloc[0] or 0),
        "soma": float(row.iloc[1] or 0),
        "media": float(row.iloc[2] or 0),
        "area_media": float(row.iloc[3] or 0),
    }


def query_data(where: str, params: list, limit: int = 50_000) -> pd.DataFrame:
    df = _run_sql(
        f"""
        SELECT
            ano_referencia, data_pagamento, data_transacao,
            natureza_transacao, tipo_imovel, subdistrito, bairro,
            nome_do_logradouro, numero_endereco, complemento, cep_imovel,
            valor_transacao, valor_venal_referencia, base_calculo, referencia,
            valor_imposto, valor_financiado, tipo_financiamento,
            area_terreno, area_construida, fracao_ideal,
            no_do_cadastro_sql, numero_guia
        FROM itbi_transacoes
        {where}
        ORDER BY data_pagamento DESC
        LIMIT {limit}
        """,
        params,
    )
    num_cols = [
        "valor_transacao", "valor_venal_referencia", "base_calculo",
        "valor_imposto", "valor_financiado", "area_terreno",
        "area_construida", "fracao_ideal", "ano_referencia",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Layout ────────────────────────────────────────────────────────────────────

st.title("🏠 Consulta de transações - Imóveis São Paulo")
st.caption("Fonte: Prefeitura de SP")

if not _USE_TURSO and not _LOCAL_DB.exists():
    st.error(f"Banco não encontrado em `{_LOCAL_DB}`.\nExecute `download_itbi.py` primeiro.")
    st.stop()

ov = db_overview()

col_ov1, col_ov2, col_ov3 = st.columns(3)
col_ov1.metric("Total de registros no banco", f"{ov['total']:,.0f}")
col_ov2.metric("Ano mais antigo", ov["ano_min"])
col_ov3.metric("Ano mais recente", ov["ano_max"])

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("🔎 Filtros")

    anos = st.multiselect("Ano de referência", options=load_distinct("ano_referencia"))

    st.markdown("**Período de pagamento**")
    col_a, col_b = st.columns(2)
    with col_a:
        dpag_ini = st.date_input("De", value=None, key="dpag_ini")
    with col_b:
        dpag_fim = st.date_input("Até", value=None, key="dpag_fim")

    natureza = st.multiselect("Natureza da transação", options=load_distinct("natureza_transacao"))
    tipo_imovel = st.multiselect("Tipo de imóvel", options=load_distinct("tipo_imovel"))
    subdistrito = st.multiselect("Subdistrito", options=load_distinct("subdistrito"))
    bairro = st.multiselect("Bairro", options=load_distinct("bairro"))

    logradouro = st.text_input("Logradouro (busca parcial)")
    numero_endereco = st.text_input("Número do logradouro")
    cep = st.text_input("CEP do imóvel")

    st.markdown("**Valor da transação (R$)**")
    col_c, col_d = st.columns(2)
    with col_c:
        valor_min = st.number_input("Mín.", min_value=0.0, value=0.0, step=50_000.0, format="%.0f")
    with col_d:
        valor_max = st.number_input("Máx.", min_value=0.0, value=0.0, step=50_000.0, format="%.0f",
                                    help="0 = sem limite superior")

    st.markdown("**Área construída (m²)**")
    col_e, col_f = st.columns(2)
    with col_e:
        area_min = st.number_input("Mín.", min_value=0.0, value=0.0, step=10.0, format="%.0f", key="area_min")
    with col_f:
        area_max = st.number_input("Máx.", min_value=0.0, value=0.0, step=10.0, format="%.0f", key="area_max",
                                   help="0 = sem limite superior")

    buscar = st.button("🔍 Buscar", type="primary", use_container_width=True)

# ── Query ─────────────────────────────────────────────────────────────────────

filters = {
    "anos": anos or None,
    "data_pag_ini": dpag_ini,
    "data_pag_fim": dpag_fim,
    "natureza": natureza or None,
    "tipo_imovel": tipo_imovel or None,
    "subdistrito": subdistrito or None,
    "bairro": bairro or None,
    "logradouro": logradouro.strip() or None,
    "numero_endereco": numero_endereco.strip() or None,
    "cep": cep.strip() or None,
    "valor_min": valor_min if valor_min > 0 else None,
    "valor_max": valor_max if valor_max > 0 else None,
    "area_min": area_min if area_min > 0 else None,
    "area_max": area_max if area_max > 0 else None,
}

if buscar:
    where, params = build_where(filters)
    with st.spinner("Consultando banco de dados..."):
        st.session_state["agg"] = query_agg(where, params)
        st.session_state["df"] = query_data(where, params)
    st.session_state["searched"] = True

if not st.session_state.get("searched"):
    st.info("Configure os filtros na barra lateral e clique em **🔍 Buscar** para consultar.")
    st.subheader("Distribuição de registros por ano (banco completo)")
    st.bar_chart(ov["by_year"].set_index("ano_referencia")["total"])
    st.stop()

agg: dict = st.session_state["agg"]
df: pd.DataFrame = st.session_state["df"]

# ── KPIs ──────────────────────────────────────────────────────────────────────

k1, k2, k3, k4 = st.columns(4)
k1.metric("Registros encontrados", f"{agg['total']:,.0f}")
k2.metric("Soma das transações", f"R$ {agg['soma']:,.0f}")
k3.metric("Valor médio", f"R$ {agg['media']:,.0f}")
k4.metric("Área média construída", f"{agg['area_media']:,.1f} m²")

if df.empty:
    st.warning("Nenhum registro encontrado com os filtros aplicados.")
    st.stop()

if len(df) >= 50_000:
    st.warning(
        "⚠️ Exibindo os **50.000 registros mais recentes**. "
        "Os agregados acima refletem o total real. Refine os filtros para ver todos os dados."
    )

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_graf, tab_tab = st.tabs(["📊 Gráficos", "📋 Tabela"])

with tab_graf:
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.subheader("Quantidade por ano")
        st.bar_chart(df.groupby("ano_referencia").size().rename("registros"))
    with r1c2:
        st.subheader("Natureza da transação")
        st.bar_chart(df["natureza_transacao"].value_counts().head(10).rename("registros"))

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.subheader("Top 10 bairros (quantidade)")
        st.bar_chart(df["bairro"].value_counts().head(10).rename("registros"))
    with r2c2:
        st.subheader("Valor médio por ano (R$)")
        st.bar_chart(df.groupby("ano_referencia")["valor_transacao"].mean().rename("valor_medio"))

with tab_tab:
    col_names = {
        "data_transacao": "Dt. Transação",
        "natureza_transacao": "Natureza",
        "bairro": "Bairro",
        "nome_do_logradouro": "Logradouro",
        "numero_endereco": "Nº",
        "complemento": "Complemento",
        "cep_imovel": "CEP",
        "referencia": "Referência",
        "valor_transacao": "Valor Transação (R$)",
        "valor_venal_referencia": "Valor Venal (R$)",
        "valor_financiado": "Valor Financiado (R$)",
        "tipo_financiamento": "Tipo Financiamento",
    }

    df_show = df[[c for c in col_names if c in df.columns]].rename(columns=col_names)

    for col in ["Valor Transação (R$)", "Valor Venal (R$)", "Valor Financiado (R$)"]:
        if col in df_show.columns:
            df_show[col] = df_show[col].apply(
                lambda x: f"R$ {x:,.0f}" if pd.notna(x) and x != "" else ""
            )

    styled = (
        df_show.style
        .set_table_styles([
            {"selector": "thead th", "props": [
                ("background-color", "#1f3a5f"),
                ("color", "white"),
                ("font-size", "12px"),
                ("font-weight", "600"),
                ("padding", "8px 12px"),
                ("text-align", "left"),
                ("border-bottom", "2px solid #e0e0e0"),
                ("white-space", "nowrap"),
            ]},
            {"selector": "tbody td", "props": [
                ("font-size", "12px"),
                ("padding", "6px 12px"),
                ("border-bottom", "1px solid #f0f0f0"),
                ("white-space", "nowrap"),
            ]},
            {"selector": "tbody tr:hover", "props": [("background-color", "#eef4ff")]},
            {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#f8f9fa")]},
            {"selector": "table", "props": [
                ("border-collapse", "collapse"),
                ("width", "100%"),
                ("font-family", "sans-serif"),
            ]},
        ])
        .hide(axis="index")
    )

    st.markdown(f"**{len(df_show):,} registros exibidos**")
    st.markdown(styled.to_html(), unsafe_allow_html=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Exportar CSV completo", csv, "itbi_consulta.csv", "text/csv")
