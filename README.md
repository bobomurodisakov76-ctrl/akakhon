# ACADEMY UZ — Premium frontend + Python backend

This project contains the original HTML/CSS/JavaScript education dashboard plus a FastAPI backend and a working media library.

## Requirements (Windows)
- Python 3.10 or newer
- A modern browser
- Node.js is **not required** for this vanilla HTML/CSS/JS frontend

## First-time setup
1. Extract the ZIP to a normal folder, for example `Desktop\\academy-uz-site`.
2. Open the folder in VS Code.
3. Double-click `START-BACKEND.bat`. The first run creates a Python virtual environment, installs dependencies, copies `backend/.env.example` to `backend/.env`, creates the SQLite database, and starts the API on `http://127.0.0.1:8001`.
4. Open `http://127.0.0.1:8001` in your browser (the backend serves the website too; no second server needed).
5. Sign in with the backend administrator account:
   - Login: `academyadmin`
   - Password: `hEQ1qIa5ItM52F`
6. Open **Media** in the left navigation. Upload images, videos, or PDF documents. The uploaded files and their details are stored on the computer in `backend/uploads` and `backend/academy.db`.

You may also run `START-ALL.bat` to start both servers and open the site.

## Configure the administrator password
Before using this beyond a local demonstration, edit `backend/.env` and change `ADMIN_PASSWORD` and `SECRET_KEY`. Restart the backend after changing them. Keep `.env` private and do not upload it to GitHub.

## API
- `GET /api/health` — health check
- `POST /api/auth/login` — administrator login (JSON: `username`, `password`)
- `GET /api/media` — list uploaded media (Bearer token required)
- `POST /api/media` — upload `title`, optional `description`, and `file` (Bearer token required)
- `DELETE /api/media/{id}` — delete a media item (Bearer token required)
- `GET /docs` — interactive API documentation

## Hisoblar (login/parol)
- Admin va menejer **Accounts** bo'limida menejer, ustoz va o'quvchi uchun login-parol ochadi (admin barcha rollarni, menejer manager/teacher/student).
- Har bir foydalanuvchi **Profil/Settings** bo'limida o'z ismi, logini va parolini o'zgartiradi.
- Demo hisoblar olib tashlangan; birinchi marta ishga tushganda faqat admin yaratiladi (`backend/.env`). Admin parolini `.env` da o'zgartiring va `academy.db` ni o'chirib qayta ishga tushiring.

## Troubleshooting
- If `py` is not recognized, install Python from https://www.python.org/downloads/ and enable **Add Python to PATH**.
- If the browser says the backend is unavailable, check that the backend terminal is still running on port 8001.
- If port 8000 or 8001 is already in use, close the other server or change the port in the relevant `.bat` file and `API_BASE` in `app.js`.
- Media files are stored locally. For a public production deployment, add cloud object storage, HTTPS, backups, rate limiting, virus scanning, a full user/role database, and stricter deployment security.
