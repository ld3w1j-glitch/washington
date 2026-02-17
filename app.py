import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Sistemas Washington", 
    page_icon="🏢", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. INICIALIZAÇÃO DO ESTADO DA SESSÃO
if "logado" not in st.session_state:
    st.session_state["logado"] = False
if "usuario_nome" not in st.session_state:
    st.session_state["usuario_nome"] = ""
if "nivel" not in st.session_state:
    st.session_state["nivel"] = "operador"
if "paginas_permitidas" not in st.session_state:
    st.session_state["paginas_permitidas"] = []

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
        st.error(f"Erro ao conectar com a base de dados: {e}")
        return pd.DataFrame()

# --- TELA DE LOGIN ---
def tela_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🔐 Login")
        df_u = buscar_usuarios()
        
        with st.form("login_form"):
            u_input = st.text_input("Usuário").strip().lower()
            s_input = st.text_input("Senha", type="password").strip()
            
            if st.form_submit_button("Entrar", use_container_width=True):
                if not df_u.empty:
                    df_u['usuario'] = df_u['usuario'].astype(str).str.strip().str.lower()
                    df_u['senha'] = df_u['senha'].astype(str).str.strip()
                    
                    user_match = df_u[(df_u['usuario'] == u_input) & (df_u['senha'] == s_input)]
                    
                    if not user_match.empty:
                        st.session_state["logado"] = True
                        st.session_state["usuario_nome"] = str(user_match.iloc[0]['usuario'])
                        st.session_state["nivel"] = str(user_match.iloc[0].get('nivel', 'operador')).lower()
                        
                        # NOVO: Carrega a lista de páginas permitidas da planilha
                        paginas_str = str(user_match.iloc[0].get('paginas', ''))
                        st.session_state["paginas_permitidas"] = [p.strip().lower() for p in paginas_str.split(",") if p.strip()]
                        
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos.")
                else:
                    st.warning("⚠️ Base de usuários não encontrada ou vazia.")

# --- PÁGINA DE GESTÃO DE USUÁRIOS ---
def pagina_gestao():
    st.title("👥 Gerenciamento de Usuários")
    df_u = conn.read(spreadsheet=URL_PLANILHA, worksheet="Usuarios", ttl=0).fillna("")
    
    col_cad, col_rem = st.columns(2)
    
    with col_cad:
        st.subheader("🆕 Novo Cadastro")
        with st.form("add_user", clear_on_submit=True):
            n_u = st.text_input("Nome de Usuário").strip().lower()
            n_s = st.text_input("Senha").strip()
            n_v = st.selectbox("Nível de Acesso", ["operador", "admin"])
            # NOVO: Seleção de páginas no cadastro
            n_p = st.multiselect("Páginas Permitidas", ["estoque", "pedidos", "separacao", "gestao"], default=["estoque"])
            
            if st.form_submit_button("Salvar Novo Usuário"):
                if n_u and n_s:
                    paginas_finais = ",".join(n_p)
                    novo_df = pd.concat([df_u, pd.DataFrame([{"usuario": n_u, "senha": n_s, "nivel": n_v, "paginas": paginas_finais}])], ignore_index=True)
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Usuarios", data=novo_df)
                    st.cache_data.clear()
                    st.success(f"Usuário {n_u} cadastrado!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos.")
    
    with col_rem:
        st.subheader("🗑️ Remover Acesso")
        lista_users = [u for u in df_u['usuario'].astype(str).tolist() if u != ""]
        user_del = st.selectbox("Selecione o usuário para excluir", lista_users)
        
        if st.button("❌ Confirmar Exclusão", type="primary"):
            if user_del == "admin" or user_del == st.session_state["usuario_nome"]:
                st.error("Por segurança, não é possível remover o administrador principal ou sua própria conta.")
            else:
                df_n = df_u[df_u['usuario'] != user_del]
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Usuarios", data=df_n)
                st.cache_data.clear()
                st.success(f"Usuário {user_del} removido.")
                st.rerun()

# --- LÓGICA DE NAVEGAÇÃO ---
if not st.session_state["logado"]:
    tela_login()
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
else:
    # 1. Mapa de Todas as Páginas Disponíveis
    mapa_paginas = {
        "estoque": st.Page("pages/estoque.py", title="Estoque", icon="📦"),
        "pedidos": st.Page("pages/pedidos.py", title="Fazer Pedidos", icon="📝"),
        "separacao": st.Page("pages/separacao.py", title="Separação", icon="🚜"),
        "gestao": st.Page(pagina_gestao, title="Gestão de Usuários", icon="👥")
    }

    # 2. Filtrar Páginas com base na coluna "paginas" da planilha
    menu_paginas = []
    
    # Se for ADMIN, ele pode ver a Gestão mesmo que não esteja escrito na célula
    if st.session_state["nivel"] == "admin" and "gestao" not in st.session_state["paginas_permitidas"]:
        st.session_state["paginas_permitidas"].append("gestao")

    for p in st.session_state["paginas_permitidas"]:
        if p in mapa_paginas:
            menu_paginas.append(mapa_paginas[p])

    # 3. Inicializa Navegação
    if not menu_paginas:
        st.error("Você não tem acesso a nenhuma página. Fale com o admin.")
        if st.sidebar.button("Sair"):
            st.session_state["logado"] = False
            st.rerun()
    else:
        navigation = st.navigation(menu_paginas)
        
        # Customização da Barra Lateral
        with st.sidebar:
            st.image("https://cdn-icons-png.flaticon.com/512/2304/2304226.png", width=100)
            st.markdown(f"### Bem-vindo, **{st.session_state['usuario_nome'].capitalize()}**")
            st.info(f"Nível: {st.session_state['nivel'].upper()}")
            st.divider()
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state["logado"] = False
                st.rerun()

        # 4. Execução
        try:
            navigation.run()
        except Exception as e:
            st.error(f"Erro ao carregar a interface: {e}")