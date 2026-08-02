"""Is the leave-one-cluster-out test capable of registering the outcomes it reports?

For a ratio estimator delta = 100*S/N and a deleted group g with cell-sum s_g and size n_g:
    delta_wo = 100*(S - s_g)/(N - n_g)
    shift    = delta_wo - delta_full = n_g*(delta_full - delta_c)/(N - n_g)
Because every cell contributes B-A in {-1,0,+1}, s_g is BOUNDED: |s_g| <= n_g.
So the attainable shift for group g is bounded a priori, independent of the data:
    max|shift_g| = n_g * max(|delta_full+100|, |delta_full-100|) / (N - n_g)
and a sign flip requires (S - s_g) >= 0, i.e. s_g <= S.
Stdlib only.
"""
import json, collections, math

P = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
D = json.load(open(P))
inc = [r for r in D if r['analysis_include']]
N = len(inc)
S = sum(r['B_correct'] - r['A_correct'] for r in inc)
full = 100.0 * S / N
print(f'N={N}  S={S}  delta_full={full:.4f} pp')

groups = collections.defaultdict(list)
for r in inc:
    groups[r['cluster']].append(r)

worst = max(abs(full + 100.0), abs(full - 100.0))
rows = []
for g, rr in groups.items():
    n = len(rr)
    s = sum(x['B_correct'] - x['A_correct'] for x in rr)
    dc = 100.0 * s / n
    obs = 100.0 * (S - s) / (N - n) - full
    cap = n * worst / (N - n)                 # a-priori max |shift| for this group
    flip_possible = (-n) <= S                 # need s_g <= S with s_g >= -n
    rows.append((g, n, dc, obs, cap, flip_possible))

can1 = [r for r in rows if r[4] > 1.0]
can_flip = [r for r in rows if r[5]]
print()
print('--- ATTAINABILITY OF THE CLAIM\'S OWN THRESHOLDS ---')
print(f'  clusters where |shift| > 1.0 pp is even ARITHMETICALLY POSSIBLE : '
      f'{len(can1)} / {len(rows)}  ({100*len(can1)/len(rows):.1f}%)')
print(f'  clusters where a SIGN FLIP is even ARITHMETICALLY POSSIBLE       : '
      f'{len(can_flip)} / {len(rows)}')
print(f'  -> the "0 clusters > 1 pp" result is forced for '
      f'{len(rows)-len(can1)} of {len(rows)} refits ({100*(len(rows)-len(can1))/len(rows):.1f}%)')
print(f'  -> the "0 sign flips" result is forced for '
      f'{len(rows)-len(can_flip)} of {len(rows)} refits (100.0%)')
mx = max(r[1] for r in rows)
print(f'  largest cluster = {mx} cells; a flip needs a deleted group with s_g <= S = {S},')
print(f'     but |s_g| <= n_g <= {mx}. Deficit factor = {abs(S)/mx:.2f}x. Flip is impossible by construction.')
print(f'  min cluster size that could ever reach |shift|>1pp: '
      f'n > N/(worst+1) = {N/(worst+1.0):.2f} cells -> n >= {math.ceil(N/(worst+1.0)+1e-9)}')

print()
print('--- THE 11 CLUSTERS THAT COULD HAVE REGISTERED (cap > 1 pp) ---')
print(f'{"cluster":>8} {"cells":>6} {"delta_c":>9} {"obs shift":>10} {"max|shift|":>11} '
      f'{"needed |dc-full|":>17}')
for g, n, dc, obs, cap, fl in sorted(can1, key=lambda t: -t[1]):
    need = 1.0 * (N - n) / n
    print(f'{g:>8} {n:>6} {dc:>9.2f} {obs:>+10.4f} {cap:>11.3f} {need:>17.1f}')
covered = sum(r[1] for r in can1)
print(f'  these {len(can1)} clusters hold {covered}/{N} cells ({100*covered/N:.1f}%);')
print(f'  the other {len(rows)-len(can1)} clusters hold {N-covered} cells and are diagnostically inert.')

print()
print('--- SATURATION CHECK: singleton clusters already at their ceiling ---')
sat = [r for r in rows if r[1] == 4 and abs(abs(r[3]) - r[4]) < 1e-9]
print(f'  n=4 clusters whose observed |shift| EQUALS the a-priori ceiling ({4*worst/(N-4):.4f} pp): {len(sat)}')
print('  i.e. a cluster that went from 100% correct in A to 0% in B (or vice versa) for all 4')
print('  models still cannot move the pooled delta by even 0.36 pp.')

print()
print('--- WHAT THE 208 REFITS ACTUALLY CONTAIN: delete-one-group JACKKNIFE SE ---')
print('  var_jack = (K-1)/K * sum_i (delta_wo_i - mean(delta_wo))^2')
K = len(rows)
dw = [full + r[3] for r in rows]
mb = sum(dw) / K
var = (K - 1) / K * sum((d - mb) ** 2 for d in dw)
se_j = math.sqrt(var)
print(f'  K={K}  jackknife SE = {se_j:.4f} pp')
print('  cluster-bootstrap SE (prim_cluster_bootstrap_results.json, pooled) = 1.6192 pp')
print(f'  ratio jackknife/bootstrap = {se_j/1.6191840859298349:.3f}')
print(f'  implied 95% jackknife interval: [{full-1.96*se_j:.4f}, {full+1.96*se_j:.4f}]'
      f'  width={2*1.96*se_j:.4f} pp')
print('  -> the same 208 refits, read as a variance estimator instead of a range,')
print('     reproduce the full sampling uncertainty. The "range is only 16% of the CI"')
print('     comparison contrasts a delete-1 spread with a resample-all-208 interval;')
print('     the ratio is an artifact of the two scales, not evidence of stability.')
