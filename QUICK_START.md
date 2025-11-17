# 🚀 Quick Start Commands

## Option 1: Using Run Scripts (Easiest)

### Terminal 1 - Backend
```bash
cd backend
./run_backend.sh
```

### Terminal 2 - Frontend
```bash
cd frontend
./run_frontend.sh
```

## Option 2: Manual Setup

### Backend Setup (Terminal 1)
```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp ../infra/.env.example .env
# Edit .env and add your TOGETHER_API_KEY (optional for MVP - dummy data works)

# Run server
uvicorn app.main:app --reload --port 8000
```

**Backend URLs:**
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Frontend Setup (Terminal 2)
```bash
cd frontend

# Install dependencies
npm install

# Run dev server
ng serve
```

**Frontend URL:**
- App: http://localhost:4200

## 🧪 Running Tests

### Backend Tests
```bash
cd backend
source venv/bin/activate
pytest
```

### Frontend Tests
```bash
cd frontend
ng test
```

## ✅ Verify It Works

1. Open http://localhost:4200 in your browser
2. You should see "Plottery" in the top bar
3. A sample document with 3 sentences should appear
4. Click on a sentence - it should highlight in blue
5. Emoji panel at bottom should show "Select a sentence..."
6. After selecting, you can add emojis (up to 5)
7. Sidebar on right shows AI suggestion buttons

## 🔑 Environment Variables

For AI features to work with real data (not dummy responses):

1. Get API key from https://api.together.xyz
2. Edit `backend/.env`:
   ```
   TOGETHER_API_KEY=your_actual_api_key_here
   ```
3. Restart backend server

Without the key, AI endpoints return dummy data (which still works for testing the flow).

## 🐛 Troubleshooting

**Backend port in use:**
```bash
uvicorn app.main:app --reload --port 8001
```

**Frontend port in use:**
```bash
ng serve --port 4201
```

**Python version issues:**
Make sure you have Python 3.11 or higher:
```bash
python3 --version
```

**Node version issues:**
Make sure you have Node 18 or higher:
```bash
node --version
```

## 📚 More Documentation

- **README.md** - Full project overview
- **PROJECT_SUMMARY.md** - Detailed architecture and team structure
- **infra/DEV_SETUP.md** - Troubleshooting and advanced setup

---

**Ready to build something amazing! 🎨✨**
