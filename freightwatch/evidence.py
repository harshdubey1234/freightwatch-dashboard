"""Sparse TF-IDF retrieval followed by deterministic temporal/semantic gates.

Not a general-purpose NLP model. Unsupported temporal wording fails closed.
Source text and every rejection remain inspectable in the audit artifact.
"""
from __future__ import annotations
import csv
import hashlib
import math
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

STOP = set('a an the on in of to and for this that were was is by with from as it its'.split())


def tokens(text):
    return [s for s in re.findall(r'[a-z0-9]+',text.lower()) if s not in STOP]


class VectorIndex:
    """Small, local sparse vector store; cosine retrieval, stable note-id ties."""
    def __init__(self, notes):
        self.notes=notes
        counts=[Counter(tokens(n['applies_to']+' '+n['note'])) for n in notes]
        df=Counter(t for c in counts for t in c)
        self.idf={t:math.log((1+len(notes))/(1+d))+1 for t,d in df.items()}
        self.vectors=[self.vector(c) for c in counts]

    def vector(self, counts):
        v={t:(1+math.log(n))*self.idf[t] for t,n in counts.items() if t in self.idf}
        norm=math.sqrt(sum(x*x for x in v.values())) or 1
        return {t:x/norm for t,x in v.items()}

    def search(self, query):
        q=self.vector(Counter(tokens(query)))
        scored=[(sum(q.get(t,0)*w for t,w in v.items()),n) for n,v in zip(self.notes,self.vectors)]
        return sorted(scored,key=lambda x:(-x[0],x[1]['note_id']))


def parse_window(note):
    """Recognize only explicit source-supported patterns, otherwise abstain."""
    start=date.fromisoformat(note['date'])
    text=note['note'].lower()
    match=re.search(r'from ([a-z]+) (\d{1,2}) to ([a-z]+) (\d{1,2})',text)
    if match:
        months={m:i+1 for i,m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}
        try:
            begin=date(start.year,months[match[1][:3]],int(match[2]))
            end=date(start.year,months[match[3][:3]],int(match[4]))
            if end < begin: end=end.replace(year=end.year+1)
            return begin,end,'explicit date interval'
        except (KeyError,ValueError): return None,None,'unrecognized date interval'
    if 'starting this week' in text:
        # Beginning is known, duration is not. Do not manufacture an expiry.
        return start,None,'open-ended event; starts on note date'
    if re.search(r'festival week|for about a week|this week',text):
        return start,start+timedelta(days=6),'seven days from note date'
    return None,None,'no supported active cost window'


def classify_effect(text):
    text=text.lower()
    blockers=[r'not part of this dataset',r'costs were not',r'without a rate change',
              r'no significant disruptions',r'no major disruptions',r'returned to normal',
              r'improved road conditions',r'costs.*not.*affected',r'no surcharge',
              r'surcharge.*waived',r'no (?:cost|rate|price) increase',r'did not increase']
    if any(re.search(p,text) for p in blockers):
        return False,'explicitly no applicable cost increase'
    if re.search(r'higher (?:trip |transportation )?costs|surcharge|pushing up transportation costs',text):
        return True,'explicit cost-increasing mechanism'
    return False,'no explicit cost-increasing mechanism'


def load_notes(path:Path):
    result=[]; seen=set()
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        required={'note_id','date','applies_to','note'}
        if not required.issubset(reader.fieldnames or []): raise ValueError('Missing note columns')
        for line,n in enumerate(reader,2):
            if None in n or any(not n.get(k) for k in required): raise ValueError(f'Invalid note row {line}')
            n={k:v.strip() for k,v in n.items()}
            date.fromisoformat(n['date'])
            if n['note_id'] in seen: raise ValueError('Duplicate note_id')
            seen.add(n['note_id'])
            begin,end,rule=parse_window(n)
            positive,effect=classify_effect(n['note'])
            magnitude=re.search(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%',n['note'])
            n.update(active_from=begin.isoformat() if begin else None,
                     active_to=end.isoformat() if end else None,window_rule=rule,
                     positive_effect=positive,effect_rule=effect,
                     stated_max_pct=float(magnitude[2]) if magnitude else None,
                     sha256=hashlib.sha256(n['note'].encode()).hexdigest())
            result.append(n)
    return sorted(result,key=lambda n:n['note_id'])


def assess(row,note,policy):
    failures=[]
    week=date.fromisoformat(row['week_of']); end=week+timedelta(days=6)
    if note['applies_to'] not in {row['route'],'All Routes'}: failures.append('wrong route')
    if date.fromisoformat(note['date']) > end: failures.append('note published after week')
    if not note['positive_effect']: failures.append(note['effect_rule'])
    if not note['active_from']:
        failures.append('active cost window is unknown')
    else:
        begin=date.fromisoformat(note['active_from'])
        finish=date.fromisoformat(note['active_to']) if note['active_to'] else date.max
        if end < begin or week > finish:
            failures.append('outside active window')
        elif not any(begin<=date.fromisoformat(day)<=finish for day in row['shipment_days']):
            failures.append('no shipment occurred during active window')
        # Duration is unspecified: conservatively justify only the onset week.
        # Later persistence is possible, but the note alone cannot establish causality.
        if finish==date.max and week > begin-timedelta(days=begin.weekday()):
            failures.append('open-ended note: later-week attribution is unverified')
    if note['stated_max_pct'] is not None:
        excess=row['history_pct']
        if excess is None or excess>note['stated_max_pct']+policy.quantified_tolerance_pp:
            failures.append('observed rise exceeds stated magnitude plus tolerance')
    return failures


def explain(rows,notes,policy):
    index=VectorIndex(notes)
    for r in rows:
        ranked=index.search(r['route']+' freight transportation costs increase fuel toll surcharge flooding')
        evidence=[]
        for score,n in ranked:
            failures=assess(r,n,policy)
            evidence.append(dict(note_id=n['note_id'],score=round(score,6),eligible=not failures,rejections=failures))
        r['retrieved_evidence']=evidence
        eligible=[e for e in evidence if e['eligible']]
        r['matched_note_id']=''
        if not r['candidate']:
            r['flagged']='No';r['verdict']='normal'
            if r['history_baseline'] is None:
                r['reason']='Not flagged: no prior weeks available to establish a cost rise. Peer comparison is diagnostic only; insufficient history.'
            else:
                r['reason']='Not flagged: does not meet the configured rising-cost and anomaly thresholds.'
        elif eligible:
            best=next(n for n in notes if n['note_id']==eligible[0]['note_id'])
            r['matched_note_id']=best['note_id'];r['flagged']='No (justified)';r['verdict']='justified'
            window=best['active_from']+' to '+(best['active_to'] or 'an unspecified end date')
            r['reason']=(f"Justified by applicable cost-increase evidence, not proof of full causality. Note {best['note_id']} "
                         f"dated {best['date']}, applicable {window}: {best['note']} "
                         'At least one shipment overlaps the active window; the note does not allocate the exact weekly cost impact.')
        else:
            r['flagged']='Yes';r['verdict']='unexplained'
            r['reason']='Unexplained: cost is elevated versus prior weeks and breaches an anomaly threshold. No note passed route, time, cost-effect, and magnitude checks. Human review required.'
        if 0<r['history_weeks']<8:
            r['reason']+=f" History uses {r['history_weeks']} available prior week(s), without padding."
        if r['low_sample']:
            r['reason']+=' Low sample: fewer than two shipments; treat the alert cautiously.'
    return rows
