import tensorflow as tf
import numpy as np
import cv2
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "cow_skin_disease_model1.keras")


model = tf.keras.models.load_model(MODEL_PATH)


CLASS_NAMES = ['foot-and-mouth', 'healthy', 'lumpy']

def predict_disease(image_path):

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Image not found at path: {image_path}")

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    img = cv2.resize(img, (224, 224))

    
    img = img / 255.0

    img = np.expand_dims(img, axis=0)  

    
    preds = model.predict(img)
    index = int(np.argmax(preds))
    confidence = float(np.max(preds)) * 100

    return CLASS_NAMES[index], confidence
