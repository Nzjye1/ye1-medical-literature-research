#!/usr/bin/env python3
"""Export explicitly selected PubMed records to RIS; no Zotero writes are made."""
import argparse
import csv
from pathlib import Path


def clean(s):
    return ' '.join(str(s or '').split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--pmids', required=True, help='comma-separated, manually selected PubMed IDs')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    ids = [s.strip() for s in args.pmids.split(',') if s.strip()]
    if not ids or len(ids) != len(set(ids)) or not all(s.isdigit() for s in ids):
        raise ValueError('Give distinct numeric PMIDs')
    with open(args.candidates, encoding='utf-8-sig', newline='') as f:
        rows = {r['pmid']: r for r in csv.DictReader(f)}
    if any(pmid not in rows for pmid in ids):
        raise ValueError('At least one requested PMID was not retrieved')
    blocks = []
    for pmid in ids:
        r = rows[pmid]
        lines = ['TY  - JOUR', 'TI  - ' + clean(r['title'])]
        for author in r['authors'].split('; '):
            if author:
                lines.append('AU  - ' + clean(author))
        for tag, field in [('PY', 'year'), ('JO', 'journal'), ('DO', 'doi'), ('UR', 'url')]:
            if r.get(field):
                lines.append(tag + '  - ' + clean(r[field]))
        # Zotero's RIS translator maps M2 to Extra; N1 creates a child note instead.
        lines.extend(['M2  - PMID: ' + pmid, 'ER  - ', ''])
        blocks.append('\n'.join(lines))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(blocks))
    print(f'Exported {len(ids)} selected records to {out}. No PDFs were exported.')

if __name__ == '__main__':
    main()
