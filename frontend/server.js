const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const path = require('path');
const fs = require('fs');

const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev, dir: __dirname });
const handle = app.getRequestHandler();
const PORT = process.env.PORT || 3000;

app.prepare().then(() => {
  createServer((req, res) => {
    const parsedUrl = parse(req.url, true);

    // Serve allure-report static files
    if (req.url.startsWith('/allure-report/')) {
      const reportPath = path.join(
        '/Users/kevingreen/PycharmProjects/Spec2Test',
        req.url
      );

      if (fs.existsSync(reportPath)) {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(fs.readFileSync(reportPath));
        return;
      }
    }

    // Handle Next.js routes
    handle(req, res, parsedUrl);
  }).listen(PORT, (err) => {
    if (err) throw err;
    console.log(`✅ Spec2Test Frontend running on http://0.0.0.0:${PORT}`);
  });
});

