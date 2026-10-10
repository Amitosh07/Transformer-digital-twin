FROM ml_runtime
USER root
COPY simulator /build/simulator
RUN python -m pip install --no-cache-dir /build/simulator
RUN useradd --uid 10002 --create-home simulator && mkdir -p /spool && chown simulator /spool
WORKDIR /app
USER simulator
HEALTHCHECK NONE
ENTRYPOINT ["simulator"]
CMD ["--help"]
