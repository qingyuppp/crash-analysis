FROM hub.jdcloud.com/baseimages/openeuler:22.03lts-amd64-depends-tools-v20250926

RUN dnf makecache && \
    dnf install -y \
    ca-certificates curl git python3 python3-pip \
    crash gdb binutils elfutils xz cpio rpm-build \
    && dnf clean all

RUN curl -fsSL https://nodejs.org/dist/v22.11.0/node-v22.11.0-linux-x64.tar.xz -o /tmp/node.tar.xz && \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 && \
    rm -f /tmp/node.tar.xz && \
    node --version && \
    npm --version

RUN npm install -g @joycode/joycode-cli --registry=http://registry.m.jd.com

RUN mkdir -p /root/.joycode/skills /opt/skills

COPY skill/crash-analysis /opt/skills/crash-analysis
COPY skill/crash-analysis /root/.joycode/skills/crash-analysis
COPY cli /opt/crash-analysis/cli
RUN python3 -m pip install --no-cache-dir /opt/crash-analysis/cli && cra --help >/dev/null

COPY runtime/joycode-entrypoint.sh /usr/local/bin/joycode-entrypoint
COPY runtime/run-vmcore-analysis /usr/local/bin/run-vmcore-analysis
RUN chmod +x /usr/local/bin/joycode-entrypoint /usr/local/bin/run-vmcore-analysis

# Convention paths: Jenkins bind-mounts inputs into /data/input/* and
# collects results from /data/output. /data/work is image-internal scratch
# for CLI collection and diagnosis actions.
RUN mkdir -p /data/input /data/output /data/work

WORKDIR /data

ENTRYPOINT ["/usr/local/bin/joycode-entrypoint"]
CMD ["/bin/bash"]
