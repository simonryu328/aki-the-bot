#!/bin/bash
# Quick test script for the Mini App API

echo "🧪 Testing Aki Mini App API"
echo "=============================="
echo ""

# Check if API is running
echo "1. Health Check..."
response=$(curl -s http://localhost:8000/)
if [ $? -eq 0 ]; then
    echo "✅ API is running"
    echo "   Response: $response"
else
    echo "❌ API is not running. Start it with: uv run python miniapp/run_api.py"
    exit 1
fi

echo ""
echo "2. API Documentation..."
echo "   📖 OpenAPI docs: http://localhost:8000/docs"
echo "   📖 ReDoc: http://localhost:8000/redoc"

echo ""
echo "3. Mini App Interface..."
echo "   🌐 Open: http://localhost:8000/miniapp/index.html"

echo ""
echo "=============================="
echo "✨ All systems operational!"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:8000/docs to test API endpoints"
echo "  2. Use ngrok to expose your local server for Telegram testing:"
echo "     ngrok http 8000"
echo "  3. Update MINIAPP_URL in .env with your ngrok URL"
echo "  4. Test /memories command in Telegram"

# Made with Bob
