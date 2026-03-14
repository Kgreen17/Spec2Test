Allure report generation

The project produces Allure result files under `allure-results/` (JSON + attachments). To generate and view the HTML report you need the Allure Commandline tool installed.

Options to install Allure CLI

1) Homebrew (macOS) - recommended:

```bash
brew install allure
# generate and open report
allure generate allure-results -o allure-report --clean
allure open allure-report
```

2) Download binary (cross-platform):
- See https://github.com/allure-framework/allure2#download
- Unpack, add to PATH, then run the same `allure generate` commands above.

3) Docker (if you prefer):

```bash
docker run --rm -v $(pwd)/allure-results:/allure-results -v $(pwd)/allure-report:/allure-report frankescobar/allure-docker-service allure generate /allure-results --clean -o /allure-report
```

If `npx allure2` is unavailable (some registries don't host it), use one of the methods above to install Allure CLI.

After generating the report you can serve it via the `allure open` or inspect the static files under `allure-report`.

