import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# ==================== CONFIGURAÇÃO VISUAL & CORES ====================
st.set_page_config(page_title="Flash Stop - Gestão Total", layout="wide", page_icon="⚡")

# Definição de Cores Flash Stop
verde_flash = "#7CFC00"
preto_fundo = "#0A0A0A"

st.markdown(f"""
    <style>
        /* Fundo do App */
        .stApp {{ background-color: {preto_fundo}; color: white; }}
        
        /* Títulos e Subtítulos */
        h1, h2, h3, h4 {{ color: {verde_flash} !important; font-family: 'Arial Black', sans-serif; }}
        
        /* Botões Estilizados */
        div.stButton > button {{
            width: 100%;
            height: 3.5em;
            background-color: {verde_flash};
            color: black;
            font-weight: bold;
            border-radius: 10px;
            border: none;
            transition: 0.3s;
        }}
        div.stButton > button:hover {{
            background-color: #A3E635;
            transform: scale(1.02);
        }}
        
        /* Inputs e Sidebar */
        .stTextInput>div>div>input, .stNumberInput>div>div>input {{
            background-color: #1A1A1A;
            color: white;
            border: 1px solid {verde_flash};
        }}
        [data-testid="stSidebar"] {{
            background-color: #111111;
            border-right: 1px solid {verde_flash};
        }}
    </style>
""", unsafe_allow_html=True)

# ==================== CONEXÃO & FUNÇÕES ====================
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_aba(nome_aba):
    try:
        df = conn.read(worksheet=nome_aba)
        return df.dropna(how='all')
    except:
        return pd.DataFrame()

# ==================== LOGIN & LOGO ====================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# Logo (Usando o link que você forneceu anteriormente ou placeholder)
logo_url = "https://i.imgur.com/8Qj8jN4.png" # Certifique-se que este link está ativo

