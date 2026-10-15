"""Validate published data and package the complete repository for submission."""
import csv
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    results = ROOT / 'results'
    with (ROOT / 'data/sample_output_format_v2.csv').open(newline='') as f:
        expected = next(csv.reader(f))
    with (results / 'output.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == expected, 'CSV columns differ from sample contract'
        rows = list(reader)
    audit = json.loads((results / 'audit.json').read_text())
    assert len(rows) == len(audit['rows'])
    proof = json.loads((results / 'reproducibility.json').read_text())
    assert proof['identical'] and len(proof['runs']) == 3
    assert proof['runs'][0] == proof['runs'][1] == proof['runs'][2]
    import hashlib
    for filename, expected_hash in proof['runs'][0].items():
        assert hashlib.sha256((results / filename).read_bytes()).hexdigest() == expected_hash, filename
    shutil.copyfile(results / 'output.csv', ROOT / 'output.csv')
    shutil.copyfile(results / 'audit.json', ROOT / 'data.json')
    archive = ROOT / 'FreightWatch_Submission.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob('*')):
            if not p.is_file() or p == archive:
                continue
            rel = p.relative_to(ROOT)
            if any(part in {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.openai'} for part in rel.parts):
                continue
            if p.suffix == '.pyc':
                continue
            z.write(p, Path('FreightWatch') / rel)
    print(f'Validated {len(rows)} CSV rows, three-run hashes, and published data. Created {archive.name}.')

if __name__ == '__main__':
    main()
