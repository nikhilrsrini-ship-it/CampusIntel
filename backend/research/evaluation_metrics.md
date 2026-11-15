# Evaluation metrics

- **Classification:** accuracy plus macro precision, recall, and F1; the macro average treats each category equally. Inspect the confusion matrix for systematic category confusion.
- **Duplicate retrieval:** precision@K and recall@K on adjudicated duplicate pairs; F1 only at a declared decision threshold.
- **Resolution time:** MAE and RMSE in hours, with R² as a supplementary fit measure; compare with the category median baseline.
- **Routing:** correct department rate, override rate, and assignment latency, measured on authorized historical cases.
- **Process mining:** observed variants, directly-follows counts, elapsed time between events, handoffs, and reassignments. These are descriptive signals, not causal effects.

The generated synthetic classification metrics file is clearly labeled `SYNTHETIC` and must not be presented as an institutional result.
