> **[IMPORTANT]**
> Before running this repository, update `checkpoints.json` and `templates/index.html` to match the Stable Diffusion models installed on your system. Model names, paths, and style settings must agree with your local WebUI configuration.

---

# SnapPocket — AI Photobooth System

> 스냅 한 장, 포켓 속으로.
>
> SnapPocket — Capture. Transform. Save.

**Portable Version is available at [movenb3at/snap-pocket-portable](https://github.com/movenb3at/snap-pocket-portable).**


SnapPocket is a web-based AI photobooth system that automates the entire experience—from camera capture and AI style transformation to QR-based photo delivery.

- AI style transformation powered by Stable Diffusion and `img2img`
- Instant photo downloads through QR codes
- Real-time monitoring of captured and generated images from the admin page
- Local-network operation with optional public access through Cloudflare Tunnel
- Designed for festivals, weddings, brand activations, arcades, and other events

---

## Features

| Feature | Description |
| --- | --- |
| Browser-based camera UI | Captures photos through a streamlined web interface |
| AI image transformation | Applies configured styles through Stable Diffusion WebUI and `img2img` |
| QR-code delivery | Generates mobile-friendly download links for processed photos |
| Admin dashboard | Lists original and generated images in real time |
| LAN and public access | Supports trusted local networks and optional Cloudflare Tunnel URLs |
| Folder monitoring | Detects newly generated images in real time with Watchdog |
| Parallel processing support | Uses Memurai, a Redis-compatible service for Windows, to support concurrent jobs |

---

## System Architecture

```text
[Camera UI] → [Flask Server] → [Stable Diffusion API]
     ↓                                ↓
[QR Generation & Sharing] ← [Save Transformed Results] ← [Admin Dashboard]
```

---

## Tech Stack

| Area | Technology |
| --- | --- |
| Backend | Python, Flask, Watchdog |
| AI engine | Stable Diffusion WebUI (AUTOMATIC1111), `img2img`, ControlNet, optional ADetailer |
| Job processing | Memurai (Redis-compatible service for Windows) |
| QR generation | `qrcode` for Python |
| Frontend | HTML, CSS, JavaScript |
| Image processing | Pillow (PIL) |
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

GPU performance directly affects image-generation time.

### Client PC

- A computer capable of running a modern web browser
- An FHD (1080p), 60 Hz or better webcam
- Network access to the host PC or the generated Cloudflare Tunnel URL

---

## Project Structure

```text
main/
├── app.py                 # Flask backend server
├── checkpoints.json       # AI model and style configuration
├── templates/
│   ├── index.html         # Main camera UI
│   ├── download.html      # Photo download page
│   └── admin.html         # Admin dashboard
├── static/
│   ├── preview/           # Temporary AI-generated previews
│   └── qr/                # Generated QR codes
├── usage/                 # Example photos of GUI
├── public/                # Final user-accessible images
├── temp/                  # Raw captured images
├── run.bat                # Automated startup script
├── requirements.txt       # Python dependencies
└── tunnel_url.txt         # Current Cloudflare Tunnel URL
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

### 4. Install ADetailer (optional)

ADetailer can improve facial details, although stronger corrections may produce results that differ more noticeably from the original photo.

1. Install the following repository through **Extensions → Install from URL**:

   ```text
   https://github.com/Bing-su/adetailer.git
   ```

2. Apply the changes and restart the WebUI.
3. Download the recommended [`face_yolov8m.pt` model](https://huggingface.co/Bingsu/adetailer/blob/main/face_yolov8m.pt) and place it in the ADetailer model directory used by your WebUI installation.

### 5. Install Memurai

Install Memurai to provide the Redis-compatible service required for parallel processing. During setup, register it as a Windows service and confirm that the service is running before starting SnapPocket.

### 6. Clone SnapPocket

Download the repository as a ZIP file or clone it with Git:

```bash
git clone https://github.com/movenb3at/snap-pocket.git
cd snap-pocket/main
```

### 7. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 8. Configure models and styles

Update the following files before launch:

- `checkpoints.json`: match model names, checkpoint paths, prompts, and available styles to your Stable Diffusion installation.
- `templates/index.html`: make sure the styles and options shown in the UI match the entries configured in `checkpoints.json`.

### 9. Start the services

Run:

```bat
run.bat
```

The script opens three Command Prompt windows for the required services. Keep all three windows open while SnapPocket is running.

The local application is available at:

```text
http://127.0.0.1:5000/main_page
```

### 10. Update the Cloudflare Tunnel URL

Copy the Cloudflare URL displayed in the first Command Prompt window, paste it into `tunnel_url.txt`, and save the file.

The temporary `trycloudflare.com` address changes each time the services restart, so `tunnel_url.txt` must be updated after every launch.

To open the public camera page, append `/main_page` to the generated address:

```text
https://<generated-address>.trycloudflare.com/main_page
```

Omitting `/main_page` may result in a 404 response.

---

## Client Setup

### 1. Open the camera page

Connect the client PC through either the generated Cloudflare URL or the host PC's LAN URL:

```text
http://<host-ipv4-address>:5000/main_page
```

For example:

```text
http://192.168.0.10:5000/main_page
```

### 2. Connect and verify the webcam

Connect the FHD webcam to the client PC, allow camera access in the browser, and confirm that the live camera preview appears correctly.

### 3. Use the keyboard shortcut instead of a coin mechanism

When a physical coin mechanism is not connected, press `Ctrl+Alt+P` after taking a photo to provide the equivalent input.

### 4. Allow camera access on an HTTP LAN origin

Chrome may block camera access on a non-HTTPS LAN address. On a trusted local network only:

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

Only add origins that you control and trust. Use HTTPS for public access.

---

## Usage

### Guest Flow

1. Open the camera page and allow camera access.
2. Capture a photo.
3. Choose a style and wait for the AI transformation to finish.
4. Scan the generated QR code.
5. Download the result to a mobile device.

### Admin Flow

1. Open `/admin` on the host, LAN, or public base URL.
2. Review the latest images, which are listed automatically.
3. Compare original captures with generated results.

If the repository is still using a default admin password, change it before exposing the service publicly.

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