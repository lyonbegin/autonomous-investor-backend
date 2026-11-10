"""Spec-driven code generator (not a template tied to paper-case IDs)."""
import hashlib,json
from pathlib import Path
from advanced_runtime import validate_advanced_spec

def generate_advanced(spec, target):
    validate_advanced_spec(spec)
    base=Path(__file__).with_name('advanced_runtime.py').read_text(encoding='utf-8')
    base=base.replace('from __future__ import annotations','')
    canonical=json.dumps(spec,sort_keys=True,ensure_ascii=False)
    generated='''# GENERATED RESEARCH-ONLY STRATEGY. NOT PAPER OR LIVE ENABLED.\nimport json\n'''+base+f'\nSPEC = json.loads({canonical!r})\n'+'''
def run(data):
    return run_advanced(SPEC,data)
if __name__=='__main__':
    import sys
    if len(sys.argv)!=2: raise SystemExit('Usage: python generated_strategy.py input.json')
    with open(sys.argv[1],encoding='utf-8') as f: rows=json.load(f)
    print(json.dumps(run(rows),indent=2,ensure_ascii=False))
'''
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(generated,encoding='utf-8')
    compile(generated,str(target),'exec')
    return {'kind':spec['kind'],'status':'PYTHON_GENERATED_RESEARCH_ONLY',
            'code_sha256':hashlib.sha256(generated.encode()).hexdigest(),
            'spec_sha256':hashlib.sha256(canonical.encode()).hexdigest()}
