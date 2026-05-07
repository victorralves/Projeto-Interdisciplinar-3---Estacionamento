from ultralytics import YOLO
import cv2
import time
import threading
import json
import os
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

    cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
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
    """Retorna os últimos 24 snapshots para o gráfico de tendência."""
    snapshots = banco.listar_snapshots(limite=24)
    return jsonify(snapshots)

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
    cap   = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
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
# PONTO DE ENTRADA
# =============================================================
if __name__ == '__main__':
    vagas = carregar_vagas()

    if not vagas:
        print("⚠️  Nenhuma vaga encontrada. Abrindo modo de mapeamento...")
        vagas = modo_mapear()
        if not vagas:
            print("Nenhuma vaga definida. Encerrando.")
            exit()
    else:
        print(f"\n✅ {len(vagas)} vaga(s) já mapeada(s).")
        print("   Pressione M para remapear ou qualquer outra tecla para iniciar a detecção.")
        escolha = input("   [Enter=detectar | m=mapear]: ").strip().lower()
        if escolha == 'm':
            vagas = modo_mapear()
            if not vagas:
                print("Nenhuma vaga definida. Encerrando.")
                exit()

    modo_detectar(vagas)