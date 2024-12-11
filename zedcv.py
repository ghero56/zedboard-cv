from flask import Flask, Response, request, render_template_string
from flask_cors import CORS
import cv2
import imageio
import os

class VideoStreamServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.app = Flask(__name__)
        CORS(self.app)
        self.host = host
        self.port = port
        self.frames = []

        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/upload', 'upload', self.upload, methods=['POST'])
        self.app.add_url_rule('/video', 'video', self.video)
        self.app.add_url_rule('/view_video', 'view_video', self.view_video)

    def index(self):
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Captura y Envío de Video</title>
        </head>
        <body>
            <h1>Captura de Video</h1>
            <video id="video" autoplay playsinline></video>
            <p id="error-message" style="color: red;"></p>
            <script>
                const video = document.getElementById('video');
                const errorMessage = document.getElementById('error-message');

                async function startVideoCapture() {
                    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                        errorMessage.textContent = 'El acceso a la cámara no está soportado en este navegador.';
                        console.error('getUserMedia no está soportado en este navegador.');
                        return;
                    }

                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                        video.srcObject = stream;

                        const mediaRecorder = new MediaRecorder(stream);
                        mediaRecorder.ondataavailable = async (event) => {
                            if (event.data.size > 0) {
                                const formData = new FormData();
                                formData.append('file', event.data, 'video.webm');

                                try {
                                    const response = await fetch('/upload', {
                                        method: 'POST',
                                        body: formData
                                    });
                                    console.log('Frame enviado:', response.status);
                                } catch (error) {
                                    console.error('Error al enviar el frame:', error);
                                }
                            }
                        };

                        mediaRecorder.start(1000); // Captura video cada segundo
                        console.log('Grabación iniciada');
                    } catch (error) {
                        errorMessage.textContent = 'No se pudo acceder a la cámara: ' + error.message;
                        console.error('Error al acceder a la cámara:', error);
                    }
                }

                startVideoCapture();
            </script>
            <a href="/view_video">Ver video procesado</a>
        </body>
        </html>
        """
        return render_template_string(html_content)

    def upload(self):
        try:
            if 'file' not in request.files:
                print("No file part")
                return "No file part", 400

            file = request.files['file']
            if file.filename == '':
                print("No selected file")
                return "No selected file", 400

            print("File received:", file.filename)  # Depuración

            try:
                video_data = file.read()
                print("Video data length:", len(video_data))  # Depuración
                video_reader = imageio.get_reader(video_data, 'webm')

                for frame in video_reader:
                    image = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # Convertir de RGB a BGR
                    resized_frame = cv2.resize(image, (1920, 1080))
                    self.frames.append(resized_frame)

                return "Frame recibido", 200

            except Exception as e:
                print(f"Failed to process video: {e}")  # Depuración
                return f"Failed to process video: {e}", 500

        except Exception as e:
            print(f"Error in upload: {e}")  # Captura cualquier otro error
            return f"Error in upload: {e}", 500

    def generate_frames(self):
        while True:
            if self.frames:
                frame = self.frames.pop(0)
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    def video(self):
        return Response(self.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

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
            <video id="processed-video" width="800" height="600" controls autoplay></video>
            <script>
                const videoElement = document.getElementById('processed-video');
                videoElement.src = '/video';  // Fuente del video procesado
                videoElement.play();
            </script>
        </body>
        </html>
        """
        return render_template_string(html_content)

    def run(self):
        print(f"Starting server at {self.host}:{self.port}")  # Depuración
        self.app.run(host=self.host, port=self.port, ssl_context=('ssl/server.crt', 'ssl/server.key'))

if __name__ == '__main__':
    server = VideoStreamServer()
    server.run()
