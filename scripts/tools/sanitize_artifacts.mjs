/* eslint-disable no-console */
import fs from "node:fs";
import path from "node:path";
const ROOT = process.env.ARTIFACTS_DIR || "scripts/artifacts";
const redactions = [
  { name: "email", rx: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, repl: "[REDACTED:email]" },
  { name: "phone", rx: /\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b/g, repl: "[REDACTED:phone]" },
  { name: "bearer", rx: /(Authorization:\s*Bearer\s+)[A-Za-z0-9\-._~+/]+=*/gi, repl: "[REDACTED:token]" },
  { name: "apikey", rx: /(api[_-]?key["']?\s*[:=]\s*["']?)[A-Za-z0-9\-._~+/]+=*/gi, repl: "[REDACTED:key]" },
];
function sanitize(t){ return redactions.reduce((acc, r) => acc.replace(r.rx, r.repl), t); }
function walk(dir, files=[]){
  for (const e of fs.readdirSync(dir, { withFileTypes:true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, files);
    else if (e.isFile() && /\.(log|json|txt|md)$/i.test(e.name)) files.push(p);
  } return files;
}
(function main(){
  if (!fs.existsSync(ROOT)) { console.log(`[sanitize_artifacts] no dir: ${ROOT}`); process.exit(0); }
  const files = walk(ROOT);
  for (const f of files) {
    const t = fs.readFileSync(f, "utf8"); const s = sanitize(t);
    if (s !== t) fs.writeFileSync(f, s);
  }
  console.log(`[sanitize_artifacts] sanitized ${files.length} files under ${ROOT}`);
})();
