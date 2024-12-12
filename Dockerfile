# Use the official Python 3.9 image as the base
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the local code to the container's working directory
COPY . /app

# Install required library for OpenCV
RUN apt-get update && apt-get install -y libgl1 && apt-get install -y unzip

# Install dependencies from requirements.txt (make sure this file exists)
RUN pip install --no-cache-dir -r requirements.txt

# Install Python dependencies
RUN pip install opencv-python

# Correct the CMD instruction
CMD ["python3", "--version"]