import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. SEGURANÇA E CONEXÃO
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("🚫 Acesso negado. Por favor, faça login.")
    st.stop()

# Configuração da página para aproveitar o espaço lateral
st.title("📝 Sistema de Pedidos")

# Inicialização de estados
if "carrinho" not in st.session_state:
    st.session_state["carrinho"] = []
if "form_version" not in st.session_state:
    st.session_state["form_version"] = 0

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CACHE DE DADOS ---
@st.cache_data(ttl=300)
def carregar_dados_pedidos():
    try:
        df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="Produtos").fillna("")
        df_s = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos").fillna("")
        
        # Garantir tratamento de texto
        df_p['Item'] = df_p['Item'].astype(str).str.strip()
        df_p['Descrição'] = df_p['Descrição'].astype(str).str.strip()
        df_p['Categoria'] = df_p['Categoria'].astype(str).str.strip()
        
        return df_p, df_s
    except:
        return None, None

df_p, df_s = carregar_dados_pedidos()

if df_p is None:
    st.error("⚠️ Erro ao carregar dados. Verifique a conexão com a planilha.")
    st.stop()

# --- INTERFACE ---
tab_novo, tab_hist = st.tabs(["🆕 Montar Pedido", "📜 Gestão e Envio"])

with tab_novo:
    with st.container(border=True):
        st.subheader("🔍 Localizar Produto")
        
        # --- FILTRO POR CATEGORIA E BUSCA (SOLICITADO) ---
        col_cat, col_txt = st.columns([1, 2])
        
        with col_cat:
            cats = ["Todas"] + sorted(df_p['Categoria'].unique().tolist())
            cat_sel = st.selectbox("Filtrar Categoria", cats)
            
        with col_txt:
            busca_txt = st.text_input("Buscar por Código ou Descrição").strip().lower()

        # Aplicando filtros no DataFrame de produtos
        df_p_filtrado = df_p.copy()
        if cat_sel != "Todas":
            df_p_filtrado = df_p_filtrado[df_p_filtrado['Categoria'] == cat_sel]
        
        if busca_txt:
            df_p_filtrado = df_p_filtrado[
                df_p_filtrado['Item'].str.contains(busca_txt) | 
                df_p_filtrado['Descrição'].str.lower().str.contains(busca_txt)
            ]

        if not df_p_filtrado.empty:
            lista_prods = (df_p_filtrado['Item'] + " - " + df_p_filtrado['Descrição']).tolist()
            
            # Lógica de Edição (se houver item sendo editado)
            idx_edicao = 0
            if "editando_item" in st.session_state:
                try:
                    idx_edicao = [i for i, s in enumerate(lista_prods) if s.startswith(st.session_state["editando_item"])][0]
                except: pass

            prod_sel = st.selectbox("Selecione o item para o pedido", lista_prods, index=idx_edicao)
            cod_at = prod_sel.split(" - ")[0]
            desc_at = prod_sel.split(" - ")[1]

            st.divider()
            st.subheader(f"🏬 Quantidades para: {desc_at}")
            
            # Grid de Lojas (20 lojas)
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
                        # Destaca se houver quantidade
                        cor_f = "#FFD700" if v_padrao > 0 else "transparent"
                        st.markdown(f'<div style="background-color:{cor_f}; border-radius:4px; text-align:center;"><b>{nome_loja}</b></div>', unsafe_allow_html=True)
                        lojas_qtds[nome_loja] = st.number_input(nome_loja, min_value=0, step=1, value=v_padrao, key=chave, label_visibility="collapsed")

            txt_btn = "💾 Salvar Alterações" if "editando_item" in st.session_state else "➕ Adicionar à Lista"
            if st.button(txt_btn, use_container_width=True, type="primary"):
                # Se estava editando, remove a versão antiga do carrinho
                if "editando_item" in st.session_state:
                    st.session_state["carrinho"] = [item for item in st.session_state["carrinho"] if item["item_codigo"] != st.session_state["editando_item"]]
                    del st.session_state["editando_item"]
                    del st.session_state["dados_edicao"]

                novos = [{"loja": l, "item_codigo": cod_at, "descricao": desc_at, "quantidade": q} for l, q in lojas_qtds.items() if q > 0]
                if novos:
                    st.session_state["carrinho"].extend(novos)
                    st.session_state.form_version += 1 # Reseta os campos de input
                    st.success(f"Item {cod_at} adicionado!")
                    st.rerun()
        else:
            st.warning("Nenhum produto encontrado com os filtros atuais.")

    # --- LISTAGEM DO CARRINHO ---
    if st.session_state["carrinho"]:
        st.divider()
        st.subheader("📋 Resumo do Pedido Atual")
        df_c = pd.DataFrame(st.session_state["carrinho"])
        
        for cod in df_c['item_codigo'].unique():
            d_item = df_c[df_c['item_codigo'] == cod]
            with st.container(border=True):
                c_t, c_e, c_c = st.columns([3, 1, 1])
                c_t.markdown(f"**Item: {cod}** | Total: **{d_item['quantidade'].sum()}** un")
                
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
            df_final["status"] = "Pendente"
            
            # Concatena com o histórico existente
            df_atualizado = pd.concat([df_s, df_final], ignore_index=True)
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
        # Garante que a coluna status existe
        if 'status' not in df_s.columns: df_s['status'] = 'Pendente'
        
        # Agrupa para mostrar um card por ID de pedido
        peds = df_s.groupby(['id_pedido', 'data']).first().reset_index().sort_values('id_pedido', ascending=False)
        
        for _, p in peds.iterrows():
            status = df_s[df_s['id_pedido'] == p['id_pedido']]['status'].iloc[0]
            icon = "🟡" if status == "Pendente" else "🚚" if status == "Em Separação" else "✅"
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1.5, 0.5])
                c1.markdown(f"#### {icon} Pedido: `{p['id_pedido']}`")
                c1.caption(f"📅 {p['data']} | Status: **{status}**")
                
                if status == "Pendente":
                    if c2.button("🚀 Iniciar Separação", key=f"env_{p['id_pedido']}", use_container_width=True):
                        df_s.loc[df_s['id_pedido'] == p['id_pedido'], 'status'] = 'Em Separação'
                        conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_s)
                        st.cache_data.clear()
                        st.rerun()
                else:
                    c2.info(f"Ocupado: {status}")
                
                # Admin pode excluir pedidos
                if st.session_state.get("nivel") == "admin":
                    if c3.button("🗑️", key=f"del_{p['id_pedido']}"):
                        df_upd = df_s[df_s['id_pedido'] != p['id_pedido']]
                        conn.update(spreadsheet=URL_PLANILHA, worksheet="Pedidos", data=df_upd)
                        st.cache_data.clear()
                        st.rerun()
