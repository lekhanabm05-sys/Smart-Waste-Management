# Admin Reports Feature - User-Specific and Overall Reports

## Overview
Admins can now download monthly PDF reports for:
1. **Specific Users** - Individual user performance reports
2. **Overall System** - Comprehensive reports for all users combined

Regular users can only download their own reports.

## Features

### For Admin Users

#### 1. User-Specific Reports
- Download monthly reports for any individual user
- View user's waste classification statistics
- Track user's environmental impact
- Monitor user's recycling performance

#### 2. Overall System Reports
- Download comprehensive reports for all users
- View system-wide statistics
- See top performing users
- Track overall environmental impact
- Monitor total system performance

### For Regular Users
- Download only their own monthly reports
- View personal statistics and performance

## How to Use

### Admin - Download User-Specific Report

1. Go to **Statistics** page
2. Select a month from the dropdown
3. Select a specific user from the **user dropdown**
4. Click **"Download PDF Report"**
5. PDF will download with filename: `user-report-{username}-{YYYY-MM}.pdf`

### Admin - Download Overall Report

1. Go to **Statistics** page
2. Select a month from the dropdown
3. Select **"Overall Report (All Users)"** from the user dropdown
4. Click **"Download PDF Report"**
5. PDF will download with filename: `overall-report-{YYYY-MM}.pdf`

### Regular User - Download Personal Report

1. Go to **Statistics** page
2. Select a month from the dropdown
3. Click **"Download My Report"**
4. PDF will download with filename: `waste-report-{YYYY-MM}.pdf`

## Report Contents

### User-Specific Report Includes:
- **User Information**: Username
- **Time Period**: Selected month and year
- **Summary Metrics**:
  - Total Classifications
  - Collected Items
  - Plastic Saved (kg)
  - CO₂ Reduced (kg)
  - Recycling Rate (%)
- **Waste Type Breakdown**:
  - Count per waste type
  - Percentage distribution

### Overall Report Includes:
- **System Overview**: All users combined
- **Time Period**: Selected month and year
- **Summary Metrics**:
  - Total Classifications (all users)
  - Total Users
  - Collected Items
  - Plastic Saved (kg)
  - CO₂ Reduced (kg)
  - Recycling Rate (%)
- **User Performance Table**:
  - Top 20 users by activity
  - Each user's total, collected, and rate
- **Waste Type Breakdown**:
  - System-wide waste distribution
  - Count and percentage per type

## API Endpoints

### 1. Download User-Specific Report
```
GET /admin/download_user_report/<year>/<month>/<username>
```

**Access**: Admin only

**Parameters**:
- `year`: Year (e.g., 2024)
- `month`: Month number (1-12)
- `username`: Target user's username

**Response**: PDF file download

**Errors**:
- 403: Not admin
- 404: User not found or no data for selected month

### 2. Download Overall Report
```
GET /admin/download_overall_report/<year>/<month>
```

**Access**: Admin only

**Parameters**:
- `year`: Year (e.g., 2024)
- `month`: Month number (1-12)

**Response**: PDF file download

**Errors**:
- 403: Not admin
- 404: No data for selected month

### 3. Download Personal Report (Existing)
```
GET /download_monthly_report/<year>/<month>
```

**Access**: All authenticated users

**Parameters**:
- `year`: Year (e.g., 2024)
- `month`: Month number (1-12)

**Response**: PDF file download

**Behavior**:
- Admin: Downloads overall report (all users)
- Regular user: Downloads personal report

## UI Changes

### Admin View
```
┌─────────────────────────────────────────────────────────┐
│ 📊 Statistics Dashboard                                 │
│ Comprehensive waste management analytics and insights   │
├─────────────────────────────────────────────────────────┤
│ 📄 Monthly Reports                                      │
│                                                         │
│ [Select Month ▼] [Overall Report (All Users) ▼]        │
│                   ─────────────────────────             │
│                   john_doe (john@example.com)           │
│                   jane_smith (jane@example.com)         │
│                   bob_wilson (bob@example.com)          │
│                                                         │
│ [📥 Download PDF Report]                                │
└─────────────────────────────────────────────────────────┘
```

