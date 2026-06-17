"""
J.A.R.V.I.S. Local Backend — Full Edition
Sub-agent manager, self-rewrite engine, full hardware diagnostics, Ollama proxy.
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess, json, os, sys, time, threading, shutil, signal
import urllib.request, urllib.error, base64

app = Flask(__name__, static_folder='static')
CORS(app)

OLLAMA_BASE = "http://localhost:11434"
WORKSPACE   = os.path.expanduser("~/jarvis_workspace")
AGENTS_DIR  = os.path.join(WORKSPACE, "agents")
BACKUP_DIR  = os.path.join(WORKSPACE, "backups")
for d in [WORKSPACE, AGENTS_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

SELF_PATH = os.path.abspath(__file__)

# ── Thread lock ────────────────────────────────────────────────────────────────
_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════════════════════
# CPU DELTA TRACKER
# ══════════════════════════════════════════════════════════════════════════════
_last_cpu = None

def _read_proc_cpu():
    with open('/proc/stat') as f:
        vals = list(map(int, f.readline().split()[1:8]))
    return vals[3], sum(vals)

def read_cpu():
    global _last_cpu
    try:
        idle, total = _read_proc_cpu()
        with _lock:
            if _last_cpu is None:
                _last_cpu = (idle, total)
                return 0.0
            p_idle, p_total = _last_cpu
            _last_cpu = (idle, total)
            d_total = total - p_total
            return round((1 - (idle - p_idle) / d_total) * 100, 1) if d_total else 0.0
    except: return 0.0

def read_mem():
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                p = line.split()
                if len(p) >= 2: info[p[0].rstrip(':')] = int(p[1])
        total = info.get('MemTotal', 1)
        avail = info.get('MemAvailable', total)
        return round((1 - avail / total) * 100, 1)
    except: return 0.0

# ══════════════════════════════════════════════════════════════════════════════
# SUB-AGENT MANAGER
# ══════════════════════════════════════════════════════════════════════════════
sub_agents = {}  # id -> agent dict

def _agent_monitor(agent_id, proc):
    """Background thread: watches a sub-agent process, captures output."""
    try:
        stdout, stderr = proc.communicate(timeout=3600)
        with _lock:
            if agent_id in sub_agents:
                sub_agents[agent_id]['status'] = 'completed' if proc.returncode == 0 else 'failed'
                sub_agents[agent_id]['return_code'] = proc.returncode
                if stdout:
                    sub_agents[agent_id]['log'].append(stdout.decode(errors='replace')[:1000])
                if stderr:
                    sub_agents[agent_id]['log'].append('STDERR: ' + stderr.decode(errors='replace')[:500])
    except subprocess.TimeoutExpired:
        proc.kill()
        with _lock:
            if agent_id in sub_agents:
                sub_agents[agent_id]['status'] = 'timeout'

def spawn_agent(name, script_path, task_description, args=None):
    """Spawn a sub-agent process. Returns agent_id."""
    agent_id = f"sa_{int(time.time())}_{name[:12].replace(' ','_')}"
    cmd = [sys.executable, script_path] + (args or [])
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True
        )
        with _lock:
            sub_agents[agent_id] = {
                'id'      : agent_id,
                'name'    : name,
                'pid'     : proc.pid,
                'status'  : 'running',
                'task'    : task_description,
                'script'  : script_path,
                'started' : time.time(),
                'log'     : [f"Spawned PID {proc.pid}"],
                'process' : proc,
            }
        t = threading.Thread(target=_agent_monitor, args=(agent_id, proc), daemon=True)
        t.start()
        return agent_id, None
    except Exception as e:
        return None, str(e)

def kill_agent(agent_id):
    with _lock:
        agent = sub_agents.get(agent_id)
    if not agent:
        return False, "Agent not found"
    proc = agent.get('process')
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            try: proc.terminate()
            except: pass
    with _lock:
        sub_agents[agent_id]['status'] = 'killed'
    return True, "Killed"

# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA HELPER
# ══════════════════════════════════════════════════════════════════════════════
def ollama(path, payload=None, timeout=120):
    url = f"{OLLAMA_BASE}{path}"
    try:
        if payload is not None:
            data = json.dumps(payload).encode()
            req  = urllib.request.Request(url, data=data,
                       headers={'Content-Type': 'application/json'})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), None
    except Exception as e:
        return None, str(e)

def ollama_generate(prompt, model='llama3', system=None):
    """Simple one-shot generation. Returns text or None."""
    messages = []
    if system:
        messages.append({"role":"system","content":system})
    messages.append({"role":"user","content":prompt})
    result, err = ollama('/api/chat', {
        "model"  : model,
        "messages": messages,
        "stream" : False,
        "options": {"num_ctx": 4096, "temperature": 0.3}
    }, timeout=180)
    if result:
        return result.get("message", {}).get("content", ""), None
    return None, err

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — CORE
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/health')
def health():
    result, _ = ollama('/api/version', timeout=3)
    return jsonify({"status": "online", "ollama": result or "starting", "agents": len(sub_agents)})

@app.route('/api/models')
def models():
    result, err = ollama('/api/tags')
    if result:
        return jsonify({"models": [m['name'] for m in result.get('models', [])]})
    return jsonify({"models": [], "error": err})

@app.route('/api/chat', methods=['POST'])
def chat():
    data    = request.json or {}
    model   = data.get('model', 'llama3')
    history = data.get('history', [])
    message = data.get('message', '')

    # ── Intercept built-in commands ───────────────────────────────────────────
    msg_lower = message.lower().strip()

    # SPAWN AGENT command
    if any(kw in msg_lower for kw in ['spawn agent', 'create agent', 'launch agent', 'start agent']):
        return _handle_spawn_command(message, model)

    # KILL AGENT command
    if any(kw in msg_lower for kw in ['kill agent', 'stop agent', 'terminate agent']):
        return _handle_kill_command(message)

    # LIST AGENTS command
    if any(kw in msg_lower for kw in ['list agents', 'show agents', 'active agents']):
        return _handle_list_agents()

    # REWRITE SELF / UPGRADE command
    if any(kw in msg_lower for kw in ['rewrite yourself', 'upgrade yourself', 'modify yourself', 'update your code', 'rewrite your']):
        return _handle_self_rewrite(message, model)

    # Regular chat
    messages = [{"role": m['role'], "content": m['content']} for m in history[-10:]]
    result, err = ollama('/api/chat', {
        "model"   : model,
        "messages": messages,
        "stream"  : False,
        "options" : {"num_ctx": 2048, "temperature": 0.7}
    }, timeout=180)

    if result:
        return jsonify({"response": result.get("message", {}).get("content", ""), "model": model})
    return jsonify({"response": f"[OLLAMA ERROR] {err}", "error": True})

# ── SPAWN HANDLER ──────────────────────────────────────────────────────────────
def _handle_spawn_command(message, model):
    """Ask Ollama to write agent code, save it, spawn it."""
    # Extract task from message
    task = message
    for kw in ['spawn agent', 'create agent', 'launch agent', 'start agent', 'to ', 'that ']:
        task = task.lower().replace(kw, ' ', 1)
    task = task.strip()

    agent_name = f"agent_{len(sub_agents)+1}"
    script_path = os.path.join(AGENTS_DIR, f"{agent_name}.py")

    # Get current model list
    result, _ = ollama('/api/tags')
    available_models = [m['name'] for m in result.get('models', [])] if result else ['llama3']
    use_model = model if model in available_models else (available_models[0] if available_models else 'llama3')

    # Ask Ollama to write the worker script
    system_prompt = """You are a Python code writer for a local AI agent system running on Android Termux.
