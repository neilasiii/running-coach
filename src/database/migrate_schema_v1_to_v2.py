#!/usr/bin/env python3
"""
Migration script to upgrade database schema from v1 to v2.

This script migrates the database schema to match the updated health data models:
- Activity: Renames columns and converts units (miles → km, seconds → minutes)
- SleepSession, VO2MaxReading, WeightReading, etc.: Renames date → reading_date
- WeightReading: Converts units (lbs → kg)

IMPORTANT: This migration is DESTRUCTIVE. Backup your database first!

Usage:
    # Dry run (show what would be changed)
    python3 src/database/migrate_schema_v1_to_v2.py --dry-run

    # Actually run the migration
    python3 src/database/migrate_schema_v1_to_v2.py
"""

import os
import sys
import argparse
from sqlalchemy import text, inspect
from connection import get_session, DATABASE_URL


def check_table_exists(session, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = session.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_name = :table_name)"
    ), {"table_name": table_name})
    return result.scalar()


def check_column_exists(session, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = session.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :table_name AND column_name = :column_name)"
    ), {"table_name": table_name, "column_name": column_name})
    return result.scalar()


def migrate_activities_table(session, dry_run: bool = False):
    """Migrate activities table to new schema."""
    print("\n📋 Migrating activities table...")

    if not check_table_exists(session, 'activities'):
        print("  ℹ️  Table 'activities' does not exist. Skipping.")
        return

    migrations = []

    # Check and rename columns
    if check_column_exists(session, 'activities', 'activity_id'):
        migrations.append("ALTER TABLE activities RENAME COLUMN activity_id TO garmin_activity_id")

    if check_column_exists(session, 'activities', 'date'):
        migrations.append("ALTER TABLE activities RENAME COLUMN date TO start_time")

    if check_column_exists(session, 'activities', 'duration_seconds'):
        migrations.append("ALTER TABLE activities RENAME COLUMN duration_seconds TO duration_minutes")
        migrations.append("UPDATE activities SET duration_minutes = duration_minutes / 60 WHERE duration_minutes IS NOT NULL")

    if check_column_exists(session, 'activities', 'distance_miles'):
        migrations.append("ALTER TABLE activities RENAME COLUMN distance_miles TO distance_km")
        migrations.append("UPDATE activities SET distance_km = distance_km * 1.60934 WHERE distance_km IS NOT NULL")

    if check_column_exists(session, 'activities', 'pace_per_mile'):
        migrations.append("ALTER TABLE activities RENAME COLUMN pace_per_mile TO avg_pace_per_km")
        # Note: pace conversion requires more complex logic, handled separately
        migrations.append("UPDATE activities SET avg_pace_per_km = NULL")  # Will be recalculated on next sync

    # Drop columns that no longer exist
    if check_column_exists(session, 'activities', 'avg_speed'):
        migrations.append("ALTER TABLE activities DROP COLUMN avg_speed")

    # Update indexes
    migrations.append("DROP INDEX IF EXISTS idx_activity_date")
    migrations.append("DROP INDEX IF EXISTS idx_activity_type_date")
    migrations.append("CREATE INDEX IF NOT EXISTS idx_activity_start_time ON activities(start_time)")
    migrations.append("CREATE INDEX IF NOT EXISTS idx_activity_type_time ON activities(activity_type, start_time)")

    if dry_run:
        print("  🔍 DRY RUN - Would execute:")
        for sql in migrations:
            print(f"     {sql}")
    else:
        for sql in migrations:
            print(f"  ⚙️  Executing: {sql[:80]}...")
            session.execute(text(sql))
        session.commit()
        print("  ✅ Activities table migrated")


