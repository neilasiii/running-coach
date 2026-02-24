#!/usr/bin/env python3
"""
Environmental pace adjustments for running workouts.

Calculates pace adjustments based on:
- Temperature and humidity (heat stress)
- Elevation gain
- Altitude

Based on research from:
- Temperature: "Maximum Performance Running" methodology (1% per °F above 60°F)
- Elevation: "Downhill All the Way" principles (3.3% per 1% grade)
- Altitude: Standard altitude adjustment (1% per 1000 feet)
- Heat index: Standard NOAA formula for apparent temperature
"""

import math
from typing import Dict, Optional, Tuple


def calculate_heat_index(temp_f: float, humidity: float) -> float:
    """
    Calculate heat index (apparent temperature) using NOAA formula.

    Args:
        temp_f: Temperature in Fahrenheit
        humidity: Relative humidity (0-100)

    Returns:
        Heat index in Fahrenheit
    """
    # Simple formula for temps < 80°F
    if temp_f < 80:
        return 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (humidity * 0.094))

    # Rothfusz regression for higher temps
    T = temp_f
    RH = humidity

    HI = (-42.379 + 2.04901523 * T + 10.14333127 * RH - 0.22475541 * T * RH
          - 0.00683783 * T * T - 0.05481717 * RH * RH + 0.00122874 * T * T * RH
          + 0.00085282 * T * RH * RH - 0.00000199 * T * T * RH * RH)

    # Adjustments for specific conditions
    if RH < 13 and 80 <= T <= 112:
        HI -= ((13 - RH) / 4) * math.sqrt((17 - abs(T - 95)) / 17)
    elif RH > 85 and 80 <= T <= 87:
        HI += ((RH - 85) / 10) * ((87 - T) / 5)

    return HI


