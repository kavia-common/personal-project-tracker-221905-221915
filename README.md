# personal-project-tracker-221905-221915

Backend (FastAPI) quick start

- Requirements: Python 3.10+
- Navigate to backend_api
  - Install deps: pip install -r requirements.txt
  - Run server: uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload
- Open API docs at: http://localhost:3001/docs

Notes
- SQLite DB file is created at backend_api/data/app.db on first run.
- CORS allows http://localhost:3000 by default for the React frontend.
- To refresh openapi.json in backend_api/interfaces/, run:
  - python -m src.api.generate_openapi

API summary (base /api)
- Projects
  - GET /api/projects?page=1&page_size=20
  - POST /api/projects
  - GET /api/projects/{id}
  - PUT /api/projects/{id}
  - DELETE /api/projects/{id}
- Tasks
  - GET /api/projects/{project_id}/tasks?page=1&page_size=20
  - POST /api/projects/{project_id}/tasks
  - GET /api/tasks/{id}
  - PUT /api/tasks/{id}
  - DELETE /api/tasks/{id}
  - POST /api/tasks/{id}/complete

Response format
- Returns JSON with consistent schemas and pagination meta for list endpoints.
- Errors return 4xx with {"detail": "..."}.

Environment variables
- None required for the backend in local development.