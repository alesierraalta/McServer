
FROM eclipse-temurin:21-jdk
RUN apt-get update && apt-get install -y curl iproute2 procps jq ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /server
RUN set -eux; \
    INSTALLER_VERSION="$(curl -fsSL https://meta.fabricmc.net/v2/versions/installer | jq -r '.[0].version')"; \
    LOADER_VERSION="$(curl -fsSL https://meta.fabricmc.net/v2/versions/loader/1.21.10 | jq -r '.[0].loader.version')"; \
    curl -fL -o fabric-installer.jar "https://maven.fabricmc.net/net/fabricmc/fabric-installer/${INSTALLER_VERSION}/fabric-installer-${INSTALLER_VERSION}.jar"; \
    java -jar fabric-installer.jar server -mcversion "1.21.10" -loader "${LOADER_VERSION}" -downloadMinecraft -dir /server; \
    mkdir -p /server/mods /server/world /server/logs && \
    chown -R 1000:1000 /server
USER 1000:1000
RUN printf '#!/usr/bin/env sh\necho "eula=true" > /server/eula.txt\nexec java -Xms2G -Xmx${MAX_RAM:-4}G \\\n  -XX:+UseZGC -XX:+ZGenerational \\\n  -XX:+UnlockDiagnosticVMOptions -XX:+UnlockExperimentalVMOptions \\\n  -XX:+ParallelRefProcEnabled -XX:+AlwaysPreTouch \\\n  -XX:MaxGCPauseMillis=50 \\\n  -XX:+UseNUMA \\\n  -jar fabric-server-launch.jar nogui\n' > /server/start.sh && chmod +x /server/start.sh
EXPOSE 25565 25575
CMD ["/server/start.sh"]