def pace_seconds_to_string(pace_seconds: float) -> str:
    """Convert pace in seconds per mile to MM:SS format."""
    minutes = int(pace_seconds // 60)
    seconds = int(pace_seconds % 60)
    return f"{minutes}:{seconds:02d}"


def adjust_pace_for_temperature(pace_seconds_per_mile: float,
                                 temp_f: float,
                                 baseline_temp_f: float = 60.0) -> Tuple[float, float]:
    """
    Adjust running pace for temperature.

    Based on "Maximum Performance Running" methodology:
    - 1% slowdown per degree F above 60°F baseline
    - No adjustment for temps below baseline

    Args:
        pace_seconds_per_mile: Current pace in seconds per mile
        temp_f: Current temperature in Fahrenheit
        baseline_temp_f: Baseline temperature (default 60°F)

    Returns:
        Tuple of (adjusted_pace_seconds, slowdown_percentage)
    """
    # Only adjust if above baseline
    if temp_f <= baseline_temp_f:
        return pace_seconds_per_mile, 0.0

    # 1% slower per degree above baseline
    temp_diff = temp_f - baseline_temp_f
    slowdown_percent = temp_diff * 1.0

    adjusted_pace = pace_seconds_per_mile * (1 + slowdown_percent / 100)
    return adjusted_pace, slowdown_percent


def adjust_pace_for_heat_index(pace_seconds_per_mile: float,
                                heat_index_f: float,
                                baseline_hi_f: float = 60.0) -> Tuple[float, float]:
    """
    Adjust running pace for heat index (combined heat and humidity).

    More accurate than temperature alone as it accounts for humidity's
    impact on evaporative cooling.

    Args:
        pace_seconds_per_mile: Current pace in seconds per mile
        heat_index_f: Heat index in Fahrenheit
        baseline_hi_f: Baseline heat index (default 60°F)

    Returns:
        Tuple of (adjusted_pace_seconds, slowdown_percentage)
    """
    # Similar to temperature adjustment but uses heat index
    if heat_index_f <= baseline_hi_f:
        return pace_seconds_per_mile, 0.0

    # Progressive slowdown based on heat index ranges
    # Moderate: 1% per degree 60-80°F
    # High: 1.5% per degree 80-90°F
    # Extreme: 2% per degree above 90°F

    slowdown_percent = 0.0

    if heat_index_f > baseline_hi_f:
        # 60-80°F range: 1% per degree
        range1_degrees = min(heat_index_f, 80) - baseline_hi_f
        if range1_degrees > 0:
            slowdown_percent += range1_degrees * 1.0

    if heat_index_f > 80:
        # 80-90°F range: 1.5% per degree
        range2_degrees = min(heat_index_f, 90) - 80
        if range2_degrees > 0:
            slowdown_percent += range2_degrees * 1.5

    if heat_index_f > 90:
        # Above 90°F: 2% per degree
        range3_degrees = heat_index_f - 90
        slowdown_percent += range3_degrees * 2.0

    adjusted_pace = pace_seconds_per_mile * (1 + slowdown_percent / 100)
    return adjusted_pace, slowdown_percent


def adjust_pace_for_elevation(pace_seconds_per_mile: float,
                               distance_miles: float,
                               elevation_gain_feet: float) -> Tuple[float, float]:
    """
    Adjust running pace for elevation gain.

    Based on "Downhill All the Way" (Runner's World) principles:
    - 3.3% slowdown per 1% grade

    Args:
        pace_seconds_per_mile: Current pace in seconds per mile
        distance_miles: Total distance in miles
        elevation_gain_feet: Total elevation gain in feet

    Returns:
        Tuple of (adjusted_pace_seconds, slowdown_percentage)
    """
    if distance_miles <= 0 or elevation_gain_feet <= 0:
        return pace_seconds_per_mile, 0.0

    # Calculate average grade percentage
    elevation_gain_miles = elevation_gain_feet / 5280
    grade_percent = (elevation_gain_miles / distance_miles) * 100

    # 3.3% slowdown per 1% grade
    slowdown_percent = grade_percent * 3.3

    adjusted_pace = pace_seconds_per_mile * (1 + slowdown_percent / 100)
    return adjusted_pace, slowdown_percent


def adjust_pace_for_altitude(pace_seconds_per_mile: float,
                             altitude_feet: float,
                             baseline_altitude_feet: float = 0) -> Tuple[float, float]:
    """
    Adjust running pace for altitude.

    Standard altitude adjustment:
    - 1% slowdown per 1000 feet above baseline

    Args:
        pace_seconds_per_mile: Current pace in seconds per mile
        altitude_feet: Current altitude in feet
        baseline_altitude_feet: Baseline altitude (default sea level)

    Returns:
        Tuple of (adjusted_pace_seconds, slowdown_percentage)
    """
    altitude_diff = altitude_feet - baseline_altitude_feet

    if altitude_diff <= 0:
        return pace_seconds_per_mile, 0.0

    # 1% per 1000 feet
    slowdown_percent = (altitude_diff / 1000) * 1.0

    adjusted_pace = pace_seconds_per_mile * (1 + slowdown_percent / 100)
    return adjusted_pace, slowdown_percent


def calculate_environmental_adjustment(
    pace_seconds_per_mile: float,
    temp_f: Optional[float] = None,
    humidity: Optional[float] = None,
    distance_miles: Optional[float] = None,
    elevation_gain_feet: Optional[float] = None,
    altitude_feet: Optional[float] = None,
    baseline_altitude_feet: float = 0,
    use_heat_index: bool = True
) -> Dict[str, any]:
    """
    Calculate comprehensive environmental pace adjustments.

    Args:
        pace_seconds_per_mile: Base pace in seconds per mile
        temp_f: Temperature in Fahrenheit
        humidity: Relative humidity (0-100)
        distance_miles: Distance for elevation calculation
        elevation_gain_feet: Total elevation gain
        altitude_feet: Current altitude
        baseline_altitude_feet: Baseline altitude for comparison
        use_heat_index: Use heat index instead of temperature alone (more accurate)

    Returns:
        Dictionary with adjustment details:
        - adjusted_pace: Final adjusted pace in seconds/mile
        - original_pace_str: Original pace as MM:SS
        - adjusted_pace_str: Adjusted pace as MM:SS
        - total_slowdown_percent: Combined slowdown percentage
        - factors: Dict of individual adjustment factors
        - recommendations: List of coaching recommendations
    """
    factors = {}
    total_slowdown_percent = 0.0
    recommendations = []

    # Heat/temperature adjustment
    if temp_f is not None and humidity is not None and use_heat_index:
        heat_index = calculate_heat_index(temp_f, humidity)
        adjusted, slowdown = adjust_pace_for_heat_index(pace_seconds_per_mile, heat_index)

        factors['heat_index'] = {
            'value': round(heat_index, 1),
            'slowdown_percent': round(slowdown, 1),
            'adjusted_pace': adjusted
        }
        total_slowdown_percent += slowdown

        if heat_index >= 90:
            recommendations.append("EXTREME HEAT: Consider indoor treadmill or postpone workout")
        elif heat_index >= 80:
            recommendations.append("High heat stress: Reduce effort, increase hydration")
        elif heat_index >= 70:
            recommendations.append("Moderate heat: Stay hydrated, consider slower pace")

    elif temp_f is not None:
        adjusted, slowdown = adjust_pace_for_temperature(pace_seconds_per_mile, temp_f)

        factors['temperature'] = {
            'value': round(temp_f, 1),
            'slowdown_percent': round(slowdown, 1),
            'adjusted_pace': adjusted
        }
        total_slowdown_percent += slowdown

    # Elevation adjustment
    if distance_miles is not None and elevation_gain_feet is not None:
        adjusted, slowdown = adjust_pace_for_elevation(
            pace_seconds_per_mile, distance_miles, elevation_gain_feet
        )

        grade_percent = (elevation_gain_feet / 5280 / distance_miles) * 100 if distance_miles > 0 else 0

        factors['elevation'] = {
            'gain_feet': elevation_gain_feet,
            'grade_percent': round(grade_percent, 1),
            'slowdown_percent': round(slowdown, 1),
            'adjusted_pace': adjusted
        }
        total_slowdown_percent += slowdown

        if grade_percent > 3:
            recommendations.append(f"Hilly course ({grade_percent:.1f}% avg grade): Focus on effort, not pace")

    # Altitude adjustment
    if altitude_feet is not None:
        adjusted, slowdown = adjust_pace_for_altitude(
            pace_seconds_per_mile, altitude_feet, baseline_altitude_feet
        )

        factors['altitude'] = {
            'current_feet': altitude_feet,
            'baseline_feet': baseline_altitude_feet,
            'slowdown_percent': round(slowdown, 1),
            'adjusted_pace': adjusted
        }
        total_slowdown_percent += slowdown

        if altitude_feet > 5000:
            recommendations.append(f"High altitude ({altitude_feet}ft): Allow extra recovery time")

    # Calculate final adjusted pace
    final_adjusted_pace = pace_seconds_per_mile * (1 + total_slowdown_percent / 100)

    return {
        'original_pace': pace_seconds_per_mile,
        'adjusted_pace': final_adjusted_pace,
        'original_pace_str': pace_seconds_to_string(pace_seconds_per_mile),
        'adjusted_pace_str': pace_seconds_to_string(final_adjusted_pace),
        'total_slowdown_percent': round(total_slowdown_percent, 1),
        'factors': factors,
        'recommendations': recommendations
    }


def format_adjustment_summary(adjustment: Dict) -> str:
    """
    Format adjustment results as human-readable summary.

    Args:
        adjustment: Result from calculate_environmental_adjustment()

    Returns:
        Formatted string summary
    """
    lines = []

    # Header
    lines.append(f"Pace Adjustment: {adjustment['original_pace_str']} → {adjustment['adjusted_pace_str']}")
    lines.append(f"Total slowdown: {adjustment['total_slowdown_percent']}%")
    lines.append("")

    # Individual factors
    if adjustment['factors']:
        lines.append("Contributing factors:")

        if 'heat_index' in adjustment['factors']:
            hi = adjustment['factors']['heat_index']
            lines.append(f"  • Heat index: {hi['value']}°F (+{hi['slowdown_percent']}%)")

        if 'temperature' in adjustment['factors']:
            temp = adjustment['factors']['temperature']
            lines.append(f"  • Temperature: {temp['value']}°F (+{temp['slowdown_percent']}%)")

        if 'elevation' in adjustment['factors']:
            elev = adjustment['factors']['elevation']
            lines.append(f"  • Elevation: {elev['gain_feet']}ft gain, {elev['grade_percent']}% avg grade (+{elev['slowdown_percent']}%)")

        if 'altitude' in adjustment['factors']:
            alt = adjustment['factors']['altitude']
            lines.append(f"  • Altitude: {alt['current_feet']}ft (+{alt['slowdown_percent']}%)")

        lines.append("")

    # Recommendations
    if adjustment['recommendations']:
        lines.append("Recommendations:")
        for rec in adjustment['recommendations']:
            lines.append(f"  • {rec}")

    return "\n".join(lines)


if __name__ == '__main__':
    """Example usage and testing."""
    import argparse

    parser = argparse.ArgumentParser(description='Calculate environmental pace adjustments')
    parser.add_argument('--pace', type=str, required=True, help='Base pace as MM:SS (e.g., "9:10")')
    parser.add_argument('--temp', type=float, help='Temperature in Fahrenheit')
    parser.add_argument('--humidity', type=float, help='Relative humidity (0-100)')
    parser.add_argument('--distance', type=float, help='Distance in miles')
    parser.add_argument('--elevation', type=float, help='Elevation gain in feet')
    parser.add_argument('--altitude', type=float, help='Current altitude in feet')
    parser.add_argument('--baseline-altitude', type=float, default=0, help='Baseline altitude in feet')

    args = parser.parse_args()

    # Parse pace
    parts = args.pace.split(':')
    pace_seconds = int(parts[0]) * 60 + int(parts[1])

    # Calculate adjustment
    adjustment = calculate_environmental_adjustment(
        pace_seconds_per_mile=pace_seconds,
        temp_f=args.temp,
        humidity=args.humidity,
        distance_miles=args.distance,
        elevation_gain_feet=args.elevation,
        altitude_feet=args.altitude,
        baseline_altitude_feet=args.baseline_altitude
    )

    # Print summary
    print(format_adjustment_summary(adjustment))
