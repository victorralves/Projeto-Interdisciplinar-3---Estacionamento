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


def listar_snapshots(limite: int = 500, dias: int = None) -> list:
    """
    Retorna os últimos N snapshots horários para o gráfico.
    Garante apenas 1 ponto por hora (o snapshot mais recente daquela hora).
    Se `dias` for informado, filtra apenas os snapshots dos últimos N dias.
    """
    conn = _conectar()
    cur = conn.cursor()

    filtro_data = ""
    params = []
    if dias is not None:
        filtro_data = "WHERE s2.hora >= datetime('now', ?)"
        params.append(f'-{dias} days')

    query = f"""
        SELECT s.hora, s.ocupadas, s.livres
        FROM snapshots_hora s
        INNER JOIN (
            SELECT hora, MAX(id) AS max_id
            FROM snapshots_hora s2
            {filtro_data}
            GROUP BY hora
        ) m ON s.id = m.max_id
        ORDER BY s.hora DESC
        LIMIT ?
    """
    params.append(limite)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return list(reversed(rows))  # ordem cronológica



# ─────────────────────────────────────────────
# FUNÇÕES DE AGREGAÇÃO PARA RELATÓRIOS
# ─────────────────────────────────────────────

def relatorio_resumo(dias: int = None) -> dict:
    """
    Retorna métricas consolidadas para os stat cards da página de Relatórios:
    - avg_ocupacao_pct  : média de ocupação percentual (snapshots)
    - avg_duracao_min   : tempo médio de permanência das sessões concluídas
    - dia_maior_movimento: nome (pt-BR) do dia com mais entradas
    - total_sessoes     : total de sessões registradas
    Se `dias` for informado, filtra apenas os dados dos últimos N dias.
    """
    conn = _conectar()
    cur  = conn.cursor()

    filtro_snap = ""
    filtro_sess = ""
    params_snap = []
    params_sess = []
    if dias is not None:
        filtro_snap = "AND hora >= datetime('now', ?)"
        params_snap = [f'-{dias} days']
        filtro_sess = "AND entrada_em >= datetime('now', ?)"
        params_sess = [f'-{dias} days']

    # Média de ocupação via snapshots
    cur.execute(f"""
        SELECT AVG(CAST(ocupadas AS REAL) / (ocupadas + livres) * 100) AS avg_ocp
        FROM snapshots_hora
        WHERE (ocupadas + livres) > 0 {filtro_snap}
    """, params_snap)
    row = cur.fetchone()
    avg_ocp = round(row['avg_ocp'], 1) if row and row['avg_ocp'] is not None else None

    # Média de duração das sessões concluídas
    cur.execute(f"""
        SELECT AVG(duracao_min) AS avg_dur
        FROM sessoes
        WHERE duracao_min IS NOT NULL {filtro_sess}
    """, params_sess)
    row = cur.fetchone()
    avg_dur = round(row['avg_dur'], 1) if row and row['avg_dur'] is not None else None

    # Dia da semana com mais entradas (0=Dom … 6=Sáb no SQLite strftime %w)
    DIAS_PT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
    cur.execute(f"""
        SELECT strftime('%w', entrada_em) AS dow, COUNT(*) AS total
        FROM sessoes
        WHERE 1=1 {filtro_sess}
        GROUP BY dow
        ORDER BY total DESC
        LIMIT 1
    """, params_sess)
    row = cur.fetchone()
    dia_maior = DIAS_PT[int(row['dow'])] if row else None

    # Total de sessões
    cur.execute(f"SELECT COUNT(*) AS total FROM sessoes WHERE 1=1 {filtro_sess}", params_sess)
    total_sessoes = cur.fetchone()['total']

    conn.close()
    return {
        'avg_ocupacao_pct': avg_ocp,
        'avg_duracao_min':  avg_dur,
        'dia_maior_movimento': dia_maior,
        'total_sessoes': total_sessoes,
    }


def relatorio_por_hora() -> list:
    """
    Retorna, para cada hora do dia (00–23), o número de entradas e saídas
    registradas na tabela sessoes. Só inclui horas com pelo menos 1 evento.
    """
    conn = _conectar()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            strftime('%H:00', entrada_em) AS hora,
            COUNT(*)                       AS entradas,
            SUM(CASE WHEN saida_em IS NOT NULL THEN 1 ELSE 0 END) AS saidas
        FROM sessoes
        GROUP BY hora
        ORDER BY hora
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def relatorio_por_dia_semana() -> list:
    """
    Retorna, para cada dia da semana (Dom–Sáb), a contagem de sessões
    concluídas separadas em curta (<60 min) e longa (>=60 min).
    Dias sem dados também são retornados com zeros.
    """
    DIAS_PT  = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
    conn = _conectar()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            strftime('%w', entrada_em) AS dow,
            SUM(CASE WHEN duracao_min IS NOT NULL AND duracao_min < 60 THEN 1 ELSE 0 END) AS curta,
            SUM(CASE WHEN duracao_min IS NOT NULL AND duracao_min >= 60 THEN 1 ELSE 0 END) AS longa
        FROM sessoes
        GROUP BY dow
        ORDER BY dow
    """)
    por_dow = {int(r['dow']): r for r in cur.fetchall()}
    conn.close()

    resultado = []
    for i, nome in enumerate(DIAS_PT):
        r = por_dow.get(i)
        resultado.append({
            'dia':   nome,
            'curta': int(r['curta']) if r else 0,
            'longa': int(r['longa']) if r else 0,
        })
    return resultado


def relatorio_distribuicao() -> dict:
    """
    Retorna totais globais de sessões curta (<60 min) e longa (>=60 min).
    """
    conn = _conectar()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            SUM(CASE WHEN duracao_min < 60  THEN 1 ELSE 0 END) AS curta,
            SUM(CASE WHEN duracao_min >= 60 THEN 1 ELSE 0 END) AS longa
        FROM sessoes
        WHERE duracao_min IS NOT NULL
    """)
    row = cur.fetchone()
    conn.close()
    curta = int(row['curta']) if row and row['curta'] else 0
    longa = int(row['longa']) if row and row['longa'] else 0
    return {'curta': curta, 'longa': longa, 'total': curta + longa}


def listar_vagas() -> list:
    """Retorna o estado atual de todas as vagas."""
    conn = _conectar()
    cur  = conn.cursor()
    cur.execute("SELECT id, situacao FROM vagas ORDER BY id")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def limpar_demo() -> dict:
    """
    Remove TODOS os dados de sessões e snapshots do banco e reseta
    todas as vagas para 'livre'. Útil após uma apresentação com dados demo.
    """
    conn = _conectar()
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM sessoes")
    n_sess = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM snapshots_hora")
    n_snap = cur.fetchone()[0]

    conn.execute("DELETE FROM sessoes")
    conn.execute("DELETE FROM snapshots_hora")
    conn.execute("UPDATE vagas SET situacao = 'livre'")
    conn.commit()
    conn.close()
    return {'sessoes_removidas': n_sess, 'snapshots_removidos': n_snap}
