import json, math
from fractions import Fraction
from collections import Counter, OrderedDict

P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows=[r for r in json.load(open(P)) if r.get('analysis_include') is True]
print("clean cells:",len(rows),"items:",len({r['question_id'] for r in rows}),
      "clusters:",len({r['cluster'] for r in rows}),"models:",len({r['model'] for r in rows}))

def sf_chi2_1df(x):
    # exact survival for 1 df
    return math.erfc(math.sqrt(x/2.0))

# validation of tail function
for crit,tgt in [(3.8414588,0.05),(6.6348966,0.01),(2.7055435,0.10),(10.827566,0.001)]:
    print("  sf(%.7f)=%.8f (target %.2f)"%(crit,sf_chi2_1df(crit),tgt))

def exact_mcnemar(b,c):
    """two-sided exact conditional (binomial p=0.5 on n=b+c), exact rational -> float"""
    n=b+c
    if n==0: return 1.0,Fraction(1)
    k=min(b,c)
    s=sum(math.comb(n,i) for i in range(0,k+1))
    p=Fraction(2*s, 1<<n)
    if p>1: p=Fraction(1)
    return float(p), p

def frac_to_float(fr):
    # safe conversion for extremely small fractions
    try:
        v=float(fr)
        if v>0: return v
    except OverflowError:
        pass
    num,den=fr.numerator,fr.denominator
    return math.exp(math.log(num)-math.log(den)) if num>0 else 0.0

def logs10(fr):
    num,den=fr.numerator,fr.denominator
    if num==0: return float('-inf')
    return (math.log(num)-math.log(den))/math.log(10)

def chi2cc(b,c):
    n=b+c
    if n==0: return 0.0,1.0
    X=(abs(b-c)-1.0)**2/n
    return X, sf_chi2_1df(X)

def table(rs):
    a=b=c=d=0
    for r in rs:
        A,B=r['A_correct'],r['B_correct']
        if A==1 and B==1: a+=1
        elif A==1 and B==0: b+=1
        elif A==0 and B==1: c+=1
        else: d+=1
    return a,b,c,d

models=sorted({r['model'] for r in rows})
print("\n%-22s %5s %5s %5s %5s %5s %8s %8s %9s %14s %16s %10s %8s"%(
    "model","n","a","b","c","d","A%","B%","delta_pp","X2_cc","p_cc","p_exact","ratio"))

res=OrderedDict()
for m in models+['POOLED']:
    rs=rows if m=='POOLED' else [r for r in rows if r['model']==m]
    a,b,c,d=table(rs); n=a+b+c+d
    Aacc=(a+b)/n*100; Bacc=(a+c)/n*100
    X,pcc=chi2cc(b,c)
    pex_f,pex_fr=exact_mcnemar(b,c)
    pex=frac_to_float(pex_fr)
    ratio=math.exp(math.log(pcc)-logs10(pex_fr)*math.log(10)) if pcc>0 else float('nan')
    res[m]=dict(n=n,a=a,b=b,c=c,d=d,bc=b+c,X=X,pcc=pcc,pex=pex,
                log10_pex=logs10(pex_fr),ratio=ratio,A=Aacc,B=Bacc)
    print("%-22s %5d %5d %5d %5d %5d %7.1f%% %7.1f%% %+8.1f %14.4f %16.4e %10.4e %8.2f"%(
        m,n,a,b,c,d,Aacc,Bacc,Bacc-Aacc,X,pcc,pex,ratio))

print("\nlog10 gap pooled: log10(p_cc)-log10(p_exact) = %.4f"%(math.log10(res['POOLED']['pcc'])-res['POOLED']['log10_pex']))
print("exact p_exact pooled (log10) = %.6f  -> %.4e"%(res['POOLED']['log10_pex'],res['POOLED']['pex']))

# monotonicity of ratio in b+c
print("\nordering check: (b+c, |b-c|, ratio) sorted by b+c")
for m,v in sorted(res.items(), key=lambda kv: kv[1]['bc']):
    print("  %-22s b+c=%4d  |b-c|=%4d  X2=%8.4f  ratio=%9.2f"%(m,v['bc'],abs(v['b']-v['c']),v['X'],v['ratio']))
