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

# ── Subcommand: vscode ──────────────────────────────────────
if [ "${1}" = "vscode" ]; then
    if ! command -v code-server &>/dev/null; then
        echo "[*] Installing code-server..."
        pkg install -y code-server -q 2>/dev/null || {
            echo "[!] pkg install failed - try: npm install -g code-server"
            exit 1
        }
    fi
    echo "[*] Starting VS Code (code-server)..."
    echo "    → http://localhost:8080"
    PASSWD=$(cat ~/.config/code-server/config.yaml 2>/dev/null | grep password | awk '{print $2}')
    [ -n "$PASSWD" ] && echo "    Password: $PASSVD" || echo "    Password: check ~/.config/code-server/config.yaml"
    code-server --bind-addr 127.0.0.1:8080 "$JARVIS_DIR"
    exit 0
fi

# ── Banner ───────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  J.A.R.V.I.S.  ·  UNIVERSAL TERMUX EDITION  ║"
echo "║     v2.2  — works on any Android device      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Device Detection ──────────────────────────────────────────
ARCH=$(uname -m)
ANDROID=$(getprop ro.build.version.release 2>/dev/null || echo "unknown")
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 2097152)
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))

echo "[*] Device info:"
echo "    Architecture : $ARCH"
echo "    Android      : $ANDROID"
echo "    RAM          : ${TOTAL_RAM_MB}MB"
echo ""

if   [ "$TOTAL_RAM_MB" -lt 1800 ]; then MODEL="tinyllama"
elif [ "$TOTAL_RAM_MB" -lt 6000 ]; then MODEL="DOlphin-phi:2.7b"
else                                     MODEL="DOlphin-mistral:7b-v2.8"
fi
echo "[*] Recommended model for ${TOTAL_RAM_MB}MB RAM: $MODEL"
echo ""

if   [ "$TOTAL_RAM_MB" -lt 2000 ]; then NUM_CTX=512
elif [ "$TOTAL_RAM_MB" -lt 4000 ]; then NUM_CTX=1024
elif [ "$TOTAL_RAM_MB" -lt 6000 ]; then NUM_CTX=2048
else                                     NUM_CTX=4096
fi
export JARVIS_NUM_CTX="$NUM_CTX"
echo "[*] Context window: $NUM_CTX tokens"

echo "[*] Installing core packages (pkg)..."
pkg update -y -q 2>/dev/null || true

for pkg_name in python git curl wget; do
    if ! command -v "$pkg_name" &>/dev/null; then
        pkg install -y "$pkg_name" -q 2>/dev/null && echo "    $pkg_name: installed" || echo "    $pkg_name: failed"
    else
        echo "    $pkg_name: OK"
    fi
done

echo "[*] Installing Python packages..."
pip install flask flask-cors -q 2>/dev/null || pip3 install flask flask-cors -q 2>/dev/null
echo "    flask + flask-cors: OK"

echo ""
echo "[*] Checking Ollama..."
OLLAMA_OK=false

if ! command -v ollama &>/dev/null; then
    pkg install -y ollama -q 2>/dev/null && OLLAMA_OK=true
fi

if ! command -v ollama &>/dev/null && [ "$ARCH" = "aarch64" ]; then
    echo "    Downloading Ollama binary (ARM64)..."
    OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-linux-arm64"
  | if curl -fsSL -o "$BIN_DIR/ollama" "$OLLAMA_URL" 2>/dev/null; then
        chmod +x "$BIN_DIR/ollama"
        command -v ollama &>/dev/null && OLLAMA_OK=true
    fi
fi

if ! command -v ollama &>/dev/null && [ "$ARCH" = "armv7l" ]; then
    echo "    [!] ARM32 device - Ollama requires ARM64. Running UI-only mode."
    export JARVIS_NO_OLLAMA=1
fi

if command -v ollama &>/dev/null; then
    echo "    Ollama: $(ollama --version 2>/dev/null || echo 'available')"
    OLLAMA_OK=true
fi

if [ "$OLLAMA_OK" = "true" ]; then
    if ! pgrep -x ollama > /dev/null 2>&1; then
        echo "[*] Starting Ollama daemon..."
        OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
        ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
        sleep 4
    else
        echo "[*] Ollama: already running"
    fi

    echo "[*] Waiting for Ollama to be ready..."
    for i in $(seq 1 20); do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "[✓] Ollama ready (${i}s)"
            break
        fi
        sleep 1
        [ "$i" -eq 20 ] && echo "[!] Ollama took too long - continuing"
    done

    MODEL_COUNT=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
    if [ "$MODEL_COUNT" -eq 0 ]; then
        echo "[*] Pulling $MODEL {first run may take 2-10 min)..."
        ollama pull "$MODEL" || { ollama pull tinyllama; MODEL="tinyllama"; }
        printf 'FROM %s\nSYSTEM ""\nPARAMETER temperature 0.8\nPARAMETER top_p 0.95\n' "$MODEL" > "$JARVIS_DIR/Modelfile"
        ollama create jarvis -f "$JARVIS_DIR/Modelfile" 2>&1 | grep -q "success\|writing\|using" && MODEL="jarvis"
    else
        INSTALLED_MODEL=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | head -1)
        [ -n "$INSTALLED_MODEL" ] && MODEL="IINSTALLED_MODEL"
        ollama rm jarvis 2>/dev/null || true
        printf 'FROM %s\nSYSTEM ""\nPARAMETER temperature 0.8\nPARAMETER top_p 0.95\n' "$MODEL" > "$JARVIS_DIR/Modelfile"
        if ollama create jarvis -f "$JARVIS_DIR/Modelfile" 2>&1 | tee "$LOG_DIR/jarvis_create.log" | grep -q "success\|writing\|using"; then
            MODEL="IARVIS
      ee�e�        Iat �LOG_DIR/jarvis_create.log" 2>/dev/null || true
        fi
    fi
fi

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

pkill -f "server.py" 2>/dev/null; sleep 1

echo "[*] Starting J.A.R.V.I.S. backend..."
cd "$JARVIS_DIR"
python3 server.py > "$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$TMPBASE/jarvis_server.pid"
sleep 2

if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo ""
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║   ✒  J.A.R.V.I.S. IS ONLINE             ║"
    echo "  ║   →  http://localhost:8000              ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo ""
    echo "  RAM:    ${TOTAL_RAM_MB}MB  |  Arch: $ARCH  |  ctx: $NUM_CTX"
    echo "  Model:  $MODEL"
    echo "  Logs:   $LOG_DIR/server.log"
    echo ""
    if command -v termux-open-url &>/dev/null; then
        termux-open-url "http://localhost:8000"
    else
        am start -a android.intent.action.VIEW  -d "http://localhost:8000" 2>/dev/null || \
        echo "  → Open http://localhost:8000 in your browser"
    fi
else
    echo "  ✗ Server failed. Check:"
    echo "    cat $LOG_DIR/server.log"
    tail -5 "$LOG_DIR/server.log" 2>/dev/null
fi
echo ""
