# Multi-stage Dockerfile for QuantAI
# Use an official Python runtime as a parent image
FROM python:3.12-slim AS build

# set workdir
WORKDIR /app

# copy requirements and install dependencies in a separate layer
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy the rest of the application
COPY . .

# final runtime image
FROM python:3.12-slim
WORKDIR /app

# copy installed packages from build stage
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /app /app

# environment variables (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
