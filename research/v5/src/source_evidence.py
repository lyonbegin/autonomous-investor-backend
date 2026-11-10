"""Auditable static Pine call-site finder. Not an AST, compiler or parity engine.

Multi-line call arguments and comment/string masking preserve exact line references.
Any unsupported semantic question is flagged, not guessed.
"""
from __future__ import annotations
import hashlib,re

CALL_NAMES=('strategy.entry','strategy.exit','strategy.order','strategy.close','strategy.close_all',
    'strategy.cancel','strategy.cancel_all','strategy.risk.', 'request.security',
    'request.security_lower_tf','request.earnings','request.dividends','request.financial',
    'request.splits','ta.ema','ta.sma','ta.rsi','ta.crossover','ta.crossunder',
    'ta.pivothigh','ta.pivotlow','alertcondition','strategy')

# Ensure nested full name ordering for a deterministic tokenizer.
CALL_RE=re.compile(r'(?<![\w.])('+'|'.join(re.escape(s) for s in sorted(CALL_NAMES,key=len,reverse=True))+r')\s*\(',re.I)
IMP_RE=re.compile(r'^\s*import\s+([\w./-]+)',re.M)


def sanitize(source):
    result=[];i=0;n=len(source);in_block=False;quote=None
    while i<n:
        ch=source[i];pair=source[i:i+2]
        if in_block:
            if pair=='*/':result.extend('  ');i+=2;in_block=False;continue
            result.append('\n' if ch=='\n' else ' ');i+=1;continue
        if quote:
            if ch=='\\' and i+1<n:result.extend('  ');i+=2;continue
            if ch==quote:quote=None
            result.append('\n' if ch=='\n' else ' ');i+=1;continue
        if pair=='/*':in_block=True;result.extend('  ');i+=2;continue
        if pair=='//':
            j=source.find('\n',i)
            if j<0:j=n
            result.extend(' '*(j-i));i=j;continue
        if ch in ('"',"'"):quote=ch;result.append(' ');i+=1;continue
        result.append(ch);i+=1
    return ''.join(result)


def analyze_pine(source):
    mask=sanitize(source)
    line_starts=[0]+[i+1 for i,x in enumerate(source) if x=='\n']
    def ln(offset):
        import bisect
        return bisect.bisect_right(line_starts,offset)
    calls=[]
    for m in CALL_RE.finditer(mask):
        start=m.end()-1;depth=1;pos=start+1
        while pos<len(mask) and depth>0:
            if mask[pos]=='(':depth+=1
            elif mask[pos]==')':depth-=1
            pos+=1
        if depth:
            calls.append({'callee':m.group(1),'start_line':ln(m.start()),'status':'UNBALANCED_CALL',
                          'excerpt':source[m.start():m.start()+160]});continue
        raw=source[m.start():pos]
        calls.append({'callee':m.group(1),'start_line':ln(m.start()),'end_line':ln(pos-1),
                      'source_expression':raw[:4000], 'truncated':len(raw)>4000,
                      'status':'STATIC_CALL_FOUND'})
    imports=[{'name':x.group(1),'line':ln(x.start())} for x in IMP_RE.finditer(mask)]
    orders=[c for c in calls if c['callee'].startswith('strategy.') and c['callee']!='strategy.risk.']
    external=[c for c in calls if c['callee'].startswith('request.')]
    other_symbols=[]
    for call in external:
        if call['callee'].lower() in ('request.security','request.security_lower_tf'):
            arg=call['source_expression']
            other_symbols.append({'line':call['start_line'],
                'chart_ticker_referenced':'syminfo.tickerid' in arg,
                'explicit_symbol_in_same_expression':bool(re.search(r'(?:ticker\.new\s*\(|["\'](?:[A-Z]+:)?[A-Z]{3,12}["\'])',arg))})
    init=next((x for x in calls if x['callee'].lower()=='strategy'),None)
    return {'status':'SOURCE_STATIC_ANALYSIS_EXECUTED_NOT_PINE_AST',
            'source_sha256_utf8':hashlib.sha256(source.encode('utf-8')).hexdigest(),
            'line_count':len(source.splitlines()), 'call_count':len(calls),'calls':calls,
            'order_calls':orders,'external_data_calls':external, 'imports':imports,
            'strategy_declaration':init, 'other_symbol_use':other_symbols,
            'direct_multileg_order_verified':False,
            'limitations':['STATIC_CALL_EXTRACTION_ONLY','NO_CONTROL_FLOW_OR_TYPE_PROOF','NO_PINE_PYTHON_PARITY_VERIFIED',
                           'MULTILINE_EXPRESSIONS_ARE_CAPTURED_BUT_NOT_FULLY_EVALUATED']}
