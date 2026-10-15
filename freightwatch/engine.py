"""Numerical core. Full precision internally; rounding only at export."""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

OUTPUT_COLUMNS = ['route', 'week_of', 'cost_per_tonne_km', 'vs_own_history',
                  'vs_similar_routes', 'flagged', 'matched_note_id', 'reason']
REQUIRED = {'shipment_id', 'origin', 'destination', 'route_type', 'quantity_tonnes',
            'distance_km', 'freight_cost_inr', 'shipment_date'}


@dataclass(frozen=True)
class Policy:
    history_threshold_pct: float = 15.0
    peer_threshold_pct: float = 20.0
    rising_floor_pct: float = 5.0
    quantified_tolerance_pp: float = 2.0
    min_shipments: int = 2

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{name} must be finite and nonnegative')
        if self.min_shipments < 1:
            raise ValueError('min_shipments must be positive')


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def load_shipments(path: Path) -> list[dict]:
    """Fail closed, with row numbers; never silently drop bad denominators."""
    rows, seen = [], set()
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f'Missing shipment columns: {sorted(REQUIRED-set(reader.fieldnames or []))}')
        for line, raw in enumerate(reader, 2):
            try:
                if None in raw or any(raw[k] is None for k in REQUIRED):
                    raise ValueError('malformed CSV record')
                r = {k: v.strip() for k, v in raw.items()}
                if any(not r[k] for k in REQUIRED):
                    raise ValueError('blank required field')
                if r['shipment_id'] in seen:
                    raise ValueError('duplicate shipment_id')
                if r['route_type'] not in {'Short', 'Medium', 'Long'}:
                    raise ValueError('route_type must be Short, Medium, or Long')
                for name in ['quantity_tonnes', 'distance_km', 'freight_cost_inr']:
                    value = float(r[name])
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError(f'{name} must be positive and finite')
                    r[name] = value
                r['date'] = date.fromisoformat(r['shipment_date'])
                r['week'] = monday(r['date'])
                r['route'] = r['origin'] + '-' + r['destination']
                r['tonne_km'] = r['quantity_tonnes'] * r['distance_km']
                if not math.isfinite(r['tonne_km']):
                    raise ValueError('tonne-km overflow')
                seen.add(r['shipment_id'])
                rows.append(r)
            except (ValueError, TypeError) as exc:
                raise ValueError(f'{path.name}, row {line}: {exc}') from exc
    if not rows:
        raise ValueError('Shipment input is empty')
    # Stable ordering makes input shuffles immaterial to floating-point summation.
    return sorted(rows, key=lambda r: r['shipment_id'])


def percent(current: float, baseline: float | None) -> float | None:
    return 100 * (current / baseline - 1) if baseline else None


def analyze(shipments: list[dict], policy: Policy) -> list[dict]:
    groups = defaultdict(list)
    for row in shipments:
        groups[(row['origin'], row['destination'], row['route_type'], row['week'])].append(row)
    weeks = []
    by_route, peers = defaultdict(list), defaultdict(list)
    for (origin, destination, kind, week), items in sorted(groups.items()):
        tonnes_km = math.fsum(x['tonne_km'] for x in items)
        cost = math.fsum(x['freight_cost_inr'] for x in items)
        row = dict(route=origin+'-'+destination, origin=origin, destination=destination,
                   route_type=kind, week_of=week.isoformat(), cost_per_tonne_km=cost/tonnes_km,
                   total_cost_inr=cost, tonne_km=tonnes_km, shipment_count=len(items),
                   shipment_days=sorted({x['date'].isoformat() for x in items}))
        weeks.append(row)
        by_route[(origin,destination,kind)].append(row)
        peers[(kind,week)].append(row)
    for r in weeks:
        week = date.fromisoformat(r['week_of'])
        prior = [p for p in by_route[(r['origin'],r['destination'],r['route_type'])]
                 if week-timedelta(weeks=8) <= date.fromisoformat(p['week_of']) < week]
        others = [p for p in peers[(r['route_type'],week)]
                  if (p['origin'],p['destination']) != (r['origin'],r['destination'])]
        history = math.fsum(p['cost_per_tonne_km'] for p in prior)/len(prior) if prior else None
        peer = math.fsum(p['cost_per_tonne_km'] for p in others)/len(others) if others else None
        own_pct, peer_pct = percent(r['cost_per_tonne_km'],history), percent(r['cost_per_tonne_km'],peer)
        # Rising is relative to history, allowing persistent elevation without a new weekly jump.
        rising = own_pct is not None and own_pct >= policy.rising_floor_pct
        history_breach = own_pct is not None and own_pct >= policy.history_threshold_pct
        peer_breach = peer_pct is not None and peer_pct >= policy.peer_threshold_pct
        candidate = rising and (history_breach or peer_breach)
        triggers = []
        if history_breach: triggers.append('history')
        if peer_breach: triggers.append('peers')
        r.update(history_baseline=history, peer_baseline=peer, history_pct=own_pct,
                 peer_pct=peer_pct, history_weeks=len(prior), peer_count=len(others),
                 candidate=candidate, triggers=triggers, rising=rising,
                 low_sample=r['shipment_count'] < policy.min_shipments,
                 excess_vs_history_inr=max(0,(r['cost_per_tonne_km']-(history or r['cost_per_tonne_km']))*r['tonne_km']))
    return sorted(weeks, key=lambda r:(r['week_of'],r['route'],r['route_type']))


def export_csv(rows: list[dict], path: Path, template: Path) -> None:
    with template.open(newline='',encoding='utf-8-sig') as f:
        header = next(csv.reader(f))
    if header != OUTPUT_COLUMNS:
        raise ValueError(f'Output template header differs from supported contract: {header}')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=header,lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(route=r['route'],week_of=r['week_of'],
                cost_per_tonne_km=f"{r['cost_per_tonne_km']:.2f}",
                vs_own_history=(f"{r['history_pct']:+.1f}% vs this route's past average" if r['history_pct'] is not None else 'N/A (no prior weeks)'),
                vs_similar_routes=(f"{r['peer_pct']:+.1f}% vs similar-length routes this week" if r['peer_pct'] is not None else 'N/A (no other same-type routes this week)'),
                flagged=r['flagged'],matched_note_id=r['matched_note_id'],reason=r['reason']))
