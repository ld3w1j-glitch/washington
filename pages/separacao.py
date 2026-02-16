import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime
import io
import zipfile

# 1. SEGURANÇA E INICIALIZAÇÃO
if "logado" not in st.session_state or not st.session_state["logado"]:
    st.error("Por favor, faça login na página principal.")
    st.stop()

# Estados da sessão
if "lojas_fixas" not in st.session_state: st.session_state.lojas_fixas = []
if "index_conf" not in st.session_state: st.session_state.index_conf = 0
if "modo_conferencia" not in st.session_state: st.session_state.modo_conferencia = False
if "historico_conferido" not in st.session_state: st.session_state.historico_conferido = []
if "itens_finalizados" not in st.session_state: st.session_state.itens_finalizados = set()

# --- CSS PERSONALIZADO (ABAS COM LINHA VERMELHA) ---
st.markdown("""
    <style>
    /* Estilização das Abas (Tabs) */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre; background-color: transparent;
        color: #808495; font-size: 18px; font-weight: 400; border: none;
    }
    .stTabs [aria-selected="true"] {
        color: #FF4B4B !important; font-weight: bold !important;
        border-bottom: 3px solid #FF4B4B !important;
    }
    .stTabs [data-baseweb="tab-border"] { display: none; }

    /* Botões e Cards */
    button[kind="primary"] { background-color: #2ecc71 !important; color: black !important; border: none !important; }
    button[kind="secondary"] { background-color: #262730 !important; color: white !important; border: 1px solid #454754 !important; }
    button[key^="btn_Loja"] { height: 110px !important; border-radius: 12px !important; font-weight: bold !important; white-space: pre-wrap !important; }
    .card-hist { background-color: #1e2130; border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #FF4B4B; }
    </style>
""", unsafe_allow_html=True)

# 2. CONEXÃO E DADOS
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2)
def carregar_dados():
    df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Pedidos").fillna("")
    df['item_codigo'] = df['item_codigo'].astype(str)
    return df

df_principal = carregar_dados()

# --- NAVEGAÇÃO POR ABAS ---
tab_sep, tab_hist = st.tabs(["🟦 Montar Pedido", "📜 Gestão e Envio"])

