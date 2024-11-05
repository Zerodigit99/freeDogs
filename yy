# Use a lightweight Python image
FROM python:3.8-slim

# Set the working directory
WORKDIR /app

# Copy files to the container
COPY . /app

# Install dependencies
RUN pip install -r requirements.txt

# Run the start script
CMD ["./start.sh"]
