# Use the official Python 3.9 image as the base
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /

# Copy the local code to the container's working directory
COPY . /app/data

RUN pip install --upgrade pip

# Install required library for OpenCV
RUN apt-get update && apt-get install -y libgl1 libglvnd0 unzip libglib2.0-0 coreutils

# Install dependencies from requirements.txt (make sure this file exists)
RUN pip install --no-cache-dir -r requirements.txt

# Correct the CMD instruction
CMD ["python3", "--version"]