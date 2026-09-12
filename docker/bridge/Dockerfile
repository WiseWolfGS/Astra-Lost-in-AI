FROM node:24-bookworm-slim@sha256:2fe369e969550cde8e867afc3fe370b260140cab4a23d467074295b42163d553
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY *.mjs ./
USER node
EXPOSE 8765
CMD ["node", "server.mjs"]