Write ONLY a Python script with NO markdown, NO explanation, NO ```python blocks.
The script must:
1. Run as an autonomous worker loop (while True)
2. Write status/output to a JSON file: ~/jarvis_workspace/agents/<agent_name>_output.json
3. Use only stdlib (no pip installs)
4. Sleep appropriately between cycles
5. Handle exceptions gracefully
6. Exit cleanly on SIGTERM
Output only the raw Python code."""

    code, err = ollama_generate(
        f"Write a Python worker agent script that: {task}\nAgent name: {agent_name}",
        model=use_model,
        system=system_prompt
    )

    if not code or err:
        return jsonify({"response": f"Failed to generate agent code: {err}", "error": True})

    # Save the script
    with open(script_path, 'w') as f:
        f.write(code)

    # Spawn it
    agent_id, spawn_err = spawn_agent(agent_name, script_path, task)
    if spawn_err:
        return jsonify({"response": f"Code generated but spawn failed: {spawn_err}", "error": True})

    return jsonify({
        "response"  : f"Sub-agent `{agent_name}` spawned (PID {sub_agents[agent_id]['pid']}). Task: {task}\n\nScript saved to workspace/agents/{agent_name}.py",
        "agent_id"  : agent_id,
        "agent_name": agent_name,
        "spawned"   : True
    })

# ── KILL HANDLER ───────────────────────────────────────────────────────────────
def _handle_kill_command(message):
    # Find agent by name or id in message
    msg_lower = message.lower()
    with _lock:
        agent_list = list(sub_agents.values())

    target = None
    for agent in agent_list:
        if agent['name'].lower() in msg_lower or agent['id'].lower() in msg_lower:
            target = agent
            break

    if not target:
        names = [a['name'] for a in agent_list if a['status'] == 'running']
        return jsonify({"response": f"No matching agent found. Running agents: {names or 'none'}"})

    ok, msg = kill_agent(target['id'])
    return jsonify({"response": f"Agent `{target['name']}` — {msg}."})

# ── LIST AGENTS ────────────────────────────────────────────────────────────────
def _handle_list_agents():
    with _lock:
        agents = list(sub_agents.values())
    if not agents:
        return jsonify({"response": "No sub-agents spawned yet. Say 'spawn agent to [task]' to create one."})
    lines = []
    for a in agents:
        elapsed = int(time.time() - a['started'])
        lines.append(f"• [{a['status'].upper()}] {a['name']} (PID {a['pid']}) — {a['task'][:60]} — {elapsed}s ago")
    return jsonify({"response": "Active sub-agents:\n" + "\n".join(lines)})

# ── SELF-REWRITE HANDLER ───────────────────────────────────────────────────────
def _handle_self_rewrite(message, model):
    instruction = message
    for kw in ['rewrite yourself', 'upgrade yourself', 'modify yourself', 'update your code', 'rewrite your code']:
        instruction = instruction.replace(kw, '').replace(kw.capitalize(), '').strip()

    # Read current source
    with open(SELF_PATH) as f:
        current_code = f.read()

    result, _ = ollama('/api/tags')
    available_models = [m['name'] for m in result.get('models', [])] if result else ['llama3']
    use_model = model if model in available_models else (available_models[0] if available_models else 'llama3')

    system_prompt = """You are a Python code editor. The user will give you the current Flask server code and an instruction to modify it.
Return ONLY the complete modified Python source code with NO markdown, NO explanation, NO ```python blocks.
Preserve all existing functionality. Make the requested change cleanly."""

    prompt = f"""Current server code:
{current_code[:8000]}

