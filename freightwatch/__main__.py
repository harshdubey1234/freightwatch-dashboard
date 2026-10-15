import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .engine import Policy, analyze, export_csv, load_shipments
from .evidence import explain,load_notes


def dump(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def run(data,out,policy):
    shipments=load_shipments(data/'shipment_records.csv')
    notes=load_notes(data/'context_notes.csv')
    rows=explain(analyze(shipments,policy),notes,policy)
    out.mkdir(parents=True,exist_ok=True)
    export_csv(rows,out/'output.csv',data/'sample_output_format_v2.csv')
    summary=dict(shipments=len(shipments),route_weeks=len(rows),routes=len({r['route'] for r in rows}),
                 verdicts=dict(sorted(Counter(r['verdict'] for r in rows).items())),
                 first_week=rows[0]['week_of'],last_week=rows[-1]['week_of'],
                 unexplained_excess_inr=sum(r['excess_vs_history_inr'] for r in rows if r['verdict']=='unexplained'))
    payload=dict(summary=summary,policy=asdict(policy),rows=rows,notes=notes)
    dump(out/'audit.json',payload)
    dump(out/'cost_log.json',dict(mode='offline sparse TF-IDF retrieval + deterministic explanations',
         llm_calls=0,input_tokens=0,output_tokens=0,provider_cost_usd=0,model=None,
         rate_source='Not applicable: no hosted or local language model is invoked in a full batch run',
         caveat='Zero API spend, not zero compute cost. Local hardware/electricity excluded.',
         shipment_records=len(shipments),route_weeks=len(rows)))
    from .dashboard import render
    (out/'dashboard.html').write_text(render(payload),encoding='utf-8')
    manifest=dict(version='1.0.0',policy=asdict(policy),input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(data.glob('*.csv'))},
                  outputs={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['output.csv','audit.json','cost_log.json','dashboard.html']})
    dump(out/'manifest.json',manifest)
    return summary


def main():
    parser=argparse.ArgumentParser(description='FreightWatch: auditable freight cost monitoring')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run');p.add_argument('--data',type=Path,default=Path('data'));p.add_argument('--out',type=Path,default=Path('results'))
    p.add_argument('--history-threshold',type=float,default=15);p.add_argument('--peer-threshold',type=float,default=20);p.add_argument('--rising-floor',type=float,default=5)
    q=sub.add_parser('ask');q.add_argument('question');q.add_argument('--results',type=Path,default=Path('results'))
    q.add_argument('--model',help='Optional installed Ollama model name; one local query-planning call')
    args=parser.parse_args()
    try:
        if args.command=='run':
            print(json.dumps(run(args.data,args.out,Policy(args.history_threshold,args.peer_threshold,args.rising_floor)),indent=2))
        else:
            from .qa import parse_query,model_plan,answer
            rows=json.loads((args.results/'audit.json').read_text(encoding='utf-8'))['rows']
            if args.model:
                plan,usage=model_plan(args.question,rows,args.model,args.results/'qa_usage.jsonl')
            else: plan=parse_query(args.question,rows)
            print(json.dumps(dict(query=plan,**answer(rows,plan)),indent=2,ensure_ascii=False))
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,f'Error: {exc}\n')


if __name__=='__main__':main()
