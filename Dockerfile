FROM python:3.10-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

RUN apt-get update
RUN apt-get install -y curl wget fontconfig xfonts-base xfonts-75dpi

# Download .deb
RUN curl -L -o wkhtmltox_0.12.6-1.buster_amd64.deb https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb

# Install with dpkg
RUN dpkg -i wkhtmltox_0.12.6-1.buster_amd64.deb || apt-get install -f -y \

# Fix missing dependencies
RUN apt-get install -f -y

# Clean up
RUN rm wkhtmltox_0.12.6-1.buster_amd64.deb

RUN rm -rf /var/lib/apt/lists/*


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
