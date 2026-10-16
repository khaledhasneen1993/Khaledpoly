#!/usr/bin/env python3
"""Describe observed evidence, including failed/blocked public APIs, without inventing fills."""
import collections,json,pathlib,sys
root=pathlib.Path(sys.argv[1]);summary=[]
for tape in root.glob('*/events.jsonl'):
 counts=collections.Counter();errors=[];first=last=None;expected=0
 for line in tape.open():
  row=json.loads(line);expected+=1
  if row['seq']!=expected:raise ValueError('Recording sequence gap')
  counts[row['kind']]+=1
  if first is None:first=row['arrivalMs']
  last=row['arrivalMs']
  if row['kind']=='RESEARCH_FEED_ERROR':errors.append(row['data'])
 summary.append({'run':tape.parent.name,'events':dict(counts),'durationMs':None if first is None else last-first,'errors':errors,'decision':'NO_GO','reason':'Short recording cannot meet preregistered seven-day holdout and sample requirements'})
if not summary:raise ValueError('No recording files produced')
(root/'collection-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
