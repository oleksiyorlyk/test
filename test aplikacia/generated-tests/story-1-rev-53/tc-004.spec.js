// Generated for TC-004 / AC3
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-004 | Require the password when the password field is empty", async ({ page }) => {
  await resetAppState(page);
 await page.getByTestId('login-tab').click();
 await page.getByTestId('login-email').fill('test.user@yourtask.local');
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('login-password-error')).toHaveText('This field is required');
 await expect(page.getByTestId('login-submit')).toBeVisible();
});