### Regular User View
```
┌─────────────────────────────────────────────────────────┐
│ 📊 Statistics Dashboard                                 │
│ Comprehensive waste management analytics and insights   │
├─────────────────────────────────────────────────────────┤
│ 📄 Monthly Reports                                      │
│                                                         │
│ [Select Month ▼]                                        │
│                                                         │
│ [📥 Download My Report]                                 │
└─────────────────────────────────────────────────────────┘
```

## Use Cases

### 1. Monitor Individual User Performance
**Scenario**: Admin wants to check how well a specific user is performing

**Steps**:
1. Select month: "January 2024"
2. Select user: "john_doe"
3. Download report
4. Review john_doe's statistics and recycling rate

### 2. Generate System-Wide Report
**Scenario**: Admin needs monthly report for management review

**Steps**:
1. Select month: "January 2024"
2. Select: "Overall Report (All Users)"
3. Download report
4. Present to management with system-wide metrics

### 3. Compare User Performance
**Scenario**: Admin wants to identify top performers

**Steps**:
1. Download overall report
2. Review "User Performance" table
3. Identify top 20 users by activity
4. Download individual reports for top users

### 4. Track Monthly Progress
**Scenario**: Admin monitors system growth month-over-month

**Steps**:
1. Download overall reports for last 3 months
2. Compare total classifications
3. Track user growth
4. Monitor environmental impact trends

## Technical Implementation

### Backend Routes
- **User-Specific**: `/admin/download_user_report/<year>/<month>/<username>`
- **Overall**: `/admin/download_overall_report/<year>/<month>`
- **Personal**: `/download_monthly_report/<year>/<month>` (existing)

### Database Queries

#### User-Specific Report
```python
# Filter for specific user
user_filter = {"uploaded_by": username}

# Get user's waste statistics
mongo.db.waste_records.aggregate([
    {"$match": {
        **user_filter,
        "timestamp": {"$gte": month_start, "$lte": month_end}
    }},
    {"$group": {"_id": "$predicted_type", "count": {"$sum": 1}}}
])
```

#### Overall Report
```python
# No user filter - all users
mongo.db.waste_records.aggregate([
    {"$match": {
        "timestamp": {"$gte": month_start, "$lte": month_end}
    }},
    {"$group": {"_id": "$predicted_type", "count": {"$sum": 1}}}
])

# Per-user statistics
mongo.db.waste_records.aggregate([
    {"$match": {"timestamp": {"$gte": month_start, "$lte": month_end}}},
    {"$group": {
        "_id": "$uploaded_by",
        "total": {"$sum": 1},
        "collected": {"$sum": {"$cond": [{"$eq": ["$status", "Collected"]}, 1, 0]}}
    }},
    {"$sort": {"total": -1}}
])
```

### PDF Generation
- Uses ReportLab library
- Professional styling with green theme
- Tables with headers and data
- Automatic pagination
- Consistent formatting

## Security

### Access Control
- **Admin routes**: Check `session.get('role') == 'admin'`
- **User validation**: Verify user exists before generating report
- **Data isolation**: Regular users can only access their own data

### Error Handling
- 403 Forbidden: Non-admin trying to access admin routes
- 404 Not Found: User doesn't exist or no data for month
- 500 Internal Error: PDF generation failure

## Benefits

### For Admins
1. **User Monitoring**: Track individual user performance
2. **System Overview**: Comprehensive system-wide insights
3. **Performance Analysis**: Identify top performers and trends
4. **Reporting**: Generate professional reports for stakeholders
5. **Data-Driven Decisions**: Make informed decisions based on data

### For Organization
1. **Accountability**: Track user contributions
2. **Transparency**: Clear performance metrics
3. **Goal Setting**: Set targets based on historical data
4. **Recognition**: Identify and reward top performers
5. **Improvement**: Identify areas needing attention

## Future Enhancements

Possible improvements:
1. **Date Range Reports**: Custom date ranges instead of just monthly
2. **Comparison Reports**: Compare multiple users side-by-side
3. **Trend Analysis**: Multi-month trend reports with charts
4. **Export Formats**: Excel, CSV in addition to PDF
5. **Scheduled Reports**: Automatic monthly report generation
6. **Email Delivery**: Send reports via email automatically
7. **Custom Filters**: Filter by waste type, location, etc.
8. **Dashboard Integration**: Embed report previews in dashboard

---

**Status**: ✅ Implemented
**Date**: Current
**Access**: Admin only (user-specific and overall reports)
