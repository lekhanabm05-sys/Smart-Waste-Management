#!/usr/bin/env python3
"""
Quick script to remove duplicate bins from MongoDB
Run this script: python cleanup_duplicate_bins.py
"""

from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['waste_management']

# Find and display duplicate bins
duplicates = list(db.bins.find({
    "bin_id": {"$regex": "^BIN-\\d{6}-\\d{5}$"},
    "area_name": "Shopping Mall"
}))

print(f"\n🔍 Found {len(duplicates)} duplicate bins:")
for bin in duplicates:
    print(f"   - {bin['bin_id']} — {bin['area_name']}")

if duplicates:
    confirm = input(f"\n⚠️  Do you want to DELETE these {len(duplicates)} bins? (yes/no): ")
    
    if confirm.lower() == 'yes':
        result = db.bins.delete_many({
            "bin_id": {"$regex": "^BIN-\\d{6}-\\d{5}$"},
            "area_name": "Shopping Mall"
        })
        print(f"\n✅ Successfully deleted {result.deleted_count} duplicate bins!")
        
        # Show remaining bins
        remaining = list(db.bins.find({}, {"bin_id": 1, "area_name": 1, "_id": 0}).sort("bin_id", 1))
        print(f"\n📋 Remaining bins ({len(remaining)}):")
        for bin in remaining:
            print(f"   - {bin['bin_id']} — {bin['area_name']}")
    else:
        print("\n❌ Cleanup cancelled.")
else:
    print("\n✅ No duplicate bins found!")
    
    # Show all bins
    all_bins = list(db.bins.find({}, {"bin_id": 1, "area_name": 1, "_id": 0}).sort("bin_id", 1))
    print(f"\n📋 All bins ({len(all_bins)}):")
    for bin in all_bins:
        print(f"   - {bin['bin_id']} — {bin['area_name']}")

client.close()
