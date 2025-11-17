# Training Analytics & ML Features Guide

This guide covers the advanced analytics features for training load monitoring, injury risk prediction, VDOT optimization, and performance prediction.

## Overview

The running coach system now includes four integrated analytics modules:

1. **Training Load Analytics** - Monitor fitness, fatigue, and form (TSS/CTL/ATL/TSB/ACWR)
2. **Injury Risk Prediction** - ML-based overtraining detection and injury risk assessment
3. **VDOT Calculator** - Automated VDOT adjustments based on performance data
4. **Performance Predictor** - Race time predictions with confidence adjustments

## Training Load Analytics

### What is Training Load?

Training load metrics help you understand:
- **Fitness** (CTL): Long-term training adaptations
- **Fatigue** (ATL): Short-term accumulated stress
- **Form** (TSB): Readiness to perform
- **Injury Risk** (ACWR): Safe vs. dangerous training load progression

### Key Metrics

**TSS (Training Stress Score)**
- Score for individual workouts based on duration and intensity
- 1 hour at lactate threshold = 100 TSS
- Calculated from heart rate data

**CTL (Chronic Training Load)**
- 42-day exponentially weighted average of TSS
- Represents your long-term fitness level
- Higher CTL = more fit, but takes weeks to build

**ATL (Acute Training Load)**
- 7-day exponentially weighted average of TSS
- Represents recent fatigue accumulation
- Responds quickly to training changes

**TSB (Training Stress Balance)**
- CTL - ATL = Form
- Positive TSB: Fresh and ready to race
- Negative TSB: Fatigued from training
- Zero TSB: Balanced fitness and fatigue

**ACWR (Acute:Chronic Workload Ratio)**
- 7-day load / 28-day load
- Research-backed injury risk indicator
- Safe zone: 0.8 - 1.3
- High risk: > 1.5

### Usage

**View Training Load Summary**
```bash
bash bin/training_analytics.sh --summary
```

Output example:
```
TRAINING LOAD SUMMARY
======================================================================

Date: 2025-11-17

Current Training Load:
  CTL (Fitness):    52.3  - Long-term training load (42-day average)
  ATL (Fatigue):    48.7  - Short-term training load (7-day average)
  TSB (Form):        3.6  - NEUTRAL
                         Balanced fitness and fatigue

Injury Risk (ACWR):
  Ratio: 1.15  - OPTIMAL
  Training load is well-balanced for adaptation without excessive injury risk.
  7-day load:   341.0 TSS
  28-day load: 1456.2 TSS

14-Day Trends:
  CTL:  +4.2  (Fitness building)
  ATL:  -2.1  (Fatigue decreasing)
  TSB:  +6.3  (Form improving)
```

**View Weekly Progression**
```bash
bash bin/training_analytics.sh --weekly --weeks 12
```

**Get JSON Output**
```bash
bash bin/training_analytics.sh --summary --json > training_load.json
```

### Interpreting Your Metrics

**CTL (Fitness)**
- Marathon training: Target 60-100
- Half marathon: Target 40-70
- 10K/5K: Target 30-50

**TSB (Form)**
- TSB > 10: Well-rested, ready to race
- TSB 0-10: Fresh, good for training
- TSB 0 to -10: Neutral, balanced
- TSB -10 to -30: Fatigued, productive training
- TSB < -30: Overreached, need recovery

**ACWR (Injury Risk)**
- < 0.8: Detraining (losing fitness)
- 0.8-1.3: Sweet spot (optimal adaptation)
- 1.3-1.5: Elevated risk (monitor closely)
- > 1.5: High risk (reduce volume immediately)

## Injury Risk Prediction

### What Does It Detect?

The injury risk system analyzes multiple data streams to detect overtraining patterns:

1. **ACWR Violations** - Training load spikes
2. **Sleep Deprivation** - Insufficient recovery time
3. **Elevated RHR** - Incomplete recovery indicator
4. **Suppressed HRV** - Stress and overtraining signal
5. **Low Training Readiness** - Garmin's composite score
6. **Training Load Spikes** - Sudden volume increases

### Usage

**Get Comprehensive Risk Assessment**
```bash
bash bin/injury_risk.sh
```

Output example:
```
INJURY RISK ASSESSMENT
======================================================================

Date: 2025-11-17

Overall Risk Score: 28.5/100
Risk Level: LOW

Injury risk is low. Training load and recovery are well-balanced.

Recommendations:
  • Continue current training pattern
  • Maintain focus on recovery practices

Detailed Risk Factors:

  ACWR (Workload Ratio): 15/100
    Training load is well-balanced for adaptation without excessive injury risk.

  Sleep Quality: 25/100
    Sleep deprivation detected - recovery is compromised
    Avg: 6.2 hrs/night

  Resting Heart Rate: 30/100
    RHR slightly elevated - monitor recovery
    Current: 48 bpm (baseline: 46 bpm)

  Heart Rate Variability: 10/100
    HRV is within normal range

  Training Readiness: 20/100
    Training readiness is moderate

  Training Load Spike: 10/100
    No significant load spike
```

