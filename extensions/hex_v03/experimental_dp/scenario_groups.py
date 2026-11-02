"""Exact duplicate reuse, never approximate clustering or probability reduction."""
import numpy as np

def references(states):
    refs=[]
    for s in range(len(states)):
        same=next((j for j in range(s) if np.array_equal(states[s],states[j]) or
                   (np.max(states[s,:,2])==0 and np.max(states[j,:,2])==0)),None)
        refs.append(s if same is None else refs[same])
    return refs
