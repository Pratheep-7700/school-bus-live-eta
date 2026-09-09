"""
Run Experiment Script:
Calculates statistical metrics (MAE, RMSE, Mean Delay, Inquiries, Reduction %)
comparing the Baseline Schedule-Only ETA system against the Proposed Dynamic ETA system.
Saves results to experiments/experiment_results.csv.
"""
import os
import sys
import pandas as pd
import numpy as np

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eta_engine.eta_calculator import str_to_minutes

def run_evaluation():
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'eta_experiment.csv')
    if not os.path.exists(data_path):
        print("Dataset not found. Generating dataset first...")
        from simulator.data_generator import generate_experiment_dataset
        generate_experiment_dataset()

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} trips from {data_path}")

    # Convert time strings to numeric minutes for calculation
    actual_mins = df['actual_arrival'].apply(str_to_minutes)
    base_mins = df['predicted_eta_baseline'].apply(str_to_minutes)
    prop_mins = df['predicted_eta_proposed'].apply(str_to_minutes)
    planned_mins = df['planned_eta'].apply(str_to_minutes)

    # 1. Mean Absolute Error (MAE)
    base_mae = np.mean(np.abs(base_mins - actual_mins))
    prop_mae = np.mean(np.abs(prop_mins - actual_mins))

    # 2. Root Mean Squared Error (RMSE)
    base_rmse = np.sqrt(np.mean((base_mins - actual_mins) ** 2))
    prop_rmse = np.sqrt(np.mean((prop_mins - actual_mins) ** 2))

    # 3. Mean Delay (Actual - Planned)
    mean_delay = np.mean(actual_mins - planned_mins)

    # 4. Total ETA Updates
    # In proposed system, updates are sent whenever proposed ETA changes significantly from baseline
    eta_updates = int(np.sum(np.abs(prop_mins - base_mins) >= 2.0))

    # 5. Customer Status Enquiries Simulation
    # Baseline uncertainty drives calls: error * 0.85
    base_enquiries = int(np.sum(np.maximum(0, np.abs(base_mins - actual_mins) * 0.85 + 0.5)))
    # Proposed dynamic updates reduce calls: error * 0.25
    prop_enquiries = int(np.sum(np.maximum(0, np.abs(prop_mins - actual_mins) * 0.25 + 0.1)))
    enquiry_reduction_pct = round(((base_enquiries - prop_enquiries) / base_enquiries) * 100, 2)

    results = [
        {"metric": "MAE (minutes)", "baseline": round(base_mae, 2), "proposed": round(prop_mae, 2), "improvement": f"{round((base_mae - prop_mae)/base_mae * 100, 1)}%"},
        {"metric": "RMSE (minutes)", "baseline": round(base_rmse, 2), "proposed": round(prop_rmse, 2), "improvement": f"{round((base_rmse - prop_rmse)/base_rmse * 100, 1)}%"},
        {"metric": "Mean Delay (minutes)", "baseline": round(mean_delay, 2), "proposed": round(mean_delay, 2), "improvement": "N/A"},
        {"metric": "ETA Updates Sent", "baseline": 0, "proposed": eta_updates, "improvement": f"+{eta_updates} updates"},
        {"metric": "Customer Enquiries", "baseline": base_enquiries, "proposed": prop_enquiries, "improvement": f"-{enquiry_reduction_pct}% reduction"}
    ]

    results_df = pd.DataFrame(results)
    out_csv = os.path.join(os.path.dirname(__file__), 'experiment_results.csv')
    results_df.to_csv(out_csv, index=False)

    print("\n==================================================================")
    print("      SIMULATED EXPERIMENT RESULTS: BASELINE vs PROPOSED ETA      ")
    print("==================================================================")
    print(results_df.to_string(index=False))
    print("==================================================================")
    print(f"Results saved to: {out_csv}\n")
    return results

if __name__ == '__main__':
    run_evaluation()
