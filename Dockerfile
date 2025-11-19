FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies (without dev dependencies)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY src ./src
COPY main.py ./

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/processed /app/data/chunks

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "main.py"]
