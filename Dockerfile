# syntax=docker/dockerfile:1
FROM node:22-bookworm AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY scripts ./scripts
COPY pytest.ini .
COPY --from=frontend-build /frontend/dist ./frontend/dist
ENV APP_ENV=production
ENV DATA_DIR=/data
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
