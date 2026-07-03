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
   uvicorn main:app --reload
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
   npm run dev
   ```
   The frontend will run on http://localhost:5173

## Troubleshooting
- If the Cost Estimation model or Document Generation fails, ensure your `GEMINI_API_KEY` is valid in `backend/.env`.
- Ensure MongoDB is running locally to store the inspection sessions and HITL reviews.
