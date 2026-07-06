import cv2
import numpy as np
import base64
import time
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import mss
import mss.tools
from PIL import Image
import io
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'screen_share_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

settings = {
    'fps': 15,
    'quality': 70,
    'monitor': 0,
    'width': 1280,
    'height': 720,
    'streaming': False,
    'clients': 0
}

def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[settings['monitor'] + 1] if settings['monitor'] < len(sct.monitors) else sct.monitors[1]
        
        while settings['streaming']:
            try:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                if settings['width'] and settings['height']:
                    img = cv2.resize(img, (settings['width'], settings['height']))
                
                _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, settings['quality']])
                frame = base64.b64encode(buffer).decode('utf-8')
                
                socketio.emit('frame', {'image': frame}, namespace='/screen')
                time.sleep(1.0 / settings['fps'])
                
            except Exception as e:
                print(f"Ошибка захвата: {e}")
                time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream')
def stream():
    return render_template('stream.html')

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    global settings
    if request.method == 'POST':
        data = request.json
        if 'fps' in data:
            settings['fps'] = max(1, min(60, int(data['fps'])))
        if 'quality' in data:
            settings['quality'] = max(10, min(100, int(data['quality'])))
        if 'monitor' in data:
            settings['monitor'] = int(data['monitor'])
        if 'width' in data:
            settings['width'] = int(data['width'])
        if 'height' in data:
            settings['height'] = int(data['height'])
        if 'streaming' in data:
            settings['streaming'] = bool(data['streaming'])
            if settings['streaming']:
                threading.Thread(target=capture_screen, daemon=True).start()
        return jsonify({'status': 'ok', 'settings': settings})
    return jsonify(settings)

@app.route('/api/monitors')
def get_monitors():
    with mss.mss() as sct:
        monitors = []
        for i, mon in enumerate(sct.monitors):
            if i == 0:
                continue
            monitors.append({
                'id': i - 1,
                'name': f"Монитор {i}",
                'width': mon['width'],
                'height': mon['height']
            })
        return jsonify(monitors)

@socketio.on('connect', namespace='/screen')
def handle_connect():
    settings['clients'] += 1
    emit('status', {'msg': 'Подключено к серверу'})

@socketio.on('disconnect', namespace='/screen')
def handle_disconnect():
    settings['clients'] -= 1
    if settings['clients'] < 0:
        settings['clients'] = 0
    if settings['clients'] == 0 and settings['streaming']:
        settings['streaming'] = False

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════╗
║          SCREEN SHARE v1.0                ║
╠═══════════════════════════════════════════╣
║  Сервер запущен!                         ║
║  Открой в браузере: http://localhost:5000║
║  Для просмотра: http://localhost:5000/stream║
╚═══════════════════════════════════════════╝
    """)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
