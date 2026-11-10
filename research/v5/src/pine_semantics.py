"""Conservative Pine static feature extraction. NOT a Pine AST or execution-equivalence proof."""
from __future__ import annotations
import re, hashlib

DECL = re.compile(r'\b(indicator|strategy|library)\s*\(', re.I)
CALLS = {
    'entry':r'\bstrategy\.entry\s*\(', 'exit':r'\bstrategy\.exit\s*\(',
    'order':r'\bstrategy\.order\s*\(', 'close':r'\bstrategy\.close(?:_all)?\s*\(',
    'risk':r'\bstrategy\.risk\.', 'security':r'\brequest\.security(?:_lower_tf)?\s*\(',
    'input':r'\binput(?:\.[a-z_]+)?\s*\(', 'import':r'^\s*import\s+',
    'alert':r'\balertcondition\s*\(', 'var':r'\bvar(?:ip)?\s+',
    'array':r'\barray\.', 'plot':r'\bplot(?:shape|char|bar|candle)?\s*\(',
}

def analyze(text:str)->dict:
    # Mask // comments and quoted strings to avoid false positives, preserving line count.
    lines=text.splitlines()
    evidence=[]
    in_block=False
    sanitized=[]
    for number,line in enumerate(lines,1):
        result=[]; i=0; in_str=None
        while i<len(line):
            ch=line[i]; nex=line[i:i+2]
            if in_block:
                if nex=='*/': in_block=False; result.extend('  ');i+=2
                else: result.append(' ');i+=1
                continue
            if in_str:
                if ch=='\\' and i+1<len(line): result.extend('  ');i+=2
                elif ch==in_str: in_str=None; result.append(' ');i+=1
                else:result.append(' ');i+=1
                continue
            if nex=='/*':in_block=True;result.extend('  ');i+=2;continue
            if nex=='//':result.extend(' '*(len(line)-i));break
            if ch in ('"',"'"):in_str=ch;result.append(' ');i+=1;continue
            result.append(ch);i+=1
        sanitized.append(''.join(result))
    full='\n'.join(sanitized)
    m=re.search(r'(?m)^\s*//\s*@version\s*=\s*(\d+)',text)
    declaration=DECL.search(full)
    for tag,pat in CALLS.items():
        for i,line in enumerate(sanitized,1):
            if re.search(pat,line,re.I | (re.M if tag=='import' else 0)):
                evidence.append({'category':tag,'line':i,'code':lines[i-1].strip()[:240]})
    # Security symbol is inferred only if simple known symbols occur in the same call line.
    security=[{'line':x['line'],'tickerid_same_line':bool(re.search(r'\bsyminfo\.tickerid\b',x['code']))}
              for x in evidence if x['category']=='security']
    warnings=['STATIC_HEURISTIC_ONLY_NO_PINE_AST_OR_RUNTIME_EQUIVALENCE']
    if 'request.security' in full: warnings.append('VERIFY_MTF_LOOKAHEAD_AND_REPAINTING')
    if 'strategy.' in full: warnings.append('VERIFY_PINE_BROKER_EMULATOR_SEMANTICS')
    return {
        'status':'PARTIAL_STATIC_ANALYSIS', 'sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'lines':len(lines),'version':int(m.group(1)) if m else None,
        'declaration':declaration.group(1).lower() if declaration else None,
        'features':evidence,'security':security,
        'actual_strategy_orders_detected': any(x['category'] in ('entry','order') for x in evidence),
        'warnings':warnings,
    }
