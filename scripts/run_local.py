"""Start the workbench and two fictional source APIs with one command."""
import signal, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def stop(signum,frame):raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,stop)
processes=[];exit_code=0
try:
    for module,port in [('app.mock_provider:app','8001'),('app.main:app','8000')]:
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn',module,'--host','127.0.0.1','--port',port],cwd=ROOT))
    print('\nWorkbench: http://127.0.0.1:8000 | Fictional sources: http://127.0.0.1:8001/docs\nUse Source automation in the workbench. Ctrl+C stops both services.\n',flush=True)
    while all(p.poll() is None for p in processes):time.sleep(.5)
    exit_code=1
except KeyboardInterrupt:pass
finally:
    for p in processes:
        if p.poll() is None:p.terminate()
    for p in processes:
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()

sys.exit(exit_code)
