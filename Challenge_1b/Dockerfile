FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Copy NLTK download script
COPY download_nltk.py .

# Download NLTK data during build
RUN python download_nltk.py

# Copy the application
COPY pdf_analyzer.py .

# Create directories for collections
RUN mkdir -p /app/collections

# Set permissions
RUN chmod +x pdf_analyzer.py

# Default command
CMD ["python", "pdf_analyzer.py", "--help"]