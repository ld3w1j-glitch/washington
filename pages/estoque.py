import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. SEGURANÇA: Verifica login
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("🚫 Acesso negado. Por favor, faça login.")
    st.stop()

st.title("📦 Controle de Estoque Operacional")

# 2. VARIÁVEIS DE SESSÃO
nivel_usuario = st.session_state.get("nivel", "operador")
usuario_atual = st.session_state.get("usuario_nome", "Usuário")

# 3. CONEXÃO
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# 4. CARREGAMENTO DOS DADOS COM TRATAMENTO DE TIPOS (Blindagem)
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="Produtos", ttl=0).fillna("")
        df_m = conn.read(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", ttl=0).fillna("")
        
        # FORÇAR TIPO TEXTO (Para evitar erro de merge Object vs Float)
        df_p['Item'] = df_p['Item'].astype(str).str.strip()
        df_p['Descrição'] = df_p['Descrição'].astype(str).str.strip()
        df_p['Categoria'] = df_p['Categoria'].astype(str).str.strip()
        df_p['Embalagem'] = df_p['Embalagem'].astype(str).str.strip()
        
        if not df_m.empty:
            df_m['codigo'] = df_m['codigo'].astype(str).str.strip()
            df_m['tipo'] = df_m['tipo'].astype(str).str.strip()
        
        return df_p, df_m
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_p, df_m = carregar_dados()

# --- CÁLCULO DE SALDO (Correção do Erro de Merge) ---
def calcular_estoque(p, m):
    p_result = p.copy()
    p_result['Estoque_Inicial'] = pd.to_numeric(p_result['Estoque_Inicial'], errors='coerce').fillna(0)
    
    if m.empty:
        p_result['Entrada'] = 0
        p_result['Saída'] = 0
        p_result['Saldo_Atual'] = p_result['Estoque_Inicial']
        return p_result
    
    m_copy = m.copy()
    m_copy['quantidade'] = pd.to_numeric(m_copy['quantidade'], errors='coerce').fillna(0)
    
    # Agrupa por código e tipo
    resumo = m_copy.groupby(['codigo', 'tipo'])['quantidade'].sum().unstack(fill_value=0)
    
    # Garante colunas de Entrada e Saída
    for col in ['Entrada', 'Saída']:
        if col not in resumo.columns:
            resumo[col] = 0
            
    # FORÇA INDEX PARA STRING (Essencial para o merge funcionar)
    resumo.index = resumo.index.astype(str)
            
    # Merge seguro (String com String)
    df_res = p_result.merge(resumo[['Entrada', 'Saída']], left_on='Item', right_index=True, how='left').fillna(0)
    df_res['Saldo_Atual'] = df_res['Estoque_Inicial'] + df_res['Entrada'] - df_res['Saída']
    return df_res

df_estoque = calcular_estoque(df_p, df_m)

# --- INTERFACE POR ABAS ---
abas_nomes = ["📊 Saldo Atual", "📜 Histórico", "🔄 Lançar Movimento", "➕ Cadastrar Item"]
if nivel_usuario == "admin":
    abas_nomes.append("🛠️ Admin")

abas = st.tabs(abas_nomes)

# ABA 1: SALDO ATUAL COM FILTRO DE CATEGORIA E BUSCA
with abas[0]:
    st.subheader("Consulta de Itens")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        categorias = ["Todas"] + sorted(df_estoque['Categoria'].unique().tolist())
        cat_filtro = st.selectbox("Filtrar por Categoria", categorias, key="sb_cat")
    with col2:
        busca_txt = st.text_input("🔍 Buscar Código ou Descrição", key="txt_busca").strip().lower()
    
    # Aplicação dos Filtros
    df_exibir = df_estoque.copy()
    if cat_filtro != "Todas":
        df_exibir = df_exibir[df_exibir['Categoria'] == cat_filtro]
    
    if busca_txt:
        df_exibir = df_exibir[
            (df_exibir['Item'].str.contains(busca_txt)) | 
            (df_exibir['Descrição'].str.lower().str.contains(busca_txt))
        ]
    
    st.dataframe(
        df_exibir[['Item', 'Descrição', 'Categoria', 'Embalagem', 'Saldo_Atual']], 
        use_container_width=True, 
        hide_index=True
    )

# ABA 2: HISTÓRICO
with abas[1]:
    st.subheader("Histórico Recente")
    if not df_m.empty:
        # Ordena pelo ID (que é timestamp) decrescente
        st.dataframe(df_m.sort_values(by='id', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma movimentação encontrada.")

# ABA 3: LANÇAR MOVIMENTO COM FILTRO INTELIGENTE
with abas[2]:
    st.subheader("Novo Lançamento")
    
    # Filtro prévio para não poluir o selectbox
    c1, c2 = st.columns([1, 2])
    with c1:
        l_cat = st.selectbox("1. Escolha a Categoria", ["Todas"] + sorted(df_p['Categoria'].unique().tolist()))
    with c2:
        l_busca = st.text_input("2. Digite código ou nome p/ filtrar").strip().lower()
    
    # Filtragem dos produtos para o selectbox
    df_lanca = df_p.copy()
    if l_cat != "Todas":
        df_lanca = df_lanca[df_lanca['Categoria'] == l_cat]
    if l_busca:
        df_lanca = df_lanca[
            (df_lanca['Item'].str.contains(l_busca)) | 
            (df_lanca['Descrição'].str.lower().str.contains(l_busca))
        ]
    
    if not df_lanca.empty:
        opcoes = (df_lanca['Item'] + " - " + df_lanca['Descrição']).tolist()
        
        with st.form("form_estoque", clear_on_submit=True):
            item_sel = st.selectbox("3. Selecione o Produto", opcoes)
            col_t, col_q, col_o = st.columns([1,1,2])
            
            tipo = col_t.selectbox("Tipo", ["Entrada", "Saída"])
            qtd = col_q.number_input("Qtd", min_value=0.1, step=1.0)
            obs = col_o.text_input("Obs/Motivo")
            
            if st.form_submit_button("Confirmar Lançamento", use_container_width=True):
                c_item = item_sel.split(" - ")[0]
                d_item = item_sel.split(" - ")[1]
                
                novo_mov = pd.DataFrame([{
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "codigo": str(c_item),
                    "descricao": d_item,
                    "tipo": tipo,
                    "quantidade": float(qtd),
                    "usuario": usuario_atual,
                    "obs": obs
                }])
                
                # Update na planilha
                df_m_final = pd.concat([df_m, novo_mov], ignore_index=True)
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", data=df_m_final)
                
                st.cache_data.clear()
                st.success(f"✅ Lançamento de {tipo} realizado com sucesso!")
                st.rerun()
    else:
        st.warning("Nenhum item corresponde aos filtros.")

# ABA 4: CADASTRAR NOVO ITEM (NOVA FUNCIONALIDADE)
with abas[3]:
    st.subheader("➕ Cadastrar Novo Item")
    st.info("Preencha todos os campos obrigatórios para manter a consistência do estoque.")
    
    # Busca categorias existentes para sugerir + permitir nova
    cats_existentes = sorted(df_p['Categoria'].unique().tolist()) if not df_p.empty else []
    
    with st.form("form_novo_item", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Código/Item - único e obrigatório
            novo_item = st.text_input("Código do Item *", 
                                    placeholder="Ex: PROD-001",
                                    help="Código único de identificação").strip().upper()
            
            # Categoria - selectbox + texto livre
            cat_opcao = st.selectbox("Categoria existente", ["Nova categoria..."] + cats_existentes)
            if cat_opcao == "Nova categoria...":
                nova_categoria = st.text_input("Nova Categoria *", placeholder="Ex: Eletrônicos").strip()
                categoria_final = nova_categoria
            else:
                categoria_final = cat_opcao
        
        with col2:
            # Descrição
            nova_descricao = st.text_input("Descrição *", 
                                         placeholder="Ex: Smartphone Samsung Galaxy").strip()
            
            # Embalagem/Unidade
            nova_embalagem = st.selectbox("Embalagem/Unidade *", 
                                        ["UN", "CX", "KG", "LT", "MT", "PC", "PAR", "RL", "FD", "OUTRO"])
            if nova_embalagem == "OUTRO":
                nova_embalagem = st.text_input("Especifique a unidade").strip().upper()
            
            # Estoque Inicial (padrão 0)
            estoque_inicial = st.number_input("Estoque Inicial", 
                                            min_value=0.0, 
                                            value=0.0, 
                                            step=1.0,
                                            help="Quantidade inicial em estoque (padrão: 0)")
        
        # Validação visual
        st.markdown("---")
        st.caption("Campos marcados com * são obrigatórios")
        
        submitted = st.form_submit_button("💾 Salvar Novo Item", use_container_width=True, type="primary")
        
        if submitted:
            # VALIDAÇÕES DE CONSISTÊNCIA
            erros = []
            
            if not novo_item:
                erros.append("O Código do Item é obrigatório")
            elif novo_item in df_p['Item'].values:
                erros.append(f"O código '{novo_item}' já existe no cadastro")
            
            if not categoria_final:
                erros.append("A Categoria é obrigatória")
            
            if not nova_descricao:
                erros.append("A Descrição é obrigatória")
            
            if not nova_embalagem:
                erros.append("A Embalagem/Unidade é obrigatória")
            
            if erros:
                for erro in erros:
                    st.error(f"❌ {erro}")
            else:
                try:
                    # Cria o novo registro
                    novo_produto = pd.DataFrame([{
                        "Item": str(novo_item),
                        "Descrição": str(nova_descricao),
                        "Categoria": str(categoria_final),
                        "Embalagem": str(nova_embalagem),
                        "Estoque_Inicial": float(estoque_inicial)
                    }])
                    
                    # Concatena com os dados existentes
                    df_p_novo = pd.concat([df_p, novo_produto], ignore_index=True)
                    
                    # Atualiza a planilha
                    conn.update(spreadsheet=URL_PLANILHA, worksheet="Produtos", data=df_p_novo)
                    
                    # Limpa cache e recarrega
                    st.cache_data.clear()
                    
                    st.success(f"✅ Item '{novo_item} - {nova_descricao}' cadastrado com sucesso!")
                    st.balloons()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao salvar na planilha: {e}")

# ABA 5: ADMIN (se for admin)
if nivel_usuario == "admin":
    with abas[4]:
        st.subheader("🛠️ Gerenciamento Administrativo")
        
        # Seção para exclusão de movimentações
        st.markdown("### 🗑️ Excluir Movimentação")
        if not df_m.empty:
            id_del = st.selectbox("Selecione ID para excluir", df_m['id'].unique().tolist())
            if st.button("❌ EXCLUIR REGISTRO", type="primary"):
                df_m_nova = df_m[df_m['id'] != id_del]
                conn.update(spreadsheet=URL_PLANILHA, worksheet="Movimentacoes", data=df_m_nova)
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("Nenhuma movimentação para excluir.")
        
        st.markdown("---")
        
        # Seção para editar/excluir produtos (extra)
        st.markdown("### 📝 Editar/Excluir Produto")
        if not df_p.empty:
            item_edit = st.selectbox("Selecione o produto", 
                                   (df_p['Item'] + " - " + df_p['Descrição']).tolist())
            
            if item_edit:
                codigo_edit = item_edit.split(" - ")[0]
                produto_atual = df_p[df_p['Item'] == codigo_edit].iloc[0]
                
                with st.expander("Editar Produto"):
                    nova_desc = st.text_input("Descrição", value=produto_atual['Descrição'])
                    nova_cat = st.text_input("Categoria", value=produto_atual['Categoria'])
                    nova_emb = st.text_input("Embalagem", value=produto_atual['Embalagem'])
                    
                    col_salvar, col_excluir = st.columns(2)
                    
                    with col_salvar:
                        if st.button("💾 Atualizar Produto"):
                            df_p.loc[df_p['Item'] == codigo_edit, 'Descrição'] = nova_desc
                            df_p.loc[df_p['Item'] == codigo_edit, 'Categoria'] = nova_cat
                            df_p.loc[df_p['Item'] == codigo_edit, 'Embalagem'] = nova_emb
                            
                            conn.update(spreadsheet=URL_PLANILHA, worksheet="Produtos", data=df_p)
                            st.cache_data.clear()
                            st.success("Produto atualizado!")
                            st.rerun()
                    
                    with col_excluir:
                        # Verifica se há movimentações antes de permitir exclusão
                        tem_movimentacao = codigo_edit in df_m['codigo'].values if not df_m.empty else False
                        
                        if tem_movimentacao:
                            st.warning("⚠️ Este item possui movimentações no histórico. Não é possível excluir.")
                        else:
                            if st.button("🗑️ Excluir Produto", type="secondary"):
                                df_p_novo = df_p[df_p['Item'] != codigo_edit]
                                conn.update(spreadsheet=URL_PLANILHA, worksheet="Produtos", data=df_p_novo)
                                st.cache_data.clear()
                                st.success("Produto excluído!")
                                st.rerun()
