import re
import string
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

def normalize_text_for_wer(text: str) -> List[str]:
    """
    Normalizes transcript text by lowercasing and removing punctuation
    to compare word tokens fairly.
    """
    if not text:
        return []
    # Lowercase
    clean = text.lower()
    # Remove punctuation
    clean = re.sub(r'[{}]'.format(re.escape(string.punctuation)), ' ', clean)
    # Tokenize words
    words = [w.strip() for w in clean.split() if w.strip()]
    return words

def compute_wer_metrics(reference_text: str, hypothesis_text: str) -> Dict[str, Any]:
    """
    Computes exact Word Error Rate (WER) and classification of errors
    (Substitutions, Deletions, Insertions) using Dynamic Programming Levenshtein distance.
    
    Formula:
      WER = (S + D + I) / N_ref
      Accuracy = max(0.0, 1.0 - WER)
    """
    r_words = normalize_text_for_wer(reference_text)
    h_words = normalize_text_for_wer(hypothesis_text)

    n_ref = len(r_words)
    n_hyp = len(h_words)

    if n_ref == 0:
        if n_hyp == 0:
            return {
                "reference_words": 0,
                "hypothesis_words": 0,
                "substitutions": 0,
                "deletions": 0,
                "insertions": 0,
                "wer": 0.0,
                "accuracy": 1.0,
                "accuracy_percent": "100.0%"
            }
        return {
            "reference_words": 0,
            "hypothesis_words": n_hyp,
            "substitutions": 0,
            "deletions": 0,
            "insertions": n_hyp,
            "wer": 1.0,
            "accuracy": 0.0,
            "accuracy_percent": "0.0%"
        }

    # DP Matrix: dp[i][j] = (cost, substitutions, deletions, insertions)
    # i: 0..n_ref (reference prefix)
    # j: 0..n_hyp (hypothesis prefix)
    d = [[0] * (n_hyp + 1) for _ in range(n_ref + 1)]
    ops = [[(0, 0, 0)] * (n_hyp + 1) for _ in range(n_ref + 1)]

    # Base cases
    for i in range(1, n_ref + 1):
        d[i][0] = i
        ops[i][0] = (0, i, 0) # i deletions

    for j in range(1, n_hyp + 1):
        d[0][j] = j
        ops[0][j] = (0, 0, j) # j insertions

    for i in range(1, n_ref + 1):
        for j in range(1, n_hyp + 1):
            if r_words[i - 1] == h_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
                ops[i][j] = ops[i - 1][j - 1]
            else:
                sub_cost = d[i - 1][j - 1] + 1
                del_cost = d[i - 1][j] + 1
                ins_cost = d[i][j - 1] + 1

                min_cost = min(sub_cost, del_cost, ins_cost)
                d[i][j] = min_cost

                if min_cost == sub_cost:
                    prev_s, prev_d, prev_i = ops[i - 1][j - 1]
                    ops[i][j] = (prev_s + 1, prev_d, prev_i)
                elif min_cost == del_cost:
                    prev_s, prev_d, prev_i = ops[i - 1][j]
                    ops[i][j] = (prev_s, prev_d + 1, prev_i)
                else:
                    prev_s, prev_d, prev_i = ops[i][j - 1]
                    ops[i][j] = (prev_s, prev_d, prev_i + 1)

    final_cost = d[n_ref][n_hyp]
    subs, dels, inss = ops[n_ref][n_hyp]

    wer = round(final_cost / n_ref, 4)
    accuracy = round(max(0.0, 1.0 - wer), 4)

    return {
        "reference_words": n_ref,
        "hypothesis_words": n_hyp,
        "substitutions": subs,
        "deletions": dels,
        "insertions": inss,
        "total_errors": final_cost,
        "wer": wer,
        "accuracy": accuracy,
        "accuracy_percent": f"{round(accuracy * 100, 2)}%"
    }

def format_accuracy_report(benchmark_results: List[Dict[str, Any]]) -> str:
    """
    Formats benchmark results into a clean markdown table report.
    """
    headers = [
        "Recording", "Format", "Reference Words", "Hypothesis Words",
        "Substitutions", "Deletions", "Insertions", "WER", "Accuracy", "Target (>=90%)"
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |"
    ]

    for item in benchmark_results:
        passed = "PASS" if item["accuracy"] >= 0.90 else "FAIL"
        lines.append(
            f"| {item['recording']} | {item['format']} | {item['reference_words']} | "
            f"{item['hypothesis_words']} | {item['substitutions']} | {item['deletions']} | "
            f"{item['insertions']} | {item['wer']:.4f} | {item['accuracy_percent']} | **{passed}** |"
        )

    return "\n".join(lines)