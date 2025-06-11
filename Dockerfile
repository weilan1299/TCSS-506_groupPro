FROM python:3.10-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Install system dependencies including wkhtmltopdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget dpkg xfonts-75dpi xfonts-base fontconfig \
    && wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bookworm_amd64.deb \
    && dpkg -i wkhtmltox_0.12.6-1.bookworm_amd64.deb || true \
    && apt-get install -f -y \
    && rm wkhtmltox_0.12.6-1.bookworm_amd64.deb \
    && rm -rf /var/lib/apt/lists/*


# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install python-docx
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "run.py"]
