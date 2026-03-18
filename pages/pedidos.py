import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. SEGURANÇA E CONEXÃO
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("🚫 Acesso negado. Por favor, faça login.")
    st.stop()

st.title("📝 Sistema de Pedidos")

# Inicialização de estados
if "carrinho" not in st.session_state:
    st.session_state["carrinho"] = []
if "form_version" not in st.session_state:
    st.session_state["form_version"] = 0

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)


def limpar_coluna_texto(df, coluna):
    if coluna not in df.columns:
        df[coluna] = ""
    df[coluna] = df[coluna].fillna("").astype(str).str.strip()
    df[coluna] = df[coluna].replace(["nan", "None", "NaN"], "")
    return df


@st.cache_data(ttl=300)
def carregar_dados_pedidos():
    try:
        df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="Produtos").fillna("")
        df_s = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos").fillna("")

        # ===== PRODUTOS =====
        for col in ["Item", "Descrição", "Categoria"]:
            df_p = limpar_coluna_texto(df_p, col)

        # ===== PEDIDOS =====
        for col in ["id_pedido", "data", "usuario", "status", "loja", "item_codigo", "descricao"]:
            df_s = limpar_coluna_texto(df_s, col)

        if "quantidade" not in df_s.columns:
            df_s["quantidade"] = 0

        df_s["quantidade"] = pd.to_numeric(df_s["quantidade"], errors="coerce").fillna(0).astype(int)

        # Remove linhas inúteis/vazias que costumam vir da planilha
        if "id_pedido" in df_s.columns:
            df_s = df_s[df_s["id_pedido"] != ""].copy()

        return df_p, df_s

    except Exception as e:
        st.error(f"⚠️ Erro ao carregar a interface: {e}")
        return None, None


df_p, df_s = carregar_dados_pedidos()

if df_p is None:
    st.stop()

# --- INTERFACE ---
tab_novo, tab_hist = st.tabs(["🆕 Montar Pedido", "📜 Gestão e Envio"])

