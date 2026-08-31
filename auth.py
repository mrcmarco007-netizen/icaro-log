import sqlite3
import bcrypt
from database import conectar_banco

def hash_senha(senha):
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha, senha_hash):
    return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))

def criar_admin_padrao():
    conn = conectar_banco()
    cursor = conn.cursor()
    # Utiliza INSERT OR IGNORE para evitar erros de duplicidade ao recarregar a aplicacao na nuvem
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (matricula, senha_hash, perfil) 
        VALUES (?, ?, ?)
    """, ("admin", hash_senha("admin123"), "ADM"))
    conn.commit()
    conn.close()

def autenticar_usuario(matricula, senha):
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT id, matricula, senha_hash, perfil, ativo FROM usuarios WHERE matricula = ?", (matricula.strip(),))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['ativo'] == 1:
        if verificar_senha(senha, row['senha_hash']):
            return {
                "id": row['id'],
                "matricula": row['matricula'],
                "perfil": row['perfil']
            }
    return None

def criar_usuario(matricula, senha, perfil):
    conn = conectar_banco()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (matricula, senha_hash, perfil) VALUES (?, ?, ?)", 
                       (matricula.strip(), hash_senha(senha), perfil))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def listar_usuarios():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT id, matricula, perfil, ativo FROM usuarios ORDER BY matricula")
    rows = cursor.fetchall()
    conn.close()
    return rows
