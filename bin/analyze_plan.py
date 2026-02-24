#!/usr/bin/env python3
import json
from datetime import datetime, timedelta
from collections import defaultdict

with open('/home/coach/running-coach/data/health/health_data_cache.json', 'r') as f:
    d = json.load(f)

activities = d.get('activities', [])

# Filter running activities
runs = []
for a in activities:
    atype = a.get('activity_type', '').lower()
    name = a.get('activity_name', '').lower()
    if 'run' in atype or 'run' in name or 'tempo' in name or 'interval' in name:
        runs.append(a)

# Group by week
weekly_data = defaultdict(lambda: {'miles': 0, 'duration': 0, 'runs': [], 'quality': []})

for run in runs:
    date_str = run.get('date', '')[:10]
    name = run.get('activity_name', '')
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        week_start = date - timedelta(days=date.weekday())
        week_key = week_start.strftime('%Y-%m-%d')

        distance_mi = run.get('distance_miles', 0) or 0
        duration_min = (run.get('duration_seconds', 0) or 0) / 60

        weekly_data[week_key]['miles'] += distance_mi
        weekly_data[week_key]['duration'] += duration_min
        weekly_data[week_key]['runs'].append(name)

        # Track quality workouts
        name_lower = name.lower()
        if any(q in name_lower for q in ['tempo', 'interval', 'threshold', '5k', 'marathon', 'repeat', 'progression', 'long run']):
            weekly_data[week_key]['quality'].append(name)

# Get weeks sorted
weeks = sorted(weekly_data.keys())

# Find peak week
peak_miles = 0
peak_week = ''
for w in weeks:
    if weekly_data[w]['miles'] > peak_miles:
        peak_miles = weekly_data[w]['miles']
        peak_week = w

print('='*70)
print('MILEAGE PROGRESSION ANALYSIS')
print('='*70)
print(f'\nHistorical Peak Week: {peak_week} with {peak_miles:.1f} miles')

# Show weeks leading up to marathon (Nov 23, 2025)
print('\n' + '='*70)
print('MARATHON BUILD (Oct-Nov 2025)')
print('='*70)
for w in [w for w in weeks if '2025-10' in w or '2025-11' in w]:
    data = weekly_data[w]
    quality_list = data['quality'][:2] if data['quality'] else ['Easy only']
    quality_str = ', '.join([q[:35] for q in quality_list])
    print(f"{w}: {data['miles']:5.1f} mi | {len(data['runs'])} runs | {quality_str}")

# Show post-marathon recovery and half build
print('\n' + '='*70)
print('POST-MARATHON RECOVERY + HALF BUILD (Dec 2025 - Jan 2026)')
print('='*70)
for w in [w for w in weeks if '2025-12' in w or '2026-01' in w]:
    data = weekly_data[w]
    quality_list = data['quality'][:2] if data['quality'] else ['Easy only']
    quality_str = ', '.join([q[:35] for q in quality_list])
    print(f"{w}: {data['miles']:5.1f} mi | {len(data['runs'])} runs | {quality_str}")

# Upcoming workouts
print('\n' + '='*70)
print('UPCOMING SCHEDULED WORKOUTS')
print('='*70)
workouts = d.get('scheduled_workouts', [])
for w in sorted(workouts, key=lambda x: x.get('scheduled_date', '')):
    date = w.get('scheduled_date', '')
    name = w.get('name', '')[:60]
    print(f"{date}: {name}")
