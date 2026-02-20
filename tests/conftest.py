# conftest.py — pytest configuration for running-coach test suite

# These are standalone integration/diagnostic scripts, not pytest test modules.
# They run code at module level (subprocess calls, print statements) and cannot
# be collected by pytest. Listed here to prevent collection errors.
collect_ignore = [
    "test_ai_call.py",
    "test_location_fix.py",
    "test_location_geocoding.py",
    "test_session.py",
]
