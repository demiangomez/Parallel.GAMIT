FROM node:22 AS build

WORKDIR /app
COPY . /app
COPY .env /app/.env

COPY package*.json /app/

RUN npm ci
RUN npm run build

FROM nginx:latest

# Install Tini
RUN apt-get update && apt-get install -y tini

COPY --from=build /app/dist /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf

# Configure tini as the init system
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["nginx", "-g", "daemon off;"]