> P.S. 이 리포지토리를 사용하기 전, checkpoints.json과 index.html은 자신이 다운받은 stable diffusion 모델에 따라 수정하셔야합니다. 실행 시 참고바랍니다.
>
---

# SnapPocket — AI Photobooth System

---

> 스냅 한 장, 포켓 속으로.
> 
> SnapPocket — Capture. Transform. Save.
> 


SnapPocket은 카메라 촬영 → AI 스타일 변환 → QR 다운로드를 **웹 기반으로 자동 처리**하는 스타일 포토부스 시스템입니다.

- Stable Diffusion 기반 AI 스타일 변환
- QR로 즉시 사진 다운로드
- 관리자 페이지에서 촬영 기록 실시간 모니터링
- 축제, 행사, 웨딩, 브랜드 이벤트 등에 최적화

---

## Features

| 기능 | 상세 설명 |
| --- | --- |
| 카메라 촬영 웹 페이지 | 사용자 인터페이스(UI) 기반 촬영 |
| AI 이미지 스타일 변환 | Stable Diffusion + img2img |
| QR 다운로드 | 모바일 다운로드 최적화 |
| 관리자 시스템 | 모든 촬영 결과 실시간 리스트업 |
| LAN & Public 접근 | 동일 와이파이 + 외부 접속 모두 지원 |
| 폴더 감지 | 실시간 이미지 생성 반영(watchdog) |

---

## System Architecture

```
[Camera UI] → [Flask Server] → [Stable Diffusion API]
     ↓                                ↓
 QR 생성 & 공유 ← 변환 결과 저장 ← 관리자 페이지

```

---

## Tech Stack

| 영역 | 기술 |
| --- | --- |
| Backend | Python, Flask, Watchdog |
| AI Engine | Stable Diffusion (API: Automatic1111 img2img) |
| QR | qrcode(Python) |
| UI | HTML / CSS / JavaScript |
| Image Processing | Pillow (PIL) |
| Deployment | Cloudflared (optional public QR), Local LAN access |

---

## Project Structure

```
main/
   ├─ app.py              # Flask backend server
   ├─ checkpoints.json    # Style configuration
   ├─ templates/
   │   ├─ index.html      # Main UI
   │   ├─ download.html   # Download page UI
   │   └─ admin.html      # Admin UI
   ├─ static/
   │   ├─ preview/        # Temporary AI result images
   │   └─ qr/             # Generated QR codes
   ├─ public/                # Final user-accessible images
   ├─ temp/                  # Raw image storage
   ├─ run.bat                # Automated Start Process
   ├─ requirements.txt       # Python library requirements
   └─ tunnel_url.txt         # Cloudflared public domain

```

---

## Installation & Setup

### 1. 사전 다운로드 및 Stable Diffusion WebUI 실행
[여기서 A1111을 다운받아서 아래 단계를 계속해주세요.](https://github.com/AUTOMATIC1111/stable-diffusion-webui)

[여기서 Controlnet 모델을 다운받아서 stable diffusion에 대응하는 폴더에 넣어주세요.](https://huggingface.co/lllyasviel/sd-controlnet-canny/blob/main/diffusion_pytorch_model.safetensors)

[여기서 Adetailer 모델을 다운받아서 stable diffusion에 대응하는 폴더에 넣어주세요.](https://huggingface.co/Bingsu/adetailer/blob/main/face_yolov8m.pt)


AUTOMATIC1111 실행:

```
./webui-user.bat
```

API와 xformers 활성화 옵션 포함 필요:

```
--api --xformers --reinstall-xformers
```

### 2. Python Dependencies 설치

```
pip install -r requirements.txt
```

### 3. 서버 실행

```
run.bat 실행
```

웹 접속:

```
http://127.0.0.1:5000/main_page
```

### 4. Public Access (via Cloudflared)

터널 생성

```
run.bat 실행
```

성공 시:

```
tunnel_url.txt → https://random-xxxx-xxxx.trycloudflare.com 저장
```

---

## Usage Flow

사용자:

1. 웹 페이지에서 카메라 권한 허용
2. 촬영 버튼 클릭
3. 스타일 선택 → AI 변환 진행
4. QR코드 스캔 → 휴대폰에서 다운로드

관리자:

1. `/admin` 접속
2. 최신 생성 이미지 자동 정렬
3. 원본 + 결과 이미지 확인

---

## Use Cases

| 행사 환경 | 활용 예시 |
| --- | --- |
| 학교 축제 | 학생 포토존 자동화 |
| 웨딩 | 포토부스 실시간 공유 |
| 브랜드 프로모션 | 이벤트 스냅 공유 유도 |
| 아케이드형 | 상시 설치 운영 |

---

## Roadmap

- [25/11/13] 프로젝트 구상 완료
- [25/11/17] 프로젝트 개발 시작
- [25/11/21] 프로젝트 개발 완료
- [25/11/24] README.MD 생성
- [25/12/12] Github 리포지토리 업로드
- [26/01/30] 예외 처리 추가
- [26/03/27] 사진 확인 단축키 변경 (space -> ctrl+alt+p)
- [26/03/28] Adetailer 보정 알고리즘 추가 -> 보류
- [26/04/02] 성별 선택 기능 및 성별 당 프롬프트 설정 기능 추가
- [26/05/04] 프론트엔드 디자인 업데이트 및 병렬 처리 기능 추가
- [26/05/17] 로깅 기능 추가 및 기존 print문 대체
- [26/05/18] admin.html 비밀번호 기능 추가 (admin)
- [26/06/10] download.html에서 "처음으로" 버튼 로직 변경 (history.back() -> LAN_URL)
---

## Future Vision

SnapPocket은 촬영의 끝이 **저장과 공유**가 되는 UX를 목표로 합니다.

오프라인 공간에 AI를 연결하여, **기억을 즉시 디지털화**합니다.

---

## License

AGPL-3.0 License

---

## Credits

Made by: **moveNb3at | SnapPocket Dev Team**

AI Powered by: **Stable Diffusion WebUI (A1111)**

---
> 더 많은 정보는 여기서 확인 가능합니다.
> [SNAP-POCKET 구축 가이드](https://docs.google.com/document/d/1q48TmpIc9Sp4wrk9G2zxNS0PNHSYADuGRAVy11EnbCk/edit?usp=sharing)

🧡 **스냅 한 장, 포켓 속으로 — SnapPocket**