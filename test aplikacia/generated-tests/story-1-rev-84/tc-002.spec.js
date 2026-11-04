// Generated for TC-002 / AC2
const { test, expect } = require('@playwright/test');
const { resetAppState, seedRegisteredUser, seedTasks } = require('../../tests/helpers/app-state');
const fixtures = require('../../test-data.json');

test("TC-002 | Reject an incorrect password", async ({ page }) => {
  await resetAppState(page);
 await seedRegisteredUser(page, fixtures.valid_user);
 await expect(page.getByTestId('login-tab')).toBeVisible();
 await page.getByTestId('login-tab').click();
 await expect(page.getByTestId('login-email')).toBeVisible();
 await expect(page.getByTestId('login-password')).toBeVisible();
 await page.getByTestId('login-email').fill(fixtures.valid_user.email);
 await page.getByTestId('login-password').fill(`${fixtures.valid_user.password}wrong`);
 await page.getByTestId('login-submit').click();
 await expect(page.getByTestId('login-global-error')).toHaveText('Invalid email or password');
 await expect(page.getByTestId('logout-button')).toBeHidden();
});
