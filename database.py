import sqlite3
import pandas as pd
from config import DB_PATH
import datetime

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        matricula TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        perfil TEXT NOT NULL,
        ativo INTEGER DEFAULT 1
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS entregas (
        ct_e TEXT PRIMARY KEY,
        nf TEXT,
        data_frete DATE,
        destinatario TEXT,
        cidade_uf TEXT,
        valor_nf REAL,
        valor_frete REAL,
        prazo_entrega INTEGER,
        status_normalizado TEXT,
        ultima_ocorrencia TEXT,
        data_ultima_ocorrencia DATE,
        dias_atraso INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nf ON entregas(nf)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON entregas(status_normalizado)')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS historico_entregas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ct_e TEXT NOT NULL,
        data_ocorrencia DATE,
        ocorrencia_original TEXT,
        status_normalizado TEXT,
        data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ct_e) REFERENCES entregas(ct_e)
    )
    ''')
    
    # Nova tabela exclusiva para armazenar os Pedidos Internos disponíveis
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pedidos_internos (
        pedido TEXT PRIMARY KEY,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Nova tabela de associação (Permite múltiplos pedidos para a mesma NF)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pedido_notas_multi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nota_fiscal TEXT NOT NULL,
        pedido TEXT NOT NULL,
        criado_por TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(nota_fiscal, pedido)
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pedido_multi ON pedido_notas_multi(pedido)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nf_multi ON pedido_notas_multi(nota_fiscal)')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS importacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        usuario TEXT,
        arquivo TEXT,
        qtd_lidos INTEGER,
        qtd_novos INTEGER,
        qtd_atualizados INTEGER,
        qtd_erros INTEGER
    )
    ''')
    
    conn.commit()
    conn.close()

def execute_query(query, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_dataframe(query, params=()):
    conn = get_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def cadastrar_pedido_interno(pedido):
    query = "INSERT INTO pedidos_internos (pedido) VALUES (?) ON CONFLICT(pedido) DO NOTHING"
    execute_query(query, (str(pedido).strip(),))

def obter_pedidos_disponiveis():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pedido FROM pedidos_internos ORDER BY criado_em DESC")
    resultados = cursor.fetchall()
    conn.close()
    return [str(row[0]) for row in resultados]

def vincular_pedidos_nf(nf, lista_pedidos, usuario):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for ped in lista_pedidos:
            cursor.execute('''
            INSERT INTO pedido_notas_multi (nota_fiscal, pedido, criado_por) 
            VALUES (?, ?, ?) 
            ON CONFLICT(nota_fiscal, pedido) DO NOTHING
            ''', (str(nf).strip(), str(ped).strip(), usuario))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def log_importacao(usuario, arquivo, lidos, novos, atualizados, erros):
    query = '''
    INSERT INTO importacoes (usuario, arquivo, qtd_lidos, qtd_novos, qtd_atualizados, qtd_erros)
    VALUES (?, ?, ?, ?, ?, ?)
    '''
    execute_query(query, (usuario, arquivo, lidos, novos, atualizados, erros))

def obter_nfs_sem_pedido():
    conn = get_connection()
    cursor = conn.cursor()
    query = '''
    SELECT DISTINCT nf 
    FROM entregas 
    WHERE nf NOT IN (SELECT nota_fiscal FROM pedido_notas_multi) 
    AND nf IS NOT NULL AND nf != ''
    ORDER BY nf
    '''
    cursor.execute(query)
    resultados = cursor.fetchall()
    conn.close()
    return [str(row[0]) for row in resultados]
def excluir_associacao(nota_fiscal, pedido):
    query = "DELETE FROM pedido_notas_multi WHERE nota_fiscal = ? AND pedido = ?"
    execute_query(query, (str(nota_fiscal).strip(), str(pedido).strip()))

def excluir_pedido_interno(pedido):
    query = "DELETE FROM pedidos_internos WHERE pedido = ?"
    execute_query(query, (str(pedido).strip(),))