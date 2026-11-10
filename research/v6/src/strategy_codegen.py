"""Spec->fully self-contained Python (stdlib); input-independent strategy family support."""
from __future__ import annotations
import json
from pathlib import Path
from strategy_runtime import validate_spec

# Generated source is portable, includes its runtime, and is not case-specific handwritten code.
RUNTIME=Path(__file__).with_name('strategy_runtime.py')

def generate(spec:dict, target:Path)->dict:
    validate_spec(spec)
    import hashlib
    spec_text=json.dumps(spec,sort_keys=True,ensure_ascii=False)
    core=RUNTIME.read_text(encoding='utf-8')
    code='''# Auto-generated from independently reviewed strategy_spec.json.
# NOT live trading and NOT verified historical performance.
import json
'''+core.replace('from __future__ import annotations','')+f'\nSPEC = json.loads({spec_text!r})\n'+'''
def run(rows=None):
    if SPEC['kind'] == 'worked_transaction': return worked_transaction(SPEC)
    if rows is None: raise InvalidSpec('Research simulation needs independently supplied series')
    if SPEC['kind'] == 'seasonal_futures_spread': return seasonal_spread(SPEC, rows)
    if SPEC['kind'] == 'earnings_decile_long_short': return earnings_decile_long_short(SPEC, rows)
    raise InvalidSpec('Unexpected kind')
if __name__ == '__main__':
    import sys
    bars=json.load(open(sys.argv[1],encoding='utf-8')) if len(sys.argv)>1 else None
    print(json.dumps(run(bars),ensure_ascii=False,indent=2))
'''
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(code,encoding='utf-8')
    compile(code,str(target),'exec')
    return {'status':'PYTHON_GENERATED','code_sha256':hashlib.sha256(code.encode('utf-8')).hexdigest(),'code_bytes':len(code),
            'spec_sha256':hashlib.sha256(spec_text.encode('utf-8')).hexdigest(),'kind':spec['kind']}
