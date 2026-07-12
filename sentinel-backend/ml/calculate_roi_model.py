"""
Kavach -- ROI Model Calculator
Calculates the conservative/base/optimistic ROI ranges for IDBI Bank
based on the December 2025 MSME advances portfolio size of ₹22,826 crore.
"""

import numpy as np

def calculate_roi():
    # Fixed inputs (IDBI Bank Dec 2025 disclosures)
    portfolio_size_crore = 22826.0
    
    # Measured model performance metrics
    legacy_recall = 0.055       # Legacy loop-based threshold=0.50 recall
    sentinel_recall = 0.5207     # Calibrated unified model threshold=0.11 recall
    recall_improvement = sentinel_recall - legacy_recall # 46.57% net increase
    
    # Scenarios: Conservative, Base Case, Optimistic
    scenarios = ["Conservative", "Base Case", "Optimistic"]
    
    # Assumptions per scenario
    assumed_msme_npa_rates = [0.05, 0.07, 0.09]  # 5%, 7%, 9% baseline MSME NPA rates
    annual_slippage_rates = [0.015, 0.020, 0.025] # 1.5%, 2.0%, 2.5% standard loans slipping to NPA annually
    prevention_rates = [0.10, 0.15, 0.25]        # % of early-detected loans saved from NPA via proactive restructuring
    avg_provisioning_cost = 0.25                 # Average provision requirement for substandard restructured loans (25%)
    
    print("| Metric / Assumption | Conservative | Base Case | Optimistic |")
    print("| :--- | :---: | :---: | :---: |")
    print(f"| **Active MSME Advances Portfolio** | INR {portfolio_size_crore:,.0f} Cr | INR {portfolio_size_crore:,.0f} Cr | INR {portfolio_size_crore:,.0f} Cr |")
    
    # 1. Baseline NPA Rate
    print("| **Assumed MSME NPA Rate (%)** | {:.1f}% | {:.1f}% | {:.1f}% |".format(
        assumed_msme_npa_rates[0]*100, assumed_msme_npa_rates[1]*100, assumed_msme_npa_rates[2]*100))
    
    # 2. Annual Slippage Rate
    print("| **Annual Slippage-to-NPA Rate (%)** | {:.1f}% | {:.1f}% | {:.1f}% |".format(
        annual_slippage_rates[0]*100, annual_slippage_rates[1]*100, annual_slippage_rates[2]*100))
    
    # 3. Projected Annual NPA Slippage (₹ Crore)
    slippages = [portfolio_size_crore * rate for rate in annual_slippage_rates]
    print("| **Projected Annual NPA Slippage (INR)** | INR {:.2f} Cr | INR {:.2f} Cr | INR {:.2f} Cr |".format(
        slippages[0], slippages[1], slippages[2]))
    
    # 4. Net Recall Improvement
    print("| **Sentinel Recall Lift over Legacy** | {:.2f}% | {:.2f}% | {:.2f}% |".format(
        recall_improvement*100, recall_improvement*100, recall_improvement*100))
    
    # 5. Proactive Mitigation/Cure Rate
    print("| **Early-Flagged Prevention Rate (%)** | {:.1f}% | {:.1f}% | {:.1f}% |".format(
        prevention_rates[0]*100, prevention_rates[1]*100, prevention_rates[2]*100))
    
    # 6. Saved Slippage to NPA (₹ Crore)
    # Saved = Annual Slippage * Recall Lift * Prevention Rate
    saved_slippages = [slippage * recall_improvement * prev_rate for slippage, prev_rate in zip(slippages, prevention_rates)]
    print("| **Prevented Annual NPA Slippages (INR)** | **INR {:.2f} Cr** | **INR {:.2f} Cr** | **INR {:.2f} Cr** |".format(
        saved_slippages[0], saved_slippages[1], saved_slippages[2]))
    
    # 7. Provisioning Cost Savings (₹ Crore)
    # Savings = Saved Slippage * Provisioning Rate (25%)
    provision_savings = [saved * avg_provisioning_cost for saved in saved_slippages]
    print("| **Direct Provisioning Savings (INR)** | **INR {:.2f} Cr** | **INR {:.2f} Cr** | **INR {:.2f} Cr** |".format(
        provision_savings[0], provision_savings[1], provision_savings[2]))
        
    # 8. Cumulative 3-Year Credit Savings (₹ Crore)
    cumulative_savings = [(saved + prov) * 3 for saved, prov in zip(saved_slippages, provision_savings)]
    print("| **Total Cumulative 3-Year Savings (INR)** | **INR {:.2f} Cr** | **INR {:.2f} Cr** | **INR {:.2f} Cr** |".format(
        cumulative_savings[0], cumulative_savings[1], cumulative_savings[2]))

if __name__ == "__main__":
    calculate_roi()
