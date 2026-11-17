FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY shared ./shared
COPY api ./api
COPY server ./server
ENV QUERY_API_HOST=0.0.0.0 QUERY_API_PORT=8788
USER node
EXPOSE 8788
CMD ["node", "server/query-server.js"]
