# Threading and Concurrency

This document explains how the system uses threading to run multiple components concurrently and the considerations involved.

## Overview

The Kiosk Sign-In System runs two separate application interfaces (Tkinter kiosk and Flask dashboard) within a single process. It also performs background I/O operations (email sending, Facebook API calls) without blocking the user interface. All of this is achieved through Python's `threading` module.

## Main Architecture: Kiosk + Dashboard

The entry point (`app.py`) starts the Flask dashboard in a background thread before launching the Tkinter main loop:

```python
def _start_dashboard():
    from dashboard.app import app as dashboard_app
    dashboard_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    dashboard_thread = threading.Thread(target=_start_dashboard, daemon=True)
    dashboard_thread.start()
    App().run()
```

### Why a Daemon Thread

The dashboard thread is created with `daemon=True`. Daemon threads are automatically terminated when the main thread exits. This means:

- Closing the kiosk window ends the main thread's `mainloop()`.
- The daemon dashboard thread is immediately killed.
- No cleanup code is needed to shut down Flask.

Without `daemon=True`, the Flask server would keep the process alive even after the kiosk window is closed.

### Why Not Multiprocessing

Threads were chosen over processes because:

1. Both components access the same SQLite database file. SQLite handles concurrent access from multiple threads within a process well (especially with WAL mode), but cross-process locking is more complex.
2. A single process is simpler to deploy and manage, especially on a single-purpose kiosk device.
3. The Flask server and Tkinter GUI do not compete for CPU -- Flask is I/O-bound (waiting for requests), and Tkinter is event-driven (waiting for user input).

### Flask Configuration

Two Flask settings are critical for this setup:

- `debug=False` -- Debug mode starts a reloader subprocess that would conflict with the Tkinter main loop.
- `use_reloader=False` -- The reloader monitors file changes and restarts the process, which would kill the kiosk.

## Background I/O Operations

### Email Notifications

When a member is signed in or out, an email notification is sent asynchronously:

```python
def send_notification(member, direction, timestamp):
    threading.Thread(
        target=_send, args=(member, direction, timestamp), daemon=True
    ).start()
```

A new thread is spawned for each notification. This is appropriate because:

- SMTP operations can take several seconds (DNS lookup, TLS handshake, authentication, message delivery).
- The kiosk UI must remain responsive during this time.
- Email sending is fire-and-forget -- we do not need the result.

The daemon flag ensures that pending email threads do not prevent the application from exiting.

### Facebook API Calls

Facebook post fetching uses the same pattern:

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

The difference here is the use of callbacks (`on_success`, `on_error`). This allows the caller to update the UI when the operation completes. However, Tkinter requires UI updates to happen on the main thread, so the callback must use `widget.after()` to schedule the update rather than modifying widgets directly.

## SQLite Thread Safety

SQLite supports multiple concurrent readers and a single writer. The system enables WAL (Write-Ahead Logging) mode on every connection:

```python
conn.execute("PRAGMA journal_mode=WAL")
```

WAL mode allows:
- Multiple threads to read simultaneously.
- A single thread to write while others read.
- No blocking between the kiosk thread and the dashboard thread for read operations.

Each function in `database.py` opens its own connection (`get_conn()`), performs the operation, and closes it. This avoids sharing connection objects between threads, which SQLite does not support safely in all configurations.

## Tkinter and the GIL

Python's Global Interpreter Lock (GIL) ensures that only one thread executes Python bytecode at a time. This has two implications for this system:

1. **CPU-bound work**: The GIL prevents true parallel execution of Python code. However, this system's background threads are I/O-bound (waiting for network responses, database writes), so the GIL is released during those waits, allowing other threads to run.

2. **Tkinter thread safety**: Tkinter is not thread-safe -- widgets must only be modified from the main thread. Background threads should use `widget.after(0, callback)` to schedule UI updates on the main thread's event loop. The email notifier avoids this issue entirely by not touching the UI.

## Virtual Keyboard Focus Management

The virtual keyboard uses a threading-adjacent technique -- delayed callbacks with `widget.after()`:

```python
def _on_focus_out(self, event):
    self._pending_detach = self.root.after(400, self._detach_if_not_entry)
```

When focus leaves an Entry widget, the keyboard detach is delayed by 400ms. If focus moves to another Entry within that window, the pending detach is cancelled. This prevents the keyboard from flickering when the user taps between input fields.

This is not threading in the traditional sense, but it uses the same principle of deferred execution -- scheduling work to happen later based on the current state.

## Summary of Threading Use

| Component            | Thread Type  | Purpose                          |
|----------------------|-------------|----------------------------------|
| Tkinter mainloop     | Main thread  | Kiosk GUI event loop             |
| Flask server         | Daemon       | Web dashboard HTTP server        |
| Email notifications  | Daemon       | SMTP email sending               |
| Facebook API fetch   | Daemon       | HTTP request to Graph API        |
