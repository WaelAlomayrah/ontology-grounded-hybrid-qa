FROM node:22.12-alpine AS build
WORKDIR /app
COPY package*.json tsconfig*.json vite.config.ts index.html ./
RUN npm install
COPY src src
RUN npm run build
FROM nginx:1.27.3-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN mkdir -p /var/cache/nginx /run && chown -R nginx:nginx /var/cache/nginx /run
USER nginx
EXPOSE 8080
