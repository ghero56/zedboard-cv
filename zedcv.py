import os
import cv2
import threading
import tempfile
import queue
from flask import Flask, Response, request, render_template_string
from flask_cors import CORS


class VideoStreamServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.app = Flask(__name__)
        CORS(self.app)
        self.host = host
        self.port = port

        self.frame_queue = queue.Queue(maxsize=10)  # Buffer para los frames procesados
        self.processing_lock = (
            threading.Lock()
        )  # Asegura que solo un hilo procese a la vez

        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/upload", "upload", self.upload, methods=["POST"])
        self.app.add_url_rule("/video", "video", self.video)
        self.app.add_url_rule("/view_video", "view_video", self.view_video)

    def index(self):
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Captura de Video</title>
        </head>
        <body>
            <h1>Captura de Video</h1>
            <video id="video" autoplay playsinline></video>
            <script>
                const video = document.getElementById('video');

                async function startVideoCapture() {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    video.srcObject = stream;

                    const mediaRecorder = new MediaRecorder(stream);
                    mediaRecorder.ondataavailable = async (event) => {
                        if (event.data.size > 0) {
                            const formData = new FormData();
                            formData.append('file', event.data, 'video.webm');

                            await fetch('/upload', {
                                method: 'POST',
                                body: formData
                            });
                        }
                    };

                    mediaRecorder.start(1000);  // Captura cada segundo
                }
                startVideoCapture();
            </script>
            <a href="/view_video">Ver video procesado</a>
        </body>
        </html>
        """
        return render_template_string(html_content)

    def upload(self):
        if "file" not in request.files:
            return "No file part", 400

        file = request.files["file"]
        if file.filename == "":
            return "No selected file", 400

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file.read())
            temp_file_path = temp_file.name

        threading.Thread(target=self.process_video, args=(temp_file_path,)).start()
        return "Video recibido", 200

    def process_video(self, video_path):
        try:
            video_capture = cv2.VideoCapture(video_path)

            while True:
                ret, frame = video_capture.read()
                if not ret:
                    break

                with self.processing_lock:
                    # Procesa el frame y lo escala
                    resized_frame = cv2.resize(frame, (1920, 1080))
                    if not self.frame_queue.full():
                        self.frame_queue.put(resized_frame)

            video_capture.release()
            os.remove(video_path)
        except Exception as e:
            print(f"Error en el procesamiento: {e}")

    def generate_frames(self):
        while True:
            if not self.frame_queue.empty():
                with self.processing_lock:
                    frame = self.frame_queue.get()
                    ret, buffer = cv2.imencode(".jpg", frame)
                    if not ret:
                        continue
                    frame = buffer.tobytes()
                yield (
                    b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

    def video(self):
        return Response(
            self.generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    def view_video(self):
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Video Procesado</title>
        </head>
        <body>
            <h1>Video Procesado</h1>
            <img src="/video" style="width:100%; max-width:1920px; height:auto;" />
        </body>
        </html>
        """
        return render_template_string(html_content)

    def run(self):
        self.app.run(host=self.host, port=self.port, threaded=True)


if __name__ == "__main__":
    server = VideoStreamServer()
    server.run()
