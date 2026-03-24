FROM python:3.11-slim

RUN apt-get update && apt-get install -y libexpat1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy modern metadata
COPY pyproject.toml README.md ./

# Copy source
COPY . .

# Install from pyproject.toml
RUN pip install --no-cache-dir .

CMD ["python", "src/weather_engine/ingestion.py"]
