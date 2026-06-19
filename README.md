# J.A.R.V.I.S. — Local AI Agent for Termux

A fully offline AI assistant that runs on your Android device via Termux + Ollama.

---

## Requirements

- Termux (F-Droid version recommended)
- Termux:API (for device info)
- Android 8+ device, 3GB+ RAM recommended

---

## Installation

```bash
# 1. Install Termux packages
pkg update && pkg upgrade -y
pkg install python git curl wget -y

# 2. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 3. Clone J.A.R.V.I.S.
git clone https://github.com/monicosupport/jhjarvis.git ~/jarvis

# 4. Launch
cd ~/jarvis && bash start.sh
```

`start.sh` will:
- Install Python dependencies (flask, flask-cors)
- Start the Ollama server
- Pull the best model for your device (auto-detected by RAM)
- Create the uncensored `jarvis` model wrapper
- Open the UI in your browser at `http://localhost:8000`

---

## Updating

**Quick update (one command):**
```bash
cd ~/jarvis && git pull && bash start.sh
```

**Update + apply all patches (hotfix included):**
```bash
cd ~/jarvis && git pull && python3 hotfix.py
```

Or step by step:
```bash
cd ~/jarvis
git pull
bash start.sh
```

If you have local changes you want to keep:

```bash
cd ~/jarvis
git stash          # save your local changes
git pull           # get latest
git stash pop      # re-apply your changes (if compatible)
bash start.sh
```

Force reset to latest (discards all local changes):

```bash
cd ~/jarvis
git fetch origin
git reset --hard origin/main
bash start.sh
```

---

## Manual Model Management

The UI sidebar has a **DOWNLOAD MODEL** section — pick any model and tap **PULL SELECTED**.

To manage models directly in Termux:

```bash
# List installed models
ollama list

# Pull a model manually
ollama pull tinyllama:1.1b
ollama pull llama3.2:1b
ollama pull phi3:mini

# Remove a model
ollama rm <model-name>

# Rebuild the jarvis uncensored wrapper
ollama rm jarvis
bash ~/jarvis/start.sh
```

### Recommended models by RAM

| RAM | Model | Size |
|-----|-------|------|
| 2GB | tinyllama:1.1b | 600MB |
| 3GB | llama3.2:1b | 1.3GB |
| 4GB | llama3.2:3b or phi3:mini | 2-2.3GB |
| 6GB+ | mistral:7b or dolphin-mistral | 4.1GB |

---

## Restart / Stop

```bash
# Start
cd ~/jarvis && bash start.sh

# Stop (kill Flask + Ollama)
pkill -f "python.*server.py"
pkill ollama

# Restart cleanly
pkill -f "python.*server.py"; pkill ollama
cd ~/jarvis && bash start.sh
```

---

## Features

- Fully local LLM via Ollama - no internet required after setup
- Uncensored `jarvis` model wrapper (no safety filters)
- Auto-executes `<bash>` commands inline - Jarvis runs tasks, not just talks
- Web search (`<search>`) and page browsing (`<browse>`) via DuckDuckGo
- Persistent memory across restarts (`memory.json`)
- Understands casual/slang speech (40+ term expander)
- Voice input (STT) and output (TTS) via Web Speech API
- Cybersecurity toolkit - nmap, hydra, sqlmap, john, aircrack-ng, gobuster, ffuf, etc.
- Autonomous coding skill - writes, saves, runs, fixes, re-runs
- Hardware monitoring - CPU, RAM, battery, temps from `/proc`
- Sub-agents - spawn background Python worker processes
- Self-rewrite - ask Jarvis to modify its own code

---

## Workspace

Data is stored in `~/jarvis_workspace/`:

```
~/jarvis_workspace/
├── memory.json          # Conversation history
├── user_profile.json    # Detected user profile/preferences
├── device_config.json   # Device capabilities cache
├── agents/              # Sub-agent scripts + output
└── backups/             # Self-rewrite backups
```

---

## Troubleshooting

**Error 400 / model not working**
```bash
ollama rm jarvis
cd ~/jarvis && bash start.sh
```

**Ollama not starting**
```bash
pkill ollama
ollama serve &
sleep 5
ollama list
```

**Port 8000 already in use**
```bash
pkill -f "python.*server.py"
cd ~/jarvis && python server.py
```

**No models installed**
```bash
ollama pull tinyllama:1.1b   # smallest/fastest
```

**Voice not working**
- Tap the button first to unlock audio
- Grant microphone permission when prompted
- TTS requires network on some Android versions for voice data

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server status |
| POST | `/api/chat` | SSE streaming chat |
| GET | `/api/models` | List installed models |
| POST | `/api/pull` | Pull a model |
| POST | `/api/bash` | Execute shell command |
| POST | `/api/search` | DuckDuckGo search |
| POST | `/api/browse` | Fetch webpage |
| GET | `/api/memory` | View memory |
| POST | `/api/memory/clear` | Clear memory |
| GET | `/api/device` | Device info |
| GET | `/api/system` | System stats |
| POST | `/api/agents/spawn` | Spawn sub-agent |

---

## Git Commands Reference

### Pull / Sync

```bash
git pull                        # fetch + merge latest
git pull --rebase               # cleaner history (no merge commit)
git pull origin main            # pull specific branch
```

### Handle Local Changes Before Pulling

```bash
git stash                       # save local changes temporarily
git pull                        # get latest from remote
git stash pop                   # restore your changes on top

git stash list                  # see all saved stashes
git stash drop                  # delete the top stash (if not needed)
```

### Discard / Reset Changes

```bash
git checkout start.sh           # discard changes to one file
git checkout -- .               # discard ALL local changes

git fetch origin
git reset --hard origin/main    # nuclear: match remote exactly
```

### Commit and Push

```bash
git add .                       # stage all changes
git add start.sh                # stage a specific file
git commit -m "your message"    # commit
git push                        # push to remote
git push origin main            # push specific branch
git commit -am "your message"   # stage modified files + commit in one step
```

### Check Status and Diff

```bash
git status                      # see what changed
git diff                        # line-by-line diff of unstaged changes
git diff start.sh               # diff a specific file
git log --oneline               # commit history (compact)
git log --oneline -5            # last 5 commits only
```

### Branches

```bash
git branch                      # list branches
git checkout -b feature/name    # create + switch to new branch
git checkout main               # switch to existing branch
git branch -d feature/name      # delete local branch
git push -u origin feature/name # push new branch to remote
```

### Fix Merge Conflicts

```bash
git status                              # find conflicted files

# After manually resolving conflicts in the file:
git add start.sh
git commit -m "resolve merge conflict"

# Take the remote version of a file (theirs)
git checkout --theirs start.sh && git add start.sh

# Keep your local version (ours)
git checkout --ours start.sh && git add start.sh
```

### Undo Mistakes

```bash
git reset --soft HEAD~1         # undo last commit, keep changes staged
git reset --hard HEAD~1         # undo last commit + discard changes
git revert <commit-sha>         # safe undo (safe for shared branches)
git commit --amend -m "fixed"   # fix last commit message
```

### Useful One-Liners

```bash
# Update + restart Jarvis in one shot
cd ~/jarvis && git stash && git pull && git stash pop && bash start.sh

# Check what changed since last pull
git diff HEAD@{1} HEAD --stat

# See who changed what
git log --oneline --author="yourname"

# Undo all local changes and sync to remote clean
git fetch origin && git reset --hard origin/main
```

---

## License

MIT
