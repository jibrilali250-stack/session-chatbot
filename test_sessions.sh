#!/bin/bash
# Test script for session endpoints

echo "=== Testing Session Endpoints ==="
echo ""

echo "1. Creating a new session..."
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8000/sessions)
echo "Response: $SESSION_RESPONSE"
SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
echo "Session ID: $SESSION_ID"
echo ""

echo "2. Getting empty session..."
curl -s http://localhost:8000/sessions/$SESSION_ID | jq .
echo ""

echo "3. Sending first message..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"message\": \"Hello, my name is Alice\"}" | jq .
echo ""

echo "4. Sending follow-up message (testing memory)..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"message\": \"What is my name?\"}" | jq .
echo ""

echo "5. Getting session history..."
curl -s http://localhost:8000/sessions/$SESSION_ID | jq .
echo ""

echo "6. Deleting session..."
curl -s -X DELETE http://localhost:8000/sessions/$SESSION_ID | jq .
echo ""

echo "7. Trying to get deleted session (should 404)..."
curl -s http://localhost:8000/sessions/$SESSION_ID | jq .
echo ""

echo "=== Test Complete ==="