with tab_novo:
    with st.container(border=True):
        st.subheader("🔍 Localizar Produto")

        col_cat, col_txt = st.columns([1, 2])

        with col_cat:
            categorias_validas = [c for c in df_p["Categoria"].tolist() if str(c).strip() != ""]
            cats = ["Todas"] + sorted(list(set(categorias_validas)))
            cat_sel = st.selectbox("Filtrar Categoria", cats)

        with col_txt:
            busca_txt = st.text_input("Buscar por Código ou Descrição").strip().lower()

        # Aplicando filtros no DataFrame de produtos
        df_p_filtrado = df_p.copy()

        if cat_sel != "Todas":
            df_p_filtrado = df_p_filtrado[df_p_filtrado["Categoria"] == cat_sel]

        if busca_txt:
            filtro_item = df_p_filtrado["Item"].astype(str).str.lower().str.contains(busca_txt, na=False, regex=False)
            filtro_desc = df_p_filtrado["Descrição"].astype(str).str.lower().str.contains(busca_txt, na=False, regex=False)
            df_p_filtrado = df_p_filtrado[filtro_item | filtro_desc]

        if not df_p_filtrado.empty:
            lista_prods = (
                df_p_filtrado["Item"].astype(str).str.strip()
                + " - "
                + df_p_filtrado["Descrição"].astype(str).str.strip()
            ).tolist()

            idx_edicao = 0
            if "editando_item" in st.session_state:
                try:
                    idx_edicao = [
                        i for i, s in enumerate(lista_prods)
                        if s.startswith(st.session_state["editando_item"])
                    ][0]
                except Exception:
                    idx_edicao = 0

            prod_sel = st.selectbox("Selecione o item para o pedido", lista_prods, index=idx_edicao)

            partes = prod_sel.split(" - ", 1)
            cod_at = partes[0]
            desc_at = partes[1] if len(partes) > 1 else ""

            st.divider()
            st.subheader(f"🏬 Quantidades para: {desc_at}")

            lojas_qtds = {}
            for r_idx in range(0, 20, 5):
                cols = st.columns(5)
                for i in range(5):
                    id_loja = r_idx + i + 1
                    nome_loja = f"Loja {id_loja:02d}"
                    chave = f"tmp_{nome_loja}_v{st.session_state.form_version}"

                    v_padrao = 0
                    if "dados_edicao" in st.session_state and nome_loja in st.session_state["dados_edicao"]:
                        try:
                            v_padrao = int(st.session_state["dados_edicao"][nome_loja])
                        except Exception:
                            v_padrao = 0

                    with cols[i]:
                        cor_f = "#FFD700" if v_padrao > 0 else "transparent"
                        st.markdown(
                            f'<div style="background-color:{cor_f}; border-radius:4px; text-align:center;"><b>{nome_loja}</b></div>',
                            unsafe_allow_html=True
                        )
                        lojas_qtds[nome_loja] = st.number_input(
                            nome_loja,
                            min_value=0,
                            step=1,
                            value=v_padrao,
                            key=chave,
                            label_visibility="collapsed"
                        )

            txt_btn = "💾 Salvar Alterações" if "editando_item" in st.session_state else "➕ Adicionar à Lista"

            if st.button(txt_btn, use_container_width=True, type="primary"):
                if "editando_item" in st.session_state:
                    st.session_state["carrinho"] = [
                        item for item in st.session_state["carrinho"]
                        if item["item_codigo"] != st.session_state["editando_item"]
                    ]
                    del st.session_state["editando_item"]
                    del st.session_state["dados_edicao"]

                novos = [
                    {
                        "loja": l,
                        "item_codigo": cod_at,
                        "descricao": desc_at,
                        "quantidade": int(q)
                    }
                    for l, q in lojas_qtds.items()
                    if int(q) > 0
                ]

                if novos:
                    st.session_state["carrinho"].extend(novos)
                    st.session_state["form_version"] += 1
                    st.success(f"Item {cod_at} adicionado!")
                    st.rerun()
                else:
                    st.warning("Informe ao menos uma quantidade maior que zero.")

    # --- LISTAGEM DO CARRINHO ---
    if st.session_state["carrinho"]:
        st.divider()
        st.subheader("📋 Resumo do Pedido Atual")
        df_c = pd.DataFrame(st.session_state["carrinho"])

        if not df_c.empty:
            df_c["quantidade"] = pd.to_numeric(df_c["quantidade"], errors="coerce").fillna(0).astype(int)

            for cod in df_c["item_codigo"].unique():
                d_item = df_c[df_c["item_codigo"] == cod]

                with st.container(border=True):
                    c_t, c_e, c_c = st.columns([3, 1, 1])
                    c_t.markdown(f"**Item: {cod}** | Total: **{int(d_item['quantidade'].sum())}** un")

                    if c_e.button("📝 Editar", key=f"ed_{cod}"):
                        st.session_state["editando_item"] = cod
                        st.session_state["dados_edicao"] = d_item.set_index("loja")["quantidade"].to_dict()
                        st.rerun()

                    if c_c.button("❌", key=f"can_{cod}"):
                        st.session_state["carrinho"] = [
                            i for i in st.session_state["carrinho"]
                            if i["item_codigo"] != cod
                        ]
                        st.rerun()

        if st.button("💾 FINALIZAR E SALVAR PEDIDO", type="primary", use_container_width=True):
            id_p = datetime.now().strftime("%Y%m%d%H%M")

            df_final = pd.DataFrame(st.session_state["carrinho"]).copy()
            df_final["quantidade"] = pd.to_numeric(df_final["quantidade"], errors="coerce").fillna(0).astype(int)
            df_final["id_pedido"] = str(id_p)
            df_final["data"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            df_final["usuario"] = str(st.session_state.get("usuario_nome", "Admin")).strip()
            df_final["status"] = "Pendente"

            # Alinha colunas antes do concat
            colunas = sorted(set(df_s.columns.tolist()) | set(df_final.columns.tolist()))
            df_s_alinhado = df_s.reindex(columns=colunas, fill_value="")
            df_final_alinhado = df_final.reindex(columns=colunas, fill_value="")

            df_atualizado = pd.concat([df_s_alinhado, df_final_alinhado], ignore_index=True)

            conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_atualizado)

            st.cache_data.clear()
            st.session_state["carrinho"] = []
            st.success(f"Pedido #{id_p} registrado com sucesso!")
            st.rerun()

# --- ABA 2: GESTÃO ---
with tab_hist:
    st.subheader("📜 Histórico e Status")

    if df_s.empty:
        st.info("Nenhum pedido registrado no banco de dados.")
    else:
        if "status" not in df_s.columns:
            df_s["status"] = "Pendente"

        df_s["status"] = df_s["status"].replace("", "Pendente")

        # Tudo como texto antes de agrupar/ordenar
        for col in ["id_pedido", "data", "status"]:
            df_s = limpar_coluna_texto(df_s, col)

        df_s = df_s[df_s["id_pedido"] != ""].copy()

        if df_s.empty:
            st.info("Nenhum pedido válido encontrado.")
        else:
            peds = (
                df_s.groupby(["id_pedido", "data"], dropna=False)
                .first()
                .reset_index()
                .sort_values("id_pedido", ascending=False)
            )

            for _, p in peds.iterrows():
                pedido_id = str(p["id_pedido"]).strip()
                status = df_s[df_s["id_pedido"] == pedido_id]["status"].iloc[0]

                icon = "🟡" if status == "Pendente" else "🚚" if status == "Em Separação" else "✅"

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 0.5])
                    c1.markdown(f"#### {icon} Pedido: `{pedido_id}`")
                    c1.caption(f"📅 {p['data']} | Status: **{status}**")

                    if status == "Pendente":
                        if c2.button("🚀 Iniciar Separação", key=f"env_{pedido_id}", use_container_width=True):
                            df_s.loc[df_s["id_pedido"] == pedido_id, "status"] = "Em Separação"
                            conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_s)
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        c2.info(f"Ocupado: {status}")

                    if st.session_state.get("nivel") == "admin":
                        if c3.button("🗑️", key=f"del_{pedido_id}"):
                            df_upd = df_s[df_s["id_pedido"] != pedido_id].copy()
                            conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_upd)
                            st.cache_data.clear()
                            st.rerun()
