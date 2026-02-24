#!/usr/bin/env python3
"""Test location geocoding to diagnose Discord /location command issues."""

import subprocess
import json
import sys

def test_geocoding(location_input):
    """Test geocoding for a given location string."""
    print(f"\n{'='*60}")
    print(f"Testing: '{location_input}'")
    print('='*60)

    # Check if it looks like coordinates
    is_coords = False
    if ',' in location_input:
        parts = [p.strip() for p in location_input.split(',')]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    is_coords = True
                    print(f"✓ Detected as coordinates: {lat}, {lon}")
            except ValueError:
                print(f"✗ Not coordinates (has comma but not valid numbers)")

    if not is_coords:
        # Try geocoding
        import urllib.parse
        encoded = urllib.parse.quote(location_input)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=en&format=json"

        print(f"\nGeocoding URL: {url}")

        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)

            if data.get('results'):
                r = data['results'][0]
                lat = r['latitude']
                lon = r['longitude']
                name = r['name']
                admin1 = r.get('admin1', '')

                print(f"\n✓ Geocoding SUCCESS:")
                print(f"  Location: {name}, {admin1}")
                print(f"  Coordinates: {lat}, {lon}")
            else:
                print(f"\n✗ Geocoding FAILED: No results found")
                print(f"  Raw response: {result.stdout}")
        else:
            print(f"\n✗ Geocoding ERROR: curl failed")

    print()

# Test various location formats
test_cases = [
    "Altamonte Springs Florida",
    "Altamonte Springs, Florida",
    "Altamonte Springs FL",
    "Altamonte Springs, FL",
    "Altamonte Springs",
    "28.6611,-81.3937",
    "Orlando FL",
    "Miami, FL",
    "New York City",
]

print("\n" + "="*60)
print("LOCATION GEOCODING TEST SUITE")
print("="*60)

for test in test_cases:
    test_geocoding(test)

print("\n" + "="*60)
print("Test complete!")
print("="*60)
