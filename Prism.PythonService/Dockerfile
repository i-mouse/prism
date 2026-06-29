FROM python:3.13-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system .
COPY . /app
CMD ["sh", "-c", "uvicorn api:pythonAPI --host 0.0.0.0 --port ${PORT:-8000}"]