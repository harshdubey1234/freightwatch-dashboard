import csv
import json
import math
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from dataclasses import replace
from datetime import date,timedelta
from pathlib import Path

from freightwatch.engine import Policy,analyze,load_shipments,monday,OUTPUT_COLUMNS,export_csv
from freightwatch.evidence import load_notes,assess,explain,VectorIndex,parse_window,classify_effect
from freightwatch.qa import parse_query,validate_plan,answer,model_plan

ROOT=Path(__file__).resolve().parents[1]


def shipment(day,rate=1,origin='A',destination='B',kind='Short',tonne_km=100):
    d=date.fromisoformat(day)
    return dict(origin=origin,destination=destination,route_type=kind,date=d,week=monday(d),
                tonne_km=tonne_km,freight_cost_inr=rate*tonne_km)


class CoreTests(unittest.TestCase):
    def test_week_boundaries(self):
        self.assertEqual(monday(date(2025,1,5)),date(2024,12,30))
        self.assertEqual(monday(date(2025,1,6)),date(2025,1,6))

    def test_ratio_of_sums_not_mean_of_ratios(self):
        r=analyze([shipment('2025-01-06',1,tonne_km=100),shipment('2025-01-07',3,tonne_km=300)],Policy())[0]
        self.assertEqual(r['cost_per_tonne_km'],2.5)

    def test_history_excludes_current_and_future(self):
        rows=analyze([shipment('2025-01-06',1),shipment('2025-01-13',2),shipment('2025-01-20',1000)],Policy())
        self.assertEqual(rows[1]['history_baseline'],1)

    def test_exact_eight_calendar_weeks(self):
        start=date(2025,1,6)
        rows=analyze([shipment((start+timedelta(weeks=i)).isoformat(),i+1) for i in range(10)],Policy())
        self.assertEqual(rows[-1]['history_baseline'],5.5) # weeks with rates 2..9
        self.assertEqual(rows[-1]['history_weeks'],8)

    def test_missing_weeks_not_padded_or_replaced_by_old_observations(self):
        rows=analyze([shipment('2024-01-01',100),shipment('2025-01-06',2),shipment('2025-01-20',3)],Policy())
        self.assertEqual(rows[-1]['history_baseline'],2)
        self.assertEqual(rows[-1]['history_weeks'],1)

    def test_history_mean_of_weekly_rates_not_reweighted(self):
        rows=analyze([shipment('2025-01-06',1,tonne_km=100),shipment('2025-01-13',3,tonne_km=300),shipment('2025-01-20',4)],Policy())
        self.assertEqual(rows[-1]['history_baseline'],2)

    def test_peer_excludes_self_and_other_types(self):
        rows=analyze([shipment('2025-01-06',2),shipment('2025-01-06',4,origin='C'),shipment('2025-01-06',100,origin='D',kind='Long')],Policy())
        row=next(r for r in rows if r['route']=='A-B')
        self.assertEqual(row['peer_baseline'],4);self.assertEqual(row['peer_count'],1)

    def test_peer_equal_route_weights(self):
        rows=analyze([shipment('2025-01-06',1),shipment('2025-01-06',2,origin='C',tonne_km=100),shipment('2025-01-06',4,origin='D',tonne_km=900)],Policy())
        self.assertEqual(rows[0]['peer_baseline'],3)

    def test_direction_preserved(self):
        rows=analyze([shipment('2025-01-06'),shipment('2025-01-06',origin='B',destination='A')],Policy())
        self.assertEqual(len(rows),2)

    def test_route_type_is_part_of_key(self):
        rows=analyze([shipment('2025-01-06'),shipment('2025-01-06',kind='Long')],Policy())
        self.assertEqual(len(rows),2)

    def test_no_history_or_peers_does_not_invent_baseline(self):
        r=analyze([shipment('2025-01-06')],Policy())[0]
        self.assertIsNone(r['history_pct']);self.assertIsNone(r['peer_pct']);self.assertFalse(r['candidate'])

    def test_static_expensive_route_is_not_rising(self):
        rows=analyze([shipment('2025-01-06',10),shipment('2025-01-13',10),shipment('2025-01-13',1,origin='C')],Policy())
        r=next(r for r in rows if r['route']=='A-B' and r['week_of']=='2025-01-13')
        self.assertGreater(r['peer_pct'],20);self.assertFalse(r['candidate'])

    def test_history_or_peer_trigger(self):
        for current,peer in [(1.3,1.3),(1.1,.8)]:
            rows=analyze([shipment('2025-01-06',1),shipment('2025-01-13',current),shipment('2025-01-13',peer,origin='C')],Policy())
            self.assertTrue(next(r for r in rows if r['route']=='A-B' and r['week_of']=='2025-01-13')['candidate'])

    def test_low_sample_stays_visible(self):
        self.assertTrue(analyze([shipment('2025-01-06')],Policy())[0]['low_sample'])

    def test_invalid_policy(self):
        for val in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):Policy(history_threshold_pct=val)


