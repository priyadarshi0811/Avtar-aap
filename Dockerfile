# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app-avtar

# Copy everything into container
COPY . .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Expose default port if needed (optional)
EXPOSE 8506

# Run main.py
CMD ["python", "main.py"]