def migrate_simple_date_rename(session, table_name: str, dry_run: bool = False):
    """Migrate tables that only need date → reading_date rename."""
    print(f"\n📋 Migrating {table_name} table...")

    if not check_table_exists(session, table_name):
        print(f"  ℹ️  Table '{table_name}' does not exist. Skipping.")
        return

    if not check_column_exists(session, table_name, 'date'):
        print(f"  ℹ️  Column 'date' already migrated or doesn't exist. Skipping.")
        return

    migrations = [
        f"ALTER TABLE {table_name} RENAME COLUMN date TO reading_date",
    ]

    # Update index for some tables
    if table_name in ['vo2_max_readings']:
        migrations.append(f"DROP INDEX IF EXISTS idx_vo2_date")
        migrations.append(f"CREATE INDEX IF NOT EXISTS idx_vo2_reading_date ON {table_name}(reading_date)")

    if dry_run:
        print("  🔍 DRY RUN - Would execute:")
        for sql in migrations:
            print(f"     {sql}")
    else:
        for sql in migrations:
            print(f"  ⚙️  Executing: {sql}")
            session.execute(text(sql))
        session.commit()
        print(f"  ✅ {table_name} migrated")


def migrate_sleep_sessions(session, dry_run: bool = False):
    """Migrate sleep_sessions table."""
    print("\n📋 Migrating sleep_sessions table...")

    if not check_table_exists(session, 'sleep_sessions'):
        print("  ℹ️  Table 'sleep_sessions' does not exist. Skipping.")
        return

    migrations = []

    if check_column_exists(session, 'sleep_sessions', 'date'):
        # Convert DateTime to Date (just take the date part)
        migrations.append("ALTER TABLE sleep_sessions RENAME COLUMN date TO sleep_date")
        migrations.append("ALTER TABLE sleep_sessions ALTER COLUMN sleep_date TYPE DATE")

    if dry_run:
        print("  🔍 DRY RUN - Would execute:")
        for sql in migrations:
            print(f"     {sql}")
    else:
        for sql in migrations:
            print(f"  ⚙️  Executing: {sql}")
            session.execute(text(sql))
        session.commit()
        print("  ✅ sleep_sessions migrated")


def migrate_weight_readings(session, dry_run: bool = False):
    """Migrate weight_readings table (includes unit conversion)."""
    print("\n📋 Migrating weight_readings table...")

    if not check_table_exists(session, 'weight_readings'):
        print("  ℹ️  Table 'weight_readings' does not exist. Skipping.")
        return

    migrations = []

    if check_column_exists(session, 'weight_readings', 'date'):
        migrations.append("ALTER TABLE weight_readings RENAME COLUMN date TO reading_date")
        migrations.append("ALTER TABLE weight_readings ALTER COLUMN reading_date TYPE DATE")

    if check_column_exists(session, 'weight_readings', 'weight_lbs'):
        migrations.append("ALTER TABLE weight_readings RENAME COLUMN weight_lbs TO weight_kg")
        migrations.append("UPDATE weight_readings SET weight_kg = weight_kg / 2.20462 WHERE weight_kg IS NOT NULL")

    if check_column_exists(session, 'weight_readings', 'body_fat_percent'):
        migrations.append("ALTER TABLE weight_readings RENAME COLUMN body_fat_percent TO body_fat_percentage")

    if check_column_exists(session, 'weight_readings', 'muscle_percent'):
        migrations.append("ALTER TABLE weight_readings RENAME COLUMN muscle_percent TO muscle_mass_kg")
        # Note: muscle_percent (%) needs to be converted to actual kg based on weight
        # This is complex, so we'll just null it out and let it be recalculated
        migrations.append("UPDATE weight_readings SET muscle_mass_kg = NULL")

    if dry_run:
        print("  🔍 DRY RUN - Would execute:")
        for sql in migrations:
            print(f"     {sql}")
    else:
        for sql in migrations:
            print(f"  ⚙️  Executing: {sql[:80]}...")
            session.execute(text(sql))
        session.commit()
        print("  ✅ weight_readings migrated")


