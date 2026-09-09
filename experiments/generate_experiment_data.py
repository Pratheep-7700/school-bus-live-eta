"""
Generate experimental dataset for evaluating baseline vs proposed dynamic ETA models.
Generates data/eta_experiment.csv with 500+ simulated trips.
"""
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulator.data_generator import generate_experiment_dataset

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("Generating 550 Simulated Bus Trips for Experiment...")
    print("--------------------------------------------------")
    generate_experiment_dataset()
    print("Dataset generation complete: data/eta_experiment.csv")
