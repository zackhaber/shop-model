import logging

logger = logging.getLogger(__name__)


def add_vat(df, vrate):
    odf = df.copy()
    odf["price"] = odf["price"] * (1 + vrate)
    logger.info("VAT added using rate=%.2f", vrate)
    return odf


def add_vat_overwrite(df, vrate):
    df["price"] = df["price"] * (1 + vrate)
    logger.info("VAT added using rate=%.2f", vrate)
    return df


def add_vat_copy(df, vrate):
    out = df.copy()
    out["price"] = out["price"] * (1 + vrate)
    logger.info("VAT added using rate=%.2f", vrate)
    return out
