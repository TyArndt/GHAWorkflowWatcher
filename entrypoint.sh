#!/bin/bash

# GitHub Workflow Webhook Server - Docker Entrypoint
# Starts both backend and frontend services

echo "Starting GitHub Workflow Webhook Server..."
echo "Backend will be available on port 8081"
echo "Frontend will be available on port 8080"
echo "Database will be stored in /app/data/"

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Services stopped."
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Start backend service in background
echo "Starting backend service..."
python Backend.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend service in background
echo "Starting frontend service..."
python frontend.py &
FRONTEND_PID=$!

# Wait a moment for frontend to start
sleep 2

echo "Both services started successfully!"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Access the services at:"
echo "  - Frontend Dashboard: http://localhost:8080"
echo "  - Backend API: http://localhost:8081"
echo "  - API Documentation: http://localhost:8081/docs/"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID