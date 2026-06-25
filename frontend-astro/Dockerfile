# ---- Frontend (Astro) Dockerfile ----
# Build the Astro project and serve the static files with a minimal web server.

# ---------- Build stage ----------
FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies (using npm, pnpm could be used as well)
COPY package.json package-lock.json* pnpm-lock.yaml* ./
RUN npm ci

# Copy source code and build
COPY . .
RUN npm run build   # produces ./dist

# ---------- Runtime stage ----------
FROM node:20-alpine AS runner
WORKDIR /app

# Serve static files using a tiny http server (serve)
RUN npm install -g serve
COPY --from=builder /app/dist ./dist

EXPOSE 4173
CMD ["serve", "-s", "dist", "-l", "4173"]
