"""Non-deploying test of the exact P01 V2.47.357 isolated preview proxy.
Synthetic local session only; NO network, no real credentials or private data.
"""
from importlib import util
from pathlib import Path
from types import SimpleNamespace

jar = Path("/tmp/p01-v247357-preview/admin-cookies.txt")
jar.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
jar.write_text("# Netscape HTTP Cookie File\nlocalhost\tFALSE\t/\tFALSE\t0\tvfnav_session\tsyntheticpreviewcookie123456789\n")
jar.chmod(0o600)

source = Path(".github/scripts/p01_v247357_preview_proxy.py")
spec = util.spec_from_file_location("vf_preview_proxy", source)
module = util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.SESSION == "vfnav_session=syntheticpreviewcookie123456789"

def target(method, path):
    return module.PreviewProxy.safe_target(SimpleNamespace(command=method, path=path))

allowed = [
    ("GET", "/browser-helper.php"),
    ("HEAD", "/browser-helper.php"),
    ("GET", "/asset.php?file=admin-pages.css&v=2.47.357"),
    ("GET", "/asset.php?file=admin-shell.css&v=2.47.357"),
    ("GET", "/asset.php?file=reference-ui.css&v=2.47.357"),
    ("GET", "/asset.php?file=admin-consolidation.css&v=2.47.357"),
    ("GET", "/asset.php?file=browser-helper.js&v=2.47.357"),
    ("HEAD", "/asset.php?file=browser-helper.js&v=2.47.357"),
    ("GET", "/asset.php?file=VF-logo.svg&v=2.47.357"),
    ("POST", "/api.php?action=plugin_token_regenerate"),
    ("POST", "/api.php?action=plugin_token_revoke"),
]
for method, path in allowed:
    assert target(method,path) == path, (method,path)
print("P01_PREVIEW_CANONICAL_ASSET_ROUTE=PASS")
print("P01_PREVIEW_ALLOWED_SCOPED_TOKEN_ENDPOINTS=PASS")

denied = [
    ("GET", "/setup.php"),
    ("GET", "/manage.php"),
    ("GET", "/api.php?action=plugin_token_revoke"),
    ("POST", "/api.php?action=import_data"),
    ("GET", "/app/bootstrap.php"),
    ("GET", "/asset.php?file=../bootstrap.php&v=2.47.357"),
    ("GET", "/asset.php?file=.env&v=2.47.357"),
    ("GET", "/asset.php?file=config.json&v=2.47.357"),
    ("GET", "/asset.php?file=admin-shell.css&v=2.47.356"),
    ("GET", "/asset.php?file=admin-shell.css"),
    ("GET", "/asset.php?file=admin-shell.css&v=2.47.357&extra=1"),
    ("GET", "/asset.php?file=admin-shell.css&file=admin-pages.css&v=2.47.357"),
    ("GET", "/asset.php?file=admin-shell.css&v=2.47.357&v=2.47.357"),
    ("GET", "/asset.php?file=admin-shell.css&v=2.47.357&broken"),
    ("GET", "/asset.php?file=admin-shell.css&v=2.47.357%0D%0A"),
    ("POST", "/asset.php?file=admin-shell.css&v=2.47.357"),
    ("GET", "/assets/../app/bootstrap.php"),
    ("GET", "/%2e%2e/app/bootstrap.php"),
    ("POST", "/api.php?action=plugin_token_regenerate&broken"),
    ("POST", "/api.php?action=plugin_token_regenerate&extra=1"),
]
for method,path in denied:
    assert target(method,path) is None, (method,path,target(method,path))
print("P01_PREVIEW_PRIVATE_ROUTE_AND_QUERY_FAIL_CLOSED=PASS")

assert source.read_text().find("def safe_target") >= 0
assert source.read_text().find('if path == "/asset.php"') >= 0
print("P01_PREVIEW_PROXY_NO_DEPLOYMENT_POLICY=PASS")
