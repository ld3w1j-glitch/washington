import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io

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

# --- FUNÇÃO PARA GERAR ETIQUETA (APENAS QR + DESCRIÇÃO) ---
def gerar_etiqueta(codigo, descricao, tamanho="media"):
    """
    Gera etiqueta minimalista: apenas QR Code + Descrição centralizada
    """
    
    # Configurações de tamanho (em pixels, 200 DPI)
    tamanhos = {
        "pequena": (236, 118),   # 30x15mm
        "media": (394, 177),     # 50x22.5mm (altura reduzida)  
        "grande": (591, 236)     # 75x30mm
    }
    
    largura, altura = tamanhos.get(tamanho, tamanhos["media"])
    
    # Criar QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(codigo)
    qr.make(fit=True)
    
    # Converter QR Code para imagem PIL
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # QR Code ocupa 85% da altura da etiqueta
    qr_tamanho = int(altura * 0.85)
    qr_img = qr_img.resize((qr_tamanho, qr_tamanho), Image.Resampling.LANCZOS)
    
    # Criar imagem da etiqueta
    etiqueta = Image.new('RGB', (largura, altura), 'white')
    draw = ImageDraw.Draw(etiqueta)
    
    # Colar QR Code à esquerda (centralizado verticalmente)
    qr_pos_x = 8
    qr_pos_y = (altura - qr_tamanho) // 2
    etiqueta.paste(qr_img, (qr_pos_x, qr_pos_y))
    
    # Área disponível para texto (à direita do QR Code)
    area_texto_x = qr_pos_x + qr_tamanho + 10
    area_texto_largura = largura - area_texto_x - 8
    
    # Fonte proporcional ao tamanho da etiqueta
    try:
        if tamanho == "pequena":
            fonte_desc = ImageFont.truetype("arialbd.ttf", 10)
        elif tamanho == "media":
            fonte_desc = ImageFont.truetype("arialbd.ttf", 14)
        else:  # grande
            fonte_desc = ImageFont.truetype("arialbd.ttf", 18)
    except:
        fonte_desc = ImageFont.load_default()
    
    # Quebrar descrição em múltiplas linhas se necessário
    max_chars = 15 if tamanho == "pequena" else 25 if tamanho == "media" else 40
    palavras = descricao.split()
    linhas = []
    linha_atual = ""
    
    for palavra in palavras:
        if len(linha_atual + " " + palavra) <= max_chars:
            linha_atual += " " + palavra if linha_atual else palavra
        else:
            if linha_atual:
                linhas.append(linha_atual)
            linha_atual = palavra
    
    if linha_atual:
        linhas.append(linha_atual)
    
    # Limitar número de linhas conforme altura
    max_linhas = 2 if tamanho == "pequena" else 3 if tamanho == "media" else 4
    linhas = linhas[:max_linhas]
    
    # Se ainda houver texto, adicionar reticências na última linha
    if len(descricao) > sum(len(l) for l in linhas) + len(linhas) - 1:
        if linhas:
            linhas[-1] = linhas[-1][:max_chars-3] + "..."
    
    # Calcular altura total do texto para centralização vertical
    bbox = draw.textbbox((0, 0), "Ay", font=fonte_desc)  # Referência para altura
    altura_linha = bbox[3] - bbox[1]
    espacamento = 2  # Espaço entre linhas
    altura_total_texto = len(linhas) * altura_linha + (len(linhas) - 1) * espacamento
    
    # Posição Y inicial (centralizada verticalmente)
    y_inicial = (altura - altura_total_texto) // 2
    
    # Desenhar cada linha centralizada horizontalmente na área de texto
    for i, linha in enumerate(linhas):
        bbox_linha = draw.textbbox((0, 0), linha, font=fonte_desc)
        largura_texto = bbox_linha[2] - bbox_linha[0]
        
        # Centralizar horizontalmente na área disponível
        x_texto = area_texto_x + (area_texto_largura - largura_texto) // 2
        y_texto = y_inicial + i * (altura_linha + espacamento)
        
        draw.text((x_texto, y_texto), linha, fill='black', font=fonte_desc)
    
    # Borda fina
    draw.rectangle([(0, 0), (largura-1, altura-1)], outline='black', width=1)
    
    return etiqueta

# --- INTERFACE POR ABAS ---
abas_nomes = ["📊 Saldo Atual", "📜 Histórico", "🔄 Lançar Movimento", "➕ Cadastrar/Editar Item", "🏷️ Gerar Etiqueta"]
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

