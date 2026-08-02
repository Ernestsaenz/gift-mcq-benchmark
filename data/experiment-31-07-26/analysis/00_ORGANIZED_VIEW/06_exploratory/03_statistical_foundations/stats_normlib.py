"""
stats_normlib.py -- pure-stdlib normality-testing library written from scratch.

No numpy/scipy. Implements:
  - Phi (normal CDF)            via math.erfc
  - Phi^-1 (normal quantile)    via Wichura AS241 (PPND16)
  - Shapiro-Wilk W + p          via Royston (1995) AS R94
  - Shapiro-Francia W' + p      via Royston (1993)
  - D'Agostino-Pearson K^2 + p  via D'Agostino (1970) / Anscombe-Glynn (1983)
  - Anderson-Darling A*^2 + p   via Stephens / D'Agostino & Stephens (1986)
  - Jarque-Bera JB + p
  - moments: g1 (skew), g2 (excess kurtosis), with standard errors
  - Q-Q diagnostics: Filliben r, tail quantile ratios

Every p-value here comes from one of these published closed-form approximations,
computed in this file. Nothing is looked up or invented.
"""
import math
from statistics import mean

SQRT2 = math.sqrt(2.0)


# ----------------------------------------------------------------- normal CDF
def phi_cdf(z):
    """Standard normal CDF via erfc. Accurate to ~1e-16 relative in the body."""
    return 0.5 * math.erfc(-z / SQRT2)


def phi_sf(z):
    """Upper tail 1-Phi(z), computed without cancellation."""
    return 0.5 * math.erfc(z / SQRT2)


# ------------------------------------------------------- normal quantile AS241
def phi_ppf(p):
    """
    Inverse standard normal CDF. Wichura (1988) AS241 algorithm PPND16.
    Relative accuracy ~1e-16 over the whole range.
    """
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        num = (((((((2.5090809287301226727e+3 * r + 3.3430575583588128105e+4) * r
                    + 6.7265770927008700853e+4) * r + 4.5921953931549871457e+4) * r
                  + 1.3731693765509461125e+4) * r + 1.9715909503065514427e+3) * r
                + 1.3314166789178437745e+2) * r + 3.3871328727963666080e0)
        den = (((((((5.2264952788528545610e+3 * r + 2.8729085735721942674e+4) * r
                    + 3.9307895800092710610e+4) * r + 2.1213794301586595867e+4) * r
                  + 5.3941960214247511077e+3) * r + 6.8718700749205790830e+2) * r
                + 4.2313330701600911252e+1) * r + 1.0)
        return q * num / den
    r = p if q < 0 else 1.0 - p
    r = math.sqrt(-math.log(r))
    if r <= 5.0:
        r -= 1.6
        num = (((((((7.74545014278341407640e-4 * r + 2.27238449892691845833e-2) * r
                    + 2.41780725177450611770e-1) * r + 1.27045825245236838258e0) * r
                  + 3.64784832476320460504e0) * r + 5.76949722146069140550e0) * r
                + 4.63033784615654529590e0) * r + 1.42343711074968357734e0)
        den = (((((((1.05075007164441684324e-9 * r + 5.47593808499534494600e-4) * r
                    + 1.51986665636164571966e-2) * r + 1.48103976427480074590e-1) * r
                  + 6.89767334985100004550e-1) * r + 1.67638483018380384940e0) * r
                + 2.05319162663775882187e0) * r + 1.0)
    else:
        r -= 5.0
        num = (((((((2.01033439929228813265e-7 * r + 2.71155556874348757815e-5) * r
                    + 1.24266094738807843860e-3) * r + 2.65321895265761230930e-2) * r
                  + 2.96560571828504891230e-1) * r + 1.78482653991729133580e0) * r
                + 5.46378491116411436990e0) * r + 6.65790464350110377720e0)
        den = (((((((2.04426310338993978564e-15 * r + 1.42151175831644588870e-7) * r
                    + 1.84631831751005468180e-5) * r + 7.86869131145613259100e-4) * r
                  + 1.48753612908506148525e-2) * r + 1.36929880922735805310e-1) * r
                + 5.99832206555887937690e-1) * r + 1.0)
    val = num / den
    return -val if q < 0 else val


