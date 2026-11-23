import logging
import os
import sys
from dotenv import load_dotenv
from shop_model.config import data_path, load_config
from shop_model.data import load_data, training_window
from shop_model.features import add_vat
from shop_model.logging_setup import setup_logging
from shop_model.model import save_model, train_model
from shop_model.seed import set_seed

logger = logging.getLogger(__name__)


def main():
    load_dotenv()
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
    try:
        config = load_config()
        set_seed(config["seed"])
        DATA_PATH = data_path(config)
        MODEL_PATH = os.environ.get("MODEL_PATH", config["model_path"])

        df = load_data(DATA_PATH)
        df = training_window(df, config)
        logger.info("Training on %d rows in the training window", len(df))
        df = add_vat(df, config["vat_rate"])
        model = train_model(df, seed=config["seed"])
        save_model(model, MODEL_PATH)
        logger.info("Model saved to %s", MODEL_PATH)
    except Exception:
        logger.exception("Training failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
