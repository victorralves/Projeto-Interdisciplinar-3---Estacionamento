"""
seed_demo.py — Popula o banco com dados realistas para apresentação.

Execute UMA VEZ antes de apresentar (com Detecção.py parado):
    python seed_demo.py

Totalmente compatível com o sistema real. Após rodar, inicie normalmente.
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

# ─── Configuração ────────────────────────────────────────────────
DB_PATH     = os.path.join("database", "estacionamento.db")
TOTAL_VAGAS = 20
DIAS_ATRAS  = 7
SEED        = 42
random.seed(SEED)

# ─── Perfil de ocupação por hora (0–23) ──────────────────────────
# Representa um estacionamento universitário / comercial
OCP_HORA = [
    0.02, 0.02, 0.02, 0.02, 0.02, 0.03,   # 00–05
    0.08, 0.25, 0.65, 0.75, 0.72, 0.80,   # 06–11
    0.90, 0.88, 0.70, 0.65, 0.68, 0.82,   # 12–17
    0.78, 0.55, 0.35, 0.18, 0.08, 0.03,   # 18–23
]


def pct_ocp(hora: int, dow: int) -> float:
    base = OCP_HORA[hora]
    if dow >= 5:           # fim de semana
        if 12 <= hora <= 14:
            base = min(base * 1.15, 0.97)
        elif hora < 9:
            base *= 0.5
    return base


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def criar_tabelas(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vagas (
            id            INTEGER PRIMARY KEY,
            situacao      TEXT    NOT NULL DEFAULT 'livre',
            atualizado_em TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga_id     INTEGER NOT NULL,
            entrada_em  TEXT    NOT NULL,
            saida_em    TEXT,
            duracao_min INTEGER
        );
        CREATE TABLE IF NOT EXISTS snapshots_hora (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            hora     TEXT    NOT NULL,
            ocupadas INTEGER NOT NULL,
            livres   INTEGER NOT NULL
        );
    """)


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    agora  = datetime.now()
    inicio = agora - timedelta(days=DIAS_ATRAS)

    print(f"Conectando em {DB_PATH}...")
    conn = conectar()
    criar_tabelas(conn)

    # ── Vagas ──────────────────────────────────────────────────────
    agora_str = agora.strftime('%Y-%m-%d %H:%M:%S')
    conn.executemany(
        "INSERT OR IGNORE INTO vagas (id, situacao, atualizado_em) VALUES (?, 'livre', ?)",
        [(i, agora_str) for i in range(1, TOTAL_VAGAS + 1)]
    )
    conn.commit()
    print("Vagas OK")

    # ── Snapshots por hora ─────────────────────────────────────────
    # Horas existentes (evita duplicatas)
    cur = conn.cursor()
    cur.execute("SELECT hora FROM snapshots_hora")
    existentes = {r[0] for r in cur.fetchall()}

    snapshots = []
    t = inicio.replace(hour=6, minute=0, second=0, microsecond=0)
    while t < agora:
        hora_str = t.strftime('%Y-%m-%d %H:00')
        if hora_str not in existentes:
            pct  = pct_ocp(t.hour, t.weekday())
            noise = random.uniform(-0.05, 0.05)
            ocp   = max(0, min(TOTAL_VAGAS, round((pct + noise) * TOTAL_VAGAS)))
            snapshots.append((hora_str, ocp, TOTAL_VAGAS - ocp))
        t += timedelta(hours=1)

    conn.executemany(
        "INSERT INTO snapshots_hora (hora, ocupadas, livres) VALUES (?, ?, ?)",
        snapshots
    )
    conn.commit()
    print(f"Snapshots inseridos: {len(snapshots)}")

    # ── Sessões ────────────────────────────────────────────────────
    sessoes = []
    for day_offset in range(DIAS_ATRAS):
        dia = (agora - timedelta(days=DIAS_ATRAS - day_offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        dow = dia.weekday()
        n_sess = random.randint(2, 4) if dow < 5 else random.randint(3, 5)

        for vaga_id in range(1, TOTAL_VAGAS + 1):
            hora_cursor = 7.0 + random.uniform(0, 1)   # início entre 07:00–08:00

            for _ in range(n_sess):
                if hora_cursor >= 22.0:
                    break

                # pausa entre sessões
                pausa = random.uniform(15, 60)
                hora_cursor += pausa / 60.0
                if hora_cursor >= 22.0:
                    break

                h = int(hora_cursor)
                m = int((hora_cursor % 1) * 60)
                entrada_dt = dia.replace(hour=min(h, 21), minute=m,
                                         second=random.randint(0, 59))

                if entrada_dt >= agora:
                    break

                # 60% curta, 40% longa
                if random.random() < 0.60:
                    dur = random.randint(10, 55)
                else:
                    dur = random.randint(65, 180)

                saida_dt = entrada_dt + timedelta(minutes=dur)

                if saida_dt >= agora:
                    sessoes.append((vaga_id,
                                    entrada_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                    None, None))
                    hora_cursor = 99
                else:
                    sessoes.append((vaga_id,
                                    entrada_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                    saida_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                    dur))
                    hora_cursor += dur / 60.0

    conn.executemany(
        "INSERT INTO sessoes (vaga_id, entrada_em, saida_em, duracao_min) VALUES (?,?,?,?)",
        sessoes
    )
    conn.commit()
    print(f"Sessoes inseridas: {len(sessoes)}")

    # ── Resumo ─────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM sessoes")
    total_sess = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT hora) FROM snapshots_hora")
    total_snap = cur.fetchone()[0]
    cur.execute("SELECT AVG(duracao_min) FROM sessoes WHERE duracao_min IS NOT NULL")
    avg_dur = cur.fetchone()[0]

    conn.close()

    print("\n=== CONCLUIDO ===")
    print(f"  Sessoes totais  : {total_sess}")
    print(f"  Snapshots       : {total_snap} horas distintas")
    print(f"  Duracao media   : {round(avg_dur or 0, 1)} min")
    print("\nAbra o frontend em Relatorios para ver os dados.")


if __name__ == '__main__':
    main()
