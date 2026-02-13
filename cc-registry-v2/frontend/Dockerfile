FROM node:18-alpine

WORKDIR /app

# Set memory limits for Node.js
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies (including dev dependencies for React development)
RUN npm ci --silent --no-audit --no-fund

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start the development server
CMD ["npm", "start"]

