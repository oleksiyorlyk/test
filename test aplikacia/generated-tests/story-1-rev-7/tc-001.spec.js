// Generated for TC-001 / AC1
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-001 | Log in with correct email and password", async ({ page }) => {
  await resetAppState(page);
 await seedRegisteredUser(page, fixtures.valid_user);
 await page.getByTestId('login-tab').click();
 await page.getByTestId('login-email').fill(fixtures.valid_user.email);
 await page.getByTestId('login-password').fill(fixtures.valid_user.password);
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('greeting-title')).toBeVisible();
 await expect(page.getByTestId('logout-button')).toBeVisible();
});
