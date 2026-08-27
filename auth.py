import sqlite3
import bcrypt
from database import get_connection

def hash_senha(senha):
    # O bcrypt exige que a senha seja convertida para bytes antes de criar o hash
    salt = bcrypt.gensalt()
    senha_hasheada = bcrypt.hashpw(senha.encode('utf-8'), salt)
    # Retornamos como string (texto) para salvar no banco de dados SQLite sem problemas
    return senha_hasheada.decode('utf-8')

def verificar_senha(senha, senha_hash):
    try:
        # Comparamos a senha digitada com o hash salvo no banco, ambos em formato de bytes
        return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))
    except ValueError:
        return False

def criar_admin_padrao():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        # Cria um usuário inicial para você não ficar trancado fora do sistema
        cursor.execute("INSERT INTO usuarios (matricula, senha_hash, perfil) VALUES (?, ?, ?)", 
                       ("admin", hash_senha("admin123"), "ADM"))
        conn.commit()
    conn.close()

def autenticar_usuario(matricula, senha):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT matricula, senha_hash, perfil, ativo FROM usuarios WHERE matricula = ?", (matricula,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        db_mat, db_hash, db_perfil, db_ativo = user
        if db_ativo == 1 and verificar_senha(senha, db_hash):
            return {"matricula": db_mat, "perfil": db_perfil}
    return None

def criar_usuario(matricula, senha, perfil):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (matricula, senha_hash, perfil) VALUES (?, ?, ?)", 
                       (matricula, hash_senha(senha), perfil))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def listar_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, matricula, perfil, ativo FROM usuarios")
    users = cursor.fetchall()
    conn.close()
    return users