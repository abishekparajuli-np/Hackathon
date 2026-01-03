import cv2
import time
import os
import threading
import atexit
from flask import current_app

# Global camera and state
_camera = None
_camera_lock = threading.RLock()
_camera_active = False

# Capture control
_capture_enabled = False
_capture_interval = 10.0  # default seconds between saved frames
_last_save_time = 0.0

# Capture limit control
_capture_max_files = 100      # default max files (0 = unlimited)
_capture_mode = "stop"        # "stop" or "rotate"
_capture_count = 0            # current number of files in CAPTURE_DIR

# Prediction throttling / status
PREDICT_FPS = 1.0
_last_pred_time = 0.0
_latest_result = "Waiting..."

# Default camera properties (can be overridden via Flask config)
_DEFAULTS = {
    "CAMERA_INDEX": 0,
    "CAMERA_BACKEND": None,
    "FRAME_WIDTH": 640,
    "FRAME_HEIGHT": 480,
    "FRAME_FPS": 30,
    "FOURCC": "MJPG",
    # default temp/capture dir (will usually be overridden by app config)
    "TEMP_UPLOAD_FOLDER": os.path.join(os.path.abspath(os.getcwd()), "tmp_uploads"),
    "CAPTURE_DIR": os.path.join(os.path.abspath(os.getcwd()), "tmp_uploads"),
    "PREDICT_FPS": 1.0,
    "CAPTURE_INTERVAL": 10.0,
    "CAPTURE_MAX_FILES": 100,
    "CAPTURE_MODE": "stop",
    "DELETE_CAPTURES_ON_STOP": False,
}

# ensure default folder exists
os.makedirs(_DEFAULTS["CAPTURE_DIR"], exist_ok=True)


def _release_camera_internal():
    global _camera, _camera_active
    with _camera_lock:
        try:
            if _camera is not None:
                try:
                    _camera.release()
                except Exception:
                    pass
                _camera = None
            _camera_active = False
        except Exception:
            pass


atexit.register(_release_camera_internal)


def _cfg(key):
    """
    Read config from Flask current_app if available, otherwise fall back to defaults.
    """
    try:
        if current_app:
            return current_app.config.get(key, _DEFAULTS.get(key))
    except RuntimeError:
        # current_app not available (outside app context)
        pass
    return _DEFAULTS.get(key)


def _init_camera():
    """
    Initialize and configure the global camera if not already opened.
    Returns True on success, False otherwise.
    """
    global _camera
    with _camera_lock:
        if _camera is not None and getattr(_camera, "isOpened", lambda: False)():
            return True

        backend = _cfg("CAMERA_BACKEND")
        index = _cfg("CAMERA_INDEX") or 0

        try:
            if backend:
                _camera = cv2.VideoCapture(index, backend)
            else:
                _camera = cv2.VideoCapture(index)
        except Exception:
            _camera = None

        if not getattr(_camera, "isOpened", lambda: False)():
            try:
                if _camera is not None:
                    _camera.release()
            except Exception:
                pass
            _camera = None
            return False

        # configure camera properties (drivers may ignore some)
        try:
            width = int(_cfg("FRAME_WIDTH") or 640)
            height = int(_cfg("FRAME_HEIGHT") or 480)
            fps = int(_cfg("FRAME_FPS") or 30)
            fourcc = _cfg("FOURCC")

            _camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            _camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            _camera.set(cv2.CAP_PROP_FPS, fps)
            if fourcc:
                try:
                    _camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*str(fourcc)))
                except Exception:
                    pass
        except Exception:
            pass

        # warm up
        time.sleep(0.15)
        return True


