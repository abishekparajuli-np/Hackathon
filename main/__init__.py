from flask import Flask
import os

app=Flask(__name__)
TEMP_UPLOAD_FOLDER = "tmp_uploads"
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

app.config["TEMP_UPLOAD_FOLDER"] = TEMP_UPLOAD_FOLDER

from main import routes

