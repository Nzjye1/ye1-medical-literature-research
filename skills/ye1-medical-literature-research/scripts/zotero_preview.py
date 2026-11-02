#!/usr/bin/env python3
"""Read-only duplicate preview for a user's local Zotero library.

No write/import is performed. Matching is limited to recognized DOI/PMID fields,
URLs and Extra; a no-match is not proof that the record is absent.
"""
import argparse
import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:23119/api/users/0/'


def doi(value):
    value = str(value or '').strip().lower()
    value = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:\s*)', '', value)
    return urllib.parse.unquote(value).strip()


def item_ids(data):
    ds = set()
    ps = set()
    if data.get('DOI'):
        ds.add(doi(data['DOI']))
    for field in ('url', 'extra', 'PMID'):
        val = str(data.get(field, ''))
        ps.update(re.findall(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', val, flags=re.I))
        ps.update(re.findall(r'\bPMID\s*[:\s]\s*(\d+)', val, flags=re.I))
        if field == 'PMID' and val.strip().isdigit():
            ps.add(val.strip())
        ds.update(doi(x) for x in re.findall(r'10\.\d{4,9}/[^\s<>]+', val, flags=re.I))
    return ds, ps


def compare(pmid, expected_doi, items):
    """A shared DOI is a clue, not proof of identical PubMed records."""
    expected = doi(expected_doi)
    matches = []
    for item in items:
        found_doi, found_pmid = item_ids(item['data'])
        same_pmid = pmid in found_pmid
        same_doi = bool(expected and expected in found_doi)
        if not same_pmid and not same_doi:
            continue
        if same_pmid and expected and found_doi and not same_doi:
            relation = 'PMID相同但DOI不同'
        elif same_pmid:
            relation = 'PMID相同'
        elif found_pmid:
            relation = 'DOI相同但PMID不同'
        else:
            relation = '仅DOI相同'
        matches.append({'key': item['key'], 'matched_by':
                       [x for x, ok in (('DOI', same_doi), ('PMID', same_pmid)) if ok],
                       'item_pmids': sorted(found_pmid), 'relation': relation})
    relations = {m['relation'] for m in matches}
    if 'PMID相同但DOI不同' in relations:
        state = '相同 PMID 的 DOI 有冲突，需核对'
    elif 'PMID相同' in relations:
        state = '已有相同 PMID，检查后避免重复导入'
    elif 'DOI相同但PMID不同' in relations:
        state = 'DOI 相同但 PMID 不同，可能是不同文献，需人工核对'
    elif matches:
        state = '仅 DOI 相同，需核对题名和 PMID'
    else:
        state = '未发现匹配，仍需人工确认'
    return matches, state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--pmids', required=True)
    ap.add_argument('--collection', help='optional collection key; omit to compare whole local personal library')
    args = ap.parse_args()
    ids = [x.strip() for x in args.pmids.split(',') if x.strip()]
    if not ids or not all(x.isdigit() for x in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Expected distinct numeric PMIDs')
    if args.collection and not re.fullmatch(r'[A-Z0-9]{8}', args.collection):
        raise ValueError('Invalid Zotero collection key')
    with open(args.candidates, encoding='utf-8-sig', newline='') as f:
        rows={r['pmid']:r for r in csv.DictReader(f)}
    if any(i not in rows for i in ids):
        raise ValueError('A selected PMID is missing from the candidate table')
    route=('collections/'+args.collection+'/items/top' if args.collection else 'items/top')
    items=[];start=0;limit=100
    while True:
        url=BASE+route+'?'+urllib.parse.urlencode({'limit':limit,'start':start})
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'Zotero-API-Version':'3'}),timeout=10) as f:
                batch=json.load(f); total=int(f.headers.get('Total-Results',len(batch)))
        except urllib.error.HTTPError as e:
            raise SystemExit(f'Local Zotero API HTTP {e.code}; check app, local API setting, and selected library.')
        except urllib.error.URLError as e:
            raise SystemExit(f'Local Zotero API unavailable: {e.reason}')
        items.extend(batch)
        start+=len(batch)
        if start>=total: break
        if not batch: raise RuntimeError('Zotero returned an incomplete page')
    results=[]
    for pmid in ids:
        row=rows[pmid]
        matches, state = compare(pmid, row.get('doi'), items)
        results.append({'pmid':pmid,'title':row['title'],'matched_items':matches,
                        'state':state})
    print(json.dumps({'scope':'指定分类' if args.collection else '本机个人文库',
      'items_checked':len(items),'write_performed':False,
      'limitation':'只比较可识别的 DOI/PMID、URL 和 Extra；共享 DOI 可能属于不同文献。未匹配不证明不存在，不检查子笔记、全文或外部文库。',
      'results':results},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
