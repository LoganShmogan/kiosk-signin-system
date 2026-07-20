# Email and Facebook Integration

This document describes how the system integrates with external services for email notifications and Facebook notice board functionality.

## Email Notifications

### Purpose

When a member is signed in or out, an email notification can be sent to their caregiver. This keeps caregivers informed of their child's arrival and departure in real time.

### How It Works

The email notification system is in `kiosk_signin/email_notifier.py`. It uses Python's built-in `smtplib` and `email` modules to send emails via Gmail's SMTP server.

#### Configuration

Email settings are stored in `kiosk_signin/email_config.json`:

```json
{
    "enabled": true,
    "sender_email": "your-email@gmail.com",
    "app_password": "your-app-password"
}
```

The `app_password` is a Gmail App Password, not the account's main password. App Passwords are generated in Google Account settings under Security > 2-Step Verification > App Passwords.

#### Trigger Flow

1. After a successful sign-in/out in `signature_screen.py`, `email_notifier.send_notification()` is called.
2. The function spawns a daemon thread to send the email asynchronously, so it does not block the UI.
3. Inside the thread, it:
   - Loads the email config from the JSON file.
   - Checks if notifications are enabled.
   - Looks up the member's caregiver and their email address.
   - Checks the caregiver's `notify_on` preference ("NONE", "IN", "OUT", or "BOTH").
   - Constructs and sends the email if all conditions are met.

#### Threading

The email is sent in a background daemon thread:

```python
def send_notification(member, direction, timestamp):
    threading.Thread(
        target=_send, args=(member, direction, timestamp), daemon=True
    ).start()
```

Daemon threads are automatically terminated when the main program exits, so they do not prevent the application from closing. The `daemon=True` flag is important here because SMTP connections can hang if the server is unreachable, and we do not want that to block shutdown.

#### Error Handling

All exceptions during email sending are silently caught. This is intentional -- email notifications are a best-effort feature and should never crash the sign-in process or display errors to the caregiver at the kiosk.

#### Email Content

The email is sent as a plain text MIME message:

```
Subject: Kiosk Sign-In Notification -- Jessica Allen

Hi,

Jessica Allen has been signed IN at 03:15 PM on Monday 21 June 2026.

-- Kiosk Sign-In System
```

#### Notification Preferences

Each caregiver can configure when they receive notifications via the `notify_on` field:

- **BOTH** -- Notified on both sign-in and sign-out (default).
- **IN** -- Notified only on sign-in.
- **OUT** -- Notified only on sign-out.
- **NONE** -- No notifications.

This is set on the member's profile screen (kiosk) or the person edit form (dashboard).

## Facebook Integration

### Purpose

The system can fetch posts from the organisation's Facebook page and display them as notices on the kiosk's social screen. This provides caregivers with up-to-date information from the organisation without needing to check Facebook directly.

### How It Works

Facebook integration is handled by `kiosk_signin/facebook_api.py`. It uses the Facebook Graph API (v19.0) to fetch recent posts.

#### Configuration

Facebook credentials are stored in `kiosk_signin/config.json`:

```json
{
    "fb_page_id": "your-page-id",
    "fb_access_token": "your-long-lived-page-access-token"
}
```

The page ID and access token are obtained through Facebook's developer tools. The access token must be a long-lived page access token with read permissions.

#### Fetching Posts

The `fetch_posts()` function constructs a Graph API URL and makes an HTTP request using Python's built-in `urllib`:

```python
params = urllib.parse.urlencode({
    "fields": "id,message,story,created_time",
    "limit": limit,
    "access_token": token,
})
url = f"{GRAPH_URL}/{page_id}/posts?{params}"
```

It requests the `message`, `story`, and `created_time` fields for up to 10 posts. Each post is transformed into a dictionary with `title`, `body`, `post_id`, and `posted_at` fields.

The `title` is the first line of the post body, truncated to 80 characters. The `post_id` is the Facebook post's unique identifier, used for deduplication.

#### Storing Notices

Fetched posts are stored in the `notices` table via `database.upsert_notices()`. This uses SQLite's `ON CONFLICT` clause:

```sql
INSERT INTO notices (title, body, source, post_id, posted_at)
VALUES (:title, :body, 'facebook', :post_id, :posted_at)
ON CONFLICT(post_id) DO UPDATE SET
    body=excluded.body, posted_at=excluded.posted_at,
    fetched_at=datetime('now','localtime')
```

If a post with the same `post_id` already exists, it is updated rather than duplicated.

#### Asynchronous Refresh

The `refresh_notices_async()` function runs the fetch-and-store operation in a background thread with optional success and error callbacks:

```python
def refresh_notices_async(on_success=None, on_error=None):
    def _run():
        try:
            posts = fetch_posts()
            database.upsert_notices(posts)
            if on_success:
                on_success(posts)
        except Exception as exc:
            if on_error:
                on_error(exc)
    threading.Thread(target=_run, daemon=True).start()
```

This pattern allows the kiosk UI to trigger a refresh without freezing while the HTTP request completes.

## Programming Concepts Applied

### Asynchronous I/O with Threading

Both integrations use Python's `threading.Thread` with `daemon=True` for non-blocking I/O operations. This is a common pattern in GUI applications where the main thread must remain responsive while network operations run in the background.

### Callback Pattern

`refresh_notices_async()` uses callbacks (`on_success`, `on_error`) to notify the caller of the result. This decouples the API fetch logic from the UI update logic -- the caller decides what to do with the result.

### Configuration Files

Both integrations store credentials in JSON files that are loaded at runtime. This separates configuration from code and allows credentials to be changed without modifying the source.

### MIME Message Construction

The email system uses Python's `email.mime` module to construct properly formatted email messages. `MIMEMultipart` creates the message container, and `MIMEText` attaches the plain text body. This follows the MIME standard for email formatting.

### URL Construction

The Facebook API integration uses `urllib.parse.urlencode()` to safely construct query strings with proper URL encoding. This handles special characters in access tokens and other parameters.
