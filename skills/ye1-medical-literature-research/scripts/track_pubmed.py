#!/usr/bin/env python3
"""Local PubMed topic cursor for manually triggered or host-scheduled runs.

Only complete retrievals advance the cursor. Emits candidates; does not send,
write to Zotero, or decide that newly discovered records are newly published.
"""
import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIELDS=('title','doi','year','publication_types','abstract','publication_status','related_notices','flags')


def stamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(row):
    return hashlib.sha256(json.dumps({k: row.get(k, '') for k in FIELDS},
                                    ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def load_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if len({r['pmid'] for r in rows}) != len(rows) or any(not r['pmid'].isdigit() for r in rows):
        raise ValueError('Invalid or duplicate PMIDs')
    return rows


def atomic_json(path, obj):
    temp=path.with_name(path.name + '.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def init(args):
    statepath=Path(args.state)
    if statepath.exists(): raise FileExistsError('State exists; choose a new topic state file')
    cfg=json.loads(Path(args.queries).read_text(encoding='utf-8'))
    receipt=json.loads((Path(args.baseline)/'receipt.json').read_text(encoding='utf-8'))
    if not receipt['complete']:raise ValueError('Incomplete baseline cannot initialize a tracker')
    base_queries={(q['name'],q['query']) for q in receipt['queries'] if q['complete']}
    if any((q['name'],q['term']) not in base_queries for q in cfg['queries']):
        raise ValueError('Each tracking query must match a completed baseline query')
    rows=load_rows(Path(args.baseline)/'candidates.csv')
    if len(rows)!=receipt['unique_records']:raise ValueError('Baseline record count mismatch')
    state={'version':1,'topic':cfg.get('topic',''),'queries':cfg['queries'],
           'last_success_start_utc':receipt['started_utc'],
           'records':{r['pmid']:digest(r) for r in rows},
           'overlap_days':3,'initialized_utc':stamp()}
    statepath.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(statepath,state)
    print(json.dumps({'initialized':True,'baseline_records':len(rows),'last_success_start_utc':state['last_success_start_utc']},ensure_ascii=False))


def run(args):
    if getattr(args, 'save_fulltext', False) and not getattr(args, 'library_topic', None):
        raise ValueError('--save-fulltext 需要 --library-topic')
    path=Path(args.state)
    lock=path.with_name(path.name+'.lock')
    try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise RuntimeError('Tracker is already running or a stale lock needs inspection')
    os.close(fd)
    try:
        state=json.loads(path.read_text(encoding='utf-8'))
        start=datetime.now(timezone.utc)
        previous=datetime.fromisoformat(state['last_success_start_utc'])
        begin=(previous-timedelta(days=state['overlap_days'])).strftime('%Y/%m/%d')
        # Inclusive end and overlapping days tolerate day-boundary and modest indexing delays.
        end=(start+timedelta(days=1)).strftime('%Y/%m/%d')
        dates=f'(({begin}[crdt] : {end}[crdt]) OR ({begin}[lr] : {end}[lr]))'
        cfg={'topic':state['topic'],'page_size':200,'queries':[
             {'name':q['name'], 'term':f"({q['term']}) AND {dates}"} for q in state['queries']]}
        runid=start.strftime('%Y%m%dT%H%M%S%fZ')
        run_dir=Path(args.runs_dir)/runid
        run_dir.mkdir(parents=True,exist_ok=False)
        cfgpath=run_dir/'queries.json';atomic_json(cfgpath,cfg)
        retrieval=run_dir/'retrieval'
        cmd=[sys.executable,str(Path(__file__).with_name('pubmed_search.py')),
             '--queries',str(cfgpath),'--out',str(retrieval),
             '--max-per-query',str(args.max_per_query)]
        p=subprocess.run(cmd,text=True,capture_output=True)
        (run_dir/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode!=0:
            print(json.dumps({'complete':False,'state_unchanged':True,'run_dir':str(run_dir)},ensure_ascii=False))
            return 1
        receipt=json.loads((retrieval/'receipt.json').read_text(encoding='utf-8'))
        if not receipt['complete']:
            raise RuntimeError('Incomplete retrieval receipt; state not advanced')
        rows=load_rows(retrieval/'candidates.csv')
        if len(rows)!=receipt['unique_records']:raise RuntimeError('Record count mismatch; state not advanced')
        old=state['records'];new=[];changed=[];same=[]
        for row in rows:
            pmid=row['pmid'];h=digest(row)
            if pmid not in old:new.append(pmid)
            elif old[pmid]!=h:changed.append(pmid)
            else:same.append(pmid)
            old[pmid]=h
        delta={'complete':True,'window':{'start_inclusive':begin,'end_inclusive':end,'fields':['crdt','lr']},
               'records_returned':len(rows),'newly_discovered_pmids':new,'changed_metadata_pmids':changed,
               'already_known_unchanged_pmids':same,
               'note':'新发现不等于新发表；字段修订亦不自动等于更正或撤稿，须复核相关通知。'}
        atomic_json(run_dir/'delta.json',delta)
        library_result = None
        library_topic = getattr(args, 'library_topic', None)
        if library_topic:
            library_log=io.StringIO()
            try:
                spec=importlib.util.spec_from_file_location('medical_local_library',Path(__file__).with_name('local_library.py'))
                library=importlib.util.module_from_spec(spec);spec.loader.exec_module(library)
                library_result=library.import_candidates(library_topic,retrieval/'candidates.csv')
                if getattr(args, 'save_fulltext', False):
                    returned={r['pmid'] for r in rows}
                    _, existing=library.read_catalog(library_topic)
                    pending=[r['pmid'] for r in existing if r.get('pmid') in returned
                             and r.get('screening_status') != '排除'
                             and not (r.get('fulltext_path') and (Path(library_topic)/r['fulltext_path']).is_file())]
                    with contextlib.redirect_stdout(library_log):
                        library_result['fulltext']=library.fetch_fulltexts(library_topic,pmids=pending)
                if library_log.getvalue():
                    with (run_dir/'run.log').open('a',encoding='utf-8') as f:f.write('\n'+library_log.getvalue())
            except Exception as exc:
                with (run_dir/'run.log').open('a',encoding='utf-8') as f:
                    f.write('\n'+library_log.getvalue()+'\nLocal library update failed: '+type(exc).__name__+': '+str(exc)+'\n')
                print(json.dumps({'complete':False,'retrieval_complete':True,'state_unchanged':True,
                                  'run_dir':str(run_dir),'library_error':str(exc)},ensure_ascii=False))
                return 1
        # Advance to the beginning of this successful retrieval, not its end.
        state['last_success_start_utc']=receipt['started_utc']
        atomic_json(path,state)
        print(json.dumps({'complete':True,'new':len(new),'changed':len(changed),'unchanged':len(same),
                          'run_dir':str(run_dir),'library':library_result},ensure_ascii=False))
        return 0
    finally:
        lock.unlink(missing_ok=True)


def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    a=sub.add_parser('init');a.add_argument('--state',required=True);a.add_argument('--queries',required=True);a.add_argument('--baseline',required=True)
    b=sub.add_parser('run');b.add_argument('--state',required=True);b.add_argument('--runs-dir',required=True);b.add_argument('--max-per-query',type=int,default=20000)
    b.add_argument('--library-topic', help='将本次结果更新到已初始化的本地主题目录')
    b.add_argument('--save-fulltext', action='store_true', help='为新发现文献尝试保存 PMC 开放全文；需要 --library-topic')
    args=ap.parse_args()
    return init(args) if args.command=='init' else run(args)

if __name__=='__main__':sys.exit(main() or 0)
