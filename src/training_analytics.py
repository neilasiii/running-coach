#!/usr/bin/env python3
"""
Training Load Analytics Module

Provides training load calculations including:
- Training Stress Score (TSS) for individual workouts
- Acute Training Load (ATL) - 7-day fatigue metric
- Chronic Training Load (CTL) - 42-day fitness metric
- Training Stress Balance (TSB) - freshness/form metric
- Acute:Chronic Workload Ratio (ACWR) - injury risk indicator

Based on established training load methodologies from:
- Dr. Andrew Coggan (TSS/CTL/ATL/TSB - cycling performance modeling)
- Tim Gabbett (ACWR - injury risk research)
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import math


# Constants for TSS calculation
THRESHOLD_HR_PERCENTAGE = 0.85  # Lactate threshold is typically ~85% of max HR
TSS_PER_HOUR_AT_THRESHOLD = 100  # By definition, 1 hour at threshold = 100 TSS

# Constants for exponentially weighted moving averages
ATL_TIME_CONSTANT = 7   # Acute Training Load tracks ~7 days (fatigue)
CTL_TIME_CONSTANT = 42  # Chronic Training Load tracks ~42 days (fitness)

# Constants for ACWR
ACWR_ACUTE_DAYS = 7    # Acute workload window (recent training)
ACWR_CHRONIC_DAYS = 28  # Chronic workload window (long-term training)

# ACWR thresholds (based on Gabbett research)
ACWR_SAFE_LOWER = 0.8   # Below this: detraining risk
ACWR_SAFE_UPPER = 1.3   # Above this: injury risk increases
ACWR_DANGER_UPPER = 1.5  # High injury risk


class TrainingLoadAnalyzer:
    """
    Analyzes training load from activity data to calculate fitness, fatigue, and form metrics.
    """

    def __init__(self, cache_file: str):
        """
        Initialize analyzer with health data cache.

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

    def calculate_workout_tss(self, activity: Dict[str, Any], threshold_hr: Optional[int] = None) -> float:
        """
        Calculate Training Stress Score for a single workout.

        TSS formula: TSS = (duration_sec × IF² × 100) / 3600
        where IF (Intensity Factor) = normalized_intensity / threshold_intensity

        For running without power, we estimate IF from heart rate:
        IF = (avg_hr / threshold_hr)

        Args:
            activity: Activity dictionary from health data cache
            threshold_hr: Lactate threshold heart rate (bpm). If None, estimates from max HR.

        Returns:
            Training Stress Score (float)
        """
        # Skip non-running activities for now
        if activity.get('activity_type') != 'RUNNING':
            return 0.0

        duration_sec = activity.get('duration_seconds', 0)
        avg_hr = activity.get('avg_heart_rate')
        max_hr = activity.get('max_heart_rate')

        # Need HR data to calculate TSS
        if not avg_hr or duration_sec <= 0:
            return 0.0

        # Estimate threshold HR if not provided
        if threshold_hr is None:
            # Use lactate threshold from cache if available
            lt_data = self.cache.get('lactate_threshold', {})
            threshold_hr = lt_data.get('threshold_heart_rate_bpm')

            # Fallback: estimate from max HR (threshold ~85% of max)
            if threshold_hr is None and max_hr:
                threshold_hr = int(max_hr * THRESHOLD_HR_PERCENTAGE)

            # Last resort: use a conservative estimate (160 bpm)
            if threshold_hr is None:
                threshold_hr = 160

        # Calculate Intensity Factor (IF)
        # For HR-based: IF = avg_hr / threshold_hr
        intensity_factor = avg_hr / threshold_hr

        # Calculate TSS
        # TSS = (duration_hours × IF² × 100)
        duration_hours = duration_sec / 3600
        tss = duration_hours * (intensity_factor ** 2) * 100

        return round(tss, 1)

    def calculate_daily_tss(self, activities: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate total TSS for each day.

        Args:
            activities: List of activity dictionaries

        Returns:
            Dictionary mapping date (YYYY-MM-DD) to total TSS
        """
        daily_tss = {}

        for activity in activities:
            # Extract date (YYYY-MM-DD) from datetime
            activity_date = activity.get('date', '')[:10]
            if not activity_date:
                continue

            tss = self.calculate_workout_tss(activity)
            daily_tss[activity_date] = daily_tss.get(activity_date, 0) + tss

        return daily_tss

    def calculate_ctl_atl_tsb(self, daily_tss: Dict[str, float], end_date: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Calculate CTL (Chronic Training Load), ATL (Acute Training Load), and TSB (Training Stress Balance)
        for each day using exponentially weighted moving averages.

        CTL (Fitness): 42-day exponentially weighted average of TSS
        ATL (Fatigue): 7-day exponentially weighted average of TSS
        TSB (Form): CTL - ATL (positive = fresh, negative = fatigued)

        Args:
            daily_tss: Dictionary mapping date to TSS
            end_date: End date for calculations (YYYY-MM-DD). If None, uses today.

        Returns:
            Dictionary mapping date to {'ctl': float, 'atl': float, 'tsb': float}
        """
        if not daily_tss:
            return {}

        # Get date range
        all_dates = sorted(daily_tss.keys())
        start_date = datetime.fromisoformat(all_dates[0]).replace(tzinfo=None)
        if end_date:
            end_date_dt = datetime.fromisoformat(end_date).replace(tzinfo=None)
        else:
            end_date_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Initialize CTL and ATL (start at 0)
        ctl = 0.0
        atl = 0.0
        results = {}

        # Calculate exponential decay factors
        # Formula: new_value = yesterday_value + (today_tss - yesterday_value) / time_constant
        current_date = start_date

        while current_date <= end_date_dt:
            date_str = current_date.strftime('%Y-%m-%d')

            # Get TSS for this day (0 if rest day)
            today_tss = daily_tss.get(date_str, 0.0)

            # Update CTL (42-day fitness)
            ctl = ctl + (today_tss - ctl) / CTL_TIME_CONSTANT

            # Update ATL (7-day fatigue)
            atl = atl + (today_tss - atl) / ATL_TIME_CONSTANT

            # Calculate TSB (form = fitness - fatigue)
            tsb = ctl - atl

            results[date_str] = {
                'ctl': round(ctl, 1),
                'atl': round(atl, 1),
                'tsb': round(tsb, 1),
                'tss': round(today_tss, 1)
            }

            current_date += timedelta(days=1)

        return results

    def calculate_acwr(self, daily_tss: Dict[str, float], target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate Acute:Chronic Workload Ratio (ACWR) for injury risk assessment.

        ACWR = (7-day average load) / (28-day average load)

        Research by Tim Gabbett shows:
        - ACWR < 0.8: Detraining risk
        - ACWR 0.8-1.3: Sweet spot (optimal adaptation)
        - ACWR 1.3-1.5: Elevated injury risk
        - ACWR > 1.5: High injury risk

        Args:
            daily_tss: Dictionary mapping date to TSS
            target_date: Date to calculate ACWR for (YYYY-MM-DD). If None, uses today.

        Returns:
            Dictionary with ACWR metrics and risk assessment
        """
        if target_date:
            end_date = datetime.fromisoformat(target_date)
        else:
            end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Calculate date ranges
        acute_start = end_date - timedelta(days=ACWR_ACUTE_DAYS - 1)
        chronic_start = end_date - timedelta(days=ACWR_CHRONIC_DAYS - 1)

        # Sum TSS for acute and chronic windows
        acute_load = 0.0
        chronic_load = 0.0

        current_date = chronic_start
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            tss = daily_tss.get(date_str, 0.0)

            chronic_load += tss
            if current_date >= acute_start:
                acute_load += tss

            current_date += timedelta(days=1)

        # Calculate averages
        acute_avg = acute_load / ACWR_ACUTE_DAYS
        chronic_avg = chronic_load / ACWR_CHRONIC_DAYS

        # Calculate ACWR (handle division by zero)
        if chronic_avg > 0:
            acwr = acute_avg / chronic_avg
        else:
            acwr = 0.0

        # Assess risk level
        if acwr < ACWR_SAFE_LOWER:
            risk_level = "DETRAINING"
            risk_description = "Training load has decreased significantly. Risk of losing fitness."
        elif acwr <= ACWR_SAFE_UPPER:
            risk_level = "OPTIMAL"
            risk_description = "Training load is well-balanced for adaptation without excessive injury risk."
        elif acwr <= ACWR_DANGER_UPPER:
            risk_level = "ELEVATED"
            risk_description = "Training load spike detected. Moderate injury risk - consider reducing volume."
        else:
            risk_level = "HIGH"
            risk_description = "Significant training load spike. High injury risk - recommend reducing volume immediately."

        return {
            'date': end_date.strftime('%Y-%m-%d'),
            'acwr': round(acwr, 2),
            'acute_load': round(acute_load, 1),
            'chronic_load': round(chronic_load, 1),
            'acute_avg_daily': round(acute_avg, 1),
            'chronic_avg_daily': round(chronic_avg, 1),
            'risk_level': risk_level,
            'risk_description': risk_description
        }

    def get_training_load_summary(self, days: int = 90) -> Dict[str, Any]:
        """
        Generate comprehensive training load summary.

        Args:
            days: Number of days to analyze (default: 90)

        Returns:
            Dictionary with training load metrics and trends
        """
        # Get activities from cache
        activities = self.cache.get('activities', [])
        if not activities:
            return {'error': 'No activity data available'}

        # Calculate daily TSS
        daily_tss = self.calculate_daily_tss(activities)

        # Calculate CTL/ATL/TSB
        ctl_atl_tsb = self.calculate_ctl_atl_tsb(daily_tss)

        # Get most recent date with data
        if not ctl_atl_tsb:
            return {'error': 'Insufficient data for training load calculations'}

        latest_date = max(ctl_atl_tsb.keys())
        latest_metrics = ctl_atl_tsb[latest_date]

        # Calculate ACWR
        acwr_data = self.calculate_acwr(daily_tss, latest_date)

        # Calculate recent trends (14-day comparison)
        dates = sorted(ctl_atl_tsb.keys())
        if len(dates) >= 14:
            two_weeks_ago = dates[-14]
            trend_start = ctl_atl_tsb[two_weeks_ago]

            ctl_change = latest_metrics['ctl'] - trend_start['ctl']
            atl_change = latest_metrics['atl'] - trend_start['atl']
            tsb_change = latest_metrics['tsb'] - trend_start['tsb']
        else:
            ctl_change = 0
            atl_change = 0
            tsb_change = 0

        # Interpret TSB
        if latest_metrics['tsb'] > 10:
            form_status = "FRESH"
            form_description = "Well-rested and ready for hard training or racing"
        elif latest_metrics['tsb'] > -10:
            form_status = "NEUTRAL"
            form_description = "Balanced fitness and fatigue"
        elif latest_metrics['tsb'] > -30:
            form_status = "FATIGUED"
            form_description = "Accumulated fatigue - consider easier training"
        else:
            form_status = "OVERREACHED"
            form_description = "Significant fatigue accumulation - prioritize recovery"

        return {
            'date': latest_date,
            'current_metrics': {
                'ctl': latest_metrics['ctl'],
                'atl': latest_metrics['atl'],
                'tsb': latest_metrics['tsb'],
                'form_status': form_status,
                'form_description': form_description
            },
            'acwr': acwr_data,
            'trends_14day': {
                'ctl_change': round(ctl_change, 1),
                'atl_change': round(atl_change, 1),
                'tsb_change': round(tsb_change, 1)
            },
            'all_data': ctl_atl_tsb
        }

    def get_weekly_load_progression(self, weeks: int = 12) -> List[Dict[str, Any]]:
        """
        Get weekly training load progression.

        Args:
            weeks: Number of weeks to analyze (default: 12)

        Returns:
            List of weekly summaries with TSS totals
        """
        activities = self.cache.get('activities', [])
        daily_tss = self.calculate_daily_tss(activities)

        # Calculate week boundaries
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date - timedelta(days=end_date.weekday())  # Start from Monday

        weekly_data = []
        for week_num in range(weeks):
            week_start = end_date - timedelta(weeks=week_num, days=6)
            week_end = end_date - timedelta(weeks=week_num)

            # Sum TSS for this week
            week_tss = 0.0
            current_date = week_start
            while current_date <= week_end:
                date_str = current_date.strftime('%Y-%m-%d')
                week_tss += daily_tss.get(date_str, 0.0)
                current_date += timedelta(days=1)

            weekly_data.append({
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'total_tss': round(week_tss, 1),
                'avg_daily_tss': round(week_tss / 7, 1)
            })

        # Reverse to show oldest first
        return list(reversed(weekly_data))


def main():
    """Command-line interface for training load analytics"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Training Load Analytics')
    parser.add_argument('--cache', type=str,
                       default='data/health/health_data_cache.json',
                       help='Path to health data cache (default: data/health/health_data_cache.json)')
    parser.add_argument('--summary', action='store_true',
                       help='Show training load summary')
    parser.add_argument('--weekly', action='store_true',
                       help='Show weekly progression')
    parser.add_argument('--weeks', type=int, default=12,
                       help='Number of weeks for weekly progression (default: 12)')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    # Resolve cache path relative to script location if not absolute
    cache_path = Path(args.cache)
    if not cache_path.is_absolute():
        cache_path = Path(__file__).parent.parent / args.cache

    try:
        analyzer = TrainingLoadAnalyzer(str(cache_path))

        if args.summary:
            summary = analyzer.get_training_load_summary()

            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                print("\n" + "="*70)
                print("TRAINING LOAD SUMMARY")
                print("="*70)

                if 'error' in summary:
                    print(f"\nError: {summary['error']}")
                    return 1

                current = summary['current_metrics']
                print(f"\nDate: {summary['date']}")
                print(f"\nCurrent Training Load:")
                print(f"  CTL (Fitness):  {current['ctl']:6.1f}  - Long-term training load (42-day average)")
                print(f"  ATL (Fatigue):  {current['atl']:6.1f}  - Short-term training load (7-day average)")
                print(f"  TSB (Form):     {current['tsb']:6.1f}  - {current['form_status']}")
                print(f"                         {current['form_description']}")

                acwr = summary['acwr']
                print(f"\nInjury Risk (ACWR):")
                print(f"  Ratio: {acwr['acwr']:4.2f}  - {acwr['risk_level']}")
                print(f"  {acwr['risk_description']}")
                print(f"  7-day load:  {acwr['acute_load']:6.1f} TSS")
                print(f"  28-day load: {acwr['chronic_load']:6.1f} TSS")

                trends = summary['trends_14day']
                print(f"\n14-Day Trends:")
                print(f"  CTL: {trends['ctl_change']:+5.1f}  (Fitness {'building' if trends['ctl_change'] > 0 else 'declining'})")
                print(f"  ATL: {trends['atl_change']:+5.1f}  (Fatigue {'increasing' if trends['atl_change'] > 0 else 'decreasing'})")
                print(f"  TSB: {trends['tsb_change']:+5.1f}  (Form {'improving' if trends['tsb_change'] > 0 else 'declining'})")

                print("\n" + "="*70 + "\n")

        if args.weekly:
            weekly_data = analyzer.get_weekly_load_progression(args.weeks)

            if args.json:
                print(json.dumps(weekly_data, indent=2))
            else:
                print("\n" + "="*70)
                print(f"WEEKLY TRAINING LOAD PROGRESSION ({args.weeks} weeks)")
                print("="*70)
                print(f"\n{'Week Start':<12} {'Week End':<12} {'Total TSS':>12} {'Avg Daily':>12}")
                print("-" * 70)

                for week in weekly_data:
                    print(f"{week['week_start']:<12} {week['week_end']:<12} "
                          f"{week['total_tss']:>12.1f} {week['avg_daily_tss']:>12.1f}")

                print("\n" + "="*70 + "\n")

        if not args.summary and not args.weekly:
            print("No output selected. Use --summary or --weekly", file=sys.stderr)
            parser.print_help()
            return 1

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
