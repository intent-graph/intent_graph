// Minimal static file server for the Playwright harness.
// Usage: node staticServer.mjs <port> <root>
//
// No external deps. Serves files under <root> with conservative MIME types.
// 404s on missing files; 403s on directory traversal attempts.

import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve, sep } from 'node:path';

const [, , portArg, rootArg] = process.argv;
if (!portArg || !rootArg) {
  console.error('Usage: node staticServer.mjs <port> <root>');
  process.exit(2);
}
const PORT = Number(portArg);
const ROOT = resolve(rootArg);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.yaml': 'text/yaml; charset=utf-8',
  '.yml': 'text/yaml; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon'
};

const server = http.createServer(async (req, res) => {
  const url = decodeURIComponent((req.url ?? '/').split('?')[0]);
  // Normalise then re-resolve relative to ROOT; reject if it escapes ROOT.
  const safePath = normalize(url).replace(/^([\\/]+)/, '');
  const absPath = resolve(join(ROOT, safePath));
  if (!absPath.startsWith(ROOT + sep) && absPath !== ROOT) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }
  try {
    const st = await stat(absPath);
    if (st.isDirectory()) {
      const indexPath = join(absPath, 'index.html');
      const buf = await readFile(indexPath);
      res.writeHead(200, { 'Content-Type': MIME['.html'] });
      res.end(buf);
      return;
    }
    const buf = await readFile(absPath);
    res.writeHead(200, {
      'Content-Type': MIME[extname(absPath)] ?? 'application/octet-stream',
      'Cache-Control': 'no-store'
    });
    res.end(buf);
  } catch (err) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end(`Not found: ${url}`);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[staticServer] listening on http://127.0.0.1:${PORT} root=${ROOT}`);
});
