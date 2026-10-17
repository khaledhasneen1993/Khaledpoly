"""Storage compression never changes journal contents, chronology or provenance."""
import gzip
from pathlib import Path


def open_tape(path, mode='rb'):
    if mode not in ('r','rt','rb'): raise ValueError('Tape is read-only')
    path=Path(path)
    kwargs={} if 'b' in mode else {'encoding':'utf-8'}
    return gzip.open(path,'rt' if mode=='r' else mode,**kwargs) if path.suffix=='.gz' else path.open(mode,**kwargs)


def recorded_tapes(root):
    root=Path(root)
    return sorted([*root.glob('*/events.jsonl'),*root.glob('*/events.jsonl.gz')])
