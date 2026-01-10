import pandas as pd
import numpy as np

def run_simulation(params, current_ward, weeks=52, seed=None):
    if seed is not None:
        np.random.seed(seed)
    
    # --- 1. SETUP PARAMETERS ---
    history = []
    
    # Map categories to their mean LOS for Gamma distribution
    los_map = np.array([0, 
                        params.get('los_cat1', 22), 
                        params.get('los_cat2', 11), 
                        params.get('los_cat3', 5), 
                        params.get('los_cat4', 2), 
                        params.get('los_cat5', 2)])
    
    # Map categories to their deterioration probabilities
    det_rates = np.array([0, 0, 
                          params.get('det_2to1', 0.12), 
                          params.get('det_3to2', 0.07), 
                          params.get('det_4to3', 0.04), 
                          params.get('det_5to4', 0.02)])

    total_dist = sum([params.get(f'dist_cat{i}', 10) for i in range(1, 6)])
    cat_probs = [params.get(f'dist_cat{i}', 10) / total_dist for i in range(1, 6)]
    
    # Ward State: Just an array of days remaining for occupied beds
    ward_days = np.array([p.get('DaysRemaining', 5) for p in current_ward], dtype=float)
    
    # --- 2. INITIALIZE BACKLOG (NumPy Matrix) ---
    # Column 0: Category | Column 1: Weeks Waiting | Column 2: Is Legacy (1=True, 0=False)
    total_bl = params.get('total_backlog', 60)
    legacy_pct = params.get('dist_legacy', 25) / 100
    num_legacy = np.random.poisson(total_bl * legacy_pct)
    num_fresh = max(0, total_bl - num_legacy)

    # Pre-allocate a large array to avoid frequent resizing
    backlog = np.zeros((5000, 3)) 
    
    # Populate Legacy cohort
    backlog[:num_legacy, 0] = 1 # All start as Cat 1
    backlog[:num_legacy, 1] = np.random.randint(26, 40, size=num_legacy)
    backlog[:num_legacy, 2] = 1
    
    # Populate Standard cohort
    backlog[num_legacy:total_bl, 0] = np.random.choice([1,2,3,4,5], size=num_fresh, p=cat_probs)
    backlog[num_legacy:total_bl, 1] = np.random.randint(0, 25, size=num_fresh)
    
    active_count = total_bl

    # --- 3. WEEKLY LOOP ---
    for week in range(weeks):
        num_det = 0
        if active_count > 0:
            view = backlog[:active_count]
            
            # A) Aging
            view[:, 1] += 1
            
            # B) Legacy Breach Pathway (Clock-based)
            # If Legacy flag is 1 AND weeks >= 26 AND not already Cat 1 -> set to Cat 1
            legacy_breach_mask = (view[:, 2] == 1) & (view[:, 1] >= 26) & (view[:, 0] > 1)
            view[legacy_breach_mask, 0] = 1
            
            # C) Clinical Deterioration Pathway (Probability-based)
            # Calculate deterioration lambda only for non-legacy patients
            std_mask = (view[:, 2] == 0) & (view[:, 0] > 1)
            if np.any(std_mask):
                current_cats = view[std_mask, 0].astype(int)
                system_lambda = det_rates[current_cats].sum()
                num_det = np.random.poisson(system_lambda)
                
                if num_det > 0:
                    upgradable_idx = np.where(view[:, 0] > 1)[0]
                    if len(upgradable_idx) > 0:
                        actual_upgrades = min(num_det, len(upgradable_idx))
                        targets = np.random.choice(upgradable_idx, size=actual_upgrades, replace=False)
                        view[targets, 0] -= 1

        # D) New Referrals (Stochastic)
        new_refs = np.random.poisson(params['weekly_refs'])
        for _ in range(new_refs):
            if active_count < 4999: # Stay within pre-allocated bounds
                if np.random.random() < legacy_pct:
                    backlog[active_count] = [1, 26, 1] # Arrives at breach
                else:
                    backlog[active_count] = [np.random.choice([1,2,3,4,5], p=cat_probs), 0, 0]
                active_count += 1

        # E) Discharges
        ward_days -= 7
        ward_days = ward_days[ward_days > 0]

        # F) Admissions & Sorting
        eff_cap = params['total_beds'] - params['safety_buffer']
        avail = int(max(0, eff_cap - len(ward_days)))
        to_admit = min(avail, params['surg_per_week'], active_count)
        
        cancellations = max(0, params['surg_per_week'] - avail) if active_count > 0 else 0
        admitted_counts = {f'Cat {i}': 0 for i in range(1, 6)}

        if to_admit > 0:
            # Vectorized multi-key sort: Category (ASC), then Weeks Waiting (DESC)
            # lexsort uses keys in reverse order: [secondary, primary]
            idx = np.lexsort((-backlog[:active_count, 1], backlog[:active_count, 0]))
            backlog[:active_count] = backlog[idx]
            
            admitted_view = backlog[:to_admit]
            for c in admitted_view[:, 0]:
                admitted_counts[f'Cat {int(c)}'] += 1
            
            # Vectorized Gamma Distribution for LOS
            shapes = los_map[admitted_view[:, 0].astype(int)]
            new_stays = np.random.gamma(shape=shapes, scale=params.get('los_scale', 1.0))
            ward_days = np.concatenate([ward_days, np.maximum(1, new_stays)])
            
            # Shift backlog up to remove admitted patients
            backlog[:active_count-to_admit] = backlog[to_admit:active_count]
            active_count -= to_admit

        # G) LOGGING
        history.append({
            'week': week,
            'Cat 1': np.sum(backlog[:active_count, 0] == 1),
            'Cat 2': np.sum(backlog[:active_count, 0] == 2),
            'Cat 3': np.sum(backlog[:active_count, 0] == 3),
            'Cat 4': np.sum(backlog[:active_count, 0] == 4),
            'Cat 5': np.sum(backlog[:active_count, 0] == 5),
            'Over_26_Wks': np.sum(backlog[:active_count, 1] >= 26),
            'occupancy': len(ward_days),
            'cancellations': cancellations,
            'admissions': admitted_counts,
            'det_events': num_det
        })
        
    return pd.DataFrame(history)

def find_ai_recommendation(params, target_wk):
    """Optimizes for Zero Risk at Target Week."""
    best_score = float('inf')
    best_config = (params['surg_per_week'], params['total_beds'])
    
    # Iterate through potential bed and slot configurations
    for beds in range(params['total_beds'], 17): 
        for slots in range(1, 13): 
            test_params = {**params, 'surg_per_week': slots, 'total_beds': beds}
            
            # Using a fixed seed for speed and stability during optimization
            df = run_simulation(test_params, [], weeks=target_wk + 1, seed=42)
            
            risk_at_target = df.iloc[target_wk]['Over_26_Wks']
            total_cancels = df['cancellations'].sum()
            
            # Scoring: Primary priority is zero risk (avg_risk * 5000)
            score = (risk_at_target * 5000) + (total_cancels * 100) + (beds * 50) + (slots * 20)
            
            if risk_at_target == 0 and score < best_score:
                best_score = score
                best_config = (slots, beds)
                    
    return best_config