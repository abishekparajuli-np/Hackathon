from flask import render_template, request, Response, jsonify, url_for
from werkzeug.utils import secure_filename
import os
from main import app
from main.cow_skin_disease import predict_disease
from main.plant_disease import predict_plant_disease
from main.crop_suggestion import predict_crop
from main.camera import (
    generate_plant_frames,
    start_camera,
    stop_camera,
    enable_capture,
    disable_capture,
    get_latest_result,
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html", title="home")


@app.route("/cow_skin_disease", methods=["GET", "POST"])
def cow_diseases():
    result = None
    error = None
    image_path = None
    prediction = None
    confidence = None

    if request.method == "POST":
        symptoms = request.form.get("symptoms")
        file = request.files.get("animal_image")

        if file and file.filename != "":
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image_path = os.path.join(app.config["TEMP_UPLOAD_FOLDER"], filename)
                file.save(image_path)
            else:
                error = "Only JPG, JPEG, PNG files are allowed."

        prediction, confidence = predict_disease(image_path)
        advice_map = {
            "foot-and-mouth": "Isolate the animal immediately and consult a veterinarian.",
            "lumpy": "Vaccination and insect control are recommended.",
            "healthy": "Animal appears healthy. Maintain hygiene and nutrition.",
        }
        result = {
            "disease": prediction,
            "confidence": confidence,
            "advice": advice_map.get(prediction, "Consult a veterinarian."),
        }

        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    return render_template(
        "cow_skin_diseases.html", title="cow_skin_diseases", result=result, error=error
    )


@app.route("/crop_suggestion", methods=["GET", "POST"])
def crop_suggest():
    suggestion = None
    error = None

    if request.method == "POST":
        user_input = {
            "N": float(request.form.get("N")),
            "P": float(request.form.get("P")),
            "K": float(request.form.get("K")),
            "temperature": float(request.form.get("temperature")),
            "humidity": float(request.form.get("humidity")),
            "ph": float(request.form.get("ph")),
            "rainfall": float(request.form.get("rainfall")),
        }

        suggestion = predict_crop(user_input)

    return render_template(
        "crop_suggestion.html",
        title="Crop Suggestion",
        suggestion=suggestion,
        error=error,
    )



@app.route("/plant_camera")
def plant_camera_page():
    return render_template("plant_camera.html", title="Plant Camera")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_plant_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/start_capture", methods=["POST"])
def start_capture():
    """
    Start the camera and enable periodic saving of frames.
    """
    ok = start_camera()
    if not ok:
        return jsonify(status="error", message="Unable to open camera"), 500

    enable_capture()
    return jsonify(status="started")


@app.route("/stop_capture", methods=["POST"])
def stop_capture():
    """
    Disable saving and stop the camera.
    """
  
    disable_capture()
    stop_camera()
    return jsonify(status="stopped")


@app.route("/latest_result")
def latest_result():
    return jsonify(result=get_latest_result())

@app.route("/insights")
def insights():
    return render_template('blog_page.html',title='Insights')