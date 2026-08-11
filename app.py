from flask import Flask, request, jsonify, send_from_directory, render_template, session, abort
from celery import Celery
import os, uuid, hashlib, json, base64, time
from datetime import datetime
from functools import wraps
import qrcode
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image, ImageDraw, ImageFont
import shutil
import socket
import cv2
import numpy as np
import copy
import logging
import secrets

# 로깅 설정
class ColorFormatter(logging.Formatter):
    RESET = "\x1b[0m"
    COLORS = {
        logging.DEBUG: "\x1b[36m",     # 청록색
        logging.INFO: "\x1b[32m",      # 초록색
        logging.WARNING: "\x1b[33m",   # 노란색
        logging.ERROR: "\x1b[31m",     # 빨간색
        logging.CRITICAL: "\x1b[41;37m" # 빨간 배경 + 흰색 글씨
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, self.RESET)
        format_str = f"[%(asctime)s][{log_color}%(levelname)s{self.RESET}|%(filename)s:%(lineno)s] --- %(message)s"
        formatter = logging.Formatter(format_str)
        return formatter.format(record)

handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

ADMIN_PASSWORD = os.environ.get("SNAP_POCKET_ADMIN_PASSWORD")
ADMIN_PASSWORD_WAS_GENERATED = not ADMIN_PASSWORD
if ADMIN_PASSWORD_WAS_GENERATED:
    ADMIN_PASSWORD = secrets.token_urlsafe(12)
ADMIN_PASSWORD_DIGEST = hashlib.sha256(ADMIN_PASSWORD.encode("utf-8")).digest()

