#!/usr/bin/env python
"""Stress the position-artifact claim.

 A. Is 'a' discontinuous, or is there a generic letter gradient?
    -> placebo contrasts among b/c/d only, and a 3-df letter-homogeneity test.
 B. Model as a random factor (effect must generalise beyond these 4 models).
 C. Covariate balance: key-position is NOT randomised, so the permutation null
    (exchangeable items) is an assumption, not a design fact.
 D. Route (iii) calibration probe.
Stdlib only.
"""
import json, os, random, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'paired_clean.json')))
for r in D:
    r['d'] = r['B_correct'] - r['A_correct']

items = collections.OrderedDict()
for r in D:
    items.setdefault(r['question_id'], []).append(r)
Q = list(items.keys())
LET = {q: items[q][0]['correct_letter'] for q in Q}
CLU = {q: items[q][0]['cluster'] for q in Q}
DS = {q: sum(x['d'] for x in items[q]) for q in Q}
DN = {q: len(items[q]) for q in Q}
clusters = collections.OrderedDict()
for q in Q:
    clusters.setdefault(CLU[q], []).append(q)
CK = list(clusters.keys())

def contrast(letmap, grpA, qs=None):
    """mean d over cells whose letter in grpA minus cells whose letter not in grpA"""
    qs = qs if qs is not None else Q
    sa = na = sn = nn = 0
    for q in qs:
        if letmap[q] in grpA: sa += DS[q]; na += DN[q]
        else:                 sn += DS[q]; nn += DN[q]
    if na == 0 or nn == 0: return None
    return 100.0*(sa/na - sn/nn)

def perm_p(grpA, qs, B=20000, seed=7):
    """item-level randomisation of the letter labels restricted to qs"""
    obs = contrast(LET, grpA, qs)
    labs = [LET[q] for q in qs]
    rnd = random.Random(seed)
    ge = 0
    for _ in range(B):
        rnd.shuffle(labs)
        pm = dict(zip(qs, labs))
        v = contrast(pm, grpA, qs)
        if abs(v) >= abs(obs)-1e-12: ge += 1
    return obs, (ge+1)/(B+1)

def cluster_boot_ci(grpA, qs, B=20000, seed=11):
    obs = contrast(LET, grpA, qs)
    qset = set(qs)
    cl = collections.OrderedDict()
    for q in qs: cl.setdefault(CLU[q], []).append(q)
    keys = list(cl.keys()); K = len(keys)
    rnd = random.Random(seed); reps = []
    for _ in range(B):
        sa=na=sn=nn=0
        for _ in range(K):
            for q in cl[keys[rnd.randrange(K)]]:
                if LET[q] in grpA: sa+=DS[q]; na+=DN[q]
                else:              sn+=DS[q]; nn+=DN[q]
        if na and nn: reps.append(100.0*(sa/na-sn/nn))
    reps.sort(); n=len(reps)
    lo=reps[int(0.025*n)]; hi=reps[min(n-1,int(math.ceil(0.975*n))-1)]
    above=sum(1 for x in reps if x>0); below=n-above-sum(1 for x in reps if x==0)
    return obs, lo, hi, 2.0*min(above,below)/n

print('='*78)
print('A.  IS THE JUMP AT (a) SPECIAL?  per-letter d (pp), full set')
print('='*78)
for L in 'abcd':
    rr=[r for r in D if r['correct_letter']==L]
    print('   %s  n=%4d  d=%+7.3f pp' % (L,len(rr),100*sum(r['d'] for r in rr)/len(rr)))

print('\n   -- one-vs-rest contrasts, EVERY letter treated identically --')
print('   (same statistic, same item-level randomisation, same cluster bootstrap)')
rows=[]
for L in 'abcd':
    o,p = perm_p({L}, Q, seed=100+ord(L))
    _,lo,hi,pb = cluster_boot_ci({L}, Q, seed=200+ord(L))
    rows.append((L,o,lo,hi,p,pb))
    print('   key=%s vs rest : ART=%+7.3f  CI=[%+7.3f,%+7.3f]  p_perm=%.4f  p_boot=%.4f'
          % (L,o,lo,hi,p,pb))

print('\n   -- PLACEBO: contrasts that involve NO position-(a) mechanism --')
nonA=[q for q in Q if LET[q]!='a']
for L in 'bcd':
    o,p = perm_p({L}, nonA, seed=300+ord(L))
    _,lo,hi,pb = cluster_boot_ci({L}, nonA, seed=400+ord(L))
    print('   within b/c/d only, key=%s vs rest : ART=%+7.3f CI=[%+7.3f,%+7.3f] p_perm=%.4f p_boot=%.4f'
          % (L,o,lo,hi,p,pb))
o,p = perm_p({'b'}, nonA, seed=999)
print('   -> b vs (c,d) placebo effect = %+.3f pp, p=%.4f' % (o,p))

# 3-df omnibus: max |one-vs-rest| over the four letters, permutation-calibrated
obs_stats={L:abs(contrast(LET,{L})) for L in 'abcd'}
obs_max=max(obs_stats.values())
labs=[LET[q] for q in Q]; rnd=random.Random(555); ge=0; B=20000
for _ in range(B):
    rnd.shuffle(labs); pm=dict(zip(Q,labs))
    if max(abs(contrast(pm,{L})) for L in 'abcd') >= obs_max-1e-12: ge+=1
