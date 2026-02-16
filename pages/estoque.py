import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. TRAVA DE SEGURANÇA (Verifica se passou pelo app.py)
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("🚫 Acesso negado. Por favor, faça login na tela inicial.")
    st.stop()

# 2. CONFIGURAÇÃO DA PÁGINA
# Nota: st.set_page_config não é necessário aqui se já estiver no app.py, 
# mas ajuda a manter o layout se a página for recarregada.
st.title("📦 Controle de Estoque Operacional")

# 3. VARIÁVEIS DE SESSÃO
nivel_usuario = st.session_state.get("nivel", "operador")
usuario_atual = st.session_state.get("usuario_nome", "Usuário")

# 4. CONEXÃO E CARREGAMENTO
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados():
    df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="Produtos", ttl=0)
    df_m = conn.read(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", ttl=0)
    
    # Tratamento de tipos para evitar o erro 'Series object has no attribute lower'
    df_p['Item'] = df_p['Item'].astype(str).str.strip()
    df_p['Descrição'] = df_p['Descrição'].astype(str).str.strip()
    
    if not df_m.empty:
        df_m['codigo'] = df_m['codigo'].astype(str).str.strip()
        df_m['id'] = df_m['id'].astype(str).str.strip()
        df_m['descricao'] = df_m['descricao'].astype(str).str.strip()
        
    return df_p, df_m

df_p, df_m = carregar_dados()

# --- CÁLCULO DE SALDO ---
def calcular_estoque(p, m):
    p['Estoque_Inicial'] = pd.to_numeric(p['Estoque_Inicial'], errors='coerce').fillna(0)
    if m.empty:
        p['Saldo_Atual'] = p['Estoque_Inicial']
        return p
    
    m['quantidade'] = pd.to_numeric(m['quantidade'], errors='coerce').fillna(0)
    resumo = m.groupby(['codigo', 'tipo'])['quantidade'].sum().unstack(fill_value=0)
    
    for col in ['Entrada', 'Saída']:
        if col not in resumo.columns:
            resumo[col] = 0
            
    df_res = p.merge(resumo[['Entrada', 'Saída']], left_on='Item', right_index=True, how='left').fillna(0)
    df_res['Saldo_Atual'] = df_res['Estoque_Inicial'] + df_res['Entrada'] - df_res['Saída']
    return df_res

df_estoque = calcular_estoque(df_p, df_m)

# --- ORGANIZAÇÃO DAS ABAS ---
abas_nomes = ["📊 Saldo Atual", "📜 Histórico", "🔄 Lançar Movimento"]
if nivel_usuario == "admin":
    abas_nomes.append("🛠️ Admin")

abas = st.tabs(abas_nomes)

# ABA 1: SALDO ATUAL (Com busca por Código ou Descrição)
with abas[0]:
    st.subheader("Consulta de Saldo")
    busca_s = st.text_input("🔍 Buscar Item (Código ou Descrição)").strip().lower()
    
    # Filtro que aceita busca em colunas numéricas convertidas
    df_s_filtrado = df_estoque[
        df_estoque['Descrição'].str.lower().str.contains(busca_s) | 
        df_estoque['Item'].str.contains(busca_s)
    ]
    st.dataframe(df_s_filtrado[['Item', 'Descrição', 'Embalagem', 'Saldo_Atual']], use_container_width=True, hide_index=True)

# ABA 2: HISTÓRICO EM ABA SEPARADA
with abas[1]:
    st.subheader("📜 Histórico de Movimentações")
    busca_h = st.text_input("🔍 Filtrar Histórico").strip().lower()
    
    if not df_m.empty:
        df_h_filtrado = df_m[
            df_m['descricao'].str.lower().str.contains(busca_h) | 
            df_m['codigo'].str.contains(busca_h)
        ]
        st.dataframe(df_h_filtrado.sort_values(by='id', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma movimentação registrada.")

# ABA 3: LANÇAR MOVIMENTO
with abas[2]:
    st.subheader("🔄 Registrar Entrada/Saída")
    busca_p = st.text_input("🔍 Pesquisar produto p/ lançamento").strip().lower()
    
    prods_f = df_p[
        df_p['Descrição'].str.lower().str.contains(busca_p) | 
        df_p['Item'].str.contains(busca_p)
    ]

    if not prods_f.empty:
        opcoes = (prods_f['Item'] + " - " + prods_f['Descrição']).tolist()
        with st.form("form_mov", clear_on_submit=True):
            escolhido = st.selectbox("Selecione o produto", opcoes)
            c_item = escolhido.split(" - ")[0]
            d_item = escolhido.split(" - ")[1]
            
            col1, col2, col3 = st.columns([1,1,2])
            tipo_m = col1.selectbox("Tipo", ["Entrada", "Saída"])
            qtd_m = col2.number_input("Qtd", min_value=1.0, step=1.0)
            obs_m = col3.text_input("Observação")
            
            if st.form_submit_button("Confirmar"):
                nova_linha = pd.DataFrame([{
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "codigo": c_item,
                    "descricao": d_item,
                    "tipo": tipo_m,
                    "quantidade": float(qtd_m),
                    "usuario": usuario_atual,
                    "obs": obs_m
                }])
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", data=pd.concat([df_m, nova_linha], ignore_index=True))
                st.success("Registrado!")
                st.rerun()

# ABA 4: ADMIN (SÓ APARECE PARA ADMIN)
if nivel_usuario == "admin":
    with abas[3]:
        st.subheader("🛠️ Painel de Controle")
        if not df_m.empty:
            st.write("Excluir último registro:")
            lista_ids = df_m['id'].tolist()
            id_para_deletar = st.selectbox("ID do Registro", lista_ids)
            if st.button("❌ APAGAR REGISTRO"):
                df_m_novo = df_m[df_m['id'] != id_para_deletar]
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", data=df_m_novo)
                st.success("Excluído!")
                st.rerun()