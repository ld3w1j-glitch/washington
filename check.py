import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd  # FALTAVA ESTE IMPORT!

st.title("🔍 Diagnóstico de Ligação")

# 1. Verificar se o segredo existe
if "connections" not in st.secrets:
    st.error("❌ O Streamlit não encontrou a pasta .streamlit ou o ficheiro secrets.toml!")
    st.write("Verifique se o nome da pasta tem o PONTO no início: `.streamlit`")
else:
    st.success("✅ Pasta .streamlit e ficheiro secrets.toml encontrados!")
    
    # 2. Verificar se os campos da Service Account estão lá
    try:
        creds = st.secrets["connections"]["gsheets"]
        if "private_key" in creds and "client_email" in creds:
            st.success(f"✅ Credenciais lidas com sucesso para: {creds['client_email']}")
        else:
            st.warning("⚠️ O ficheiro secrets.toml existe, mas faltam campos (private_key ou client_email).")
    except Exception as e:
        st.error(f"❌ Erro ao ler campos do secrets.toml: {e}")

# 3. Teste de Leitura da aba Usuarios
st.divider()
st.subheader("Teste de Leitura da aba 'Usuarios'")

url = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"

if st.button("Testar Conexão Agora"):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=url, worksheet="Usuarios")
        st.success("✅ CONEXÃO BEM-SUCEDIDA!")
        st.write("Dados encontrados na aba Usuarios:")
        st.dataframe(df)
    except Exception as e:
        st.error(f"❌ Falha na conexão: {e}")
        st.info("💡 Dica: Se o erro mencionar 'WorksheetNotFound', crie a aba 'Usuarios' na planilha.")
