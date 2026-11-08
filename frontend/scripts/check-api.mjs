import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const directory = mkdtempSync(join(tmpdir(), "testforge-api-"));
try {
  const output = join(directory, "generated.ts");
  execFileSync(
    process.execPath,
    [
      "node_modules/openapi-typescript/bin/cli.js",
      "../contracts/openapi.json",
      "-o",
      output,
    ],
    { stdio: "pipe" },
  );
  const normalize = (value) => value.replaceAll("\r\n", "\n");
  if (
    normalize(readFileSync(output, "utf8")) !==
    normalize(readFileSync("src/shared/api/generated.ts", "utf8"))
  ) {
    throw new Error("API types are out of date. Run npm run api:generate.");
  }
  console.log("Generated API types match OpenAPI.");
} finally {
  rmSync(directory, { recursive: true, force: true });
}
