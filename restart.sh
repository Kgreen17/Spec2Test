#!/bin/bash
# Restart Spec2Test with fixed API endpoints

cd /Users/kevingreen/PycharmProjects/Spec2Test

echo "Stopping containers..."
docker-compose down

echo "Waiting..."
sleep 3

echo "Rebuilding and starting..."
docker-compose up -d --build

echo "Waiting for services..."
sleep 5

echo ""
echo "✅ Application restarted with fixed API endpoints!"
echo ""
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo ""
echo "Fixed endpoints:"
echo "  - /api/upload (was /upload)"
echo "  - /api/jobs (was /jobs)"
echo ""

open http://localhost:3000

