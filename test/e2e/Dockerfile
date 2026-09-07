# Playwright test runner image. Kept isolated from the production Dockerfile
# so browser dependencies never ship in the app image (PLAN.md sec 12).
FROM mcr.microsoft.com/playwright:v1.56.0-jammy

# The database-persistence test restarts the app service via the host's
# docker socket (bind-mounted by docker-compose.test.yml), so the docker CLI
# needs to be present in this image.
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /e2e

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

CMD ["npx", "playwright", "test"]
