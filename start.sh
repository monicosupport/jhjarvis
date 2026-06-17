#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# J.A.R.V.I.S. Termux Launcher
# Auto-starts Ollama + backend, opens browser
# ============================================================
JARVIS_DIR="$HOME/jarvis"
LOG_DIR="/tmp/jarvis_logs"
mkdir -p "$LOG_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    J.A.R.V.I.S.  ·  TERMUX LAUNCHER     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Dependencies ─────────────────────────────────────────────
echo "[*] Checking Python dependencies..."
pip install flask flask-cors -q 2>/dev/null
echo "    flask: OK"

# ── Kill stale server ─────────────────────────────────────────
pkill -f "server.py" 2>/dev/null

# ── Ollama ────────────────────────────────────────────────────
if command -v ollama &>/dev/null; then
    if ! pgrep -x "ollama" > /dev/null 2>&1; then
        echo "[*] Starting Ollama..."
        ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
        OLLAMA_PID=$!
        echo "    Ollama PID: $OLLAMA_PID"
        sleep 5
    else
        echo "[*] Ollama: already running"
    fi

    # Pull a small model if nothing installed
    MODEL_COUNT=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
    if [ "$MODEL_COUNT" -eq 0 ]; then
        echo "[*] No models found. Pulling llama3.2:1b (smallest)..."
        ollama pull llama3.2:1b &
        echo "    (Pull running in background — check: ollama list)"
    else
        echo "[*] Models available: $MODEL_COUNT"
    fi
else
    echo "[!] Ollama not found."
    echo "    Install: curl -fsSL https://ollama.ai/install.sh | sh"
    echo "    Or on Termux: pkg install ollama (if available)"
fi

# ── JARVIS Backend ────────────────────────────────────────────
echo "[*] Starting JARVIS backend..."
cd "$JARVIS_DIR"
python3 server.py > "$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "    Server PID: $SERVER_PID"
sleep 2

# ── Verify ────────────────────────────────────────────────────
if kill -0 $SERVER_PID 2>/dev/null; then
    echo ""
    echo "  ✓ J.A.R.V.I.S. ONLINE → http://localhost:8000"
    echo "  ✓ Logs: $LOG_DIR/server.log"
    echo "  ✓ Workspace: ~/jarvis_workspace"
    echo ""

    # Open browser
    if command -v termux-open-url &>/dev/null; then
        termux-open-url "http://localhost:8000"
    elif command -v am &>/dev/null; then
        am start -a android.intent.action.VIEW -d "http://localhost:8000" 2>/dev/null
    else
        echo "  Open http://localhost:8000 in your browser"
    fi
else
    echo ""
    echo "  ✗ Server failed. Check: cat $LOG_DIR/server.log"
fi

# ── Save PID for stop script ──────────────────────────────────
echo "$SERVER_PID" > /tmp/jarvis_server.pid
echo ""
