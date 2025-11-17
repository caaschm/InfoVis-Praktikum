# Plottery - AI-Powered Creative Writing App

A collaborative creative writing tool that helps authors visualize story emotion and plot through emojis, with AI-powered text and emoji generation.

---

## 🚀 Quick Start

### Terminal 1 - Backend:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm install
ng serve
```

### Then open:
- **Frontend UI:** http://localhost:4200
- **Backend API Docs:** http://localhost:8000/docs

---

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [API Documentation](#api-documentation)
- [Development Guide](#development-guide)
- [Team Structure](#team-structure)

---

## Overview

Plottery is a creative writing application that combines text editing with emoji-based plot visualization. Authors can:

- Upload or paste text documents
- Automatically split text into sentences
- Tag each sentence with up to 5 emojis representing mood/plot
- Use AI to generate emoji suggestions from text
- Use AI to generate text suggestions from emoji combinations
- Visualize the emotional arc of their story through the emoji timeline

**Current Status:** MVP with single-user functionality, no authentication required.

---

## Tech Stack

### Frontend
- **Framework:** Angular 17 (Standalone Components)
- **Language:** TypeScript
- **Styling:** SCSS
- **State Management:** RxJS BehaviorSubjects
- **HTTP Client:** Angular HttpClient

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Server:** Uvicorn
- **Database:** SQLite + SQLAlchemy
- **AI Integration:** together.ai API
- **Validation:** Pydantic v2

### Development
- **Testing:** pytest (backend), Jasmine/Karma (frontend)
- **Environment:** .env files
- **CORS:** Enabled for localhost:4200

---

## Project Structure

```
InfoVis-Praktikum/
├── backend/                 # Python FastAPI application
│   ├── app/
│   │   ├── main.py         # FastAPI app entry point
│   │   ├── database.py     # SQLAlchemy setup
│   │   ├── models.py       # Database models
│   │   ├── schemas.py      # Pydantic schemas
│   │   ├── routers/        # API endpoints
│   │   │   ├── documents.py
│   │   │   ├── sentences.py
│   │   │   └── ai.py
│   │   └── services/
│   │       └── ai_client.py # together.ai integration
│   ├── tests/              # Backend tests
│   ├── requirements.txt    # Python dependencies
│   └── run_backend.sh      # Start script
│
├── frontend/               # Angular application
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/       # Services and models
│   │   │   │   ├── services/
│   │   │   │   │   ├── api.service.ts
│   │   │   │   │   ├── document.service.ts
│   │   │   │   │   └── ai.service.ts
│   │   │   │   └── models/ # TypeScript interfaces
│   │   │   ├── layout/     # Top-level layout components
│   │   │   │   └── top-bar/
│   │   │   └── features/   # Feature modules
│   │   │       └── document-editor/
│   │   │           ├── text-viewer/
│   │   │           ├── emoji-panel/
│   │   │           └── sidebar/
│   │   └── environments/   # Environment configs
│   └── run_frontend.sh     # Start script
│
├── infra/                  # Infrastructure & config
│   ├── .env.example        # Environment template
│   └── DEV_SETUP.md        # Troubleshooting guide
│
├── README.md               # This file
├── PROJECT_SUMMARY.md      # Architecture details
├── QUICK_START.md          # Quick commands
├── .gitignore
└── LICENSE
```

---

## Setup Instructions

### Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** 18 or higher
- **npm:** 9 or higher
- **Angular CLI:** `npm install -g @angular/cli`

### Backend Setup

1. **Navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp ../infra/.env.example .env
   # Edit .env and add your TOGETHER_API_KEY (optional for testing)
   ```

5. **Run the server:**
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

   Or use the script:
   ```bash
   chmod +x run_backend.sh
   ./run_backend.sh
   ```

6. **Verify:** Open http://localhost:8000/docs

### Frontend Setup

1. **Navigate to frontend:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   ng serve
   ```

   Or use the script:
   ```bash
   chmod +x run_frontend.sh
   ./run_frontend.sh
   ```

4. **Verify:** Open http://localhost:4200

### Database
The SQLite database (`plottery.db`) is automatically created in the `backend/` directory when you first run the server.

---

## API Documentation

### Base URL
`http://localhost:8000/api`

### Endpoints

#### Documents
- `POST /api/documents` - Create document from text
- `GET /api/documents` - List all documents
- `GET /api/documents/{id}` - Get document with sentences and emojis
- `DELETE /api/documents/{id}` - Delete document

