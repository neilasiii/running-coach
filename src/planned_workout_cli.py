#!/usr/bin/env python3
"""
Planned Workout CLI

Command-line interface for managing planned workouts.
"""

import argparse
import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from planned_workout_manager import PlannedWorkoutManager


def format_workout_display(workout: dict, verbose: bool = False) -> str:
    """Format a workout for display"""
    status_emoji = {
        "planned": "📅",
        "completed": "✅",
        "skipped": "⏭️",
        "modified": "✏️"
    }

    emoji = status_emoji.get(workout["status"], "❓")
    workout_info = workout["workout"]

    # Basic info
    lines = [
        f"{emoji} {workout['date']} - {workout['domain'].upper()}: {workout_info.get('type', 'N/A')}"
    ]

    if verbose:
        lines.append(f"  ID: {workout['id']}")
        if workout.get('week_number'):
            lines.append(f"  Week: {workout['week_number']}, Phase: {workout.get('phase', 'N/A')}")

        lines.append(f"  Description: {workout_info.get('description', 'N/A')}")

        if workout_info.get('duration_minutes'):
            lines.append(f"  Duration: {workout_info['duration_minutes']} min")

        if workout_info.get('pace_target'):
            lines.append(f"  Pace: {workout_info['pace_target']}")

        if workout_info.get('hr_target'):
            lines.append(f"  HR Target: {workout_info['hr_target']}")

        # Show actual performance if completed
        if workout["status"] == "completed" and workout.get("actual_performance"):
            perf = workout["actual_performance"]
            lines.append(f"  ✓ Completed: {perf.get('date_completed', 'N/A')}")
            if perf.get('duration_minutes'):
                lines.append(f"    Duration: {perf['duration_minutes']} min")
            if perf.get('distance_miles'):
                lines.append(f"    Distance: {perf['distance_miles']:.2f} mi")
            if perf.get('avg_pace'):
                lines.append(f"    Avg Pace: {perf['avg_pace']}")
            if perf.get('avg_hr'):
                lines.append(f"    Avg HR: {perf['avg_hr']} bpm")
            if perf.get('notes'):
                lines.append(f"    Notes: {perf['notes']}")

        # Show adjustments
        if workout.get("adjustments"):
            lines.append(f"  Adjustments ({len(workout['adjustments'])}):")
            for adj in workout["adjustments"]:
                lines.append(f"    • {adj['date']}: {adj['change']} ({adj['reason']})")

    return "\n".join(lines)


def cmd_list(args):
    """List workouts"""
    manager = PlannedWorkoutManager(args.data_file)

    # Filter by criteria
    if args.today:
        workouts = manager.get_today_workouts()
        print(f"Today's Workouts ({date.today().isoformat()}):")
    elif args.upcoming:
        workouts = manager.get_upcoming_workouts(args.upcoming)
        end_date = (date.today() + timedelta(days=args.upcoming)).isoformat()
        print(f"Upcoming Workouts (Next {args.upcoming} days):")
    elif args.week:
        workouts = manager.get_workouts_by_week(args.week)
        print(f"Week {args.week} Workouts:")
    elif args.phase:
        workouts = manager.get_workouts_by_phase(args.phase)
        print(f"Phase: {args.phase}")
    elif args.domain:
        workouts = manager.get_workouts_by_domain(args.domain)
        print(f"Domain: {args.domain}")
    elif args.status:
        workouts = manager.get_workouts_by_status(args.status)
        print(f"Status: {args.status}")
    elif args.date:
        workouts = manager.get_workouts_by_date(args.date)
        print(f"Workouts on {args.date}:")
    else:
        workouts = manager.get_all_workouts()
        print("All Planned Workouts:")

    if not workouts:
        print("No workouts found.")
        return

    print(f"Found {len(workouts)} workout(s)\n")

    for workout in workouts:
        print(format_workout_display(workout, verbose=args.verbose))
        print()


def cmd_get(args):
    """Get a specific workout by ID"""
    manager = PlannedWorkoutManager(args.data_file)
    workout = manager.get_workout(args.workout_id)

    if not workout:
        print(f"Workout not found: {args.workout_id}", file=sys.stderr)
        sys.exit(1)

    print(format_workout_display(workout, verbose=True))


