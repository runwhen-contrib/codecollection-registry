#!/usr/bin/env python3
"""
Create raw data tables in the database
"""
import sys
import os
sys.path.append('/app')

from app.core.database import engine, Base
from app.models import RawYamlData, RawRepositoryData

def create_raw_data_tables():
    """Create the raw data tables"""
    print("Creating raw data tables...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("Raw data tables created successfully!")

if __name__ == "__main__":
    create_raw_data_tables()