def start_camera():
    """
    Open camera and load capture configuration.
    Returns True if camera started successfully.
    """
    global _camera_active, PREDICT_FPS, _capture_interval, _capture_max_files, _capture_mode, _capture_count
    with _camera_lock:
        ok = _init_camera()
        if not ok:
            _camera_active = False
            print("camera.py: Error - Unable to open webcam.")
            return False
        _camera_active = True
        try:
            PREDICT_FPS = float(_cfg("PREDICT_FPS") or PREDICT_FPS)
        except Exception:
            pass
        try:
            _capture_interval = float(_cfg("CAPTURE_INTERVAL") or _capture_interval)
        except Exception:
            pass
        try:
            _capture_max_files = int(_cfg("CAPTURE_MAX_FILES") or 0)
        except Exception:
            _capture_max_files = 0
        try:
            mode = str(_cfg("CAPTURE_MODE") or "stop").lower()
            _capture_mode = "rotate" if mode == "rotate" else "stop"
        except Exception:
            _capture_mode = "stop"

        # count existing files in capture dir
        capture_dir = _cfg("CAPTURE_DIR") or _DEFAULTS["CAPTURE_DIR"]
        try:
            os.makedirs(capture_dir, exist_ok=True)
            files = [
                f for f in os.listdir(capture_dir)
                if os.path.isfile(os.path.join(capture_dir, f))
            ]
            _capture_count = len(files)
        except Exception:
            _capture_count = 0

        print(f"camera.py: Camera started. capture_max={_capture_max_files} mode={_capture_mode} current_count={_capture_count} interval={_capture_interval}s")
        return True


def _clear_dir_files(dirpath):
    """
    Remove all regular files in dirpath. Return count removed.
    """
    removed = 0
    try:
        if not os.path.isdir(dirpath):
            return 0
        for fn in os.listdir(dirpath):
            path = os.path.join(dirpath, fn)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    removed += 1
            except Exception:
                pass
    except Exception:
        pass
    return removed


def clear_captures():
    """
    Public: delete all saved captures in CAPTURE_DIR. Returns number deleted.
    """
    capture_dir = _cfg("CAPTURE_DIR") or _DEFAULTS["CAPTURE_DIR"]
    with _camera_lock:
        removed = _clear_dir_files(capture_dir)
        # reset count
        global _capture_count
        _capture_count = 0
    print(f"camera.py: clear_captures removed {removed} files from {capture_dir}")
    return removed


def stop_camera():
    """
    Stop and release camera. Optionally delete captures if DELETE_CAPTURES_ON_STOP is True.
    """
    global _camera_active, _capture_enabled
    with _camera_lock:
        _capture_enabled = False
        _camera_active = False
        try:
            delete_on_stop = bool(_cfg("DELETE_CAPTURES_ON_STOP"))
        except Exception:
            delete_on_stop = False

        if delete_on_stop:
            capture_dir = _cfg("CAPTURE_DIR") or _DEFAULTS["CAPTURE_DIR"]
            removed = _clear_dir_files(capture_dir)
            print(f"camera.py: stop_camera cleared {removed} files from {capture_dir}")
            global _capture_count
            _capture_count = 0

        _release_camera_internal()
        print("camera.py: Camera stopped.")


def enable_capture():
    """
    Enable periodic saving of frames.
    """
    global _capture_enabled
    with _camera_lock:
        _capture_enabled = True
    print("camera.py: Capture enabled.")


def disable_capture():
    """
    Disable periodic saving of frames.
    """
    global _capture_enabled
    with _camera_lock:
        _capture_enabled = False
    print("camera.py: Capture disabled.")


def is_capture_enabled():
    with _camera_lock:
        return bool(_capture_enabled)


def is_camera_active():
    with _camera_lock:
        return bool(_camera_active and _camera is not None and getattr(_camera, "isOpened", lambda: False)())


def get_latest_result():
    return _latest_result


def get_capture_status():
    """
    Returns a dict with capture status useful for UI: enabled, max_files, mode, current_count, interval.
    """
    return {
        "enabled": is_capture_enabled(),
        "max_files": _capture_max_files,
        "mode": _capture_mode,
        "current_count": _capture_count,
        "interval": _capture_interval,
    }


# Placeholder: replace with your actual model inference
def predict_plant_disease(image_path):
    return "Healthy Plant"


