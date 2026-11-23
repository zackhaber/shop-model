# Model Card: Shop Sales Model

## Intended Use
- **Primary use:** Helping staff price new shop inventory items based on historical sales probability.
- **Out of scope:** Must not be used for evaluating employee performance or automated customer credit scoring.

## Data
- Trained on `prices_v2.csv` windows starting from August 2026.
- Input features: Pre-VAT item price (in euros).

## Metrics
- Evaluated on a frozen 8-week holdout dataset.
- **Accuracy:** 0.767 (95% CI: 0.683 to 0.842) against a threshold of 0.70.

## Limitations
- Relies on a single feature (price); does not account for seasonality, product categories, or marketing shifts.
- Prices above €81 represent extrapolation.

## Monitoring & Rollback
- Watch input price distributions via Prometheus/Grafana.
- **Rollback command:** `make champion V=1`
