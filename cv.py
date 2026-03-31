"""
Gesture-Based Volume Control
==============================
Control system volume using the distance between your thumb and index finger.
Optimized for Intel i5-12500H + Iris Xe Graphics.

Author: Gesture Volume Control Project
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import platform
import sys

# ── Platform-specific volume control ──────────────────────────────────────────
SYSTEM = platform.system()

# if SYSTEM == "Windows":
#     try:
#         from ctypes import cast, POINTER
#         from comtypes import CLSCTX_ALL
#         from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
#         _devices = AudioUtilities.GetSpeakers()
#         _interface = _devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
#         _volume_obj = cast(_interface, POINTER(IAudioEndpointVolume))
#         VOL_MIN, VOL_MAX = _volume_obj.GetVolumeRange()[:2]
#         BACKEND = "pycaw"
#     except ImportError:
#         print("[WARN] pycaw not found → using mock volume (install pycaw for real control)")
#         BACKEND = "mock"
if SYSTEM == "Windows":
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()

        # 🔥 FIX: ensure proper COM interface activation
        interface = devices.Activate(
            IAudioEndpointVolume._iid_,
            CLSCTX_ALL,
            None
        )

        volume = cast(interface, POINTER(IAudioEndpointVolume))

        VOL_MIN, VOL_MAX = volume.GetVolumeRange()[:2]

        _volume_obj = volume  # keep same variable name used later
        BACKEND = "pycaw"

    except Exception as e:
        print(f"[WARN] Pycaw error: {e} → using mock volume")
        BACKEND = "mock"

elif SYSTEM == "Linux":
    import subprocess
    BACKEND = "alsa"

elif SYSTEM == "Darwin":
    import subprocess
    BACKEND = "osascript"

else:
    BACKEND = "mock"


# def set_system_volume(percent: float):
#     """Set system volume to percent (0–100)."""
#     pct = max(0.0, min(100.0, percent))
#     if BACKEND == "pycaw":
#         vol_db = VOL_MIN + (VOL_MAX - VOL_MIN) * (pct / 100.0)
#         _volume_obj.SetMasterVolumeLevel(vol_db, None)
#     elif BACKEND == "alsa":
#         subprocess.run(
#             ["amixer", "-q", "sset", "Master", f"{int(pct)}%"],
#             capture_output=True,
#         )
#     elif BACKEND == "osascript":
#         subprocess.run(
#             ["osascript", "-e", f"set volume output volume {int(pct)}"],
#             capture_output=True,
#         )
    # mock: no-op

import os

def set_system_volume(percent):
    os.system(f"nircmd.exe setsysvolume {int(percent * 655.35)}")


# ── MediaPipe setup ────────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles
# Temporary compatibility fix
# mp_hands = mp.solutions.hands if hasattr(mp, "solutions") else mp.python.solutions.hands
# mp_draw  = mp.solutions.drawing_utils if hasattr(mp, "solutions") else mp.python.solutions.drawing_utils
# mp_styles = mp.solutions.drawing_styles if hasattr(mp, "solutions") else mp.python.solutions.drawing_styles

HAND_CONNECTIONS = mp_hands.HAND_CONNECTIONS

# Landmark indices
THUMB_TIP  = 4
INDEX_TIP  = 8
WRIST      = 0

# ── Config ────────────────────────────────────────────────────────────────────
# Distance range (in pixels) mapped to 0–100% volume.
# Calibrated for typical 720p webcam at ~50 cm distance.
DIST_MIN   = 30    # thumb & index nearly touching  → 0 %
DIST_MAX   = 220   # fully spread                   → 100 %

SMOOTHING  = 0.15  # EMA factor (lower = smoother, higher = more responsive)
FONT       = cv2.FONT_HERSHEY_SIMPLEX

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG       = (18,  18,  18)
C_ACCENT   = (0,  230, 180)   # teal
C_WARN     = (0,  120, 255)   # orange
C_WHITE    = (240, 240, 240)
C_DARK     = (40,  40,  40)
C_RED      = (60,  60,  220)
C_MUTE     = (0,   60, 200)


# ── Utility helpers ───────────────────────────────────────────────────────────

def landmark_px(lm, w, h):
    return int(lm.x * w), int(lm.y * h)


def euclidean(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def draw_rounded_rect(img, x1, y1, x2, y2, r, color, thickness=-1, alpha=1.0):
    """Draw a filled or outlined rounded rectangle."""
    if thickness == -1:
        overlay = img.copy()
        cv2.rectangle(overlay, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(overlay, (x1, y1 + r), (x2, y2 - r), color, -1)
        for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:
            cv2.circle(overlay, (cx, cy), r, color, -1)
        if alpha < 1.0:
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
        else:
            img[:] = overlay
    else:
        cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, thickness)
        cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, thickness)
        for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:
            cv2.circle(img, (cx, cy), r, color, thickness)


def draw_volume_bar(frame, vol_pct, x, y, w, h):
    """Draw a vertical volume bar with gradient fill."""
    draw_rounded_rect(frame, x, y, x+w, y+h, 8, C_DARK)
    fill = int((vol_pct / 100.0) * (h - 4))
    if fill > 0:
        fy = y + h - 2 - fill
        # gradient: teal → orange at high volumes
        frac = vol_pct / 100.0
        r = int(0   + frac * 0)
        g = int(230 - frac * 110)
        b = int(180 - frac * 180 + frac * 255)
        draw_rounded_rect(frame, x+2, fy, x+w-2, y+h-2, 6, (b, g, r))
    # percentage text
    cv2.putText(frame, f"{int(vol_pct)}%", (x - 2, y + h + 22),
                FONT, 0.55, C_WHITE, 1, cv2.LINE_AA)


def draw_ui_panel(frame, vol_pct, dist, fps, muted, hand_detected):
    h, w = frame.shape[:2]

    # ── top bar ──────────────────────────────────────────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 52), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    title = "✋  Gesture Volume Control"
    cv2.putText(frame, title, (14, 34), FONT, 0.75, C_ACCENT, 2, cv2.LINE_AA)

    fps_txt = f"FPS: {fps:.0f}"
    fps_color = C_ACCENT if fps >= 20 else C_WARN
    cv2.putText(frame, fps_txt, (w - 110, 34), FONT, 0.6, fps_color, 1, cv2.LINE_AA)

    # ── volume bar (right side) ───────────────────────────────────────────────
    bar_x, bar_y, bar_w, bar_h = w - 54, 70, 28, h - 140
    draw_volume_bar(frame, vol_pct, bar_x, bar_y, bar_w, bar_h)
    cv2.putText(frame, "VOL", (bar_x - 1, bar_y - 10), FONT, 0.45, C_WHITE, 1, cv2.LINE_AA)

    # ── status badge ─────────────────────────────────────────────────────────
    badge_color = C_MUTE if muted else (C_DARK if not hand_detected else C_ACCENT)
    badge_txt   = "MUTED" if muted else ("NO HAND" if not hand_detected else "ACTIVE")
    draw_rounded_rect(frame, 12, h - 56, 130, h - 20, 6, badge_color, alpha=0.85)
    cv2.putText(frame, badge_txt, (22, h - 31), FONT, 0.55, C_WHITE, 1, cv2.LINE_AA)

    # ── distance readout ─────────────────────────────────────────────────────
    if hand_detected:
        cv2.putText(frame, f"dist: {int(dist)}px", (145, h - 31),
                    FONT, 0.5, (160, 160, 160), 1, cv2.LINE_AA)

    # ── hint bar ─────────────────────────────────────────────────────────────
    overlay2 = frame.copy()
    cv2.rectangle(overlay2, (0, h - 22), (w, h), (10, 10, 10), -1)
    cv2.addWeighted(overlay2, 0.7, frame, 0.3, 0, frame)
    cv2.putText(frame, "Q: quit   M: mute   R: recalibrate",
                (10, h - 6), FONT, 0.38, (120, 120, 120), 1, cv2.LINE_AA)


def draw_hand_overlay(frame, thumb, index, mid, vol_pct, muted):
    """Draw connection line, circles and volume bubble between thumb & index."""
    color = C_MUTE if muted else C_ACCENT
    # line between thumb and index
    cv2.line(frame, thumb, index, color, 3, cv2.LINE_AA)

    # endpoint circles
    cv2.circle(frame, thumb, 12, color, -1)
    cv2.circle(frame, thumb,  12, C_WHITE, 2)
    cv2.circle(frame, index, 12, color, -1)
    cv2.circle(frame, index,  12, C_WHITE, 2)

    # midpoint bubble
    cv2.circle(frame, mid, 20, color, -1)
    cv2.circle(frame, mid, 20, C_WHITE, 2)
    txt = f"{int(vol_pct)}%"
    ts = cv2.getTextSize(txt, FONT, 0.5, 1)[0]
    cv2.putText(frame, txt, (mid[0] - ts[0]//2, mid[1] + 5),
                FONT, 0.5, C_WHITE, 1, cv2.LINE_AA)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Gesture-Based Volume Control")
    print(f"  Platform : {SYSTEM}  |  Backend: {BACKEND}")
    print("  Controls : Q=quit  M=mute  R=recalibrate")
    print("=" * 55)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        sys.exit("[ERROR] Cannot open webcam. Check connection.")

    # Lower resolution for better performance on Iris Xe
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.75,
        min_tracking_confidence=0.65,
        model_complexity=0,          # fastest model – great for Iris Xe
    )

    smooth_vol   = 50.0             # EMA-smoothed volume %
    muted        = False
    vol_before_mute = 50.0
    hand_detected   = False
    raw_dist        = 0.0

    prev_time = time.time()
    fps       = 0.0

    # calibration range (can be adjusted at runtime)
    dist_min = DIST_MIN
    dist_max = DIST_MAX

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Frame drop – retrying…")
            continue

        frame = cv2.flip(frame, 1)          # mirror
        h, w  = frame.shape[:2]

        # ── FPS ──────────────────────────────────────────────────────────────
        now      = time.time()
        fps      = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
        prev_time = now

        # ── Hand detection ────────────────────────────────────────────────────
        rgb         = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results     = hands.process(rgb)
        rgb.flags.writeable = True

        hand_detected = results.multi_hand_landmarks is not None

        if hand_detected:
            hand_lms = results.multi_hand_landmarks[0]

            # Draw skeleton
            mp_draw.draw_landmarks(
                frame, hand_lms, HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )

            # Key points
            thumb = landmark_px(hand_lms.landmark[THUMB_TIP],  w, h)
            index = landmark_px(hand_lms.landmark[INDEX_TIP],  w, h)
            mid   = ((thumb[0] + index[0]) // 2, (thumb[1] + index[1]) // 2)

            raw_dist  = euclidean(thumb, index)
            vol_pct   = np.interp(raw_dist, [dist_min, dist_max], [0, 100])
            vol_pct   = float(np.clip(vol_pct, 0, 100))

            # Exponential moving average smoothing
            smooth_vol = smooth_vol + SMOOTHING * (vol_pct - smooth_vol)

            if not muted:
                set_system_volume(smooth_vol)

            draw_hand_overlay(frame, thumb, index, mid, smooth_vol, muted)

        # ── Composite UI ──────────────────────────────────────────────────────
        draw_ui_panel(frame, smooth_vol, raw_dist, fps, muted, hand_detected)

        cv2.imshow("Gesture Volume Control", frame)

        # ── Key handling ──────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('m'):
            muted = not muted
            if muted:
                vol_before_mute = smooth_vol
                set_system_volume(0)
                print("[INFO] Muted")
            else:
                set_system_volume(smooth_vol)
                print("[INFO] Unmuted")
        elif key == ord('r'):
            dist_min = DIST_MIN
            dist_max = DIST_MAX
            print("[INFO] Calibration reset")

    cap.release()
    cv2.destroyAllWindows()
    hands.close()
    print("[INFO] Exited cleanly.")


if __name__ == "__main__":
    main()