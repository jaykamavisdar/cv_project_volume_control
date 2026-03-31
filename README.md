# 🖐️ Gesture-Based Volume Control

> Control your system volume in real-time using only the distance between your **thumb** and **index finger** — no buttons, no sliders, just your hand.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?logo=python" />
  <img src="https://img.shields.io/badge/OpenCV-4.8%2B-green?logo=opencv" />
  <img src="https://img.shields.io/badge/MediaPipe-0.10%2B-orange" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey" />
  <img src="https://img.shields.io/badge/Hardware-Intel%20Iris%20Xe-0071C5?logo=intel" />
</p>

---

## 📸 How It Works

```
Thumb & Index CLOSE  →  🔇 0% Volume
      ↕  (spread fingers apart)
Thumb & Index FAR    →  🔊 100% Volume
```

The app uses **MediaPipe Hands** to detect 21 hand landmarks in real-time, measures the Euclidean distance between the thumb tip and index fingertip, maps that distance to a 0–100% volume range, and applies **Exponential Moving Average (EMA) smoothing** to eliminate jitter before setting the OS volume.

---

## 🔧 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | Intel Core i5 (8th gen+) | ✅ Intel i5-12500H |
| **GPU** | Integrated | ✅ Intel Iris Xe (MediaPipe uses OpenCL) |
| **RAM** | 4 GB | 8 GB |
| **Webcam** | 720p 30fps | 1080p 60fps |
| **Python** | 3.9 | 3.10 / 3.11 |
| **OS** | Windows 10/11, Ubuntu 20.04+, macOS 12+ | Windows 11 |

> **Intel i5-12500H + Iris Xe note:** The app uses `model_complexity=0` in MediaPipe (fastest model) and targets 720p capture so Iris Xe's OpenCL backend handles inference at 25–30 FPS comfortably without needing a discrete GPU.

---

## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/gesture-volume-control.git
cd gesture-volume-control
```

### 2. Create & activate a virtual environment (recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Platform-specific audio setup

<details>
<summary><b>🪟 Windows</b></summary>

Uncomment the `pycaw` and `comtypes` lines in `requirements.txt`, then:
```bash
pip install pycaw comtypes
```
No other setup needed — pycaw talks directly to the Windows Core Audio API.
</details>

<details>
<summary><b>🐧 Linux (Ubuntu / Debian)</b></summary>

The app uses `amixer` (ALSA). Make sure it's installed:
```bash
sudo apt install alsa-utils
```
If you use PulseAudio, run:
```bash
sudo apt install pulseaudio-utils
```
and optionally replace the `amixer` call in `gesture_volume.py` with `pactl set-sink-volume @DEFAULT_SINK@`.
</details>

<details>
<summary><b>🍎 macOS</b></summary>

No extra packages needed — the app uses the built-in `osascript` command.
</details>

---

## ▶️ Running the App

```bash
python gesture_volume.py
```

A window titled **"Gesture Volume Control"** will open showing your webcam feed.

---

## 🎮 Controls

| Key | Action |
|-----|--------|
| **Spread fingers** | Increase volume |
| **Pinch fingers** | Decrease volume |
| `M` | Toggle mute / unmute |
| `R` | Reset calibration to defaults |
| `Q` | Quit the application |

---

## 🖼️ UI Overview

```
┌─────────────────────────────────────────┬───┐
│ ✋ Gesture Volume Control       FPS: 28 │ V │
│                                          │ O │
│   [live webcam feed with hand skeleton] │ L │
│                                          │   │
│   👍←──────────────────→☝️             │ █ │
│          midpoint bubble (vol%)          │ █ │
│                                          │   │
│ [ACTIVE]   dist: 142px                  │67%│
│ Q: quit   M: mute   R: recalibrate      │   │
└──────────────────────────────────────────┴───┘
```

- **Teal line** — live connection between thumb & index tip  
- **Midpoint bubble** — shows current volume percentage  
- **Vertical bar** — colour-coded volume meter (teal → amber at high levels)  
- **Status badge** — `ACTIVE` / `NO HAND` / `MUTED`  

---

## ⚙️ Configuration

Edit the constants at the top of `gesture_volume.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `DIST_MIN` | `30` px | Finger distance → 0% volume |
| `DIST_MAX` | `220` px | Finger distance → 100% volume |
| `SMOOTHING` | `0.15` | EMA factor (0=frozen, 1=raw) |

**Tip:** If the range feels off for your webcam distance, hold your hand at a comfortable position, check the `dist:` readout in the UI, and adjust `DIST_MIN` / `DIST_MAX` accordingly.

---

## 🧠 Technical Deep-Dive

### Hand Landmark Detection
MediaPipe Hands returns 21 3-D landmarks per hand. We use:
- **Landmark 4** → Thumb tip  
- **Landmark 8** → Index finger tip  

### Distance → Volume Mapping
```
distance (px)  →  numpy.interp([DIST_MIN, DIST_MAX], [0, 100])  →  volume %
```

### Smoothing (EMA)
```python
smooth_vol = smooth_vol + α × (raw_vol - smooth_vol)
```
`α = 0.15` gives a ~6-frame lag, eliminating jitter without noticeable delay.

### Volume Backend
| OS | API used |
|----|----------|
| Windows | `pycaw` → Windows Core Audio (WASAPI) |
| Linux | `amixer sset Master N%` |
| macOS | `osascript` → AppleScript |

---

## 📁 Project Structure

```
gesture-volume-control/
├── gesture_volume.py   # Main application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| Webcam not found | Try `cv2.VideoCapture(1)` instead of `0` |
| Low FPS | Close other apps; ensure Iris Xe drivers are up to date |
| Volume not changing (Windows) | Run as Administrator; install `pycaw` |
| Volume not changing (Linux) | Check `amixer` is installed; verify sink name |
| Hand not detected | Improve lighting; keep hand within 30–70 cm of camera |
| Jittery volume | Increase `SMOOTHING` value (e.g. `0.08`) |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙌 Acknowledgements

- [MediaPipe](https://developers.google.com/mediapipe) by Google — hand landmark detection  
- [OpenCV](https://opencv.org/) — video capture and rendering  
- [pycaw](https://github.com/AndreMiras/pycaw) — Windows audio control  

---

<p align="center">Made with ✋ and Python</p>