def migrate_hrv_readings(session, dry_run: bool = False):
    """Migrate hrv_readings table."""
    print("\n📋 Migrating hrv_readings table...")

    if not check_table_exists(session, 'hrv_readings'):
        print("  ℹ️  Table 'hrv_readings' does not exist. Skipping.")
        return

    migrations = []

    if check_column_exists(session, 'hrv_readings', 'date'):
        migrations.append("ALTER TABLE hrv_readings RENAME COLUMN date TO reading_date")
        migrations.append("ALTER TABLE hrv_readings ALTER COLUMN reading_date TYPE DATE")

    # Remove hrv_status column (no longer used)
    if check_column_exists(session, 'hrv_readings', 'hrv_status'):
        migrations.append("ALTER TABLE hrv_readings DROP COLUMN hrv_status")

    # Add new columns if they don't exist
    if not check_column_exists(session, 'hrv_readings', 'baseline_balanced_low'):
        migrations.append("ALTER TABLE hrv_readings ADD COLUMN baseline_balanced_low FLOAT")

    if not check_column_exists(session, 'hrv_readings', 'baseline_balanced_high'):
        migrations.append("ALTER TABLE hrv_readings ADD COLUMN baseline_balanced_high FLOAT")

    # Make hrv_value nullable (it might not always be available)
    migrations.append("ALTER TABLE hrv_readings ALTER COLUMN hrv_value DROP NOT NULL")

    if dry_run:
        print("  🔍 DRY RUN - Would execute:")
        for sql in migrations:
            print(f"     {sql}")
    else:
        for sql in migrations:
            print(f"  ⚙️  Executing: {sql[:80]}...")
            session.execute(text(sql))
        session.commit()
        print("  ✅ hrv_readings migrated")


def migrate_training_readiness(session, dry_run: bool = False):
    """Migrate training_readiness table."""
    print("\n📋 Migrating training_readiness table...")

    if not check_table_exists(session, 'training_readiness'):
        print("  ℹ️  Table 'training_readiness' does not exist. Skipping.")
        return

    migrations = []

    if check_column_exists(session, 'training_readiness', 'date'):
        migrations.append("ALTER TABLE training_readiness RENAME COLUMN date TO reading_date")
        migrations.append("ALTER TABLE training_readiness ALTER COLUMN reading_date TYPE DATE")

    if check_column_exists(session, 'training_readiness', 'readiness_score'):
        migrations.append("ALTER TABLE training_readiness RENAME COLUMN readiness_score TO score")

    if dry_run:
        print("  🔍 DRY RUN - Would execute:")
        for sql in migrations:
            print(f"     {sql}")
    else:
        for sql in migrations:
            print(f"  ⚙️  Executing: {sql}")
            session.execute(text(sql))
        session.commit()
        print("  ✅ training_readiness migrated")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate database schema from v1 to v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be changed
  python3 src/database/migrate_schema_v1_to_v2.py --dry-run

  # Actually run the migration
  python3 src/database/migrate_schema_v1_to_v2.py

IMPORTANT: Backup your database before running this migration!
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without actually changing anything'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  Database Schema Migration: v1 → v2")
    print("=" * 70)
    print(f"\nDatabase URL: {DATABASE_URL}")
    print(f"Mode: {'DRY RUN (no changes will be made)' if args.dry_run else 'LIVE (changes will be applied)'}")

    if not args.dry_run:
        print("\n⚠️  WARNING: This migration will modify your database schema!")
        print("⚠️  Make sure you have a backup before proceeding.")
        response = input("\nDo you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            sys.exit(0)

    try:
        with get_session() as session:
            # Migrate all tables
            migrate_activities_table(session, args.dry_run)
            migrate_sleep_sessions(session, args.dry_run)
            migrate_simple_date_rename(session, 'vo2_max_readings', args.dry_run)
            migrate_weight_readings(session, args.dry_run)
            migrate_simple_date_rename(session, 'resting_hr_readings', args.dry_run)
            migrate_hrv_readings(session, args.dry_run)
            migrate_training_readiness(session, args.dry_run)

            print("\n" + "=" * 70)
            if args.dry_run:
                print("✅ DRY RUN COMPLETE - No changes were made")
                print("\nTo actually run the migration, run without --dry-run flag")
            else:
                print("✅ MIGRATION COMPLETE")
                print("\nYour database schema has been upgraded to v2")
                print("You can now run: bash bin/sync_garmin_data.sh")
            print("=" * 70)

    except Exception as e:
        print(f"\n❌ ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
