# ----------------------------------------------
# 메인 애플리케이션 코드 (Celery 적용)
# ----------------------------------------------

from flask import Flask, request, jsonify, send_from_directory, render_template
from celery import Celery
import os, uuid, hashlib, json, base64, time
from datetime import datetime
import qrcode
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image
import shutil
import socket
import cv2
import numpy as np
import copy
import logging

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Celery 설정 ---
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ----------------------------------------------
# 기본 경로 설정
# ----------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
PREVIEW_DIR = os.path.join(BASE_DIR, "static/preview")
QR_DIR = os.path.join(BASE_DIR, "static/qr")

for d in [TEMP_DIR, PUBLIC_DIR, PREVIEW_DIR, QR_DIR]:
    os.makedirs(d, exist_ok=True)

# 메인 페이지
@app.route("/main_page")
def index():
    return render_template("index.html")

# 관리자 페이지 데이터
@app.route("/admin_data")
def admin_data():
    base = os.path.join(os.getcwd(), "public")
    items = []
    for folder in os.listdir(base):
        path = os.path.join(base, folder)
        if os.path.isdir(path):
            timestamp = os.path.getmtime(path)
            t = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            items.append({
                "folder": folder,
                "time": t,
                "timestamp": timestamp
            })
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(items)

# 랜IP 자동 감지
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]

    except Exception:
        ip = "127.0.0.1"
        logger.warning("LAN IP detection failed, defaulting to localhost.")

    finally:
        s.close()
    
    return ip

LAN_URL = f"http://{get_lan_ip()}:5000/main_page"
logger.info(f"LAN URL: {LAN_URL}")


# ----------------------------------------------
# SD AUTOMATIC1111 API URL
# ----------------------------------------------
SD_URL = "http://127.0.0.1:7860/sdapi/v1/img2img"

# ----------------------------------------------
# 사진 업로드 (임시 저장)
# ----------------------------------------------
@app.route("/upload_temp", methods=["POST"])
def upload_temp():
    data = request.json
    img_b64 = data["image"]
    
    session_id = str(uuid.uuid4())
    session_folder = os.path.join(TEMP_DIR, session_id)
    os.makedirs(session_folder, exist_ok=True)

    img_data = img_b64.split(",")[1]
    img_path = os.path.join(session_folder, "raw.png")
    with open(img_path, "wb") as f:
        f.write(base64.b64decode(img_data))

    return jsonify({"session_id": session_id})

