#!/usr/bin/env python3
"""Probe exact PYNE CLI behavior in an isolated GH-hosted venv; do not edit production."""
import json
from pathlib import Path
import subprocess
import tempfile

out=[]
def do(args,cwd=None):
    try:
        p=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=25)
        r={"cmd":args,"code":p.returncode,"stdout":p.stdout[-1800:],"stderr":p.stderr[-2800:]}
    except Exception as e:
        r={"cmd":args,"error":type(e).__name__+":"+str(e)}
    out.append(r)
    print(json.dumps(r,ensure_ascii=False),flush=True)
with tempfile.TemporaryDirectory(prefix="wf02-cli-probe-") as temp:
    root=Path(temp)
    pine='//@version=6\nstrategy("tiny")\nplot(close)\n'
    (root/'strategy.pine').write_text(pine,encoding="utf-8")
    (root/'strategy.pyne').write_text(pine,encoding="utf-8")
    do(["pyne","compile","--help"],temp)
    do(["pyne","check",str(root/'strategy.pine')],temp)
    do(["pyne","compile",str(root/'strategy.pine'),"--emit","-o",str(root/'out.py')],temp)
    do(["pyne","compile",str(root/'strategy.pyne'),"--emit"],temp)
    do(["pyne","compile",str(root/'strategy.pyne')],temp)
    for item in ["out.py","strategy.py"]:
        p=root/item
        if p.is_file():
            out.append({"generated_path":item,"bytes":p.stat().st_size,
                        "head":p.read_text(errors="replace")[:350]})
Path("wf02_isolated_cli_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
