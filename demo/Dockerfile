FROM php:8.4-apache

RUN apt-get update && apt-get install -y \
        libzip-dev \
        zip \
  && docker-php-ext-install zip

COPY ./index.php /var/www/html/index.php
USER www-data