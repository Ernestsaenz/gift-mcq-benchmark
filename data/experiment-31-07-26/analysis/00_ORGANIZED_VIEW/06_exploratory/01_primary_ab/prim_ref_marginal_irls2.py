#!/usr/bin/env python3
"""Addendum: where do the claim's z/p come from, and is the common-effect
assumption of models (i)/(ii) defensible?  Standard library only."""
import math, json, collections
exec(open('/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/prim_ref_marginal_irls.py').read().split("# ---- claim comparison")[0])

print('\n' + '='*78)
print('A) PROVENANCE OF THE CLAIMED z VALUES')
for lab,b,se,zc in [('(i) ', bi[1], rsei_c[1], -9.465), ('(ii)', bii[1], rseii_c[1], -9.605)]:
    zfull = b/se
    zround = round(b,4)/round(se,4)
    print('  %s z(full precision)=%.5f  z(from ROUNDED b/SE)=%.5f  claimed=%.3f  -> claim matches %s'
          % (lab, zfull, zround, zc,
             'ROUNDED inputs' if abs(zround-zc)<abs(zfull-zc) else 'full precision'))
    print('       p(full)=%.4e   p(from rounded z)=%.4e' % (two_sided_p(zfull), two_sided_p(zround)))

print('\nB) CI LOWER BOUND, model (ii)')
lo_full = math.exp(bii[1]-1.959963985*rseii_c[1])
lo_round = math.exp(round(bii[1],4)-1.959963985*round(rseii_c[1],4))
print('  full precision=%.6f (rounds to %.4f) ; from rounded inputs=%.6f (rounds to %.4f) ; claimed 0.2431'
      % (lo_full, round(lo_full,4), lo_round, round(lo_round,4)))

print('\nC) CLOSED-FORM ARITHMETIC AUDIT of the IRLS-validation sub-claim')
print('  model (i)   IRLS intercept              = %.10f' % bi[0])
print('              exact logit(1166/1299)      = %.10f  |diff|=%.2e   <- TRUE machine-precision check'
      % (math.log(1166/133), abs(bi[0]-math.log(1166/133))))
print('              claim-cited logit(0.8976)   = %.10f  |diff|=%.2e   <- rounded input, not a precision test'
      % (math.log(.8976/.1024), abs(bi[0]-math.log(.8976/.1024))))
print('  model (iii) IRLS intercept              = %.10f' % biii[0])
print('              exact logit(318/325)        = %.10f  |diff|=%.2e' % (math.log(318/7), abs(biii[0]-math.log(318/7))))
print('              claim SAYS logit(318/325)   = 3.8180        -> arithmetic error of %.5f' % abs(3.8180-math.log(318/7)))
print('              (3.8180 would require %d/325 correct-equivalent p=%.6f; actual p=%.6f)'
      % (round(325/(1+math.exp(-3.8180))), 1/(1+math.exp(-3.8180)), 318/325))

print('\nD) JOINT WALD TEST: condB x model interaction = 0  (model iii)')
beta3, mu3, bread3, dev3, it3 = irls_logit(Xiii, y)
rse3, G3 = cr1_se(Xiii, y, mu3, bread3, clus)
# rebuild full robust covariance for the 3 interaction rows
def cr1_V(X,y,mu,bread,groups):
    n,k=len(X),len(X[0]); by=collections.defaultdict(list)
    for i,g in enumerate(groups): by[g].append(i)
    G=len(by); meat=[[0.0]*k for _ in range(k)]
    for g,idx in by.items():
        s=[0.0]*k
        for i in idx:
            e=y[i]-mu[i]
            for a in range(k):
                if X[i][a]!=0.0: s[a]+=X[i][a]*e
        for a in range(k):
            for b in range(k): meat[a][b]+=s[a]*s[b]
    c=(G/(G-1.0))*((n-1.0)/(n-k))
    meat=[[c*v for v in row] for row in meat]
    return matmul(matmul(bread,meat),bread)
V3 = cr1_V(Xiii,y,mu3,bread3,clus)
idxint = [5,6,7]
Vsub = [[V3[a][b] for b in idxint] for a in idxint]
bsub = [beta3[a] for a in idxint]
Vi = matinv(Vsub)
W = sum(bsub[a]*Vi[a][b]*bsub[b] for a in range(3) for b in range(3))
# chi2 df=3 survival = erfc-free: P(X>w) = exp(-w/2)*(1+sqrt(w/2)*... ) ; use series for df=3
def chi2_sf_df3(w):
    # df=3: sf = erfc(sqrt(w/2)) + sqrt(2w/pi)*exp(-w/2)
    return math.erfc(math.sqrt(w/2)) + math.sqrt(2*w/math.pi)*math.exp(-w/2)
print('  cluster-robust Wald W=%.4f on 3 df -> p=%.4f' % (W, chi2_sf_df3(W)))
print('  LR: deviance(ii)=%.4f  deviance(iii)=%.4f  diff=%.4f on 3 df (model-based, ignores clustering)'
      % (2196.730878, dev3, 2196.730878-dev3))
print('  per-model condB (from saturated fit) = ', ['%s %.4f' % (m.split("/")[-1][:12],
        beta3[1] + (0.0 if m==models[0] else beta3[5+oth.index(m)])) for m in models])
