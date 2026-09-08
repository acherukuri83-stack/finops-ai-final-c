# Multi-stage. `dev` target = Vite dev server (compose); default = static build on Caddy.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci || npm install

FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM deps AS build
COPY . .
# Railway passes service variables as build args; VITE_API_BASE must point at the
# public URL of the ai-platform service (e.g. https://ai-platform-xxxx.up.railway.app).
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 8080
