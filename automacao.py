import streamlit as st
import pyautogui
import time

# 1. BLOQUEIO DE SEGURANÇA
if "logado" not in st.session_state or not st.session_state.logado:
    st.error("Acesso negado.")
    st.stop()

st.title("🤖 Automação de Tarefas")
st.info("Aviso: Esta automação controla o mouse e teclado do servidor local.")

# 2. CAMPOS DE CONFIGURAÇÃO
with st.container(border=True):
    st.subheader("Configurar Automação")
    texto_para_digitar = st.text_input("Texto para digitar:")
    delay = st.slider("Aguardar quantos segundos antes de começar?", 1, 10, 3)

# 3. BOTÃO DE EXECUÇÃO
if st.button("🚀 Iniciar Automação", use_container_width=True):
    st.warning(f"A automação começará em {delay} segundos. Vá para a janela desejada!")
    
    # Contagem regressiva no Streamlit
    progress_bar = st.progress(0)
    for i in range(delay):
        time.sleep(1)
        progress_bar.progress((i + 1) / delay)
    
    try:
        # EXEMPLO DE TAREFA: 
        # 1. Clicar em algum lugar (você precisaria das coordenadas X, Y)
        # pyautogui.click(x=100, y=200)
        
        # 2. Digitar o texto
        pyautogui.write(texto_para_digitar, interval=0.1)
        
        # 3. Apertar Enter
        pyautogui.press('enter')
        
        st.success("✅ Tarefa concluída!")
    except Exception as e:
        st.error(f"Erro na automação: {e}")

# Sidebar
st.sidebar.divider()
st.sidebar.page_link("app.py", label="Voltar ao Início", icon="🏠")
