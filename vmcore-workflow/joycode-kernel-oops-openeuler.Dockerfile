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

RUN mkdir -p /root/.joycode/skills /opt/skills /usr/local/lib/kernel-analysis

# Fetch the published skill during image construction. This keeps the
# development-node deployment bundle small while ensuring the skill matches
# the pushed main branch.
RUN git clone --depth 1 --branch main https://github.com/qingyuppp/linux-kernel-analysis.git /tmp/linux-kernel-analysis && \
    cp -a /tmp/linux-kernel-analysis/linux-kernel-oops /opt/skills/linux-kernel-oops && \
    cp -a /tmp/linux-kernel-analysis/linux-kernel-oops /root/.joycode/skills/linux-kernel-oops && \
    python3 -m pip install --no-cache-dir /opt/skills/linux-kernel-oops/cli && \
    cra --help >/dev/null && \
    rm -rf /tmp/linux-kernel-analysis
COPY classify_evidence.py /usr/local/lib/kernel-analysis/classify_evidence.py

COPY joycode-entrypoint.sh /usr/local/bin/joycode-entrypoint
COPY analyze-vmcore /usr/local/bin/analyze-vmcore
COPY crash-query /usr/local/bin/crash-query
COPY run-vmcore-analysis /usr/local/bin/run-vmcore-analysis
RUN chmod +x /usr/local/bin/joycode-entrypoint /usr/local/bin/analyze-vmcore /usr/local/bin/crash-query /usr/local/bin/run-vmcore-analysis

# Convention paths: Jenkins bind-mounts inputs into /data/input/* and
# collects results from /data/output. /data/work is image-internal scratch
# for the analyze-vmcore script (rpm unpack, etc.).
RUN mkdir -p /data/input /data/output /data/work

WORKDIR /data

ENTRYPOINT ["/usr/local/bin/joycode-entrypoint"]
CMD ["/bin/bash"]
