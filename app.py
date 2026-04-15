import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ==================== CONFIGURAÇÃO ====================
st.set_page_config(page_title="Flash Stop - Gestão", layout="wide", page_icon="⚡")

conn = st.connection("gsheets", type=GSheetsConnection)
logo_url = "https://i.imgur.com/8Qj8jN4.png" 

def carregar_aba(nome_aba):
    try:
        df = conn.read(worksheet=nome_aba)
        return df.dropna(how='all')
    except Exception as e:
        return pd.DataFrame()

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col_l1, col_l2, col_l3 = st.columns([1,2,1])
    with col_l2:
        st.image(logo_url, width=300)
        st.subheader("Acesso ao Sistema")
        with st.form("login"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if u == "admin" and s == "flash123":
                    st.session_state.autenticado = True
                    st.session_state.nome_usuario = u
                    st.rerun()
                else: st.error("Credenciais inválidas")
    st.stop()

# ==================== MENU LATERAL ====================
st.sidebar.image(logo_url, use_container_width=True)
menu = st.sidebar.radio("Navegação", 
    ["📊 Dashboard & Alertas", "🛍️ Venda (PDV)", "📋 Relatórios Contábeis", "📦 Gestão de Stock", "📍 Cadastrar PDV", "📟 Máquinas (Automação)"])

# ==================== 1. DASHBOARD & ALERTAS (CORRIGIDO) ====================
if menu == "📊 Dashboard & Alertas":
    st.header("📊 Painel de Controle")
    produtos = carregar_aba("produtos")
    
    if produtos.empty:
        st.info("💡 Dica: Cadastre produtos na aba 'Gestão de Stock' para ativar os alertas.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("⚠️ Alerta de Estoque")
            # Força a conversão para número para evitar erro de comparação
            produtos['estoque'] = pd.to_numeric(produtos['estoque'], errors='coerce').fillna(0)
            baixo = produtos[produtos['estoque'] < 5]
            
            if not baixo.empty:
                for _, row in baixo.iterrows():
                    st.error(f"**Repor urgente:** {row['nome']} | Restam apenas {int(row['estoque'])} un.")
            else:
                st.success("✅ Todos os itens com estoque ok!")

        with col2:
            st.subheader("📅 Alerta de Validade")
            # Converte data e ignora erros de formato
            produtos['validade_dt'] = pd.to_datetime(produtos['validade'], dayfirst=True, errors='coerce')
            hoje = datetime.now()
            
            vencidos = produtos[produtos['validade_dt'] < hoje].copy()
            a_vencer = produtos[(produtos['validade_dt'] >= hoje) & (produtos['validade_dt'] <= hoje + pd.Timedelta(days=15))].copy()

            if not vencidos.empty:
                for _, row in vencidos.iterrows():
                    st.error(f"**VENCIDO:** {row['nome']} ({row['validade']})")
            
            if not a_vencer.empty:
                for _, row in a_vencer.iterrows():
                    st.warning(f"**Vence em breve:** {row['nome']} ({row['validade']})")
            
            if vencidos.empty and a_vencer.empty:
                st.success("✅ Nenhuma validade crítica detectada.")

    # Gráfico de Vendas
    vendas = carregar_aba("vendas")
    if not vendas.empty:
        st.divider()
        st.subheader("🏆 Faturamento por Unidade")
        vendas['valor'] = pd.to_numeric(vendas['valor'], errors='coerce').fillna(0)
        st.bar_chart(vendas.groupby('pdv')['valor'].sum())

# ==================== DEMAIS MENUS (Venda, Relatórios, etc.) ====================
elif menu == "🛍️ Venda (PDV)":
    st.header("🛍️ Frente de Caixa")
    pdvs = carregar_aba("pontos")
    prods = carregar_aba("produtos")
    
    if pdvs.empty or prods.empty:
        st.warning("⚠️ Cadastre PDVs e Produtos primeiro!")
    else:
        with st.form("venda_f"):
            pdv_sel = st.selectbox("📍 Unidade PDV", pdvs['nome'].tolist())
            prod_sel = st.selectbox("📦 Produto", prods['nome'].tolist())
            qtd = st.number_input("Quantidade", min_value=1, value=1)
            forma = st.selectbox("Pagamento", ["Dinheiro", "Pix", "Cartão"])
            if st.form_submit_button("Concluir Venda"):
                idx = prods[prods['nome'] == prod_sel].index[0]
                # Grava Venda
                v_df = pd.DataFrame([{"data": datetime.now().strftime("%d/%m/%Y %H:%M"), "pdv": pdv_sel, "produto": prod_sel, "valor": float(prods.at[idx, 'preco']) * qtd, "forma": forma}])
                conn.update(worksheet="vendas", data=pd.concat([carregar_aba("vendas"), v_df], ignore_index=True))
                # Baixa Stock
                prods.at[idx, 'estoque'] = int(prods.at[idx, 'estoque']) - qtd
                conn.update(worksheet="produtos", data=prods)
                st.success("Venda realizada!")
                st.balloons()

elif menu == "📋 Relatórios Contábeis":
    st.header("📋 Relatórios")
    vendas = carregar_aba("vendas")
    if not vendas.empty:
        pdv_f = st.selectbox("Filtrar PDV", ["Todos"] + vendas['pdv'].unique().tolist())
        df = vendas if pdv_f == "Todos" else vendas[vendas['pdv'] == pdv_f]
        st.metric("Total Bruto", f"R$ {pd.to_numeric(df['valor']).sum():.2f}")
        st.dataframe(df)
    else: st.info("Sem vendas.")

elif menu == "📍 Cadastrar PDV":
    st.header("📍 Configurar PDV")
    with st.form("pdv_c"):
        n = st.text_input("Nome do PDV")
        if st.form_submit_button("Salvar"):
            conn.update(worksheet="pontos", data=pd.concat([carregar_aba("pontos"), pd.DataFrame([{"nome": n}])], ignore_index=True))
            st.success("PDV Cadastrado!")

# ==================== 5. MÁQUINAS (AUTOMAÇÃO) ====================
elif menu == "📟 Máquinas (Automação)":
    st.header("📟 Gestão de Máquinas de Cartão")
    
    # --- FORMULÁRIO DE CADASTRO ---
    with st.expander("➕ Cadastrar Nova Máquina"):
        with st.form("c_maq"):
            n = st.text_input("Nome da Máquina (Ex: Stone PDV 01)")
            tid = st.text_input("Serial Number (TID)")
            if st.form_submit_button("CADASTRAR MÁQUINA"):
                if n and tid:
                    nova_m = pd.DataFrame([{"nome": n, "tid": tid}])
                    conn.update(worksheet="maquinas", data=pd.concat([carregar_aba("maquinas"), nova_m], ignore_index=True))
                    st.success(f"Máquina {n} cadastrada!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos!")

    st.divider()

    # --- LISTAGEM E EXCLUSÃO ---
    st.subheader("📋 Máquinas Ativas")
    maquinas_df = carregar_aba("maquinas")
    
    if not maquinas_df.empty:
        st.dataframe(maquinas_df, use_container_width=True)
        
        # Opção de Excluir
        st.subheader("🗑️ Remover Máquina")
        lista_maquinas = maquinas_df['nome'].tolist()
        maq_para_excluir = st.selectbox("Selecione a máquina que deseja remover:", lista_maquinas)
        
        if st.button("CONFIRMAR EXCLUSÃO"):
            # Filtra o dataframe mantendo todas as máquinas EXCETO a selecionada
            novo_df_maquinas = maquinas_df[maquinas_df['nome'] != maq_para_excluir]
            conn.update(worksheet="maquinas", data=novo_df_maquinas)
            st.warning(f"Máquina {maq_para_excluir} removida com sucesso!")
            time.sleep(1) # Pequena pausa para o usuário ler a mensagem
            st.rerun()
    else:
        st.info("Nenhuma máquina cadastrada no momento.")

elif menu == "📦 Gestão de Estoque":
    st.header("📦 Estoque")
    with st.form("s_c"):
        n = st.text_input("Nome Produto")
        e = st.number_input("Estoque", min_value=0)
        v = st.text_input("Validade (DD/MM/AAAA)")
        p = st.number_input("Preço")
        if st.form_submit_button("Salvar"):
            conn.update(worksheet="produtos", data=pd.concat([carregar_aba("produtos"), pd.DataFrame([{"nome": n, "estoque": e, "validade": v, "preco": p}])], ignore_index=True))
            st.success("Salvo!")
    st.dataframe(carregar_aba("produtos"))
