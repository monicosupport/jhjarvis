# J.A.R.V.I.S. — Local Agent Client (Termux Edition)

> **Just A Rather Very Intelligent System** — running 100% locally on your Android device via Termux + Ollama.

## Features
- 🎤 **Wake-word activation** — just say *"Hey Jarvis"*
- 🗣️ **ElevenLabs TTS voice** — Jarvis speaks back with a real AI voice
- 📖 **Ollama integration** — any local LLM (llama3, mistral, etc.)
- 🛡 **Full device diagnostics** — CPU, RAM, storage, battery, temps, processes
- 💾 **Auto-saves AI-generated code** to `~/jarvis_workspace`
- 🛑️ **RAM overflow guard** — auto-trims context if RAM > 85%
- 🌐 Holographic HUD interface with live hardware monitor
- 💻 **VS Code in browser** — edit Jarvis code from your phone via code-server

## Quick Start (Termux)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Clone this repo
git clone https://github.com/monicosupport/jhjarvis ~/jarvis

# 3. Set up
chmod +x ~/jarvis/start.sh
~/jarvis/start.sh install      # install all dependencies

# 4. Launch
~/jarvis/start.sh              # start Jarvis (Ollama + web server + voice)
```

## Launch Commands

| Command | What it does |
|---------|-------------|
| `~/jarvis/start.sh` | Start everything (Ollama + backend + opens browser) |
| `~/jarvis/start.sh install` | Install / update all dependencies |
| `~/jarvis/start.sh test-voice` | Test ElevenLabs voice — plays a spoken response |
| `~/jarvis/start.sh vscode` | Launch VS Code (code-server) at http://localhost:8080 |

## VS Code (code-server)

Edit `server.py`, `start.sh`, and all Jarvis files directly from your phone in a full browser-based VS Code.

**One-time install:**
```bash
pkg install code-server
```

**Launch:**
```bash
~/jarvis/start.sh vscode
# Then open http://localhost:8080 in your browser
```

> `start.sh vscode` auto-installs code-server if missing, opens the `~/jarvis` folder, and prints your password.

## Hardware Monitor (HUD)

The UI shows live hardware stats — auto-refreshes every 3 seconds:

| Metric | Source |
|--------|--------|
| ⚡ Latency | ms per AI response |
| 🧠 CPU | Core count + live usage % |
| 💾 RAM | Used / Total GB |
| 🗄️ Storage | Used / Total GB |
| 🔋 Battery | % + charging status |
| ⚠ Warnings | Context > 80% or battery ≤ 20% |

## Viewing Logs

Logs are written to `$TMPDIR/jarvis_logs/` — safe Termux path (`/tmp` requires root on Android).

```bash
cat ${TMPDIR:-$PREFIX/tmp}/jarvis_logs/server.log
cat ${TMPDIR:-$PREFIX/tmp}/jarvis_logs/ollama.log
```

## Endpoints

| Route | Description |
|-------|-------------|
| `GET /health` | Backend + Ollama status |
| `POST /api/chat` | Chat with Ollama model |
| `GET /api/models` | List installed models |
| `GET /api/system` | Real-time CPU + RAM stats |
| `GET /api/device` | Full diagnostic scan (CPU, RAM, storage, battery) |
| `POST /api/code` | Save / run AI-generated code |
| `GET /api/workspace` | List saved code files |

## Voice Commands
Say **"Hey Jarvis"** to wake, then speak your command.
Or click the mic button. You can also type in the input bar.

## Requirements
- Termux (Android)
- Python 3 + pip + `flask`, `flask-cors`
- Ollama
- ElevenLabs API key (voice)
- `code-server` (optional, VS Code)

---
*Built with ❤️ for local-first AI.*
