// Copies browser-side engines from node_modules into public/ so they're served from our own
// origin, not a CDN: the ZXing barcode reader, and Tesseract.js (OCR for label photos: its
// worker, the LSTM builds of its core, and the compact English model). Runs before `dev` and
// `build`; the copies are gitignored.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const publicDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public");

function copy(source, target) {
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
}

copy(
  require.resolve("zxing-wasm/reader/zxing_reader.wasm"),
  join(publicDir, "wasm", "zxing_reader.wasm"),
);

const tesseract = dirname(require.resolve("tesseract.js/package.json"));
copy(join(tesseract, "dist", "worker.min.js"), join(publicDir, "ocr", "worker.min.js"));
const core = dirname(
  createRequire(join(tesseract, "package.json")).resolve("tesseract.js-core/package.json"),
);
for (const build of [
  "tesseract-core-lstm",
  "tesseract-core-simd-lstm",
  "tesseract-core-relaxedsimd-lstm",
]) {
  copy(join(core, `${build}.wasm.js`), join(publicDir, "ocr", "core", `${build}.wasm.js`));
}
const english = dirname(require.resolve("@tesseract.js-data/eng/package.json"));
copy(
  join(english, "4.0.0_best_int", "eng.traineddata.gz"),
  join(publicDir, "ocr", "lang", "eng.traineddata.gz"),
);
