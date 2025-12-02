#!/usr/bin/env python3
"""
Planned Workout Manager

Manages the athlete's planned workout schedule extracted from baseline training plans.
Provides CRUD operations for planned workouts and tracks completion status.
"""

import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pathlib import Path
import uuid


class PlannedWorkoutManager:
    """Manager for planned workout schedule"""

    def __init__(self, data_file: Optional[str] = None):
        """Initialize manager with data file path"""
        if data_file is None:
            # Default to data/plans/planned_workouts.json
            base_dir = Path(__file__).parent.parent
            data_file = base_dir / "data" / "plans" / "planned_workouts.json"

        self.data_file = Path(data_file)
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load planned workouts from JSON file"""
        if not self.data_file.exists():
            # Initialize with empty structure
            return {
                "metadata": {
                    "plan_name": "",
                    "plan_id": "",
                    "race_date": None,
                    "plan_start_date": None,
                    "plan_end_date": None,
                    "created_date": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat(),
                    "athlete": "",
                    "version": "1.0"
                },
                "planned_workouts": []
            }

        with open(self.data_file, 'r') as f:
            return json.load(f)

    def _save_data(self):
        """Save planned workouts to JSON file (atomic write)"""
        # Ensure directory exists
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

        # Update last modified timestamp
        self.data["metadata"]["last_modified"] = datetime.now().isoformat()

        # Atomic write: write to temp file, then rename
        temp_file = self.data_file.with_suffix('.json.tmp')
        with open(temp_file, 'w') as f:
            json.dump(self.data, f, indent=2)

        temp_file.rename(self.data_file)

    def set_plan_metadata(self, **kwargs):
        """Update plan metadata fields"""
        for key, value in kwargs.items():
            if key in self.data["metadata"]:
                self.data["metadata"][key] = value
        self._save_data()

    def add_workout(self, workout_data: Dict[str, Any]) -> str:
        """
        Add a new planned workout

        Args:
            workout_data: Dictionary containing workout details
                Required: date, domain, workout (with type, description)
                Optional: week_number, phase, status, actual_performance, adjustments

        Returns:
            Workout ID
        """
        # Generate unique ID if not provided
        workout_id = workout_data.get('id', str(uuid.uuid4()))

        # Default values
        workout = {
            "id": workout_id,
            "date": workout_data["date"],
            "week_number": workout_data.get("week_number"),
            "phase": workout_data.get("phase"),
            "domain": workout_data["domain"],
            "workout": workout_data["workout"],
            "status": workout_data.get("status", "planned"),
            "actual_performance": workout_data.get("actual_performance"),
            "adjustments": workout_data.get("adjustments", [])
        }

        self.data["planned_workouts"].append(workout)
        self._save_data()
        return workout_id

    def get_workout(self, workout_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific workout by ID"""
        for workout in self.data["planned_workouts"]:
            if workout["id"] == workout_id:
                return workout
        return None

    def get_workouts_by_date(self, target_date: str) -> List[Dict[str, Any]]:
        """Get all workouts for a specific date (YYYY-MM-DD)"""
        return [w for w in self.data["planned_workouts"] if w["date"] == target_date]

    def get_workouts_by_date_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get all workouts within a date range (inclusive)"""
        return [
            w for w in self.data["planned_workouts"]
            if start_date <= w["date"] <= end_date
        ]

    def get_workouts_by_week(self, week_number: int) -> List[Dict[str, Any]]:
        """Get all workouts for a specific week number"""
        return [w for w in self.data["planned_workouts"] if w.get("week_number") == week_number]

    def get_workouts_by_phase(self, phase: str) -> List[Dict[str, Any]]:
        """Get all workouts for a specific training phase"""
        return [w for w in self.data["planned_workouts"] if w.get("phase") == phase]

    def get_workouts_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all workouts for a specific domain (running, strength, mobility, nutrition)"""
        return [w for w in self.data["planned_workouts"] if w["domain"] == domain]

    def get_workouts_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all workouts with specific status (planned, completed, skipped, modified)"""
        return [w for w in self.data["planned_workouts"] if w["status"] == status]

    def get_today_workouts(self) -> List[Dict[str, Any]]:
        """Get all workouts scheduled for today"""
        today = date.today().isoformat()
        return self.get_workouts_by_date(today)

    def get_upcoming_workouts(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get workouts scheduled in the next N days"""
        from datetime import timedelta
        today = date.today()
        end_date = (today + timedelta(days=days)).isoformat()
        return self.get_workouts_by_date_range(today.isoformat(), end_date)

    def update_workout(self, workout_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a workout's fields

        Args:
            workout_id: ID of workout to update
            updates: Dictionary of fields to update

        Returns:
            True if workout was found and updated, False otherwise
        """
        for workout in self.data["planned_workouts"]:
            if workout["id"] == workout_id:
                # Update fields
                for key, value in updates.items():
                    if key != "id":  # Don't allow ID changes
                        workout[key] = value
                self._save_data()
                return True
        return False

    def mark_completed(self, workout_id: str, actual_performance: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a workout as completed

        Args:
            workout_id: ID of workout to mark complete
            actual_performance: Optional dict with actual workout data
                (garmin_activity_id, date_completed, duration_minutes, distance_miles,
                 avg_pace, avg_hr, notes)

        Returns:
            True if successful, False if workout not found
        """
        updates = {"status": "completed"}
        if actual_performance:
            updates["actual_performance"] = actual_performance
        return self.update_workout(workout_id, updates)

    def mark_skipped(self, workout_id: str, reason: Optional[str] = None) -> bool:
        """Mark a workout as skipped with optional reason"""
        workout = self.get_workout(workout_id)
        if not workout:
            return False

        updates = {"status": "skipped"}

        if reason:
            adjustment = {
                "date": date.today().isoformat(),
                "reason": reason,
                "change": "Workout skipped",
                "modified_by": "athlete"
            }
            adjustments = workout.get("adjustments", [])
            adjustments.append(adjustment)
            updates["adjustments"] = adjustments

        return self.update_workout(workout_id, updates)

    def add_adjustment(self, workout_id: str, reason: str, change: str,
                       modified_by: str = "coach") -> bool:
        """
        Add an adjustment note to a workout

        Args:
            workout_id: ID of workout to adjust
            reason: Reason for adjustment
            change: Description of what changed
            modified_by: Who made the adjustment (default: "coach")

        Returns:
            True if successful, False if workout not found
        """
        workout = self.get_workout(workout_id)
        if not workout:
            return False

        adjustment = {
            "date": date.today().isoformat(),
            "reason": reason,
            "change": change,
            "modified_by": modified_by
        }

        adjustments = workout.get("adjustments", [])
        adjustments.append(adjustment)

        return self.update_workout(workout_id, {"adjustments": adjustments, "status": "modified"})

    def delete_workout(self, workout_id: str) -> bool:
        """Delete a workout by ID"""
        original_length = len(self.data["planned_workouts"])
        self.data["planned_workouts"] = [
            w for w in self.data["planned_workouts"] if w["id"] != workout_id
        ]

        if len(self.data["planned_workouts"]) < original_length:
            self._save_data()
            return True
        return False

    def get_all_workouts(self) -> List[Dict[str, Any]]:
        """Get all planned workouts"""
        return self.data["planned_workouts"]

    def get_week_summary(self, week_number: int) -> Dict[str, Any]:
        """Get summary statistics for a specific week"""
        workouts = self.get_workouts_by_week(week_number)

        total_workouts = len(workouts)
        completed = len([w for w in workouts if w["status"] == "completed"])
        skipped = len([w for w in workouts if w["status"] == "skipped"])
        planned = len([w for w in workouts if w["status"] == "planned"])
        modified = len([w for w in workouts if w["status"] == "modified"])

        by_domain = {}
        for workout in workouts:
            domain = workout["domain"]
            by_domain[domain] = by_domain.get(domain, 0) + 1

        return {
            "week_number": week_number,
            "total_workouts": total_workouts,
            "completed": completed,
            "skipped": skipped,
            "planned": planned,
            "modified": modified,
            "completion_rate": completed / total_workouts if total_workouts > 0 else 0,
            "by_domain": by_domain,
            "workouts": workouts
        }

    def get_plan_summary(self) -> Dict[str, Any]:
        """Get overall plan statistics"""
        all_workouts = self.data["planned_workouts"]

        total = len(all_workouts)
        completed = len([w for w in all_workouts if w["status"] == "completed"])
        skipped = len([w for w in all_workouts if w["status"] == "skipped"])
        planned = len([w for w in all_workouts if w["status"] == "planned"])
        modified = len([w for w in all_workouts if w["status"] == "modified"])

        by_domain = {}
        by_phase = {}

        for workout in all_workouts:
            domain = workout["domain"]
            by_domain[domain] = by_domain.get(domain, 0) + 1

            phase = workout.get("phase")
            if phase:
                by_phase[phase] = by_phase.get(phase, 0) + 1

        return {
            "metadata": self.data["metadata"],
            "total_workouts": total,
            "completed": completed,
            "skipped": skipped,
            "planned": planned,
            "modified": modified,
            "completion_rate": completed / total if total > 0 else 0,
            "by_domain": by_domain,
            "by_phase": by_phase
        }

    def clear_all_workouts(self):
        """Remove all planned workouts (keeps metadata)"""
        self.data["planned_workouts"] = []
        self._save_data()

    def export_to_json(self, output_file: str):
        """Export planned workouts to a JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def import_from_json(self, input_file: str, merge: bool = False):
        """
        Import planned workouts from a JSON file

        Args:
            input_file: Path to JSON file to import
            merge: If True, merge with existing workouts. If False, replace all.
        """
        with open(input_file, 'r') as f:
            imported_data = json.load(f)

        if merge:
            # Merge workouts, avoiding duplicates by ID
            existing_ids = {w["id"] for w in self.data["planned_workouts"]}
            for workout in imported_data.get("planned_workouts", []):
                if workout["id"] not in existing_ids:
                    self.data["planned_workouts"].append(workout)
        else:
            # Replace all
            self.data = imported_data

        self._save_data()


if __name__ == "__main__":
    # Basic testing
    manager = PlannedWorkoutManager()
    print(f"Data file: {manager.data_file}")
    print(f"Total workouts: {len(manager.get_all_workouts())}")
    print(f"Today's workouts: {len(manager.get_today_workouts())}")
