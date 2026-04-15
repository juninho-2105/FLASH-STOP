import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# ==================== CONFIGURAÇÃO ====================
st.set_page_config(page_title="Flash Stop Pro v2.7", layout="wide", page_icon="⚡")

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
    st.title("⚡ Sistema Flash Stop")
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
    ["📊 Dashboard & Alertas", "🛍️ Venda (PDV)", "📋 Relatórios Contábeis", "📦 Gestão de Estoque", "🚚 Histórico de Reposição", "📍 Unidades PDV"])

# ==================== 1. DASHBOARD & ALERTAS ====================
if menu == "📊 Dashboard & Alertas":
    st.header("📊 Painel de Controle")
    produtos = carregar_aba("produtos")
    hoje = datetime.now()

    if not produtos.empty:
        col_alerta1, col_alerta2 = st.columns(2)
        with col_alerta1:
            st.subheader("📉 Alertas de Estoque")
            produtos['estoque'] = pd.to_numeric(produtos['estoque'], errors='coerce').fillna(0)
            baixo = produtos[produtos['estoque'] < 5]
            if not baixo.empty:
                for _, p in baixo.iterrows():
                    st.error(f"Repor: {p['nome']} ({int(p['estoque'])} un)")
            else: st.success("Estoque OK")

        with col_alerta2:
            st.subheader("📅 Alertas de Validade")
            produtos['validade_dt'] = pd.to_datetime(produtos['validade'], format='%d/%m/%Y', errors='coerce')
            vencidos = produtos[produtos['validade_dt'] < hoje]
            if not vencidos.empty:
                for _, p in vencidos.iterrows():
                    st.markdown(f"🔥 **VENCIDO:** {p['nome']} ({p['validade']})")
            else: st.success("Validades OK")

    vendas = carregar_aba("vendas")
    if not vendas.empty:
        st.divider()
        st.subheader("🏆 Faturamento por Unidade")
        st.bar_chart(vendas.groupby('pdv')['valor'].sum())

# ==================== 2. GESTÃO DE ESTOQUE (COM REPOSIÇÃO) ====================
elif menu == "📦 Gestão de Estoque":
    st.header("📦 Inventário e Entradas")
    produtos_df = carregar_aba("produtos")
    
    with st.expander("➕ Nova Reposição / Cadastro"):
        with st.form("reposicao_form"):
            nome_prod = st.text_input("Nome do Produto")
            qtd_entrada = st.number_input("Quantidade de Entrada", min_value=1, value=1)
            validade = st.text_input("Validade (DD/MM/AAAA)")
            preco = st.number_input("Preço de Venda R$", min_value=0.0)
            
            if st.form_submit_button("Confirmar Entrada"):
                # Atualiza ou Cria Produto
                if not produtos_df.empty and nome_prod in produtos_df['nome'].values:
                    idx = produtos_df[produtos_df['nome'] == nome_prod].index[0]
                    produtos_df.at[idx, 'estoque'] = int(produtos_df.at[idx, 'estoque']) + qtd_entrada
                    produtos_df.at[idx, 'validade'] = validade
                    produtos_df.at[idx, 'preco'] = preco
                else:
                    novo = pd.DataFrame([{"nome": nome_prod, "estoque": qtd_entrada, "validade": validade, "preco": preco}])
                    produtos_df = pd.concat([produtos_df, novo], ignore_index=True)
                
                conn.update(worksheet="produtos", data=produtos_df)

                # Grava no Histórico de Reposição
                historico_df = carregar_aba("reposicoes")
                nova_repo = pd.DataFrame([{
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "produto": nome_prod,
                    "qtd_adicionada": qtd_entrada,
                    "usuario": st.session_state.nome_usuario
                }])
                conn.update(worksheet="reposicoes", data=pd.concat([historico_df, nova_repo], ignore_index=True))
                
                st.success(f"Estoque de {nome_prod} atualizado!")

    st.dataframe(carregar_aba("produtos"), use_container_width=True)

# ==================== 3. HISTÓRICO DE REPOSIÇÃO ====================
elif menu == "🚚 Histórico de Reposição":
    st.header("🚚 Auditoria de Entradas")
    reposicoes = carregar_aba("reposicoes")
    if not reposicoes.empty:
        st.dataframe(reposicoes.sort_values(by="data", ascending=False), use_container_width=True)
    else:
        st.info("Nenhuma reposição registrada.")

# ==================== 4. VENDA PDV (BAIXA AUTOMÁTICA) ====================
elif menu == "🛍️ Venda (PDV)":
    st.header("🛍️ Nova Venda")
    pontos_df = carregar_aba("pontos")
    produtos_df = carregar_aba("produtos")
    
    if produtos_df.empty:
        st.error("Cadastre produtos no estoque antes de vender.")
    else:
        with st.form("venda_form"):
            pdv = st.selectbox("PDV", pontos_df['nome'].tolist() if not pontos_df.empty else ["Loja Padrão"])
            prod = st.selectbox("Produto", produtos_df['nome'].tolist())
            qtd = st.number_input("Qtd", min_value=1, value=1)
            
            if st.form_submit_button("VENDER"):
                idx = produtos_df[produtos_df['nome'] == prod].index[0]
                stock = int(produtos_df.at[idx, 'estoque'])
                
                if stock >= qtd:
                    # Registra Venda
                    vendas_df = pd.concat([carregar_aba("vendas"), pd.DataFrame([{
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "pdv": pdv, "produto": prod, "valor": float(produtos_df.at[idx, 'preco']) * qtd
                    }])], ignore_index=True)
                    conn.update(worksheet="vendas", data=vendas_df)
                    
                    # Baixa Estoque
                    produtos_df.at[idx, 'estoque'] = stock - qtd
                    conn.update(worksheet="produtos", data=produtos_df)
                    st.success("Venda Concluída!")
                else:
                    st.error("Estoque insuficiente!")

# (Relatórios e Unidades PDV seguem a lógica das versões anteriores)