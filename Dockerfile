# Use the official Python 3.9 image as the base
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the local code to the container's working directory
COPY . /app

# Install dependencies from requirements.txt (make sure this file exists)
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies (like unzip if needed)
RUN apt-get update && apt-get install -y unzip


CMD ["python3", "--varsion"]
