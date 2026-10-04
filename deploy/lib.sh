# Shared by deploy/deploy.sh and deploy/test-image.sh: naming and building the production image.
# Source it; don't run it. Expects REPO_DIR to be set.

IMAGE="chummer5"

# The image tag for HEAD: "<version>" when HEAD is tagged v<version> (a release), otherwise
# "<version>-dev.<short commit>". See spec/deployment.md's "Versions".
image_tag() {
    local version commit
    version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "${REPO_DIR}/pyproject.toml" | head -1)"
    commit="$(git -C "${REPO_DIR}" rev-parse --short HEAD)"
    if git -C "${REPO_DIR}" tag --points-at HEAD | grep -qx "v${version}"; then
        echo "${version}"
    else
        echo "${version}-dev.${commit}"
    fi
}

# Build ${IMAGE}:$1 from a `git archive` of HEAD -- never the working tree, and never the repo root
# as context (its .dockerignore drops legacy/, which the app reads at runtime).
build_image() {
    local tag="$1" context
    for tool in podman git; do
        command -v "${tool}" >/dev/null || { echo "error: ${tool} not found" >&2; return 1; }
    done
    if ! git -C "${REPO_DIR}" cat-file -e HEAD:deploy/Containerfile 2>/dev/null; then
        echo "error: deploy/Containerfile isn't committed; the image is built from HEAD." >&2
        return 1
    fi
    if [[ -n "$(git -C "${REPO_DIR}" status --porcelain --untracked-files=no)" ]]; then
        echo "warning: uncommitted changes are NOT in the image; it is built from HEAD." >&2
    fi
    context="$(mktemp -d)"
    git -C "${REPO_DIR}" archive HEAD \
        pyproject.toml uv.lock README.md LICENSE NOTICE src legacy/Chummer/data legacy/Chummer/lang \
        deploy/Containerfile | tar -x -C "${context}"
    local status=0
    podman build ${BUILD_PLATFORM:+--platform "${BUILD_PLATFORM}"} \
        --label "org.opencontainers.image.version=${tag}" \
        --label "org.opencontainers.image.revision=$(git -C "${REPO_DIR}" rev-parse HEAD)" \
        -t "${IMAGE}:${tag}" -f "${context}/deploy/Containerfile" "${context}" || status=$?
    rm -rf "${context}"
    return ${status}
}
