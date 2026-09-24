# Vercel Hosting Configuration & Deployment Guide
## AAROGYA-SHIELD / VITALSYNC Edge-AI System

This guide explains how to deploy **AAROGYA-SHIELD / VITALSYNC** to **Vercel** with zero configuration issues.

---

### Architecture Overview

```
                          ┌────────────────────────────────────────┐
                          │          VERCEL (Global CDN)           │
                          │                                        │
                          │  /      → Smartwatch Companion (user-ui)│
                          │  /lab   → Simulation Lab (testing-ui)  │
                          └───────────────────┬────────────────────┘
                                              │
                    REST (HTTPS)              │  WebSocket Stream (WSS)
              ┌───────────────────────────────┴───────────────────────────────┐
              ▼                                                               ▼
┌───────────────────────────────┐                               ┌───────────────────────────────┐
│     FastAPI REST APIs         │                               │     Live Telemetry Stream     │
│   (Predict, Profile, Alerts)  │                               │    (/ws/live 1 Hz updates)    │
└───────────────────────────────┘                               └───────────────────────────────┘
              ▲                                                               ▲
              └───────────────────────────────┬───────────────────────────────┘
                                              │
                                ┌─────────────┴─────────────┐
                                │     PERSISTENT BACKEND    │
                                │  Raspberry Pi 4 Edge Node │
                                │  OR Railway / Render / VPS │
                                └───────────────────────────┘
```

> **Important WebSocket Note**: Vercel Serverless Functions do not support persistent WebSockets (`ws://` / `wss://`). While the frontends run with maximum performance on Vercel's global edge network, the FastAPI backend should run on a persistent host (e.g., **Raspberry Pi 4 with Cloudflare Tunnel**, **Railway**, **Render**, or **Fly.io**) to provide continuous 1 Hz telemetry and alert streaming.

---

### Pre-Configured Files in This Repository

| File | Purpose | Location |
|---|---|---|
| `vercel.json` | **Unified Root Config**: Builds both `user-ui` (`/`) and `testing-ui` (`/lab`) into one Vercel deployment. | Root directory |
| `build_all.js` | Node.js script that compiles both frontends into a unified `dist/` directory. | Root directory |
| `package.json` | Root build manifest for Vercel automatic build detection. | Root directory |
| `user-ui/vercel.json` | Standalone Vercel config for deploying **only** the Smartwatch Companion. | `user-ui/` |
| `testing-ui/vercel.json` | Standalone Vercel config for deploying **only** the Simulation Lab. | `testing-ui/` |
| `user-ui/.env.example` | Template for Watch Companion environment variables. | `user-ui/` |
| `testing-ui/.env.example` | Template for Simulation Lab environment variables. | `testing-ui/` |

---

### Option 1: Unified Deployment (Recommended — 1 Vercel Project)

Deploy both the Smartwatch Companion and Simulation Lab under a single Vercel project:
- **`https://your-app.vercel.app/`** $\to$ Realistic Light-Mode Smartwatch Companion
- **`https://your-app.vercel.app/lab`** $\to$ Simulation Lab & Engineering Testbed
- Cross-navigation buttons are automatically active between both interfaces!

#### Steps via Vercel Dashboard:
1. Push this repository to **GitHub** / **GitLab** / **Bitbucket**.
2. Go to [vercel.com/new](https://vercel.com/new) and import your repository.
3. Configure the project:
   - **Framework Preset**: `Other` (or leave default)
   - **Root Directory**: `./` (default repository root)
   - **Build Command**: `node build_all.js` (automatically detected from `vercel.json`)
   - **Output Directory**: `dist` (automatically detected from `vercel.json`)
4. Add **Environment Variables** in the Vercel dashboard:
   - `VITE_API_URL`: `https://your-backend-domain.com`
   - `VITE_WS_URL`: `wss://your-backend-domain.com/ws/live`
5. Click **Deploy**.

---

### Option 2: Standalone Deployments (2 Separate Vercel Projects)

If you prefer two separate domains (e.g., `watch.yourdomain.com` and `lab.yourdomain.com`):

#### Project A: Smartwatch Companion (`user-ui`)
1. In Vercel, click **Add New Project** and select this repository.
2. Edit **Root Directory** $\to$ select `user-ui`.
3. Vercel automatically detects `Vite` preset:
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Add Environment Variables:
   - `VITE_API_URL`: `https://your-backend-domain.com`
   - `VITE_WS_URL`: `wss://your-backend-domain.com/ws/live`
5. Deploy.

#### Project B: Simulation Lab (`testing-ui`)
1. In Vercel, click **Add New Project** and select this repository again.
2. Edit **Root Directory** $\to$ select `testing-ui`.
3. Vercel automatically detects `Vite` preset:
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Add Environment Variables:
   - `VITE_API_URL`: `https://your-backend-domain.com`
   - `VITE_WS_URL`: `wss://your-backend-domain.com/ws/live`
5. Deploy.

---

### Option 3: Deploy via Vercel CLI

Install the Vercel CLI if you haven't already:
```bash
npm install -g vercel
```

#### Deploy Unified Project (Root):
```bash
# Navigate to repository root
cd "d:/Studies/SIH 2026"

# Deploy to preview
vercel

# Deploy to production
vercel --prod
```

#### Deploy Standalone User-UI:
```bash
cd "d:/Studies/SIH 2026/user-ui"
vercel --prod
```

#### Deploy Standalone Testing-UI:
```bash
cd "d:/Studies/SIH 2026/testing-ui"
vercel --prod
```

---

### Backend Hosting Options (For WebSocket Support)

To connect your Vercel frontends to a live backend with persistent WebSockets:

#### A. Raspberry Pi 4 / Local Edge Device + Cloudflare Tunnel (Free & Secure)
Expose your local edge node to the internet with an automatic HTTPS/WSS domain without opening router ports:
```bash
# On your Raspberry Pi or PC:
cloudflared tunnel --url http://localhost:8000
```
Cloudflare will give you a URL like:
`https://random-subdomain.trycloudflare.com`

Set your Vercel Environment Variables:
- `VITE_API_URL`: `https://random-subdomain.trycloudflare.com`
- `VITE_WS_URL`: `wss://random-subdomain.trycloudflare.com/ws/live`

#### B. Railway / Render / Fly.io Cloud Deployment
You can deploy `backend/` using Docker or standard Python command:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**:
  - `MONGO_URI`: Your MongoDB connection string (e.g., MongoDB Atlas or Railway MongoDB plugin)

---

### Verifying Vercel Deployment

Once deployed:
1. Open your Vercel deployment URL.
2. Open Browser Developer Tools $\to$ **Console** / **Network** tab.
3. Verify that the bottom sync pill reads:
   `● Authoritative Edge Stream Connected (1 Hz)`
4. Test profile onboarding and presets; verify immediate bi-directional synchronization.
