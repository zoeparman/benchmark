import numpy as np
from scipy import stats
import warnings


def wilcoxon_tests(df, inverted):
    pvalues, effect_sizes = {}, {}
    for method_name in df:
        method_results = df[method_name].to_numpy()
        statistic, pvalue = stats.wilcoxon(
            method_results, alternative="less" if inverted else "greater"
        )
        pvalues[method_name] = pvalue
        effect_sizes[method_name] = np.median(method_results)
    return effect_sizes, pvalues


def corrcoef(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Calculates row-wise correlations between two arrays.
    :param a: first set of row vectors (shape: [num_rows, num_measurements])
    :param b: second set of row vectors (shape: [num_rows, num_measurements])
    :return: row-wise correlations between a and b (shape: [num_rows])
    """
    # Subtract mean
    # [batch_size, num_observations]
    a -= a.mean(axis=1, keepdims=True)
    b -= b.mean(axis=1, keepdims=True)
    # Calculate numerator
    # [batch_size]
    cov = (a * b).sum(axis=1)
    # Calculate denominator
    # [batch_size]
    denom = np.sqrt((a**2).sum(axis=1)) * np.sqrt((b**2).sum(axis=1))
    denom_zero = denom == 0.0
    if np.any(denom_zero):
        warnings.warn("Zero standard deviation detected.")
    corrcoefs = np.divide(cov, denom, out=np.zeros_like(cov), where=denom != 0)
    return corrcoefs
