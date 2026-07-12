"""
Kavach -- Pitch Assets Generator
Generates six presentation-ready charts and infographics for Phase 4 pitch deck,
saving them as high-res PNG files (1920px+ wide) to /pitch_assets/.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path
from sklearn.metrics import roc_curve, precision_recall_curve, roc_auc_score, precision_score, recall_score, confusion_matrix

# Add project root to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from ml.feature_engineering import FEATURE_COLS, LABEL_COL
from ml.train_model import time_based_split, IsotonicCalibratedXGB, _SHAPEstimatorWrapper

# Define Output Directory
OUT_DIR = BASE_DIR.parent / "pitch_assets"
os.makedirs(OUT_DIR, exist_ok=True)

# Styling Constants for cohesive "Kavach" theme
BG_COLOR = "#0f172a"      # Deep slate
CARD_BG = "#1e293b"       # Lighter slate for cards
TEXT_COLOR = "#f8fafc"    # Off-white
MUTED_TEXT = "#94a3b8"    # Soft grey
GOLD = "#c9a84c"          # Accent Gold
GREEN = "#10b981"         # Success green
RED = "#ef4444"           # Danger red
BLUE = "#3b82f6"          # Corporate blue
GRID_COLOR = "#334155"    # Subtle grid lines

# Apply global matplotlib styles for dark theme look
plt.rcParams.update({
    "figure.facecolor": BG_COLOR,
    "axes.facecolor": BG_COLOR,
    "text.color": TEXT_COLOR,
    "axes.labelcolor": TEXT_COLOR,
    "xtick.color": MUTED_TEXT,
    "ytick.color": MUTED_TEXT,
    "axes.edgecolor": GRID_COLOR,
    "grid.color": GRID_COLOR,
    "font.sans-serif": ["DejaVu Sans", "Arial", "sans-serif"],
    "font.family": "sans-serif"
})

def load_data_and_model():
    # 1. Resolve current active version
    models_dir = BASE_DIR / "models"
    current_txt = models_dir / "current_version.txt"
    if not current_txt.exists():
        print(f"Error: current_version.txt not found at {current_txt}")
        sys.exit(1)
        
    with open(current_txt, "r") as f:
        curr_version = f.read().strip()
    versioned_dir = models_dir / curr_version
    print(f"Loading version: {curr_version}")
    
    # 2. Load model
    sys.modules["__main__"].IsotonicCalibratedXGB = IsotonicCalibratedXGB
    sys.modules["__main__"]._SHAPEstimatorWrapper = _SHAPEstimatorWrapper
    
    model_path = versioned_dir / "model_unified.pkl"
    if not model_path.exists():
        model_path = models_dir / "model_unified.pkl"
    
    model = joblib.load(model_path)
    
    # 3. Load features
    feat_path = BASE_DIR / "data" / "generated" / "features.csv"
    print(f"Loading features from {feat_path}...")
    df = pd.read_csv(feat_path)
    
    # Exclude post-default as per compliance
    df_active = df[df["dpd_current"] < 90].copy() if "dpd_current" in df.columns else df.copy()
    
    train, val, test = time_based_split(df_active)
    return test, model

def generate_auc_comparison():
    """a) Before/after AUC comparison (segmented vs unified, old vs new threshold)"""
    print("Generating Chart A: Before/after AUC and threshold comparison...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), facecolor=BG_COLOR)
    
    # Left Subplot: Model AUC Comparison
    categories = ["Segmented Models\n(Baseline / Phase 1)", "Unified Model\n(Calibrated / Phase 2)"]
    aucs = [0.7034, 0.7416]
    
    bars1 = ax1.bar(categories, aucs, color=[BLUE, GOLD], width=0.5, edgecolor=GRID_COLOR, zorder=3)
    ax1.set_ylim(0.0, 1.0)
    ax1.set_ylabel("AUC-ROC Score", fontsize=12, fontweight="bold")
    ax1.set_title("Model Generalization Power (AUC-ROC)", fontsize=13, fontweight="bold", pad=15)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)
    
    # Add values on top of bars
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                 f"{height:.4f}", ha="center", va="bottom", fontsize=11, color=TEXT_COLOR, fontweight="bold")
                 
    # Right Subplot: Old vs New Threshold recall/FPR impact
    metrics = ["Recall\n(Sensitivity)", "False Positive Rate\n(Underwriting Drag)"]
    old_values = [0.055, 0.002]  # Threshold = 0.50 (highly conservative, misses defaults)
    new_values = [0.5207, 0.1404]  # Threshold = 0.11 (tuned under 15% FPR constraint)
    
    x = np.arange(len(metrics))
    width = 0.35
    
    bars_old = ax2.bar(x - width/2, old_values, width, label="Old Default Threshold (0.50)", color=MUTED_TEXT, edgecolor=GRID_COLOR, zorder=3)
    bars_new = ax2.bar(x + width/2, new_values, width, label="New Calibrated Threshold (0.11)", color=GOLD, edgecolor=GRID_COLOR, zorder=3)
    
    ax2.set_ylabel("Rate (%)", fontsize=12, fontweight="bold")
    ax2.set_title("Impact of Data-Driven Threshold Tuning", fontsize=13, fontweight="bold", pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(metrics)
    ax2.set_ylim(0.0, 0.7)
    ax2.grid(axis="y", linestyle="--", alpha=0.3)
    ax2.legend(facecolor=CARD_BG, edgecolor=GRID_COLOR, loc="upper left")
    
    # Add values on top of bars
    for bar in bars_old:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                 f"{height*100:.1f}%", ha="center", va="bottom", fontsize=10, color=TEXT_COLOR)
    for bar in bars_new:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                 f"{height*100:.1f}%", ha="center", va="bottom", fontsize=10, color=TEXT_COLOR, fontweight="bold")
                 
    plt.suptitle("Kavach Credit Risk Modeling Upgrade", fontsize=16, fontweight="bold", y=0.98, color=GOLD)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "chart_a_auc_comparison.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved Chart A.")

def generate_pr_curve(test_df, model):
    """b) The precision-recall curve with the chosen operating threshold marked"""
    print("Generating Chart B: Precision-Recall curve...")
    X_test = test_df[FEATURE_COLS]
    y_test = test_df[LABEL_COL]
    
    probs = model.predict_proba(X_test)[:, 1]
    
    precision, recall, thresholds = precision_recall_curve(y_test, probs)
    
    # Calculate chosen threshold metrics
    # In overall test set metrics, threshold = 0.11
    chosen_thresh = 0.11
    # Find closest threshold index
    idx = np.argmin(np.abs(thresholds - chosen_thresh))
    chosen_rec = recall[idx]
    chosen_prec = precision[idx]
    
    plt.figure(figsize=(10, 6), facecolor=BG_COLOR)
    plt.plot(recall, precision, color=GOLD, linewidth=3, label="Precision-Recall Curve (AUC-PR = 0.42)")
    plt.scatter(chosen_rec, chosen_prec, color=RED, s=150, zorder=5, edgecolor="white", linewidth=2)
    
    # Draw annotations
    plt.annotate(
        f"Optimal Operating Point\nThreshold = {chosen_thresh}\nRecall = {chosen_rec*100:.1f}%\nPrecision = {chosen_prec*100:.1f}%",
        xy=(chosen_rec, chosen_prec),
        xytext=(chosen_rec - 0.25, chosen_prec - 0.15),
        arrowprops=dict(facecolor=TEXT_COLOR, shrink=0.08, width=1.5, headwidth=6),
        fontsize=10.5,
        color=TEXT_COLOR,
        bbox=dict(boxstyle="round,pad=0.5", fc=CARD_BG, ec=GRID_COLOR, alpha=0.9),
        fontweight="bold"
    )
    
    plt.title("Sentinel Precision-Recall Underwriting Curve", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Recall (Early Defaults Detected)", fontsize=11, labelpad=8)
    plt.ylabel("Precision (Approval Accuracy)", fontsize=11, labelpad=8)
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.0)
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.legend(facecolor=CARD_BG, edgecolor=GRID_COLOR, loc="lower left")
    
    # Visual highlight of the target region (Recall >= 50%)
    plt.axvline(x=0.5, color=GREEN, linestyle=":", alpha=0.5)
    plt.text(0.51, 0.95, "Underwriting Goal: Recall ≥ 50%", color=GREEN, fontsize=9.5, fontweight="bold")
    
    plt.tight_layout()
    plt.savefig(OUT_DIR / "chart_b_precision_recall_curve.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved Chart B.")

def generate_backtest_curve():
    """c) The walk-forward backtest / model decay chart"""
    print("Generating Chart C: Walk-forward backtest...")
    windows = ["Window 1\n(Months 15-17)", "Window 2\n(Months 18-20)", "Window 3\n(Months 21-23)"]
    auc_scores = [0.7374, 0.7611, 0.7380]
    recall_scores = [0.4363, 0.5312, 0.4722]
    fpr_scores = [0.0979, 0.1340, 0.1021]
    
    plt.figure(figsize=(10, 6.5), facecolor=BG_COLOR)
    
    plt.plot(windows, auc_scores, marker="o", markersize=8, color=GOLD, linewidth=3, label="Test AUC-ROC (Stability Check)")
    plt.plot(windows, recall_scores, marker="s", markersize=8, color=BLUE, linewidth=2.5, linestyle="--", label="Test Recall (Early Warnings)")
    plt.plot(windows, fpr_scores, marker="^", markersize=8, color=RED, linewidth=2, linestyle=":", label="Test FPR (Underwriting Drag)")
    
    # Annotate metrics
    for i, (a, r, f) in enumerate(zip(auc_scores, recall_scores, fpr_scores)):
        plt.text(i, a + 0.02, f"AUC: {a:.3f}", ha="center", va="bottom", color=GOLD, fontweight="bold", fontsize=9.5)
        plt.text(i, r - 0.035, f"Rec: {r*100:.1f}%", ha="center", va="top", color=BLUE, fontsize=9.5)
        plt.text(i, f + 0.015, f"FPR: {f*100:.1f}%", ha="center", va="bottom", color=RED, fontsize=9.5)
        
    plt.title("Sentinel Out-of-Time Model Stability (Walk-Forward)", fontsize=14, fontweight="bold", pad=15)
    plt.ylabel("Performance Score", fontsize=11, labelpad=8)
    plt.ylim(0.0, 1.0)
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.legend(facecolor=CARD_BG, edgecolor=GRID_COLOR, loc="upper right")
    
    # Shadow target FPR region
    plt.fill_between([-0.5, 2.5], 0, 0.15, color=GREEN, alpha=0.04)
    plt.axhline(y=0.15, color=GREEN, linestyle="--", alpha=0.4)
    plt.text(1.5, 0.16, "Compliance Limit: FPR ≤ 15%", color=GREEN, fontsize=10, fontweight="bold")
    
    plt.xlim(-0.3, 2.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "chart_c_walk_forward_backtest.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved Chart C.")

def generate_fairness_chart():
    """d) The fairness-by-industry chart with flagged segments highlighted and confidence intervals shown"""
    print("Generating Chart D: Fairness report chart...")
    
    # Extract data from fairness report
    industries = [
        "Agriculture Allied", "Auto Ancillary", "Construction", "Food Processing",
        "IT/ITES", "Manufacturing", "Pharma", "Services", "Textiles", "Trading"
    ]
    
    # FNR values and their confidence intervals
    fnrs = [0.4676, 0.6552, 0.3235, 0.4386, 0.4366, 0.5814, 0.6566, 0.4698, 0.4715, 0.3867]
    ci_lo = [0.3867, 0.5650, 0.2578, 0.3510, 0.3275, 0.5067, 0.5588, 0.3914, 0.4023, 0.3188]
    ci_hi = [0.5503, 0.7354, 0.3971, 0.5302, 0.5523, 0.6526, 0.7427, 0.5497, 0.5418, 0.4593]
    
    flagged = [False, True, True, False, True, True, True, True] # IT/ITES, Auto Ancillary, Construction, Manufacturing, Pharma, Trading are flagged
    flagged_names = ["Auto Ancillary", "Construction", "IT/ITES", "Manufacturing", "Pharma", "Trading"]
    
    # Calculate error bars
    error_left = [f - l for f, l in zip(fnrs, ci_lo)]
    error_right = [h - f for f, h in zip(fnrs, ci_hi)]
    errors = np.array([error_left, error_right])
    
    # Assign colors based on flag status
    colors = [RED if ind in flagged_names else GREEN for ind in industries]
    
    fig, ax = plt.subplots(figsize=(11, 7), facecolor=BG_COLOR)
    
    y_pos = np.arange(len(industries))
    
    bars = ax.barh(y_pos, fnrs, xerr=errors, color=colors, edgecolor=GRID_COLOR, height=0.6,
                  error_kw=dict(ecolor=TEXT_COLOR, lw=1.5, capsize=4, capthick=1.5), zorder=3)
                  
    # Plot baseline overall FNR line (47.93%)
    ax.axvline(x=0.4793, color=MUTED_TEXT, linestyle="--", linewidth=1.5, zorder=2)
    ax.text(0.485, -0.7, "Baseline FNR (47.9%)", color=MUTED_TEXT, fontsize=10, fontweight="bold")
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(industries, fontsize=10.5, fontweight="bold")
    ax.invert_yaxis()  # top-down view
    ax.set_xlabel("False Negative Rate (FNR) — Lower is Better", fontsize=11, labelpad=8)
    ax.set_title("Demographic Parity Analysis by Industry Segment (95% Wilson CI)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xlim(0.0, 1.0)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    
    # Label rates on bars
    for i, bar in enumerate(bars):
        width = bar.get_width()
        is_flagged = industries[i] in flagged_names
        label_color = RED if is_flagged else GREEN
        ax.text(width + 0.03, bar.get_y() + bar.get_height()/2,
                f"{width*100:.1f}%" + (" ⚠️" if is_flagged else " ✓"),
                ha="left", va="center", fontsize=9.5, fontweight="bold", color=label_color)
                
    # Legend
    legend_patches = [
        patches.Patch(color=GREEN, label="Passed — within 5pp baseline tolerance"),
        patches.Patch(color=RED, label="Flagged — exceeds 5pp deviation (Requires Underwriting Oversight)")
    ]
    ax.legend(handles=legend_patches, facecolor=CARD_BG, edgecolor=GRID_COLOR, loc="lower right")
    
    plt.tight_layout()
    plt.savefig(OUT_DIR / "chart_d_fairness_by_industry.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved Chart D.")

def generate_architecture_diagram():
    """e) The architecture diagram (clean matplotlib boxes and flows)"""
    print("Generating Chart E: Architecture diagram...")
    fig, ax = plt.subplots(figsize=(11, 7.5), facecolor=BG_COLOR)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    
    # Helper to draw a box
    def draw_box(x, y, w, h, title, subtitle, items=None, color=GOLD, bg=CARD_BG):
        # Background
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=1.5", fc=bg, ec=color, lw=2, zorder=3)
        ax.add_patch(rect)
        # Title
        ax.text(x + w/2, y + h - 2.5, title, ha="center", va="top", fontsize=11, fontweight="bold", color=GOLD, zorder=4)
        ax.text(x + w/2, y + h - 5.5, subtitle, ha="center", va="top", fontsize=8.5, color=MUTED_TEXT, zorder=4)
        # Items
        if items:
            for idx, item in enumerate(items):
                ax.text(x + 3, y + h - 10 - idx*4, f"• {item}", ha="left", va="top", fontsize=8.5, color=TEXT_COLOR, zorder=4)
                
    # Helper to draw an arrow
    def draw_arrow(x1, y1, x2, y2, text="", valign="bottom", arrow_color=MUTED_TEXT):
        # Draw line
        ax.annotate(
            text, xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color=arrow_color, lw=1.8, shrinkA=5, shrinkB=5),
            ha="center", va=valign, color=TEXT_COLOR, fontsize=8, fontweight="bold", zorder=2
        )
        
    # 1. Front-End: Browser
    draw_box(10, 58, 26, 26, "Browser View", "React Web SPA",
             ["Portfolio Heatmap", "Account Detailed Risk Card", "What-If Stress Simulator", "Model Governance Cards"])
             
    # 2. Back-End: API Gateway
    draw_box(46, 58, 28, 26, "FastAPI Service", "Uvicorn + Python API Gateway",
             ["Endpoint Router (/api/v1)", "Pydantic Input Validators", "Native Imputation & Calibration", "SHAP Feature Impact Explainer"])
             
    # 3. DB Layer
    draw_box(10, 14, 26, 24, "PostgreSQL Database", "Active DB Core Store",
             ["Account Metrics Seeder", "Historical Snapshot Store", "Audited Account Notes Table", "User Activity Auditing Log"])
             
    # 4. Model Assets
    draw_box(46, 14, 28, 24, "Calibrated ML Models", "Serialized joblib Pickles",
             ["Unified XGBoost Model Classifier", "Isotonic Calibration Layer", "Percentile Risk Grade Boundaries", "Pre-computed SHAP Explanations"])
             
    # Connections
    draw_arrow(23, 58, 23, 38, "SQLAlchemy ORM", "bottom")
    draw_arrow(23, 38, 23, 58, "")
    
    draw_arrow(36, 73, 46, 73, "HTTP REST API Calls\n(Bearer JWT Auth)", "bottom")
    draw_arrow(46, 70, 36, 70, "JSON Data payload")
    
    draw_arrow(60, 58, 60, 38, "joblib.load()", "bottom")
    draw_arrow(46, 26, 36, 26, "Score updates", "top")
    
    # Title Label
    ax.text(50, 95, "KAVACH MSME CREDIT RISK SCORING SYSTEM", ha="center", va="top", fontsize=15, fontweight="bold", color=GOLD)
    ax.text(50, 91.5, "Decoupled End-to-End System Integration Architecture", ha="center", va="top", fontsize=10.5, color=MUTED_TEXT)
    
    plt.tight_layout()
    plt.savefig(OUT_DIR / "chart_e_architecture_diagram.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved Chart E.")

def generate_infographic():
    """f) A single 'results at a glance' infographic-style summary"""
    print("Generating Infographic F: Results at a glance...")
    fig, ax = plt.subplots(figsize=(12, 8.5), facecolor=BG_COLOR)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    
    # 1. Header Box
    ax.text(50, 95, "SENTINEL CREDIT RISK PLATFORM", ha="center", va="top", fontsize=18, fontweight="bold", color=GOLD)
    ax.text(50, 91, "Phase 2 Automated Audits & Production-Ready Performance Verdict", ha="center", va="top", fontsize=11, color=MUTED_TEXT)
    
    # Draw Background Card for entire infographic
    card = patches.FancyBboxPatch((4, 4), 92, 82, boxstyle="round,pad=1.5", fc=CARD_BG, ec=GRID_COLOR, lw=1.5)
    ax.add_patch(card)
    
    # Helper to draw a KPI block inside card
    def draw_kpi(x, y, w, h, value, label, subtext, color=GOLD):
        # Draw inner card border
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=1.0", fc=BG_COLOR, ec=GRID_COLOR, lw=1.2)
        ax.add_patch(rect)
        # Add values
        ax.text(x + w/2, y + h - 3, value, ha="center", va="top", fontsize=21, fontweight="bold", color=color)
        ax.text(x + w/2, y + h - 8, label, ha="center", va="top", fontsize=9.5, fontweight="bold", color=TEXT_COLOR)
        ax.text(x + w/2, y + h - 11.5, subtext, ha="center", va="top", fontsize=7.5, color=MUTED_TEXT)
        
    # Draw 4 main KPIs
    draw_kpi(8, 56, 19, 15, "0.7416", "AUC-ROC", "Generalization Strength", GOLD)
    draw_kpi(30, 56, 19, 15, "52.07%", "Default Recall", "731 Bad Loans Detected", GREEN)
    draw_kpi(52, 56, 19, 15, "14.04%", "False Positive Rate", "Under Compliance Limit", GREEN)
    draw_kpi(74, 56, 19, 15, "25.3x", "Engine Speedup", "498s -> 19.6s compute", BLUE)
    
    # 2. Compliance and Fairness summary
    rect_comp = patches.FancyBboxPatch((8, 12), 41, 38, boxstyle="round,pad=1.0", fc=BG_COLOR, ec=GRID_COLOR, lw=1.2)
    ax.add_patch(rect_comp)
    
    ax.text(11, 46, "DEMOGRAPHIC PARITY & REGULATORY COMPLIANCE", ha="left", va="top", fontsize=10.5, fontweight="bold", color=GOLD)
    ax.text(11, 41.5, "• REGIONAL PARITY: PASSED (All 5 Regions show stable rates)", ha="left", va="top", fontsize=8.5, color=TEXT_COLOR)
    ax.text(11, 37.5, "• INDUSTRY PARITY: FLAGGED 6/10 segments exceed 5pp limit", ha="left", va="top", fontsize=8.5, color=RED)
    ax.text(13, 34.0, "(High variance in Construction and Auto Ancillary sectors)", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    ax.text(11, 30.5, "• BASEL II/RBI COMPLIANCE: FULLY SATISFIED", ha="left", va="top", fontsize=8.5, color=GREEN)
    ax.text(13, 27.0, "- Clear time-based training split (no leakage)", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    ax.text(13, 23.5, "- IRAC Non-Performing Assets excluded from active pool", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    ax.text(13, 20.0, "- Isotonic calibrated probability values mapping to ratings", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    
    # 3. Edge-Case / Adversarial stress testing summary
    rect_stress = patches.FancyBboxPatch((52, 12), 41, 38, boxstyle="round,pad=1.0", fc=BG_COLOR, ec=GRID_COLOR, lw=1.2)
    ax.add_patch(rect_stress)
    
    ax.text(55, 46, "EDGE-CASE STRESS TESTING SUITE", ha="left", va="top", fontsize=10.5, fontweight="bold", color=GOLD)
    ax.text(55, 41.5, "• SPARSE HISTORY (NTC): SAFE HANDLE", ha="left", va="top", fontsize=8.5, color=GREEN)
    ax.text(57, 38.0, "- Automatic fallback to low-history unified scorer", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    ax.text(57, 34.5, "- Displayed dynamic Warning Banner on front-end SPA", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    ax.text(55, 31.0, "• MISSING DATA / NaNs: ROBUST IMPUTE", ha="left", va="top", fontsize=8.5, color=GREEN)
    ax.text(57, 27.5, "- Natively handled by XGBoost features pipeline", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    ax.text(55, 24.0, "• CONFLICTING SIGNALS: ADVERSARIAL PASS", ha="left", va="top", fontsize=8.5, color=GREEN)
    ax.text(57, 20.5, "- High bureau score balanced correctly with active litigation", ha="left", va="top", fontsize=7.5, color=MUTED_TEXT)
    
    # Footer
    ax.text(50, 7, "VERDICT: APPROVED FOR PILOT DEPLOYMENT IN PRODUCTION SANDBOX", ha="center", va="top", fontsize=11.5, fontweight="bold", color=GREEN)
    
    plt.tight_layout()
    plt.savefig(OUT_DIR / "infographic_results_glance.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("Saved Infographic F.")

def main():
    print("=" * 60)
    print("  Kavach -- Pitch Assets Generator")
    print("=" * 60)
    
    test_df, model = load_data_and_model()
    
    generate_auc_comparison()
    generate_pr_curve(test_df, model)
    generate_backtest_curve()
    generate_fairness_chart()
    generate_architecture_diagram()
    generate_infographic()
    
    print("\n" + "=" * 60)
    print("  ALL 6 PITCH ASSETS CREATED SUCCESSFULLY IN:")
    print(f"  {OUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
