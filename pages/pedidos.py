import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import io

# 1. SEGURANÇA E CONEXÃO
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("🚫 Acesso negado. Por favor, faça login.")
    st.stop()

st.set_page_config(page_title="Pedidos Alvorada", layout="wide")

if "carrinho" not in st.session_state:
    st.session_state["carrinho"] = []
if "form_version" not in st.session_state:
    st.session_state["form_version"] = 0

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CACHE DE DADOS (Proteção Erro 429) ---
@st.cache_data(ttl=600)
def carregar_dados_pedidos():
    try:
        df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="Produtos").fillna("")
        df_s = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos").fillna("")
        return df_p, df_s
    except:
        return None, None

df_p, df_s = carregar_dados_pedidos()

if df_p is None:
    st.error("⚠️ O Google está processando muitas informações. Aguarde 1 minuto.")
    st.stop()

# --- INTERFACE ---
tab_novo, tab_hist = st.tabs(["🆕 Montar Pedido", "📜 Gestão e Envio"])

with tab_novo:
    with st.container(border=True):
        st.subheader("📦 1. Selecionar Produto")
        lista_prods = (df_p['Item'].astype(str) + " - " + df_p['Descrição']).tolist()
        
        # Lógica de Edição
        idx_edicao = 0
        if "editando_item" in st.session_state:
            try:
                idx_edicao = [i for i, s in enumerate(lista_prods) if s.startswith(st.session_state["editando_item"])][0]
            except: pass

        prod_sel = st.selectbox("Escolha o item", lista_prods, index=idx_edicao)
        cod_at = prod_sel.split(" - ")[0]
        desc_at = prod_sel.split(" - ")[1]

        st.divider()
        st.subheader("🏬 2. Quantidades por Loja")
        
        lojas_qtds = {}
        for r_idx in range(0, 20, 5):
            cols = st.columns(5)
            for i in range(5):
                id_loja = r_idx + i + 1
                nome_loja = f"Loja {id_loja:02d}"
                chave = f"tmp_{nome_loja}_v{st.session_state.form_version}"
                
                v_padrao = 0
                if "dados_edicao" in st.session_state and nome_loja in st.session_state["dados_edicao"]:
                    v_padrao = st.session_state["dados_edicao"][nome_loja]
                
                with cols[i]:
                    cor_f = "#FFD700" if v_padrao > 0 else "#1E1E1E"
                    cor_t = "#000000" if v_padrao > 0 else "#FFFFFF"
                    st.markdown(f'<div style="background-color:{cor_f}; border:2px solid #555; padding:8px; border-radius:8px; text-align:center;"><b style="color:{cor_t};">{nome_loja}</b></div>', unsafe_allow_html=True)
                    lojas_qtds[nome_loja] = st.number_input(nome_loja, min_value=0, step=1, value=v_padrao, key=chave, label_visibility="collapsed")

        txt_btn = "💾 Salvar Alterações" if "editando_item" in st.session_state else "➕ Adicionar à Lista"
        if st.button(txt_btn, use_container_width=True, type="secondary"):
            if "editando_item" in st.session_state:
                st.session_state["carrinho"] = [item for item in st.session_state["carrinho"] if item["item_codigo"] != st.session_state["editando_item"]]
                del st.session_state["editando_item"]
                del st.session_state["dados_edicao"]

            novos = [{"loja": l, "item_codigo": cod_at, "descricao": desc_at, "quantidade": q} for l, q in lojas_qtds.items() if q > 0]
            if novos:
                st.session_state["carrinho"].extend(novos)
                st.session_state.form_version += 1
                st.rerun()

    # Carrinho provisório resumido
    if st.session_state["carrinho"]:
        st.divider()
        st.subheader("📋 Itens na Fila")
        df_c = pd.DataFrame(st.session_state["carrinho"])
        for cod in df_c['item_codigo'].unique():
            d_item = df_c[df_c['item_codigo'] == cod]
            with st.container(border=True):
                c_t, c_e, c_c = st.columns([3, 1, 1])
                c_t.markdown(f"**Item: {cod}** | Total: {d_item['quantidade'].sum()} un")
                if c_e.button("📝 Editar", key=f"ed_{cod}"):
                    st.session_state["editando_item"] = cod
                    st.session_state["dados_edicao"] = d_item.set_index('loja')['quantidade'].to_dict()
                    st.rerun()
                if c_c.button("❌", key=f"can_{cod}"):
                    st.session_state["carrinho"] = [i for i in st.session_state["carrinho"] if i["item_codigo"] != cod]
                    st.rerun()

        if st.button("💾 FINALIZAR E SALVAR PEDIDO", type="primary", use_container_width=True):
            id_p = datetime.now().strftime("%Y%m%d%H%M")
            df_final = pd.DataFrame(st.session_state["carrinho"])
            df_final["id_pedido"] = id_p
            df_final["data"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            df_final["usuario"] = st.session_state.get("usuario_nome", "Admin")
            df_final["status"] = "Pendente" # Status inicial
            
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=pd.concat([df_s, df_final], ignore_index=True))
            st.cache_data.clear()
            st.success("Pedido salvo!")
            st.session_state["carrinho"] = []
            st.rerun()

# --- ABA 2: GESTÃO E ENVIO PARA SEPARAÇÃO ---
with tab_hist:
    st.subheader("📜 Histórico e Envio")
    if df_s.empty:
        st.info("Nenhum pedido.")
    else:
        if 'status' not in df_s.columns: df_s['status'] = 'Pendente'
        
        peds = df_s.groupby(['id_pedido', 'data']).first().reset_index().sort_values('id_pedido', ascending=False)
        
        for _, p in peds.iterrows():
            status = df_s[df_s['id_pedido'] == p['id_pedido']]['status'].iloc[0]
            cor_status = "🟡" if status == "Pendente" else "🚚" if status == "Em Separação" else "✅"
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1.5, 0.5])
                c1.markdown(f"#### {cor_status} Pedido: `{p['id_pedido']}`")
                c1.caption(f"📅 {p['data']} | Status: **{status}**")
                
                # Botão de Despacho
                if status == "Pendente":
                    if c2.button("🚀 Enviar p/ Estoque", key=f"env_{p['id_pedido']}", use_container_width=True):
                        df_s.loc[df_s['id_pedido'] == p['id_pedido'], 'status'] = 'Em Separação'
                        conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_s)
                        st.cache_data.clear()
                        st.success("Pedido enviado para separação!")
                        st.rerun()
                else:
                    c2.info(f"Status: {status}")
                
                if st.session_state.get("nivel") == "admin" and c3.button("🗑️", key=f"del_{p['id_pedido']}"):
                    df_upd = df_s[df_s['id_pedido'] != p['id_pedido']]
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_upd)
                    st.cache_data.clear()
                    st.rerun()