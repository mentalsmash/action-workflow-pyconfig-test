ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

RUN set -ex; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      wget \
      jq \
      fzf \
      ca-certificates \
      locales \
      python3 \
      python3-termcolor \
      python3-tabulate \
      python3-yaml \
      bsdextrautils;  \
    locale-gen en_US en_US.UTF-8; \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8; \
    # Enable the GitHub CLI apt repository
    mkdir -p -m 755 /etc/apt/keyrings; \
    wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
      tee /etc/apt/keyrings/githubcli-archive-keyring.gpg; \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list; \
    apt-get update; \
    # Install requried tools
    apt-get install -y --no-install-recommends \
      gh; \
    apt-get clean

ENV LANG en_US.UTF-8
