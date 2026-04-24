from ultralytics import YOLO
import cv2
import time

# Modelo YOLO
model = YOLO("yolov8m.pt")

# Webcam
cap = cv2.VideoCapture(0)

ultimo_frame = 0

# COLE SUAS VAGAS AQUI
vagas = [
    (254, 451, 362, 444),
    (299, 407, 396, 411),
    (336, 375, 429, 375),
    (369, 347, 455, 349),
    (401, 326, 481, 321),
    (429, 302, 504, 302),
    (453, 282, 529, 275),
    (479, 260, 548, 257),
    (504, 241, 567, 240),
    (523, 227, 580, 225),
    (74, 293, 154, 296),
    (117, 277, 189, 275),
    (153, 257, 226, 260),
    (187, 238, 254, 241),
    (216, 226, 285, 226),
    (249, 210, 314, 211),
    (279, 198, 337, 198),
    (306, 188, 359, 187),
    (329, 176, 378, 176),
    (343, 165, 388, 167),
]

while True:
    ret, frame = cap.read()
    if not ret:
        break

    agora = time.time()

    if agora - ultimo_frame >= 0.1:
        ultimo_frame = agora

        results = model(frame)

        carros = []

        # Detectar carros
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                name = model.names[cls]

                if name == "car":
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    carros.append((x1, y1, x2, y2))

                    # desenhar box do carro
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    cv2.putText(frame, f"{conf*100:.0f}%",
                                (x1, y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (255, 0, 0), 2)

        ocupadas = 0

        # Verificar vagas
        for vaga in vagas:
            vx1, vy1, vx2, vy2 = vaga
            ocupada = False

            for carro in carros:
                cx1, cy1, cx2, cy2 = carro

                # verifica interseção
                if cx1 < vx2 and cx2 > vx1 and cy1 < vy2 and cy2 > vy1:
                    ocupada = True
                    break

            if ocupada:
                ocupadas += 1
                cor = (0, 0, 255)  # vermelho
            else:
                cor = (0, 255, 0)  # verde

            cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), cor, 2)

        livres = len(vagas) - ocupadas

        # Mostrar contador
        cv2.putText(frame, f"Ocupadas: {ocupadas}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 0, 255), 2)

        cv2.putText(frame, f"Livres: {livres}",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 255, 0), 2)

        cv2.imshow("Estacionamento Inteligente", frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()