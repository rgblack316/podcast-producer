FROM node:20-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
# Strip preview-only dev tooling so the build has no external platform dependencies
RUN node -e "const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json'));for(const k of Object.keys(p.devDependencies||{}))if(k.startsWith('@emergentbase'))delete p.devDependencies[k];delete p.packageManager;fs.writeFileSync('package.json',JSON.stringify(p,null,2))" \
    && yarn install --network-timeout 600000
COPY . .
ARG REACT_APP_BACKEND_URL=""
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL \
    GENERATE_SOURCEMAP=false \
    DISABLE_EMERGENT_OVERLAY=true
RUN yarn build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
