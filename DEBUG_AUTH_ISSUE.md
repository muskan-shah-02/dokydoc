# 🔴 Authorization Issue Debug Guide

## What's Happening

Your logs show:
```
✅ 15:37:28 - GET /api/v1/users/me/permissions - 200 (SUCCESS)
❌ 15:37:43 - GET /api/v1/users/ - 401 (FAIL - 15 seconds later!)
❌ 15:38:12 - POST /api/v1/users/invite - 401 (FAIL)
```

**Same token, same browser session, but some endpoints work and others don't!**

## Root Cause

**Browser localStorage token issue + React Strict Mode double-rendering**

## Immediate Fix (TRY THIS FIRST)

1. **Open Browser DevTools** (F12)
2. **Go to Application tab → Local Storage**
3. **Check `accessToken` value** - copy it
4. **Go to Console tab**
5. **Run these commands:**
   ```javascript
   // Check if token exists
   console.log('Token:', localStorage.getItem('accessToken'));
   
   // Check token expiration
   const token = localStorage.getItem('accessToken');
   if (token) {
     const payload = JSON.parse(atob(token.split('.')[1]));
     console.log('Token expires:', new Date(payload.exp * 1000));
     console.log('Current time:', new Date());
     console.log('Token expired?', payload.exp * 1000 < Date.now());
   }
   ```

6. **If token is expired, logout and login again**
7. **Or manually refresh by running:**
   ```javascript
   localStorage.clear();
   window.location.href = '/login';
   ```

## Why This Happens

1. **Token expires** but frontend doesn't detect it
2. **Some endpoints cached** (like /users/me/permissions)
3. **Other endpoints not cached** (like /users/) so they fail
4. **React Strict Mode** causes double API calls (see two OPTIONS requests)

## Permanent Fix (I'll Implement)

1. Auto-detect token expiration
2. Auto-refresh tokens before expiry
3. Handle 401 errors by redirecting to login
4. Fix React Strict Mode double-rendering
