import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

from database import get_dataframe, obter_nfs_sem_pedido, init_db, cadastrar_pedido_interno, vincular_pedidos_nf, obter_pedidos_disponiveis, excluir_associacao, excluir_pedido_interno
from processor import processar_planilha_icaro
from auth import autenticar_usuario, criar_usuario, listar_usuarios, criar_admin_padrao

st.set_page_config(page_title="ÍCARO Log", page_icon="🚚", layout="wide")

init_db()
criar_admin_padrao()

if 'usuario' not in st.session_state:
    st.session_state['usuario'] = None

if st.session_state['usuario'] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🚚 Login - ÍCARO Log")
        st.info("Utilize a matrícula 'admin' e a senha 'admin123' no primeiro acesso.")
        with st.form("login_form"):
            matricula = st.text_input("Matrícula")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema")
            
            if submit:
                user = autenticar_usuario(matricula, senha)
                if user:
                    st.session_state['usuario'] = user['matricula']
                    st.session_state['perfil'] = user['perfil']
                    st.session_state['matricula'] = user['matricula']
                    st.rerun()
                else:
                    st.error("Matrícula ou senha incorretos, ou usuário desativado.")
    st.stop()

with st.sidebar:
    st.title("🚚 ÍCARO Log")
    st.write(f"**Usuário:** {st.session_state['usuario']} | **Perfil:** {st.session_state['perfil']}")
    st.divider()
    
    opcoes_menu = ["Dashboard", "Consulta de Entregas"]
    if st.session_state['perfil'] in ['ADM', 'RECEBIMENTO']:
        opcoes_menu.extend(["Pedidos x Notas", "Atualizar Rastreamentos"])
    if st.session_state['perfil'] == 'ADM':
        opcoes_menu.append("Administração")
        
    st.write("**Navegação**")
    menu = st.radio("", opcoes_menu, label_visibility="collapsed")
    
    st.divider()
    if st.button("Sair do Sistema"):
        st.session_state.clear()
        st.rerun()

def carregar_dados_completos():
    query = '''
    SELECT e.*, IFNULL(GROUP_CONCAT(p.pedido, ', '), '') as pedido 
    FROM entregas e
    LEFT JOIN pedido_notas_multi p ON e.nf = p.nota_fiscal
    GROUP BY e.ct_e
    '''
    return get_dataframe(query)

