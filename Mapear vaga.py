import cv2

# Abrir webcam
cap = cv2.VideoCapture(0)

vagas = []
pontos = []

def mouse_click(event, x, y, flags, param):
    global pontos, vagas

    if event == cv2.EVENT_LBUTTONDOWN:
        pontos.append((x, y))

        # Quando tiver 2 pontos, cria uma vaga
        if len(pontos) == 2:
            x1, y1 = pontos[0]
            x2, y2 = pontos[1]

            vagas.append((x1, y1, x2, y2))
            print(f"Vaga salva: {(x1, y1, x2, y2)}")

            pontos = []

cv2.namedWindow("Mapear Vagas")
cv2.setMouseCallback("Mapear Vagas", mouse_click)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Desenhar vagas salvas
    for vaga in vagas:
        x1, y1, x2, y2 = vaga
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Mostrar pontos temporários
    for p in pontos:
        cv2.circle(frame, p, 5, (255, 0, 0), -1)

    cv2.imshow("Mapear Vagas", frame)

    key = cv2.waitKey(1) & 0xFF

    # Z apaga última vaga
    if key == ord('z'):
        if vagas:
            removida = vagas.pop()
            print(f"Removida: {removida}")

    # ESC sai
    elif key == 27:
        break

cap.release()
cv2.destroyAllWindows()

# Mostrar tudo formatado
print("\nCopie isso para o código:")
print("vagas = [")

for vaga in vagas:
    print(f"    {vaga},")

print("]")