#!/usr/bin/env python3
"""
Hotfix for J.A.R.V.I.S. — Error 400 fix (broken jarvis model fallback).
Run in Termux: python3 hotfix.py
"""
import os, re, subprocess

srv = os.path.expanduser("~/jarvis/server.py")
if not os.path.exists(srv):
    print("[!] server.py not found — are you in the right directory?"); exit(1)

with open(srv) as f:
    src = f.read()

patched = False

# ── Patch 1: smarter get_best_model with jarvis validation ──────────────────
OLD1 = '''def get_best_model(requested=None):
    """Return (model_name, None) if ready, or (None, pulling_target) if not."""
    models = get_installed_models()
    if models:
        # Always prefer the custom uncensored 'jarvis' model if it exists
        for m in models:
            if m.lower() == 'jarvis:latest' or m.lower() == 'jarvis':
                return m, None
        if requested:
            base = requested.split(':')[0].lower()
            for m in models:
                if base in m.lower():
                    return m, None
        # Requested model not found but we DO have something installed — use it
        return models[0], None
    # Nothing installed at all
    target = _device.get('recommended_model', 'dolphin-phi:2.7b')
    return None, target'''

NEW1 = '''def get_best_model(requested=None):
    """Return (model_name, None) if ready, or (None, pulling_target) if not."""
    models = get_installed_models()
    if models:
        # Try jarvis first, but skip it if Ollama rejects it (broken Modelfile)
        for m in models:
            if m.lower() in ('jarvis:latest', 'jarvis'):
                try:
                    p = json.dumps({"model": m, "messages": [{"role":"user","content":"hi"}],
                                    "stream": False, "options": {"num_predict": 1}}).encode()
                    req = urllib.request.Request(f"{OLLAMA_BASE}/api/chat", data=p,
                                                 headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        if r.status == 200:
                            return m, None
                except Exception:
                    pass
                # jarvis broken — remove it so start.sh recreates it next boot
                try: subprocess.run(["ollama","rm","jarvis"], capture_output=True, timeout=10)
                except Exception: pass
                break
        # Fall back to any non-jarvis model
        for m in models:
            if "jarvis" not in m.lower():
                return m, None
        return models[0], None
    target = _device.get('recommended_model', 'dolphin-phi:2.7b')
    return None, target'''

if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    patched = True
    print("[✓] Patch 1 applied: jarvis validation + fallback")
elif "if m.lower() in ('jarvis:latest', 'jarvis'):" in src:
    print("[~] Patch 1 already applied")
    patched = True
else:
    print("[!] Patch 1: could not find target — server.py may be a different version")

# ── Patch 2: catch HTTP 400 in generate() and retry with fallback model ─────
OLD2 = "        except Exception as e:\n            yield f\"data: {json.dumps({'error': True, 'response': f'[OLLAMA ERROR] {str(e)}'})}\\n\\n\""
NEW2 = (
    "        except urllib.error.HTTPError as he:\n"
    "            if he.code in (400, 404):\n"
    "                fb = next((m for m in get_installed_models() if 'jarvis' not in m.lower()), None)\n"
    "                msg = f'\\u26a0\\ufe0f Model rejected (HTTP {he.code}). ' + (f'Retrying with {fb}\\u2026' if fb else 'Run bash start.sh to rebuild.')\n"
    "                yield f\"data: {json.dumps({'token': msg})}\\n\\n\"\n"
    "                if fb:\n"
    "                    try:\n"
    "                        p2 = json.dumps({'model': fb, 'messages': messages, 'stream': True, 'options': {'num_ctx': num_ctx, 'temperature': 0.7}}).encode()\n"
    "                        r2 = urllib.request.Request(f'{OLLAMA_BASE}/api/chat', data=p2, headers={'Content-Type': 'application/json'})\n"
    "                        with urllib.request.urlopen(r2, timeout=180) as resp2:\n"
    "                            for raw2 in resp2:\n"
    "                                raw2 = raw2.strip()\n"
    "                                if not raw2: continue\n"
    "                                try: c2 = json.loads(raw2)\n"
    "                                except Exception: continue\n"
    "                                t2 = c2.get('message', {}).get('content', '')\n"
    "                                if t2: yield f\"data: {json.dumps({'token': t2})}\\n\\n\"\n"
    "                                if c2.get('done'): yield f\"data: {json.dumps({'done': True, 'model': fb})}\\n\\n\"\n"
    "                    except Exception as e2:\n"
    "                        yield f\"data: {json.dumps({'error': True, 'response': f'Fallback failed: {e2}'})}\\n\\n\"\n"
    "            else:\n"
    "                yield f\"data: {json.dumps({'error': True, 'response': f'HTTP {he.code}'})}\\n\\n\"\n"
    "        except Exception as e:\n"
    "            yield f\"data: {json.dumps({'error': True, 'response': f'[OLLAMA ERROR] {str(e)}'})}\\n\\n\""
)

if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1)
    patched = True
    print("[✓] Patch 2 applied: HTTP 400 fallback in generate()")
elif "except urllib.error.HTTPError as he:" in src:
    print("[~] Patch 2 already applied")
else:
    print("[!] Patch 2: target not found")

# ── Patch 3: global Flask 500 error handler (returns JSON, not HTML) ─────────
OLD3 = "if __name__ == '__main__':"
NEW3 = (
    "@app.errorhandler(Exception)\n"
    "def handle_exception(e):\n"
    "    import traceback\n"
    "    tb = traceback.format_exc()\n"
    "    app.logger.error('Unhandled exception: %s', tb)\n"
    "    return jsonify({'error': True, 'response': f'Server error: {str(e)}', 'trace': tb[-500:]}), 500\n\n"
    "@app.errorhandler(404)\n"
    "def handle_404(e):\n"
    "    return jsonify({'error': True, 'response': 'Not found'}), 404\n\n"
    "if __name__ == '__main__':"
)

if OLD3 in src and "@app.errorhandler(Exception)" not in src:
    src = src.replace(OLD3, NEW3, 1)
    patched = True
    print("[✓] Patch 3 applied: global 500/404 JSON error handlers")
elif "@app.errorhandler(Exception)" in src:
    print("[~] Patch 3 already applied")
else:
    print("[!] Patch 3: could not find 'if __name__' block")

if patched:
    bak = srv + ".bak"
    import shutil; shutil.copy(srv, bak)
    with open(srv, "w") as f:
        f.write(src)
    print(f"[✓] Saved. Backup at {bak}")
    print("[*] Restarting server...")
    subprocess.Popen(["bash", os.path.expanduser("~/jarvis/start.sh")],
                     stdout=open("/tmp/jarvis_restart.log","w"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    print("[✓] Start.sh launched — check your browser in ~10s")
else:
    print("[!] No patches applied.")
