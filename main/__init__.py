from flask import Flask
import os

app=Flask(__name__)
TMP_DIR = os.path.abspath(os.path.join(os.getcwd(), "tmp_uploads"))
os.makedirs(TMP_DIR, exist_ok=True)

    # Camera/capture configuration (tweak as required)
app.config["TEMP_UPLOAD_FOLDER"] = TMP_DIR         # temporary prediction files
app.config["CAPTURE_DIR"] = TMP_DIR               # where saved photos go
app.config["CAPTURE_INTERVAL"] = 10.0              # one picture every 10 seconds
app.config["CAPTURE_MAX_FILES"] = 100              # maximum number of saved pictures
app.config["CAPTURE_MODE"] = "stop"                # "stop" (disable on limit) or "rotate"
app.config["DELETE_CAPTURES_ON_STOP"] = False
TEMP_UPLOAD_FOLDER = "tmp_uploads"
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

app.config["TEMP_UPLOAD_FOLDER"] = TEMP_UPLOAD_FOLDER

from main import routes

