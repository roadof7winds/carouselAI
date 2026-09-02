FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY rules ./rules

RUN pip install --no-cache-dir -e .

ENV CAROUSELAI_DATA_DIR=/app/data
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["python", "-m", "carouselai.web.app"]
