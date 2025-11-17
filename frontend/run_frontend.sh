#!/bin/bash

# Quick start script for Plottery frontend

echo "🚀 Starting Plottery Frontend..."
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Run the dev server
echo "🎉 Starting Angular dev server..."
echo "App will be available at: http://localhost:4200"
echo ""
ng serve
