import json,os,random,collections,math
HERE=os.path.dirname(os.path.abspath(__file__))
D=json.load(open(os.path.join(HERE,'paired_clean.json')))
for r in D: r['d']=r['B_correct']-r['A_correct']
it=collections.OrderedDict()
for r in D: it.setdefault(r['question_id'],[]).append(r)
Q=list(it); LET={q:it[q][0]['correct_letter'] for q in Q}; CLU={q:it[q][0]['cluster'] for q in Q}
DS={q:sum(x['d'] for x in it[q]) for q in Q}; DN={q:len(it[q]) for q in Q}
cl=collections.OrderedDict()
for q in Q: cl.setdefault(CLU[q],[]).append(q)
CK=list(cl)
def stat(idx_items):
    sa=na=sn=nn=0
    for q in idx_items:
        if LET[q]=='a': sa+=DS[q]; na+=DN[q]
        else: sn+=DS[q]; nn+=DN[q]
    return 100*(sa/na-sn/nn) if na and nn else None
def boot(units,B,seed):
    rnd=random.Random(seed); v=[]
    K=len(units)
    for _ in range(B):
        bag=[]
        for _ in range(K): bag.extend(units[rnd.randrange(K)])
        s=stat(bag)
        if s is not None: v.append(s)
    m=sum(v)/len(v); return m, math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
m1,s1=boot([cl[c] for c in CK],20000,1)   # cluster bootstrap
m2,s2=boot([[q] for q in Q],20000,2)      # i.i.d. ITEM bootstrap (ignores clusters)
print('cluster bootstrap SE = %.4f   (mean %+.4f)'%(s1,m1))
print('i.i.d. item bootstrap SE = %.4f (mean %+.4f)'%(s2,m2))
print('ratio = %.4f  -> clustering inflates SE by only %.1f%%'%(s1/s2,100*(s1/s2-1)))
# permutation SD of the null statistic
labs=[LET[q]=='a' for q in Q]; rnd=random.Random(3); v=[]
for _ in range(20000):
    rnd.shuffle(labs)
    sa=na=sn=nn=0
    for q,l in zip(Q,labs):
        if l: sa+=DS[q]; na+=DN[q]
        else: sn+=DS[q]; nn+=DN[q]
    v.append(100*(sa/na-sn/nn))
m=sum(v)/len(v); sp=math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
print('item permutation null SD = %.4f (mean %+.4f)'%(sp,m))
print('=> routes (i) and (ii) rest on SEs of %.3f vs %.3f: the SAME variance estimate.'%(s1,sp))
