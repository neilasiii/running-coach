#!/bin/bash
set -e

echo "🚀 Starting Running Coach Service..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h postgres -p 5432; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "✅ PostgreSQL is ready!"

# Wait an additional 2 seconds for database to be fully initialized
sleep 2

# Check if database is initialized
echo "🔍 Checking database initialization..."
TABLE_COUNT=$(psql "${DATABASE_URL}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -eq "0" ]; then
  echo "📊 Database empty - initializing tables..."

  # Run database initialization
  python3 src/database/init_db.py create

  # Mark the migration as applied (stamp without running)
  echo "📝 Marking migration as applied..."
  alembic stamp head

  echo "✅ Database initialized successfully!"
else
  echo "✅ Database already initialized ($TABLE_COUNT tables found)"

  # Check if alembic_version table exists
  ALEMBIC_TABLE=$(psql "${DATABASE_URL}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'alembic_version';" 2>/dev/null || echo "0")

  if [ "$ALEMBIC_TABLE" -eq "0" ]; then
    echo "📝 Alembic version tracking not initialized - stamping current state..."
    alembic stamp head
  else
    # Run any pending migrations
    echo "🔄 Checking for pending migrations..."
    alembic upgrade head
  fi
fi

echo "🌐 Starting web server..."
exec python -m src.web.app
