"""Backend auto-detection: prefer local when up, fall back to deployed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import push_leads_to_api as push

ok = True


def check(label, condition):
    global ok
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    ok = ok and bool(condition)


check("default target is auto", push.DEFAULT_TARGET == "auto")
check("local URL is port 5023", push.TARGETS["local"] == "http://localhost:5023")
check("deployed URL is the Azure host",
      push.TARGETS["deployed"] == "https://apiclientalio.azurewebsites.net")
check("local is probed before deployed",
      push.AUTO_ORDER.index("local") < push.AUTO_ORDER.index("deployed"))

original = push.is_reachable

# 1) Local HTTP up -> local wins, deployed never contacted.
push.is_reachable = lambda url, timeout=3.0: url == push.TARGETS["local"]
label, url = push.resolve_auto()
check("uses local when local is up", url == push.TARGETS["local"])
check("labelled local", label == "local")

# 2) Only the HTTPS local port up -> still treated as local.
push.is_reachable = lambda url, timeout=3.0: url == push.TARGETS["local-https"]
label, url = push.resolve_auto()
check("uses local-https when only that is up", url == push.TARGETS["local-https"])

# 3) Nothing local up -> deployed, never a silent no-op.
push.is_reachable = lambda url, timeout=3.0: False
label, url = push.resolve_auto()
check("falls back to deployed", url == push.TARGETS["deployed"])

# 4) Only deployed up -> deployed.
push.is_reachable = lambda url, timeout=3.0: url == push.TARGETS["deployed"]
label, url = push.resolve_auto()
check("uses deployed when only it is up", url == push.TARGETS["deployed"])

# 5) An explicit --target must bypass detection entirely.
push.is_reachable = lambda url, timeout=3.0: url == push.TARGETS["local"]


class Args:
    target = [["deployed"]]
    base_url = None


check("explicit --target overrides auto", push.resolve_targets(Args()) == [("deployed", push.TARGETS["deployed"])])


class ArgsUrl:
    target = None
    base_url = "https://custom.example"


check("--base-url overrides auto",
      push.resolve_targets(ArgsUrl()) == [("custom.example", "https://custom.example")])

# 6) auto must resolve to exactly one target.
push.is_reachable = original
resolved = push.resolve_targets(Args.__mro__ and type("A", (), {"target": None, "base_url": None})())
check("auto resolves to a single target", len(resolved) == 1)

print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
raise SystemExit(0 if ok else 1)