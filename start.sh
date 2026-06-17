#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# J.A.R.V.I.S. Termux Launcher v2.2 — Universal Edition
# Works on Android 7+ · ARM32 + ARM64 · 1GB–16GB RAM
# No root required
# ============================================================
JARVIS_DIR="$HOME/jarvis"
# Termux uses $TMPDIR, not /tmp (which doesn't exist without root)
TMPBASE="${TMPDIR:-$PREFIX/tmp}"
LOG_DIR="$TMPBASE/jarvis_logs"
BIN_DIR="$HOME/bin"
mkdir -p "$LOG_DIR" "$BIN_DIR"

# Add ~/bin to PATH
export PATH="$BIN_DIR:$PREFIX/bin:$PATH"

# ── Banner ────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  J.A.R.V.I.S.  ·  UNIVERSAL TERMUX EDITION  ║"
echo "║     v2.2  — works on any Android device      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Device Detection ──────────────────────────────────────────
ARCH=$(uname -m)                      # aarch64 | armv7l | x86_64
ANDROID=$(getprop ro.build.version.release 2>/dev/null || echo "unknown")
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 2097152)
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))

echo "[*] Device info:"
echo "    Architecture : $ARCH"
echo "    Android      : $ANDROID"
echo "    RAM          : ${TOTAL_RAM_MB}MB"
echo ""

# ── Determine best model for this device's RAM ────────────────
if   [ "$TOTAL_RAM_MB" -lt 1800 ]; then MODEL="tinyllama"
elif [ "$TOTAL_RAM_MB" -lt 3500 ]; then MODEL="llama3.2:1b"
elif [ "$TOTAL_RAM_MB" -lt 6000 ]; then MODEL="llama3.2:3b"
else                                     MODEL="llama3"
fi
echo "[*] Recommended model for ${TOTAL_RAM_MB}MB RAM: $MODEL"
echo ""

# ── Set num_ctx based on RAM ──────────────────────────────────
if   [ "$TOTAL_RAM_MB" -lt 2000 ]; then NUM_CTX=512
elif [ "$TOTAL_RAM_MB" -lt 4000 ]; then NUM_CTX=1024
elif [ "$TOTAL_RAM_MB" -lt 6000 ]; then NUM_CTX=2048
else                                     NUM_CTX=4096
fi
export JARVIS_NUM_CTX="$NUM_CTX"
echo "[*] Context window: $NUM_CTX tokens"

# ── Core dependencies ─────────────────────────────────────────
echo "[*] Installing core packages (pkg)..."
# Always update first — old Termux pkg index is stale
pkg update -y -q 2>/dev/null || true

for pkg_name in python git curl wget; do
    if ! command -v "$pkg_name" &>/dev/null; then
        pkg install -y "$pkg_name" -q 2>/dev/null && echo "    $pkg_name: installed" || echo "    $pkg_name: failed (continuing)"
    else
        echo "    $pkg_name: OK"
    fi
done

# ── Python pip packages ───────────────────────────────────────
echo "[*] Installing Python packages..."
pip install flask flask-cors -q 2>/dev/null || pip3 install flask flask-cors -q 2>/dev/null
echo "    flask + flask-cors: OK"

# ── Ollama install (smart multi-path) ─────────────────────────
echo ""
echo "[*] Checking Ollama..."
OLLAMA_OK=false

# Path 1: pkg install ollama (F-Droid Termux, recent versions)
if ! command -v ollama &>/dev/null; then
    echo "    Trying pkg install ollama..."
    pkg install -y ollama -q 2>/dev/null && OLLAMA_OK=true
fi

# Path 2: Binary download (for old Termux or Play Store version)
if ! command -v ollama &>/dev/null && [ "$ARCH" = "aarch64" ]; then
    echo "    pkg failed — downloading Ollama binary (ARM64)..."
    OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-linux-arm64"
    if curl -fsSL -o "$BIN_DIR/ollama" "$OLLAMA_URL" 2>/dev/null; then
        chmod +x "$BIN_DIR/ollama"
        command -v ollama &>/dev/null && OLLAMA_OK=true && echo "    Binary installed: OK"
    else
        echo "    Binary download failed — will run UI-only mode"
    fi