def _remove_oldest_file_in_dir(dirpath):
    """
    Remove the oldest file in dirpath. Return True if removed.
    """
    try:
        entries = [
            (os.path.join(dirpath, fn), os.path.getmtime(os.path.join(dirpath, fn)))
            for fn in os.listdir(dirpath)
            if os.path.isfile(os.path.join(dirpath, fn))
        ]
        if not entries:
            return False
        entries.sort(key=lambda x: x[1])
        oldest = entries[0][0]
        os.remove(oldest)
        return True
    except Exception:
        return False


def generate_plant_frames():
    """
    MJPEG generator: captures frames, runs throttled prediction, overlays text, and saves frames
    periodically when capture is enabled while enforcing the capture limit/mode.
    """
    global _camera, _last_pred_time, _latest_result, _camera_active, _last_save_time, _capture_count, _capture_enabled

    temp_dir = _cfg("TEMP_UPLOAD_FOLDER") or _DEFAULTS["TEMP_UPLOAD_FOLDER"]
    capture_dir = _cfg("CAPTURE_DIR") or _DEFAULTS["CAPTURE_DIR"]
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(capture_dir, exist_ok=True)

    # ensure camera is initialized if start_camera wasn't explicitly called
    with _camera_lock:
        if _camera is None and _camera_active:
            _init_camera()

    while True:
        if not is_camera_active():
            time.sleep(0.1)
            continue

        with _camera_lock:
            if _camera is None:
                if not _init_camera():
                    time.sleep(0.1)
                    continue
            try:
                success, frame = _camera.read()
            except Exception:
                success, frame = False, None

        if not success or frame is None:
            time.sleep(0.02)
            continue

        now = time.time()
        # prediction throttling
        if now - _last_pred_time >= (1.0 / max(0.0001, PREDICT_FPS)):
            tmpname = f"camera_frame_{int(now*1000)}.jpg"
            temp_path = os.path.join(temp_dir, tmpname)
            try:
                cv2.imwrite(temp_path, frame)
                try:
                    _latest_result = predict_plant_disease(temp_path) or _latest_result
                except Exception as e:
                    print("camera.py: Prediction error:", e)
                # remove temp prediction file
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass
            except Exception as e:
                print("camera.py: Failed to write/remove temp frame:", e)
            _last_pred_time = now

        # Capture saving with limit enforcement
        try:
            save_now = False
            with _camera_lock:
                cap_enabled = _capture_enabled
                max_files = _capture_max_files
                mode = _capture_mode
                cur_count = _capture_count

            if cap_enabled and (now - _last_save_time >= _capture_interval):
                if max_files <= 0:
                    save_now = True
                else:
                    if cur_count < max_files:
                        save_now = True
                    else:
                        if mode == "rotate":
                            removed = _remove_oldest_file_in_dir(capture_dir)
                            if removed:
                                with _camera_lock:
                                    _capture_count = max(0, _capture_count - 1)
                                save_now = True
                            else:
                                save_now = False
                        else:  # stop
                            with _camera_lock:
                                _capture_enabled = False
                            print("camera.py: Capture limit reached — automatic capture disabled (mode=stop).")
                            save_now = False

            if save_now:
                filename = time.strftime("img_%Y%m%d_%H%M%S.jpg")
                save_path = os.path.join(capture_dir, filename)
                try:
                    cv2.imwrite(save_path, frame)
                    _last_save_time = now
                    with _camera_lock:
                        _capture_count += 1
                    print(f"camera.py: Saved capture -> {save_path} (count={_capture_count})")
                except Exception as e:
                    print("camera.py: Failed to save capture:", e)
        except Exception as e:
            print("camera.py: Error during capture save check:", e)

        # Overlay the prediction text
        try:
            cv2.putText(
                frame,
                f"Disease: {_latest_result}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
        except Exception:
            pass

        # Encode frame
        try:
            ok, buffer = cv2.imencode(".jpg", frame)
            if not ok:
                time.sleep(0.01)
                continue
            frame_bytes = buffer.tobytes()
        except Exception:
            time.sleep(0.01)
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" +
               frame_bytes +
               b"\r\n")