# ---------------------------------------------------------------------- moments
def moments(x):
    """Return n, mean, sd(ddof=1), g1 (sample skewness, b1^0.5), g2 (excess kurt)."""
    n = len(x)
    m = sum(x) / n
    m2 = sum((v - m) ** 2 for v in x) / n
    m3 = sum((v - m) ** 3 for v in x) / n
    m4 = sum((v - m) ** 4 for v in x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1)) if n > 1 else 0.0
    if m2 <= 0:
        return n, m, sd, float('nan'), float('nan')
    g1 = m3 / m2 ** 1.5
    g2 = m4 / (m2 * m2) - 3.0
    return n, m, sd, g1, g2


def se_skew(n):
    """SE of g1 under normality (Fisher)."""
    return math.sqrt(6.0 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))


def se_kurt(n):
    """SE of g2 under normality (Fisher)."""
    return math.sqrt(24.0 * n * (n - 1) ** 2 / ((n - 3) * (n - 2) * (n + 3) * (n + 5)))


# ------------------------------------------------------- D'Agostino-Pearson K^2
def dagostino_k2(x):
    """
    Omnibus normality test. Z1 from D'Agostino (1970) skewness transform,
    Z2 from Anscombe & Glynn (1983) kurtosis transform, K2 = Z1^2 + Z2^2 ~ chi2_2.
    p = exp(-K2/2) is the EXACT chi-square-2df upper tail (closed form).
    Requires n >= 20 for the kurtosis transform to be trustworthy.
    """
    n, _, _, g1, g2 = moments(x)
    if n < 8 or not math.isfinite(g1):
        return None
    # --- skewness -> Z1
    Y = g1 * math.sqrt((n + 1) * (n + 3) / (6.0 * (n - 2)))
    beta2 = (3.0 * (n * n + 27 * n - 70) * (n + 1) * (n + 3) /
             ((n - 2) * (n + 5) * (n + 7) * (n + 9)))
    W2 = -1.0 + math.sqrt(2.0 * (beta2 - 1.0))
    W = math.sqrt(W2)
    delta = 1.0 / math.sqrt(math.log(W))
    alpha = math.sqrt(2.0 / (W2 - 1.0))
    t = Y / alpha
    Z1 = delta * math.log(t + math.sqrt(t * t + 1.0))
    # --- kurtosis -> Z2
    b2 = g2 + 3.0
    E = 3.0 * (n - 1) / (n + 1)
    varb2 = 24.0 * n * (n - 2) * (n - 3) / ((n + 1) ** 2 * (n + 3) * (n + 5))
    xx = (b2 - E) / math.sqrt(varb2)
    sqrtb1 = (6.0 * (n * n - 5 * n + 2) / ((n + 7) * (n + 9)) *
              math.sqrt(6.0 * (n + 3) * (n + 5) / (n * (n - 2) * (n - 3))))
    A = 6.0 + 8.0 / sqrtb1 * (2.0 / sqrtb1 + math.sqrt(1.0 + 4.0 / (sqrtb1 ** 2)))
    denom = 1.0 + xx * math.sqrt(2.0 / (A - 4.0))
    if denom <= 0:
        Z2 = float('inf') if xx > 0 else float('-inf')
    else:
        term = ((1.0 - 2.0 / A) / denom) ** (1.0 / 3.0)
        Z2 = ((1.0 - 2.0 / (9.0 * A)) - term) / math.sqrt(2.0 / (9.0 * A))
    if math.isinf(Z2):
        return {'K2': float('inf'), 'Z1': Z1, 'Z2': Z2, 'p': 0.0, 'g1': g1, 'g2': g2}
    K2 = Z1 * Z1 + Z2 * Z2
    p = math.exp(-K2 / 2.0)          # chi-square, 2 df -> exact closed form
    return {'K2': K2, 'Z1': Z1, 'Z2': Z2, 'p': p, 'g1': g1, 'g2': g2}


