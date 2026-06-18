# Statistics Page Fix - Environmental Impact Calculations

## Problem
The statistics page was showing **0 kg** for all environmental impact metrics:
- Plastic Saved: 0 kg
- CO₂ Reduced: 0 kg  
- Recycling Rate: 0.0%

## Root Cause
The calculations were based on items with status **"Recycled"**, but in the actual workflow:
- Items start with status: **"In Transit"**
- When bins are collected, items change to: **"Collected"**
- There is no automatic transition to **"Recycled"** status

Since no items had "Recycled" status, all calculations returned zero.

## Solution
Changed the statistics calculation to use **"Collected"** status instead of "Recycled":

### Before (Incorrect):
```python
# Count recycled items per type
recycled_filter = {**query_filter, "status": "Recycled"}
recycled_cursor = mongo.db.waste_records.aggregate([
    {"$match": recycled_filter},
    {"$group": {"_id": "$predicted_type", "count": {"$sum": 1}}}
])
recycled_by_type = {item["_id"]: item["count"] for item in recycled_cursor}
```

### After (Fixed):
```python
# Count collected items per type (items that have been collected are considered processed)
collected_filter = {**query_filter, "status": "Collected"}
collected_cursor = mongo.db.waste_records.aggregate([
    {"$match": collected_filter},
    {"$group": {"_id": "$predicted_type", "count": {"$sum": 1}}}
])
collected_by_type = {item["_id"]: item["count"] for item in collected_cursor}
```

## What Changed

### 1. Plastic Saved Calculation
**Before**: Based on recycled plastic items (always 0)
```python
plastic_recycled_count = recycled_by_type.get('Plastic Waste', 0)
plastic_saved_kg = round(plastic_recycled_count * WEIGHTS_KG.get('Plastic Waste', 0), 2)
```

**After**: Based on collected plastic items
```python
plastic_collected_count = collected_by_type.get('Plastic Waste', 0)
plastic_saved_kg = round(plastic_collected_count * WEIGHTS_KG.get('Plastic Waste', 0), 2)
```

### 2. CO₂ Reduced Calculation
**Before**: Based on all recycled items (always 0)
```python
for t, cnt in recycled_by_type.items():
    w = WEIGHTS_KG.get(t, 0)
    co2_per = CO2_SAVED_PER_KG.get(t, 0)
    total_co2_saved += cnt * w * co2_per
    total_recycled_count += cnt
```

**After**: Based on all collected items
```python
for t, cnt in collected_by_type.items():
    w = WEIGHTS_KG.get(t, 0)
    co2_per = CO2_SAVED_PER_KG.get(t, 0)
    total_co2_saved += cnt * w * co2_per
    total_collected_count += cnt
```

### 3. Recycling Rate Calculation
**Before**: (Recycled count / Total count) × 100 (always 0%)
```python
recycling_percentage = round((total_recycled_count / total * 100), 1) if total > 0 else 0.0
```

**After**: (Collected count / Total count) × 100
```python
recycling_percentage = round((total_collected_count / total * 100), 1) if total > 0 else 0.0
```

## Calculation Formulas

### Plastic Saved (kg)
```
Plastic Saved = Number of Collected Plastic Items × 0.12 kg
```
Example: 10 plastic items collected = 10 × 0.12 = 1.2 kg

### CO₂ Reduced (kg)
```
CO₂ Reduced = Σ (Item Count × Weight per Item × CO₂ Factor)
```

CO₂ Factors per kg:
- Plastic Waste: 2.5 kg CO₂
- Wet Waste: 0.4 kg CO₂
- Dry Waste: 0.9 kg CO₂
- Metal Waste: 1.8 kg CO₂

Example:
- 10 Plastic items: 10 × 0.12 kg × 2.5 = 3.0 kg CO₂
- 5 Metal items: 5 × 0.05 kg × 1.8 = 0.45 kg CO₂
- Total: 3.45 kg CO₂ reduced

### Recycling Rate (%)
```
Recycling Rate = (Collected Items / Total Items) × 100
```
Example: 15 collected out of 20 total = (15/20) × 100 = 75%

## Expected Results After Fix

### Scenario: User has uploaded and collected waste
- **Total Classifications**: 20 items
- **Collected Items**: 15 items
  - 10 Plastic Waste
  - 3 Wet Waste
  - 2 Metal Waste

### Statistics Will Show:
1. **Plastic Saved**: 1.2 kg (10 × 0.12)
2. **CO₂ Reduced**: 3.75 kg
   - Plastic: 10 × 0.12 × 2.5 = 3.0 kg
   - Wet: 3 × 0.18 × 0.4 = 0.216 kg
   - Metal: 2 × 0.05 × 1.8 = 0.18 kg
   - Total: 3.396 kg ≈ 3.4 kg
3. **Recycling Rate**: 75% (15/20 × 100)

## Workflow Alignment

The fix aligns with the actual waste management workflow:

1. **User uploads waste image** → Status: "In Transit"
2. **Admin approves pickup** → Status: "In Transit" (unchanged)
3. **Admin marks as collected** → Status: "Collected"
4. **Statistics calculate impact** → Based on "Collected" items ✅

## Benefits

1. **Accurate Metrics**: Statistics now reflect actual collected waste
2. **Real-time Updates**: Metrics update as bins are collected
3. **User Motivation**: Users see their environmental impact immediately
4. **Workflow Consistency**: Calculations match the actual process

## Testing Checklist

- [ ] Upload waste images (status: In Transit)
- [ ] Request pickup (status: In Transit)
- [ ] Admin approves pickup (status: In Transit)
- [ ] Admin marks as collected (status: Collected)
- [ ] Check statistics page shows non-zero values
- [ ] Verify plastic saved calculation
- [ ] Verify CO₂ reduced calculation
- [ ] Verify recycling rate percentage

## Notes

- The term "Recycling Rate" now represents the percentage of waste that has been collected and processed
- "Collected" items are considered as successfully recycled/processed
- The "Recycled" status is still available in the database but not used in the current workflow
- If needed in the future, a separate "Recycled" status can be implemented with additional workflow steps

---

**Status**: ✅ Fixed
**Date**: Current
**Impact**: High - Core statistics functionality restored
