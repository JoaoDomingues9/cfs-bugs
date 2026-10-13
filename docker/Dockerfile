# Imagem de reprodução dos bugs do cFS: GCC 13 + Clang 18 (= imagem piloto-cfs:0.3 do piloto).
# Base fixada por digest (índice multi-arquitetura: amd64 e arm64).
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG DEBIAN_FRONTEND=noninteractive
# DNS só para a build, se a rede local bloquear o DNS por omissão do Docker:
# --build-arg BUILD_DNS=<servidor>. O /etc/resolv.conf é montado pelo Docker em cada RUN, por
# isso esta alteração não fica na imagem.
ARG BUILD_DNS=

# clang-18 e llvm-18 são as versões por omissão do Ubuntu 24.04.
# libclang-rt-18-dev: runtime de profiling do Clang (--coverage).
# Os pacotes apt não estão fixados por versão: as versões instaladas são registadas em cada
# corrida (ver .github/workflows/reproduzir.yml) e comparadas com as da imagem de referência:
# gcc-13 13.3.0-6ubuntu2~24.04.1, clang-18 1:18.1.3-1ubuntu1, cmake 3.28.3-1build7, lcov 2.0-4ubuntu2.
RUN if [ -n "$BUILD_DNS" ]; then echo "nameserver $BUILD_DNS" > /etc/resolv.conf; fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential cmake git lcov python3 \
      clang-18 llvm-18 libclang-rt-18-dev \
      ca-certificates file xxd jq \
 && rm -rf /var/lib/apt/lists/*

# As builds correm com --user "$(id -u):$(id -g)", uid sem entrada no /etc/passwd da imagem.
# HOME gravável para o git/cmake não se queixarem.
ENV HOME=/tmp
WORKDIR /w
