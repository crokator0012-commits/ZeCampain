/* Runs as Vercel's build step (see vercel.json). Substitutes the real GitHub
   token — read from the GH_TOKEN environment variable set in the Vercel
   project dashboard, never committed to git — into index.html's placeholder
   right before the page is served. The repo's own copy of index.html always
   keeps the placeholder; only Vercel's ephemeral build output has the real
   token embedded. */
const fs = require("fs");
const path = require("path");

const PLACEHOLDER = "__GH_TOKEN_PLACEHOLDER__";
const token = process.env.GH_TOKEN;

if (!token) {
  console.error("GH_TOKEN environment variable is not set in this Vercel project — aborting build.");
  process.exit(1);
}

const file = path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(file, "utf8");

const occurrences = html.split(PLACEHOLDER).length - 1;
if (occurrences !== 1) {
  console.error(`Expected exactly 1 occurrence of ${PLACEHOLDER} in index.html, found ${occurrences} — aborting build.`);
  process.exit(1);
}

fs.writeFileSync(file, html.split(PLACEHOLDER).join(token), "utf8");
console.log("GH_TOKEN injected into index.html for this build.");
