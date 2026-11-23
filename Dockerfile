FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml .
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir --no-deps .

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}
EXPOSE 8888
CMD ["uvicorn", "shop_model.api:app", "--host", "0.0.0.0", "--port", "8888"]
