// Generated for TC-003 / AC3
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-003 | Empty email field shows the required-field message", async ({ page }) => {
  await resetAppState(page);
 await seedRegisteredUser(page, fixtures.valid_user);
 await expect(page.getByTestId('login-tab')).toBeVisible();
 await page.getByTestId('login-tab').click();
 await expect(page.getByTestId('login-email')).toBeVisible();
 await expect(page.getByTestId('login-password')).toBeVisible();
 await page.getByTestId('login-password').fill(fixtures.valid_user.password);
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('login-email-error')).toHaveText('This field is required');
 await expect(page.getByTestId('logout-button')).toBeHidden();
});
