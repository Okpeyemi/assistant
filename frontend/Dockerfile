FROM node:20-alpine

WORKDIR /app

# Copier package.json et installer les dépendances
COPY package.json package-lock.json ./
RUN npm ci

# Copier tout le code source et builder
COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
