FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang-18 llvm-18 libclang-rt-18-dev \
      python3 python3-venv \
      git ca-certificates \
      make \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/clang-18 /usr/bin/clang \
 && ln -sf /usr/bin/llvm-symbolizer-18 /usr/bin/llvm-symbolizer

ENV ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

WORKDIR /work
CMD ["/bin/bash"]