**Get JSON Output**
```bash
bash bin/injury_risk.sh --json > injury_risk.json
```

### Risk Levels

**LOW (< 30)**
- Continue current training
- Maintain recovery practices

**MODERATE (30-50)**
- Monitor recovery metrics daily
- Ensure 7-9 hours sleep
- Add rest day if multiple factors worsen

**HIGH (50-70)**
- Reduce training volume 20-30%
- Add extra rest day
- Prioritize sleep and recovery

**CRITICAL (> 70)**
- Take 2-3 complete rest days immediately
- Reduce volume 40-50% when resuming
- Consider medical consultation
- No high-intensity workouts until normalized

### When to Check

- Beginning of each training week
- After completing key workouts
- When feeling unusually fatigued
- Before planning high-volume weeks
- During taper periods

## VDOT Calculator

### What is VDOT?

VDOT is Jack Daniels' performance metric that:
- Measures running fitness level
- Predicts race times across all distances
- Prescribes training paces for optimal adaptation
- Tracks fitness progression over time

### Features

**Calculate VDOT from Race Results**
```bash
bash bin/vdot_calculator.sh --race Marathon 4:05:32
bash bin/vdot_calculator.sh --race Half 1:52:15
bash bin/vdot_calculator.sh --race 10K 48:30
bash bin/vdot_calculator.sh --race 5K 22:45
```

**Generate Training Paces**
```bash
bash bin/vdot_calculator.sh --vdot 45
```

Output:
```
Training Paces for VDOT 45:
  Easy (E):       10:20-10:40 /mile
  Marathon (M):   9:00-9:20 /mile
  Threshold (T):  8:20-8:30 /mile
  Interval (I):   7:45-7:55 /mile
  Repetition (R): 7:20-7:30 /mile
```

**Analyze Workout Performance**
```bash
bash bin/vdot_calculator.sh --analyze
```

Output:
```
WORKOUT PERFORMANCE ANALYSIS
======================================================================

Workouts Analyzed: 15 (last 30 days)
Quality Score: 0.85

Recommendation: SLIGHT INCREASE VDOT by +1
Reasoning: Some evidence of improved efficiency. Consider small upward adjustment.

Current VO2 Max: 51.0 ml/kg/min
Estimated VDOT from VO2: 50.0
```

**Track VDOT Progression**
```bash
bash bin/vdot_calculator.sh --progression
```

**Predict Race Times**
```bash
bash bin/vdot_calculator.sh --predict 45
```

Output:
```
Race Time Predictions for VDOT 45:
  5K        : 23:18
  10K       : 48:42
  Half      : 1:50:25
  Marathon  : 3:51:30
```

### VDOT Adjustment Guidelines

**When to Increase VDOT (+1 to +3)**
- Consistently hitting paces at lower HR than expected
- Recent race performance better than predicted
- VO2 max increasing
- Training feels easier at prescribed paces

**When to Decrease VDOT (-1 to -3)**
- Struggling to maintain paces even at high HR
- Recent race performance slower than predicted
- Accumulated fatigue/sleep deprivation
- Training feels harder than it should

**When to Maintain VDOT**
- Workout performance aligns with predictions
- HR matches expected zones for paces
- Recent race times match VDOT predictions

## Performance Predictor

### What Does It Predict?

Race times adjusted for:
- Current fitness level (VDOT/VO2 max)
- Training load state (CTL/ATL/TSB)
- Recovery status (sleep, RHR, HRV)
- Taper adequacy

### Usage

**Predict Race Times**
```bash
bash bin/performance_predictor.sh --predict
```

Output:
```
RACE TIME PREDICTIONS
======================================================================

VDOT: 50.0 (VO2max (51.0 ml/kg/min))

Adjustments:
  Fitness:  well-rested (TSB +8), good fitness base (CTL 65)
  Recovery: Good recovery
  Total adjustment: -1.5%

Predicted Times:

Distance    Base Time  Adjusted   Garmin
----------------------------------------------------------------------
5K            21:35      21:16     21:22
10K           45:02      44:21     44:35
Half        1:40:15    1:38:45   1:39:12
Marathon    3:31:20    3:28:08   3:29:45
```

**Assess Race Readiness**
```bash
bash bin/performance_predictor.sh --race-readiness Marathon --days-until-race 10
```