# ----------------------------------------------
# 변환 Task (백그라운드에서 실행됨)
# ----------------------------------------------
@celery.task(bind=True)
def process_transform_task(self, session_id, style_key, gender, overrides):

    # 실시간 Checkpoint 설정 로드
    checkpoint_path = os.path.join(BASE_DIR, "checkpoints.json")

    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            STYLE_CONFIG = json.load(f)["checkpoints"]

    except Exception as e:
        logger.error(f"checkpoints.json load failed: {e}")
    
    else:
        logger.info("checkpoints.json loaded successfully.")
        
        cfg = copy.deepcopy(STYLE_CONFIG.get(style_key, {}))
        cfg.update(overrides)

        if gender and cfg.get("model_name") is not None:
            base_prompt = cfg.get("prompt", "")
            gender_prompt = cfg.get(f"{gender}_prompt", "")
            if gender_prompt:
                cfg["prompt"] = f"{gender_prompt}, {base_prompt}".strip(", ")

            base_neg = cfg.get("negative_prompt", "")
            gender_neg = cfg.get(f"{gender}_negative_prompt", "")
            if gender_neg:
                cfg["negative_prompt"] = f"{gender_neg}, {base_neg}".strip(", ")

            base_ad = cfg.get("ad_prompt", "")
            gender_ad = cfg.get(f"{gender}_ad_prompt", "")
            if gender_ad or base_ad:
                cfg["ad_prompt"] = f"{gender_ad}, {base_ad}".strip(", ")

            base_ad_neg = cfg.get("ad_negative_prompt", "")
            gender_ad_neg = cfg.get(f"{gender}_ad_negative_prompt", "")
            if gender_ad_neg or base_ad_neg:
                cfg["ad_negative_prompt"] = f"{gender_ad_neg}, {base_ad_neg}".strip(", ")
                
            logger.info(f"Applied Gender/Group Prompts for: {gender}, with style: {style_key}")

        raw_path = os.path.join(TEMP_DIR, session_id, "raw.png")
        img = Image.open(raw_path)
        orig_w, orig_h = img.size

        with open(raw_path, "rb") as f:
            init_b64 = base64.b64encode(f.read()).decode()

        result_b64 = None

        if cfg.get("model_name") is None:
            if style_key == "distortion_lens_filter": # 볼록거울 필터
                img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                rows, cols = img_cv.shape[:2]
                mapy, mapx = np.indices((rows, cols), dtype=np.float32)
                mapx = 2 * mapx / (cols - 1) - 1
                mapy = 2 * mapy / (rows - 1) - 1
                r, theta = cv2.cartToPolar(mapx, mapy)
                r[r < 1] = r[r < 1] ** 2  
                mapx, mapy = cv2.polarToCart(r, theta)
                mapx = ((mapx + 1) * cols - 1) / 2
                mapy = ((mapy + 1) * rows - 1) / 2
                distorted = cv2.remap(img_cv, mapx, mapy, cv2.INTER_LINEAR)
                _, buffer = cv2.imencode('.png', distorted)
                result_b64 = base64.b64encode(buffer).decode()

            elif style_key == "face_filter": # 얼굴 필터
                pass # 얼굴 필터 로직 추가 (추후 구현 예정)

            elif style_key == "canny_filter": # canny 필터
                img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
                edges = cv2.Canny(img_cv, 50, 150)
                edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
                _, buffer = cv2.imencode('.png', edges_colored)
                result_b64 = base64.b64encode(buffer).decode()

            else: 
                result_b64 = init_b64 # 원본 반환

        else:
            payload = {
                "checkpoint": cfg["model_name"],
                "init_images": [init_b64],
                "prompt": cfg["prompt"],
                "negative_prompt": cfg["negative_prompt"],
                "steps": cfg["steps"],
                "denoising_strength": cfg["denoising_strength"],
                "sampler_name": "DPM++ 2M",
                "width": orig_w,
                "height": orig_h,
                "resize_mode": 1,
                "cfg_scale": cfg["cfg_scale"],
                "scale_by": 1,
                "alwayson_scripts": {
                    "controlnet": {
                        "args": [{"enabled": True,
                                "image": init_b64,
                                "module": "canny",
                                "model": cfg.get("controlnet_model", "diffusion_pytorch_model [a3cd7cd6]"),
                                "weight": cfg.get("controlnet_weight", 0),
                                "resize_mode": "Crop and Resize",
                                "pixel_perfect": True,
                                "guidance_start": 0.0,
                                "guidance_end": cfg.get("guidance_end", 1.0),
                                "threshold_a": 33.0,
                                "threshold_b": 100.0,
                                "control_mode": "ControlNet is more important"}]
                    }
                    # 과도한 보정으로 ADetailer는 일단 보류 (원본과 너무 달라지는 문제 발생)
                    # "ADetailer": {
                        # "args": [{"ad_model": cfg.get("ad_model", "mediapipe_face_full"),
                                # "ad_prompt": cfg.get("ad_prompt", ""),
                                # "ad_negative_prompt": cfg.get("ad_negative_prompt", ""),
                                # "ad_denoising_strength": cfg.get("ad_denoising_strength", 0.2),
                                # "ad_confidence": 0.3}]
                    #}
                }
            }
            
            try:
                r = requests.post(SD_URL, json=payload, timeout=None)
                r.raise_for_status() 
                result_b64 = r.json()["images"][0]
                
            except Exception as e:
                logger.error(f"Stable Diffusion API Request failed: {e}")
                result_b64 = init_b64

        preview_path = os.path.join(PREVIEW_DIR, f"{session_id}.png")
        with open(preview_path, "wb") as f:
            f.write(base64.b64decode(result_b64))

        return result_b64