app.config.update(
    SECRET_KEY=os.environ.get("SNAP_POCKET_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict"
)

# Celery 설정
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
app.config['CELERY_TRACK_STARTED'] = True

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 기본 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
PREVIEW_DIR = os.path.join(BASE_DIR, "static/preview")
QR_DIR = os.path.join(BASE_DIR, "static/qr")
METADATA_DIR = os.path.join(BASE_DIR, "metadata")

for d in [TEMP_DIR, PUBLIC_DIR, PREVIEW_DIR, QR_DIR, METADATA_DIR]:
    os.makedirs(d, exist_ok=True)

TRANSFORM_STATUS_FILENAME = "transform_status.json"
TRANSFORM_STATUSES = {"captured", "processing", "success", "failed"}


def _load_json_object(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json_object(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = os.path.join(directory, f".{uuid.uuid4().hex}.json")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _get_session_folder(session_id):
    if not isinstance(session_id, str) or not session_id:
        return None
    temp_root = os.path.abspath(TEMP_DIR)
    session_folder = os.path.abspath(os.path.join(temp_root, session_id))
    try:
        is_inside_temp = (
            os.path.normcase(os.path.commonpath([temp_root, session_folder]))
            == os.path.normcase(temp_root)
        )
    except ValueError:
        return None
    if not is_inside_temp or session_folder == temp_root:
        return None
    return session_folder


def _write_transform_status(session_id, status, **details):
    if status not in TRANSFORM_STATUSES:
        raise ValueError(f"Unsupported transform status: {status}")
    session_folder = _get_session_folder(session_id)
    if session_folder is None or not os.path.isdir(session_folder):
        raise FileNotFoundError(f"Session folder not found: {session_id}")
    payload = {
        "status": status,
        "updated_at": time.time(),
        **details
    }
    _write_json_object(
        os.path.join(session_folder, TRANSFORM_STATUS_FILENAME),
        payload
    )


def is_admin_authenticated():
    return session.get("admin_authenticated") is True


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_authenticated():
            return jsonify({"error": "관리자 로그인이 필요합니다."}), 401
        return view(*args, **kwargs)
    return wrapped

# 메인 페이지
@app.route("/main_page")
def index():
    return render_template("index.html", watermark_text=WATERMARK_TEXT)

# 관리자 로그인
@app.route("/admin_login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    if not isinstance(password, str) or not password:
        return jsonify({"error": "비밀번호를 입력해주세요."}), 400

    password_digest = hashlib.sha256(password.encode("utf-8")).digest()
    if not secrets.compare_digest(password_digest, ADMIN_PASSWORD_DIGEST):
        return jsonify({"error": "비밀번호가 일치하지 않습니다."}), 401

    session.clear()
    session["admin_authenticated"] = True
    return jsonify({"ok": True})


# 관리자 페이지 데이터
@app.route("/admin_data")
@admin_required
def admin_data():
    items = []
    session_folders = []
    session_statuses = []
    public_folders_for_sessions = set()

    for session_id in os.listdir(TEMP_DIR):
        session_path = os.path.join(TEMP_DIR, session_id)
        if not os.path.isdir(session_path):
            continue

        session_folders.append(session_id)
        folder = hashlib.sha256(session_id.encode()).hexdigest()[:16]
        public_folders_for_sessions.add(folder)
        raw_path = os.path.join(session_path, "raw.png")
        public_result_path = os.path.join(PUBLIC_DIR, folder, "result.png")
        preview_path = os.path.join(PREVIEW_DIR, f"{session_id}.png")
        result_available = (
            os.path.isfile(public_result_path)
            or os.path.isfile(preview_path)
        )
        timestamp_source = raw_path if os.path.isfile(raw_path) else session_path
        timestamp = os.path.getmtime(timestamp_source)

        status_data = _load_json_object(
            os.path.join(session_path, TRANSFORM_STATUS_FILENAME)
        ) or {}
        status = status_data.get("status")
        if status not in TRANSFORM_STATUSES:
            status = "success" if result_available else "captured"
        session_statuses.append(status)

        metadata = _load_json_object(os.path.join(METADATA_DIR, f"{folder}.json"))
        if metadata is None:
            metadata = _load_json_object(os.path.join(session_path, "metadata.json"))

        items.append({
            "id": session_id,
            "folder": folder,
            "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": timestamp,
            "status": status,
            "metadata": metadata,
            "raw_url": (
                f"/admin_session_image/{session_id}/raw"
                if os.path.isfile(raw_path)
                else None
            ),
            "result_url": (
                f"/admin_session_image/{session_id}/result"
                if result_available
                else None
            )
        })

    for folder in os.listdir(PUBLIC_DIR):
        if folder in public_folders_for_sessions:
            continue
        public_path = os.path.join(PUBLIC_DIR, folder)
        result_path = os.path.join(public_path, "result.png")
        if not os.path.isdir(public_path) or not os.path.isfile(result_path):
            continue
        raw_path = os.path.join(public_path, "raw.png")
        timestamp = os.path.getmtime(result_path)
        items.append({
            "id": f"legacy-{folder}",
            "folder": folder,
            "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": timestamp,
            "status": "success",
            "metadata": _load_json_object(
                os.path.join(METADATA_DIR, f"{folder}.json")
            ),
            "raw_url": f"/public/{folder}/raw.png" if os.path.isfile(raw_path) else None,
            "result_url": f"/public/{folder}/result.png"
        })

    items.sort(key=lambda x: x["timestamp"], reverse=True)
    success_count = session_statuses.count("success")
    failure_count = session_statuses.count("failed")
    untransformed_count = session_statuses.count("captured")
    transformed_total = success_count + failure_count
    summary_total = transformed_total + untransformed_count
    success_rate = (
        round(success_count / transformed_total * 100, 1)
        if transformed_total
        else 0.0
    )
    return jsonify({
        "items": items,
        "stats": {
            "photo_count": len(session_folders),
            "success_count": success_count,
            "failure_count": failure_count,
            "untransformed_count": untransformed_count,
            "transformed_total": transformed_total,
            "summary_total": summary_total,
            "success_rate": success_rate
        }
    })

# 랜IP 자동 감지
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]

    except Exception:
        logger.error("Is this device connected to a network? LAN IP detection failed.")
        ip = "127.0.0.1" # Fallback
        
    finally:
        s.close()
    
    return ip

LAN_URL = f"http://{get_lan_ip()}:5000/main_page"
logger.info(f"LAN URL: {LAN_URL}")


# SD AUTOMATIC1111 API URL
SD_URL = "http://127.0.0.1:7860/sdapi/v1/img2img"
SD_TIMEOUT_SECONDS = 10 * 60

WATERMARK_TEXT = "SNAP POCKET"
DEFAULT_FRAME_COLOR = "clear_white"
FRAME_COLOR_PRESETS = {
    "clear_white": {
        "colors": ((255, 255, 255, 255),),
        "watermark": (40, 40, 40, 255)
    },
    "matte_black": {
        "colors": ((18, 18, 21, 255),),
        "watermark": (245, 245, 245, 255)
    },
    "cybernetic_blue": {
        "colors": ((0, 199, 217, 255),),
        "watermark": (4, 42, 50, 255)
    },
    "metal_purple": {
        "colors": ((101, 76, 159, 255),),
        "watermark": (255, 255, 255, 255)
    },
    "liquid_glass": {
        "colors": ((218, 235, 242, 190),),
        "watermark": (34, 50, 58, 235)
    },
    "black_white": {
        "colors": ((18, 18, 21, 255), (248, 247, 244, 255)),
        "watermark": (40, 40, 40, 255)
    },
    "cobalt_cream": {
        "colors": ((31, 74, 194, 255), (246, 235, 208, 255)),
        "watermark": (34, 38, 48, 255)
    },
    "burgundy_blush": {
        "colors": ((101, 27, 53, 255), (242, 205, 211, 255)),
        "watermark": (74, 23, 40, 255)
    },
    "forest_sand": {
        "colors": ((24, 74, 58, 255), (221, 199, 158, 255)),
        "watermark": (34, 47, 40, 255)
    },
    "orange_navy": {
        "colors": ((241, 105, 44, 255), (23, 35, 64, 255)),
        "watermark": (255, 255, 255, 255)
    }
}


def _load_watermark_font(font_size):
    font_candidates = [
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
        "DejaVuSans-Bold.ttf",
        "arial.ttf"
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _create_frame_canvas(size, frame_color):
    preset = (
        FRAME_COLOR_PRESETS.get(frame_color)
        if isinstance(frame_color, str)
        else None
    ) or FRAME_COLOR_PRESETS[DEFAULT_FRAME_COLOR]
    colors = preset["colors"]
    canvas = Image.new("RGBA", size, colors[0])

    if len(colors) == 2:
        ImageDraw.Draw(canvas).polygon(
            ((0, size[1]), (size[0], 0), (size[0], size[1])),
            fill=colors[1]
        )

    return canvas, preset["watermark"]


def create_framed_photo(image_path, output_path, frame_color=DEFAULT_FRAME_COLOR):
    with Image.open(image_path) as image_source:
        image = image_source.convert("RGB")

    border_size = max(20, round(image.width * 0.02))
    font_size = max(18, round(image.width * 0.028))
    font = _load_watermark_font(font_size)

    measurement_canvas = Image.new("RGB", (1, 1), "white")
    measurement_draw = ImageDraw.Draw(measurement_canvas)
    text_box = measurement_draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    watermark_border = text_height + border_size * 2

    canvas_width = image.width + border_size * 2
    canvas_height = border_size + image.height + watermark_border
    framed_photo, watermark_fill = _create_frame_canvas(
        (canvas_width, canvas_height),
        frame_color
    )
    framed_photo.paste(image, (border_size, border_size))

    watermark_x = canvas_width - border_size - text_width - text_box[0]
    watermark_y = (
        border_size
        + image.height
        + (watermark_border - text_height) // 2
        - text_box[1]
    )
    ImageDraw.Draw(framed_photo).text(
        (watermark_x, watermark_y),
        WATERMARK_TEXT,
        fill=watermark_fill,
        font=font
    )
    framed_photo.save(output_path, format="PNG")


def create_framed_collage(
    raw_path,
    transformed_path,
    output_path,
    frame_color=DEFAULT_FRAME_COLOR
):
    with Image.open(raw_path) as raw_source:
        raw_image = raw_source.convert("RGB")
    with Image.open(transformed_path) as transformed_source:
        transformed_image = transformed_source.convert("RGB")

    content_width = max(raw_image.width, transformed_image.width)
    border_size = max(20, round(content_width * 0.02))
    font_size = max(18, round(content_width * 0.028))
    font = _load_watermark_font(font_size)

    measurement_canvas = Image.new("RGB", (1, 1), "white")
    measurement_draw = ImageDraw.Draw(measurement_canvas)
    text_box = measurement_draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    watermark_border = text_height + border_size * 2

    canvas_width = content_width + border_size * 2
    canvas_height = (
        border_size
        + raw_image.height
        + border_size
        + transformed_image.height
        + watermark_border
    )
    raw_x = border_size + (content_width - raw_image.width) // 2
    transformed_x = border_size + (content_width - transformed_image.width) // 2
    raw_y = border_size
    transformed_y = raw_y + raw_image.height + border_size
    collage, watermark_fill = _create_frame_canvas(
        (canvas_width, canvas_height),
        frame_color
    )
    collage.paste(raw_image, (raw_x, raw_y))
    collage.paste(transformed_image, (transformed_x, transformed_y))

    watermark_x = canvas_width - border_size - text_width - text_box[0]
    watermark_y = (
        transformed_y
        + transformed_image.height
        + (watermark_border - text_height) // 2
        - text_box[1]
    )
    ImageDraw.Draw(collage).text(
        (watermark_x, watermark_y),
        WATERMARK_TEXT,
        fill=watermark_fill,
        font=font
    )
    collage.save(output_path, format="PNG")

# 사진 업로드 (임시 저장)
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

    _write_transform_status(session_id, "captured")

    return jsonify({"session_id": session_id})

# 변환 처리
def _run_transform_task(session_id, style_key, gender, adetailer_enabled, overrides):

    # 실시간 Checkpoint 설정 로드
    checkpoint_path = os.path.join(BASE_DIR, "checkpoints.json")

    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            STYLE_CONFIG = json.load(f)["checkpoints"]

    except Exception as e:
        logger.exception(f"checkpoints.json load failed: {e}")
        raise RuntimeError("스타일 설정을 불러오지 못했습니다.") from e
    
    else:
        logger.info("checkpoints.json loaded successfully.")

        if style_key not in STYLE_CONFIG:
            raise ValueError(f"Unsupported style: {style_key}")
        if type(adetailer_enabled) is not bool:
            raise ValueError("ADetailer enabled flag must be a boolean.")
        if not isinstance(overrides, dict):
            raise ValueError("Style overrides must be an object.")

        cfg = copy.deepcopy(STYLE_CONFIG.get(style_key, {}))
        cfg.update(overrides)

        if cfg.get("model_name") is None:
            adetailer_enabled = False

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
        with Image.open(raw_path) as image_source:
            img = image_source.convert("RGB")
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
                raise NotImplementedError("얼굴 필터는 아직 지원되지 않습니다.")

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
                }
            }

            if adetailer_enabled:
                payload["alwayson_scripts"]["ADetailer"] = {
                    "args": [
                        True,
                        False,
                        {
                            "ad_model": cfg.get("ad_model") or "face_yolov8m.pt",
                            "ad_tab_enable": True,
                            "ad_prompt": cfg.get("ad_prompt", ""),
                            "ad_negative_prompt": cfg.get("ad_negative_prompt", ""),
                            "ad_denoising_strength": cfg.get("ad_denoising_strength", 0.2),
                            "ad_confidence": cfg.get("ad_confidence", 0.3)
                        }
                    ]
                }
                logger.info(f"ADetailer enabled for style: {style_key}")
            
            try:
                r = requests.post(SD_URL, json=payload, timeout=SD_TIMEOUT_SECONDS)
                r.raise_for_status() 
                response_data = r.json()
                images = response_data.get("images")
                if not isinstance(images, list) or not images:
                    raise ValueError("Stable Diffusion response did not contain an image.")
                result_b64 = images[0]

            except requests.Timeout as e:
                logger.error(f"Stable Diffusion API timed out after {SD_TIMEOUT_SECONDS} seconds: {e}")
                raise RuntimeError("AI 변환 시간이 10분을 초과했습니다.") from e
            except Exception as e:
                logger.exception(f"Stable Diffusion API request failed: {e}")
                raise RuntimeError("AI 변환 요청에 실패했습니다.") from e

        if not result_b64:
            raise RuntimeError("변환 결과 이미지가 생성되지 않았습니다.")

        preview_path = os.path.join(PREVIEW_DIR, f"{session_id}.png")
        with open(preview_path, "wb") as f:
            f.write(base64.b64decode(result_b64))

        transform_metadata_path = os.path.join(TEMP_DIR, session_id, "metadata.json")
        transform_metadata = _load_json_object(transform_metadata_path) or {}
        transform_metadata.update({
            "style": style_key,
            "gender": gender,
            "adetailer_enabled": adetailer_enabled
        })
        _write_json_object(transform_metadata_path, transform_metadata)

        return result_b64


# 변환 Task
@celery.task(bind=True)
def process_transform_task(self, session_id, style_key, gender, adetailer_enabled, overrides):
    try:
        result = _run_transform_task(
            session_id,
            style_key,
            gender,
            adetailer_enabled,
            overrides
        )
        _write_transform_status(session_id, "success")
        return result
    except Exception as e:
        try:
            _write_transform_status(session_id, "failed", error=str(e))
        except Exception:
            logger.exception(f"Failed to record transform failure for session {session_id}")
        raise


# 변환 시작
@app.route("/transform", methods=["POST"])
def transform():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    style_key = data.get("style")
    gender = data.get("gender")
    adetailer_enabled = data.get("adetailer_enabled", False)
    add_frame = data.get("add_frame") is True
    frame_color = data.get("frame_color", DEFAULT_FRAME_COLOR)
    overrides = data.get("overrides", {})

    if not session_id or not style_key:
        return jsonify({"error": "변환 요청 정보가 올바르지 않습니다."}), 400
    if type(adetailer_enabled) is not bool:
        return jsonify({"error": "ADetailer 보정 여부는 boolean 값이어야 합니다."}), 400
    if add_frame and (
        not isinstance(frame_color, str)
        or frame_color not in FRAME_COLOR_PRESETS
    ):
        return jsonify({"error": "지원하지 않는 프레임 색상입니다."}), 400

    session_folder = _get_session_folder(session_id)
    if (
        session_folder is None
        or not os.path.isfile(os.path.join(session_folder, "raw.png"))
    ):
        return jsonify({"error": "촬영 세션을 찾을 수 없습니다."}), 409

    task_id = str(uuid.uuid4())
    try:
        _write_json_object(
            os.path.join(session_folder, "metadata.json"),
            {
                "style": style_key,
                "gender": gender,
                "add_frame": add_frame,
                "frame_color": frame_color if add_frame else None,
                "adetailer_enabled": adetailer_enabled
            }
        )
        _write_transform_status(session_id, "processing", task_id=task_id)
        task = process_transform_task.apply_async(
            args=[session_id, style_key, gender, adetailer_enabled, overrides],
            task_id=task_id
        )
    except Exception as e:
        try:
            _write_transform_status(session_id, "failed", error=str(e))
        except Exception:
            logger.exception(f"Failed to record enqueue failure for session {session_id}")
        logger.exception(f"Failed to enqueue transform task: {e}")
        return jsonify({"error": "변환 작업을 시작하지 못했습니다."}), 503
    
    return jsonify({"task_id": task.id}), 202

# 상태 확인
@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = process_transform_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {"state": task.state, "status": "변환 대기 중..."}
    elif task.state == 'STARTED':
        response = {"state": task.state, "status": "AI 변환 중..."}
    elif task.state == 'RETRY':
        response = {"state": task.state, "status": "AI 변환 재시도 중..."}
    elif task.state == 'SUCCESS':
        response = {"state": task.state, "preview_image": task.result}
    else:
        response = {"state": task.state, "status": "AI 변환에 실패했습니다. 다시 시도해주세요."}
    return jsonify(response)

# URL 생성 + QR 생성
@app.route("/finalize", methods=["POST"])
def finalize():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    add_frame = data.get("add_frame") is True
    style_key = data.get("style")
    frame_color = data.get("frame_color", DEFAULT_FRAME_COLOR)
    if not session_id:
        return jsonify({"error": "저장할 촬영 세션이 없습니다."}), 400
    if add_frame and (
        not isinstance(frame_color, str)
        or frame_color not in FRAME_COLOR_PRESETS
    ):
        return jsonify({"error": "지원하지 않는 프레임 색상입니다."}), 400

    preview_path = os.path.join(PREVIEW_DIR, f"{session_id}.png")
    raw_src_path = os.path.join(TEMP_DIR, session_id, "raw.png")
    if not os.path.isfile(preview_path) or not os.path.isfile(raw_src_path):
        logger.warning(f"Finalize source files are missing for session {session_id}")
        return jsonify({"error": "변환 결과를 찾을 수 없습니다. 다시 촬영해주세요."}), 409

    try:
        tunnel_file = os.path.join(BASE_DIR, "tunnel_url.txt")
        if os.path.exists(tunnel_file):
            with open(tunnel_file, "r", encoding='utf-16') as f:
                tunnel_url = f.read().strip()
        else:
            tunnel_url = "http://localhost:5000"

        hash_value = hashlib.sha256(session_id.encode()).hexdigest()[:16]

        transform_metadata = {}
        transform_metadata_path = os.path.join(TEMP_DIR, session_id, "metadata.json")
        try:
            with open(transform_metadata_path, "r", encoding="utf-8") as f:
                loaded_metadata = json.load(f)
            if isinstance(loaded_metadata, dict):
                transform_metadata = loaded_metadata
        except (OSError, json.JSONDecodeError):
            pass

        photo_metadata = {
            "style": transform_metadata.get("style") or style_key,
            "gender": transform_metadata.get("gender"),
            "add_frame": add_frame,
            "frame_color": frame_color if add_frame else None,
            "adetailer_enabled": transform_metadata.get("adetailer_enabled")
        }
        metadata_path = os.path.join(METADATA_DIR, f"{hash_value}.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(photo_metadata, f, ensure_ascii=False, indent=2)

        public_folder = os.path.join(PUBLIC_DIR, hash_value)
        os.makedirs(public_folder, exist_ok=True)

        final_path = os.path.join(public_folder, "result.png")
        if add_frame:
            if style_key == "none":
                create_framed_photo(preview_path, final_path, frame_color)
            else:
                create_framed_collage(
                    raw_src_path,
                    preview_path,
                    final_path,
                    frame_color
                )
            os.remove(preview_path)
        else:
            os.rename(preview_path, final_path)

        raw_dst_path = os.path.join(public_folder, "raw.png")
        shutil.copy(raw_src_path, raw_dst_path)

        base_url = tunnel_url.rstrip("/")
        download_page_url = f"{base_url}/dl/{hash_value}/"
        direct_download_url = f"{base_url}/download/{hash_value}/"

        qr_img = qrcode.make(direct_download_url)
        qr_path = os.path.join(QR_DIR, f"{hash_value}.png")
        qr_img.save(qr_path)

        with open(qr_path, "rb") as f:
            qr_b64 = base64.b64encode(f.read()).decode()

        return jsonify({
            "download_url": download_page_url,
            "direct_download_url": direct_download_url,
            "qrcode_b64": "data:image/png;base64," + qr_b64
        })
    except Exception as e:
        logger.exception(f"Failed to finalize session {session_id}: {e}")
        return jsonify({"error": "결과 이미지를 저장하지 못했습니다."}), 500

# 다운로드 페이지
@app.route("/dl/<folder>/")
def download_page(folder):
    return render_template("download.html", folder=folder, lan_url=LAN_URL)

@app.route("/download/<folder>/")
def download_image(folder):
    return send_from_directory(
        os.path.join(PUBLIC_DIR, folder),
        "result.png",
        as_attachment=True,
        download_name=f"photo_{folder}.png"
    )

@app.route("/public/<folder>/<filename>")
def serve_image(folder, filename):
    if filename != "result.png" and not is_admin_authenticated():
        abort(401)
    return send_from_directory(os.path.join(PUBLIC_DIR, folder), filename)


@app.route("/admin_session_image/<session_id>/<image_type>")
@admin_required
def admin_session_image(session_id, image_type):
    if image_type == "raw":
        return send_from_directory(TEMP_DIR, f"{session_id}/raw.png")
    if image_type == "result":
        folder = hashlib.sha256(session_id.encode()).hexdigest()[:16]
        public_result_path = os.path.join(PUBLIC_DIR, folder, "result.png")
        if os.path.isfile(public_result_path):
            return send_from_directory(os.path.join(PUBLIC_DIR, folder), "result.png")
        return send_from_directory(PREVIEW_DIR, f"{session_id}.png")
    abort(404)

# 관리자 페이지
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

# 폴더 감지 (watchdog)
class FolderEvent(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            logger.info(f"New Folder Detected: {event.src_path}")

def start_watcher():
    observer = Observer()
    observer.schedule(FolderEvent(), PUBLIC_DIR, recursive=True)
    observer.start()

if __name__ == "__main__":
    if ADMIN_PASSWORD_WAS_GENERATED:
        logger.warning(f"Temporary admin password: {ADMIN_PASSWORD}")
    start_watcher()
    app.run(host="0.0.0.0", port=5000, debug=False)