Output:
```
RACE READINESS ASSESSMENT - Marathon
======================================================================

Days Until Race: 10
Readiness Score: 75/100
Readiness Level: GOOD

You are ready to race with minor adjustments.

Predicted Time: 3:28:08

Readiness Factors:
  ✓ Strong fitness base
  ✓ Well-tapered and fresh
  ✓ Low injury risk
  ~ Moderate recovery concerns (sleep deprivation)

Concerns:
  ⚠ Sleep: Sleep deprivation detected - recovery is compromised

Recommendations:
  • Prioritize sleep (7-9 hours) in final week
  • Maintain easy shakeout runs only
  • Trust your training and taper
```

### Confidence Adjustments

**Fitness Adjustments**
- TSB > 10: -2% (well-rested)
- TSB > 0: -1% (fresh)
- TSB 0 to -10: 0% (neutral)
- TSB -10 to -20: +2% (fatigued)
- TSB < -20: +5% (overreached)

**Recovery Adjustments**
- Excellent recovery: -1%
- Good recovery: 0%
- Moderate concerns: +2%
- Poor recovery: +5%

**CTL (Fitness Base)**
- Marathon: CTL > 60 optimal
- Half: CTL > 40 optimal
- Low fitness: +2-5% adjustment

## Integration with Coaching Agents

All coaching agents can now access these analytics:

### Running Coach
- Uses ACWR to adjust weekly volume safely
- Checks TSB before prescribing hard workouts
- Uses VDOT analysis to adjust training paces
- Considers injury risk when planning training

### Strength Coach
- Checks TSB to avoid heavy lifting when fatigued
- Uses injury risk to adjust intensity
- Coordinates with training load to prevent overload

### Mobility Coach
- Uses recovery metrics to prioritize mobility work
- Increases focus when injury risk elevated
- Scales intensity based on fatigue state

### Nutrition Coach
- Adjusts calorie recommendations based on training load
- Emphasizes recovery nutrition when TSB negative
- Considers sleep quality for meal timing

## Best Practices

### Weekly Routine

**Monday**
```bash
# Start week with comprehensive assessment
bash bin/injury_risk.sh
bash bin/training_analytics.sh --summary
```

**Mid-Week (Wednesday)**
```bash
# Quick check on training load
bash bin/training_analytics.sh --summary
```

**Sunday**
```bash
# Weekly review
bash bin/training_analytics.sh --weekly --weeks 4
bash bin/vdot_calculator.sh --analyze
```

### Race Preparation

**8 Weeks Out**
```bash
bash bin/vdot_calculator.sh --predict <current-vdot>
bash bin/performance_predictor.sh --race-readiness Marathon --days-until-race 56
```

**2 Weeks Out**
```bash
bash bin/performance_predictor.sh --race-readiness Marathon --days-until-race 14
bash bin/training_analytics.sh --summary
```

**Race Week**
```bash
bash bin/performance_predictor.sh --predict
bash bin/injury_risk.sh
```

### Troubleshooting

**High Injury Risk Despite Feeling Good**
- Trust the data - overtraining symptoms lag behind metrics
- Reduce volume 20-30% for one week
- Focus on sleep and recovery
- Recheck in 3-4 days

**ACWR > 1.5**
- Immediate volume reduction needed
- Replace hard workout with easy run
- Add extra rest day
- Return to training gradually (increase 10% per week max)

**Negative TSB for Extended Period**
- Normal during training blocks
- Concerning if < -30 for > 2 weeks
- Schedule recovery week (50% volume)
- Check sleep and nutrition

**VDOT Recommendations Conflict with Feel**
- Trust longer-term trends over single workouts
- Wait 2-3 weeks before adjusting
- Consider external factors (weather, sleep, stress)
- Use race performances as ultimate validation

## Technical Details

### TSS Calculation
```
TSS = (duration_sec × IF² × 100) / 3600
where IF (Intensity Factor) = avg_hr / threshold_hr
```

### CTL/ATL Calculation
```
CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) / 42
ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) / 7
TSB = CTL - ATL
```

### VDOT Formula
```
VO2 = -4.60 + 0.182258 * velocity + 0.000104 * velocity²
VDOT = VO2 / percent_max_sustainable
```

### ACWR Calculation
```
ACWR = (sum of last 7 days TSS) / (sum of last 28 days TSS)
```

## References

- Coggan, A. (2003). Training and Racing Using a Power Meter
- Gabbett, T. (2016). The training-injury prevention paradox
- Daniels, J. (2013). Daniels' Running Formula (3rd ed)
- Seiler, S. (2010). What is best practice for training intensity distribution
