FROM rust:slim-bookworm AS build

# Install dependencies
RUN apt update && apt install -y --no-install-recommends \
    ca-certificates \
    git

# Build drcov-merge
WORKDIR /build
RUN git clone --recursive "https://github.com/airbus-seclab/afl-cov-fast.git" \
    && cd afl-cov-fast/drcov-merge \
    && cargo build --release

FROM debian:bookworm-slim

VOLUME ["/workdir", "/project"]
WORKDIR /workdir

# Install dependencies
RUN apt update && apt install -y --no-install-recommends \
    python3 \
    python3-tqdm \
    lcov \
    llvm-16 \
    llvm-16-tools && \
    rm -rf /var/lib/apt/lists/*

# Copy binaries from build stage
COPY --from=build /build/afl-cov-fast /afl-cov-fast
COPY --from=build /build/afl-cov-fast/drcov-merge/target/release/drcov-merge /usr/bin/drcov-merge

# Make sure the LLVM directory is in the path so that we can use the tool names
# directly instead of aliases (e.g. llvm-profdata instead of llvm-profdata-16)
ENV PATH="/usr/lib/llvm-16/bin:$PATH"

# Open shell
ENTRYPOINT ["/bin/bash"]
CMD []
