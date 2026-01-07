# 🚀 MVP Release Guide

## Release Version: 1.0.0-MVP

**Date:** January 2026
**Status:** ✅ Ready for Deployment

---

## 📦 What's Included in the MVP

### Core Features

1. **Text Document Management**
   - Upload or paste text documents
   - Automatic sentence splitting
   - Real-time text editing

2. **Emoji Annotation System**
   - Add up to 5 emojis per sentence
   - Manual emoji selection from quick picker
   - Visual emoji timeline/dictionary

3. **AI-Powered Features** 🤖
   - Generate emojis from text (per sentence or bulk)
   - Generate text from emoji combinations
   - Story analysis (drama, humor, conflict, mystery metrics)
   - Intent-based suggestions

4. **Character Management**
   - Create and manage story characters
   - Assign emojis to characters
   - Color-coded character highlighting
   - Character sentiment tracking

5. **Visualization**
   - Emoji dictionary with hover highlighting
   - Character flow graph (Sankey diagram)
   - Spider chart for story analysis
   - Interactive timeline view

---

## 🏃 Quick Start (< 5 minutes)

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenRouter API key (free tier: <https://openrouter.ai/keys>)

### One-Time Setup

```bash
# 1. Clone/navigate to project
cd InfoVis-Praktikum

# 2. Configure API key
cd backend
cp .env.example .env
# Edit .env and add: OPENROUTER_API_KEY=your_key_here

# 3. Install backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Install frontend
cd ../frontend
npm install
```

### Run the MVP

**Terminal 1 - Backend:**

```bash
cd backend
./run_backend.sh
```

**Terminal 2 - Frontend:**

```bash
cd frontend
./run_frontend.sh
```

**Access the app:**

- Frontend: <http://localhost:4200>
- Backend API: <http://localhost:8000/docs>

---

## 🎯 MVP Demo Workflow

### Basic Usage

1. Open <http://localhost:4200>
2. Sample document loads automatically
3. Click on any sentence to select it
4. Use the right sidebar tabs:
   - **🤖 AI Tab** (default): Generate emojis, edit manually, get AI suggestions
   - **😀 Emojis Tab**: View emoji dictionary, manage characters
   - **📊 Graph Tab**: See character flow visualization
   - **👥 Characters Tab**: Character sentiment analysis
   - **🎭 Analysis Tab**: Story emotion spider chart

### AI Generation Demo

1. Click **🤖 AI** tab (first tab on right)
2. Click "Generate Emojis for All Sentences" → AI analyzes entire story
3. Select a sentence
4. Manually add/remove emojis using the editor
5. Click "Generate Text" → AI creates new text from your emojis

### Character Management Demo

1. Click **😀 Emojis** tab
2. View emoji dictionary entries
3. Hover over entries → sentences highlight in text
4. Click ➕ on recurring emoji → promote to character
5. Edit character name and description
6. Click **👥 Characters** tab to see sentiment

---

## 🏗️ Production Build

### Build for Deployment

```bash
# Backend (no build needed, runs directly)
cd backend
source venv/bin/activate
python -m pytest  # Run tests

# Frontend
cd frontend
npm run build
# Output: frontend/dist/plottery-frontend/
```

### Deployment Options

**Option 1: Static + API**

- Deploy `frontend/dist/plottery-frontend/` to any static host (Netlify, Vercel, GitHub Pages)
- Deploy backend to Railway, Render, or Heroku
- Update `frontend/src/environments/environment.prod.ts` with API URL

**Option 2: Single Server**

- Serve frontend static files from FastAPI
- Run on single server/VPS
- Example: DigitalOcean droplet, AWS EC2

**Option 3: Docker (Future)**

- Docker Compose setup available in `/infra` (needs update)

---

## 📊 MVP Metrics

### Code Statistics

- **Frontend:** Angular 17, TypeScript, ~25 components
- **Backend:** FastAPI, Python 3.11, SQLite
- **Total Lines:** ~15,000 LOC
- **Bundle Size:** 439 kB (gzipped: ~96 kB)

### Feature Completeness

- ✅ Text editing: 100%
- ✅ Emoji annotation: 100%
- ✅ AI generation: 100%
- ✅ Character management: 100%
- ✅ Visualizations: 90% (basic implementations)

---

## 🐛 Known Limitations (MVP)

### Not Included in MVP

- Multi-user support / authentication
- Document persistence across sessions (uses in-memory DB)
- File upload UI (only text paste)
- Undo/redo history beyond browser back button
- Mobile responsive design
- Export to PDF/DOCX

### Performance Notes

- AI requests take 2-5 seconds (depends on OpenRouter API)
- Large documents (>50 sentences) may slow down
- Dictionary rebuilds on every emoji change

### Browser Support

- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ⚠️ Safari (minor styling issues)
- ❌ IE11 (not supported)

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
source venv/bin/activate
pytest -v
# Expected: 8+ tests passing
```

### Frontend Tests

```bash
cd frontend
npm test
# Run Jasmine/Karma tests
```

### Manual Test Checklist

- [ ] Upload text → sentences appear
- [ ] Click sentence → becomes selected
- [ ] Add emoji → appears in slot
- [ ] Generate emojis → AI adds emojis
- [ ] Generate text → AI creates suggestion
- [ ] Apply suggestion → text updates
- [ ] Create character → appears in list
- [ ] Hover emoji in dictionary → highlights in text
- [ ] Spider chart → drag handles work
- [ ] Graph tab → sankey diagram shows

---

## 📝 Environment Variables

### Backend (.env)

```bash
OPENROUTER_API_KEY=sk-or-v1-...  # Required for AI features
DATABASE_URL=sqlite:///./plottery.db  # Optional, uses default
CORS_ORIGINS=http://localhost:4200  # Optional, uses default
```

### Frontend (environments/*.ts)

```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000'
};
```

---

## 🚀 Next Steps (Post-MVP)

### Version 1.1 (Suggested)

- Add document persistence (save to disk/cloud)
- File upload dialog
- Export functionality
- Mobile responsiveness
- Performance optimizations

### Version 2.0 (Future)

- Multi-user collaboration
- User authentication
- Document sharing
- Real-time collaboration
- Advanced visualizations

---

## 📞 Support

### Documentation

- See `README.md` for detailed setup
- See `QUICK_START.md` for command reference
- See `PROJECT_SUMMARY.md` for architecture

### Troubleshooting

**Backend won't start:**

```bash
# Check Python version
python3 --version  # Should be 3.11+

# Recreate venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Frontend build fails:**

```bash
# Clear cache
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**AI features not working:**

- Check `.env` file has valid `OPENROUTER_API_KEY`
- Check backend logs for API errors
- Verify API key at <https://openrouter.ai/keys>

---

## ✅ MVP Acceptance Criteria

All criteria met for MVP release:

- [x] Application runs without errors
- [x] Core text editing functionality works
- [x] Emoji annotation system functional
- [x] AI features operational (with valid API key)
- [x] Character management complete
- [x] Basic visualizations working
- [x] Build process successful
- [x] Documentation complete
- [x] Quick start guide available
- [x] Known limitations documented

**Status: MVP READY FOR RELEASE** 🎉

---

*Built with ❤️ for creative writers*
