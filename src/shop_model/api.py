import logging
import os
import threading
import time
from contextlib import asynccontextmanager
import joblib
import mlflow
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from shop_model.config import load_config
from shop_model.db import save_prediction
from shop_model.features import add_vat
from shop_model.logging_setup import setup_logging
from shop_model.metrics import INPUTS, LATENCY, PREDICTIONS

load_dotenv()
setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

config = load_config()
APP_VERSION = os.environ.get("APP_VERSION", "dev")
MODEL_URI = os.environ.get("MODEL_URI", f"models:/{config['mlflow']['model_name']}@champion")

state = {"model": None, "model_version": None}

def load_model(uri):
    if not uri.startswith("models:/"):
        return joblib.load(uri), f"file:{uri}"
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", config["mlflow"]["tracking_uri"]))
    name, alias = uri.removeprefix("models:/").split("@")
    version = mlflow.MlflowClient().get_model_version_by_alias(name, alias).version
    return mlflow.sklearn.load_model(f"models:/{name}/{version}"), f"{name}/{version}"

def load_until_ready(uri, wait=5):
    while state["model"] is None:
        try:
            state["model"], state["model_version"] = load_model(uri)
            logger.info("Serving %s (from %s), app version %s", state["model_version"], uri, APP_VERSION)
        except Exception as err:
            logger.warning("No model loaded yet, retrying in %d s: %s", wait, err)
            time.sleep(wait)

@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=load_until_ready, args=(MODEL_URI,), daemon=True).start()
    yield

app = FastAPI(title="Shop sales model", lifespan=lifespan)

class Item(BaseModel):
    price: float

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready(response: Response):
    if state["model"] is None:
        response.status_code = 503
        return {"ready": False, "model_version": None}
    return {"ready": True, "model_version": state["model_version"], "app_version": APP_VERSION}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/predict")
def predict(item: Item):
    if state["model"] is None:
        raise HTTPException(status_code=503, detail="No model loaded")
    with LATENCY.time():
        df = add_vat(pd.DataFrame({"price": [item.price]}), config["vat_rate"])
        probability = float(state["model"].predict_proba(df[["price"]])[0][1])
        logger.info("price=%.2f probability=%.3f model=%s", item.price, probability, state["model_version"])
        save_prediction(item.price, probability, state["model_version"])
        PREDICTIONS.inc()
        INPUTS.observe(item.price)
    return {"price": item.price, "probability_sold": round(probability, 3), "model_version": state["model_version"]}
