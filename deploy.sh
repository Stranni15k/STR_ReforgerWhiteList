#!/bin/bash

echo "Starting Whitelist Bot deployment..."

mkdir -p data

docker-compose down
docker-compose up --build -d
docker-compose ps

echo "Deployment complete!"
echo "API is available at: http://localhost:5000"
echo "Check Discord for bot status"