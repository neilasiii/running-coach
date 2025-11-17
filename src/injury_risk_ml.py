#!/usr/bin/env python3
"""
Injury Risk Prediction Module

Uses machine learning and pattern detection to identify overtraining signals and injury risk.
Analyzes multiple data streams:
- Training load patterns (ACWR violations)
- Sleep quality trends
- Resting heart rate elevation
- Heart rate variability changes
- Recovery metrics (training readiness)
- Training volume progression

Based on research from:
- Tim Gabbett (ACWR and injury risk)
- Stephen Seiler (training load and recovery)
- Erik Kvalheim (HRV and overtraining)
"""

import json
import sys
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict

# Try to import sklearn, but make it optional
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# Risk thresholds
RISK_LOW = 30
RISK_MODERATE = 50
RISK_HIGH = 70
RISK_CRITICAL = 85

# Signal weights for risk scoring
WEIGHT_ACWR = 0.25
WEIGHT_SLEEP = 0.15
WEIGHT_RHR = 0.20
WEIGHT_HRV = 0.15
WEIGHT_READINESS = 0.15
WEIGHT_LOAD_SPIKE = 0.10


class InjuryRiskPredictor:
    """
    Predicts injury risk based on training load patterns and recovery metrics.
    """

    def __init__(self, cache_file: str):
        """
        Initialize predictor with health data cache.

        Args:
            cache_file: Path to health_data_cache.json
        """
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Load health data cache"""
        if not self.cache_file.exists():
            raise FileNotFoundError(f"Cache file not found: {self.cache_file}")

        with open(self.cache_file, 'r') as f:
            return json.load(f)

    def _get_baseline_rhr(self, days: int = 90) -> Tuple[float, float]:
        """
        Calculate baseline resting heart rate (mean and std dev).

        Args:
            days: Number of days to use for baseline (default: 90)

        Returns:
            Tuple of (mean_rhr, std_rhr)
        """
        rhr_readings = self.cache.get('resting_hr_readings', [])
        if not rhr_readings:
            return (50.0, 5.0)  # Default values

        # Get recent readings
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent_rhr = [r[1] for r in rhr_readings if r[0] >= cutoff]

        if len(recent_rhr) < 7:
            return (50.0, 5.0)

        return (np.mean(recent_rhr), np.std(recent_rhr))

    def _get_baseline_hrv(self, days: int = 28) -> Tuple[float, float]:
        """
        Calculate baseline HRV (mean and std dev).

        Args:
            days: Number of days to use for baseline (default: 28)

        Returns:
            Tuple of (mean_hrv, std_hrv)
        """
        hrv_readings = self.cache.get('hrv_readings', [])
        if not hrv_readings:
            return (50.0, 10.0)

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        recent_hrv = [h['last_night_avg'] for h in hrv_readings
                      if h.get('date', '') >= cutoff and h.get('last_night_avg')]

        if len(recent_hrv) < 7:
            return (50.0, 10.0)

        return (np.mean(recent_hrv), np.std(recent_hrv))

    def analyze_acwr_risk(self) -> Dict[str, Any]:
        """
        Analyze injury risk from ACWR violations.

        Returns:
            Dictionary with ACWR risk score and details
        """
        # Import here to avoid circular dependency
        from training_analytics import TrainingLoadAnalyzer

        analyzer = TrainingLoadAnalyzer(str(self.cache_file))
        activities = self.cache.get('activities', [])
        daily_tss = analyzer.calculate_daily_tss(activities)
        acwr_data = analyzer.calculate_acwr(daily_tss)

        acwr = acwr_data.get('acwr', 1.0)
        risk_level = acwr_data.get('risk_level', 'OPTIMAL')

        # Calculate risk score (0-100)
        if risk_level == 'OPTIMAL':
            risk_score = 10
        elif risk_level == 'DETRAINING':
            risk_score = 25
        elif risk_level == 'ELEVATED':
            risk_score = 60
        else:  # HIGH
            risk_score = 90

        # Additional detail: check for consistent violations over past week
        violation_count = 0
        for days_back in range(7):
            target_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime('%Y-%m-%d')
            day_acwr = analyzer.calculate_acwr(daily_tss, target_date)
            if day_acwr.get('acwr', 0) > 1.3:
                violation_count += 1

        if violation_count >= 4:
            risk_score = min(100, risk_score + 20)
            concern = "ACWR has been elevated for multiple days - high injury risk"
        elif violation_count >= 2:
            risk_score = min(100, risk_score + 10)
            concern = "ACWR violations detected on multiple recent days"
        else:
            concern = acwr_data.get('risk_description', '')

        return {
            'risk_score': risk_score,
            'acwr': acwr,
            'risk_level': risk_level,
            'violation_days': violation_count,
            'concern': concern
        }

    def analyze_sleep_risk(self, days: int = 14) -> Dict[str, Any]:
        """
        Analyze injury risk from poor sleep patterns.

        Insufficient sleep impairs recovery and increases injury risk.

        Args:
            days: Number of days to analyze (default: 14)

        Returns:
            Dictionary with sleep risk score and details
        """
        sleep_sessions = self.cache.get('sleep_sessions', [])
        if not sleep_sessions:
            return {
                'risk_score': 0,
                'concern': 'No sleep data available',
                'avg_duration_hrs': 0,
                'poor_sleep_nights': 0
            }

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        recent_sleep = [s for s in sleep_sessions if s.get('date', '') >= cutoff]

        if len(recent_sleep) < 7:
            return {
                'risk_score': 0,
                'concern': 'Insufficient sleep data',
                'avg_duration_hrs': 0,
                'poor_sleep_nights': 0
            }

        # Analyze sleep duration
        durations = [s['total_duration_minutes'] / 60 for s in recent_sleep]
        avg_duration = np.mean(durations)

        # Count poor sleep nights (< 6.5 hours or score < 60)
        poor_sleep_count = sum(1 for s in recent_sleep
                              if s['total_duration_minutes'] < 390 or  # < 6.5 hours
                              (s.get('sleep_score') and s['sleep_score'] < 60))

        poor_sleep_pct = poor_sleep_count / len(recent_sleep)

        # Calculate risk score
        if avg_duration >= 7.5 and poor_sleep_pct < 0.2:
            risk_score = 5
            concern = "Sleep is adequate for recovery"
        elif avg_duration >= 7.0 and poor_sleep_pct < 0.35:
            risk_score = 20
            concern = "Sleep is acceptable but could be improved"
        elif avg_duration >= 6.0 and poor_sleep_pct < 0.5:
            risk_score = 50
            concern = "Sleep deprivation detected - recovery is compromised"
        else:
            risk_score = 80
            concern = "Severe sleep deprivation - high injury risk"

        return {
            'risk_score': risk_score,
            'concern': concern,
            'avg_duration_hrs': round(avg_duration, 1),
            'poor_sleep_nights': poor_sleep_count,
            'poor_sleep_percentage': round(poor_sleep_pct * 100, 1)
        }

    def analyze_rhr_risk(self, days: int = 14) -> Dict[str, Any]:
        """
        Analyze injury risk from elevated resting heart rate.

        Elevated RHR (>5 bpm above baseline) indicates incomplete recovery.

        Args:
            days: Number of days to analyze (default: 14)

        Returns:
            Dictionary with RHR risk score and details
        """
        rhr_readings = self.cache.get('resting_hr_readings', [])
        if not rhr_readings:
            return {
                'risk_score': 0,
                'concern': 'No RHR data available',
                'avg_rhr': 0,
                'baseline_rhr': 0,
                'elevation': 0
            }

        # Get baseline
        baseline_mean, baseline_std = self._get_baseline_rhr()

        # Get recent readings
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent_rhr = [r[1] for r in rhr_readings if r[0] >= cutoff]

        if len(recent_rhr) < 7:
            return {
                'risk_score': 0,
                'concern': 'Insufficient RHR data',
                'avg_rhr': 0,
                'baseline_rhr': int(baseline_mean),
                'elevation': 0
            }

        avg_rhr = np.mean(recent_rhr)
        elevation = avg_rhr - baseline_mean

        # Count days with elevated RHR (>1 std dev above baseline)
        elevated_days = sum(1 for rhr in recent_rhr if rhr > baseline_mean + baseline_std)
        elevated_pct = elevated_days / len(recent_rhr)

        # Calculate risk score
        if elevation < 3 and elevated_pct < 0.3:
            risk_score = 5
            concern = "RHR is within normal range"
        elif elevation < 5 and elevated_pct < 0.5:
            risk_score = 30
            concern = "RHR slightly elevated - monitor recovery"
        elif elevation < 8 and elevated_pct < 0.7:
            risk_score = 60
            concern = "RHR elevated - incomplete recovery detected"
        else:
            risk_score = 85
            concern = "RHR significantly elevated - high overtraining risk"

        return {
            'risk_score': risk_score,
            'concern': concern,
            'avg_rhr': int(avg_rhr),
            'baseline_rhr': int(baseline_mean),
            'elevation': round(elevation, 1),
            'elevated_days': elevated_days,
            'elevated_percentage': round(elevated_pct * 100, 1)
        }

    def analyze_hrv_risk(self, days: int = 14) -> Dict[str, Any]:
        """
        Analyze injury risk from HRV (Heart Rate Variability) decline.

        Decreased HRV indicates stress and incomplete recovery.

        Args:
            days: Number of days to analyze (default: 14)

        Returns:
            Dictionary with HRV risk score and details
        """
        hrv_readings = self.cache.get('hrv_readings', [])
        if not hrv_readings:
            return {
                'risk_score': 0,
                'concern': 'No HRV data available',
                'avg_hrv': 0,
                'baseline_hrv': 0,
                'change_pct': 0
            }

        # Get baseline
        baseline_mean, baseline_std = self._get_baseline_hrv()

        # Get recent readings
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        recent_hrv = [h['last_night_avg'] for h in hrv_readings
                      if h.get('date', '') >= cutoff and h.get('last_night_avg')]

        if len(recent_hrv) < 7:
            return {
                'risk_score': 0,
                'concern': 'Insufficient HRV data',
                'avg_hrv': 0,
                'baseline_hrv': int(baseline_mean),
                'change_pct': 0
            }

        avg_hrv = np.mean(recent_hrv)
        change_pct = ((avg_hrv - baseline_mean) / baseline_mean) * 100

        # Count days with suppressed HRV (>1 std dev below baseline)
        suppressed_days = sum(1 for hrv in recent_hrv if hrv < baseline_mean - baseline_std)
        suppressed_pct = suppressed_days / len(recent_hrv)

        # Calculate risk score (lower HRV = higher risk)
        if change_pct > -5 and suppressed_pct < 0.3:
            risk_score = 5
            concern = "HRV is within normal range"
        elif change_pct > -10 and suppressed_pct < 0.5:
            risk_score = 30
            concern = "HRV slightly decreased - monitor recovery"
        elif change_pct > -20 and suppressed_pct < 0.7:
            risk_score = 60
            concern = "HRV significantly decreased - recovery compromised"
        else:
            risk_score = 85
            concern = "HRV severely suppressed - high overtraining risk"

        return {
            'risk_score': risk_score,
            'concern': concern,
            'avg_hrv': round(avg_hrv, 1),
            'baseline_hrv': round(baseline_mean, 1),
            'change_pct': round(change_pct, 1),
            'suppressed_days': suppressed_days,
            'suppressed_percentage': round(suppressed_pct * 100, 1)
        }

    def analyze_readiness_risk(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze injury risk from Garmin training readiness scores.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dictionary with readiness risk score and details
        """
        readiness_data = self.cache.get('training_readiness', [])
        if not readiness_data:
            return {
                'risk_score': 0,
                'concern': 'No training readiness data available',
                'avg_score': 0,
                'poor_readiness_days': 0
            }

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        recent_readiness = [r for r in readiness_data if r.get('date', '') >= cutoff]

        if len(recent_readiness) < 3:
            return {
                'risk_score': 0,
                'concern': 'Insufficient readiness data',
                'avg_score': 0,
                'poor_readiness_days': 0
            }

        scores = [r['score'] for r in recent_readiness if r.get('score')]
        if not scores:
            return {
                'risk_score': 0,
                'concern': 'No readiness scores available',
                'avg_score': 0,
                'poor_readiness_days': 0
            }

        avg_score = np.mean(scores)

        # Count poor readiness days (score < 50 or level POOR/LOW)
        poor_days = sum(1 for r in recent_readiness
                       if (r.get('score') and r['score'] < 50) or
                       r.get('level') in ['POOR', 'LOW'])

        poor_pct = poor_days / len(recent_readiness)

        # Calculate risk score
        if avg_score >= 70 and poor_pct < 0.2:
            risk_score = 5
            concern = "Training readiness is good"
        elif avg_score >= 55 and poor_pct < 0.4:
            risk_score = 30
            concern = "Training readiness is moderate"
        elif avg_score >= 40 and poor_pct < 0.6:
            risk_score = 60
            concern = "Training readiness is poor - recovery needed"
        else:
            risk_score = 85
            concern = "Training readiness is very poor - high injury risk"

        return {
            'risk_score': risk_score,
            'concern': concern,
            'avg_score': round(avg_score, 1),
            'poor_readiness_days': poor_days,
            'poor_readiness_percentage': round(poor_pct * 100, 1)
        }

    def detect_load_spike(self, days: int = 7) -> Dict[str, Any]:
        """
        Detect sudden training load spikes.

        Args:
            days: Number of days to check for spike (default: 7)

        Returns:
            Dictionary with spike detection results
        """
        from training_analytics import TrainingLoadAnalyzer

        analyzer = TrainingLoadAnalyzer(str(self.cache_file))
        activities = self.cache.get('activities', [])
        daily_tss = analyzer.calculate_daily_tss(activities)

        # Get recent TSS values
        recent_dates = sorted(daily_tss.keys())[-days:]
        if len(recent_dates) < days:
            return {
                'risk_score': 0,
                'concern': 'Insufficient data for spike detection',
                'spike_detected': False
            }

        recent_tss = [daily_tss[d] for d in recent_dates]

        # Compare to previous period
        prev_dates = sorted(daily_tss.keys())[-days*2:-days] if len(daily_tss) >= days*2 else []
        if len(prev_dates) >= days:
            prev_tss = [daily_tss[d] for d in prev_dates]
            avg_recent = np.mean(recent_tss)
            avg_prev = np.mean(prev_tss)

            increase_pct = ((avg_recent - avg_prev) / avg_prev * 100) if avg_prev > 0 else 0

            # Check for spike
            if increase_pct > 50:
                risk_score = 80
                concern = f"Major load spike detected ({increase_pct:.0f}% increase)"
                spike_detected = True
            elif increase_pct > 25:
                risk_score = 50
                concern = f"Moderate load spike detected ({increase_pct:.0f}% increase)"
                spike_detected = True
            elif increase_pct > 10:
                risk_score = 25
                concern = f"Minor load increase detected ({increase_pct:.0f}% increase)"
                spike_detected = False
            else:
                risk_score = 5
                concern = "No significant load spike"
                spike_detected = False
        else:
            increase_pct = 0
            risk_score = 0
            concern = "Insufficient data for comparison"
            spike_detected = False

        return {
            'risk_score': risk_score,
            'concern': concern,
            'spike_detected': spike_detected,
            'increase_percentage': round(increase_pct, 1)
        }

    def get_comprehensive_risk_assessment(self) -> Dict[str, Any]:
        """
        Generate comprehensive injury risk assessment combining all risk factors.

        Returns:
            Dictionary with overall risk score and contributing factors
        """
        # Analyze all risk factors
        acwr_risk = self.analyze_acwr_risk()
        sleep_risk = self.analyze_sleep_risk()
        rhr_risk = self.analyze_rhr_risk()
        hrv_risk = self.analyze_hrv_risk()
        readiness_risk = self.analyze_readiness_risk()
        spike_risk = self.detect_load_spike()

        # Calculate weighted overall risk score
        overall_risk = (
            acwr_risk['risk_score'] * WEIGHT_ACWR +
            sleep_risk['risk_score'] * WEIGHT_SLEEP +
            rhr_risk['risk_score'] * WEIGHT_RHR +
            hrv_risk['risk_score'] * WEIGHT_HRV +
            readiness_risk['risk_score'] * WEIGHT_READINESS +
            spike_risk['risk_score'] * WEIGHT_LOAD_SPIKE
        )

        # Determine risk level
        if overall_risk < RISK_LOW:
            risk_level = "LOW"
            risk_description = "Injury risk is low. Training load and recovery are well-balanced."
            recommendations = [
                "Continue current training pattern",
                "Maintain focus on recovery practices"
            ]
        elif overall_risk < RISK_MODERATE:
            risk_level = "MODERATE"
            risk_description = "Some risk factors detected. Monitor recovery closely."
            recommendations = [
                "Ensure adequate sleep (7-9 hours)",
                "Monitor recovery metrics daily",
                "Consider adding extra rest day if multiple factors worsen"
            ]
        elif overall_risk < RISK_HIGH:
            risk_level = "HIGH"
            risk_description = "Multiple risk factors elevated. Action needed to reduce injury risk."
            recommendations = [
                "Reduce training volume by 20-30% this week",
                "Add extra rest day",
                "Prioritize sleep and recovery",
                "Consider easy weeks only until metrics improve"
            ]
        else:
            risk_level = "CRITICAL"
            risk_description = "High injury risk detected. Immediate action required."
            recommendations = [
                "Take 2-3 complete rest days immediately",
                "Reduce training volume by 40-50% when resuming",
                "Prioritize sleep, nutrition, and stress management",
                "Consider consulting with sports medicine professional",
                "Do not attempt high-intensity workouts until recovery metrics normalize"
            ]

        # Identify primary concerns (risk score > 50)
        primary_concerns = []
        if acwr_risk['risk_score'] > 50:
            primary_concerns.append(f"ACWR: {acwr_risk['concern']}")
        if sleep_risk['risk_score'] > 50:
            primary_concerns.append(f"Sleep: {sleep_risk['concern']}")
        if rhr_risk['risk_score'] > 50:
            primary_concerns.append(f"RHR: {rhr_risk['concern']}")
        if hrv_risk['risk_score'] > 50:
            primary_concerns.append(f"HRV: {hrv_risk['concern']}")
        if readiness_risk['risk_score'] > 50:
            primary_concerns.append(f"Readiness: {readiness_risk['concern']}")
        if spike_risk['risk_score'] > 50:
            primary_concerns.append(f"Load Spike: {spike_risk['concern']}")

        return {
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'overall_risk_score': round(overall_risk, 1),
            'risk_level': risk_level,
            'risk_description': risk_description,
            'primary_concerns': primary_concerns,
            'recommendations': recommendations,
            'risk_factors': {
                'acwr': acwr_risk,
                'sleep': sleep_risk,
                'resting_hr': rhr_risk,
                'hrv': hrv_risk,
                'training_readiness': readiness_risk,
                'load_spike': spike_risk
            }
        }


