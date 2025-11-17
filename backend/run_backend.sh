#!/bin/bash

# Quick start script for Plottery backend

echo "🚀 Starting Plottery Backend..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp ../infra/.env.example .env
    echo "⚠️  Please edit .env and add your TOGETHER_API_KEY"
fi

# Run the server
echo "🎉 Starting FastAPI server..."
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --port 8000