if menu == "Dashboard":
    st.title("📊 Dashboard")
    df = carregar_dados_completos()
    
    if not df.empty:
        total_entregas = len(df)
        entregues = len(df[df['status_normalizado'] == 'Entregue'])
        finalizados = len(df[df['status_normalizado'] == 'Finalizado'])
        atrasados = len(df[df['status_normalizado'] == 'Atrasado'])
        em_transito = len(df[~df['status_normalizado'].isin(['Entregue', 'Atrasado', 'Devolução', 'Finalizado'])])
        
        if 'filtro_dash' not in st.session_state:
            st.session_state['filtro_dash'] = "Todos"
            
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total de Entregas", total_entregas)
            if st.button("Listar Todos", use_container_width=True): st.session_state['filtro_dash'] = "Todos"
        with col2:
            st.metric("Entregues", entregues)
            if st.button("Listar Entregues", use_container_width=True): st.session_state['filtro_dash'] = "Entregue"
        with col3:
            st.metric("Finalizados (Devoluções)", finalizados)
            if st.button("Listar Finalizados", use_container_width=True): st.session_state['filtro_dash'] = "Finalizado"
        with col4:
            st.metric("Em Trânsito", em_transito)
            if st.button("Listar Em Trânsito", use_container_width=True): st.session_state['filtro_dash'] = "Em Trânsito"
        with col5:
            st.metric("Atrasados", atrasados)
            if st.button("Listar Atrasados", use_container_width=True): st.session_state['filtro_dash'] = "Atrasado"
            
        st.divider()
        
        st.subheader(f"📄 Listagem de Entregas: {st.session_state['filtro_dash']}")
        df_lista = df.copy()
        if st.session_state['filtro_dash'] == "Entregue":
            df_lista = df_lista[df_lista['status_normalizado'] == 'Entregue']
        elif st.session_state['filtro_dash'] == "Finalizado":
            df_lista = df_lista[df_lista['status_normalizado'] == 'Finalizado']
        elif st.session_state['filtro_dash'] == "Atrasado":
            df_lista = df_lista[df_lista['status_normalizado'] == 'Atrasado']
        elif st.session_state['filtro_dash'] == "Em Trânsito":
            df_lista = df_lista[~df_lista['status_normalizado'].isin(['Entregue', 'Atrasado', 'Devolução', 'Finalizado'])]
            
        st.dataframe(df_lista[['nf', 'pedido', 'ct_e', 'destinatario', 'cidade_uf', 'data_frete', 'prazo_entrega', 'status_normalizado', 'dias_atraso']], use_container_width=True)
        
        st.divider()
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.subheader("Status das Entregas (Geral)")
            fig1 = px.pie(df, names='status_normalizado', hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            st.subheader("Top Cidades Destino")
            top_cidades = df['cidade_uf'].value_counts().head(10).reset_index()
            top_cidades.columns = ['Cidade/UF', 'Quantidade']
            fig2 = px.bar(top_cidades, x='Cidade/UF', y='Quantidade')
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Nenhum dado de rastreamento encontrado, importe uma planilha ÍCARO.")

elif menu == "Consulta de Entregas":
    st.title("🔎 Consulta de Entregas")
    df = carregar_dados_completos()
    
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        filtro_nf = col1.text_input("Buscar por NF")
        filtro_pedido = col2.text_input("Buscar por Pedido")
        filtro_cte = col3.text_input("Buscar por CT-e")
        
        df_filtrado = df.copy()
        if filtro_nf: df_filtrado = df_filtrado[df_filtrado['nf'].astype(str).str.contains(filtro_nf, case=False, na=False)]
        if filtro_pedido: df_filtrado = df_filtrado[df_filtrado['pedido'].astype(str).str.contains(filtro_pedido, case=False, na=False)]
        if filtro_cte: df_filtrado = df_filtrado[df_filtrado['ct_e'].astype(str).str.contains(filtro_cte, case=False, na=False)]
        
        st.dataframe(df_filtrado[['nf', 'pedido', 'ct_e', 'destinatario', 'cidade_uf', 'data_frete', 'valor_frete', 'status_normalizado', 'ultima_ocorrencia']], use_container_width=True)
    else:
        st.info("Nenhum dado disponível.")

elif menu == "Pedidos x Notas":
    st.title("🔗 Associação: Pedido x Nota Fiscal")
    
    st.subheader("1. Cadastrar Pedido Interno Disponível")
    st.write("Adicione os pedidos ao banco antes de realizar a associação múltipla.")
    with st.form("form_novo_pedido"):
        novo_pedido = st.text_input("Número do Pedido Interno")
        submit_pedido = st.form_submit_button("Adicionar à Lista de Disponíveis")
        if submit_pedido:
            if novo_pedido:
                cadastrar_pedido_interno(novo_pedido)
                st.success(f"Pedido {novo_pedido} adicionado com sucesso!")
                st.rerun()
            else:
                st.warning("Digite o número do pedido.")
                
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("2. Vínculo Múltiplo (NF ↔ Pedidos)")
        nfs_pendentes = obter_nfs_sem_pedido()
        nota_fiscal = st.selectbox("Nota Fiscal (NF)", options=[""] + nfs_pendentes)
        
        pedidos_lista = obter_pedidos_disponiveis()
        pedidos_selecionados = st.multiselect("Selecione os Pedidos (Pode escolher vários)", options=pedidos_lista)
        
        if st.button("Salvar Associação"):
            if nota_fiscal and pedidos_selecionados:
                vincular_pedidos_nf(nota_fiscal, pedidos_selecionados, st.session_state.get('matricula', 'ADM'))
                st.success("Associação múltipla salva com sucesso!")
                st.rerun()
            else:
                st.warning("Selecione a Nota Fiscal e ao menos um Pedido Interno.")
                
    with col2:
        st.subheader("Importação em Massa (CSV)")
        arquivo_csv = st.file_uploader("Selecione o arquivo CSV", type=['csv'])
        if arquivo_csv:
            try:
                df_csv = pd.read_csv(arquivo_csv, sep=None, engine='python')
                cols = [c.strip().lower() for c in df_csv.columns]
                df_csv.columns = cols
                
                col_nf = next((c for c in cols if 'nota' in c or 'nf' in c), None)
                col_ped = next((c for c in cols if 'pedido' in c), None)
                
                if col_nf and col_ped:
                    sucessos = 0
                    for _, row in df_csv.iterrows():
                        nf = str(row[col_nf]).strip()
                        ped = str(row[col_ped]).strip()
                        if nf and ped and nf != 'nan' and ped != 'nan':
                            cadastrar_pedido_interno(ped)
                            vincular_pedidos_nf(nf, [ped], st.session_state.get('matricula', 'ADM'))
                            sucessos += 1
                    st.success(f"{sucessos} associações realizadas com sucesso!")
                    st.rerun()
                else:
                    st.error("Colunas 'Nota Fiscal' e 'Pedido' não encontradas.")
            except Exception as e:
                st.error(f"Erro ao processar: {str(e)}")

    st.divider()
    
    # Nova área restrita para exclusões
    if st.session_state.get('perfil') in ['RECEBIMENTO', 'ADM']:
        st.subheader("🗑️ Exclusão de Registros (Acesso Restrito)")
        st.write("Cuidado: A exclusão é permanente e afeta os relatórios.")
        
        col_del1, col_del2 = st.columns(2)
        with col_del1:
            st.write("**Excluir Pedido Interno**")
            pedidos_para_excluir = obter_pedidos_disponiveis()
            pedido_excluir = st.selectbox("Selecione o Pedido", options=[""] + pedidos_para_excluir, key="sel_ped_excluir")
            if st.button("Excluir Pedido", type="primary"):
                if pedido_excluir:
                    excluir_pedido_interno(pedido_excluir)
                    st.success(f"Pedido {pedido_excluir} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("Selecione um pedido para excluir.")
                    
        with col_del2:
            st.write("**Excluir Vínculo (NF ↔ Pedido)**")
            query_vinc = "SELECT nota_fiscal, pedido FROM pedido_notas_multi"
            df_vinc = get_dataframe(query_vinc)
            opcoes_vinculo = [""]
            if not df_vinc.empty:
                opcoes_vinculo += [f"NF: {row['nota_fiscal']} | Pedido: {row['pedido']}" for _, row in df_vinc.iterrows()]
            
            vinculo_excluir = st.selectbox("Selecione o Vínculo", options=opcoes_vinculo, key="sel_vinc_excluir")
            if st.button("Excluir Vínculo", type="primary"):
                if vinculo_excluir:
                    partes = vinculo_excluir.split(" | ")
                    nf_part = partes[0].replace("NF: ", "").strip()
                    ped_part = partes[1].replace("Pedido: ", "").strip()
                    excluir_associacao(nf_part, ped_part)
                    st.success("Vínculo excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("Selecione um vínculo para excluir.")
                    
        st.divider()

    st.subheader("📋 Status dos Pedidos Internos (Fila e Vínculos)")
    st.write("Acompanhe o tempo de espera dos pedidos e utilize os filtros para buscar datas específicas.")
    
    query_fila = '''
    SELECT 
        p.pedido, 
        p.criado_em as data_inclusao,
        pm.nota_fiscal,
        pm.criado_em as data_vinculo
    FROM pedidos_internos p
    LEFT JOIN pedido_notas_multi pm ON p.pedido = pm.pedido
    ORDER BY p.criado_em DESC
    '''
    df_fila = get_dataframe(query_fila)
    
    if not df_fila.empty:
        df_fila['data_inclusao'] = pd.to_datetime(df_fila['data_inclusao'])
        df_fila['data_vinculo'] = pd.to_datetime(df_fila['data_vinculo'])
        hoje = pd.Timestamp.now().normalize()
        
        def calcular_espera(row):
            dt_inc = row['data_inclusao'].normalize()
            if pd.isna(row['nota_fiscal']):
                dias = (hoje - dt_inc).days
            else:
                dt_vinc = row['data_vinculo'].normalize()
                dias = (dt_vinc - dt_inc).days
            return max(0, dias)
                
        df_fila['Dias de Espera'] = df_fila.apply(calcular_espera, axis=1)
        df_fila['Status'] = df_fila['nota_fiscal'].apply(lambda x: 'Aguardando NF' if pd.isna(x) else 'Vinculado')
        
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            filtro_status = st.selectbox("Filtrar por Status do Pedido:", ["Todos", "Aguardando NF", "Vinculado"])
        with col_filtro2:
            filtro_data_vinc = st.date_input("Filtrar por Período de Vínculo:", value=[], help="Selecione a data de início e a data de fim.")
            
        if filtro_status != "Todos":
            df_fila = df_fila[df_fila['Status'] == filtro_status]
            
        if filtro_data_vinc and len(filtro_data_vinc) == 2:
            df_fila = df_fila[(df_fila['data_vinculo'].dt.date >= filtro_data_vinc[0]) & (df_fila['data_vinculo'].dt.date <= filtro_data_vinc[1])]
        elif filtro_data_vinc and len(filtro_data_vinc) == 1:
            df_fila = df_fila[df_fila['data_vinculo'].dt.date == filtro_data_vinc[0]]
        
        df_fila['data_inclusao'] = df_fila['data_inclusao'].dt.strftime('%d/%m/%Y %H:%M')
        df_fila['data_vinculo'] = df_fila['data_vinculo'].dt.strftime('%d/%m/%Y %H:%M').fillna('-')
        df_fila['nota_fiscal'] = df_fila['nota_fiscal'].fillna('-')
        
        df_exibicao = df_fila[['pedido', 'data_inclusao', 'Status', 'nota_fiscal', 'data_vinculo', 'Dias de Espera']]
        df_exibicao.columns = ['Pedido', 'Data de Inclusão', 'Status', 'Nota Fiscal', 'Data do Vínculo', 'Dias de Espera']
        
        st.dataframe(df_exibicao, use_container_width=True)
    else:
        st.info("Nenhum pedido interno cadastrado ainda.")

elif menu == "Atualizar Rastreamentos":
    st.title("📥 Atualizar Base de Rastreamento")
    st.info("Faça o upload da planilha exportada pelo portal da transportadora ÍCARO.")
    arquivo = st.file_uploader("Planilha ÍCARO (.xlsx, .xls, .csv)", type=['xlsx', 'xls', 'csv'])
    if arquivo:
        if st.button("Processar Planilha", type="primary"):
            with st.spinner("Analisando dados..."):
                resultado = processar_planilha_icaro(arquivo, st.session_state.get('matricula', 'ADM'))
                if resultado.get("sucesso"):
                    st.success("Processamento concluído!")
                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Lidos", resultado['lidos'])
                    col2.metric("Novos", resultado['novos'])
                    col3.metric("Atualizados", resultado['atualizados'])
                    col4.metric("Ignorados", resultado['ignorados'])
                    col5.metric("Erros", resultado['erros'])
                else:
                    st.error(f"Falha na importação: {resultado.get('erro')}")

elif menu == "Administração":
    st.title("⚙️ Administração de Usuários")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Cadastrar Novo Usuário")
        with st.form("form_novo_usuario"):
            nova_mat = st.text_input("Matrícula")
            nova_senha = st.text_input("Senha", type="password")
            novo_perfil = st.selectbox("Perfil de Acesso", ["RECEBIMENTO", "PÓS-VENDA", "ADM"])
            submit = st.form_submit_button("Cadastrar Usuário")
            
            if submit:
                if not nova_mat or not nova_senha:
                    st.warning("Preencha matrícula e senha.")
                else:
                    if criar_usuario(nova_mat, nova_senha, novo_perfil):
                        st.success(f"Matrícula {nova_mat} cadastrada com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro: Esta matrícula já existe no sistema.")
                        
    with col2:
        st.subheader("Usuários Ativos no Sistema")
        users = listar_usuarios()
        df_users = pd.DataFrame(users, columns=["ID", "Matrícula", "Perfil", "Status Ativo"])
        st.dataframe(df_users, hide_index=True, use_container_width=True)