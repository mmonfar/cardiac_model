Here is the full content for CLINICAL_LOGIC.md. I have formatted it specifically for GitHub so that the math and tables render clearly for any clinical or technical reviewer.Markdown# 🩺 Clinical Logic & Validation Specification

This document outlines the clinical assumptions, mathematical models, and prioritization heuristics used in the Cardiac Service Strategy Lab.

## 1. Stochastic Deterioration Model
The simulation assumes that a patient’s clinical status is dynamic. Time spent on the waitlist is treated as a physiological stressor.

### The 26-Week Risk Multiplier
Patients are assigned a baseline weekly probability of "upgrading" to a higher acuity category (e.g., Cat 3 → Cat 2).
- **Pre-Breach (0-25 weeks):** $P(\text{deterioration}) = 0.04$ (4% weekly).
- **Post-Breach (26+ weeks):** $P(\text{deterioration}) = 0.04 \times 2.0 = 0.08$ (8% weekly).

**Rationale:** Prolonged waiting for cardiac intervention is associated with increased symptom burden and higher risks of acute decompensation. The $2.0\times$ multiplier forces the model to recognize that "stale" backlogs become more difficult and expensive to clear over time.

---

## 2. Resource Consumption by Acuity (LOS Mapping)
The model acknowledges that a "bed" is not a uniform unit of capacity. Higher acuity patients consume more "Bed-Days," creating a non-linear relationship between admissions and occupancy.

| Category | Clinical Urgency | Mean Length of Stay (LOS) |
| :--- | :--- | :--- |
| **Cat 1** | Critical / Emergent | 22 Days |
| **Cat 2** | Urgent | 11 Days |
| **Cat 3** | Semi-Urgent | 5 Days |
| **Cat 4** | Routine | 2 Days |
| **Cat 5** | Minor / Investigative | 2 Days |



**Impact:** Deterioration from Cat 3 to Cat 1 represents a **440% increase** in bed-day consumption per patient.

---

## 3. Prioritization Heuristics
The admission engine mimics the multidisciplinary team (MDT) decision-making process using a multi-key sort:

1. **Safety First (Clinical Category):** The system always pulls Cat 1 and Cat 2 patients first.
2. **Breach Prevention (Wait Time):** Within a category, the system prioritizes those approaching or exceeding the 26-week threshold.

```python
# The underlying sorting logic:
backlog.sort(key=lambda x: (x['cat'], -x['weeks_waiting']))

4. Operational "Bed-Choke" LogicA surgery is logged as a "Cancellation" when theater slots are available but effective bed capacity is zero.Effective Capacity = $Total\ Beds - Safety\ Buffer$The Safety Buffer represents beds reserved for emergency non-elective admissions (e.g., emergency department arrivals).5. Metrics & Stability ScoringThe Stability Score (%) evaluates the health of the configuration:Throughput: Success in reducing the 26-week legacy count.Efficiency: Penalization for every "Bed-Choke" cancellation.A high stability score indicates a "Balanced System" where theater throughput is perfectly matched to ward discharge rates.