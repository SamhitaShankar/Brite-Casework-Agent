import express from 'express';
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn, ChildProcess } from 'child_process';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { createServer as createViteServer } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;
const PYTHON_BACKEND_PORT = 8001;
const PYTHON_BACKEND_URL = `http://127.0.0.1:${PYTHON_BACKEND_PORT}`;

let pythonProcess: ChildProcess | null = null;

function startPythonBackend(): void {
  console.log(`[Python Backend] Launching Python 3.10+ casework backend on port ${PYTHON_BACKEND_PORT}...`);
  
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  pythonProcess = spawn(
    pythonCmd,
    ['-m', 'backend.server_runner'],
    {
      cwd: process.cwd(),
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['ignore', 'inherit', 'inherit'],
    }
  );

  pythonProcess.on('error', (err) => {
    console.error('[FastAPI Backend Error]', err);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.warn(`[FastAPI Backend Exited] code=${code} signal=${signal}`);
  });

  const cleanup = () => {
    if (pythonProcess) {
      console.log('[FastAPI Backend] Terminating child process on exit...');
      pythonProcess.kill('SIGTERM');
      pythonProcess = null;
    }
  };

  process.on('exit', cleanup);
  process.on('SIGINT', () => {
    cleanup();
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    cleanup();
    process.exit(0);
  });
}

async function startServer() {
  // 1. Boot Python FastAPI Authoritative Backend
  startPythonBackend();

  const app = express();

  // 2. Health & Status check showing FastAPI authoritative architecture
  app.get('/api/runtime-info', (_req, res) => {
    res.json({
      architecture: 'FastAPI (Python 3.10+) + SQLAlchemy + PostgreSQL / SQLite',
      frontend: 'React 19 + Vite + TailwindCSS',
      policy_engine: 'Deterministic Safeguarding Gate (ACA-2026/1 + ACA-2026/2 §3.9)',
      llm_service: 'Gemini 2.5 Flash with zero-synthetic fallback',
      status: 'authoritative_active',
    });
  });

  // 3. Proxy all API routes strictly to the authoritative FastAPI backend
  const apiProxy = createProxyMiddleware({
    target: PYTHON_BACKEND_URL,
    changeOrigin: true,
    ws: true,
    on: {
      error: (err, _req, res) => {
        console.error('[API Proxy Error]', err.message);
        if (res && 'writeHead' in res && !res.headersSent) {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            error: 'FastAPI Backend Starting or Unavailable',
            detail: err.message,
          }));
        }
      },
    },
  });

  app.use('/api', apiProxy);

  // 4. Vite Frontend Middleware
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Brite Casework System] Server running on http://localhost:${PORT}`);
    console.log(`[Brite Casework System] Authoritative API proxied to FastAPI on port ${PYTHON_BACKEND_PORT}`);
  });
}

startServer();
