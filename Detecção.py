from ultralytics import YOLO
import cv2
import time
import threading
import json
import os
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify
from flask_cors import CORS
import banco

# =============================================================
# CONFIGURAÇÃO — arquivo onde as vagas são salvas
# =============================================================
VAGAS_FILE = os.path.join(os.path.dirname(__file__), 'vagas.json')

def salvar_vagas(vagas: list):
    with open(VAGAS_FILE, 'w') as f:
        json.dump(vagas, f)
    print(f"💾 {len(vagas)} vaga(s) salva(s) em {VAGAS_FILE}")

def carregar_vagas() -> list:
    if os.path.exists(VAGAS_FILE):
        with open(VAGAS_FILE, 'r') as f:
            dados = json.load(f)
        print(f"📂 {len(dados)} vaga(s) carregada(s) de {VAGAS_FILE}")
        return [tuple(v) for v in dados]
    return []

# =============================================================
# MODO MAPEAR — clica dois pontos para definir cada vaga
# =============================================================
def modo_mapear():
    print("\n MODO MAPEAR VAGAS")
    print("   Clique ESQUERDO: marcar pontos da vaga (2 cliques = 1 vaga)")
    print("   Z: desfazer ultima vaga")
    print("   S: salvar e iniciar deteccao")
    print("   ESC: sair sem salvar\n")

    cap = cv2.VideoCapture(2, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("ERRO: nao foi possivel abrir a camera.")
        return []

    vagas = carregar_vagas()

    # Usar dict mutavel evita problema de nonlocal com reatribuicao no Windows
    estado = {'pontos': []}

    WIN = "Mapear Vagas"  # nome simples, sem caracteres especiais

    def mouse_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            estado['pontos'].append((x, y))
            print(f"  Ponto {len(estado['pontos'])}: ({x}, {y})")
            if len(estado['pontos']) == 2:
                x1, y1 = estado['pontos'][0]
                x2, y2 = estado['pontos'][1]
                vagas.append((x1, y1, x2, y2))
                print(f"  OK Vaga {len(vagas)} mapeada: ({x1},{y1}) -> ({x2},{y2})")
                estado['pontos'] = []

    cv2.namedWindow(WIN)
    cv2.setMouseCallback(WIN, mouse_click)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Desenha vagas ja salvas
        for i, vaga in enumerate(vagas):
            x1, y1, x2, y2 = vaga
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, str(i + 1), (x1, max(y1 - 4, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Desenha ponto temporario do primeiro clique
        for p in estado['pontos']:
            cv2.circle(frame, p, 6, (0, 0, 255), -1)

        cv2.putText(frame, f"Vagas:{len(vagas)} Pontos:{len(estado['pontos'])} | S=salvar Z=desfazer ESC=sair",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow(WIN, frame)

        key = cv2.waitKey(30) & 0xFF  # 30ms da mais tempo ao loop de eventos
        if key == ord('z') and vagas:
            removida = vagas.pop()
            print(f"  Vaga removida: {removida}")
        elif key == ord('s'):
            salvar_vagas(vagas)
            break
        elif key == 27:
            print("Saindo sem salvar.")
            vagas = None
            break

    cap.release()
    cv2.destroyAllWindows()
    return vagas  # None se ESC, lista se S

# =============================================================
# API FLASK
# =============================================================
app = Flask(__name__)
CORS(app)

from flask import request as flask_request

estado_vagas = []
lock = threading.Lock()

@app.route('/')
def home():
    return "API SmartPark rodando 🚀"

@app.route('/api/vagas', methods=['GET'])
def get_vagas():
    with lock:
        return jsonify(estado_vagas)

@app.route('/api/resumo', methods=['GET'])
def get_resumo():
    with lock:
        total    = len(estado_vagas)
        ocupadas = sum(1 for v in estado_vagas if v['situacao'] == 'ocupada')
        livres   = total - ocupadas
        return jsonify({ 'total': total, 'livres': livres, 'ocupadas': ocupadas })

@app.route('/api/sessoes', methods=['GET'])
def get_sessoes():
    """Retorna as últimas 50 sessões (entradas/saídas) do banco de dados."""
    sessoes = banco.listar_sessoes(limite=50)
    return jsonify(sessoes)

@app.route('/api/snapshots', methods=['GET'])
def get_snapshots():
    """Retorna snapshots para o gráfico. Aceita ?dias=N para filtrar período."""
    dias = flask_request.args.get('dias', type=int, default=None)
    snapshots = banco.listar_snapshots(dias=dias)
    return jsonify(snapshots)

@app.route('/api/relatorio/resumo', methods=['GET'])
def get_relatorio_resumo():
    """Métricas consolidadas. Aceita ?dias=N para filtrar período."""
    dias = flask_request.args.get('dias', type=int, default=None)
    return jsonify(banco.relatorio_resumo(dias=dias))

@app.route('/api/relatorio/trafego', methods=['GET'])
def get_relatorio_trafego():
    """Entradas e saídas por hora do dia."""
    return jsonify(banco.relatorio_por_hora())

@app.route('/api/relatorio/por-dia-semana', methods=['GET'])
def get_relatorio_por_dia():
    """Sessões curtas/longas por dia da semana."""
    return jsonify(banco.relatorio_por_dia_semana())

@app.route('/api/relatorio/distribuicao', methods=['GET'])
def get_relatorio_distribuicao():
    """Totais globais de curta vs longa duração."""
    return jsonify(banco.relatorio_distribuicao())

@app.route('/api/exportar/csv', methods=['GET'])
def exportar_csv():
    """Exporta sessões como CSV. Aceita ?dias=N."""
    dias = flask_request.args.get('dias', type=int, default=None)
    sessoes = banco.listar_sessoes(limite=9999)

    # Filtro de data no Python (simples)
    if dias is not None:
        from datetime import datetime as _dt, timedelta as _td
        limite_data = (_dt.now() - _td(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
        sessoes = [s for s in sessoes if s.get('entrada_em', '') >= limite_data]

    import io
    output = io.StringIO()
    output.write('ID,Vaga,Entrada,Saida,Duracao(min)\n')
    for s in sessoes:
        saida = s.get('saida_em') or ''
        dur   = s.get('duracao_min') or ''
        output.write(f"{s['id']},{s['vaga_id']},{s['entrada_em']},{saida},{dur}\n")

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=relatorio_smartpark.csv'}
    )

def iniciar_api():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# =============================================================
# MODO DETECTAR
# =============================================================
def modo_detectar(vagas: list):
    global estado_vagas

    print(f"\n🚗 MODO DETECÇÃO iniciado com {len(vagas)} vagas")
    print("   • ESC: encerrar\n")

    model = YOLO("yolov8m.pt")
    cap   = cv2.VideoCapture(2, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("❌ Erro: não foi possível abrir a câmera no modo de detecção.")
        return

    ultimo_frame    = 0
    ultimo_snapshot = 0

    banco.inicializar_banco(total_vagas=len(vagas))

    with lock:
        estado_vagas = [{'id': i + 1, 'situacao': 'livre'} for i in range(len(vagas))]

    # Inicia API em thread separada
    thread_api = threading.Thread(target=iniciar_api, daemon=True)
    thread_api.start()
    print("✅ API rodando em http://localhost:5000")

    while True:
        ret, frame = cap.read()
        if not ret:

            break

        agora = time.time()

        if agora - ultimo_frame >= 1:
            ultimo_frame = agora

            results = model(frame)
            carros  = []

            for r in results:
                for box in r.boxes:
                    cls  = int(box.cls[0])
                    name = model.names[cls]
                    if name == "car":
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        carros.append((x1, y1, x2, y2))
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

            ocupadas    = 0
            novo_estado = []

            for idx, vaga in enumerate(vagas):
                vx1, vy1, vx2, vy2 = vaga
                ocupada = False
                for carro in carros:
                    cx1, cy1, cx2, cy2 = carro
                    if cx1 < vx2 and cx2 > vx1 and cy1 < vy2 and cy2 > vy1:
                        ocupada = True
                        break

                situacao = 'ocupada' if ocupada else 'livre'
                novo_estado.append({'id': idx + 1, 'situacao': situacao})

                cor = (0, 0, 255) if ocupada else (0, 255, 0)
                if ocupada:
                    ocupadas += 1
                cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), cor, 2)
                cv2.putText(frame, str(idx + 1), (vx1, vy1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)

            # Atualiza banco (detecta entradas/saídas)
            banco.atualizar_estados(novo_estado)

            with lock:
                estado_vagas = novo_estado

            # Snapshot periódico (a cada 10s para demo na maquete)
            if agora - ultimo_snapshot >= 10:
                ultimo_snapshot = agora
                livres_total = len(vagas) - ocupadas
                banco.gravar_snapshot(ocupadas=ocupadas, livres=livres_total)
                print(f"📸 Snapshot: {ocupadas} ocupadas / {livres_total} livres")

            livres = len(vagas) - ocupadas
            cv2.putText(frame, f"Ocupadas: {ocupadas}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(frame, f"Livres: {livres}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "API: localhost:5000", (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            cv2.imshow("Estacionamento Inteligente", frame)

        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

# =============================================================
# MODO DEMO — API com dados do banco, sem câmera nem YOLO
# =============================================================
def modo_demo():
    """Sobe a API Flask usando os dados já presentes no banco (sem câmera)."""
    global estado_vagas

    banco.inicializar_banco(total_vagas=20)

    vagas_db = banco.listar_vagas()
    with lock:
        if vagas_db:
            estado_vagas = vagas_db
        else:
            estado_vagas = [{'id': i + 1, 'situacao': 'livre'} for i in range(20)]

    thread_api = threading.Thread(target=iniciar_api, daemon=True)
    thread_api.start()

    print("\n ✅ API Demo rodando em http://localhost:5000")
    print("    Abra o frontend e navegue para Relatórios.")
    print("    Pressione Ctrl+C para encerrar.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Modo demo encerrado.")


# =============================================================
# SEED DEMO — popula o banco com dados realistas (7 dias)
# =============================================================
_OCP_HORA = [
    0.02, 0.02, 0.02, 0.02, 0.02, 0.03,   # 00–05
    0.08, 0.25, 0.65, 0.75, 0.72, 0.80,   # 06–11
    0.90, 0.88, 0.70, 0.65, 0.68, 0.82,   # 12–17
    0.78, 0.55, 0.35, 0.18, 0.08, 0.03,   # 18–23
]

def _seed_demo_data(total_vagas: int, dias_atras: int = 7):
    """Insere sessões e snapshots fictícios no banco (últimos N dias)."""
    import sqlite3 as _sql

    db_path = banco.DB_PATH
    conn = _sql.connect(db_path, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = _sql.Row

    agora = datetime.now()
    inicio = agora - timedelta(days=dias_atras)
    random.seed(42)

    # ── Snapshots por hora ─────────────────────────────────────
    cur = conn.cursor()
    cur.execute("SELECT hora FROM snapshots_hora")
    existentes = {r[0] for r in cur.fetchall()}

    snapshots = []
    t = inicio.replace(hour=6, minute=0, second=0, microsecond=0)
    while t < agora:
        hora_str = t.strftime('%Y-%m-%d %H:00')
        if hora_str not in existentes:
            pct = _OCP_HORA[t.hour]
            dow = t.weekday()
            if dow >= 5:
                if 12 <= t.hour <= 14:
                    pct = min(pct * 1.15, 0.97)
                elif t.hour < 9:
                    pct *= 0.5
            noise = random.uniform(-0.05, 0.05)
            ocp = max(0, min(total_vagas, round((pct + noise) * total_vagas)))
            snapshots.append((hora_str, ocp, total_vagas - ocp))
        t += timedelta(hours=1)

    conn.executemany(
        "INSERT INTO snapshots_hora (hora, ocupadas, livres) VALUES (?, ?, ?)",
        snapshots
    )
    conn.commit()

    # ── Sessões ────────────────────────────────────────────────
    sessoes = []
    for day_offset in range(dias_atras):
        dia = (agora - timedelta(days=dias_atras - day_offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        dow = dia.weekday()
        n_sess = random.randint(2, 4) if dow < 5 else random.randint(3, 5)

        for vaga_id in range(1, total_vagas + 1):
            hora_cursor = 7.0 + random.uniform(0, 1)

            for _ in range(n_sess):
                if hora_cursor >= 22.0:
                    break

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
    conn.close()

    print(f"  📊 Seed concluído: {len(sessoes)} sessões + {len(snapshots)} snapshots inseridos")


# =============================================================
# MODO DEMO COM CÂMERA — câmera + YOLO + seed auto + limpeza
# =============================================================
def modo_demo_camera(vagas: list):
    """
    Igual ao modo_detectar, mas:
      • No início, popula o banco com dados demo (7 dias de histórico).
      • Ao encerrar (ESC ou Ctrl+C), limpa automaticamente o banco.
    """
    global estado_vagas

    total = len(vagas)
    print(f"\n🎬 MODO DEMO COM CÂMERA iniciado com {total} vagas")
    print("   • O banco será populado com dados de demonstração.")
    print("   • Ao encerrar, todos os dados demo serão removidos.")
    print("   • ESC: encerrar\n")

    # ── Inicializa banco e popula com dados demo ──
    banco.inicializar_banco(total_vagas=total)
    print("  ⏳ Populando banco com dados de demonstração...")
    _seed_demo_data(total_vagas=total, dias_atras=7)

    model = YOLO("yolov8m.pt")
    cap   = cv2.VideoCapture(2, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("❌ Erro: não foi possível abrir a câmera no modo demo.")
        print("  🧹 Limpando dados demo do banco...")
        banco.limpar_demo()
        print("  ✅ Banco limpo.")
        return

    ultimo_frame    = 0
    ultimo_snapshot = 0

    with lock:
        estado_vagas = [{'id': i + 1, 'situacao': 'livre'} for i in range(total)]

    # Inicia API em thread separada
    thread_api = threading.Thread(target=iniciar_api, daemon=True)
    thread_api.start()
    print("  ✅ API rodando em http://localhost:5000")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            agora = time.time()

            if agora - ultimo_frame >= 1:
                ultimo_frame = agora

                results = model(frame)
                carros  = []

                for r in results:
                    for box in r.boxes:
                        cls  = int(box.cls[0])
                        name = model.names[cls]
                        if name == "car":
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            carros.append((x1, y1, x2, y2))
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

                ocupadas    = 0
                novo_estado = []

                for idx, vaga in enumerate(vagas):
                    vx1, vy1, vx2, vy2 = vaga
                    ocupada = False
                    for carro in carros:
                        cx1, cy1, cx2, cy2 = carro
                        if cx1 < vx2 and cx2 > vx1 and cy1 < vy2 and cy2 > vy1:
                            ocupada = True
                            break

                    situacao = 'ocupada' if ocupada else 'livre'
                    novo_estado.append({'id': idx + 1, 'situacao': situacao})

                    cor = (0, 0, 255) if ocupada else (0, 255, 0)
                    if ocupada:
                        ocupadas += 1
                    cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), cor, 2)
                    cv2.putText(frame, str(idx + 1), (vx1, vy1 - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)

                banco.atualizar_estados(novo_estado)

                with lock:
                    estado_vagas = novo_estado

                if agora - ultimo_snapshot >= 10:
                    ultimo_snapshot = agora
                    livres_total = total - ocupadas
                    banco.gravar_snapshot(ocupadas=ocupadas, livres=livres_total)
                    print(f"📸 Snapshot: {ocupadas} ocupadas / {livres_total} livres")

                livres = total - ocupadas
                cv2.putText(frame, f"DEMO | Ocupadas: {ocupadas}", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(frame, f"Livres: {livres}", (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, "API: localhost:5000 | ESC=sair (limpa banco)", (20, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

                cv2.imshow("SmartPark — Demo com Camera", frame)

            if cv2.waitKey(1) == 27:
                break

    except KeyboardInterrupt:
        pass

    # ── Limpeza automática ──
    cap.release()
    cv2.destroyAllWindows()

    print("\n  🧹 Limpando dados demo do banco...")
    res = banco.limpar_demo()
    print(f"  ✅ Banco limpo!")
    print(f"     {res['sessoes_removidas']} sessões removidas")
    print(f"     {res['snapshots_removidos']} snapshots removidos")
    print(f"     Vagas resetadas para 'livre'")
    print("\n🛑 Modo demo com câmera encerrado.")


# =============================================================
# PONTO DE ENTRADA
# =============================================================
if __name__ == '__main__':
    print()
    print("=" * 52)
    print("   SmartPark — Sistema de Monitoramento")
    print("=" * 52)
    print()
    print("  [1] Modo Real        — câmera + detecção YOLO")
    print("  [2] Demo com Câmera  — câmera + YOLO + seed auto + limpeza")
    print("  [3] Sair")
    print()

    escolha = input("  Escolha [1/2/3]: ").strip()

    # ── Demo com Câmera ──
    if escolha == '2':
        vagas = carregar_vagas()

        if not vagas:
            print("\n⚠️  Nenhuma vaga mapeada. Abrindo modo de mapeamento...")
            vagas = modo_mapear()
            if not vagas:
                print("Nenhuma vaga definida. Encerrando.")
                exit()
        else:
            print(f"\n  ✅ {len(vagas)} vaga(s) já mapeada(s).")
            sub = input("     [Enter = iniciar demo | m = remapear vagas]: ").strip().lower()
            if sub == 'm':
                vagas = modo_mapear()
                if not vagas:
                    print("Nenhuma vaga definida. Encerrando.")
                    exit()

        modo_demo_camera(vagas)

    # ── Sair ──
    elif escolha == '3':
        print("  Até logo!")
        exit()

    # ── Modo Real (default) ──
    else:
        vagas = carregar_vagas()

        if not vagas:
            print("\n⚠️  Nenhuma vaga mapeada. Abrindo modo de mapeamento...")
            vagas = modo_mapear()
            if not vagas:
                print("Nenhuma vaga definida. Encerrando.")
                exit()
        else:
            print(f"\n  ✅ {len(vagas)} vaga(s) já mapeada(s).")
            sub = input("     [Enter = iniciar detecção | m = remapear vagas]: ").strip().lower()
            if sub == 'm':
                vagas = modo_mapear()
                if not vagas:
                    print("Nenhuma vaga definida. Encerrando.")
                    exit()

        modo_detectar(vagas)