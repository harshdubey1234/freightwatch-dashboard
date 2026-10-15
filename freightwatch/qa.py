"""Grounded Q&A: optional local model translates language into a validated query.

The model never writes the answer, computes money, selects evidence, or changes flags.
"""
import json
import re
import urllib.request
from datetime import date

MONTHS={name.lower():i for i,name in enumerate(
    ['January','February','March','April','May','June','July','August','September','October','November','December'],1)}


def validate_plan(plan,rows):
    if not isinstance(plan,dict) or set(plan)!={'route','month','verdict'}:
        raise ValueError('Query must contain exactly route, month, verdict')
    if plan['route'] is not None and plan['route'] not in {r['route'] for r in rows}:
        raise ValueError('Unknown route; use an exact route from the dataset')
    if plan['verdict'] not in [None,'unexplained','justified','normal']:
        raise ValueError('Unknown verdict')
    if plan['month'] is not None:
        if not isinstance(plan['month'],str) or not re.fullmatch(r'\d{4}-\d{2}',plan['month']):
            raise ValueError('Specify month as YYYY-MM')
        date.fromisoformat(plan['month']+'-01')
    return plan


def parse_query(question,rows):
    q=question.lower()
    matches=[r for r in sorted({r['route'] for r in rows}) if all(c.lower() in q for c in r.split('-'))]
    if len(matches)>1: raise ValueError('Please ask about one route at a time')
    month=None
    iso=re.search(r'\b(\d{4}-\d{2})\b',q)
    if iso: month=iso[1]
    else:
        found=[n for n in MONTHS if re.search(r'\b'+n+r'\b',q)]
        if len(found)>1: raise ValueError('Please ask about one month at a time')
        if found:
            year=re.search(r'\b(20\d{2})\b',q)
            if not year: raise ValueError('Please include the year: the data spans 2024 and 2025')
            month=f'{year[1]}-{MONTHS[found[0]]:02d}'
    if re.search(r'\b20\d{2}\b',q) and not month:
        raise ValueError('Please specify a month as YYYY-MM, or omit the date')
    verdict='unexplained' if re.search(r'\bunexplained\b|\bflagged\b',q) else ('justified' if re.search(r'\bjustified\b',q) else None)
    if not matches and not re.search(r'\ball\b|\bsummary\b|\bflagged\b|\bunexplained\b|\bjustified\b',q):
        raise ValueError('Supported questions name an exact route, or ask for a summary / unexplained / justified routes')
    return validate_plan(dict(route=matches[0] if matches else None,month=month,verdict=verdict),rows)


def model_plan(question,rows,model,usage_path=None):
    """One opt-in Ollama call to localhost; real token counters, no cloud API."""
    routes=sorted({r['route'] for r in rows})
    schema={'type':'object','properties':{
        'route':{'type':['string','null'],'enum':routes+[None]},
        'month':{'type':['string','null'],'description':'YYYY-MM only; null if no month specified'},
        'verdict':{'type':['string','null'],'enum':['unexplained','justified','normal',None]}},
        'required':['route','month','verdict'],'additionalProperties':False}
    payload={'model':model,'stream':False,'format':schema,'options':{'temperature':0,'seed':42},
             'messages':[{'role':'system','content':
                'Translate the question into the JSON filter schema. Never answer it. '+
                'Select only explicit filters. Routes: '+', '.join(routes)+'. Months must include a year.'},
                {'role':'user','content':question}]}
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response: data=json.load(response)
    usage=dict(model=model,llm_calls=1,input_tokens=data.get('prompt_eval_count'),
               output_tokens=data.get('eval_count'),provider_cost_usd=0,
               cost_basis='Local inference: no per-token provider charge; hardware and electricity excluded',temperature=0,seed=42)
    # Log measured usage even if the subsequent model plan fails validation.
    if usage_path is not None:
        with usage_path.open('a',encoding='utf-8') as f: f.write(json.dumps(usage)+'\n')
    plan=validate_plan(json.loads(data['message']['content']),rows)
    # Reject inferred routes and dates not explicitly grounded in the question.
    if plan['route'] and not all(c.lower() in question.lower() for c in plan['route'].split('-')):
        raise ValueError('Model inferred a route not present in the question')
    if plan['month'] and plan['month'][:4] not in question:
        raise ValueError('Please provide an explicit year; model inference rejected')
    if plan['month']:
        number=int(plan['month'][5:])
        month_name=next(k for k,v in MONTHS.items() if v==number)
        if plan['month'] not in question and not re.search(r'\b'+month_name+r'\b',question.lower()):
            raise ValueError('Model inferred a month not present in the question')
    return plan,usage


def answer(rows,plan):
    selected=[r for r in rows if (not plan['route'] or r['route']==plan['route']) and
              (not plan['month'] or r['week_of'].startswith(plan['month'])) and
              (not plan['verdict'] or r['verdict']==plan['verdict'])]
    if not selected: return dict(answer='No matching route-weeks in the computed results.',sources=[])
    abnormal=[r for r in selected if r['candidate']]
    top=sorted(abnormal or selected,key=lambda r:(-r['excess_vs_history_inr'],r['week_of'],r['route']))[:5]
    text=(f"Found {len(selected)} route-weeks: {sum(r['verdict']=='unexplained' for r in selected)} unexplained, "
          f"{sum(r['verdict']=='justified' for r in selected)} justified, and {sum(r['verdict']=='normal' for r in selected)} below thresholds. "
          'Showing up to five rows, ranked by excess cost versus historical rate (not recoverable savings).')
    return dict(answer=text,sources=[{k:r[k] for k in ['route','week_of','cost_per_tonne_km','history_pct','peer_pct','reason','matched_note_id']} for r in top])
