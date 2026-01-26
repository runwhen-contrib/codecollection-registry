#!/usr/bin/env python3
"""
Debug script to check Redis configuration at runtime
Run this inside a worker pod to see what values are actually being used
"""
import os
import sys

print("=" * 70)
print("ENVIRONMENT VARIABLES (Redis related)")
print("=" * 70)

redis_vars = {k: v for k, v in os.environ.items() if 'REDIS' in k.upper()}
for key in sorted(redis_vars.keys()):
    value = redis_vars[key]
    # Mask password
    if 'PASSWORD' in key.upper():
        value = '***MASKED***'
    print(f"{key} = {repr(value)}")

print("\n" + "=" * 70)
print("PYDANTIC SETTINGS (after parsing)")
print("=" * 70)

sys.path.insert(0, '/app')
from app.core.config import settings

print(f"settings.REDIS_URL = {repr(settings.REDIS_URL)}")
print(f"settings.REDIS_SENTINEL_HOSTS = {repr(settings.REDIS_SENTINEL_HOSTS)}")
print(f"settings.REDIS_SENTINEL_MASTER = {repr(settings.REDIS_SENTINEL_MASTER)}")
print(f"settings.REDIS_DB = {repr(settings.REDIS_DB)} (type: {type(settings.REDIS_DB).__name__})")
print(f"settings.REDIS_PASSWORD = {'***SET***' if settings.REDIS_PASSWORD else 'None'}")

print("\n" + "=" * 70)
print("CELERY CONFIGURATION")
print("=" * 70)

from app.tasks.celery_app import broker_url, transport_options

print(f"broker_url = {broker_url}")
print(f"transport_options = {transport_options}")

print("\n" + "=" * 70)
print("DIAGNOSIS")
print("=" * 70)

if isinstance(settings.REDIS_DB, str):
    print(f"⚠️  WARNING: REDIS_DB is a STRING: {repr(settings.REDIS_DB)}")
    print(f"   This will cause int() conversion errors!")
elif isinstance(settings.REDIS_DB, int):
    print(f"✅ OK: REDIS_DB is an integer: {settings.REDIS_DB}")
else:
    print(f"❌ ERROR: REDIS_DB has unexpected type: {type(settings.REDIS_DB)}")

if settings.REDIS_SENTINEL_HOSTS and 'sentinel://' in settings.REDIS_URL:
    print(f"✅ OK: Using Sentinel configuration")
elif settings.REDIS_SENTINEL_HOSTS and 'redis://' in settings.REDIS_URL:
    print(f"⚠️  WARNING: Sentinel hosts configured but REDIS_URL is not sentinel://")
else:
    print(f"ℹ️  Using standalone Redis")

print("\n" + "=" * 70)