# ----------------------------------------------------------- Anderson-Darling
def anderson_darling(x):
    """
    A^2 for the composite normal hypothesis (mu, sigma estimated from the data).
    Small-sample correction A*^2 = A^2 (1 + 0.75/n + 2.25/n^2) and the
    D'Agostino & Stephens (1986) p-value approximation.
    """
    xs = sorted(x)
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in xs) / (n - 1))
    if sd <= 0:
        return None
    z = [(v - m) / sd for v in xs]
    S = 0.0
    for i in range(n):
        f1 = phi_cdf(z[i])
        f2 = phi_cdf(z[n - 1 - i])
        f1 = min(max(f1, 1e-300), 1 - 1e-16)
        s2 = max(phi_sf(z[n - 1 - i]), 1e-300)   # 1 - F, computed stably
        S += (2 * (i + 1) - 1) * (math.log(f1) + math.log(s2))
    A2 = -n - S / n
    Astar = A2 * (1.0 + 0.75 / n + 2.25 / (n * n))
    if Astar >= 0.6:
        p = math.exp(1.2937 - 5.709 * Astar + 0.0186 * Astar ** 2)
    elif Astar > 0.34:
        p = math.exp(0.9177 - 4.279 * Astar - 1.38 * Astar ** 2)
    elif Astar > 0.2:
        p = 1 - math.exp(-8.318 + 42.796 * Astar - 59.938 * Astar ** 2)
    else:
        p = 1 - math.exp(-13.436 + 101.14 * Astar - 223.73 * Astar ** 2)
    return {'A2': A2, 'Astar2': Astar, 'p': max(min(p, 1.0), 0.0)}


# --------------------------------------------------------------- Shapiro-Wilk
def _blom_scores(n):
    return [phi_ppf((i + 1 - 0.375) / (n + 0.25)) for i in range(n)]


def shapiro_wilk(x):
    """
    Shapiro-Wilk W and p, Royston (1995) AS R94. Valid 3 <= n <= 5000.
    """
    xs = sorted(x)
    n = len(xs)
    if n < 3:
        return None
    if n > 5000:
        return None
    m = _blom_scores(n)
    ssumm2 = sum(v * v for v in m)
    rsn = 1.0 / math.sqrt(n)
    c = [v / math.sqrt(ssumm2) for v in m]
    a = [0.0] * n
    if n > 5:
        an = (c[n - 1] + 0.221157 * rsn - 0.147981 * rsn ** 2 - 2.071190 * rsn ** 3
              + 4.434685 * rsn ** 4 - 2.706056 * rsn ** 5)
        an1 = (c[n - 2] + 0.042981 * rsn - 0.293762 * rsn ** 2 - 1.752461 * rsn ** 3
               + 5.682633 * rsn ** 4 - 3.582633 * rsn ** 5)
        phi = ((ssumm2 - 2.0 * m[n - 1] ** 2 - 2.0 * m[n - 2] ** 2) /
               (1.0 - 2.0 * an ** 2 - 2.0 * an1 ** 2))
        a[n - 1], a[0] = an, -an
        a[n - 2], a[1] = an1, -an1
        rt = math.sqrt(phi)
        for i in range(2, n - 2):
            a[i] = m[i] / rt
    else:
        an = (c[n - 1] + 0.221157 * rsn - 0.147981 * rsn ** 2 - 2.071190 * rsn ** 3
              + 4.434685 * rsn ** 4 - 2.706056 * rsn ** 5)
        phi = (ssumm2 - 2.0 * m[n - 1] ** 2) / (1.0 - 2.0 * an ** 2)
        a[n - 1], a[0] = an, -an
        rt = math.sqrt(phi)
        for i in range(1, n - 1):
            a[i] = m[i] / rt
    xbar = sum(xs) / n
    ssq = sum((v - xbar) ** 2 for v in xs)
    if ssq <= 0:
        return None
    num = sum(a[i] * xs[i] for i in range(n))
    W = num * num / ssq
    if W >= 1.0:
        W = 1.0 - 1e-15
    # --- p-value
    if n == 3:
        pi6 = 6.0 / math.pi
        stqr = math.asin(math.sqrt(0.75))
        p = pi6 * (math.asin(math.sqrt(W)) - stqr)
        return {'W': W, 'p': max(min(p, 1.0), 0.0), 'z': None}
    if n <= 11:
        gamma = -2.273 + 0.459 * n
        w = -math.log(gamma - math.log(1.0 - W))
        mu = 0.5440 - 0.39978 * n + 0.025054 * n ** 2 - 0.0006714 * n ** 3
        sigma = math.exp(1.3822 - 0.77857 * n + 0.062767 * n ** 2 - 0.0020322 * n ** 3)
    else:
        ln = math.log(n)
        w = math.log(1.0 - W)
        mu = -1.5861 - 0.31082 * ln - 0.083751 * ln ** 2 + 0.0038915 * ln ** 3
        sigma = math.exp(-0.4803 - 0.082676 * ln + 0.0030302 * ln ** 2)
    z = (w - mu) / sigma
    return {'W': W, 'p': phi_sf(z), 'z': z}


