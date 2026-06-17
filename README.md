# J.A.R.V.I.S. — Local Agent Client (Termux Edition)

> **Just A Rather Very Intelligent System** — running 100% locally on your Android device via Termux + Ollama.

## Features
- 🎤 **Wake-word activation** — just say *"Hey Jarvis"*  
- 🗣️ **Text-to-speech** responses (Web Speech API)  
- 🤖 **Ollama integration** — any local LLM (llama3, mistral, etc.)  
- 📡 **Full device diagnostics** — CPU, RAM, storage, battery, temps, processes  
- 💾 **Auto-saves AI-generated code** to `~/jarvis_workspace`  
- 🛡️ **RAM overflow guard** — auto-trims context if RAM > 85%  
- 🌐 Holographic HUD interface  

## Quick Start (Termux)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Clone this repo
git clone https://github.com/monicosupport/jhjarvis ~/jarvis

# 3. Launch
chmod +x ~/jarvis/start.sh
~/jarvis/start.sh
```

## Endpoints
| Route | Description |
|-------|-------------|
| `GET /health` | Backend + Ollama status |
| `POST /api/chat` | Chat with Ollama model |
| `GET /api/models` | List installed Ollama models |
| `GET /api/system` | Real-time CPU + RAM stats |
| `GET /api/device` | Full device diagnostic scan |
| `POST /api/code` | Save (and optionally run) AI-generated code |
| `GET /api/workspace` | List saved code files |

## Voice Commands
Say **"Hey Jarvis"** to wake, then speak your command.  
Or click the mic button to force command mode.  
You can also type in the input bar.

## Requirements
- Termux (Android)
- Python 3 + pip
- `flask`, `flask-cors`  
- Ollama

---
*Built with ❤️ for local-first AI.*
