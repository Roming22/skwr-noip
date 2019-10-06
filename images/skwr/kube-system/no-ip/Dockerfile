FROM   alpine

#
# Default skwr config
#
RUN addgroup -g 9999 skwr \
    && adduser -G skwr -S -u 9999 skwr
ENV PATH="/opt/module/bin:$PATH"
ENV RESPONSE_FILE="/tmp/no-ip.status"
HEALTHCHECK --start-period=10s --interval=30s --timeout=5s --retries=3 \
    CMD healthcheck.sh || exit 1

#
# Add module and packages
#
RUN apk add bash curl python3

# Add module
COPY module /opt/module
RUN cd /opt/module/bin;\ 
    chmod +x *.py *.sh
ENTRYPOINT ["run.py"]

USER skwr
