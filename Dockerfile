# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Expose the port that the app runs on
EXPOSE 8080

# Define environment variable for dynamic port binding (Render/Cloud Run uses $PORT)
ENV PORT=8080

# Command to run the application using Gunicorn for production
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]
