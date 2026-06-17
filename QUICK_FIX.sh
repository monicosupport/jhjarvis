#!/bin/bash
# Quick fix for stuck processing — restart Ollama

echo "[!] Killing stuck Ollama processes..."
pkill -9 ollama 2>/dev/null
sleep 1

echo "[!] Killing stuck server..."
pkill -9 -f "server.py" 2>/dev/null
sleep 1

echo "[✓] Processes killed. Restarting..."
# Restart Ollama (if installed)
if command -v ollama &> /dev/null; then
    echo "[*] Starting Ollama..."
    ollama serve > ~/ollama.log 2>&1 &
    sleep 3
fi

# Restart JARVIS
cd ~/jarvis || cd ~/

if [ -f "./start.sh" ]; then
    bash ./start.sh
else
    echo "[!] start.sh not found"
    python3 server.py
fi
