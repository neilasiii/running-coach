#!/usr/bin/env python3
"""
VDOT Calculator and Auto-Adjustment System

Implements Jack Daniels' VDOT methodology for:
- Calculating VDOT from race performances
- Generating training paces from VDOT
- Auto-adjusting VDOT based on workout performance
- Tracking fitness progression over time

Based on:
- "Daniels' Running Formula" by Jack Daniels, PhD
- VDOT tables and pace calculations from proven running science
"""

import json
import sys
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


# VDOT pace calculation constants
# These are empirically derived from Jack Daniels' research
VDOT_VELOCITY_CONSTANTS = {
    'E': 0.65,   # Easy pace: 65% of VDOT
    'M': 0.78,   # Marathon pace: 78% of VDOT
    'T': 0.88,   # Threshold pace: 88% of VDOT
    'I': 0.98,   # Interval pace: 98% of VDOT
    'R': 1.05    # Repetition pace: 105% of VDOT
}

# Standard race distances (meters)
RACE_DISTANCES = {
    '5K': 5000,
    '10K': 10000,
    'Half': 21097.5,
    'Marathon': 42195
}


class VDOTCalculator:
    """
    Calculate and adjust VDOT based on performance data.
    """

    def __init__(self, cache_file: str):
        """
        Initialize calculator with health data cache.

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

    def calculate_vo2(self, velocity_mpm: float) -> float:
        """
        Calculate VO2 from running velocity using Jack Daniels' formula.

        VO2 = -4.60 + 0.182258 * v + 0.000104 * v²
        where v is velocity in meters/minute

        Args:
            velocity_mpm: Velocity in meters per minute

        Returns:
            VO2 in ml/kg/min
        """
        v = velocity_mpm
        vo2 = -4.60 + 0.182258 * v + 0.000104 * (v ** 2)
        return vo2

    def calculate_percent_max(self, time_seconds: float) -> float:
        """
        Calculate percentage of VO2max based on race duration.

        Uses Jack Daniels' oxygen cost curves accounting for
        the fact that longer efforts can't sustain max VO2.

        Args:
            time_seconds: Race time in seconds

        Returns:
            Percentage of VO2max (0-1.0)
        """
        time_minutes = time_seconds / 60

        # Empirical formula from Daniels' research
        # Shorter races = higher % of VO2max sustained
        if time_minutes <= 3:
            return 1.0
        elif time_minutes <= 8:
            return 0.96 + (8 - time_minutes) * 0.008
        elif time_minutes <= 15:
            return 0.92 + (15 - time_minutes) * 0.00571
        elif time_minutes <= 30:
            return 0.88 + (30 - time_minutes) * 0.00267
        elif time_minutes <= 60:
            return 0.85 + (60 - time_minutes) * 0.001
        elif time_minutes <= 120:
            return 0.83 + (120 - time_minutes) * 0.000333
        elif time_minutes <= 180:
            return 0.81 + (180 - time_minutes) * 0.000333
        else:
            return 0.80

    def calculate_vdot_from_race(self, distance_meters: float, time_seconds: float) -> float:
        """
        Calculate VDOT from race performance using Jack Daniels' formula.

        Args:
            distance_meters: Race distance in meters
            time_seconds: Race time in seconds

        Returns:
            VDOT value
        """
        # Calculate velocity
        velocity_mpm = distance_meters / (time_seconds / 60)

        # Calculate VO2 at this velocity
        vo2 = self.calculate_vo2(velocity_mpm)

        # Adjust for percentage of max sustainable at this duration
        percent_max = self.calculate_percent_max(time_seconds)

        # VDOT = VO2 / percent_max
        vdot = vo2 / percent_max

        return round(vdot, 1)

    def calculate_training_paces(self, vdot: float) -> Dict[str, Dict[str, Any]]:
        """
        Calculate training paces for all zones from VDOT.

        Args:
            vdot: VDOT value

        Returns:
            Dictionary of pace zones with min/max paces in min/mile and min/km
        """
        paces = {}

        # For each training zone, calculate velocity and convert to pace
        for zone, percent in VDOT_VELOCITY_CONSTANTS.items():
            # Target VO2 for this zone
            target_vo2 = vdot * percent

            # Solve velocity from VO2 equation (quadratic formula)
            # VO2 = -4.60 + 0.182258 * v + 0.000104 * v²
            # Rearranged: 0.000104 * v² + 0.182258 * v + (-4.60 - VO2) = 0
            a = 0.000104
            b = 0.182258
            c = -4.60 - target_vo2

            discriminant = b**2 - 4*a*c
            if discriminant < 0:
                continue

            velocity_mpm = (-b + math.sqrt(discriminant)) / (2 * a)

            # Convert to pace (min/mile and min/km)
            # velocity is meters/minute
            pace_per_mile = 1609.34 / velocity_mpm  # minutes per mile
            pace_per_km = 1000 / velocity_mpm  # minutes per km

            # Format as MM:SS
            pace_mile_min = int(pace_per_mile)
            pace_mile_sec = int((pace_per_mile - pace_mile_min) * 60)
            pace_km_min = int(pace_per_km)
            pace_km_sec = int((pace_per_km - pace_km_min) * 60)

            # Add range (±5-10 seconds depending on zone)
            range_sec = 10 if zone in ['E', 'M'] else 5

            paces[zone] = {
                'pace_per_mile': f"{pace_mile_min}:{pace_mile_sec:02d}",
                'pace_per_km': f"{pace_km_min}:{pace_km_sec:02d}",
                'pace_per_mile_range': f"{pace_mile_min}:{max(0, pace_mile_sec-range_sec):02d}-{pace_mile_min}:{min(59, pace_mile_sec+range_sec):02d}",
                'velocity_mpm': round(velocity_mpm, 2)
            }

        return paces

    def calculate_race_predictions(self, vdot: float) -> Dict[str, str]:
        """
        Predict race times for standard distances from VDOT.

        Args:
            vdot: VDOT value

        Returns:
            Dictionary of predicted race times
        """
        predictions = {}

        for race_name, distance_m in RACE_DISTANCES.items():
            # Binary search for time that gives this VDOT
            # Start with reasonable bounds
            min_time = 300  # 5 minutes
            max_time = 18000  # 5 hours

            target_vdot = vdot
            best_time = None

            for _ in range(50):  # Binary search iterations
                mid_time = (min_time + max_time) / 2
                calculated_vdot = self.calculate_vdot_from_race(distance_m, mid_time)

                if abs(calculated_vdot - target_vdot) < 0.1:
                    best_time = mid_time
                    break

                if calculated_vdot < target_vdot:
                    max_time = mid_time
                else:
                    min_time = mid_time

            if best_time:
                # Format as HH:MM:SS
                hours = int(best_time // 3600)
                minutes = int((best_time % 3600) // 60)
                seconds = int(best_time % 60)

                if hours > 0:
                    predictions[race_name] = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    predictions[race_name] = f"{minutes}:{seconds:02d}"

        return predictions

    def estimate_vdot_from_vo2max(self, vo2_max: float) -> float:
        """
        Estimate VDOT from VO2 max.

        Note: VDOT ≈ VO2max for elite runners with excellent running economy.
        For recreational runners, VDOT is typically 10-20% lower than VO2max due to
        running economy factors (biomechanics, efficiency, etc).

        Args:
            vo2_max: VO2 max in ml/kg/min

        Returns:
            Estimated VDOT (conservative estimate)
        """
        # Conservative conversion accounting for typical running economy
        # Most recreational runners: VDOT = 0.80-0.85 * VO2max
        # Well-trained runners: VDOT = 0.90-0.95 * VO2max
        # Elite runners: VDOT ≈ 0.98-1.00 * VO2max
        # Use 0.85 as reasonable middle ground for trained recreational runners
        return round(vo2_max * 0.85, 1)

    def estimate_vdot_from_workouts(self, days: int = 60) -> Optional[float]:
        """
        Estimate VDOT from actual workout paces using heart rate to identify effort level.

        More accurate than VO2max estimation as it accounts for actual running economy.

        Args:
            days: Number of days of workouts to analyze (default: 60)

        Returns:
            Estimated VDOT from workout paces, or None if insufficient data
        """
        activities = self.cache.get('activities', [])
        if not activities:
            return None

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent_runs = [a for a in activities
                      if a.get('activity_type') == 'RUNNING' and a.get('date', '') >= cutoff]

        # Collect workouts at different effort levels based on HR and duration
        marathon_effort_runs = []  # HR 145-160, 45+ min
        tempo_runs = []  # HR 160-170, 20-40 min

        for activity in recent_runs:
            duration_min = activity.get('duration_seconds', 0) / 60
            pace = activity.get('pace_per_mile', 0)
            distance = activity.get('distance_miles', 0)
            avg_hr = activity.get('avg_heart_rate', 0)

            if pace == 0 or distance == 0 or avg_hr == 0:
                continue

            # True marathon pace runs: 8:30-9:30 pace, HR 150-165, 45+ min
            # These are runs specifically at or near goal marathon pace
            if 8.5 <= pace <= 9.5 and 150 <= avg_hr <= 165 and duration_min >= 45:
                # This is actual marathon effort - use pace directly with minimal adjustment
                estimated_marathon_pace = pace * 1.005  # Tiny adjustment for race day fatigue
                marathon_effort_runs.append(estimated_marathon_pace)

            # Moderate sustained runs: HR 145-160, duration 60+ min (likely marathon training pace)
            # But exclude if pace is too slow (>10:00 = easy runs)
            elif 145 <= avg_hr <= 160 and duration_min >= 60 and pace < 10.0:
                # These sustained efforts at moderate pace estimate marathon capability
                estimated_marathon_pace = pace * 1.02
                marathon_effort_runs.append(estimated_marathon_pace)

            # Tempo/Threshold runs: HR 160-172, duration 20-50 min, faster pace
            # Convert to marathon equivalent
            elif 160 <= avg_hr <= 172 and 20 <= duration_min <= 50 and pace < 9.5:
                # Threshold pace is about 6-8% faster than marathon
                estimated_marathon_pace = pace * 1.07  # Threshold to marathon conversion
                tempo_runs.append(estimated_marathon_pace)

        # Prioritize marathon effort runs, use tempo as backup
        if marathon_effort_runs:
            avg_marathon_pace = sum(marathon_effort_runs) / len(marathon_effort_runs)
        elif tempo_runs:
            avg_marathon_pace = sum(tempo_runs) / len(tempo_runs)
        else:
            return None

        # Convert pace (min/mile) to marathon time
        marathon_time_seconds = avg_marathon_pace * 26.2 * 60

        # Calculate VDOT from this marathon performance
        vdot = self.calculate_vdot_from_race(RACE_DISTANCES['Marathon'], marathon_time_seconds)

        return vdot

    def analyze_workout_performance(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze recent workout performance to detect if VDOT needs adjustment.

        Looks for patterns:
        - Consistently hitting paces at lower HR than expected → VDOT may be too low
        - Struggling to hit paces even at high HR → VDOT may be too high
        - Pace drift over time → fitness change

        Args:
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with performance analysis and VDOT adjustment recommendations
        """
        activities = self.cache.get('activities', [])
        if not activities:
            return {'error': 'No activity data available'}

        # Filter recent running activities
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent_runs = [a for a in activities
                      if a.get('activity_type') == 'RUNNING' and a.get('date', '') >= cutoff]

        if not recent_runs:
            return {'error': 'No recent running activities'}

        # Analyze pace and HR trends
        workout_quality_scores = []
        pace_improvements = []

        for activity in recent_runs:
            avg_pace = activity.get('pace_per_mile', 0)
            avg_hr = activity.get('avg_heart_rate', 0)

            if avg_pace == 0 or avg_hr == 0:
                continue

            # Estimate expected HR for this pace based on typical HR zones
            # This is a rough heuristic:
            # Easy pace (10:00+): HR ~130-145
            # Moderate pace (8:30-10:00): HR ~145-160
            # Threshold pace (8:00-8:30): HR ~160-170
            # Interval pace (<8:00): HR ~170+

            if avg_pace >= 10:
                expected_hr_min = 130
                expected_hr_max = 145
                intensity = 'easy'
            elif avg_pace >= 8.5:
                expected_hr_min = 145
                expected_hr_max = 160
                intensity = 'moderate'
            elif avg_pace >= 8.0:
                expected_hr_min = 160
                expected_hr_max = 170
                intensity = 'threshold'
            else:
                expected_hr_min = 170
                expected_hr_max = 185
                intensity = 'interval'

            # Score: negative if HR is lower than expected (good), positive if higher (struggling)
            if avg_hr < expected_hr_min:
                quality_score = (expected_hr_min - avg_hr) / 10  # More aerobically efficient
            elif avg_hr > expected_hr_max:
                quality_score = -(avg_hr - expected_hr_max) / 10  # Less efficient
            else:
                quality_score = 0  # Within expected range

            workout_quality_scores.append(quality_score)

        # Calculate average quality score
        if not workout_quality_scores:
            return {'error': 'Insufficient data for analysis'}

        avg_quality = sum(workout_quality_scores) / len(workout_quality_scores)

        # Get current VO2 max from Garmin
        vo2_readings = self.cache.get('vo2_max_readings', [])
        current_vo2_max = vo2_readings[0]['vo2_max'] if vo2_readings else None

        # Make VDOT adjustment recommendation
        if avg_quality > 1.0:
            recommendation = "INCREASE"
            adjustment = "+2 to +3"
            reasoning = "Consistently hitting paces at lower heart rates than expected. Fitness has improved."
        elif avg_quality > 0.5:
            recommendation = "SLIGHT INCREASE"
            adjustment = "+1"
            reasoning = "Some evidence of improved efficiency. Consider small upward adjustment."
        elif avg_quality < -1.0:
            recommendation = "DECREASE"
            adjustment = "-2 to -3"
            reasoning = "Struggling to maintain paces even at elevated heart rates. May be overtrained or VDOT set too high."
        elif avg_quality < -0.5:
            recommendation = "SLIGHT DECREASE"
            adjustment = "-1"
            reasoning = "Some workouts showing higher effort than expected for paces. Consider small downward adjustment."
        else:
            recommendation = "MAINTAIN"
            adjustment = "0"
            reasoning = "Workout performance aligns well with current VDOT. No adjustment needed."

        # Estimate current VDOT from multiple sources
        estimated_vdot_vo2 = None
        estimated_vdot_workouts = None

        if current_vo2_max:
            estimated_vdot_vo2 = self.estimate_vdot_from_vo2max(current_vo2_max)

        # Get VDOT from actual workout paces (most accurate)
        estimated_vdot_workouts = self.estimate_vdot_from_workouts(days=60)

        # Use workout-based estimate as primary if available
        best_vdot_estimate = estimated_vdot_workouts if estimated_vdot_workouts else estimated_vdot_vo2

        return {
            'workouts_analyzed': len(workout_quality_scores),
            'avg_quality_score': round(avg_quality, 2),
            'recommendation': recommendation,
            'adjustment': adjustment,
            'reasoning': reasoning,
            'current_vo2_max': current_vo2_max,
            'estimated_vdot_from_vo2': estimated_vdot_vo2,
            'estimated_vdot_from_workouts': estimated_vdot_workouts,
            'best_vdot_estimate': best_vdot_estimate,
            'analysis_period_days': days
        }

    def track_vdot_progression(self) -> List[Dict[str, Any]]:
        """
        Track VDOT progression over time using VO2 max readings.

        Returns:
            List of VDOT estimates over time
        """
        vo2_readings = self.cache.get('vo2_max_readings', [])
        if not vo2_readings:
            return []

        progression = []
        for reading in vo2_readings:
            vo2_max = reading.get('vo2_max')
            date = reading.get('date', '')[:10]

            if vo2_max:
                estimated_vdot = self.estimate_vdot_from_vo2max(vo2_max)
                progression.append({
                    'date': date,
                    'vo2_max': vo2_max,
                    'estimated_vdot': estimated_vdot
                })

        return list(reversed(progression))  # Oldest first


