# ── Stage 1 : build de l'application React ──────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Les variables REACT_APP_* sont intégrées (baked) au moment du build
ARG REACT_APP_API_URL
ARG REACT_APP_API_BASE_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL

COPY package.json package-lock.json* ./
RUN npm ci --silent

COPY . .
RUN npm run build

# ── Stage 2 : servir les fichiers statiques avec nginx ───────────────────────
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
