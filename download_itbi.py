"""
Download e carga dos dados de ITBI (Imposto sobre Transmissão de Bens Imóveis)
da Prefeitura de São Paulo em banco SQLite local.

Fonte: https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501
"""

import os
import sys
import time
import sqlite3
import logging
import unicodedata
from pathlib import Path

import requests
import pandas as pd
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = Path(r"C:\Users\mathe\itbi_sp\downloads")
DB_PATH = Path(r"C:\Users\mathe\itbi_sp\itbi_sp.db")

DOWNLOAD_DIR.mkdir(exist_ok=True)

FILES = {
    2026: "https://prefeitura.sp.gov.br/documents/d/fazenda/guias-de-itbi-pagas-3-xlsx",
    2025: "https://prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/GUIAS%20DE%20ITBI%20PAGAS%20%2828012026%29%20XLS.xlsx",
    2024: "https://prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/GUIAS-DE-ITBI-PAGAS-2024.xlsx",
    2023: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/XLSX/GUIAS-DE-ITBI-PAGAS-2023.xlsx",
    2022: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/XLSX/GUIAS_DE_ITBI_PAGAS_12-2022.xlsx",
    2021: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/ITBI_Setembro_2022/GUIAS_DE_ITBI_PAGAS_(2021).xlsx",
    2020: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/ITBI_Setembro_2022/GUIAS_DE_ITBI_PAGAS_(2020).xlsx",
    2019: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/ITBI_Setembro_2022/GUIAS_DE_ITBI_PAGAS_(2019).xlsx",
    2018: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2018.xlsx",
    2017: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2017.xlsx",
    2016: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2016.xlsx",
    2015: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2015.xlsx",
    2014: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2014.xlsx",
    2013: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2013.xlsx",
    2012: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2012.xlsx",
    2011: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2011.xlsx",
    2010: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2010.xlsx",
    2009: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2009.xlsx",
    2008: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2008.xlsx",
    2007: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2007.xlsx",
    2006: "https://www.prefeitura.sp.gov.br/cidade/secretarias/upload/fazenda/arquivos/itbi/guias_de_itbi_pagas_2006.xlsx",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

COLUMN_MAP = {
    "numero da guia": "numero_guia",
    "n da guia": "numero_guia",
    "numero guia": "numero_guia",
    "guia": "numero_guia",
    "data de pagamento": "data_pagamento",
    "dt pagamento": "data_pagamento",
    "data pagamento": "data_pagamento",
    "natureza da transacao": "natureza_transacao",
    "natureza transacao": "natureza_transacao",
    "natureza": "natureza_transacao",
    "nat transacao": "natureza_transacao",
    "natureza de transacao": "natureza_transacao",
    "tipo do imovel": "tipo_imovel",
    "tipo imovel": "tipo_imovel",
    "tipo de imovel": "tipo_imovel",
    "tipo": "tipo_imovel",
    "subdistrito": "subdistrito",
    "sub distrito": "subdistrito",
    "sub-distrito": "subdistrito",
    "setor quadra": "setor_quadra",
    "setor/quadra": "setor_quadra",
    "valor da transacao": "valor_transacao",
    "valor transacao": "valor_transacao",
    "vl transacao": "valor_transacao",
    "valor da transacao (r$)": "valor_transacao",
    "valor de transacao declarado pelo contribuinte": "valor_transacao",
    "valor de transacao (declarado pelo contribuinte)": "valor_transacao",
    "valor venal de referencia": "valor_venal_referencia",
    "vl venal referencia": "valor_venal_referencia",
    "valor venal de referencia (r$)": "valor_venal_referencia",
    "valor venal referencia": "valor_venal_referencia",
    "valor financiado": "valor_financiado",
    "vl financiado": "valor_financiado",
    "valor financiado (r$)": "valor_financiado",
    "base de calculo": "base_calculo",
    "base calculo": "base_calculo",
    "base de calculo (r$)": "base_calculo",
    "base de calculo adotada": "base_calculo",
    "valor do imposto": "valor_imposto",
    "valor imposto": "valor_imposto",
    "vl imposto": "valor_imposto",
    "valor do imposto (r$)": "valor_imposto",
    "cep do imovel": "cep_imovel",
    "cep imovel": "cep_imovel",
    "cep": "cep_imovel",
    "fracao ideal": "fracao_ideal",
    "fracao ideal (%)": "fracao_ideal",
    "area do terreno": "area_terreno",
    "area terreno": "area_terreno",
    "area do terreno (m2)": "area_terreno",
    "area do terreno m2": "area_terreno",
    "area construida": "area_construida",
    "area construida (m2)": "area_construida",
    "area construida m2": "area_construida",
    "n do cadastro sql": "no_do_cadastro_sql",
    "no do cadastro sql": "no_do_cadastro_sql",
    "n do cadastro (sql)": "no_do_cadastro_sql",
    "nome do logradouro": "nome_do_logradouro",
    "numero": "numero_endereco",
    "complemento": "complemento",
    "bairro": "bairro",
    "referencia": "referencia",
    "data de transacao": "data_transacao",
    "data transacao": "data_transacao",
    "proporcao transmitida %": "proporcao_transmitida",
    "proporcao transmitida (%)": "proporcao_transmitida",
    "proporcao transmitida": "proporcao_transmitida",
    "valor venal de referencia proporcional": "valor_venal_ref_proporcional",
    "valor venal de referencia (proporcional)": "valor_venal_ref_proporcional",
    "tipo de financiamento": "tipo_financiamento",
    "tipo financiamento": "tipo_financiamento",
    "cartorio de registro": "cartorio_registro",
    "matricula do imovel": "matricula_imovel",
    "situacao do sql": "situacao_sql",
    "testada m": "testada_m",
    "testada (m)": "testada_m",
    "uso iptu": "uso_iptu",
    "uso (iptu)": "uso_iptu",
    "descricao do uso iptu": "descricao_uso_iptu",
    "descricao do uso (iptu)": "descricao_uso_iptu",
    "padrao iptu": "padrao_iptu",
    "padrao (iptu)": "padrao_iptu",
    "descricao do padrao iptu": "descricao_padrao_iptu",
    "descricao do padrao (iptu)": "descricao_padrao_iptu",
    "acc iptu": "acc_iptu",
    "acc (iptu)": "acc_iptu",
}

POSITIONAL_COLUMNS = [
    "no_do_cadastro_sql", "nome_do_logradouro", "numero_endereco",
    "complemento", "bairro", "referencia", "cep_imovel",
    "natureza_transacao", "valor_transacao", "data_transacao",
    "valor_venal_referencia", "proporcao_transmitida",
    "valor_venal_ref_proporcional", "base_calculo",
    "tipo_financiamento", "valor_financiado", "cartorio_registro",
    "matricula_imovel", "situacao_sql", "area_terreno", "testada_m",
    "fracao_ideal", "area_construida", "uso_iptu", "descricao_uso_iptu",
    "padrao_iptu", "descricao_padrao_iptu", "acc_iptu",
]

KNOWN_COLUMNS = [
    "ano_referencia", "numero_guia", "data_pagamento", "natureza_transacao",
    "tipo_imovel", "subdistrito", "setor_quadra", "valor_transacao",
    "valor_venal_referencia", "valor_financiado", "base_calculo",
    "valor_imposto", "cep_imovel", "fracao_ideal", "area_terreno",
    "area_construida", "no_do_cadastro_sql", "nome_do_logradouro",
    "numero_endereco", "complemento", "bairro", "referencia",
    "data_transacao", "proporcao_transmitida", "valor_venal_ref_proporcional",
    "tipo_financiamento", "cartorio_registro", "matricula_imovel",
    "situacao_sql", "testada_m", "uso_iptu", "descricao_uso_iptu",
    "padrao_iptu", "descricao_padrao_iptu", "acc_iptu",
]


def download_file(url: str, dest: Path, max_retries: int = 3) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, stream=True, timeout=120, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            with open(dest, "wb") as f:
                with tqdm(total=total, unit="B", unit_scale=True, desc=dest.name, leave=False) as bar:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bar.update(len(chunk))
            if dest.stat().st_size < 1000:
                log.warning(f"Arquivo muito pequeno ({dest.stat().st_size} bytes), pode estar corrompido: {dest.name}")
                return False
            return True
        except Exception as e:
            log.warning(f"Tentativa {attempt}/{max_retries} falhou para {dest.name}: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    return False


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    original_cols = list(df.columns)
    normalized = {}
    for i, col in enumerate(original_cols):
        col_str = str(col).strip()
        key = strip_accents(col_str).lower().replace("_", " ").replace("  ", " ")
        if key in COLUMN_MAP:
            normalized[col] = COLUMN_MAP[key]
        else:
            clean = key.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_").replace("%", "pct")
            normalized[col] = clean if clean else f"col_{i}"
    df = df.rename(columns=normalized)
    return df


def _parse_sheet(raw: pd.DataFrame) -> pd.DataFrame | None:
    """Detecta cabeçalho, normaliza colunas e descarta linhas vazias de uma sheet."""
    if raw.empty:
        return None

    header_keywords = {"cadastro", "logradouro", "transac", "natureza", "terreno", "iptu", "cep"}
    header_row = None
    for i in range(min(10, len(raw))):
        row_values = [strip_accents(str(v)).lower() for v in raw.iloc[i].values if pd.notna(v)]
        matches = sum(1 for v in row_values if any(kw in v for kw in header_keywords))
        if matches >= 3:
            header_row = i
            break

    if header_row is not None:
        raw.columns = [
            str(raw.iloc[header_row, j]).strip() if pd.notna(raw.iloc[header_row, j]) else f"col_{j}"
            for j in range(len(raw.columns))
        ]
        raw = raw.iloc[header_row + 1:].reset_index(drop=True)
        raw = normalize_columns(raw)
    else:
        num_cols = len(raw.columns)
        col_names = POSITIONAL_COLUMNS[:num_cols]
        if num_cols > len(POSITIONAL_COLUMNS):
            col_names += [f"extra_{i}" for i in range(num_cols - len(POSITIONAL_COLUMNS))]
        raw.columns = col_names

    raw = raw.dropna(how="all")
    # remove colunas duplicadas que surgem quando dois headers normalizam para o mesmo nome
    raw = raw.loc[:, ~raw.columns.duplicated(keep="first")]
    return raw if not raw.empty else None


def read_excel_safe(filepath: Path, year: int) -> pd.DataFrame | None:
    try:
        xf = pd.ExcelFile(filepath, engine="openpyxl")
        sheet_names = xf.sheet_names
    except Exception as e:
        log.error(f"Erro ao abrir {filepath.name}: {e}")
        return None

    log.info(f"    Sheets encontradas: {sheet_names}")
    dfs = []
    for sheet in sheet_names:
        try:
            raw = pd.read_excel(xf, sheet_name=sheet, header=None)
        except Exception as e:
            log.warning(f"    Sheet '{sheet}': erro ao ler — {e}")
            continue

        df = _parse_sheet(raw)
        if df is None:
            log.info(f"    Sheet '{sheet}': vazia ou sem dados reconhecíveis, ignorada")
            continue

        df["ano_referencia"] = year
        dfs.append(df)
        log.info(f"    Sheet '{sheet}': {len(df):,} linhas")

    if not dfs:
        log.warning(f"Nenhuma sheet com dados válidos em {filepath.name}")
        return None

    return pd.concat(dfs, ignore_index=True)


def create_database(conn: sqlite3.Connection):
    conn.execute("DROP TABLE IF EXISTS itbi_transacoes")
    conn.execute("""
        CREATE TABLE itbi_transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_referencia INTEGER,
            numero_guia TEXT,
            data_pagamento TEXT,
            natureza_transacao TEXT,
            tipo_imovel TEXT,
            subdistrito TEXT,
            setor_quadra TEXT,
            valor_transacao REAL,
            valor_venal_referencia REAL,
            valor_financiado REAL,
            base_calculo REAL,
            valor_imposto REAL,
            cep_imovel TEXT,
            fracao_ideal REAL,
            area_terreno REAL,
            area_construida REAL,
            no_do_cadastro_sql TEXT,
            nome_do_logradouro TEXT,
            numero_endereco TEXT,
            complemento TEXT,
            bairro TEXT,
            referencia TEXT,
            data_transacao TEXT,
            proporcao_transmitida REAL,
            valor_venal_ref_proporcional REAL,
            tipo_financiamento TEXT,
            cartorio_registro TEXT,
            matricula_imovel TEXT,
            situacao_sql TEXT,
            testada_m REAL,
            uso_iptu TEXT,
            descricao_uso_iptu TEXT,
            padrao_iptu TEXT,
            descricao_padrao_iptu TEXT,
            acc_iptu TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ano ON itbi_transacoes(ano_referencia)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_natureza ON itbi_transacoes(natureza_transacao)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tipo ON itbi_transacoes(tipo_imovel)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subdistrito ON itbi_transacoes(subdistrito)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bairro ON itbi_transacoes(bairro)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_pagamento ON itbi_transacoes(data_pagamento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_data_transacao ON itbi_transacoes(data_transacao)")
    conn.commit()


def load_to_db(df: pd.DataFrame, conn: sqlite3.Connection, year: int) -> int:
    cols_to_insert = [c for c in KNOWN_COLUMNS if c in df.columns]
    df_insert = df[cols_to_insert].copy()

    for date_col in ["data_pagamento", "data_transacao"]:
        if date_col in df_insert.columns:
            df_insert[date_col] = pd.to_datetime(
                df_insert[date_col], errors="coerce", dayfirst=True
            ).dt.strftime("%Y-%m-%d")

    for col in ["valor_transacao", "valor_venal_referencia", "valor_financiado",
                 "base_calculo", "valor_imposto", "fracao_ideal", "area_terreno", "area_construida",
                 "proporcao_transmitida", "valor_venal_ref_proporcional", "testada_m"]:
        if col in df_insert.columns:
            df_insert[col] = pd.to_numeric(df_insert[col], errors="coerce")

    text_cols = {
        "numero_guia", "natureza_transacao", "tipo_imovel", "subdistrito", "setor_quadra",
        "cep_imovel", "no_do_cadastro_sql", "nome_do_logradouro", "numero_endereco",
        "complemento", "bairro", "referencia", "tipo_financiamento", "cartorio_registro",
        "matricula_imovel", "situacao_sql", "uso_iptu", "descricao_uso_iptu",
        "padrao_iptu", "descricao_padrao_iptu", "acc_iptu",
    }
    for col in text_cols:
        if col in df_insert.columns:
            df_insert[col] = df_insert[col].astype(str).str.strip()
            df_insert[col] = df_insert[col].replace({"nan": None, "None": None, "": None})

    if "cep_imovel" in df_insert.columns:
        df_insert["cep_imovel"] = df_insert["cep_imovel"].apply(
            lambda x: x.zfill(8) if isinstance(x, str) and x.isdigit() else x
        )

    rows_before = conn.execute("SELECT COUNT(*) FROM itbi_transacoes WHERE ano_referencia = ?", (year,)).fetchone()[0]
    if rows_before > 0:
        log.info(f"  Removendo {rows_before} registros existentes de {year} antes de recarregar...")
        conn.execute("DELETE FROM itbi_transacoes WHERE ano_referencia = ?", (year,))

    df_insert.to_sql("itbi_transacoes", conn, if_exists="append", index=False)
    conn.commit()
    return len(df_insert)


def main():
    log.info("=" * 60)
    log.info("ITBI Sao Paulo - Download e Carga de Dados")
    log.info("=" * 60)

    log.info(f"\nBaixando {len(FILES)} arquivos...")
    downloaded = {}
    for year in sorted(FILES.keys()):
        url = FILES[year]
        dest = DOWNLOAD_DIR / f"itbi_{year}.xlsx"
        if dest.exists() and dest.stat().st_size > 1000:
            log.info(f"  {year}: ja existe ({dest.stat().st_size:,} bytes), pulando download")
            downloaded[year] = dest
            continue
        log.info(f"  {year}: baixando...")
        if download_file(url, dest):
            log.info(f"  {year}: OK ({dest.stat().st_size:,} bytes)")
            downloaded[year] = dest
        else:
            log.error(f"  {year}: FALHOU")

    log.info(f"\nCarregando dados no SQLite: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    create_database(conn)

    total_rows = 0
    for year in sorted(downloaded.keys()):
        filepath = downloaded[year]
        log.info(f"  Processando {year}...")

        df = read_excel_safe(filepath, year)
        if df is None:
            continue

        log.info(f"    Colunas encontradas: {list(df.columns)}")
        log.info(f"    Linhas no arquivo: {len(df):,}")

        rows = load_to_db(df, conn, year)
        total_rows += rows
        log.info(f"    Inseridas: {rows:,} linhas")

    log.info("\n" + "=" * 60)
    log.info("RESUMO")
    log.info("=" * 60)

    cursor = conn.execute("""
        SELECT ano_referencia, COUNT(*) as total
        FROM itbi_transacoes
        GROUP BY ano_referencia
        ORDER BY ano_referencia
    """)
    for row in cursor:
        log.info(f"  {row[0]}: {row[1]:>10,} registros")

    total = conn.execute("SELECT COUNT(*) FROM itbi_transacoes").fetchone()[0]
    log.info(f"\n  TOTAL: {total:,} registros no banco")
    log.info(f"  Banco: {DB_PATH}")
    log.info(f"  Tamanho: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")

    conn.close()
    log.info("\nConcluido!")


if __name__ == "__main__":
    main()
