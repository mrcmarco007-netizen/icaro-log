import pandas as pd
import datetime
import streamlit as st
from config import normalizar_status, STATUS_ENTREGUE, STATUS_ATRASADO, STATUS_FINALIZADO
from database import get_connection

def calcular_atraso(data_frete, prazo, data_ocorrencia, status_normalizado):
    try:
        if pd.isna(data_frete): return 0
        data_frete_dt = pd.to_datetime(data_frete)
        
        if pd.notna(prazo) and (isinstance(prazo, (int, float)) or (isinstance(prazo, str) and str(prazo).isnumeric())):
            data_prevista = data_frete_dt + datetime.timedelta(days=int(float(prazo)))
        elif pd.notna(prazo):
            data_prevista = pd.to_datetime(prazo)
        else:
            return 0
            
        # Considera a entrega pausada caso o status seja Entregue ou Finalizado
        if status_normalizado in [STATUS_ENTREGUE, STATUS_FINALIZADO] and pd.notna(data_ocorrencia):
            data_fim = pd.to_datetime(data_ocorrencia)
        else:
            data_fim = datetime.datetime.now()
            
        if data_fim > data_prevista:
            return int((data_fim - data_prevista).days)
        return 0
    except:
        return 0

def limpar_valor_monetario(valor):
    try:
        if pd.isna(valor): return 0.0
        if isinstance(valor, (int, float)): return float(valor)
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except:
        return 0.0

def get_val(row, col_name, default=""):
    val = row.get(col_name, default)
    if pd.isna(val):
        return default
    return val

def processar_planilha_icaro(file_buffer, matricula_usuario):
    try:
        df = pd.read_excel(file_buffer)
    except Exception:
        try:
            df = pd.read_csv(file_buffer, sep=';', encoding='utf-8')
        except:
            return {"sucesso": False, "erro": "Formato de arquivo inválido. Use XLSX, XLS ou CSV."}

    df.columns = [str(c).strip().lower().replace(' ', '_').replace('°', '').replace('/', '_') for c in df.columns]
    
    colunas_obrigatorias = ['n_ct-e', 'notas_fiscais', 'data_frete', 'destinatario']
    for col in colunas_obrigatorias:
        if col not in df.columns:
            return {"sucesso": False, "erro": f"Coluna obrigatória não encontrada: {col}. Verifique o arquivo."}

    conn = get_connection()
    cursor = conn.cursor()
    
    resumo = {'lidos': len(df), 'novos': 0, 'atualizados': 0, 'erros': 0, 'ignorados': 0}
    primeiro_erro_exibido = False
    
    for index, row in df.iterrows():
        try:
            ct_e_raw = str(get_val(row, 'n_ct-e', '')).strip()
            if ct_e_raw.endswith('.0'): ct_e_raw = ct_e_raw[:-2]
            
            nf_raw = str(get_val(row, 'notas_fiscais', '')).strip()
            if nf_raw.endswith('.0'): nf_raw = nf_raw[:-2]
            
            if not ct_e_raw or ct_e_raw.lower() == 'nan':
                ct_e_raw = f"COMP_{nf_raw}_{str(get_val(row, 'data_frete', ''))}_{str(get_val(row, 'destinatario', ''))}"[:50]
                
            if not nf_raw or nf_raw.lower() == 'nan':
                resumo['erros'] += 1
                continue

            data_frete = get_val(row, 'data_frete', None)
            ultima_ocorr = str(get_val(row, 'última_ocorrência', ''))
            data_ocorr = get_val(row, 'data_última_ocorrência', None)
            prazo = get_val(row, 'prazo_entrega', 0)
            
            status_norm = normalizar_status(ultima_ocorr)
            atraso = calcular_atraso(data_frete, prazo, data_ocorr, status_norm)
            
            # Se não estiver entregue nem finalizado, e tiver atraso, atualiza para Atrasado
            if status_norm not in [STATUS_ENTREGUE, STATUS_FINALIZADO] and atraso > 0:
                status_norm = STATUS_ATRASADO
            
            valor_nf = limpar_valor_monetario(get_val(row, 'valor_nf', 0))
            valor_frete = limpar_valor_monetario(get_val(row, 'total_frete', 0))

            cidade = str(get_val(row, 'cidade_destinatário', '')).strip()
            uf = str(get_val(row, 'uf_destinatário', '')).strip()
            cidade_uf = f"{cidade}/{uf}" if cidade and uf else (cidade or uf)

            p_cte = str(ct_e_raw)
            p_nf = str(nf_raw)
            p_data_frete = str(data_frete) if pd.notna(data_frete) else ""
            p_destinatario = str(get_val(row, 'destinatario', ''))
            p_cidade_uf = str(cidade_uf)
            p_valor_nf = float(valor_nf)
            p_valor_frete = float(valor_frete)
            p_prazo = str(prazo) if pd.notna(prazo) else ""
            p_status = str(status_norm)
            p_ultima_ocorr = str(ultima_ocorr) if ultima_ocorr else ""
            p_data_ocorr = str(data_ocorr) if pd.notna(data_ocorr) else ""
            p_atraso = int(atraso)

            cursor.execute("SELECT status_normalizado, data_ultima_ocorrencia FROM entregas WHERE ct_e = ?", (p_cte,))
            entrega_existente = cursor.fetchone()

            if entrega_existente:
                db_status, db_data = entrega_existente
                if not p_data_ocorr or db_data == p_data_ocorr and db_status == p_status:
                    resumo['ignorados'] += 1
                    continue
                
                query_upd = '''
                UPDATE entregas SET 
                    status_normalizado = ?, ultima_ocorrencia = ?, data_ultima_ocorrencia = ?, dias_atraso = ?
                WHERE ct_e = ?
                '''
                cursor.execute(query_upd, (p_status, p_ultima_ocorr, p_data_ocorr, p_atraso, p_cte))
                resumo['atualizados'] += 1
            else:
                query_ins = '''
                INSERT INTO entregas (
                    ct_e, nf, data_frete, destinatario, cidade_uf, valor_nf, valor_frete, 
                    prazo_entrega, status_normalizado, ultima_ocorrencia, data_ultima_ocorrencia, dias_atraso
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
                cursor.execute(query_ins, (
                    p_cte, p_nf, p_data_frete, p_destinatario, p_cidade_uf, p_valor_nf, 
                    p_valor_frete, p_prazo, p_status, p_ultima_ocorr, p_data_ocorr, p_atraso
                ))
                resumo['novos'] += 1
            
            cursor.execute('''
            INSERT INTO historico_entregas (ct_e, data_ocorrencia, ocorrencia_original, status_normalizado)
            VALUES (?, ?, ?, ?)
            ''', (p_cte, p_data_ocorr, p_ultima_ocorr, p_status))
            
        except Exception as e:
            resumo['erros'] += 1
            if not primeiro_erro_exibido:
                st.error(f"Erro técnico na linha {index+2}. Motivo: {str(e)}")
                primeiro_erro_exibido = True

    conn.commit()
    conn.close()
    
    from database import log_importacao
    log_importacao(matricula_usuario, file_buffer.name, resumo['lidos'], resumo['novos'], resumo['atualizados'], resumo['erros'])
    
    resumo['sucesso'] = True
    return resumo