#### Sentences
- `GET /api/sentences/{id}` - Get single sentence
- `PATCH /api/sentences/{id}` - Update sentence text and emojis

#### AI
- `POST /api/ai/emojis-from-text` - Generate emoji suggestions from text
- `POST /api/ai/text-from-emojis` - Generate text from emoji combination

#### Health
- `GET /health` - Health check endpoint

**Interactive Docs:** Visit http://localhost:8000/docs for full API documentation with try-it-out functionality.

---

## Development Guide

### Data Flow

```
User Input → Component → DocumentService (State) → ApiService → Backend API
                              ↓
                        BehaviorSubject
                              ↓
                    All Components React
```

### Key Services

**DocumentService** (`frontend/src/app/core/services/document.service.ts`)
- Central state management
- Holds current document, sentences, selected sentence
- Exposes observables for reactive updates
- Debounces save operations (500ms)

**ApiService** (`frontend/src/app/core/services/api.service.ts`)
- Low-level HTTP wrapper
- Handles all backend communication
- Error handling and logging

**AIService** (`frontend/src/app/core/services/ai.service.ts`)
- Calls AI endpoints
- Manages AI suggestion state

### Making Changes

**Adding a new API endpoint:**
1. Add route in `backend/app/routers/`
2. Add Pydantic schema in `backend/app/schemas.py`
3. Update frontend model in `frontend/src/app/core/models/`
4. Add method in `frontend/src/app/core/services/api.service.ts`
5. Add test in `backend/tests/`

**Adding a UI component:**
1. Generate: `ng generate component features/your-feature/your-component`
2. Add to parent component's imports
3. Use DocumentService for state access
4. Style in component's `.scss` file

---

## Team Structure (5 Developers)

### 👤 Developer 1: Layout & UI
**Focus Areas:**
- `frontend/src/app/layout/`
- Component styling (`.scss` files)
- Responsive design
- Animations and transitions
- Global styles

**Tasks:**
- Enhance visual design
- Add loading states
- Improve mobile responsiveness
- Create theme system

---

### 👤 Developer 2: AI Integration
**Focus Areas:**
- `backend/app/services/ai_client.py`
- `backend/app/routers/ai.py`
- together.ai API integration
- Prompt engineering

**Tasks:**
- Implement real together.ai calls
- Refine prompts for emoji generation
- Refine prompts for text generation
- Add context awareness
- Handle API errors gracefully

---

### 👤 Developer 3: Database & Models
**Focus Areas:**
- `backend/app/models.py`
- `backend/app/database.py`
- `backend/app/schemas.py`
- Database migrations

**Tasks:**
- Add document search/filter
- Implement pagination
- Add database indexes
- Create backup/export functionality
- Optimize queries

---

### 👤 Developer 4: Sidebar Features
**Focus Areas:**
- `frontend/src/app/features/document-editor/sidebar/`
- New suggestion types
- Settings panel
- History tracking

**Tasks:**
- Add "Settings" tab
- Add "History" tab (version control)
- Create more AI suggestion types
- Implement suggestion voting/rating
- Add export options

---

### 👤 Developer 5: Testing & Tooling
**Focus Areas:**
- `backend/tests/`
- `frontend/**/*.spec.ts`
- CI/CD setup
- Development tools

**Tasks:**
- Add component tests
- Add E2E tests
- Set up GitHub Actions
- Create Docker setup
- Add code quality tools (linting, formatting)
- Performance monitoring

---

## Testing

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

---

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
TOGETHER_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///./plottery.db
CORS_ORIGINS=http://localhost:4200
```

**Note:** The app works without `TOGETHER_API_KEY` using dummy data for testing.

---

## Troubleshooting

See [`infra/DEV_SETUP.md`](infra/DEV_SETUP.md) for common issues and solutions.

**Common Issues:**

1. **Backend port already in use:**
   ```bash
   lsof -ti:8000 | xargs kill -9
   ```

2. **Frontend port already in use:**
   ```bash
   ng serve --port 4201
   ```

3. **Database locked:**
   - Close all backend processes
   - Delete `plottery.db` and restart

4. **CORS errors:**
   - Verify backend is running on port 8000
   - Check CORS configuration in `backend/app/main.py`

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Add tests
4. Run tests: `pytest` (backend) and `ng test` (frontend)
5. Commit: `git commit -m "Add feature"`
6. Push: `git push origin feature/your-feature`
7. Create Pull Request

---

## License

MIT License - See LICENSE file for details

---

## Contact & Support

For questions or issues, please create an issue in the repository.

**Project Status:** MVP / Active Development
**Last Updated:** November 2025