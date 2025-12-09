#!/bin/bash
set -e

echo "=================================="
echo "Room Detection Service - Deployment"
echo "=================================="
echo ""

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: docker-compose.yml not found"
    echo "Run this script from the project root directory"
    exit 1
fi

# Check if model file exists
if [ ! -f "backend/maskrcnn_best.pth" ]; then
    echo "Warning: Model file not found at backend/maskrcnn_best.pth"
    echo "Please upload the model file before starting services"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Pulling latest changes..."
git pull

echo ""
echo "Building and starting services..."
docker-compose down
docker-compose up -d --build

echo ""
echo "Waiting for services to start..."
sleep 5

echo ""
echo "Checking service health..."
HEALTH=$(curl -s http://localhost/health || echo "failed")

if [[ $HEALTH == *"healthy"* ]]; then
    echo "✓ Services are healthy!"
    echo ""
    echo "Deployment complete!"
    echo "Access the app at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'localhost')"
else
    echo "✗ Health check failed"
    echo "Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop services: docker-compose down"