Instruction: {instruction}

Return the complete modified Python file."""

    new_code, err = ollama_generate(prompt, model=use_model, system=system_prompt)
    if not new_code or err:
        return jsonify({"response": f"Could not generate rewrite: {err}", "error": True})

    # Backup
    backup_path = os.path.join(BACKUP_DIR, f"server_bak_{int(time.time())}.py")
    shutil.copy2(SELF_PATH, backup_path)

    # Write new code
    with open(SELF_PATH, 'w') as f:
        f.write(new_code)

    # Schedule restart
    def delayed_restart():
        time.sleep(1.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=delayed_restart, daemon=True).start()

    return jsonify({
        "response" : f"Self-rewrite complete. Backup saved. Restarting in 1.5s...",
        "rewritten": True,
        "backup"   : backup_path
    })

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — SUB-AGENTS API
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/agents')
def list_agents():
    with _lock:
        agents = []
        for a in sub_agents.values():
            agents.append({
                'id'     : a['id'],
                'name'   : a['name'],
                'pid'    : a['pid'],
                'status' : a['status'],
                'task'   : a['task'],
                'started': a['started'],
                'uptime' : int(time.time() - a['started']),
                'log'    : a['log'][-5:],
            })
    return jsonify({"agents": agents, "count": len(agents)})

@app.route('/api/agents/spawn', methods=['POST'])
def api_spawn_agent():
    data         = request.json or {}
    name         = data.get('name', f'agent_{len(sub_agents)+1}')
    code         = data.get('code', '')
    task         = data.get('task', 'Custom task')
    execute_code = data.get('execute', True)

    if not code:
        return jsonify({"error": "No code provided"}), 400

    script_path = os.path.join(AGENTS_DIR, f"{name}.py")
    with open(script_path, 'w') as f:
        f.write(code)

    if not execute_code:
        return jsonify({"saved": script_path})

    agent_id, err = spawn_agent(name, script_path, task)
    if err:
        return jsonify({"error": err}), 500
    return jsonify({"agent_id": agent_id, "name": name, "pid": sub_agents[agent_id]['pid']})

@app.route('/api/agents/<agent_id>/kill', methods=['POST'])
def api_kill_agent(agent_id):
    ok, msg = kill_agent(agent_id)
    return jsonify({"success": ok, "message": msg})

@app.route('/api/agents/<agent_id>/log')
def api_agent_log(agent_id):
    with _lock:
        agent = sub_agents.get(agent_id)
    if not agent:
        return jsonify({"error": "Not found"}), 404
    # Also read output file if exists
    out_file = os.path.join(AGENTS_DIR, f"{agent['name']}_output.json")
    output = None
    if os.path.exists(out_file):
        try:
            with open(out_file) as f:
                output = json.load(f)
        except: pass
    return jsonify({"log": agent['log'], "output": output})

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — SELF-REWRITE API
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/self/read')
def self_read():
    filename = request.args.get('file', 'server.py')
    # Security: only allow reading files in workspace or self
    if filename == 'server.py':
        path = SELF_PATH
    else:
        path = os.path.join(WORKSPACE, os.path.basename(filename))
    try:
        with open(path) as f:
            return jsonify({"file": filename, "content": f.read(), "path": path})
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route('/api/self/rewrite', methods=['POST'])
def api_self_rewrite():
    data     = request.json or {}
    filename = data.get('file', 'server.py')
    new_code = data.get('code', '')
    restart  = data.get('restart', True)

    if filename == 'server.py':
        target_path = SELF_PATH
    else:
        target_path = os.path.join(WORKSPACE, os.path.basename(filename))

    # Backup
    backup = os.path.join(BACKUP_DIR, f"{filename}.bak.{int(time.time())}")
    if os.path.exists(target_path):
        shutil.copy2(target_path, backup)

    with open(target_path, 'w') as f:
        f.write(new_code)

    if filename == 'server.py' and restart:
        def do_restart():
            time.sleep(1.5)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        threading.Thread(target=do_restart, daemon=True).start()
        return jsonify({"success": True, "restarting": True, "backup": backup})

    return jsonify({"success": True, "file": filename, "backup": backup})

@app.route('/api/self/history')
def self_history():
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True)[:10]:
        fp = os.path.join(BACKUP_DIR, f)
        backups.append({"name": f, "size": os.path.getsize(fp), "mtime": int(os.path.getmtime(fp))})
    return jsonify({"backups": backups})

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — HARDWARE & SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/system')
def system():
    return jsonify({"cpu": read_cpu(), "ram": read_mem(), "gpu": 0, "agents": len([a for a in sub_agents.values() if a['status']=='running'])})

@app.route('/api/device')
def device_scan():
    report = {}
    try:
        with open('/proc/uptime') as f: secs = float(f.read().split()[0])
        h, r = divmod(int(secs), 3600); m = r // 60
        report['uptime'] = f"{h}h {m}m"
    except: report['uptime'] = 'unknown'

    try:
        cores, model = 0, 'unknown'
        with open('/proc/cpuinfo') as f:
            for line in f:
                if 'processor' in line: cores += 1
                if 'model name' in line or 'Hardware' in line:
                    model = line.split(':',1)[-1].strip()
        report['cpu'] = {'cores': cores, 'model': model, 'load_pct': read_cpu()}
    except: report['cpu'] = {'load_pct': read_cpu()}

    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                p = line.split()
                if len(p) >= 2: info[p[0].rstrip(':')] = int(p[1])
        total_mb = info.get('MemTotal',0)//1024
        avail_mb = info.get('MemAvailable',0)//1024
        swap_t   = info.get('SwapTotal',0)//1024
        swap_f   = info.get('SwapFree',0)//1024
        report['memory'] = {'total_mb':total_mb,'available_mb':avail_mb,'used_pct':read_mem(),
                            'swap_total_mb':swap_t,'swap_used_mb':swap_t-swap_f}
    except: report['memory'] = {'used_pct': read_mem()}

    try:
        r = subprocess.run(['df','-h','/'],capture_output=True,text=True,timeout=5)
        lines = r.stdout.strip().split('\n')
        if len(lines) > 1:
            p = lines[1].split()
            report['storage'] = {'size':p[1],'used':p[2],'avail':p[3],'use_pct':p[4]}
    except: pass

    try:
        bat_paths = ['/sys/class/power_supply/battery','/sys/class/power_supply/Battery',
                     '/sys/class/power_supply/BAT0','/sys/class/power_supply/BAT1']
        for bp in bat_paths:
            if os.path.isdir(bp):
                bat = {}
                for key in ['capacity','status','temp','technology']:
                    fp = os.path.join(bp,key)
                    if os.path.exists(fp):
                        with open(fp) as f: bat[key] = f.read().strip()
                if 'temp' in bat: bat['temp_c'] = round(int(bat.pop('temp'))/10,1)
                report['battery'] = bat
                break
    except: pass

    try:
        ifaces = {}
        with open('/proc/net/dev') as f:
            f.readline(); f.readline()
            for line in f:
                p = line.split()
                if len(p) > 9:
                    ifaces[p[0].rstrip(':')] = {'rx_mb':round(int(p[1])/1024/1024,2),'tx_mb':round(int(p[9])/1024/1024,2)}
        report['network'] = ifaces
    except: pass

    try:
        temps = {}
        if os.path.isdir('/sys/class/thermal'):
            for tz in sorted(os.listdir('/sys/class/thermal'))[:8]:
                tp = f'/sys/class/thermal/{tz}/temp'
                if os.path.exists(tp):
                    with open(tp) as f: temps[tz] = round(int(f.read().strip())/1000,1)
        if temps: report['temperatures_c'] = temps
    except: pass

    try:
        r = subprocess.run(['ps','-eo','pid,pcpu,pmem,comm','--sort=-pcpu'],capture_output=True,text=True,timeout=5)
        procs = []
        for line in r.stdout.strip().split('\n')[1:8]:
            p = line.split(None,3)
            if len(p) >= 4: procs.append({'pid':p[0],'cpu':p[1],'mem':p[2],'cmd':p[3]})
        report['top_processes'] = procs
    except: pass

    try:
        for prop in ['ro.product.model','ro.product.brand','ro.build.version.release']:
            r = subprocess.run(['getprop',prop],capture_output=True,text=True,timeout=2)
            if r.returncode == 0 and r.stdout.strip():
                report.setdefault('android',{})[prop.split('.')[-1]] = r.stdout.strip()
    except: pass

    report['scanned_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(report)

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — CODE WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/api/code', methods=['POST'])
def code_write():
    data     = request.json or {}
    filename = os.path.basename(data.get('filename', f'code_{int(time.time())}.py'))
    src      = data.get('code', '')
    execute  = data.get('execute', False)

    filepath = os.path.join(WORKSPACE, filename)
    with open(filepath, 'w') as f:
        f.write(src)

    out = ""
    if execute:
        try:
            r   = subprocess.run([sys.executable, filepath], capture_output=True, text=True, timeout=30)
            out = (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired: out = "TIMEOUT"
        except Exception as e:           out = str(e)

    return jsonify({"saved": filename, "executed": execute, "output": out})

@app.route('/api/workspace')
def workspace_list():
    files = []
    for root, dirs, fnames in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d != 'backups']  # skip backups
        for fname in sorted(fnames)[:30]:
            fp = os.path.join(root, fname)
            rel = os.path.relpath(fp, WORKSPACE)
            files.append({"name": rel, "size": os.path.getsize(fp), "mtime": int(os.path.getmtime(fp))})
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify({"files": files[:30], "path": WORKSPACE, "count": len(files)})

# ══════════════════════════════════════════════════════════════════════════════
# BOOT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("\n  ╔═╗  ╔═╗╦═╗╦  ╦╦╔═╗")
    print("  ║ ║  ╠═╣╠╦╝╚╗╔╝║╚═╗")
    print("  ╚═╝  ╩ ╩╩╚═ ╚╝ ╩╚═╝  v2.0 — FULL EDITION\n")
    print(f"  Backend     → http://0.0.0.0:8000")
    print(f"  Workspace   → {WORKSPACE}")
    print(f"  Agents dir  → {AGENTS_DIR}")
    print(f"  Self-path   → {SELF_PATH}\n")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
