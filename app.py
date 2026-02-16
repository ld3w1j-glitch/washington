import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Sistema Alvorada", page_icon="🏢", layout="wide")

# 2. INICIALIZAÇÃO DO ESTADO DA SESSÃO
if "logado" not in st.session_state:
    st.session_state["logado"] = False
if "usuario_nome" not in st.session_state:
    st.session_state["usuario_nome"] = ""
if "nivel" not in st.session_state:
    st.session_state["nivel"] = "operador"

# 3. CONEXÃO COM O GOOGLE SHEETS
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÃO DE CARREGAMENTO DE USUÁRIOS ---
@st.cache_data(ttl=300)
def buscar_usuarios():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Usuarios").fillna("")
        return df
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return pd.DataFrame()

# --- TELA DE LOGIN ---
def tela_login():
    st.title("🔐 Login - Portal Alvorada")
    df_u = buscar_usuarios()
    
    with st.form("login_form"):
        u_input = st.text_input("Usuário").strip().lower()
        s_input = st.text_input("Senha", type="password").strip()
        
        if st.form_submit_button("Entrar"):
            if not df_u.empty:
                df_u['usuario'] = df_u['usuario'].astype(str).str.strip().str.lower()
                df_u['senha'] = df_u['senha'].astype(str).str.strip()
                
                user_match = df_u[(df_u['usuario'] == u_input) & (df_u['senha'] == s_input)]
                
                if not user_match.empty:
                    st.session_state["logado"] = True
                    st.session_state["usuario_nome"] = str(user_match.iloc[0]['usuario'])
                    st.session_state["nivel"] = str(user_match.iloc[0].get('nivel', 'operador')).lower()
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")

# --- PÁGINA DE GESTÃO DE USUÁRIOS (INTERNA) ---
def pagina_gestao():
    st.title("👥 Gerenciamento de Usuários")
    df_u = conn.read(spreadsheet=URL_PLANILHA, worksheet="Usuarios", ttl=0).fillna("")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🆕 Novo Cadastro")
        with st.form("add_user", clear_on_submit=True):
            n_u = st.text_input("Nome").strip().lower()
            n_s = st.text_input("Senha").strip()
            n_v = st.selectbox("Nível", ["operador", "admin"])
            if st.form_submit_button("Salvar"):
                if n_u and n_s:
                    novo_df = pd.concat([df_u, pd.DataFrame([{"usuario": n_u, "senha": n_s, "nivel": n_v}])], ignore_index=True)
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Usuarios", data=novo_df)
                    st.cache_data.clear()
                    st.success("Usuário cadastrado!")
                    st.rerun()
    
    with col2:
        st.subheader("🗑️ Remover Acesso")
        lista_users = [u for u in df_u['usuario'].astype(str).tolist() if u != ""]
        user_del = st.selectbox("Selecione para remover", lista_users)
        if st.button("❌ Excluir"):
            if user_del == "admin" or user_del == st.session_state["usuario_nome"]:
                st.error("Não é possível remover este usuário.")
            else:
                df_n = df_u[df_u['usuario'] != user_del]
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Usuarios", data=df_n)
                st.cache_data.clear()
                st.success("Removido!")
                st.rerun()

# --- LÓGICA DE NAVEGAÇÃO E EXIBIÇÃO ---
if not st.session_state["logado"]:
    tela_login()
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
else:
    # 1. Definimos as páginas apontando para os arquivos na pasta /pages
    # IMPORTANTE: Os arquivos devem existir na pasta 'pages' com esses nomes exatos
    pg_separacao = st.Page("pages/separacao.py", title="Separação", icon="🚜", default=(st.session_state["nivel"] == "operador"))
    pg_estoque = st.Page("pages/estoque.py", title="Estoque", icon="📦")
    pg_pedidos = st.Page("pages/pedidos.py", title="Fazer Pedidos", icon="📝")
    pg_gestao = st.Page(pagina_gestao, title="Gestão de Usuários", icon="👥")

    # 2. Montamos o menu conforme o nível
    if st.session_state["nivel"] == "admin":
        menu_paginas = [pg_separacao, pg_pedidos, pg_estoque, pg_gestao]
    else:
        menu_paginas = [pg_estoque, pg_pedidos]

    # 3. Criamos a navegação
    pg = st.navigation(menu_paginas)
    
    # Barra Lateral
    with st.sidebar:
        st.markdown(f"### Olá, {st.session_state['usuario_nome'].capitalize()}!")
        st.caption(f"Nível de Acesso: {st.session_state['nivel'].upper()}")
        st.divider()
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state["logado"] = False
            st.rerun()

    # 4. Executa a página
    try:
        pg.run()
    except Exception as e:
        st.error(f"Erro ao carregar página: {e}")
        st.info("Verifique se a pasta 'pages' contém os arquivos: separacao.py, estoque.py e pedidos.py")