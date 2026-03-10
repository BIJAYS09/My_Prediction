# Multi-stage Dockerfile for QuantAI with React Frontend
# Stage 1: Build React Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend-react

# Copy frontend package files
COPY frontend-react/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source
COPY frontend-react .

# Build optimized production bundle
RUN npm run build

# Stage 2: Build Python Backend
FROM python:3.12-slim AS backend-builder

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Stage 3: Final Runtime Image
FROM python:3.12-slim

WORKDIR /app

# Copy installed Python packages from backend-builder
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy backend application files
COPY --from=backend-builder /app /app

# Copy built React frontend into static serving directory
COPY --from=frontend-builder /app/frontend-react/dist ./static

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

EXPOSE 8000

# Run FastAPI server (which serves React static files)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
