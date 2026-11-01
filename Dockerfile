FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.lock README.md ./
COPY src ./src
COPY data/demo ./data/demo
RUN pip install --no-cache-dir --constraint requirements.lock . && python -m recommendation_engine demo
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8003
CMD ["uvicorn", "recommendation_engine.api:app", "--host", "0.0.0.0", "--port", "8003"]