# ----------------------------------------------
# 변환 시작 라우트 (Task 큐에 넣기만 함)
# ----------------------------------------------
@app.route("/transform", methods=["POST"])
def transform():
    data = request.json
    session_id = data["session_id"]
    style_key = data["style"]
    gender = data.get("gender") 
    overrides = data.get("overrides", {})

    task = process_transform_task.apply_async(args=[session_id, style_key, gender, overrides])
    
    return jsonify({"task_id": task.id}), 202

# ----------------------------------------------
# 상태 확인 라우트
# ----------------------------------------------
@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = process_transform_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {"state": task.state, "status": "대기 및 변환 중..."}
    elif task.state == 'SUCCESS':
        response = {"state": task.state, "preview_image": task.result}
    else:
        response = {"state": task.state, "status": "오류 발생"}
    return jsonify(response)

# ----------------------------------------------
# URL 생성 + QR 생성
# ----------------------------------------------
@app.route("/finalize", methods=["POST"])
def finalize():
    data = request.json
    session_id = data["session_id"]

    tunnel_file = os.path.join(BASE_DIR, "tunnel_url.txt")
    if os.path.exists(tunnel_file):
        with open(tunnel_file, "r", encoding='utf-16') as f:
            tunnel_url = f.read().strip()
    else:
        tunnel_url = "http://localhost:5000"

    hash_value = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    public_folder = os.path.join(PUBLIC_DIR, hash_value)
    os.makedirs(public_folder, exist_ok=True)

    preview_path = os.path.join(PREVIEW_DIR, f"{session_id}.png")
    final_path = os.path.join(public_folder, "result.png")
    os.rename(preview_path, final_path)

    raw_src_path = os.path.join(TEMP_DIR, session_id, "raw.png")
    raw_dst_path = os.path.join(public_folder, "raw.png")   
    shutil.copy(raw_src_path, raw_dst_path)
    
    download_url = f"{tunnel_url}/dl/{hash_value}/"

    qr_img = qrcode.make(download_url)
    qr_path = os.path.join(QR_DIR, f"{hash_value}.png")
    qr_img.save(qr_path)

    with open(qr_path, "rb") as f:
        qr_b64 = base64.b64encode(f.read()).decode()

    return jsonify({
        "download_url": download_url,
        "qrcode_b64": "data:image/png;base64," + qr_b64
    })

# ----------------------------------------------
# 다운로드 페이지
# ----------------------------------------------
@app.route("/dl/<folder>/")
def download_page(folder):
    return render_template("download.html", folder=folder)

@app.route("/public/<folder>/<filename>")
def serve_image(folder, filename):
    return send_from_directory(os.path.join(PUBLIC_DIR, folder), filename)

# ----------------------------------------------
# 관리자 페이지
# ----------------------------------------------
@app.route("/admin")
def admin_page():
    folders = os.listdir(PUBLIC_DIR)
    folders.sort(reverse=True)
    result = []
    for f in folders:
        img_path = os.path.join(PUBLIC_DIR, f, "result.png")
        if os.path.exists(img_path):
            ts = time.ctime(os.path.getmtime(img_path))
            result.append({"folder": f, "time": ts})
    return render_template("admin.html", items=result)

# ----------------------------------------------
# 폴더 감지 (watchdog)
# ----------------------------------------------
class FolderEvent(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            logger.info(f"New Folder Detected: {event.src_path}")

def start_watcher():
    observer = Observer()
    observer.schedule(FolderEvent(), PUBLIC_DIR, recursive=True)
    observer.start()

if __name__ == "__main__":
    start_watcher()
    app.run(host="0.0.0.0", port=5000, debug=True)