import pandas as pd

DB_PATH = 'banco.db'
STATUS_ENTREGUE = 'Entregue'
STATUS_ATRASADO = 'Atrasado'
STATUS_FINALIZADO = 'Finalizado'

def normalizar_status(ocorrencia):
    if pd.isna(ocorrencia) or not ocorrencia:
        return 'Sem atualização'
    
    ocorrencia_str = str(ocorrencia).strip().lower()
    
    if ocorrencia_str == 'devolução com cobrança do cliente':
        return STATUS_FINALIZADO
        
    if 'realizada' in ocorrencia_str or 'entregue' in ocorrencia_str:
        return STATUS_ENTREGUE
        
    if 'devolução' in ocorrencia_str:
        return 'Devolução'
        
    return 'Em Trânsito'