#!/bin/bash
set -e

cd /Users/kevingreen/PycharmProjects/Spec2Test

echo "==========================================="
echo "Starting Spec2Test Application"
echo "==========================================="
echo ""

# Stop existing containers
echo "Stopping existing containers..."
docker-compose -f docker-compose.yml down 2>/dev/null || true

# Wait
sleep 2

# Start fresh
echo "Starting fresh build and deployment..."
docker-compose -f docker-compose.yml up -d --build

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 5

# Check status
echo ""
echo "Checking service status..."
docker-compose -f docker-compose.yml ps

echo ""
echo "==========================================="
echo "✅ SPEC2TEST IS RUNNING"
echo "==========================================="
echo ""
echo "🌐 Frontend:  http://localhost:3000"
echo "🔌 Backend:   http://localhost:8000"
echo ""
echo "📝 To view logs:"
echo "   docker-compose -f docker-compose.yml logs -f"
echo ""
echo "🛑 To stop:"
echo "   docker-compose -f docker-compose.yml down"
echo ""
echo "⚠️  If you still see placeholder in browser:"
echo "   1. Do a hard refresh: Cmd + Shift + R (macOS)"
echo "   2. Or open in incognito/private window"
echo ""
echo "==========================================="

# Open in browser
open http://localhost:3000

echo "Browser should open in a moment..."

