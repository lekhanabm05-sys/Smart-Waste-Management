# Custom Notification Feature - Admin Guide

## Overview
Admins can now send custom notifications to specific users or all users from the Manage Pickups page.

## Features

### 1. Send Notifications from Pickup Requests
- Navigate to **Admin Dashboard** → **Manage Pickups**
- Click the blue **"Notify"** button next to any pickup request
- Send custom messages to the user who made the pickup request

### 2. Send Bin Full Alerts
- Select a bin from the dropdown
- **Choose recipient**: Send to all users or a specific user
- System validates that the bin has at least 6 items before sending
- Alert notifies about bin requiring immediate collection

### 3. Send System Alerts
- Create custom system-wide or user-specific alerts
- Enter title and message
- **Choose recipient**: Broadcast to all users or target a specific user
- Select severity level (Info, Warning, Danger)

## How to Use

### Send Notification from Pickup Request
1. Go to **Manage Pickups** page
2. Find the pickup request in either Pending or Approved sections
3. Click the **"Notify"** button next to the request
4. Fill in the modal form:
   - **Recipient**: Auto-filled with the username (read-only)
   - **Notification Title**: Enter a descriptive title
   - **Message**: Enter your custom message
   - **Severity**: Choose from Info, Success, Warning, or Danger
5. Click **"Send Notification"**

### Send Bin Full Alert
1. Go to **Create Alerts & Notifications** section
2. Click **"Bin Full Alert"** tab
3. Select the bin ID from dropdown
4. **Select recipient**:
   - Choose "All Users (Broadcast)" to send to everyone
   - Or select a specific user from the list
5. Click **"Send Bin Full Alert"**

### Send System Alert
1. Go to **Create Alerts & Notifications** section
2. Click **"System Alert"** tab
3. Enter alert title and message
4. **Select recipient**:
   - Choose "All Users (Broadcast)" to send to everyone
   - Or select a specific user from the list
5. Select severity level
6. Click **"Send System Alert"**

## Recipient Options

### All Users (Broadcast)
- Sends notification to every user in the system
- Appears in all users' notification pages
- Useful for system-wide announcements, maintenance notices, or general alerts

### Specific User
- Sends notification only to the selected user
- Private communication between admin and user
- Useful for:
  - Individual pickup updates
  - Personal reminders
  - User-specific instructions
  - Follow-up questions

## Notification Types by Severity

- **Info** (Blue): General information, updates, reminders
- **Success** (Green): Positive updates, confirmations, completions
- **Warning** (Orange): Important notices, delays, attention needed
- **Danger** (Red): Urgent alerts, critical issues, immediate action required

## Features

### Real-time Delivery
- Notifications are delivered instantly to the user's account
- Users can view them in the Notifications page
- Unread notifications show in the navigation bar

### Activity Logging
- All sent notifications are logged in the Activity Logs
- Track who sent what notification and when

### User Verification
- System verifies the recipient exists before sending
- Error messages if user not found

## Use Cases

### Broadcast Notifications (All Users)
1. **System Maintenance**: "System will be down for maintenance on Sunday 2-4 PM"
2. **Holiday Schedule**: "Collection schedule changed for upcoming holiday"
3. **New Features**: "New waste classification feature now available"
4. **General Reminders**: "Remember to segregate waste properly"

### Targeted Notifications (Specific User)
1. **Pickup Delays**: Notify specific user about their pickup delay
2. **Special Instructions**: Send instructions to user about their specific waste
3. **Follow-ups**: Request additional information from a particular user
4. **Personal Updates**: Inform user about changes to their pickup status
5. **Reminders**: Send reminder to user who hasn't used the system recently

## Example Messages

### Pickup Delay
- **Title**: "Pickup Delay Notice"
- **Message**: "Your pickup for Bin BIN-001 has been delayed due to weather conditions. We'll collect it tomorrow morning."
- **Severity**: Warning

### Pickup Confirmation
- **Title**: "Pickup Scheduled"
- **Message**: "Your pickup request has been approved and scheduled for tomorrow at 10 AM."
- **Severity**: Success

### Additional Information Needed
- **Title**: "Information Required"
- **Message**: "Please provide more details about the waste type in Bin BIN-002 before we can process your pickup request."
- **Severity**: Info

## Technical Details

### Backend Route
- **Endpoint**: `/admin/send-notification`
- **Method**: POST
- **Authentication**: Admin only
- **Payload**:
  ```json
  {
    "recipient": "username",
    "title": "Notification Title",
    "message": "Notification message",
    "notification_type": "custom",
    "severity": "info"
  }
  ```

### Database
- Notifications are stored in the `notifications` collection
- Each notification includes:
  - Recipient username
  - Title and message
  - Timestamp
  - Read/unread status
  - Severity level
  - Icon type

## Benefits

1. **Direct Communication**: Reach users instantly without email or phone
2. **Centralized**: All notifications in one place
3. **Trackable**: View notification history in activity logs
4. **Flexible**: Customize message and severity for any situation
5. **User-Friendly**: Simple modal interface for quick messaging

## Notes

- Only admins can send custom notifications
- Recipients must be registered users in the system
- Notifications persist until the user marks them as read
- All notification activity is logged for audit purposes
