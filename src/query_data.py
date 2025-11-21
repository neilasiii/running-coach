#!/usr/bin/env python3
"""
Query helper script for coaching agents to access database.
Returns JSON output for easy parsing.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any

from database.connection import get_session
from database.models import (
    Activity, SleepSession, RestingHRReading, VO2MaxReading,
    AthleteProfile, TrainingStatus, CommunicationPreference,
    Race, AthleteDocument, Workout
)


def serialize_datetime(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def get_recent_activities(limit: int = 10, activity_type: str = None) -> List[Dict]:
    """Get recent activities from database."""
    with get_session() as session:
        query = session.query(Activity).order_by(Activity.start_time.desc())

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type.upper())

        activities = query.limit(limit).all()

        return [{
            'id': str(a.id),
            'activity_type': a.activity_type,
            'start_time': a.start_time,
            'distance_km': float(a.distance_km) if a.distance_km else None,
            'duration_minutes': a.duration_minutes,
            'avg_pace_per_km': a.avg_pace_per_km,
            'avg_heart_rate': a.avg_heart_rate,
            'max_heart_rate': a.max_heart_rate,
            'calories': a.calories,
        } for a in activities]


def get_recent_sleep(days: int = 7) -> List[Dict]:
    """Get recent sleep sessions."""
    with get_session() as session:
        cutoff = datetime.utcnow() - timedelta(days=days)
        sessions = session.query(SleepSession)\
            .filter(SleepSession.sleep_date >= cutoff.date())\
            .order_by(SleepSession.sleep_date.desc())\
            .all()

        return [{
            'sleep_date': s.sleep_date.isoformat(),
            'total_duration_minutes': s.total_duration_minutes,
            'deep_sleep_minutes': s.deep_sleep_minutes,
            'light_sleep_minutes': s.light_sleep_minutes,
            'rem_sleep_minutes': s.rem_sleep_minutes,
            'awake_minutes': s.awake_minutes,
            'sleep_score': s.sleep_score,
        } for s in sessions]


def get_resting_hr(days: int = 14) -> List[Dict]:
    """Get recent resting heart rate readings."""
    with get_session() as session:
        cutoff = datetime.utcnow() - timedelta(days=days)
        readings = session.query(RestingHRReading)\
            .filter(RestingHRReading.reading_date >= cutoff.date())\
            .order_by(RestingHRReading.reading_date.desc())\
            .all()

        return [{
            'reading_date': r.reading_date.isoformat(),
            'resting_hr': r.resting_hr,
        } for r in readings]


def get_training_status() -> Dict:
    """Get current training status."""
    with get_session() as session:
        status = session.query(TrainingStatus)\
            .filter(TrainingStatus.valid_until.is_(None))\
            .first()

        if not status:
            return {}

        return {
            'vdot_prescribed': status.vdot_prescribed,
            'vdot_current': status.vdot_current,
            'current_phase': status.current_phase,
            'weekly_volume_hours': float(status.weekly_volume_hours) if status.weekly_volume_hours else None,
            'weekly_run_count': status.weekly_run_count,
            'easy_pace': status.easy_pace,
            'marathon_pace': status.marathon_pace,
            'threshold_pace': status.threshold_pace,
            'interval_pace': status.interval_pace,
            'repetition_pace': status.repetition_pace,
        }


def get_communication_prefs() -> Dict:
    """Get communication preferences."""
    with get_session() as session:
        prefs = session.query(CommunicationPreference).first()

        if not prefs:
            return {'detail_level': 'BRIEF'}  # Default

        return {
            'detail_level': prefs.detail_level,
            'include_paces': prefs.include_paces,
            'show_weekly_mileage': prefs.show_weekly_mileage,
            'include_heart_rate_targets': prefs.include_heart_rate_targets,
        }


def get_upcoming_races(limit: int = 5) -> List[Dict]:
    """Get upcoming races."""
    with get_session() as session:
        today = datetime.utcnow().date()
        races = session.query(Race)\
            .filter(Race.date >= today)\
            .order_by(Race.date)\
            .limit(limit)\
            .all()

        return [{
            'id': str(r.id),
            'name': r.name,
            'date': r.date.isoformat(),
            'distance': r.distance,
            'priority': r.priority,
            'goal_time_a': r.goal_time_a,
            'goal_time_b': r.goal_time_b,
            'goal_time_c': r.goal_time_c,
        } for r in races]


def get_athlete_profile() -> Dict:
    """Get athlete profile."""
    with get_session() as session:
        profile = session.query(AthleteProfile)\
            .filter(AthleteProfile.is_active == True)\
            .first()

        if not profile:
            return {}

        return {
            'id': str(profile.id),
            'name': profile.name,
            'email': profile.email,
        }


def search_workouts(domain: str = None, workout_type: str = None, limit: int = 10) -> List[Dict]:
    """Search workout library."""
    with get_session() as session:
        query = session.query(Workout)

        if domain:
            query = query.filter(Workout.domain == domain)
        if workout_type:
            query = query.filter(Workout.workout_type == workout_type)

        workouts = query.limit(limit).all()

        return [{
            'id': str(w.id),
            'name': w.name,
            'domain': w.domain,
            'workout_type': w.workout_type,
            'difficulty': w.difficulty,
            'duration_minutes': w.duration_minutes,
            'description': w.description,
        } for w in workouts]


def main():
    parser = argparse.ArgumentParser(description='Query coaching data from database')
    parser.add_argument('query', choices=[
        'recent-activities', 'recent-runs', 'recent-sleep', 'resting-hr',
        'training-status', 'communication-prefs', 'upcoming-races',
        'athlete-profile', 'search-workouts'
    ])
    parser.add_argument('--limit', type=int, default=10, help='Limit results')
    parser.add_argument('--days', type=int, default=7, help='Number of days (for time-based queries)')
    parser.add_argument('--domain', help='Workout domain (for search)')
    parser.add_argument('--type', help='Workout type (for search)')

    args = parser.parse_args()

    try:
        result = None

        if args.query == 'recent-activities':
            result = get_recent_activities(limit=args.limit)
        elif args.query == 'recent-runs':
            result = get_recent_activities(limit=args.limit, activity_type='RUNNING')
        elif args.query == 'recent-sleep':
            result = get_recent_sleep(days=args.days)
        elif args.query == 'resting-hr':
            result = get_resting_hr(days=args.days)
        elif args.query == 'training-status':
            result = get_training_status()
        elif args.query == 'communication-prefs':
            result = get_communication_prefs()
        elif args.query == 'upcoming-races':
            result = get_upcoming_races(limit=args.limit)
        elif args.query == 'athlete-profile':
            result = get_athlete_profile()
        elif args.query == 'search-workouts':
            result = search_workouts(domain=args.domain, workout_type=args.type, limit=args.limit)

        # Output as JSON
        print(json.dumps(result, default=serialize_datetime, indent=2))
        return 0

    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
