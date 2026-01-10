import pandas as pd
import numpy as np

def run_simulation(params, current_ward, weeks=52, seed=None):
    if seed is not None:
        np.random.seed(seed)
    
    # --- 1. SETUP PARAMETERS ---
    history = []

    los_map = {
        1: params.get('los_cat1', 22),
        2: params.get('los_cat2', 11),
        3: params.get('los_cat3', 5),
        4: params.get('los_cat4', 2),
        5: params.get('los_cat5', 2)
    }
    
    det_matrix = {
        5: params.get('det_5to4', 0.02),
        4: params.get('det_4to3', 0.04),
        3: params.get('det_3to2', 0.07),
        2: params.get('det_2to1', 0.12)
    }

    # NEW: Calculate probabilities for fresh referrals based on sidebar mix
    total_dist = (params.get('dist_cat1', 10) + params.get('dist_cat2', 15) + 
                  params.get('dist_cat3', 20) + params.get('dist_cat4', 30) + 
                  params.get('dist_cat5', 25))
    
    cat_probs = [
        params.get('dist_cat1', 10) / total_dist,
        params.get('dist_cat2', 15) / total_dist,
        params.get('dist_cat3', 20) / total_dist,
        params.get('dist_cat4', 30) / total_dist,
        params.get('dist_cat5', 25) / total_dist
    ]
    
    active_beds = [{'cat': p.get('Cat', 3), 'days_remaining': p.get('DaysRemaining', 5)} for p in current_ward]
    
    # --- 2. INITIALIZE BACKLOG ---
    backlog = []
    total_backlog = params.get('total_backlog', 60)
    legacy_pct = params.get('dist_legacy', 25) / 100
    
    num_legacy = np.random.poisson(total_backlog * legacy_pct)
    num_fresh = max(0, total_backlog - num_legacy)

    for _ in range(num_legacy):
        # Forced to Cat 1 and flagged as Legacy Diagnosis
        backlog.append({
            'cat': 1, 
            'weeks_waiting': np.random.randint(26, 40),
            'is_legacy_diagnosis': True  # <--- NEW FLAG
        })
    
    for _ in range(num_fresh):
        backlog.append({
            'cat': np.random.choice([1,2,3,4,5], p=cat_probs), 
            'weeks_waiting': np.random.randint(0, 25),
            'is_legacy_diagnosis': False # <--- NEW FLAG
        })
    
    # --- 3. WEEKLY LOOP ---
    for week in range(weeks):
        # A) DETERIORATION & BREACH LOGIC
        system_lambda = 0
        for p in backlog:
            p['weeks_waiting'] += 1
            
            # --- PATHWAY A: THE CLOCK (Specific to Legacy Diagnosis Cohort) ---
            if p.get('is_legacy_diagnosis', False) and p['weeks_waiting'] >= 26 and p['cat'] > 1:
                p['cat'] = 1

            # --- PATHWAY B: THE CLINICAL DECLINE (For Standard Cohort) ---
            # Standard patients decline stochasticly via the matrix
            if not p.get('is_legacy_diagnosis', False) and p['cat'] in det_matrix and p['cat'] > 1:
                system_lambda += det_matrix[p['cat']]
                        
        num_deteriorations = np.random.poisson(system_lambda)

        if num_deteriorations > 0:
            upgradable = [p for p in backlog if p['cat'] > 1]
            if upgradable:
                actual_upgrades = min(num_deteriorations, len(upgradable))
                targets = np.random.choice(upgradable, size=actual_upgrades, replace=False)
                for p in targets:
                    p['cat'] -= 1 

        # B) STOCHASTIC REFERRALS
        new_refs = np.random.poisson(params['weekly_refs'])
        for _ in range(new_refs):
            if np.random.random() < legacy_pct:
                # Arrives as part of the special high-risk cohort
                backlog.append({'cat': 1, 'weeks_waiting': 26, 'is_legacy_diagnosis': True})
            else:
                # Arrives as a standard patient
                backlog.append({
                    'cat': np.random.choice([1,2,3,4,5], p=cat_probs), 
                    'weeks_waiting': 0,
                    'is_legacy_diagnosis': False
                })

        # C) DISCHARGES
        for p in active_beds: 
            p['days_remaining'] -= 7
        active_beds = [p for p in active_beds if p['days_remaining'] > 0]

        # D) ADMISSIONS & STOCHASTIC LOS
        eff_cap = params['total_beds'] - params['safety_buffer']
        avail = max(0, eff_cap - len(active_beds))
        to_admit = min(avail, params['surg_per_week'])
        
        cancellations = max(0, params['surg_per_week'] - avail) if len(backlog) > 0 else 0
        
        # Sort by Category (1 is highest) then by longest wait
        backlog.sort(key=lambda x: (x['cat'], -x['weeks_waiting']))
        
        admitted = {f'Cat {i}': 0 for i in range(1,6)}
        for _ in range(int(to_admit)):
            if backlog:
                p = backlog.pop(0)
                admitted[f"Cat {p['cat']}"] += 1
                
                # Use the clean map value based on the category
                base_days = los_map[p['cat']]
                
                # Calculate actual stay using Gamma distribution for realistic variance
                # scale=params.get('los_scale', 1.0) controls the "tail" (outliers)
                actual_los = int(np.random.gamma(shape=base_days, scale=params.get('los_scale', 1.0)))
                
                active_beds.append({
                    'cat': p['cat'], 
                    'days_remaining': max(1, actual_los)
                })

        # E) LOGGING
        history.append({
            'week': week, 
            'Cat 1': len([p for p in backlog if p['cat']==1]),
            'Cat 2': len([p for p in backlog if p['cat']==2]), 
            'Cat 3': len([p for p in backlog if p['cat']==3]),
            'Cat 4': len([p for p in backlog if p['cat']==4]), 
            'Cat 5': len([p for p in backlog if p['cat']==5]),
            'Over_26_Wks': len([p for p in backlog if p['weeks_waiting'] >= 26]),
            'occupancy': len(active_beds), 
            'cancellations': cancellations,
            'admissions': admitted, 
            'ward_state': [dict(p) for p in active_beds],
            'det_events': num_deteriorations 
        })
    return pd.DataFrame(history)

def find_ai_recommendation(params, target_wk):
    """Optimizes for Zero Risk at Target Week."""
    best_score = float('inf')
    best_config = (params['surg_per_week'], params['total_beds'])
    
    for beds in range(params['total_beds'], 16): 
        for slots in range(1, 15): 
            test_params = {**params, 'surg_per_week': slots, 'total_beds': beds}
            results = [run_simulation(test_params, [], weeks=target_wk + 1, seed=s) for s in range(3)]
            
            avg_risk = np.mean([df.iloc[target_wk]['Over_26_Wks'] for df in results])
            avg_cancels = np.mean([df['cancellations'].sum() for df in results])
            
            score = (avg_risk * 1000) + (avg_cancels * 50) + (beds * 20) + (slots * 10)
            
            if avg_risk == 0 and score < best_score:
                best_score = score
                best_config = (slots, beds)
                    
    return best_config