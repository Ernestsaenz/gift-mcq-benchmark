"""Part 5: reconcile the marginal, conditional and mixed-model estimates."""
import math

# --- numbers carried over from the fitted models (all computed in this session)
b_marg_i = -1.1140       # (i)   condB, no model FE
b_marg_ii = -1.1747      # (ii)  condB, + model FE      [population-averaged]
se_marg_ii = 0.1223      # cluster-robust (208 clinical clusters)
b_feU = -1.8882          # (iv-a) unconditional item FE  [inconsistent]
b_clog = -1.5900         # (iv-b) conditional logit      [subject-specific]
se_clog = 0.1674         # cluster-robust (142 clusters with informative strata)
b_glmm = -1.5968         # GLMM M1 condB                 [subject-specific]
se_glmm = 0.1404
sigma = 1.6553

print("=" * 78)
print("RECONCILIATION: marginal vs subject-specific condition effect")
print("=" * 78)

icc = sigma ** 2 / (sigma ** 2 + math.pi ** 2 / 3)
print("  sigma_item = %.4f ; sigma^2 = %.4f ; ICC(latent) = %.4f"
      % (sigma, sigma ** 2, icc))

# Zeger-Liang-Albert attenuation: b_marg ~= b_cond / sqrt(1 + c^2 sigma^2),
# c = 16*sqrt(3)/(15*pi)
c = 16.0 * math.sqrt(3.0) / (15.0 * math.pi)
print("  attenuation constant c = 16*sqrt(3)/(15*pi) = %.6f ; c^2 = %.6f"
      % (c, c ** 2))
fac = math.sqrt(1.0 + c ** 2 * sigma ** 2)
print("  predicted attenuation factor sqrt(1 + c^2 sigma^2) = %.4f" % fac)
print("  GLMM b_cond=%.4f  =>  predicted marginal b = %.4f" % (b_glmm, b_glmm / fac))
print("  observed  marginal b (model ii)               = %.4f" % b_marg_ii)
print("  discrepancy = %.4f (%.1f%% of the observed marginal effect)"
      % (b_glmm / fac - b_marg_ii, 100 * abs(b_glmm / fac - b_marg_ii / 1) / abs(b_marg_ii)))

print("\n  agreement of the two subject-specific estimators:")
print("    conditional logit (exact conditional likelihood) : %+.4f" % b_clog)
print("    GLMM random intercept (Gauss-Hermite ML)         : %+.4f" % b_glmm)
print("    difference                                       : %+.4f (%.2f%%)"
      % (b_glmm - b_clog, 100 * abs(b_glmm - b_clog) / abs(b_clog)))

print("\n  incidental-parameters bias of the UNCONDITIONAL item-FE fit:")
print("    unconditional item FE : %+.4f" % b_feU)
print("    conditional logit     : %+.4f" % b_clog)
print("    inflation factor      : %.4f  (T=2 theory gives exactly 2.0; here the")
print("                             strata have up to T=8 rows so the bias shrinks)")
print("    confirmed exactly at T=2 in prim_mixed_check.py: -4.09539 = 2 x -2.04769")

print("\n" + "=" * 78)
print("HEADLINE TABLE: effect of replacing the correct option text with NOTA")
print("=" * 78)
rows = [
    ("(i)   condB only, marginal", b_marg_i, 0.1177, "cluster-robust, 208 clusters"),
    ("(ii)  + model FE, marginal", b_marg_ii, se_marg_ii, "cluster-robust, 208 clusters"),
    ("(iv-b) conditional logit (within item)", b_clog, se_clog, "cluster-robust, 142 clusters"),
    ("      GLMM (1|item), within item", b_glmm, se_glmm, "model-based (observed info)"),
]
print("  %-40s %8s %8s %8s %8s %8s"
      % ("model", "b", "SE", "OR", "lo95", "hi95"))
for nm, b, se, note in rows:
    print("  %-40s %+8.4f %8.4f %8.4f %8.4f %8.4f"
          % (nm, b, se, math.exp(b), math.exp(b - 1.959964 * se),
             math.exp(b + 1.959964 * se)))
    print("  %-40s   z=%.3f  p=%.3g   [%s]"
          % ("", b / se, math.erfc(abs(b / se) / math.sqrt(2)), note))
