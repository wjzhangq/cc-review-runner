from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    BUILD_VERSION = _pkg_version("cc-review-runner")
except PackageNotFoundError:
    BUILD_VERSION = "0.0.0+dev"