def main():
    """Command-line interface for VDOT calculator"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='VDOT Calculator and Adjustment')
    parser.add_argument('--cache', type=str,
                       default='data/health/health_data_cache.json',
                       help='Path to health data cache')
    parser.add_argument('--race', nargs=2, metavar=('DISTANCE', 'TIME'),
                       help='Calculate VDOT from race: DISTANCE (5K/10K/Half/Marathon) TIME (MM:SS or HH:MM:SS)')
    parser.add_argument('--vdot', type=float,
                       help='Calculate training paces for given VDOT')
    parser.add_argument('--predict', type=float, metavar='VDOT',
                       help='Predict race times for given VDOT')
    parser.add_argument('--analyze', action='store_true',
                       help='Analyze recent workout performance')
    parser.add_argument('--progression', action='store_true',
                       help='Show VDOT progression over time')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    # Resolve cache path
    cache_path = Path(args.cache)
    if not cache_path.is_absolute():
        cache_path = Path(__file__).parent.parent / args.cache

    try:
        calc = VDOTCalculator(str(cache_path))

        if args.race:
            distance_name, time_str = args.race
            if distance_name not in RACE_DISTANCES:
                print(f"Error: Unknown distance '{distance_name}'. Use: 5K, 10K, Half, or Marathon", file=sys.stderr)
                return 1

            distance_m = RACE_DISTANCES[distance_name]

            # Parse time
            time_parts = time_str.split(':')
            if len(time_parts) == 2:  # MM:SS
                time_sec = int(time_parts[0]) * 60 + int(time_parts[1])
            elif len(time_parts) == 3:  # HH:MM:SS
                time_sec = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            else:
                print(f"Error: Invalid time format '{time_str}'. Use MM:SS or HH:MM:SS", file=sys.stderr)
                return 1

            vdot = calc.calculate_vdot_from_race(distance_m, time_sec)
            paces = calc.calculate_training_paces(vdot)

            if args.json:
                print(json.dumps({'vdot': vdot, 'paces': paces}, indent=2))
            else:
                print(f"\nVDOT from {distance_name} in {time_str}: {vdot}")
                print("\nTraining Paces:")
                print(f"  Easy (E):       {paces['E']['pace_per_mile_range']} /mile")
                print(f"  Marathon (M):   {paces['M']['pace_per_mile_range']} /mile")
                print(f"  Threshold (T):  {paces['T']['pace_per_mile_range']} /mile")
                print(f"  Interval (I):   {paces['I']['pace_per_mile_range']} /mile")
                print(f"  Repetition (R): {paces['R']['pace_per_mile_range']} /mile")

        elif args.vdot:
            paces = calc.calculate_training_paces(args.vdot)

            if args.json:
                print(json.dumps(paces, indent=2))
            else:
                print(f"\nTraining Paces for VDOT {args.vdot}:")
                print(f"  Easy (E):       {paces['E']['pace_per_mile_range']} /mile")
                print(f"  Marathon (M):   {paces['M']['pace_per_mile_range']} /mile")
                print(f"  Threshold (T):  {paces['T']['pace_per_mile_range']} /mile")
                print(f"  Interval (I):   {paces['I']['pace_per_mile_range']} /mile")
                print(f"  Repetition (R): {paces['R']['pace_per_mile_range']} /mile")

        elif args.predict:
            predictions = calc.calculate_race_predictions(args.predict)

            if args.json:
                print(json.dumps(predictions, indent=2))
            else:
                print(f"\nRace Time Predictions for VDOT {args.predict}:")
                for race, time in predictions.items():
                    print(f"  {race:10s}: {time}")

        elif args.analyze:
            analysis = calc.analyze_workout_performance()

            if args.json:
                print(json.dumps(analysis, indent=2))
            else:
                if 'error' in analysis:
                    print(f"Error: {analysis['error']}", file=sys.stderr)
                    return 1

                print("\n" + "="*70)
                print("WORKOUT PERFORMANCE ANALYSIS")
                print("="*70)

                print(f"\nWorkouts Analyzed: {analysis['workouts_analyzed']} (last {analysis['analysis_period_days']} days)")
                print(f"Quality Score: {analysis['avg_quality_score']:.2f}")
                print(f"\nRecommendation: {analysis['recommendation']} VDOT by {analysis['adjustment']}")
                print(f"Reasoning: {analysis['reasoning']}")

                print(f"\nVDOT Estimates:")
                if analysis.get('estimated_vdot_from_workouts'):
                    print(f"  From workout paces: {analysis['estimated_vdot_from_workouts']} (MOST ACCURATE)")
                if analysis.get('current_vo2_max'):
                    print(f"  From VO2 max ({analysis['current_vo2_max']} ml/kg/min): {analysis['estimated_vdot_from_vo2']}")
                if analysis.get('best_vdot_estimate'):
                    print(f"\n  → Recommended VDOT: {analysis['best_vdot_estimate']}")

                print("\n" + "="*70 + "\n")

        elif args.progression:
            progression = calc.track_vdot_progression()

            if args.json:
                print(json.dumps(progression, indent=2))
            else:
                print("\n" + "="*70)
                print("VDOT PROGRESSION")
                print("="*70)
                print(f"\n{'Date':<12} {'VO2 Max':>10} {'Est. VDOT':>12}")
                print("-" * 70)

                for entry in progression:
                    print(f"{entry['date']:<12} {entry['vo2_max']:>10.1f} {entry['estimated_vdot']:>12.1f}")

                print("\n" + "="*70 + "\n")

        else:
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