fi

# Path 3: ARM32 — Ollama doesn't support it; skip gracefully
if ! command -v ollama &>/dev/null && [ "$ARCH" = "armv7l" ]; then
    echo "    [!] ARM32 device — Ollama requires ARM64."
    echo "        J.A.R.V.I.S. will run in offline/demo mode."
    export JARVIS_NO_OLLAMA=1
fi

if command -v ollama &>/dev/null; then
    echo "    Ollama: $(ollama --version 2>/dev/null || echo 'available')"
    OLLAMA_OK=true
fi

# ── Start Ollama ──────────────────────────────────────────────
if [ "$OLLAMA_OK" = "true" ]; then
    if ! pgrep -x "ollama" > /dev/null 2>&1; then
        echo "[*] Starting Ollama daemon..."
        OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
        ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
        sleep 4
    else
        echo "[*] Ollama: already running"
    fi

    # Pull recommended model if nothing installed — SYNCHRONOUS so it's ready before the browser opens
    MODEL_COUNT=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
    if [ "$MODEL_COUNT" -eq 0 ]; then
        echo ""
        echo "╔══════════════════════════════════════════════╗"
        echo "║  No models found — pulling $MODEL"
        echo "║  This may take 2–10 minutes on first run.    "
        echo "║  Progress shown below. Please wait...        "
        echo "╚══════════════════════════════════════════════╝"
        echo ""
        ollama pull "$MODEL"
        PULL_EXIT=$?
        if [ "$PULL_EXIT" -ne 0 ]; then
            echo "[!] Pull failed (exit $PULL_EXIT). Trying tinyllama as fallback..."
            ollama pull tinyllama
            MODEL="tinyllama"
        fi
        echo "[✓] Model ready"
    else
        # Use the ACTUAL installed model name, not the RAM-guessed one
        INSTALLED_MODEL=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | head -1)
        if [ -n "$INSTALLED_MODEL" ]; then
            MODEL="$INSTALLED_MODEL"
        fi
        echo "[*] Models available: $MODEL_COUNT"
        ollama list 2>/dev/null | tail -n +2 | awk '{print "    • "$1}'
        echo "[*] Active model: $MODEL"
    fi
fi

# ── Write device config for server.py ─────────────────────────
cat > "$JARVIS_DIR/device_config.json" <<EOF
{
  "arch": "$ARCH",
  "android": "$ANDROID",
  "ram_mb": $TOTAL_RAM_MB,
  "num_ctx": $NUM_CTX,
  "recommended_model": "$MODEL",
  "ollama_available": $( [ "$OLLAMA_OK" = "true" ] && echo "true" || echo "false")
}
EOF
echo "[*] Device config written."

# ── Kill stale server ─────────────────────────────────────────
pkill -f "server.py" 2>/dev/null; sleep 1

# ── Start JARVIS backend ──────────────────────────────────────
echo "[*] Starting J.A.R.V.I.S. backend..."
cd "$JARVIS_DIR"
python3 server.py > "$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$TMPBASE/jarvis_server.pid"
sleep 2

# ── Result ────────────────────────────────────────────────────
if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo ""
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║   ✓  J.A.R.V.I.S. IS ONLINE             ║"
    echo "  ║   →  http://localhost:8000               ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo ""
    echo "  RAM:    ${TOTAL_RAM_MB}MB  |  Arch: $ARCH  |  ctx: $NUM_CTX"
    echo "  Model:  $MODEL"
    echo "  Logs:   $LOG_DIR/server.log"
    echo ""

    # Open browser
    if command -v termux-open-url &>/dev/null; then
        termux-open-url "http://localhost:8000"
    else
        am start -a android.intent.action.VIEW -d "http://localhost:8000" 2>/dev/null || \
        echo "  → Open http://localhost:8000 in your browser"
    fi
else
    echo ""
    echo "  ✗ Server failed. Check:"
    echo "    cat $LOG_DIR/server.log"
    tail -5 "$LOG_DIR/server.log" 2>/dev/null
fi
echo ""