def main():
    """Command-line interface for injury risk prediction"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Injury Risk Prediction')
    parser.add_argument('--cache', type=str,
                       default='data/health/health_data_cache.json',
                       help='Path to health data cache')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    # Resolve cache path
    cache_path = Path(args.cache)
    if not cache_path.is_absolute():
        cache_path = Path(__file__).parent.parent / args.cache

    try:
        predictor = InjuryRiskPredictor(str(cache_path))
        assessment = predictor.get_comprehensive_risk_assessment()

        if args.json:
            print(json.dumps(assessment, indent=2))
        else:
            print("\n" + "="*70)
            print("INJURY RISK ASSESSMENT")
            print("="*70)

            print(f"\nDate: {assessment['date']}")
            print(f"\nOverall Risk Score: {assessment['overall_risk_score']:.1f}/100")
            print(f"Risk Level: {assessment['risk_level']}")
            print(f"\n{assessment['risk_description']}")

            if assessment['primary_concerns']:
                print(f"\nPrimary Concerns:")
                for concern in assessment['primary_concerns']:
                    print(f"  • {concern}")

            print(f"\nRecommendations:")
            for rec in assessment['recommendations']:
                print(f"  • {rec}")

            print(f"\nDetailed Risk Factors:")
            factors = assessment['risk_factors']

            print(f"\n  ACWR (Workload Ratio): {factors['acwr']['risk_score']:.0f}/100")
            print(f"    {factors['acwr']['concern']}")

            print(f"\n  Sleep Quality: {factors['sleep']['risk_score']:.0f}/100")
            print(f"    {factors['sleep']['concern']}")
            if factors['sleep'].get('avg_duration_hrs'):
                print(f"    Avg: {factors['sleep']['avg_duration_hrs']:.1f} hrs/night")

            print(f"\n  Resting Heart Rate: {factors['resting_hr']['risk_score']:.0f}/100")
            print(f"    {factors['resting_hr']['concern']}")
            if factors['resting_hr'].get('avg_rhr'):
                print(f"    Current: {factors['resting_hr']['avg_rhr']} bpm "
                      f"(baseline: {factors['resting_hr']['baseline_rhr']} bpm)")

            print(f"\n  Heart Rate Variability: {factors['hrv']['risk_score']:.0f}/100")
            print(f"    {factors['hrv']['concern']}")

            print(f"\n  Training Readiness: {factors['training_readiness']['risk_score']:.0f}/100")
            print(f"    {factors['training_readiness']['concern']}")

            print(f"\n  Training Load Spike: {factors['load_spike']['risk_score']:.0f}/100")
            print(f"    {factors['load_spike']['concern']}")

            print("\n" + "="*70 + "\n")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