# ==========================================
# ABA 1: MONTAR PEDIDO (SEPARAÇÃO)
# ==========================================
with tab_sep:
    if st.session_state.modo_conferencia:
        if st.button("⬅️ Voltar para a Grade", type="secondary"):
            st.session_state.modo_conferencia = False
            st.rerun()

        dados_it = st.session_state.dados_para_conferir
        lojas_com_itens = dados_it[dados_it['qtd_final'] > 0].to_dict('records')
        idx = st.session_state.index_conf
        loja_atual = lojas_com_itens[idx]
        
        st.markdown(f"""<div style="background-color:#2ecc71; padding:40px; border-radius:20px; text-align:center; color:black; margin-top:10px;">
            <h1 style="margin:0;">{loja_atual['loja']}</h1>
            <p style="font-size:20px; font-weight:bold;">SEPARAR AGORA:</p>
            <h1 style="font-size:120px; margin:0; line-height:1;">{int(loja_atual['qtd_final'])}</h1>
        </div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button("⬅️ ANTERIOR", use_container_width=True) and idx > 0:
            st.session_state.index_conf -= 1; st.rerun()
            
        if idx < len(lojas_com_itens) - 1:
            if c2.button("PRÓXIMO ➡️", use_container_width=True):
                st.session_state.index_conf += 1; st.rerun()
        else:
            if c2.button("✅ FINALIZAR ITEM", type="primary", use_container_width=True):
                for r in lojas_com_itens:
                    st.session_state.historico_conferido.append({
                        "pedido": r['id_pedido'], "item": r['item_codigo'], "desc": r['descricao'],
                        "loja": r['loja'], "qtd": int(r['qtd_final']), "hora": datetime.now().strftime("%H:%M")
                    })
                st.session_state.itens_finalizados.add(st.session_state.item_codigo_atual)
                st.session_state.modo_conferencia = False
                st.session_state.lojas_fixas = []
                st.rerun()
    else:
        fila = df_principal[(df_principal['status'] == 'Em Separação') & (~df_principal['item_codigo'].isin(st.session_state.itens_finalizados))]
        
        if fila.empty:
            st.success("🎉 Todos os itens foram processados!")
        else:
            c1, c2 = st.columns(2)
            id_foco = c1.selectbox("🎯 Escolha o Pedido:", ["Selecione..."] + sorted(list(fila['id_pedido'].unique())))
            
            if id_foco != "Selecione...":
                itens_ped = fila[fila['id_pedido'] == id_foco]
                item_sel = c2.selectbox("📦 Escolha o Item:", ["Selecione..."] + (itens_ped['item_codigo'] + " - " + itens_ped['descricao']).unique().tolist())
                
                if item_sel != "Selecione...":
                    cod_it = item_sel.split(" - ")[0]
                    dados_it = itens_ped[itens_ped['item_codigo'] == cod_it].copy()
                    
                    total_ped = pd.to_numeric(dados_it['quantidade']).sum()
                    qtd_real = st.number_input("📥 Quantidade Recebida:", min_value=0, value=int(total_ped))
                    
                    soma_fixas = pd.to_numeric(dados_it[dados_it['loja'].isin(st.session_state.lojas_fixas)]['quantidade']).sum()
                    sobra = max(0, qtd_real - soma_fixas)
                    soma_rateio = pd.to_numeric(dados_it[~dados_it['loja'].isin(st.session_state.lojas_fixas)]['quantidade']).sum()
                    fator = sobra / soma_rateio if soma_rateio > 0 else 0
                    
                    dados_it['qtd_final'] = dados_it.apply(lambda x: x['quantidade'] if x['loja'] in st.session_state.lojas_fixas else np.floor(float(x['quantidade']) * fator), axis=1)

                    for r_idx in range(0, 20, 5):
                        cols = st.columns(5)
                        for i in range(5):
                            lj = f"Loja {r_idx + i + 1:02d}"
                            row = dados_it[dados_it['loja'] == lj]
                            with cols[i]:
                                if not row.empty and float(row['quantidade'].iloc[0]) > 0:
                                    fixo = lj in st.session_state.lojas_fixas
                                    q_f = int(dados_it[dados_it['loja'] == lj]['qtd_final'].iloc[0])
                                    q_o = int(row['quantidade'].iloc[0])
                                    label = f"{'✅ FIXO' if fixo else lj}\n\n{q_f}\n\nPed: {q_o}"
                                    if st.button(label, key=f"btn_{lj}", type=("primary" if fixo else "secondary"), use_container_width=True):
                                        if fixo: st.session_state.lojas_fixas.remove(lj)
                                        else: st.session_state.lojas_fixas.append(lj)
                                        st.rerun()
                                else:
                                    st.button(f"{lj}\n\n-\n\n0", key=f"{lj}_vazio", disabled=True, use_container_width=True)

                    if st.button("🔍 INICIAR CONFERÊNCIA", type="primary", use_container_width=True):
                        st.session_state.modo_conferencia = True
                        st.session_state.index_conf = 0
                        st.session_state.dados_para_conferir = dados_it
                        st.session_state.item_codigo_atual = cod_it
                        st.rerun()

# ==========================================
# ABA 2: GESTÃO E ENVIO (EXCEL E TXT)
# ==========================================
with tab_hist:
    if not st.session_state.historico_conferido:
        st.info("Nenhum item finalizado no momento.")
    else:
        df_h = pd.DataFrame(st.session_state.historico_conferido)
        
        for pid in df_h['pedido'].unique():
            with st.container():
                st.markdown(f'<div class="card-hist"><b>🚚 PEDIDO: {pid}</b></div>', unsafe_allow_html=True)
                c1, c2, _ = st.columns([1,1,2])
                if c1.button("✏️ EDITAR", key=f"ed_{pid}"):
                    st.session_state.historico_conferido = [r for r in st.session_state.historico_conferido if r['pedido'] != pid]
                    st.rerun()
                if c2.button("🗑️ EXCLUIR", key=f"del_{pid}"):
                    st.session_state.historico_conferido = [r for r in st.session_state.historico_conferido if r['pedido'] != pid]
                    st.rerun()

        st.divider()
        st.subheader("🏁 Exportar Relatórios")

        # 1. FUNÇÃO EXCEL ORGANIZADO (COLUNAS: COD | DESC | LOJA 1 | LOJA 2...)
        def gerar_excel(df):
            df_pivot = df.pivot_table(index=['item', 'desc'], columns='loja', values='qtd', aggfunc='sum').reset_index().fillna(0)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_pivot.to_excel(writer, index=False, sheet_name='Relatorio')
            return output.getvalue()

        # 2. FUNÇÃO ZIP INDIVIDUAL
        def gerar_zip(df):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for lj in df['loja'].unique():
                    d = df[df['loja'] == lj]
                    txt = f"LOJA: {lj}\n" + "-"*25 + "\n"
                    for _, r in d.iterrows():
                        txt += f"ITEM: {r['item']} | DESC: {r['desc']} | QTD: {r['qtd']}\n"
                    z.writestr(f"{lj}.txt", txt)
            return buf.getvalue()

        col_ex1, col_ex2 = st.columns(2)
        col_ex1.download_button("📊 Baixar Planilha (Excel)", data=gerar_excel(df_h), file_name=f"separacao_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)
        col_ex2.download_button("📥 Baixar TXTs (ZIP)", data=gerar_zip(df_h), file_name="lojas_individual.zip", use_container_width=True)