FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer — only re-runs when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# The app listens on 8000
EXPOSE 8000

# Run without --reload in the container (production-style).
# Host 0.0.0.0 so it's reachable from outside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]