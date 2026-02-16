import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. TRAVA DE SEGURANÇA
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("🚫 Acesso negado. Por favor, faça login na tela inicial.")
    st.stop()

# 2. CONFIGURAÇÃO DA PÁGINA
st.title("📦 Controle de Estoque Operacional")

# 3. VARIÁVEIS DE SESSÃO
nivel_usuario = st.session_state.get("nivel", "operador")
usuario_atual = st.session_state.get("usuario_nome", "Usuário")

# 4. CONEXÃO E CARREGAMENTO
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60) # Cache curto para manter agilidade e precisão
def carregar_dados():
    try:
        df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="Produtos", ttl=0).fillna("")
        df_m = conn.read(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", ttl=0).fillna("")
        
        # Garantir tipos de dados
        df_p['Item'] = df_p['Item'].astype(str).str.strip()
        df_p['Descrição'] = df_p['Descrição'].astype(str).str.strip()
        df_p['Categoria'] = df_p['Categoria'].astype(str).str.strip()
        
        return df_p, df_m
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_p, df_m = carregar_dados()

# --- CÁLCULO DE SALDO ---
def calcular_estoque(p, m):
    # Criar cópia para não afetar o original
    p_result = p.copy()
    p_result['Estoque_Inicial'] = pd.to_numeric(p_result['Estoque_Inicial'], errors='coerce').fillna(0)
    
    if m.empty:
        p_result['Saldo_Atual'] = p_result['Estoque_Inicial']
        return p_result
    
    m_copy = m.copy()
    m_copy['quantidade'] = pd.to_numeric(m_copy['quantidade'], errors='coerce').fillna(0)
    
    resumo = m_copy.groupby(['codigo', 'tipo'])['quantidade'].sum().unstack(fill_value=0)
    
    for col in ['Entrada', 'Saída']:
        if col not in resumo.columns:
            resumo[col] = 0
            
    df_res = p_result.merge(resumo[['Entrada', 'Saída']], left_on='Item', right_index=True, how='left').fillna(0)
    df_res['Saldo_Atual'] = df_res['Estoque_Inicial'] + df_res['Entrada'] - df_res['Saída']
    return df_res

df_estoque = calcular_estoque(df_p, df_m)

# --- ORGANIZAÇÃO DAS ABAS ---
abas_nomes = ["📊 Saldo Atual", "📜 Histórico", "🔄 Lançar Movimento"]
if nivel_usuario == "admin":
    abas_nomes.append("🛠️ Admin")

abas = st.tabs(abas_nomes)

# ABA 1: SALDO ATUAL
with abas[0]:
    st.subheader("Consulta de Saldo")
    
    col_cat, col_busca = st.columns([1, 2])
    
    with col_cat:
        lista_categorias = ["Todas"] + sorted(df_estoque['Categoria'].unique().tolist())
        cat_f = st.selectbox("Filtrar Categoria", lista_categorias, key="cat_saldo")
    
    with col_busca:
        busca_s = st.text_input("🔍 Buscar Código ou Descrição", key="busca_saldo").strip().lower()
    
    # Aplicação dos Filtros
    df_filtrado = df_estoque.copy()
    if cat_f != "Todas":
        df_filtrado = df_filtrado[df_filtrado['Categoria'] == cat_f]
    
    if busca_s:
        df_filtrado = df_filtrado[
            df_filtrado['Descrição'].str.lower().str.contains(busca_s) | 
            df_filtrado['Item'].str.contains(busca_s)
        ]
    
    st.dataframe(
        df_filtrado[['Item', 'Descrição', 'Categoria', 'Embalagem', 'Saldo_Atual']], 
        use_container_width=True, 
        hide_index=True
    )

# ABA 2: HISTÓRICO
with abas[1]:
    st.subheader("📜 Histórico de Movimentações")
    busca_h = st.text_input("🔍 Filtrar por código ou descrição no histórico").strip().lower()
    
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
    
    # Filtros para o lançamento
    c1, c2 = st.columns([1, 2])
    with c1:
        cat_lanca = st.selectbox("1. Filtrar Categoria", ["Todas"] + sorted(df_p['Categoria'].unique().tolist()))
    with c2:
        busca_lanca = st.text_input("2. Digite parte do nome ou código").strip().lower()

    # Filtragem do DataFrame de produtos para o Selectbox
    prods_f = df_p.copy()
    if cat_lanca != "Todas":
        prods_f = prods_f[prods_f['Categoria'] == cat_lanca]
    
    if busca_lanca:
        prods_f = prods_f[
            prods_f['Descrição'].str.lower().str.contains(busca_lanca) | 
            prods_f['Item'].str.contains(busca_lanca)
        ]

    if not prods_f.empty:
        opcoes = (prods_f['Item'] + " - " + prods_f['Descrição']).tolist()
        
        with st.form("form_mov", clear_on_submit=True):
            escolhido = st.selectbox("3. Selecione o produto exato", opcoes)
            c_item = escolhido.split(" - ")[0]
            d_item = escolhido.split(" - ")[1]
            
            col1, col2, col3 = st.columns([1,1,2])
            tipo_m = col1.selectbox("Tipo", ["Entrada", "Saída"])
            qtd_m = col2.number_input("Quantidade", min_value=0.1, step=1.0)
            obs_m = col3.text_input("Observação/Motivo")
            
            if st.form_submit_button("Confirmar Lançamento", use_container_width=True):
                # Recarrega m para garantir que temos a lista atualizada antes de concatenar
                _, df_m_atual = carregar_dados()
                
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
                
                df_final = pd.concat([df_m_atual, nova_linha], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", data=df_final)
                st.cache_data.clear()
                st.success(f"✅ {tipo_m} de {qtd_m} unidades de {d_item} realizada!")
                st.rerun()
    else:
        st.warning("Nenhum produto encontrado com os filtros aplicados.")

# ABA 4: ADMIN
if nivel_usuario == "admin":
    with abas[3]:
        st.subheader("🛠️ Painel de Controle")
        if not df_m.empty:
            st.write("Excluir registro específico:")
            # Mostra os últimos 10 para facilitar
            df_ultimos = df_m.sort_values(by='id', ascending=False).head(10)
            id_para_deletar = st.selectbox("Selecione o ID (Data/Hora) para excluir", df_ultimos['id'].tolist())
            
            if st.button("❌ APAGAR REGISTRO SELECIONADO", type="primary"):
                df_m_novo = df_m[df_m['id'] != id_para_deletar]
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", data=df_m_novo)
                st.cache_data.clear()
                st.success("Registro removido com sucesso!")
                st.rerun()
