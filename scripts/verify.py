"""Run from the project root: python scripts/verify.py. Standard library only."""
import csv
import hashlib
import json
import random
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date,timedelta
from decimal import Decimal,getcontext
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from freightwatch.engine import Policy,analyze,load_shipments
from freightwatch.evidence import explain,load_notes
from freightwatch.__main__ import run,dump


def reference_check(rows):
    """Independent Decimal implementation; no production aggregation helpers."""
    getcontext().prec=40
    sums=defaultdict(lambda:[Decimal(0),Decimal(0)])
    with (ROOT/'data/shipment_records.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            day=date.fromisoformat(r['shipment_date']);w=(day-timedelta(days=day.weekday())).isoformat()
            k=(r['origin']+'-'+r['destination'],r['route_type'],w)
            sums[k][0]+=Decimal(r['freight_cost_inr'])
            sums[k][1]+=Decimal(r['quantity_tonnes'])*Decimal(r['distance_km'])
    rates={k:a/b for k,(a,b) in sums.items()}
    errors={k:0.0 for k in ['weekly_rate','history_baseline','peer_baseline']}
    for row in rows:
        route,typ,w=row['route'],row['route_type'],row['week_of'];day=date.fromisoformat(w)
        historical=[v for (r,t,d),v in rates.items() if (r,t)==(route,typ) and 0<(day-date.fromisoformat(d)).days<=56]
        peers=[v for (r,t,d),v in rates.items() if r!=route and t==typ and d==w]
        expected=[rates[(route,typ,w)],sum(historical)/len(historical) if historical else None,sum(peers)/len(peers) if peers else None]
        for metric,key,value in zip(errors,['cost_per_tonne_km','history_baseline','peer_baseline'],expected):
            if value is None:assert row[key] is None
            else:errors[metric]=max(errors[metric],abs(float(value)-row[key]))
    assert max(errors.values())<1e-10,errors
    return dict(rows_checked=len(rows),max_absolute_errors=errors,tolerance=1e-10)


def main():
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/test_results.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:print(result.stderr);raise SystemExit(result.returncode)
    data=ROOT/'data';policy=Policy();rows=explain(analyze(load_shipments(data/'shipment_records.csv'),policy),load_notes(data/'context_notes.csv'),policy)
    reference=reference_check(rows)
    cases=[]
    with (ROOT/'tests/golden_cases.csv').open(newline='') as f:
        for c in csv.DictReader(f):
            row=next(r for r in rows if (r['route'],r['week_of'])==(c['route'],c['week_of']))
            ok=(row['verdict'],row['matched_note_id'])==(c['verdict'],c['note_id'])
            cases.append(dict(**c,passed=ok,actual_verdict=row['verdict'],actual_note_id=row['matched_note_id']))
    assert all(c['passed'] for c in cases),cases
    # Fresh processes, not cached in-process calls.
    hashes=[]
    with tempfile.TemporaryDirectory() as temp:
        for i in range(3):
            out=Path(temp)/str(i)
            subprocess.run([sys.executable,'-m','freightwatch','run','--data',str(data),'--out',str(out)],cwd=ROOT,check=True,capture_output=True)
            hashes.append({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())})
        assert hashes[0]==hashes[1]==hashes[2]
        # Input-order metamorphic test.
        shuffled=Path(temp)/'shuffled';shuffled.mkdir()
        for name in ['shipment_records.csv','context_notes.csv']:
            with (data/name).open(newline='') as f:r=list(csv.reader(f))
            header=r.pop(0);random.Random(42).shuffle(r)
            with (shuffled/name).open('w',newline='') as f:w=csv.writer(f);w.writerow(header);w.writerows(r)
        (shuffled/'sample_output_format_v2.csv').write_bytes((data/'sample_output_format_v2.csv').read_bytes())
        run(shuffled,Path(temp)/'shuffle-output',policy)
        assert hashlib.sha256((Path(temp)/'shuffle-output/output.csv').read_bytes()).hexdigest()==hashes[0]['output.csv']
    # Verify no look-ahead: truncating the dataset cannot change earlier results.
    cutoff='2025-03-31'
    short=[r for r in load_shipments(data/'shipment_records.csv') if r['shipment_date']<cutoff]
    past=explain(analyze(short,policy),load_notes(data/'context_notes.csv'),policy)
    assert past==[r for r in rows if r['week_of']<cutoff]
    sensitivity=[]
    for hist,peer,floor in [(10,15,3),(15,20,5),(20,25,7)]:
        p=Policy(hist,peer,floor);rr=explain(analyze(load_shipments(data/'shipment_records.csv'),p),load_notes(data/'context_notes.csv'),p)
        sensitivity.append(dict(history_threshold=hist,peer_threshold=peer,rising_floor=floor,
                               unexplained=sum(r['verdict']=='unexplained' for r in rr),justified=sum(r['verdict']=='justified' for r in rr)))
    report=dict(numerical_reference=reference,golden_cases=cases,golden_passed=sum(c['passed'] for c in cases),
                golden_total=len(cases),limitations='Small hand-authored regression set, not independent production accuracy or a held-out benchmark.',
                input_order_invariant=True,no_lookahead_prefix_invariant=True,sensitivity=sensitivity)
    dump(ROOT/'results/evaluation.json',report)
    dump(ROOT/'results/reproducibility.json',dict(runs=hashes,identical=True,method='Three independent Python subprocesses; SHA-256 of every generated artifact.'))
    print(result.stderr.splitlines()[-3:]);print(json.dumps(report,indent=2));print('Three fresh runs: byte-identical.')


if __name__=='__main__':main()
