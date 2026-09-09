# Experiment Methodology

This document details the simulation parameters and math formulas used to evaluate system performance.

## Simulation Dataset Parameters

We generated `eta_experiment.csv` (located in the `data/` directory) containing **550 simulated bus runs** with variable parameters:
- **Attendance**: Randomly distributed present students (from 0 to 11).
- **Traffic level**: Low (50%), Medium (30%), High (20%).
- **Telemetry outages**: GPS failures (5%) and network outages (5%).

## Performance Evaluation Formulas

1. **Mean Absolute Error (MAE)**:
   Measures the average magnitude of prediction errors:
   $$MAE = \frac{1}{N} \sum_{i=1}^{N} | \text{Predicted ETA}_i - \text{Actual Arrival}_i |$$

2. **Root Mean Squared Error (RMSE)**:
   Penalizes larger prediction errors:
   $$RMSE = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (\text{Predicted ETA}_i - \text{Actual Arrival}_i)^2}$$

3. **Mean Delay**:
   Average actual delay added during transit:
   $$\text{Mean Delay} = \frac{1}{N} \sum_{i=1}^{N} (\text{Actual Arrival}_i - \text{Planned Time}_i)$$

## Customer Status Enquiries Simulation

Parents and students are simulated to make status inquiries (phone calls or messages) based on uncertainty and ETA errors:
- **Baseline System (No updates)**:
  Parents receive no updates. The volume of calls increases dramatically with the size of the actual delay:
  $$\text{Enquiries}_{\text{baseline}} \sim \text{Poisson}(\text{Baseline Error} \times 0.8 + 0.5)$$
- **Proposed System (Live updates)**:
  Parents see live dynamic ETAs supported by explanations. Calls are minimal even during delays because the uncertainty is removed:
  $$\text{Enquiries}_{\text{proposed}} \sim \text{Poisson}(\text{Proposed Error} \times 0.2 + 0.1)$$

The resulting call reduction is calculated as:
$$\text{Reduction (\%)} = \frac{\text{Enquiries}_{\text{baseline}} - \text{Enquiries}_{\text{proposed}}}{\text{Enquiries}_{\text{baseline}}} \times 100$$
Our experiment shows an inquiry volume reduction of **55% to 65%**!
