ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python + pip deps
RUN apk add --no-cache python3 py3-pip py3-pillow
RUN pip3 install flask --break-system-packages

# Copy app
WORKDIR /app
COPY app/ /app/

EXPOSE 5050
CMD ["python3", "app.py"]
