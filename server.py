"""
J.A.R.V.I.S. Local Backend — Termux Edition
Proxies to Ollama, serves real hardware stats, manages code workspace.
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess, json, os, time, threading, urllib.request, urllib.error

app = Flask(__name__, static_folder='static')
CORS(app)

OLLAMA_BASE = "http://localhost:11434"
WORKSPACE   = os.path.expanduser("~/jarvis_workspace")
os.makedirs(WORKSPACE, exist_ok=True)

# ── CPU delta tracker ──────────────────────────────────────────────────────────
_last_cpu  = None
_cpu_lock  = threading.Lock()

def _read_proc_cpu():
    with open('/proc/stat') as f:
        vals = list(map(int, f.readline().split()[1:8]))
    return vals[3], sum(vals)          # (idle, total)

def read_cpu():
    global _last_cpu
    try:
        idle, total = _read_proc_cpu()
        with _cpu_lock:
            if _last_cpu is None:
                _last_cpu = (idle, total)
                return 0.0
            p_idle, p_total = _last_cpu
            _last_cpu = (idle, total)
            d_total = total - p_total
            return round((1 - (idle - p_idle) / d_total) * 100, 1) if d_total else 0.0
    except:
        return 0.0

def read_mem():
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                p = line.split()
                if len(p) >= 2:
                    info[p[0].rstrip(':')] = int(p[1])
        total = info.get('MemTotal', 1)
        avail = info.get('MemAvailable', total)
        return round((1 - avail / total) * 100, 1)
    except:
        return 0.0

# ── Ollama helper ──────────────────────────────────────────────────────────────
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

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/health')
def health():
    result, _ = ollama('/api/version', timeout=2)
    return jsonify({"status": "online", "ollama": result or "starting"})

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

    messages = [{"role": m['role'], "content": m['content']} for m in history[-10:]]

    result, err = ollama('/api/chat', {
        "model"  : model,
        "messages": messages,
        "stream" : False,
        "options": {"num_ctx": 2048, "temperature": 0.7}
    }, timeout=180)

    if result:
        return jsonify({
            "response": result.get("message", {}).get("content", ""),
            "model"   : model
        })
    return jsonify({"response": f"[OLLAMA ERROR] {err}", "error": True})

@app.route('/api/system')
def system():
    return jsonify({"cpu": read_cpu(), "ram": read_mem(), "gpu": 0})

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
            r   = subprocess.run(['python3', filepath],
                                 capture_output=True, text=True, timeout=30)
            out = (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            out = "TIMEOUT"
        except Exception as e:
            out = str(e)

    return jsonify({"saved": filename, "executed": execute, "output": out})

@app.route('/api/device')
def device_scan():
    """Full device diagnostic — CPU, RAM, storage, battery, network, processes, temps, uptime."""
    report = {}

    # ── Uptime ──────────────────────────────────────────────
    try:
        with open('/proc/uptime') as f:
            secs = float(f.read().split()[0])
        h, m = divmod(int(secs), 3600); m //= 60
        report['uptime'] = f"{h}h {m}m"
    except: report['uptime'] = 'unknown'

    # ── CPU info ────────────────────────────────────────────
    try:
        cores = 0
        model = 'unknown'
        with open('/proc/cpuinfo') as f:
            for line in f:
                if 'processor' in line: cores += 1
                if 'model name' in line or 'Hardware' in line:
                    model = line.split(':',1)[-1].strip()
        report['cpu'] = {'cores': cores, 'model': model, 'load_pct': read_cpu()}
    except: report['cpu'] = {'load_pct': read_cpu()}

    # ── Memory ──────────────────────────────────────────────
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                p = line.split()
                if len(p) >= 2: info[p[0].rstrip(':')] = int(p[1])
        total_mb = info.get('MemTotal',0) // 1024
        avail_mb = info.get('MemAvailable',0) // 1024
        swap_total = info.get('SwapTotal',0) // 1024
        swap_free  = info.get('SwapFree',0) // 1024
        report['memory'] = {
            'total_mb': total_mb, 'available_mb': avail_mb,
            'used_pct': read_mem(),
            'swap_total_mb': swap_total, 'swap_used_mb': swap_total - swap_free
        }
    except: report['memory'] = {'used_pct': read_mem()}

    # ── Storage ─────────────────────────────────────────────
    try:
        r = subprocess.run(['df','-h','/'],capture_output=True,text=True,timeout=5)
        lines = r.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            report['storage'] = {
                'filesystem': parts[0], 'size': parts[1],
                'used': parts[2], 'avail': parts[3], 'use_pct': parts[4]
            }
        # Termux storage
        termux_home = os.path.expanduser('~')
        r2 = subprocess.run(['df','-h', termux_home], capture_output=True, text=True, timeout=5)
        lines2 = r2.stdout.strip().split('\n')
        if len(lines2) > 1:
            p2 = lines2[1].split()
            report['termux_storage'] = {'size': p2[1], 'used': p2[2], 'avail': p2[3]}
    except: pass

    # ── Battery ─────────────────────────────────────────────
    try:
        bat_paths = ['/sys/class/power_supply/battery', '/sys/class/power_supply/Battery',
                     '/sys/class/power_supply/BAT0', '/sys/class/power_supply/BAT1']
        bat = {}
        for bp in bat_paths:
            if os.path.isdir(bp):
                for key in ['capacity','status','temp','voltage_now','current_now','technology']:
                    fp = os.path.join(bp, key)
                    if os.path.exists(fp):
                        with open(fp) as f: bat[key] = f.read().strip()
                break
        if bat:
            if 'temp' in bat: bat['temp_c'] = round(int(bat.pop('temp')) / 10, 1)
            report['battery'] = bat
        else:
            # Termux API fallback
            r = subprocess.run(['termux-battery-status'], capture_output=True, text=True, timeout=3)
            if r.returncode == 0: report['battery'] = json.loads(r.stdout)
    except: pass

    # ── Network ─────────────────────────────────────────────
    try:
        ifaces = {}
        with open('/proc/net/dev') as f:
            f.readline(); f.readline()
            for line in f:
                p = line.split()
                if len(p) > 9:
                    iname = p[0].rstrip(':')
                    ifaces[iname] = {'rx_mb': round(int(p[1])/1024/1024,2),
                                     'tx_mb': round(int(p[9])/1024/1024,2)}
        report['network'] = ifaces
    except: pass

    # ── Temperatures ────────────────────────────────────────
    try:
        temps = {}
        thermal_dir = '/sys/class/thermal'
        if os.path.isdir(thermal_dir):
            for tz in sorted(os.listdir(thermal_dir))[:8]:
                tp = os.path.join(thermal_dir, tz, 'temp')
                if os.path.exists(tp):
                    with open(tp) as f:
                        val = int(f.read().strip())
                    temps[tz] = round(val / 1000, 1)
        if temps: report['temperatures_c'] = temps
    except: pass

    # ── Top processes ────────────────────────────────────────
    try:
        r = subprocess.run(['ps', '-eo', 'pid,pcpu,pmem,comm', '--sort=-pcpu'],
                           capture_output=True, text=True, timeout=5)
        procs = []
        for line in r.stdout.strip().split('\n')[1:11]:
            p = line.split(None, 3)
            if len(p) >= 4:
                procs.append({'pid': p[0], 'cpu': p[1], 'mem': p[2], 'cmd': p[3]})
        report['top_processes'] = procs
    except: pass

    # ── Android/device props (Termux) ────────────────────────
    try:
        for prop in ['ro.product.model','ro.product.brand','ro.build.version.release']:
            r = subprocess.run(['getprop', prop], capture_output=True, text=True, timeout=2)
            if r.returncode == 0 and r.stdout.strip():
                report.setdefault('android', {})[prop.split('.')[-1]] = r.stdout.strip()
    except: pass

    report['scanned_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(report)

@app.route('/api/workspace')
def workspace_list():
    files = []
    if os.path.exists(WORKSPACE):
        for f in sorted(os.listdir(WORKSPACE))[-20:]:
            fp = os.path.join(WORKSPACE, f)
            files.append({"name": f, "size": os.path.getsize(fp),
                          "mtime": int(os.path.getmtime(fp))})
    return jsonify({"files": files, "path": WORKSPACE, "count": len(files)})

if __name__ == '__main__':
    print(f"\n  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗")
    print(f"     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝")
    print(f"     ██║███████║██████╔╝██║   ██║██║███████╗")
    print(f"██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║")
    print(f"╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║")
    print(f" ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝\n")
    print(f"  Backend → http://0.0.0.0:8000")
    print(f"  Workspace → {WORKSPACE}\n")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
