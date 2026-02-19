# NIFTY Options Paper Trading Terminal — Deployment Guide

---

## 1. Run Locally on Windows (Recommended for full features)

```cmd
cd C:\nifty_terminal
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

App opens at → http://localhost:8501

### Local Login Flow (No copy-paste needed)
1. In Fyers API portal → set Redirect URL to: `http://127.0.0.1:8085/callback`
2. In Profile tab → fill Client ID + Secret Key → Save
3. Click **🚀 Auto Login** — browser opens Fyers login automatically
4. Log in → browser shows "Auth code captured!" → token saved automatically
5. Click **⚡ Initialise Strategy** → go to Strategy Control → Start

---

## 2. Deploy on Render (Free Cloud Hosting)

### Step A — Prepare GitHub repo
1. Create a GitHub account at github.com
2. Create a new repository (e.g. `nifty-terminal`)
3. Upload all files from `nifty_terminal/` folder to the repo root
   - app.py, requirements.txt, render.yaml must be at root level

### Step B — Deploy on Render
1. Go to https://render.com → Sign up (free)
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Fill in:
   - **Name:** nifty-terminal (or any name)
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
   - **Instance Type:** Free
5. Click **Create Web Service**
6. Wait ~3 minutes → your app is live at `https://your-app-name.onrender.com`

### Step C — Set up Fyers for Render (Manual Login method)
Since the server is in the cloud, Auto Login won't work.
Use **Option B — Manual Login** in the Profile tab:

1. In Fyers API portal → set Redirect URL to: `https://trade.fyers.in`
   (or any URL you can see in the browser after redirect)
2. In Profile tab → fill credentials → Save
3. Click **Generate Login URL** → click the link → log in on Fyers
4. After login, browser redirects to trade.fyers.in — look at the URL bar:
   ```
   https://trade.fyers.in/?auth_code=eyJhbGc...&state=sample_state
   ```
5. Copy the value after `auth_code=` (everything until `&state`)
6. Paste into the "Paste auth_code here" box → click Exchange for Token

### Important: Render Free Tier Limitations
| Limitation | Impact |
|---|---|
| Spins down after 15 min inactivity | App restarts, session cleared (token lost) |
| SQLite is ephemeral | Trade history lost on restart |
| No persistent disk | Upgrade to Starter ($7/mo) for disk |

**Workaround for token expiry on free tier:**
- Fyers tokens last 24 hours
- Re-login each morning after 9:00 AM IST
- Or upgrade to Render Starter plan for persistent disk + always-on

---

## 3. Token Refresh — Daily Routine

Fyers access tokens expire daily. Each morning:
1. Go to Profile tab
2. Click **Auto Login** (local) or **Generate Login URL** (Render)
3. Complete login
4. Click **Initialise Strategy**
5. Scheduler auto-starts strategy at 9:20 AM IST

---

## 4. Fyers API Portal Setup

1. Go to https://myapi.fyers.in
2. Login → My Apps → Create App
3. Fill in:
   - App Name: NIFTY Terminal
   - Redirect URL:
     - Local: `http://127.0.0.1:8085/callback`
     - Render: `https://trade.fyers.in`
4. Note your **App ID** (Client ID) and **Secret Key**

---

## 5. Telegram Bot Setup

1. Open Telegram → Search `@BotFather` → `/newbot`
2. Follow prompts → copy the **Bot Token**
3. Start a conversation with your new bot (search its name, click Start)
4. Get your Chat ID: visit this URL in browser:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Look for `"id"` inside `"chat"` in the response
5. Enter both in Profile tab → Test Telegram Alert

---

## 6. Quick Reference

| Where | URL |
|---|---|
| Local app | http://localhost:8501 |
| Render free | https://your-app.onrender.com |
| Fyers portal | https://myapi.fyers.in |
| Render dashboard | https://dashboard.render.com |
