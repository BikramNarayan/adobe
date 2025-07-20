FROM --platform=linux/amd64 python:3.10

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Copy the processing script
COPY process_pdfs.py .

# Create input and output directories
RUN mkdir -p /sample_dataset/pdf /sample_dataset/outputs

# Run the script
CMD ["python", "process_pdfs.py"] 