FROM node:20-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the app
COPY . .

# The API URL must be available at BUILD time because Next.js
# inlines NEXT_PUBLIC_* vars and pre-renders pages.
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

# Build the production bundle
RUN npm run build

EXPOSE 3000

# Start the production server
CMD ["npm", "run", "start"]
