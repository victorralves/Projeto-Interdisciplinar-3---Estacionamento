from ultralytics import YOLO
import cv2
import time
import threading
from flask import Flask, jsonify
from flask_cors import CORS

# =============================================================
# API FLASK
# =============================================================
app = Flask(__name__)
CORS(app)

estado_vagas = []
lock = threading.Lock()

# 🔥 NOVA ROTA (resolve o 404 no /)
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

def iniciar_api():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# =============================================================
# DETECÇÃO
# =============================================================
model = YOLO("yolov8m.pt")
cap   = cv2.VideoCapture(0)

ultimo_frame = 0

vagas = [
    (212, 451, 223, 452),
    (281, 418, 289, 425),
    (332, 369, 336, 373),
    (377, 354, 383, 354),
    (418, 329, 427, 329),
    (450, 299, 459, 304),
    (485, 276, 490, 286),
    (539, 264, 539, 273),
    (561, 254, 574, 254),
    (585, 221, 592, 221),
    (30, 292, 41, 296),
    (91, 273, 95, 277),
    (136, 258, 139, 260),
    (173, 238, 177, 243),
    (224, 226, 228, 230),
    (265, 210, 267, 210),
    (298, 196, 305, 197),
    (326, 181, 334, 180),
    (361, 168, 365, 169),
    (397, 157, 399, 161),
    (425, 144, 433, 148),
]

with lock:
    estado_vagas = [{'id': i + 1, 'situacao': 'livre'} for i in range(len(vagas))]

# Inicia API em thread separada
thread_api = threading.Thread(target=iniciar_api, daemon=True)
thread_api.start()

print("✅ API rodando em http://localhost:5000")

# =============================================================
# LOOP DETECÇÃO
# =============================================================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    agora = time.time()

    if agora - ultimo_frame >= 0.1:
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

        ocupadas = 0
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

        with lock:
            estado_vagas = novo_estado

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