FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY app1.html /usr/share/nginx/html/app1.html
COPY index.html /usr/share/nginx/html/index.html
COPY app2.html /usr/share/nginx/html/app2.html
COPY app3.html /usr/share/nginx/html/app3.html
