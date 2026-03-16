#!/bin/bash

echo "🧹 Killing old processes..."
killall -9 python3 node 2>/dev/null || true
sleep 2

echo "📦 Installing frontend dependencies..."
cd /Users/kevingreen/PycharmProjects/Spec2Test/frontend
npm install --legacy-peer-deps

echo "🚀 Starting frontend on port 3000..."
npm run dev &

echo "⏳ Waiting for frontend to start..."
sleep 8

echo "🚀 Starting backend on port 8000..."
cd /Users/kevingreen/PycharmProjects/Spec2Test
python3 -m uvicorn backend.app:app --reload --port 8000 &

echo ""
echo "✅ Both servers are running!"
echo ""
echo "📱 Frontend: http://localhost:3000"
echo "⚙️  Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers"

wait

