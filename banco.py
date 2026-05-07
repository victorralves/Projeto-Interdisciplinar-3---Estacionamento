import sqlite3
import os
from datetime import datetime

# Configuração: o banco fica em uma subpasta para evitar que ferramentas de 'Live Server'
# fiquem atualizando a página do navegador toda vez que o arquivo .db muda.
DB_DIR = "database"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_PATH = os.path.join(DB_DIR, "estacionamento.db")


def _conectar():
    """Retorna uma conexão com o banco. Row factory ativada para acessar por nome."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_banco(total_vagas: int):
    """Cria as tabelas (se não existirem) e popula a tabela de vagas."""
    conn = _conectar()
    cur = conn.cursor()

    # --- Tabela de vagas (estado atual) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vagas (
            id            INTEGER PRIMARY KEY,
            situacao      TEXT    NOT NULL DEFAULT 'livre',
            atualizado_em TEXT    NOT NULL
        )
    """)

    # --- Tabela de sessões (histórico entrada/saída) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessoes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga_id      INTEGER NOT NULL REFERENCES vagas(id),
            entrada_em   TEXT    NOT NULL,
            saida_em     TEXT,
            duracao_min  INTEGER
        )
    """)

    # --- Tabela de snapshots por hora ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshots_hora (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            hora     TEXT    NOT NULL,
            ocupadas INTEGER NOT NULL,
            livres   INTEGER NOT NULL
        )
    """)

    # Insere vagas que ainda não existem no banco
    agora = _agora()
    for i in range(1, total_vagas + 1):
        cur.execute("""
            INSERT OR IGNORE INTO vagas (id, situacao, atualizado_em)
            VALUES (?, 'livre', ?)
        """, (i, agora))

    conn.commit()
    conn.close()
    print(f"✅ Banco inicializado em: {DB_PATH}")


def _agora() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def atualizar_estados(novo_estado: list):
    """
    Recebe a lista de vagas com situação atual e:
    - Atualiza a tabela `vagas`
    - Abre sessão quando livre → ocupada
    - Fecha sessão quando ocupada → livre
    """
    conn = _conectar()
    cur = conn.cursor()
    agora = _agora()

    for vaga in novo_estado:
        vaga_id  = vaga['id']
        situacao = vaga['situacao']

        # Estado anterior no banco
        cur.execute("SELECT situacao FROM vagas WHERE id = ?", (vaga_id,))
        row = cur.fetchone()
        estado_anterior = row['situacao'] if row else None

        # Detecta transição
        if estado_anterior == 'livre' and situacao == 'ocupada':
            # Carro entrou → abre sessão
            cur.execute("""
                INSERT INTO sessoes (vaga_id, entrada_em)
                VALUES (?, ?)
            """, (vaga_id, agora))

        elif estado_anterior == 'ocupada' and situacao == 'livre':
            # Carro saiu → fecha sessão ativa
            cur.execute("""
                SELECT id, entrada_em FROM sessoes
                WHERE vaga_id = ? AND saida_em IS NULL
                ORDER BY entrada_em DESC LIMIT 1
            """, (vaga_id,))
            sessao = cur.fetchone()
            if sessao:
                entrada = datetime.strptime(sessao['entrada_em'], '%Y-%m-%d %H:%M:%S')
                saida   = datetime.strptime(agora, '%Y-%m-%d %H:%M:%S')
                duracao = int((saida - entrada).total_seconds() / 60)
                cur.execute("""
                    UPDATE sessoes
                    SET saida_em = ?, duracao_min = ?
                    WHERE id = ?
                """, (agora, duracao, sessao['id']))

        # Atualiza estado atual da vaga
        cur.execute("""
            UPDATE vagas SET situacao = ?, atualizado_em = ?
            WHERE id = ?
        """, (situacao, agora, vaga_id))

    conn.commit()
    conn.close()


def gravar_snapshot(ocupadas: int, livres: int):
    """Grava um snapshot do estado atual para histórico horário."""
    conn = _conectar()
    hora = datetime.now().strftime('%Y-%m-%d %H:00')
    conn.execute("""
        INSERT INTO snapshots_hora (hora, ocupadas, livres)
        VALUES (?, ?, ?)
    """, (hora, ocupadas, livres))
    conn.commit()
    conn.close()


def listar_sessoes(limite: int = 50) -> list:
    """Retorna as sessões mais recentes (concluídas e em andamento)."""
    conn = _conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            s.id,
            s.vaga_id,
            s.entrada_em,
            s.saida_em,
            s.duracao_min
        FROM sessoes s
        ORDER BY s.entrada_em DESC
        LIMIT ?
    """, (limite,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def listar_snapshots(limite: int = 24) -> list:
    """Retorna os últimos N snapshots horários para o gráfico."""
    conn = _conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT hora, ocupadas, livres
        FROM snapshots_hora
        ORDER BY hora DESC
        LIMIT ?
    """, (limite,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return list(reversed(rows))  # ordem cronológica
