import os
import joblib
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
DATASET_DIR=os.path.join(BASE_DIR,"dataset")

pipeline_path = os.path.join(MODEL_DIR, "crop_model.pkl")
encoder_path = os.path.join(MODEL_DIR, "label_encoder.pkl")
dataset_path= os.path.join(DATASET_DIR,"crop_dataset_full.csv")

pipeline = joblib.load(pipeline_path)
label_encoder = joblib.load(encoder_path)
crop_df=pd.read_csv(dataset_path)

def predict_crop(user_input):
    """
    user_input: dict with keys:
    'N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall'
    """

    X = pd.DataFrame([user_input])

    X['NPK_total'] = X['N'] + X['P'] + X['K']
    X['N_P_ratio'] = X['N'] / (X['P'] + 1e-6)
    X['N_K_ratio'] = X['N'] / (X['K'] + 1e-6)
    X['P_K_ratio'] = X['P'] / (X['K'] + 1e-6)
    X['moisture_index'] = X['temperature'] * X['humidity']

    pred_encoded = pipeline.predict(X)

    pred_crop = label_encoder.inverse_transform(pred_encoded)[0]
    crop_info = crop_df[crop_df['label'] == pred_crop][['fertilizer', 'season', 'ph_level', 'rainfall_level']].iloc[0].to_dict()

    return {
        "predicted_crop": pred_crop,
         **crop_info
    }
