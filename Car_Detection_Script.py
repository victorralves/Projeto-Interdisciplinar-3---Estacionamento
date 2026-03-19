from ultralytics import YOLO
import cv2

model = YOLO("yolov8l.pt")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, classes=[2], conf=0.15, imgsz=640)

    annotated_frame = results[0].plot()

    cv2.imshow("Detecção de Carros", annotated_frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()