// Copies the ZXing barcode reader (WebAssembly) into public/ so it's served from our own
// origin instead of a CDN. Runs before `dev` and `build`; the copy is gitignored.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const source = require.resolve("zxing-wasm/reader/zxing_reader.wasm");
const target = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "wasm");
mkdirSync(target, { recursive: true });
copyFileSync(source, join(target, "zxing_reader.wasm"));