# ------------------------------------------------------------ Shapiro-Francia
def shapiro_francia(x):
    """
    W' = squared correlation between order statistics and Blom normal scores.
    p-value from Royston (1993), valid roughly 5 <= n <= 5000.
    (This is also Filliben's probability plot correlation, squared.)
    """
    xs = sorted(x)
    n = len(xs)
    if n < 5:
        return None
    m = _blom_scores(n)
    xbar = sum(xs) / n
    mbar = sum(m) / n
    sxm = sum((xs[i] - xbar) * (m[i] - mbar) for i in range(n))
    sxx = sum((v - xbar) ** 2 for v in xs)
    smm = sum((v - mbar) ** 2 for v in m)
    if sxx <= 0 or smm <= 0:
        return None
    r = sxm / math.sqrt(sxx * smm)
    W = r * r
    if W >= 1.0:
        W = 1.0 - 1e-15
    u = math.log(n)
    v = math.log(u)
    mu = -1.2725 + 1.0521 * (v - u)
    sigma = 1.0308 - 0.26758 * (v + 2.0 / u)
    z = (math.log(1.0 - W) - mu) / sigma
    return {'Wprime': W, 'r': r, 'p': phi_sf(z), 'z': z}


# ---------------------------------------------------------------- Jarque-Bera
def jarque_bera(x):
    n, _, _, g1, g2 = moments(x)
    if not math.isfinite(g1):
        return None
    JB = n / 6.0 * (g1 * g1 + g2 * g2 / 4.0)
    return {'JB': JB, 'p': math.exp(-JB / 2.0)}   # chi2_2 exact upper tail


# ------------------------------------------------------------- Q-Q diagnostics
def qq_tail_report(x):
    """
    Rank-based Q-Q comparison: standardise the data, then compare empirical
    quantiles with the N(0,1) quantiles they would equal under normality.
    Also returns max |deviation| on the standardised scale (a sup-norm Q-Q gap).
    """
    xs = sorted(x)
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in xs) / (n - 1))
    if sd <= 0:
        return None
    z = [(v - m) / sd for v in xs]
    theo = _blom_scores(n)
    maxdev = max(abs(z[i] - theo[i]) for i in range(n))
    out = {'max_qq_dev_sd': maxdev, 'min_z': z[0], 'max_z': z[-1]}
    for q in (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99):
        idx = min(n - 1, max(0, int(round(q * (n + 1))) - 1))
        out[f'emp_q{int(q*100)}'] = z[idx]
        out[f'thy_q{int(q*100)}'] = phi_ppf(q)
    return out


def n_distinct(x):
    return len(set(x))


def tie_fraction(x):
    """Fraction of observations that share their value with at least one other."""
    from collections import Counter
    c = Counter(x)
    tied = sum(v for v in c.values() if v > 1)
    return tied / len(x)