def cmd_add(args):
    """Add a new workout"""
    manager = PlannedWorkoutManager(args.data_file)

    # Build workout data from args
    workout_data = {
        "date": args.date,
        "domain": args.domain,
        "workout": {
            "type": args.type,
            "description": args.description,
        }
    }

    if args.week:
        workout_data["week_number"] = args.week

    if args.phase:
        workout_data["phase"] = args.phase

    if args.duration:
        workout_data["workout"]["duration_minutes"] = args.duration

    if args.pace:
        workout_data["workout"]["pace_target"] = args.pace

    if args.hr:
        workout_data["workout"]["hr_target"] = args.hr

    workout_id = manager.add_workout(workout_data)
    print(f"✓ Workout added: {workout_id}")


def cmd_complete(args):
    """Mark workout as completed"""
    manager = PlannedWorkoutManager(args.data_file)

    actual_perf = None
    if args.garmin_id or args.duration or args.distance or args.pace or args.hr or args.notes:
        actual_perf = {
            "date_completed": date.today().isoformat()
        }
        if args.garmin_id:
            actual_perf["garmin_activity_id"] = args.garmin_id
        if args.duration:
            actual_perf["duration_minutes"] = args.duration
        if args.distance:
            actual_perf["distance_miles"] = args.distance
        if args.pace:
            actual_perf["avg_pace"] = args.pace
        if args.hr:
            actual_perf["avg_hr"] = args.hr
        if args.notes:
            actual_perf["notes"] = args.notes

    if manager.mark_completed(args.workout_id, actual_perf):
        print(f"✓ Workout marked as completed: {args.workout_id}")
    else:
        print(f"Workout not found: {args.workout_id}", file=sys.stderr)
        sys.exit(1)


def cmd_skip(args):
    """Mark workout as skipped"""
    manager = PlannedWorkoutManager(args.data_file)

    if manager.mark_skipped(args.workout_id, args.reason):
        print(f"✓ Workout marked as skipped: {args.workout_id}")
    else:
        print(f"Workout not found: {args.workout_id}", file=sys.stderr)
        sys.exit(1)


def cmd_adjust(args):
    """Add adjustment to workout"""
    manager = PlannedWorkoutManager(args.data_file)

    if manager.add_adjustment(args.workout_id, args.reason, args.change, args.modified_by):
        print(f"✓ Adjustment added to workout: {args.workout_id}")
    else:
        print(f"Workout not found: {args.workout_id}", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args):
    """Delete a workout"""
    manager = PlannedWorkoutManager(args.data_file)

    if manager.delete_workout(args.workout_id):
        print(f"✓ Workout deleted: {args.workout_id}")
    else:
        print(f"Workout not found: {args.workout_id}", file=sys.stderr)
        sys.exit(1)


def cmd_summary(args):
    """Show plan summary"""
    manager = PlannedWorkoutManager(args.data_file)

    if args.week:
        summary = manager.get_week_summary(args.week)
        print(f"Week {args.week} Summary:")
        print(f"  Total Workouts: {summary['total_workouts']}")
        print(f"  Completed: {summary['completed']}")
        print(f"  Skipped: {summary['skipped']}")
        print(f"  Planned: {summary['planned']}")
        print(f"  Modified: {summary['modified']}")
        print(f"  Completion Rate: {summary['completion_rate']:.1%}")
        print(f"\nBy Domain:")
        for domain, count in summary['by_domain'].items():
            print(f"  {domain}: {count}")
    else:
        summary = manager.get_plan_summary()
        metadata = summary['metadata']
        print(f"Plan: {metadata['plan_name']}")
        print(f"Race Date: {metadata['race_date']}")
        print(f"Duration: {metadata['plan_start_date']} to {metadata['plan_end_date']}")
        print(f"\nTotal Workouts: {summary['total_workouts']}")
        print(f"Completed: {summary['completed']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Planned: {summary['planned']}")
        print(f"Modified: {summary['modified']}")
        print(f"Completion Rate: {summary['completion_rate']:.1%}")
        print(f"\nBy Domain:")
        for domain, count in summary['by_domain'].items():
            print(f"  {domain}: {count}")
        if summary['by_phase']:
            print(f"\nBy Phase:")
            for phase, count in summary['by_phase'].items():
                print(f"  {phase}: {count}")


