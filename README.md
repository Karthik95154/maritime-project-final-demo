# Maritime Application 2

## Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB running locally on port 27017

## Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   Copy `.env.example` to `.env` and fill in your keys (especially the Gemini API key for document generation):
   ```bash
   cp .env.example .env
   ```
5. Run the backend server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   The backend API will run on http://localhost:8000

## Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev -- --host 0.0.0.0 --port 5173
   ```
   The frontend will run on http://localhost:5173

## VS Code Port Forwarding
- Forward port `8000` for the FastAPI backend.
- Forward port `5173` for the main frontend.
- Forward port `5174` for the separate HITL review frontend.
- Start everything from the repo root with:
  ```bash
  npm run dev:local
  ```
- Start all three services with the more reliable preview setup:
  ```bash
  npm run run:all
  ```
- Or run services separately:
  ```bash
  npm run dev:backend
  npm run dev:frontend
  npm run dev:hitl
  ```
- Open the main app on `http://localhost:5173`.
- Open the HITL review console on `http://localhost:5174`.
- When using a public dev tunnel, start the frontend with the tunnel hostname so Vite HMR connects back correctly:
  ```bash
  $env:TUNNEL_HOST="73ng7877-5173.inc1.devtunnels.ms"
  npm run dev:frontend
  ```
  Or use:
  ```bash
  powershell -ExecutionPolicy Bypass -File .\start-frontend-tunnel.ps1 -TunnelHost "73ng7877-5173.inc1.devtunnels.ms"
  ```
- For a separate HITL port, start the preview server in HITL mode:
  ```bash
  powershell -ExecutionPolicy Bypass -File .\start-frontend-preview.ps1 -Port 5174 -Mode hitl
  ```
- If the public tunnel still gives `504` or websocket errors, use preview mode instead of the Vite dev server:
  ```bash
  npm run dev:backend
  powershell -ExecutionPolicy Bypass -File .\start-frontend-preview.ps1 -Port 5173
  ```

## Troubleshooting
- If the Cost Estimation model or Document Generation fails, ensure your `GEMINI_API_KEY` is valid in `backend/.env`.
- Ensure MongoDB is running locally to store the inspection sessions and HITL reviews.
