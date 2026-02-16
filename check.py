import streamlit as st
from streamlit_gsheets import GSheetsConnection

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

# 3. Teste de Escrita Real
st.divider()
st.subheader("Teste de Escrita na Folha")
url = "https://docs.google.com/spreadsheets/d/1lIldvBHzJ3VIczDvZv-WRFtp3R7Jf5yfM2LrIlseshE/edit?usp=sharing"

if st.button("Tentar Escrever Agora"):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        test_data = {"Teste": ["OK"]}
        conn.update(spreadsheet=url, worksheet="Usuarios", data=pd.DataFrame(test_data))
        st.success("🔥 CONSEGUI ESCREVER! A ligação está perfeita.")
    except Exception as e:
        st.error(f"❌ Falha ao escrever: {e}")
        st.info("Se o erro for 'Permission Denied', o problema é a partilha no Google Sheets.")