"""
demo_metrics_viz.py
====================
Simple demo: Confusion Matrix + Performance Graphs
Works out-of-the-box with scikit-learn, matplotlib, seaborn.

Install deps (if needed):
    pip install scikit-learn matplotlib seaborn numpy
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns

from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    roc_curve, auc,
    precision_recall_curve,
    accuracy_score, precision_score, recall_score, f1_score
)

# ─────────────────────────────────────────────
# 1. Generate synthetic dataset
# ─────────────────────────────────────────────
CLASSES = ["Normal", "Fall Detected", "Near-Fall"]
N_CLASSES = len(CLASSES)

X, y = make_classification(
    n_samples=1000,
    n_features=10,
    n_informative=6,
    n_classes=N_CLASSES,
    n_clusters_per_class=1,
    random_state=42,
)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, stratify=y, random_state=42
)

# ─────────────────────────────────────────────
# 2. Train a simple model
# ─────────────────────────────────────────────
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)   # shape (n_samples, n_classes)

print(classification_report(y_test, y_pred, target_names=CLASSES))

# ─────────────────────────────────────────────
# 3. Helpers
# ─────────────────────────────────────────────
PALETTE = ["#4f46e5", "#06b6d4", "#f59e0b"]   # indigo / cyan / amber

def per_class_metrics(y_true, y_pred, n_classes):
    """Return per-class precision, recall, f1 arrays."""
    p = precision_score(y_true, y_pred, average=None, labels=range(n_classes))
    r = recall_score(y_true,    y_pred, average=None, labels=range(n_classes))
    f = f1_score(y_true,        y_pred, average=None, labels=range(n_classes))
    return p, r, f

# ─────────────────────────────────────────────
# 4. Figure layout
# ─────────────────────────────────────────────
fig = plt.figure(figsize=(18, 14), facecolor="#0f172a")
fig.suptitle("Model Performance Dashboard", fontsize=22, fontweight="bold",
             color="white", y=0.98)

gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.5, wspace=0.45)

ax_cm    = fig.add_subplot(gs[0:2, 0:2])   # Confusion Matrix (big, top-left)
ax_roc   = fig.add_subplot(gs[0, 2])       # ROC curve
ax_pr    = fig.add_subplot(gs[1, 2])       # Precision-Recall curve
ax_bar   = fig.add_subplot(gs[2, 0:2])     # Per-class bar chart
ax_hist  = fig.add_subplot(gs[2, 2])       # Cross-val accuracy distribution

# shared style
for ax in fig.get_axes():
    ax.set_facecolor("#1e293b")
    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")

# ─────────────────────────────────────────────
# 4a. Confusion Matrix
# ─────────────────────────────────────────────
cm = confusion_matrix(y_test, y_pred)
cm_pct = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100

annot = np.array(
    [[f"{cm[i,j]}\n({cm_pct[i,j]:.1f}%)" for j in range(N_CLASSES)]
     for i in range(N_CLASSES)]
)

sns.heatmap(
    cm_pct,
    ax=ax_cm,
    annot=annot, fmt="",
    cmap="YlOrRd",
    linewidths=1, linecolor="#0f172a",
    xticklabels=CLASSES, yticklabels=CLASSES,
    cbar_kws={"shrink": 0.8},
    annot_kws={"size": 11, "color": "white", "weight": "bold"},
)
ax_cm.set_title("Confusion Matrix", color="white", fontsize=14, pad=12)
ax_cm.set_xlabel("Predicted Label", color="#94a3b8", fontsize=10)
ax_cm.set_ylabel("True Label",      color="#94a3b8", fontsize=10)
ax_cm.tick_params(colors="white")

# ─────────────────────────────────────────────
# 4b. ROC curve (one-vs-rest per class)
# ─────────────────────────────────────────────
from sklearn.preprocessing import label_binarize
y_test_bin = label_binarize(y_test, classes=range(N_CLASSES))

for i, (cls, col) in enumerate(zip(CLASSES, PALETTE)):
    fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_prob[:, i])
    roc_auc = auc(fpr, tpr)
    ax_roc.plot(fpr, tpr, color=col, lw=2,
                label=f"{cls} (AUC={roc_auc:.2f})")

ax_roc.plot([0, 1], [0, 1], "w--", lw=1, alpha=0.4)
ax_roc.set_title("ROC Curve", color="white", fontsize=12)
ax_roc.set_xlabel("FPR", color="#94a3b8", fontsize=9)
ax_roc.set_ylabel("TPR", color="#94a3b8", fontsize=9)
ax_roc.legend(fontsize=7, labelcolor="white", facecolor="#1e293b",
              edgecolor="#334155")

# ─────────────────────────────────────────────
# 4c. Precision-Recall curve
# ─────────────────────────────────────────────
for i, (cls, col) in enumerate(zip(CLASSES, PALETTE)):
    prec, rec, _ = precision_recall_curve(y_test_bin[:, i], y_prob[:, i])
    pr_auc = auc(rec, prec)
    ax_pr.plot(rec, prec, color=col, lw=2,
               label=f"{cls} (AUC={pr_auc:.2f})")

ax_pr.set_title("Precision-Recall Curve", color="white", fontsize=12)
ax_pr.set_xlabel("Recall",    color="#94a3b8", fontsize=9)
ax_pr.set_ylabel("Precision", color="#94a3b8", fontsize=9)
ax_pr.legend(fontsize=7, labelcolor="white", facecolor="#1e293b",
             edgecolor="#334155")

# ─────────────────────────────────────────────
# 4d. Per-class bar chart (Precision / Recall / F1)
# ─────────────────────────────────────────────
prec_arr, rec_arr, f1_arr = per_class_metrics(y_test, y_pred, N_CLASSES)

x = np.arange(N_CLASSES)
w = 0.25
bars = [
    ax_bar.bar(x - w,  prec_arr, width=w, color="#4f46e5", label="Precision"),
    ax_bar.bar(x,      rec_arr,  width=w, color="#06b6d4", label="Recall"),
    ax_bar.bar(x + w,  f1_arr,   width=w, color="#f59e0b", label="F1-Score"),
]
for bar_group in bars:
    for bar in bar_group:
        h = bar.get_height()
        ax_bar.text(bar.get_x() + bar.get_width() / 2, h + 0.01,
                    f"{h:.2f}", ha="center", va="bottom",
                    color="white", fontsize=8)

ax_bar.set_xticks(x)
ax_bar.set_xticklabels(CLASSES, color="white")
ax_bar.set_ylim(0, 1.15)
ax_bar.set_title("Per-Class Metrics", color="white", fontsize=12)
ax_bar.set_ylabel("Score", color="#94a3b8", fontsize=9)
ax_bar.legend(fontsize=8, labelcolor="white", facecolor="#1e293b",
              edgecolor="#334155")

# ─────────────────────────────────────────────
# 4e. Cross-val accuracy histogram
# ─────────────────────────────────────────────
from sklearn.model_selection import cross_val_score

cv_scores = cross_val_score(
    RandomForestClassifier(n_estimators=50, random_state=42),
    X, y,
    cv=StratifiedKFold(n_splits=10, shuffle=True, random_state=42),
    scoring="accuracy"
)

ax_hist.hist(cv_scores, bins=6, color="#4f46e5", edgecolor="#0f172a",
             alpha=0.85)
ax_hist.axvline(cv_scores.mean(), color="#f59e0b", lw=2,
                label=f"Mean={cv_scores.mean():.3f}")
ax_hist.set_title("10-Fold CV Accuracy", color="white", fontsize=12)
ax_hist.set_xlabel("Accuracy", color="#94a3b8", fontsize=9)
ax_hist.set_ylabel("Count",    color="#94a3b8", fontsize=9)
ax_hist.legend(fontsize=8, labelcolor="white", facecolor="#1e293b",
               edgecolor="#334155")

# ─────────────────────────────────────────────
# 5. Overall accuracy watermark
# ─────────────────────────────────────────────
acc = accuracy_score(y_test, y_pred)
fig.text(0.01, 0.01,
         f"Overall Accuracy: {acc*100:.2f}%  |  Test samples: {len(y_test)}",
         color="#64748b", fontsize=9)

plt.savefig("metrics_dashboard.png", dpi=150,
            bbox_inches="tight", facecolor="#0f172a")
print("\n Saved -> metrics_dashboard.png")
plt.show()
