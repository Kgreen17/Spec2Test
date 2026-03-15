#!/bin/bash
set -e

cd /Users/kevingreen/PycharmProjects/Spec2Test

echo "🔄 Installing backend dependencies..."
pip install -q -r requirements.txt

echo "🔄 Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps --silent

echo "✅ Dependencies installed!"
echo ""
echo "🚀 Ready to start servers:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd /Users/kevingreen/PycharmProjects/Spec2Test"
echo "  python3 -m uvicorn backend.app:app --reload"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd /Users/kevingreen/PycharmProjects/Spec2Test/frontend"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:3000"

