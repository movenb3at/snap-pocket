> **[IMPORTANT]**
> Before running this repository, copy `checkpoints.example.json` to the Git-ignored `checkpoints.json`, then update the local file and `templates/index.html` to match the Stable Diffusion models installed on your system.

---

# SnapPocket — AI Photobooth System

> 스냅 한 장, 포켓 속으로.
>
> SnapPocket — Capture. Transform. Save.

**Portable Version is available at [movenb3at/snap-pocket-portable](https://github.com/movenb3at/snap-pocket-portable).**


SnapPocket is a web-based AI photobooth system that automates the entire experience—from camera capture and AI style transformation to QR-based photo delivery.

- AI style transformation powered by Stable Diffusion and `img2img`
- Optional branded photo frames with live color previews and ten presets
- Per-device coin balances with prepayment, administrator locks, and remote balance controls
- Instant attachment downloads through QR codes
- Password-protected monitoring of devices, captures, previews, and finalized images from the admin page
- Local-network operation with automated HTTPS access through a Cloudflare Quick Tunnel
- Designed for festivals, weddings, brand activations, arcades, and other events

---

## Features

| Feature | Description |
| --- | --- |
| Browser-based camera UI | Waits for camera metadata, preserves the camera's full aspect ratio without cropping or stretching, and limits high-resolution captures to 2,073,600 pixels without upscaling lower-resolution cameras |
| AI image transformation | Applies configured styles through Stable Diffusion WebUI and `img2img` |
| YOLO face mosaic | Detects every face locally with Ultralytics YOLO and pixelates padded face boxes without calling Stable Diffusion |
| Photo framing | Adds an optional date-stamped SnapPocket frame with ten color presets and supports framed original/result comparisons or result-only output |
| Per-device coin control | Accepts prepayment from the camera or download page, consumes one coin only when a capture continues to style selection, and keeps retakes free |
| QR delivery | Serves the finished PNG as an attachment from a scanned QR code |
| Admin dashboard | Shows each device's first-seen time, balance, and lock state; provides remote coin controls; and replaces an intermediate transform preview with the finalized result automatically |
| LAN and public access | Supports trusted local networks and automatically manages a temporary Cloudflare Quick Tunnel URL |
| Folder monitoring | Detects newly generated images in real time with Watchdog |
| Queued job processing | Uses Celery with Memurai to give each client an independent task and process GPU work sequentially |
| Explicit failure handling | Reports upload, queue, Stable Diffusion, and finalization failures instead of silently returning the original photo |

---

## System Architecture

```text
[Camera Clients] → [Flask API] → [Celery Queue / Memurai]
       │                  │                    ├──→ [Stable Diffusion API] → [AI Preview]
[Browser UUID]      [In-memory Coin State]     └──→ [Local YOLO + OpenCV] → [Mosaic Preview]
       │                  │                                      │
[Retake-safe Upload]  [Status Polling] ← [Task State] ←──────────┘
       │                  │
       └────────────→ [Finalize PNG + QR] → [Download Page]
                              │
          [Protected Admin: Devices, Coins, Preview → Final Result]
```

---

## Tech Stack

| Area | Technology |
| --- | --- |
| Backend | Python, Flask, Watchdog |
| AI engine | Stable Diffusion WebUI (AUTOMATIC1111), `img2img`, ControlNet, optional ADetailer, and Ultralytics YOLO face detection |
| Job processing | Celery with Memurai (Redis-compatible service for Windows) |
| QR generation | `qrcode` for Python |
| Frontend | HTML, CSS, JavaScript |
| Image processing | OpenCV for mosaic pixelation, Pillow (PIL), and a local DenkiChip font with Arial fallback for watermarks |
| Connectivity | Local LAN access, optional Cloudflare Tunnel |

---

## Requirements

### Host PC

- Windows (other operating systems have not been fully tested)
- At least 16 GB of RAM
- NVIDIA GeForce RTX 3060 Ti or a comparable or faster NVIDIA GPU
- Python and Git
- Stable Diffusion WebUI by AUTOMATIC1111
- Memurai installed and registered as a Windows service
- A compatible `face_yolov8*.pt` model when using `mosaic_filter`

GPU performance directly affects image-generation time.

### Client PC

- A computer capable of running a modern browser with camera and `localStorage` support
- A browser-compatible webcam of any orientation or resolution
- Network access to the host PC or the generated Cloudflare Tunnel URL

SnapPocket waits until the browser reports the camera's actual dimensions. It preserves the complete source frame without cropping, padding, or stretching. Captures at or below 2,073,600 pixels keep their native resolution; larger captures are reduced proportionally to that pixel limit.

---

## Project Structure

```text
snap-pocket/
├── app.py                 # Flask backend server
├── checkpoints.example.json # Public AI model/style template
├── checkpoints.json       # Local AI model/style configuration (Git-ignored)
├── models/
│   └── mosaic/             # Local face_yolov8*.pt weights (Git-ignored)
├── templates/
│   ├── index.html         # Main camera UI
│   ├── download.html      # Photo download page
│   └── admin.html         # Admin dashboard
├── static/
│   ├── fonts/             # Local UI font and its OFL license
│   ├── preview/           # Temporary AI-generated previews
│   └── qr/                # Generated QR codes
├── usage/                 # Example photos of GUI
├── public/                # Final user-accessible images
├── temp/                  # Raw captured images
├── run.bat                # Automated startup script
├── start_tunnel.ps1       # Quick Tunnel URL discovery and cleanup
├── requirements.txt       # Python dependencies
└── tunnel_url.txt         # Runtime-only Cloudflare Quick Tunnel URL
```
---

## Usage Photos
![main_page_screenshot](./usage/2.png)
![download_page_screenshot](./usage/3.png)
![admin_page_before_login_screenshot](./usage/4.png)
![admin_page_after_login_screenshot](./usage/1.png)

---

## Installation and Setup

### 1. Install Stable Diffusion WebUI

Install [AUTOMATIC1111 Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) by following its official setup instructions.

### 2. Enable API access and xFormers

Open `webui-user.bat` in the `stable-diffusion-webui` directory and set the launch arguments to:

```bat
set COMMANDLINE_ARGS=--api --xformers
```

Run `webui-user.bat`, then confirm that the WebUI is available at:

```text
http://127.0.0.1:7860
```

### 3. Install ControlNet

1. In Stable Diffusion WebUI, open **Extensions → Install from URL**.
2. Enter the following repository URL and install it:

   ```text
   https://github.com/Mikubill/sd-webui-controlnet.git
   ```

3. Open the **Installed** tab and select **Apply and restart UI**.
4. Download the [ControlNet Canny model](https://huggingface.co/lllyasviel/sd-controlnet-canny/blob/main/diffusion_pytorch_model.safetensors).
5. Place the model file in:

   ```text
   stable-diffusion-webui/extensions/sd-webui-controlnet/models/
   ```

### 4. Install ADetailer (optional) and the mosaic YOLO model

ADetailer can improve facial details, although stronger corrections may produce results that differ more noticeably from the original photo.

1. Install the following repository through **Extensions → Install from URL**:

   ```text
   https://github.com/Bing-su/adetailer.git
   ```

2. Apply the changes and restart the WebUI.
3. Download the recommended [`face_yolov8n.pt` model](https://huggingface.co/Bingsu/adetailer/blob/main/face_yolov8n.pt).
4. From the SnapPocket repository root, place the model in the local mosaic directory:

   ```powershell
   New-Item -ItemType Directory -Force models\mosaic
   Copy-Item "C:\path\to\face_yolov8n.pt" models\mosaic\
   ```

The local mosaic filter and ADetailer load models independently. If you also use ADetailer, keep a compatible copy in the model directory used by the WebUI extension. Model weights are not distributed with this repository; download and use them under the upstream project's terms.

### 5. Install Memurai

Install Memurai to provide the Redis-compatible service required for parallel processing. During setup, register it as a Windows service and confirm that the service is running before starting SnapPocket.

### 6. Clone SnapPocket

Download the repository as a ZIP file or clone it with Git:

```bash
git clone https://github.com/movenb3at/snap-pocket.git
cd snap-pocket
```

### 7. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 8. Configure models and styles

Create the private local configuration from the public template:

```powershell
Copy-Item checkpoints.example.json checkpoints.json
```

Then update the following files before launch:

- `checkpoints.json`: enter the real model names, checkpoint paths, prompts, and available styles for your Stable Diffusion installation. This file is intentionally excluded from Git.
- `checkpoints.example.json`: keep only shareable placeholders and the public configuration schema. Commit style-key changes such as `mosaic_filter` here.
- `templates/index.html`: make sure the styles and options shown in the UI match the entries configured in `checkpoints.json`.

Optional `mosaic_filter` keys may be added to the local `checkpoints.json`. When omitted, SnapPocket uses these defaults:

| Key | Default | Accepted range or value |
| --- | --- | --- |
| `yolo_confidence` | `0.3` | `0.01` to `1.0` |
| `yolo_iou` | `0.5` | `0.01` to `1.0` |
| `yolo_imgsz` | `640` | Integer from `320` to `2048` |
| `yolo_device` | `cpu` | Any Ultralytics-supported device string |
| `face_padding_ratio` | `0.12` | `0.0` to `0.5` |
| `mosaic_scale` | `0.08` | `0.01` to `1.0`; smaller values create larger mosaic blocks |

### 9. Start the services

Run:

```bat
run.bat
```

The script starts the Celery worker, Flask server, and Cloudflare tunnel. Keep the launcher and service consoles open while SnapPocket is running.

If `SNAP_POCKET_ADMIN_PASSWORD` is not already set, `run.bat` generates a temporary administrator password and prints it once in the launcher console. To use a fixed password for the current Command Prompt session, set it before launching:

```bat
set SNAP_POCKET_ADMIN_PASSWORD=choose-a-strong-password
run.bat
```

`run.bat` also generates `SNAP_POCKET_SECRET_KEY` when it is not already defined. The key signs Flask administrator sessions and is intentionally regenerated for a new launcher session unless you provide a fixed value.

`run.bat` also calls `start_tunnel.ps1`, so `cloudflared` must be installed and available on `PATH`. The helper waits for the Quick Tunnel URL instead of relying on a fixed delay.

The local application is available at:

```text
http://127.0.0.1:5000/main_page
```

### 10. Use the automatically managed Cloudflare Tunnel URL

No manual copy-and-paste step is required. `start_tunnel.ps1` removes any stale address, starts a Quick Tunnel for `http://localhost:5000`, waits up to 30 seconds for a `trycloudflare.com` URL, and saves it to `tunnel_url.txt` in the UTF-16 format expected by `app.py`.

The temporary address changes each time the services restart. Keep the tunnel console open while SnapPocket is running. When the tunnel stops, the helper removes `tunnel_url.txt` so the application cannot reuse an expired address.

Pages opened through an older Quick Tunnel address cannot discover a replacement address after the tunnel restarts. Keep the same tunnel process running for the full event session, or use a named Cloudflare Tunnel when a stable origin is required.

To open the public camera page, append `/main_page` to the generated address:

```text
https://<generated-address>.trycloudflare.com/main_page
```

Omitting `/main_page` may result in a 404 response.

---

## Client Setup

### 1. Open the camera page

For camera clients, prefer the generated Cloudflare HTTPS URL so browser camera APIs run in a secure context. A host PC or trusted same-network client can also open the LAN URL:

```text
http://<host-ipv4-address>:5000/main_page
```

For example:

```text
http://192.168.0.10:5000/main_page
```

### 2. Connect and verify the webcam

Connect the webcam, allow camera access in the browser, and wait for the capture button to become available. Confirm that the contained preview shows the complete camera frame at its actual aspect ratio. Portrait, 4:3, widescreen, and ultrawide sources are supported.

### 3. Register coins before or after taking a photo

Press `Ctrl+Alt+P` on either the camera page or the download page whenever a coin is inserted. Coins may be registered before a photo is taken and accumulate for that browser device. The photo confirmation dialog shows the current balance; **Continue** consumes one coin, while **Retake** is free and removes the discarded capture's temporary session folder.

Devices are locked by default, which means coins can be added with the keyboard shortcut only. An administrator can unlock a device from `/admin`; while the device is unlocked, an on-screen coin-add button is also available before capture begins.

### 4. Prefer HTTPS for camera access

Browser camera APIs may be unavailable on a non-HTTPS LAN address. The recommended client URL is:

```text
https://<generated-address>.trycloudflare.com/main_page
```

After a completed photo, **Back to Start** uses the relative path `/main_page`, so a download page opened through Cloudflare stays on the same HTTPS origin. If LAN-only testing is required, Chrome can treat a trusted LAN origin as secure on that individual device:

1. Run `ipconfig` on the host PC.
2. Find the IPv4 address under **Wireless LAN adapter Wi-Fi**.
3. Build the exact LAN URL, including the port:

   ```text
   http://<host-ipv4-address>:5000
   ```

4. In Chrome, open:

   ```text
   chrome://flags/#unsafely-treat-insecure-origin-as-secure
   ```

5. Add the LAN origin to **Insecure origins treated as secure**.
6. Restart Chrome and reopen the camera page.

Only add origins that you control and trust. This Chrome flag is a per-device development workaround; use the Cloudflare HTTPS URL for normal client operation.

---

## Usage

### Guest Flow

1. Open the camera page and allow camera access.
2. Register one or more coins with `Ctrl+Alt+P` at any time on the camera or download page.
3. Wait for camera metadata, then capture a photo. The preview uses the camera's actual aspect ratio and the mobile confirmation dialog remains scrollable.
4. Review the remaining coin count. **Retake** is free and deletes the discarded temporary session; **Continue** atomically consumes one coin.
5. Choose a style and gender, then enable only the available ADetailer, frame, color, and result-only options.
6. Wait for the AI transformation and frame composition to finish. Queue wait time is excluded, and the 10-minute limit starts when the Celery worker begins the Stable Diffusion task; a timeout or backend failure is shown as an error instead of silently returning the original photo.
7. Scan the generated QR code to receive the PNG attachment on a mobile device.
8. Use **Back to Start** to open `/main_page` on the same origin as the current download page. A Cloudflare download page therefore returns to the Cloudflare HTTPS camera page.

### YOLO Mosaic Behavior

- Choose **`[필터] 모자이크`** and select a gender because the shared transform form currently requires both fields. Gender does not change the local mosaic result.
- The filter runs locally through Ultralytics YOLO and OpenCV, does not call Stable Diffusion, and does not expose the ADetailer option.
- Every detected face bounding box is expanded by the configured padding ratio before the complete region is pixelated.
- Missing `checkpoints.json`, missing `face_yolov8*.pt` weights, zero detected faces, or PNG encoding failure produces an explicit error. SnapPocket does not return an unprotected original image as a successful mosaic result.

### Frame Output Modes

| Frame | Style | Result only | Final PNG |
| --- | --- | --- | --- |
| Off | No transform | Not available | Original image without a SnapPocket frame |
| Off | Transform or filter | Not available | Transformed result without a SnapPocket frame |
| On | No transform | Not available | Framed original image |
| On | Transform or filter | Off | Framed original + transformed result comparison |
| On | Transform or filter | On | Framed transformed result only |

ADetailer is hidden when the selected style does not support it. **Result only** appears only when a transform or filter other than **No transform** and a frame are both enabled. The transform button remains visible while disabled until the required style and gender selections are complete.

### Admin Flow

1. Open `/admin` on the host, LAN, or public base URL and enter the password printed by `run.bat`, or the value supplied through `SNAP_POCKET_ADMIN_PASSWORD`.
2. Identify each connected browser by its UUID and first-seen timestamp, then review its balance and outline lock indicator.
3. Enter the administrator password when locking or unlocking a device. Unlocking exposes that device's on-screen coin-add button; locking it again returns the device to keyboard-only coin input.
4. Add or subtract one coin remotely. The affected camera or download page shows a green add notification or red subtract notification with the remaining balance.
5. Review automatically sorted captures and the recorded style, gender, ADetailer, frame color, and frame output mode. Frame state is displayed as `미사용`, `사용/단일출력`, or `사용/복수출력`.
6. Select a thumbnail to open the full image. While processing, the card is labeled `변환 미리보기`; after finalization it automatically changes to `Result` and reloads the final framed PNG without a page refresh.

Administrator authentication is verified by Flask. The admin list and original `raw.png` images are unavailable without a valid session; public result downloads continue to work through their QR links.

### Reliability and Multi-device Behavior

- Every browser keeps its own capture approval, upload session, and Celery task ID. One device cannot approve or overwrite another device's capture.
- Each browser origin stores a persistent UUID in `localStorage`, so closing and reopening the window on the same origin keeps the device identity. If a Cloudflare Quick Tunnel restarts with a different hostname, the new origin may create a new device identity.
- Coin balances, lock states, first-seen timestamps, and remote-notification history live only in the Flask server's memory. Restarting the server resets them to an empty state; a returning browser is recreated with zero coins and a locked state.
- One Flask server process can serve multiple independent devices. Coin state is not shared across multiple Flask server processes, so this in-memory design must not be scaled with separate web workers without adding a shared state store.
- Coin consumption and administrator balance changes use the same server lock, preventing simultaneous operations from spending the same coin or producing a negative balance.
- The default `--pool=solo` Celery worker processes transformation tasks one at a time to protect GPU stability. Additional client tasks remain in the queue.
- Queue time in `PENDING` does not consume the transformation timeout. The 10-minute limit starts when the worker reports `STARTED`.
- Stable Diffusion timeouts, invalid responses, queue failures, and missing result files are shown as errors. SnapPocket no longer substitutes the original photo when AI generation fails.
- Mosaic model loading, face detection, and PNG encoding failures are also reported explicitly instead of returning an unprotected original image.
- Retaking a photo aborts the previous upload, ignores late responses, and requests deletion of the discarded session's `temp` folder.

---

## Use Cases

| Environment | Example |
| --- | --- |
| School festival | Automated student photo zone |
| Wedding | Real-time photobooth sharing |
| Brand promotion | Branded event photos and social sharing |
| Arcade or permanent venue | Always-on self-service installation |

---

## Project History

- [2025-11-13] Project concept completed
- [2025-11-17] Development started
- [2025-11-21] Initial development completed
- [2025-11-24] README created
- [2025-12-12] Repository published to GitHub
- [2026-01-30] Exception handling added
- [2026-03-27] Photo confirmation shortcut changed from `Space` to `Ctrl+Alt+P`
- [2026-03-28] ADetailer correction algorithm added, then placed on hold
- [2026-04-02] Gender selection and gender-specific prompt configuration added
- [2026-05-04] Frontend design updated and parallel processing added
- [2026-05-17] Logging added and existing `print` statements replaced
- [2026-05-18] Password protection added to `admin.html`
- [2026-06-10] The **Back to Start** button in `download.html` changed from `history.back()` to `LAN_URL`
- [2026-07-28] Completely changed the design of HTML files.
- [2026-08-04] Added configurable photo frames, orientation-aware collages, direct QR downloads, full-image previews, local watermark fonts, and automatic Cloudflare Quick Tunnel URL management.
- [2026-08-06] Added server-side administrator sessions, explicit transform failure handling, retake race protection, queue-aware 10-minute limits, taller admin previews, and same-origin **Back to Start** navigation.
- [2026-08-31] Added aspect-ratio-safe camera capture, prepayment and per-device in-memory coin balances, administrator device locks and remote coin controls, free retake cleanup, result-only frame output, mobile confirmation scrolling, and automatic admin preview-to-final image refresh.
- [2026-09-01] Added local YOLO face mosaic filtering, Git-ignored `models/mosaic` weights, and a public `checkpoints.example.json` with private local configuration kept in `checkpoints.json`.
- [2026-09-04] Added convex and concave mirror filters, corrected edge-coordinate mapping, and documented the strict mirror-filter key migration.

---

## Vision

SnapPocket is designed to make saving and sharing the natural conclusion of every photo experience.

By bringing AI into physical event spaces, it turns moments into downloadable digital memories in seconds.

---

## License

This project is licensed under the AGPL-3.0 License.

---

## Credits

Created by **moveNb3at | SnapPocket Dev Team**

AI powered by **Stable Diffusion WebUI (AUTOMATIC1111)**

---

For a more detailed setup walkthrough, see the korean document here. [스냅포켓 구축 가이드](https://docs.google.com/document/d/1q48TmpIc9Sp4wrk9G2zxNS0PNHSYADuGRAVy11EnbCk/edit?tab=t.0)

🧡 **스냅 한 장, 포켓 속으로 — SnapPocket**
