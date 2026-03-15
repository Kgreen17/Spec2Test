#!/bin/bash
# Quick Setup and Run Script for Spec2Test with Confluence/Jira Link Support

set -e

PROJECT_DIR="/Users/kevingreen/PycharmProjects/Spec2Test"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Spec2Test - Confluence/Jira Link Support               ║"
echo "║                    QUICK SETUP SCRIPT                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Kill any existing processes
echo "🔄 Cleaning up old processes..."
killall python3 2>/dev/null || true
killall node 2>/dev/null || true
killall npm 2>/dev/null || true
sleep 2

# Check Python
echo "✅ Checking Python..."
python3 --version

# Check Node
echo "✅ Checking Node..."
node --version
npm --version

# Install backend dependencies
echo ""
echo "📦 Installing backend dependencies..."
pip install -q -r requirements.txt 2>/dev/null || pip install -r requirements.txt

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps --silent

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ SETUP COMPLETE                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 To start the application, open TWO terminals:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TERMINAL 1 - Backend Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "cd $PROJECT_DIR"
echo "python3 -m uvicorn backend.app:app --reload --port 8000"
echo ""
echo "Wait for: 'Application startup complete'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TERMINAL 2 - Frontend Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "cd $PROJECT_DIR/frontend"
echo "npm run dev"
echo ""
echo "Wait for: 'compiled successfully' or 'ready'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "BROWSER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Open: http://localhost:3000"
echo "2. Hard Refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)"
echo "3. Look for the TWO BUTTONS at top:"
echo "   [📤 Upload Document]  [🔗 Paste Link]"
echo "4. Click on [🔗 Paste Link] to use the new feature!"
echo "5. Paste a Confluence or Jira URL"
echo "6. Click 'Submit & Start Pipeline'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "EXAMPLE URLS TO TEST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Confluence Page:"
echo "  https://your-domain.atlassian.net/wiki/spaces/KEY/pages/12345"
echo ""
echo "Jira Ticket:"
echo "  https://your-domain.atlassian.net/browse/PROJECT-123"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DOCUMENTATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Quick Start:          STARTUP_GUIDE.md"
echo "Button Location:      LINK_BUTTON_LOCATION.md"
echo "Button Exists Proof:  PASTE_LINK_BUTTON_EXISTS.md"
echo "Visual Guide:         BUTTON_VISUAL_GUIDE.md"
echo "Full Documentation:   START_HERE.md"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "✨ All set! Start the servers in two terminals and open the browser!"
echo ""