p_max=(ge+1)/(B+1)
print('\n   OMNIBUS max|one-vs-rest| over 4 letters: obs=%.3f (letter a), '
      'permutation p = %.4f' % (obs_max,p_max))
print('   -> this is the honest p once you admit the letter was CHOSEN by looking')

print()
print('='*78)
print('B.  MODEL AS A RANDOM FACTOR (does the artifact generalise past these 4?)')
print('='*78)
per={}
for m in sorted(set(r['model'] for r in D)):
    rr=[r for r in D if r['model']==m]
    a=[r['d'] for r in rr if r['correct_letter']=='a']
    n=[r['d'] for r in rr if r['correct_letter']!='a']
    per[m]=100*(sum(a)/len(a)-sum(n)/len(n))
    print('   %-28s ART=%+8.3f pp' % (m,per[m]))
v=list(per.values()); k=len(v); mu=sum(v)/k
sd=math.sqrt(sum((x-mu)**2 for x in v)/(k-1)); se=sd/math.sqrt(k)
t=mu/se
# two-sided t with 3 df, exact via incomplete beta (series-free: use numeric integration)
def t_sf(t,df):
    t=abs(t); x=df/(df+t*t)
    # regularised incomplete beta I_x(df/2, 1/2) via numeric integration
    a=df/2.0; b=0.5; N=200000; s=0.0
    for i in range(N):
        u=(i+0.5)/N*x
        s+=u**(a-1)*(1-u)**(b-1)
    s*=x/N
    lbeta=math.lgamma(a)+math.lgamma(b)-math.lgamma(a+b)
    return 0.5*s/math.exp(lbeta)          # one-sided
print('   mean=%+.3f  SD=%.3f  SE=%.3f  t(%d df)=%.3f  two-sided p=%.4f'
      % (mu,sd,se,k-1,t,2*t_sf(t,k-1)))
print('   95%% CI over models = [%+.3f, %+.3f]  (t.975,3=3.182)' % (mu-3.182*se,mu+3.182*se))
print('   -> the claim\'s SE treats the 4 models as FIXED; across models the effect')
print('      ranges -2.75..-14.50 pp and the model-level interval covers 0.')

print()
print('='*78)
print('C.  COVARIATE BALANCE: key position is NOT randomised')
print('='*78)
aQ=[q for q in Q if LET[q]=='a']; nQ=[q for q in Q if LET[q]!='a']
def prop(qs,f):
    vals=[f(items[q][0]) for q in qs]; return sum(vals)/len(vals)
for name,f in (('negated_stem',lambda r: 1 if r['negated_stem'] else 0),
               ('has_context', lambda r: 1 if r['has_context'] else 0),
               ('qlen',        lambda r: r['qlen']),
               ('year',        lambda r: r['year'])):
    print('   %-13s  key=a: %9.3f   key=b/c/d: %9.3f' % (name,prop(aQ,f),prop(nQ,f)))
print('   A-arm accuracy  key=a: %.4f   key=b/c/d: %.4f'
      % (sum(r['A_correct'] for r in D if r['correct_letter']=='a')/364,
         sum(r['A_correct'] for r in D if r['correct_letter']!='a')/1327))
for name,f in (('exam_part',lambda r:r['exam_part']),('region',lambda r:r['region'])):
    ca=collections.Counter(f(items[q][0]) for q in aQ)
    cn=collections.Counter(f(items[q][0]) for q in nQ)
    ks=sorted(set(ca)|set(cn))
    print('   %s:' % name)
    for kk in ks[:12]:
        print('      %-22s a=%5.3f  bcd=%5.3f' % (str(kk),ca[kk]/len(aQ),cn[kk]/len(nQ)))

print()
print('='*78)
print('D.  ROUTE (iii) CALIBRATION PROBE')
print('='*78)
mixed=[c for c,qs in clusters.items() if len(set(LET[q]=='a' for q in qs))>1]
mq=[q for c in mixed for q in clusters[c]]
print('   mixed clusters=%d  items in them=%d  of which key=a: %d'
      % (len(mixed),len(mq),sum(1 for q in mq if LET[q]=='a')))
print('   a-items OUTSIDE mixed clusters (labels FROZEN by route iii): %d of 91'
      % sum(1 for q in aQ if q not in set(mq)))
# how much of the observed statistic can route (iii) even move?
rnd=random.Random(31); vals=[]
base={q:LET[q]=='a' for q in Q}
def art_from(m):
    sa=na=sn=nn=0
    for q in Q:
        if m[q]: sa+=DS[q]; na+=DN[q]
        else:    sn+=DS[q]; nn+=DN[q]
    return 100*(sa/na-sn/nn)
for _ in range(20000):
    pm=dict(base)
    for c in mixed:
        qs=clusters[c]; ls=[base[q] for q in qs]; rnd.shuffle(ls)
        for q,l in zip(qs,ls): pm[q]=l
    vals.append(art_from(pm))
vals.sort()
print('   route (iii) null distribution: mean=%+.3f sd=%.3f  range=[%+.3f,%+.3f]'
      % (sum(vals)/len(vals), math.sqrt(sum((x-sum(vals)/len(vals))**2 for x in vals)/(len(vals)-1)),
         vals[0],vals[-1]))
print('   NOTE: this null is NOT centred at 0 -> it tests a different (restricted) null')
print('   distinct values realised: %d' % len(set(round(v,6) for v in vals)))