def cmd_export(args):
    """Export workouts to JSON"""
    manager = PlannedWorkoutManager(args.data_file)
    manager.export_to_json(args.output)
    print(f"✓ Workouts exported to: {args.output}")


def cmd_import(args):
    """Import workouts from JSON"""
    manager = PlannedWorkoutManager(args.data_file)
    manager.import_from_json(args.input, merge=args.merge)
    print(f"✓ Workouts imported from: {args.input}")


def main():
    parser = argparse.ArgumentParser(description="Manage planned workouts")
    parser.add_argument(
        '--data-file',
        help='Path to planned workouts data file (default: data/plans/planned_workouts.json)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List workouts')
    list_parser.add_argument('--today', action='store_true', help='Show only today\'s workouts')
    list_parser.add_argument('--upcoming', type=int, metavar='DAYS', help='Show workouts in next N days')
    list_parser.add_argument('--week', type=int, help='Filter by week number')
    list_parser.add_argument('--phase', help='Filter by training phase')
    list_parser.add_argument('--domain', help='Filter by domain (running, strength, mobility, nutrition)')
    list_parser.add_argument('--status', help='Filter by status (planned, completed, skipped, modified)')
    list_parser.add_argument('--date', help='Filter by specific date (YYYY-MM-DD)')
    list_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed information')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get a specific workout')
    get_parser.add_argument('workout_id', help='Workout ID')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new workout')
    add_parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    add_parser.add_argument('--domain', required=True, help='Domain (running, strength, mobility, nutrition)')
    add_parser.add_argument('--type', required=True, help='Workout type')
    add_parser.add_argument('--description', required=True, help='Workout description')
    add_parser.add_argument('--week', type=int, help='Week number')
    add_parser.add_argument('--phase', help='Training phase')
    add_parser.add_argument('--duration', type=int, help='Duration in minutes')
    add_parser.add_argument('--pace', help='Pace target')
    add_parser.add_argument('--hr', help='HR target')

    # Complete command
    complete_parser = subparsers.add_parser('complete', help='Mark workout as completed')
    complete_parser.add_argument('workout_id', help='Workout ID')
    complete_parser.add_argument('--garmin-id', type=int, help='Garmin activity ID')
    complete_parser.add_argument('--duration', type=int, help='Actual duration (minutes)')
    complete_parser.add_argument('--distance', type=float, help='Actual distance (miles)')
    complete_parser.add_argument('--pace', help='Actual avg pace')
    complete_parser.add_argument('--hr', type=int, help='Actual avg HR')
    complete_parser.add_argument('--notes', help='Notes about the workout')

    # Skip command
    skip_parser = subparsers.add_parser('skip', help='Mark workout as skipped')
    skip_parser.add_argument('workout_id', help='Workout ID')
    skip_parser.add_argument('--reason', help='Reason for skipping')

    # Adjust command
    adjust_parser = subparsers.add_parser('adjust', help='Add adjustment to workout')
    adjust_parser.add_argument('workout_id', help='Workout ID')
    adjust_parser.add_argument('--reason', required=True, help='Reason for adjustment')
    adjust_parser.add_argument('--change', required=True, help='Description of change')
    adjust_parser.add_argument('--modified-by', default='coach', help='Who made the adjustment')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a workout')
    delete_parser.add_argument('workout_id', help='Workout ID')

    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show plan or week summary')
    summary_parser.add_argument('--week', type=int, help='Show summary for specific week')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export workouts to JSON')
    export_parser.add_argument('output', help='Output file path')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import workouts from JSON')
    import_parser.add_argument('input', help='Input file path')
    import_parser.add_argument('--merge', action='store_true', help='Merge with existing workouts')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    command_map = {
        'list': cmd_list,
        'get': cmd_get,
        'add': cmd_add,
        'complete': cmd_complete,
        'skip': cmd_skip,
        'adjust': cmd_adjust,
        'delete': cmd_delete,
        'summary': cmd_summary,
        'export': cmd_export,
        'import': cmd_import
    }

    command_map[args.command](args)


if __name__ == "__main__":
    main()
