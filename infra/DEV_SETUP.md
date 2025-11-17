# Development Server Setup

## Running the Backend (FastAPI)

### Quick Start
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Alternative: Using python-dotenv
If you have a `.env` file in the backend directory:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Environment Variables
Copy `infra/.env.example` to `backend/.env` and set:
- `TOGETHER_API_KEY` - Your together.ai API key

## Running the Frontend (Angular)

### Quick Start
```bash
cd frontend
npm install
ng serve
```

The app will be available at: http://localhost:4200

### Build for Production
```bash
cd frontend
ng build --configuration production
```

Output will be in `frontend/dist/`

## Running Tests

### Backend Tests
```bash
cd backend
source venv/bin/activate
pytest
pytest -v  # Verbose output
pytest --cov=app  # With coverage
```

### Frontend Tests
```bash
cd frontend
ng test
ng test --code-coverage  # With coverage
```

## Database

The SQLite database (`plottery.db`) is created automatically on first run in the `backend/` directory.

To reset the database, simply delete `plottery.db` and restart the backend.

## Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
uvicorn app.main:app --reload --port 8001
```

**Module not found errors:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**Database errors:**
```bash
# Delete and recreate database
rm plottery.db
# Restart backend - it will auto-create tables
```

### Frontend Issues

**Port 4200 already in use:**
```bash
ng serve --port 4201
```

**Module not found:**
```bash
rm -rf node_modules package-lock.json
npm install
```

**CORS errors:**
- Make sure backend is running on port 8000
- Check that CORS is properly configured in `backend/app/main.py`

## Development Tips

### Hot Reload
Both servers support hot reload:
- Backend: `--reload` flag enables auto-restart on code changes
- Frontend: `ng serve` watches for file changes automatically

### API Testing
Use the interactive docs at http://localhost:8000/docs to test API endpoints

### VS Code Extensions (Recommended)
- Python
- Pylance
- Angular Language Service
- ESLint
- Prettier

## Production Deployment (Future)

TODO: Add Docker setup and production deployment instructions
