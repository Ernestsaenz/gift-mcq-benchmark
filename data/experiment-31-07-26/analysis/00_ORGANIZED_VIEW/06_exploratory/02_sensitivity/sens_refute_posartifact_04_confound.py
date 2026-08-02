#!/usr/bin/env python
"""Does the (a) contrast survive the covariates it is confounded with?

(a)-key items are shorter (qlen 675 vs 920) and far less often carry clinical
context (0.264 vs 0.419). Both are plausible drivers of d = B - A.
Stratify / adjust and see what is left.
Stdlib only.
"""
import json, os, random, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'paired_clean.json')))
for r in D: r['d'] = r['B_correct'] - r['A_correct']

items = collections.OrderedDict()
for r in D: items.setdefault(r['question_id'], []).append(r)
Q = list(items.keys())
LET={q:items[q][0]['correct_letter'] for q in Q}
CLU={q:items[q][0]['cluster'] for q in Q}
DS ={q:sum(x['d'] for x in items[q]) for q in Q}
DN ={q:len(items[q]) for q in Q}
CTX={q:items[q][0]['has_context'] for q in Q}
QL ={q:items[q][0]['qlen'] for q in Q}

print('=== marginal association of the CONFOUNDERS with d (nothing to do with (a)) ===')
for lab,sel in (('has_context=True', lambda q: CTX[q]), ('has_context=False', lambda q: not CTX[q])):
    qs=[q for q in Q if sel(q)]
    s=sum(DS[q] for q in qs); n=sum(DN[q] for q in qs)
    print('   %-19s items=%3d cells=%4d  d=%+7.3f pp' % (lab,len(qs),n,100*s/n))
ql=sorted(QL[q] for q in Q); t1=ql[len(ql)//3]; t2=ql[2*len(ql)//3]
def tert(q): return 0 if QL[q]<=t1 else (1 if QL[q]<=t2 else 2)
for t in (0,1,2):
    qs=[q for q in Q if tert(q)==t]
    s=sum(DS[q] for q in qs); n=sum(DN[q] for q in qs)
    print('   qlen tertile %d (<=%d)  items=%3d cells=%4d  d=%+7.3f pp' % (t,t2 if t==2 else (t1 if t==0 else t2),len(qs),n,100*s/n))

def art(qs, letmap=LET):
    sa=na=sn=nn=0
    for q in qs:
        if letmap[q]=='a': sa+=DS[q]; na+=DN[q]
        else:              sn+=DS[q]; nn+=DN[q]
    if not na or not nn: return None,0,0
    return 100*(sa/na-sn/nn), na, nn

print()
print('=== STRATIFIED artifact (cell-count-weighted pooling over strata) ===')
def stratified(keyfn, name, B=20000, seed=17):
    strata=collections.OrderedDict()
    for q in Q: strata.setdefault(keyfn(q),[]).append(q)
    parts=[]; wsum=0.0; acc=0.0
    for k,qs in strata.items():
        v,na,nn=art(qs)
        if v is None:
            print('   %-8s %-10s  (no contrast: na=%d nn=%d) SKIPPED' % (name,str(k),na,nn)); continue
        w=1.0/(1.0/na+1.0/nn)      # inverse-variance-ish weight
        parts.append((k,v,na,nn,w)); acc+=w*v; wsum+=w
        print('   %-8s %-10s  ART=%+8.3f  (a cells=%3d, other=%4d)' % (name,str(k),v,na,nn))
    pooled=acc/wsum
    # permutation p: shuffle the (a) label WITHIN each stratum
    rnd=random.Random(seed); ge=0
    for _ in range(B):
        pm={}
        for k,qs in strata.items():
            ls=[LET[q]=='a' for q in qs]; rnd.shuffle(ls)
            for q,l in zip(qs,ls): pm[q]='a' if l else 'z'
        acc2=0.0; ws=0.0
        for k,qs in strata.items():
            v,na,nn=art(qs,pm)
            if v is None: continue
            w=1.0/(1.0/na+1.0/nn); acc2+=w*v; ws+=w
        if ws and abs(acc2/ws)>=abs(pooled)-1e-12: ge+=1
    print('   >> POOLED %s-adjusted ARTIFACT = %+.3f pp   within-stratum permutation p = %.4f'
          % (name,pooled,(ge+1)/(B+1)))
    return pooled

stratified(lambda q: CTX[q], 'context')
print()
stratified(lambda q: tert(q), 'qlen3')
print()
stratified(lambda q: (CTX[q],tert(q)), 'ctx*qlen')

print()
print('=== the same, but as a placebo: does adjustment kill the c-vs-rest effect too? ===')
def art_c(qs, letmap=LET):
    sa=na=sn=nn=0
    for q in qs:
        if letmap[q]=='c': sa+=DS[q]; na+=DN[q]
        else:              sn+=DS[q]; nn+=DN[q]
    if not na or not nn: return None,0,0
    return 100*(sa/na-sn/nn),na,nn
strata=collections.OrderedDict()
for q in Q: strata.setdefault((CTX[q],tert(q)),[]).append(q)
acc=ws=0.0
for k,qs in strata.items():
    v,na,nn=art_c(qs)
    if v is None: continue
    w=1.0/(1.0/na+1.0/nn); acc+=w*v; ws+=w
print('   ctx*qlen-adjusted c-vs-rest = %+.3f pp' % (acc/ws))