if not st.session_state.autenticado:
    col_l1, col_l2, col_l3 = st.columns([1,2,1])
    with col_l2:
        st.image(logo_url, width=300)
        st.title("⚡ Acesso Restrito")
        with st.form("login"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("ENTRAR NO SISTEMA"):
                if u == "admin" and s == "flash123":
                    st.session_state.autenticado = True
                    st.session_state.nome_usuario = u
                    st.rerun()
                else:
                    st.error("Credenciais inválidas")
    st.stop()

# ==================== MENU LATERAL ====================
st.sidebar.image(logo_url, width=150)
st.sidebar.markdown(f"👤 **{st.session_state.nome_usuario.upper()}**")
menu = st.sidebar.radio("⚡ NAVEGAÇÃO", 
    ["📊 Dashboard & Alertas", "🛍️ Venda (PDV)", "📋 Relatórios Contábeis", "📦 Gestão de Stock", "📍 Cadastrar PDV", "📟 Máquinas (Automação)"])

# ==================== 1. DASHBOARD & ALERTAS ====================
if menu == "📊 Dashboard & Alertas":
    st.header("📊 Painel de Controle Flash Stop")
    produtos = carregar_aba("produtos")
    
    if not produtos.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📉 Alertas de Stock")
            produtos['estoque'] = pd.to_numeric(produtos['estoque'], errors='coerce').fillna(0)
            baixo = produtos[produtos['estoque'] < 5]
            if not baixo.empty:
                for _, p in baixo.iterrows(): st.error(f"Repor: {p['nome']} ({int(p['estoque'])} un)")
            else: st.success("Stock em dia!")
        
        with c2:
            st.subheader("📅 Validades")
            produtos['validade_dt'] = pd.to_datetime(produtos['validade'], format='%d/%m/%Y', errors='coerce')
            vencidos = produtos[produtos['validade_dt'] < datetime.now()]
            if not vencidos.empty:
                for _, p in vencidos.iterrows(): st.warning(f"VENCIDO: {p['nome']}")
            else: st.success("Tudo na validade!")
            
    vendas = carregar_aba("vendas")
    if not vendas.empty:
        st.divider()
        st.subheader("🏆 Faturamento por Unidade")
        st.bar_chart(vendas.groupby('pdv')['valor'].sum())

# ==================== 2. VENDA (PDV) ====================
elif menu == "🛍️ Venda (PDV)":
    st.header("🛍️ Frente de Caixa")
    pdvs = carregar_aba("pontos")
    prods = carregar_aba("produtos")
    
    if pdvs.empty or prods.empty:
        st.warning("⚠️ Cadastre PDVs e Produtos primeiro!")
    else:
        with st.form("venda_f"):
            pdv_sel = st.selectbox("📍 PDV", pdvs['nome'].tolist())
            prod_sel = st.selectbox("📦 Produto", prods['nome'].tolist())
            qtd = st.number_input("Qtd", min_value=1, value=1)
            forma = st.selectbox("Pagamento", ["Dinheiro", "Pix", "Cartão"])
            
            if st.form_submit_button("CONCLUIR VENDA"):
                idx = prods[prods['nome'] == prod_sel].index[0]
                stock = int(prods.at[idx, 'estoque'])
                if stock >= qtd:
                    venda_df = pd.DataFrame([{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "pdv": pdv_sel, "produto": prod_sel, "valor": float(prods.at[idx, 'preco']) * qtd, "forma": forma}])
                    conn.update(worksheet="vendas", data=pd.concat([carregar_aba("vendas"), venda_df], ignore_index=True))
                    prods.at[idx, 'estoque'] = stock - qtd
                    conn.update(worksheet="produtos", data=prods)
                    st.success("⚡ Venda Registrada com Sucesso!")
                    st.balloons()
                else: st.error("Stock insuficiente!")

# ==================== 3. RELATÓRIOS CONTÁBEIS ====================
elif menu == "📋 Relatórios Contábeis":
    st.header("📋 Contabilidade Flash")
    vendas = carregar_aba("vendas")
    if not vendas.empty:
        pdv_f = st.selectbox("Filtrar por Unidade", ["Todos"] + vendas['pdv'].unique().tolist())
        df = vendas if pdv_f == "Todos" else vendas[vendas['pdv'] == pdv_f]
        st.metric("Total Bruto", f"R$ {df['valor'].sum():.2f}")
        st.dataframe(df, use_container_width=True)
    else: st.info("Sem dados.")

# ==================== 4. CADASTRAR PDV ====================
elif menu == "📍 Cadastrar PDV":
    st.header("📍 Novas Unidades")
    with st.form("c_pdv"):
        n = st.text_input("Nome da Unidade")
        l = st.text_input("Localização")
        if st.form_submit_button("ATIVAR PDV"):
            conn.update(worksheet="pontos", data=pd.concat([carregar_aba("pontos"), pd.DataFrame([{"nome": n, "local": l}])], ignore_index=True))
            st.success("Unidade Cadastrada!")
    st.dataframe(carregar_aba("pontos"))

# ==================== 5. MÁQUINAS (AUTOMAÇÃO) ====================
elif menu == "📟 Máquinas (Automação)":
    st.header("📟 Integração de Maquininhas")
    with st.form("c_maq"):
        n = st.text_input("Nome da Máquina")
        tid = st.text_input("Serial Number (TID)")
        if st.form_submit_button("INTEGRAR"):
            conn.update(worksheet="maquinas", data=pd.concat([carregar_aba("maquinas"), pd.DataFrame([{"nome": n, "tid": tid}])], ignore_index=True))
            st.success("Maquininha conectada ao sistema!")

# ==================== 6. GESTÃO DE STOCK ====================
elif menu == "📦 Gestão de Stock":
    st.header("📦 Inventário")
    with st.expander("➕ Adicionar Produto"):
        with st.form("c_prod"):
            n = st.text_input("Nome")
            e = st.number_input("Estoque", min_value=0)
            v = st.text_input("Validade (DD/MM/AAAA)")
            p = st.number_input("Preço")
            if st.form_submit_button("SALVAR"):
                conn.update(worksheet="produtos", data=pd.concat([carregar_aba("produtos"), pd.DataFrame([{"nome": n, "estoque": e, "validade": v, "preco": p}])], ignore_index=True))
                st.success("Produto Salvo!")
    st.dataframe(carregar_aba("produtos"))
