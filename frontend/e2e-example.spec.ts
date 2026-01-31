/**
 * Example E2E Test for DokyDoc User Management
 * 
 * To set up Playwright:
 * 1. cd frontend
 * 2. npm install -D @playwright/test
 * 3. npx playwright install
 * 4. Move this file to e2e/ directory
 * 5. Run: npx playwright test
 */

import { test, expect } from '@playwright/test';

// Test configuration
const BASE_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

test.describe('User Management E2E Flow', () => {
  let adminToken: string;

  test.beforeAll(async ({ request }) => {
    // Login via API to get token
    const response = await request.post(`${API_URL}/api/login/access-token`, {
      form: {
        username: 'admin@tenant1.com',
        password: 'Test123!'
      }
    });
    const data = await response.json();
    adminToken = data.access_token;
  });

  test('Complete user invite flow', async ({ page, context }) => {
    // Set auth token in localStorage before page loads
    await context.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, adminToken);

    // Navigate to users page
    await page.goto(`${BASE_URL}/users`);

    // Verify page loaded
    await expect(page.locator('h1')).toHaveText('User Management');

    // Click invite button
    await page.click('text=Invite User');

    // Wait for dialog to open
    await expect(page.locator('text=Invite User').first()).toBeVisible();

    // Fill in user details
    const timestamp = Date.now();
    const testEmail = `testuser${timestamp}@tenant1.com`;
    
    await page.fill('input[id="inviteEmail"]', testEmail);
    await page.check('input[type="checkbox"] ~ span:has-text("Developer")');

    // Submit form
    await page.click('button:has-text("Send Invite")');

    // Wait for success (dialog closes and user appears in list)
    await expect(page.locator(`text=${testEmail}`)).toBeVisible({ timeout: 10000 });

    // Verify user details
    const userRow = page.locator(`tr:has-text("${testEmail}")`);
    await expect(userRow.locator('text=Developer')).toBeVisible();
    await expect(userRow.locator('text=Active')).toBeVisible();
  });

  test('Edit user roles', async ({ page, context }) => {
    // Set auth token
    await context.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, adminToken);

    await page.goto(`${BASE_URL}/users`);

    // Find a developer user
    const userRow = page.locator('tr:has-text("Developer")').first();
    
    // Click actions menu
    await userRow.locator('button[aria-label*="menu"], button:has(svg)').last().click();

    // Click edit roles
    await page.click('text=Edit Roles');

    // Add PM role
    await page.check('input[type="checkbox"] ~ span:has-text("PM")');

    // Save changes
    await page.click('button:has-text("Save Changes")');

    // Verify PM badge appears
    await expect(userRow.locator('text=PM')).toBeVisible({ timeout: 5000 });
  });

  test('Cannot deactivate own account', async ({ page, context }) => {
    // Set auth token
    await context.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, adminToken);

    await page.goto(`${BASE_URL}/users`);

    // Find row with "You" badge (own account)
    const ownUserRow = page.locator('tr:has-text("You")');
    
    // Click actions menu
    await ownUserRow.locator('button').last().click();

    // Deactivate button should be disabled
    const deactivateBtn = page.locator('button:has-text("Deactivate")');
    await expect(deactivateBtn).toBeDisabled();
  });

  test('Search filters users correctly', async ({ page, context }) => {
    await context.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, adminToken);

    await page.goto(`${BASE_URL}/users`);

    // Get initial user count
    const initialRows = await page.locator('tbody tr').count();
    expect(initialRows).toBeGreaterThan(0);

    // Type in search box
    await page.fill('input[placeholder*="Search"]', 'admin');

    // Should show only admin users
    await page.waitForTimeout(500); // Debounce
    const filteredRows = await page.locator('tbody tr').count();
    expect(filteredRows).toBeLessThanOrEqual(initialRows);

    // Clear search
    await page.fill('input[placeholder*="Search"]', '');
    await page.waitForTimeout(500);
    
    // Should show all users again
    const finalRows = await page.locator('tbody tr').count();
    expect(finalRows).toBe(initialRows);
  });

  test('Displays user statistics correctly', async ({ page, context }) => {
    await context.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, adminToken);

    await page.goto(`${BASE_URL}/users`);

    // Check stats cards exist
    await expect(page.locator('text=Total Users').locator('..')).toBeVisible();
    await expect(page.locator('text=Active Users').locator('..')).toBeVisible();
    await expect(page.locator('text=Administrators').locator('..')).toBeVisible();

    // Stats should show numbers
    const totalUsers = await page.locator('text=Total Users').locator('..').locator('text=/\\d+/').textContent();
    expect(parseInt(totalUsers || '0')).toBeGreaterThan(0);
  });
});

test.describe('Multi-tenant Isolation E2E', () => {
  test('Tenant1 cannot see Tenant2 users', async ({ page, context, request }) => {
    // Login as Tenant1 admin
    const tenant1Response = await request.post(`${API_URL}/api/login/access-token`, {
      form: {
        username: 'admin@tenant1.com',
        password: 'Test123!'
      }
    });
    const tenant1Token = (await tenant1Response.json()).access_token;

    await context.addInitScript((token) => {
      localStorage.setItem('accessToken', token);
    }, tenant1Token);

    await page.goto(`${BASE_URL}/users`);

    // Get all user emails visible on page
    const userEmails = await page.locator('tbody tr td:first-child').allTextContents();
    
    // Should see tenant1 users
    expect(userEmails.some(email => email.includes('tenant1.com'))).toBe(true);
    
    // Should NOT see tenant2 users
    expect(userEmails.some(email => email.includes('tenant2.com'))).toBe(false);
  });
});

// Run with:
// npx playwright test
// npx playwright test --ui (interactive mode)
// npx playwright test --headed (see browser)
