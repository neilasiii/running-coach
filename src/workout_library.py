#!/usr/bin/env python3
"""
Workout Library Manager

Provides CRUD operations and search functionality for the workout library.
Supports workouts across all coaching domains: running, strength, mobility, nutrition.

Now uses PostgreSQL database as primary storage with optional JSON export/import for backward compatibility.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from database.connection import get_session
    from database.models import Workout
    DATABASE_AVAILABLE = True
except ImportError:
    # Fall back to JSON if database not available
    DATABASE_AVAILABLE = False
    get_session = None
    Workout = None


class WorkoutLibrary:
    """Main interface for workout library operations - uses database as primary storage"""

    def __init__(self, library_path: str = None):
        """
        Initialize workout library

        Args:
            library_path: Path to workout_library.json (used only for legacy import/export)
        """
        if library_path is None:
            # Default to data/library/workout_library.json (for legacy operations)
            script_dir = Path(__file__).parent
            repo_root = script_dir.parent
            library_path = repo_root / "data" / "library" / "workout_library.json"

        self.library_path = Path(library_path)
        self.library_dir = self.library_path.parent

        # Ensure library directory exists (for export)
        self.library_dir.mkdir(parents=True, exist_ok=True)

        # Check if database is available
        if not DATABASE_AVAILABLE:
            print("Warning: Database not available. Using JSON file for storage (legacy mode).")
            # Load from JSON if database not available
            self.workouts = self._load_library_json()
        else:
            # Use database - no need to load everything into memory
            self.workouts = None

    def _load_library_json(self) -> Dict[str, Dict]:
        """Load workout library from JSON file (legacy fallback)"""
        if not self.library_path.exists():
            # Initialize empty library
            return {
                "metadata": {
                    "created_date": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat(),
                    "version": "1.0"
                },
                "workouts": {},
                "blocks": {}
            }

        try:
            with open(self.library_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error loading library: {e}")
            print("Initializing new library")
            return {
                "metadata": {
                    "created_date": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat(),
                    "version": "1.0"
                },
                "workouts": {},
                "blocks": {}
            }

    def _save_library_json(self):
        """Save workout library to JSON file (legacy fallback)"""
        if self.workouts is None:
            return  # Database mode, no JSON to save

        # Update last modified timestamp
        self.workouts["metadata"]["last_modified"] = datetime.now().isoformat()

        # Write to temp file first, then rename (atomic operation)
        temp_path = self.library_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(self.workouts, f, indent=2)
            temp_path.replace(self.library_path)
        except Exception as e:
            print(f"Error saving library: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

    def add_workout(self, workout: Dict[str, Any]) -> str:
        """
        Add a new workout to the library

        Args:
            workout: Workout dictionary (must include name, domain, type, content)

        Returns:
            Workout ID
        """
        # Validate required fields
        required_fields = ["name", "domain", "type", "content"]
        for field in required_fields:
            if field not in workout:
                raise ValueError(f"Missing required field: {field}")

        # Validate domain
        valid_domains = ["running", "strength", "mobility", "nutrition", "multi_domain"]
        if workout["domain"] not in valid_domains:
            raise ValueError(f"Invalid domain: {workout['domain']}. Must be one of {valid_domains}")

        # Generate ID if not provided
        if "id" not in workout:
            workout_id = str(uuid.uuid4())
        else:
            workout_id = workout["id"]

        if DATABASE_AVAILABLE:
            # Save to database
            with get_session() as session:
                db_workout = Workout(
                    id=workout_id,
                    name=workout["name"],
                    domain=workout["domain"],
                    workout_type=workout["type"],
                    description=workout.get("description", ""),
                    content=workout["content"],
                    difficulty=workout.get("difficulty"),
                    duration_minutes=workout.get("duration_minutes"),
                    equipment=workout.get("equipment", []),
                    tags=workout.get("tags", []),
                    vdot_min=workout.get("vdot_min"),
                    vdot_max=workout.get("vdot_max"),
                )
                session.add(db_workout)
                session.commit()
            return workout_id
        else:
            # Legacy JSON mode
            now = datetime.now().isoformat()
            workout["created_date"] = now
            workout["modified_date"] = now
            workout["id"] = workout_id

            # Set defaults
            if "tags" not in workout:
                workout["tags"] = []
            if "equipment" not in workout:
                workout["equipment"] = []

            # Add to library
            self.workouts["workouts"][workout_id] = workout
            self._save_library_json()
            return workout_id

    def get_workout(self, workout_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a workout by ID

        Args:
            workout_id: Workout ID

        Returns:
            Workout dictionary or None if not found
        """
        if DATABASE_AVAILABLE:
            with get_session() as session:
                workout = session.query(Workout).filter(Workout.id == workout_id).first()
                if workout:
                    return workout.to_dict()
                return None
        else:
            # Legacy JSON mode
            return self.workouts["workouts"].get(workout_id)

    def update_workout(self, workout_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing workout

        Args:
            workout_id: Workout ID
            updates: Dictionary of fields to update

        Returns:
            True if successful, False if workout not found
        """
        if DATABASE_AVAILABLE:
            with get_session() as session:
                workout = session.query(Workout).filter(Workout.id == workout_id).first()
                if not workout:
                    return False

                # Update allowed fields
                if "name" in updates:
                    workout.name = updates["name"]
                if "description" in updates:
                    workout.description = updates["description"]
                if "content" in updates:
                    workout.content = updates["content"]
                if "difficulty" in updates:
                    workout.difficulty = updates["difficulty"]
                if "duration_minutes" in updates:
                    workout.duration_minutes = updates["duration_minutes"]
                if "equipment" in updates:
                    workout.equipment = updates["equipment"]
                if "tags" in updates:
                    workout.tags = updates["tags"]
                if "vdot_min" in updates:
                    workout.vdot_min = updates["vdot_min"]
                if "vdot_max" in updates:
                    workout.vdot_max = updates["vdot_max"]

                workout.updated_at = datetime.utcnow()
                session.commit()
                return True
        else:
            # Legacy JSON mode
            if workout_id not in self.workouts["workouts"]:
                return False

            workout = self.workouts["workouts"][workout_id]
            workout.update(updates)
            workout["modified_date"] = datetime.now().isoformat()
            self._save_library_json()
            return True

    def delete_workout(self, workout_id: str) -> bool:
        """
        Delete a workout from the library

        Args:
            workout_id: Workout ID

        Returns:
            True if successful, False if workout not found
        """
        if DATABASE_AVAILABLE:
            with get_session() as session:
                workout = session.query(Workout).filter(Workout.id == workout_id).first()
                if not workout:
                    return False
                session.delete(workout)
                session.commit()
                return True
        else:
            # Legacy JSON mode
            if workout_id not in self.workouts["workouts"]:
                return False
            del self.workouts["workouts"][workout_id]
            self._save_library_json()
            return True

    def search(self,
               domain: Optional[str] = None,
               workout_type: Optional[str] = None,
               difficulty: Optional[str] = None,
               tags: Optional[List[str]] = None,
               equipment: Optional[List[str]] = None,
               duration_min: Optional[int] = None,
               duration_max: Optional[int] = None,
               vdot_min: Optional[int] = None,
               vdot_max: Optional[int] = None,
               keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search workouts with filters

        Args:
            domain: Filter by domain (running, strength, mobility, nutrition)
            workout_type: Filter by workout type (tempo, intervals, etc.)
            difficulty: Filter by difficulty level
            tags: List of tags to match (workout must have all tags)
            equipment: List of equipment (workout must have all equipment)
            duration_min: Minimum duration in minutes
            duration_max: Maximum duration in minutes
            vdot_min: Minimum VDOT level
            vdot_max: Maximum VDOT level
            keyword: Search in name and description

        Returns:
            List of matching workouts
        """
        if DATABASE_AVAILABLE:
            with get_session() as session:
                query = session.query(Workout)

                # Apply filters
                if domain:
                    query = query.filter(Workout.domain == domain)
                if workout_type:
                    query = query.filter(Workout.workout_type == workout_type)
                if difficulty:
                    query = query.filter(Workout.difficulty == difficulty)
                if duration_min is not None:
                    query = query.filter(Workout.duration_minutes >= duration_min)
                if duration_max is not None:
                    query = query.filter(Workout.duration_minutes <= duration_max)
                if vdot_min is not None:
                    query = query.filter(Workout.vdot_min >= vdot_min)
                if vdot_max is not None:
                    query = query.filter(Workout.vdot_max <= vdot_max)
                if keyword:
                    keyword_filter = f"%{keyword}%"
                    query = query.filter(
                        (Workout.name.ilike(keyword_filter)) |
                        (Workout.description.ilike(keyword_filter))
                    )

                # Note: tags and equipment filtering requires array operations
                # PostgreSQL specific - checking if all required elements are present
                if tags:
                    for tag in tags:
                        query = query.filter(Workout.tags.contains([tag]))
                if equipment:
                    for item in equipment:
                        query = query.filter(Workout.equipment.contains([item]))

                workouts = query.all()
                return [w.to_dict() for w in workouts]
        else:
            # Legacy JSON mode
            results = []
            for workout_id, workout in self.workouts["workouts"].items():
                # Apply filters
                if domain and workout.get("domain") != domain:
                    continue
                if workout_type and workout.get("type") != workout_type:
                    continue
                if difficulty and workout.get("difficulty") != difficulty:
                    continue
                if duration_min and workout.get("duration_minutes", 0) < duration_min:
                    continue
                if duration_max and workout.get("duration_minutes", float('inf')) > duration_max:
                    continue
                if vdot_min and workout.get("vdot_min", 0) < vdot_min:
                    continue
                if vdot_max and workout.get("vdot_max", float('inf')) > vdot_max:
                    continue
                if keyword:
                    keyword_lower = keyword.lower()
                    name_match = keyword_lower in workout.get("name", "").lower()
                    desc_match = keyword_lower in workout.get("description", "").lower()
                    if not (name_match or desc_match):
                        continue
                if tags and not all(tag in workout.get("tags", []) for tag in tags):
                    continue
                if equipment and not all(item in workout.get("equipment", []) for item in equipment):
                    continue

                results.append(workout)

            return results

    def list_all_workouts(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all workouts, optionally filtered by domain

        Args:
            domain: Optional domain filter

        Returns:
            List of workouts
        """
        return self.search(domain=domain)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get library statistics

        Returns:
            Dictionary with statistics
        """
        if DATABASE_AVAILABLE:
            with get_session() as session:
                total_workouts = session.query(Workout).count()

                # Count by domain
                from sqlalchemy import func
                domain_counts = dict(
                    session.query(Workout.domain, func.count(Workout.id))
                    .group_by(Workout.domain)
                    .all()
                )

                # Count by difficulty
                difficulty_counts = dict(
                    session.query(Workout.difficulty, func.count(Workout.id))
                    .group_by(Workout.difficulty)
                    .all()
                )

                return {
                    "total_workouts": total_workouts,
                    "by_domain": domain_counts,
                    "by_difficulty": difficulty_counts,
                }
        else:
            # Legacy JSON mode
            workouts = self.workouts["workouts"]
            stats = {
                "total_workouts": len(workouts),
                "by_domain": {},
                "by_difficulty": {}
            }

            for workout in workouts.values():
                domain = workout.get("domain", "unknown")
                stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

                difficulty = workout.get("difficulty", "unknown")
                stats["by_difficulty"][difficulty] = stats["by_difficulty"].get(difficulty, 0) + 1

            return stats

    def export_to_json(self, export_path: Optional[str] = None) -> str:
        """
        Export all workouts from database to JSON file

        Args:
            export_path: Path to export file (defaults to library_path)

        Returns:
            Path to exported file
        """
        if export_path is None:
            export_path = self.library_path

        export_path = Path(export_path)

        if DATABASE_AVAILABLE:
            # Export from database
            with get_session() as session:
                workouts = session.query(Workout).all()

                export_data = {
                    "metadata": {
                        "created_date": datetime.now().isoformat(),
                        "last_modified": datetime.now().isoformat(),
                        "version": "1.0",
                        "exported_from": "database"
                    },
                    "workouts": {},
                    "blocks": {}
                }

                for workout in workouts:
                    export_data["workouts"][str(workout.id)] = workout.to_dict()

                with open(export_path, 'w') as f:
                    json.dump(export_data, f, indent=2)

                return str(export_path)
        else:
            # Already in JSON mode, just save
            self._save_library_json()
            return str(self.library_path)

    def import_from_json(self, import_path: Optional[str] = None) -> int:
        """
        Import workouts from JSON file to database

        Args:
            import_path: Path to import file (defaults to library_path)

        Returns:
            Number of workouts imported
        """
        if import_path is None:
            import_path = self.library_path

        import_path = Path(import_path)

        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")

        with open(import_path, 'r') as f:
            data = json.load(f)

        if not DATABASE_AVAILABLE:
            # In JSON mode, just load it
            self.workouts = data
            return len(data.get("workouts", {}))

        # Import to database
        count = 0
        workouts_data = data.get("workouts", {})

        with get_session() as session:
            for workout_id, workout_data in workouts_data.items():
                try:
                    db_workout = Workout(
                        id=workout_data.get("id", workout_id),
                        name=workout_data["name"],
                        domain=workout_data["domain"],
                        workout_type=workout_data["type"],
                        description=workout_data.get("description", ""),
                        content=workout_data["content"],
                        difficulty=workout_data.get("difficulty"),
                        duration_minutes=workout_data.get("duration_minutes"),
                        equipment=workout_data.get("equipment", []),
                        tags=workout_data.get("tags", []),
                        vdot_min=workout_data.get("vdot_min"),
                        vdot_max=workout_data.get("vdot_max"),
                    )
                    session.merge(db_workout)  # Update if exists, insert if new
                    count += 1
                except Exception as e:
                    print(f"Warning: Failed to import workout {workout_id}: {e}")

            session.commit()

        return count

    # Legacy methods for training blocks (not yet migrated to database)
    def add_training_block(self, block: Dict[str, Any]) -> str:
        """Add a training block (multi-week program) - not yet supported in database mode"""
        if DATABASE_AVAILABLE:
            raise NotImplementedError("Training blocks not yet supported in database mode")

        # Legacy JSON mode
        if "id" not in block:
            block["id"] = str(uuid.uuid4())

        now = datetime.now().isoformat()
        block["created_date"] = now
        block["modified_date"] = now

        self.workouts["blocks"][block["id"]] = block
        self._save_library_json()
        return block["id"]

    def get_training_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        """Get a training block by ID - not yet supported in database mode"""
        if DATABASE_AVAILABLE:
            raise NotImplementedError("Training blocks not yet supported in database mode")

        return self.workouts["blocks"].get(block_id)

    def list_training_blocks(self) -> List[Dict[str, Any]]:
        """List all training blocks - not yet supported in database mode"""
        if DATABASE_AVAILABLE:
            raise NotImplementedError("Training blocks not yet supported in database mode")

        return list(self.workouts["blocks"].values())


if __name__ == "__main__":
    # Quick CLI for testing
    import sys

    if len(sys.argv) < 2:
        print("Usage: python workout_library.py <command>")
        print("Commands: stats, list [domain]")
        sys.exit(1)

    library = WorkoutLibrary()
    command = sys.argv[1]

    if command == "stats":
        stats = library.get_stats()
        print(f"\nLibrary stats: {json.dumps(stats, indent=2)}")
    elif command == "list":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        workouts = library.list_all_workouts(domain)
        print(f"\nFound {len(workouts)} workouts")
        for w in workouts:
            print(f"  - {w['name']} ({w['domain']}/{w.get('workout_type', 'N/A')})")
    else:
        print(f"Unknown command: {command}")
