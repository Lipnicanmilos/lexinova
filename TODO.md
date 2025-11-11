# TODO: Fix Dark Mode Not Persisting After Logout/Login

## Completed Tasks
- [x] Analyze the issue: Dark mode setting not applied after logout and re-login
- [x] Search for dark_mode usage in the codebase
- [x] Read relevant files: user model, main.py, dashboard.html, profile.html
- [x] Identify the problem: Google OAuth callback was missing dark_mode in session
- [x] Fix Google OAuth callback to include dark_mode in session_user dictionary
- [x] Verify the fix: Regular login already includes dark_mode, Google login now does too

## Summary
The issue was that when users logged in via Google OAuth, the session dictionary did not include the `dark_mode` field, even though it was stored in the database. This caused the frontend to not apply dark mode after login. The fix was to add `"dark_mode": user.dark_mode` to the `session_user` dictionary in the Google OAuth callback.

Regular login already included this field, so the issue was specific to Google authentication.