# ABA 4: CADASTRAR/EDITAR ITEM (COM AMBAS FUNCIONALIDADES)
with abas[3]:
    st.subheader("➕ Cadastrar / ✏️ Editar Item")
    
    # Escolher entre cadastrar novo ou editar existente
    modo = st.radio("Selecione a ação:", ["Cadastrar Novo Item", "Editar Item Existente"], horizontal=True)
    
    cats_existentes = sorted(df_p['Categoria'].unique().tolist()) if not df_p.empty else []
    
    if modo == "Cadastrar Novo Item":
        st.info("Preencha os dados para cadastrar um novo item no estoque.")
        
        with st.form("form_novo_item", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Código/Item - único e obrigatório
                novo_item = st.text_input("Código do Item *", 
                                        placeholder="Ex: PROD-001",
                                        help="Código único de identificação").strip().upper()
                
                # Categoria - selectbox + texto livre
                cat_opcao = st.selectbox("Categoria", ["Nova categoria..."] + cats_existentes)
                nova_categoria = st.text_input("Nova Categoria (se selecionado acima)", placeholder="Ex: Eletrônicos").strip()
            
            with col2:
                # Descrição
                nova_descricao = st.text_input("Descrição *", 
                                             placeholder="Ex: Smartphone Samsung Galaxy").strip()
                
                # Embalagem/Unidade
                nova_embalagem = st.selectbox("Embalagem/Unidade *", 
                                            ["UN", "CX", "KG", "LT", "MT", "PC", "PAR", "RL", "FD", "OUTRO"])
                especifique_emb = st.text_input("Especifique (quantidade/embalagem)", placeholder="Ex: PT").strip().upper()
                
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
                # Definir valores finais
                categoria_final = nova_categoria if cat_opcao == "Nova categoria..." else cat_opcao
                embalagem_final = especifique_emb if nova_embalagem == "OUTRO" else nova_embalagem
                
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
                
                if not embalagem_final:
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
                            "Embalagem": str(embalagem_final),
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
    
    else:  # Modo Editar
        st.info("Selecione o item que deseja editar.")
        
        if not df_p.empty:
            # Selecionar item para editar (fora do form para atualizar os valores padrão)
            opcoes_edit = (df_p['Item'] + " - " + df_p['Descrição']).tolist()
            item_para_editar = st.selectbox("Selecione o item para editar", opcoes_edit, key="edit_select")
            
            if item_para_editar:
                codigo_edit = item_para_editar.split(" - ")[0]
                produto_atual = df_p[df_p['Item'] == codigo_edit].iloc[0]
                
                # Verifica se tem movimentações
                tem_movimentacao = codigo_edit in df_m['codigo'].values if not df_m.empty else False
                
                st.markdown("---")
                st.subheader(f"Editando: {codigo_edit}")
                
                if tem_movimentacao:
                    st.warning("⚠️ Este item possui movimentações no histórico. Exclusão desabilitada.", icon="ℹ️")
                
                # INICIALIZAR VALORES DEFAULT NO SESSION STATE PARA EVITAR ERROS
                if 'edit_cat_opcao' not in st.session_state:
                    st.session_state.edit_cat_opcao = produto_atual['Categoria'] if produto_atual['Categoria'] in cats_existentes else "Nova categoria..."
                
                with st.form("form_editar_item", clear_on_submit=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Código (somente leitura)
                        st.text_input("Código do Item", value=str(produto_atual['Item']), disabled=True, help="Código não pode ser alterado")
                        
                        # Categoria
                        cat_atual = str(produto_atual['Categoria'])
                        cat_options = ["Nova categoria..."] + cats_existentes
                        
                        # Determinar índice correto
                        if cat_atual in cats_existentes:
                            cat_index = cat_options.index(cat_atual)
                        else:
                            cat_index = 0
                            
                        cat_opcao_edit = st.selectbox("Categoria", cat_options, index=cat_index, key="edit_cat_select")
                        
                        # Campo de nova categoria (sempre visível mas apenas usado se necessário)
                        default_nova_cat = "" if cat_index > 0 else cat_atual
                        nova_categoria_edit = st.text_input("Nova Categoria (se selecionado acima)", value=default_nova_cat).strip()
                    
                    with col2:
                        # Descrição
                        descricao_edit = st.text_input("Descrição *", value=str(produto_atual['Descrição'])).strip()
                        
                        # Embalagem
                        emb_atual = str(produto_atual['Embalagem'])
                        opcoes_emb = ["UN", "CX", "KG", "LT", "MT", "PC", "PAR", "RL", "FD", "OUTRO"]
                        
                        try:
                            idx_emb = opcoes_emb.index(emb_atual)
                        except ValueError:
                            idx_emb = 9  # OUTRO
                        
                        embalagem_edit = st.selectbox("Embalagem/Unidade", opcoes_emb, index=idx_emb)
                        
                        # Campo específico para OUTRO
                        default_especifique = emb_atual if idx_emb == 9 else ""
                        especifique_emb_edit = st.text_input("Especifique (emb)", value=default_especifique).strip().upper()
                        
                        # Estoque Inicial com tratamento de erro
                        try:
                            estoque_val = float(produto_atual['Estoque_Inicial']) if pd.notna(produto_atual['Estoque_Inicial']) else 0.0
                        except:
                            estoque_val = 0.0
                            
                        estoque_edit = st.number_input("Estoque Inicial", 
                                                     min_value=0.0, 
                                                     value=estoque_val, 
                                                     step=1.0,
                                                     help="Altere apenas se necessário corrigir o valor inicial")
                    
                    # Botão de submit ÚNICO E OBRIGATÓRIO - SEMPRE PRESENTE
                    st.markdown("---")
                    submitted = st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary")
                    
                    if submitted:
                        # Definir valores finais
                        categoria_final_edit = nova_categoria_edit if cat_opcao_edit == "Nova categoria..." else cat_opcao_edit
                        embalagem_final_edit = especifique_emb_edit if embalagem_edit == "OUTRO" else embalagem_edit
                        
                        # Validações
                        erros = []
                        if not descricao_edit:
                            erros.append("A Descrição é obrigatória")
                        if not categoria_final_edit:
                            erros.append("A Categoria é obrigatória")
                        if not embalagem_final_edit:
                            erros.append("A Embalagem é obrigatória")
                        
                        if erros:
                            for erro in erros:
                                st.error(f"❌ {erro}")
                        else:
                            try:
                                # Atualiza o dataframe
                                idx = df_p.index[df_p['Item'] == codigo_edit].tolist()[0]
                                df_p.at[idx, 'Descrição'] = str(descricao_edit)
                                df_p.at[idx, 'Categoria'] = str(categoria_final_edit)
                                df_p.at[idx, 'Embalagem'] = str(embalagem_final_edit)
                                df_p.at[idx, 'Estoque_Inicial'] = float(estoque_edit)
                                
                                # Salva na planilha
                                conn.update(spreadsheet=URL_PLANILHA, worksheet="Produtos", data=df_p)
                                st.cache_data.clear()
                                st.success(f"✅ Item '{codigo_edit}' atualizado com sucesso!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao atualizar: {e}")
                
                # SEÇÃO DE EXCLUSÃO (FORA DO FORM)
                if not tem_movimentacao:
                    st.markdown("---")
                    st.markdown("### 🗑️ Zona de Perigo")
                    st.error("⚠️ Atenção: A exclusão não pode ser desfeita!", icon="⚠️")
                    
                    with st.form("form_excluir_item", clear_on_submit=False):
                        st.write(f"Você está prestes a excluir: **{codigo_edit} - {produto_atual['Descrição']}**")
                        confirmacao = st.checkbox("Confirmo que desejo excluir este item permanentemente")
                        
                        # Botão de excluir em form separado
                        excluir_submit = st.form_submit_button("🗑️ EXCLUIR ITEM DEFINITIVAMENTE", type="primary", use_container_width=True)
                        
                        if excluir_submit and confirmacao:
                            try:
                                df_p_novo = df_p[df_p['Item'] != codigo_edit]
                                conn.update(spreadsheet=URL_PLANILHA, worksheet="Produtos", data=df_p_novo)
                                st.cache_data.clear()
                                st.success(f"✅ Item '{codigo_edit}' excluído com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao excluir: {e}")
                        elif excluir_submit and not confirmacao:
                            st.error("❌ Você precisa confirmar a exclusão marcando a checkbox!")
        else:
            st.warning("Não há itens cadastrados para editar.")

# ABA 5: GERAR ETIQUETA COM QR CODE
with abas[4]:
    st.subheader("🏷️ Gerador de Etiquetas com QR Code")
    
    # Layout em colunas para filtros e preview
    col_filtros, col_preview = st.columns([1, 2])
    
    with col_filtros:
        st.markdown("### 1. Selecione o Item")
        
        # Filtros para encontrar o item
        e_cat = st.selectbox("Filtrar por Categoria", 
                            ["Todas"] + sorted(df_p['Categoria'].unique().tolist()),
                            key="etq_cat")
        e_busca = st.text_input("Buscar código ou descrição", 
                               key="etq_busca").strip().lower()
        
        # Filtrar dataframe
        df_etq = df_p.copy()
        if e_cat != "Todas":
            df_etq = df_etq[df_etq['Categoria'] == e_cat]
        if e_busca:
            df_etq = df_etq[
                (df_etq['Item'].str.contains(e_busca)) | 
                (df_etq['Descrição'].str.lower().str.contains(e_busca))
            ]
        
        if not df_etq.empty:
            opcoes_etq = (df_etq['Item'] + " - " + df_etq['Descrição']).tolist()
            item_etq_sel = st.selectbox("Selecione o produto", opcoes_etq, key="etq_sel")
            
            # Configurações da etiqueta
            st.markdown("### 2. Configurações")
            tamanho_etq = st.selectbox(
                "Tamanho da Etiqueta",
                ["pequena (30x15mm)", "media (50x22mm)", "grande (75x30mm)"],
                index=1
            )
            
            # Quantidade de cópias
            qtd_copias = st.number_input("Quantidade", min_value=1, max_value=50, value=1)
            
            # Botão gerar
            gerar = st.button("🖨️ Gerar Etiqueta(s)", type="primary", use_container_width=True)
        else:
            st.warning("Nenhum item encontrado.")
            gerar = False
            item_etq_sel = None
    
    with col_preview:
        if gerar and item_etq_sel:
            # Extrair código e descrição
            codigo_etq = item_etq_sel.split(" - ")[0]
            produto_info = df_p[df_p['Item'] == codigo_etq].iloc[0]
            
            descricao_etq = produto_info['Descrição']
            
            # Mapear tamanho selecionado
            tamanho_map = {
                "pequena (30x15mm)": "pequena",
                "media (50x22mm)": "media", 
                "grande (75x30mm)": "grande"
            }
            tam_selecionado = tamanho_map[tamanho_etq]
            
            # Gerar etiquetas
            etiquetas_geradas = []
            for i in range(qtd_copias):
                img_etiqueta = gerar_etiqueta(
                    codigo_etq, 
                    descricao_etq, 
                    tam_selecionado
                )
                etiquetas_geradas.append(img_etiqueta)
            
            # Exibir preview
            with st.container():
                st.markdown("### Preview")
                st.image(etiquetas_geradas[0], width=400)
            
            # Botões de download
            col_down1, col_down2 = st.columns(2)
            
            with col_down1:
                # Download individual
                buf = io.BytesIO()
                etiquetas_geradas[0].save(buf, format='PNG')
                buf.seek(0)
                
                st.download_button(
                    label="📥 PNG",
                    data=buf,
                    file_name=f"etiqueta_{codigo_etq}.png",
                    mime="image/png",
                    use_container_width=True
                )
            
            with col_down2:
                # Se múltiplas etiquetas, criar ZIP
                if qtd_copias > 1:
                    import zipfile
                    
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for idx, img in enumerate(etiquetas_geradas):
                            img_buf = io.BytesIO()
                            img.save(img_buf, format='PNG')
                            img_buf.seek(0)
                            zip_file.writestr(f"etiqueta_{codigo_etq}_{idx+1}.png", img_buf.getvalue())
                    
                    zip_buf.seek(0)
                    st.download_button(
                        label=f"📦 ZIP ({qtd_copias})",
                        data=zip_buf,
                        file_name=f"etiquetas_{codigo_etq}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

# ABA 6: ADMIN (se for admin) - Índice muda para 5
if nivel_usuario == "admin":
    with abas[5]:
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
        
        # Seção para editar/excluir produtos (mantida para admins, mas agora redundante com a aba 4)
        st.markdown("### 📝 Gerenciar Produtos (Admin)")
        st.info("Use a aba 'Cadastrar/Editar Item' para editar produtos de forma mais prática.")