class InputTests(unittest.TestCase):
    def mutate(self,key,value,duplicate=False):
        with (ROOT/'data/shipment_records.csv').open(newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;r=next(reader)
        r[key]=value
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.csv'
            with p.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(r)
                if duplicate:w.writerow(r)
            return load_shipments(p)

    def test_invalid_denominators_and_nonfinite_values(self):
        for key in ['quantity_tonnes','distance_km','freight_cost_inr']:
            for value in ['0','-1','nan','inf','']:
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.mutate(key,value)

    def test_duplicate_shipment(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):self.mutate('shipment_id','same',True)

    def test_bad_date(self):
        with self.assertRaises(ValueError):self.mutate('shipment_date','2025-02-30')

    def test_bad_type(self):
        with self.assertRaises(ValueError):self.mutate('route_type','Tiny')


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.notes=load_notes(ROOT/'data/context_notes.csv')

    def row(self,route='Chennai-Bangalore',week='2025-02-24',days=None,rise=30):
        return dict(route=route,week_of=week,shipment_days=days or [week],history_pct=rise)

    def note(self,n):return next(x for x in self.notes if x['note_id']==n)

    def test_flood_window_exact(self):
        n=self.note('N001');self.assertEqual(n['active_from'],'2025-02-24');self.assertEqual(n['active_to'],'2025-03-08')

    def test_valid_flood_evidence(self):
        self.assertEqual(assess(self.row(),self.note('N001'),Policy()),[])

    def test_after_flood_is_rejected(self):
        self.assertIn('outside active window',assess(self.row(week='2025-03-10'),self.note('N001'),Policy()))

    def test_overlap_requires_actual_affected_shipment(self):
        self.assertIn('no shipment occurred during active window',assess(self.row(week='2025-03-03',days=['2025-03-09']),self.note('N001'),Policy()))

    def test_wrong_route_rejected(self):
        self.assertIn('wrong route',assess(self.row(route='Mumbai-Pune'),self.note('N001'),Policy()))

    def test_future_note_rejected(self):
        self.assertIn('note published after week',assess(self.row(week='2025-02-17'),self.note('N001'),Policy()))

    def test_every_decoy_rejected(self):
        for n in self.notes:
            if n['note_id'] in ['N001','N002','N003']:continue
            self.assertFalse(n['positive_effect'],n['note_id'])

    def test_small_diesel_rise_cannot_explain_large_spike(self):
        r=self.row(route='Mumbai-Pune',week='2025-05-05',rise=30)
        self.assertIn('observed rise exceeds stated magnitude plus tolerance',assess(r,self.note('N003'),Policy()))

    def test_diesel_onset_can_explain_magnitude_consistent_rise(self):
        self.assertEqual(assess(self.row(week='2025-05-05',rise=6),self.note('N003'),Policy()),[])

    def test_unknown_end_does_not_authorize_months_of_justification(self):
        self.assertIn('open-ended note: later-week attribution is unverified',assess(self.row(week='2025-06-23',rise=6),self.note('N003'),Policy()))

    def test_festival_expires(self):
        self.assertIn('outside active window',assess(self.row(route='Ahmedabad-Mumbai',week='2025-01-27'),self.note('N002'),Policy()))

    def test_unsupported_temporal_phrase_abstains(self):
        self.assertIsNone(parse_window(dict(date='2025-01-01',note='Costs increased sometime recently.'))[0])

    def test_unknown_positive_wording_abstains(self):
        self.assertFalse(classify_effect('A toll was discussed at a meeting.')[0])

    def test_negated_surcharge_is_not_positive(self):
        self.assertFalse(classify_effect('No surcharge applied this week.')[0])
        self.assertFalse(classify_effect('The festival surcharge was waived.')[0])

    def test_retrieval_stable_and_route_relevant(self):
        index=VectorIndex(self.notes)
        a=index.search('Chennai Bangalore flooding higher trip costs')
        self.assertEqual(a,index.search('Chennai Bangalore flooding higher trip costs'))
        self.assertEqual(a[0][1]['note_id'],'N001')

    def test_empty_notes_cannot_justify(self):
        rows=analyze([shipment('2025-01-06',1),shipment('2025-01-13',1.3)],Policy())
        result=explain(rows,[],Policy())[-1]
        self.assertEqual(result['verdict'],'unexplained');self.assertEqual(result['matched_note_id'],'')


class QATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=explain(analyze(load_shipments(ROOT/'data/shipment_records.csv'),Policy()),load_notes(ROOT/'data/context_notes.csv'),Policy())

    def test_march_requires_year(self):
        with self.assertRaisesRegex(ValueError,'year'):parse_query('Why Chennai-Bangalore in March?',self.rows)

    def test_plain_english_query(self):
        plan=parse_query('Why did Chennai-Bangalore get pricier in March 2025?',self.rows)
        result=answer(self.rows,plan)
        self.assertTrue(result['sources']);self.assertTrue(all(r['week_of'].startswith('2025-03') for r in result['sources']))

    def test_invalid_model_route_rejected(self):
        with self.assertRaises(ValueError):validate_plan(dict(route='Paris-London',month=None,verdict=None),self.rows)

    def test_extra_model_fields_rejected(self):
        with self.assertRaises(ValueError):validate_plan(dict(route=None,month=None,verdict=None,answer='made up'),self.rows)

    def test_out_of_domain_abstention(self):
        with self.assertRaises(ValueError):parse_query('What is the capital of France?',self.rows)

    def test_empty_result_not_fabricated(self):
        result=answer(self.rows,dict(route=None,month='2030-01',verdict=None))
        self.assertEqual(result['sources'],[])

    def model_response(self,plan):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(dict(message=dict(content=json.dumps(plan)),prompt_eval_count=50,eval_count=20)).encode()
        return response

    def test_local_model_adapter_and_measured_usage(self):
        plan=dict(route='Chennai-Bangalore',month='2025-03',verdict=None)
        with patch('urllib.request.urlopen',return_value=self.model_response(plan)) as call:
            actual,usage=model_plan('Why Chennai-Bangalore in March 2025?',self.rows,'test-model')
        self.assertEqual(actual,plan);self.assertEqual(usage['input_tokens'],50)
        self.assertEqual(call.call_args[0][0].full_url,'http://127.0.0.1:11434/api/chat')

    def test_model_cannot_invent_month(self):
        plan=dict(route='Chennai-Bangalore',month='2025-04',verdict=None)
        with patch('urllib.request.urlopen',return_value=self.model_response(plan)),self.assertRaisesRegex(ValueError,'month'):
            model_plan('Why Chennai-Bangalore in March 2025?',self.rows,'test-model')

    def test_rejected_model_plan_still_logs_tokens(self):
        plan=dict(route='Paris-London',month=None,verdict=None)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'usage.jsonl'
            with patch('urllib.request.urlopen',return_value=self.model_response(plan)),self.assertRaises(ValueError):
                model_plan('Why Paris-London?',self.rows,'test-model',p)
            self.assertEqual(json.loads(p.read_text())['output_tokens'],20)


if __name__=='__main__':unittest.main()
