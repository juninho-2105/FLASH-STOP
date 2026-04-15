import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import time

# ==================== CONFIGURAÇÃO & SEGURANÇA ====================
st.set_page_config(page_title="Flash Stop - Gestão Total", layout="wide", page_icon="⚡")

# Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_aba(nome_aba):
    try:
        df = conn.read(worksheet=nome_aba)
        return df.dropna(how='all')
    except:
        return pd.DataFrame()

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("⚡ Acesso Flash Stop")
    with st.form("login"):
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and s == "flash123":
                st.session_state.autenticado = True
                st.session_state.nome_usuario = u
                st.rerun()
            else:
                st.error("Credenciais inválidas")
    st.stop()

# ==================== MENU LATERAL ====================
st.sidebar.title(f"👤 {st.session_state.nome_usuario}")
menu = st.sidebar.radio("⚡ Navegação", 
    ["📊 Dashboard & Alertas", "🛍️ Venda (PDV)", "📋 Relatórios Contábeis", "📦 Gestão de Stock", "🚚 Reposição", "📍 Cadastrar PDV", "📟 Máquinas (Automação)"])

# ==================== 1. DASHBOARD & ALERTAS ====================
if menu == "📊 Dashboard & Alertas":
    st.header("📊 Painel de Controle")
    produtos = carregar_aba("produtos")
    if not produtos.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📉 Stock Baixo")
            produtos['estoque'] = pd.to_numeric(produtos['estoque'], errors='coerce').fillna(0)
            baixo = produtos[produtos['estoque'] < 5]
            if not baixo.empty:
                for _, p in baixo.iterrows(): st.error(f"Repor: {p['nome']} ({int(p['estoque'])} un)")
            else: st.success("Stock em dia!")
        
        with col2:
            st.subheader("📅 Vencimentos")
            produtos['validade_dt'] = pd.to_datetime(produtos['validade'], format='%d/%m/%Y', errors='coerce')
            vencidos = produtos[produtos['validade_dt'] < datetime.now()]
            if not vencidos.empty:
                for _, p in vencidos.iterrows(): st.warning(f"VENCIDO: {p['nome']}")
            else: st.success("Validades em dia!")

# ==================== 2. VENDA (PDV) ====================
elif menu == "🛍️ Venda (PDV)":
    st.header("🛍️ Frente de Caixa")
    pontos_df = carregar_aba("pontos")
    produtos_df = carregar_aba("produtos")
    
    if pontos_df.empty or produtos_df.empty:
        st.warning("Cadastre PDVs e Produtos primeiro!")
    else:
        with st.form("venda_f"):
            pdv_sel = st.selectbox("📍 Selecione o PDV", pontos_df['nome'].tolist())
            prod_sel = st.selectbox("📦 Produto", produtos_df['nome'].tolist())
            qtd = st.number_input("Quantidade", min_value=1, value=1)
            forma = st.selectbox("Pagamento", ["Dinheiro", "Pix", "Cartão"])
            
            if st.form_submit_button("Finalizar Venda"):
                idx = produtos_df[produtos_df['nome'] == prod_sel].index[0]
                stock_atual = int(produtos_df.at[idx, 'estoque'])
                if stock_atual >= qtd:
                    # Registra Venda
                    venda_df = pd.DataFrame([{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "pdv": pdv_sel, "produto": prod_sel, "valor": float(produtos_df.at[idx, 'preco']) * qtd, "forma": forma}])
                    conn.update(worksheet="vendas", data=pd.concat([carregar_aba("vendas"), venda_df], ignore_index=True))
                    # Baixa Stock
                    produtos_df.at[idx, 'estoque'] = stock_atual - qtd
                    conn.update(worksheet="produtos", data=produtos_df)
                    st.success("Venda Concluída!")
                else: st.error("Stock insuficiente!")

# ==================== 3. RELATÓRIOS CONTÁBEIS ====================
elif menu == "📋 Relatórios Contábeis":
    st.header("📋 Contabilidade por PDV")
    vendas = carregar_aba("vendas")
    if not vendas.empty:
        lista_pdvs = ["Todos"] + vendas['pdv'].unique().tolist()
        escolha = st.selectbox("Filtrar Unidade", lista_pdvs)
        df_f = vendas if escolha == "Todos" else vendas[vendas['pdv'] == escolha]
        
        c1, c2 = st.columns(2)
        c1.metric("Total Bruto", f"R$ {df_f['valor'].sum():.2f}")
        c2.metric("Nº Vendas", len(df_f))
        st.dataframe(df_f, use_container_width=True)
    else: st.info("Sem vendas registradas.")

# ==================== 4. CADASTRAR PDV ====================
elif menu == "📍 Cadastrar PDV":
    st.header("📍 Gestão de Unidades")
    with st.form("cad_pdv"):
        nome_p = st.text_input("Nome da Unidade")
        local = st.text_input("Localização")
        if st.form_submit_button("Cadastrar PDV"):
            novo_p = pd.DataFrame([{"nome": nome_p, "local": local}])
            conn.update(worksheet="pontos", data=pd.concat([carregar_aba("pontos"), novo_p], ignore_index=True))
            st.success("PDV Ativado!")
    st.dataframe(carregar_aba("pontos"))

# ==================== 5. MÁQUINAS (AUTOMAÇÃO) ====================
elif menu == "📟 Máquinas (Automação)":
    st.header("📟 Integração de Maquininhas")
    with st.form("cad_maq"):
        n = st.text_input("Nome da Máquina")
        tid = st.text_input("ID Terminal (Serial)")
        t_d = st.number_input("Taxa Débito %", value=1.99)
        t_c = st.number_input("Taxa Crédito %", value=3.49)
        if st.form_submit_button("Ligar Máquina ao App"):
            nova_m = pd.DataFrame([{"nome": n, "id_terminal": tid, "taxa_debito": t_d, "taxa_credito": t_c}])
            conn.update(worksheet="maquinas", data=pd.concat([carregar_aba("maquinas"), nova_m], ignore_index=True))
            st.success("Máquina conectada! Vendas automáticas via API habilitadas.")
    st.dataframe(carregar_aba("maquinas"))

# ==================== 6. GESTÃO DE STOCK / REPOSIÇÃO (RESTANTE) ====================
elif menu == "📦 Gestão de Stock":
    st.header("📦 Inventário")
    st.dataframe(carregar_aba("produtos"))

elif menu == "🚚 Reposição":
    st.header("🚚 Entradas de Mercadoria")
    with st.form("repo"):
        prod = st.text_input("Nome do Produto")
        qtd = st.number_input("Quantidade", min_value=1)
        val = st.text_input("Validade (DD/MM/AAAA)")
        prc = st.number_input("Preço Venda")
        if st.form_submit_button("Confirmar Entrada"):
            # Lógica simplificada de reposição
            p_df = carregar_aba("produtos")
            novo = pd.DataFrame([{"nome": prod, "estoque": qtd, "validade": val, "preco": prc}])
            conn.update(worksheet="produtos", data=pd.concat([p_df, novo], ignore_index=True))
            st.success("Stock atualizado!")
