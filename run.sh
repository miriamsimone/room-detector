#!/bin/bash
# Run both backend and frontend servers

echo "Starting Room Detection Service..."
echo ""

# Check for model
if [ ! -f "backend/maskrcnn_best.pth" ]; then
    echo "⚠️  Warning: maskrcnn_best.pth not found in backend/"
    echo "   Copy the model file before using detection"
    echo ""
fi

# Start backend
echo "Starting backend on http://localhost:8000"
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:3000"
cd frontend
python -m http.server 3000 &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Services running:"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

# Wait
wait
