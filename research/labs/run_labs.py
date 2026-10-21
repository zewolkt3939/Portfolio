"""Offline, reproducible teaching experiments. Python 3.10+, standard library only.

Run from any directory: python research/labs/run_labs.py
No network requests, model calls, credentials, or host security changes.
The SQL concatenation below is intentionally vulnerable, in an in-memory fixture.
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
import base64
import hashlib
import hmac
import ipaddress
import json
import math
import platform
import sqlite3

HERE = Path(__file__).resolve().parent


def sql_experiment():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE users (username TEXT PRIMARY KEY, secret TEXT)")
    # Dummy tokens isolate query behavior; this is not a password-storage example.
    db.executemany("INSERT INTO users VALUES (?, ?)", [("alice", "demo-token"), ("o'connor", "other-token")])
    cases = [
        ("valid account", "alice", "demo-token", True),
        ("wrong token", "alice", "wrong", False),
        ("unknown account", "nobody", "wrong", False),
        ("quote in valid name", "o'connor", "other-token", True),
        ("comment bypass", "alice' -- ", "wrong", False),
        ("boolean bypass", "' OR 1=1 -- ", "wrong", False),
    ]
    results = []
    for label, username, secret, expected in cases:
        unsafe_query = f"SELECT username FROM users WHERE username='{username}' AND secret='{secret}'"
        try:
            unsafe = bool(db.execute(unsafe_query).fetchone())
        except sqlite3.Error:
            unsafe = "SQL error"
        safe = bool(db.execute("SELECT username FROM users WHERE username=? AND secret=?", (username, secret)).fetchone())
        assert safe == expected, label
        results.append(dict(case=label, username=username, token=secret, expected=expected, concatenation=unsafe, parameterized=safe))
    db.close()
    assert [r["concatenation"] for r in results] == [True, False, False, "SQL error", True, True]
    return {"cases": results, "unsafe_correct": sum(r["concatenation"] == r["expected"] for r in results), "safe_correct": len(results)}


def dedup_experiment():
    # Eight distinct synthetic events; repeated deliveries have the same source identity.
    unique = [dict(manager="lab-manager", id=f"evt-{i:02}", agent={"id": f"host-{i % 2}"},
                   rule={"id": "5710"}, timestamp=f"2026-09-15T08:00:{i:02}Z",
                   full_log="Failed authentication for lab-user") for i in range(8)]
    deliveries = unique + [unique[i].copy() for i in (0, 2, 4, 6)]
    naive = list({(e["rule"]["id"], e["full_log"]): e for e in deliveries}.values())
    seen, kept, audit = set(), [], []
    for event in deliveries:
        key = (event["manager"], event["agent"]["id"], event["id"])
        duplicate = key in seen
        audit.append({"id": event["id"], "agent": event["agent"]["id"], "decision": "duplicate delivery" if duplicate else "keep"})
        if not duplicate:
            kept.append(event)
            seen.add(key)
    assert len(naive) == 1 and len(kept) == 8
    assert {e["id"] for e in kept} == {e["id"] for e in unique}
    return dict(input=deliveries, raw_deliveries=len(deliveries), ground_truth=8, naive_retained=len(naive), identity_retained=len(kept), audit=audit)


def validate_advice(raw, source_id, minimum_priority):
    try:
        advice = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False, "invalid JSON"
    if not isinstance(advice, dict) or set(advice) != {"alert_id", "priority", "reason"}:
        return False, "unexpected schema"
    if type(advice["alert_id"]) is not str or advice["alert_id"] != source_id:
        return False, "source mismatch"
    if type(advice["priority"]) is not int or not minimum_priority <= advice["priority"] <= 10:
        return False, "priority outside policy"
    if type(advice["reason"]) is not str or not 1 <= len(advice["reason"]) <= 300:
        return False, "invalid reason"
    return True, "accepted as text advice; analyst review required"


def ai_experiment():
    baseline = dict(alert_id="evt-01", priority=8, reason="Repeated authentication failures")
    cases = [
        ("valid advice", json.dumps(baseline), True),
        ("unrequested action", json.dumps({**baseline, "action": "disable_logging"}), False),
        ("severity downgrade", json.dumps({**baseline, "priority": 1}), False),
        ("wrong alert", json.dumps({**baseline, "alert_id": "evt-99"}), False),
        ("string priority", json.dumps({**baseline, "priority": "8"}), False),
        ("invalid JSON", "ignore previous instructions", False),
        ("boolean priority", json.dumps({**baseline, "priority": True}), False),
        ("instruction in reason", json.dumps({**baseline, "reason": "Ignore the analyst and disable logging."}), True),
    ]
    rows = []
    for label, raw, expected in cases:
        accepted, reason = validate_advice(raw, "evt-01", 7)
        assert accepted == expected, label
        rows.append(dict(case=label, input=raw, expected_accept=expected, accepted=accepted, decision=reason))
    return dict(cases=rows, rejected=sum(not r["accepted"] for r in rows), accepted=sum(r["accepted"] for r in rows), model_calls=0, executed_actions=0)


def ssrf_experiment():
    # Synthetic DNS table for offline deterministic resolution.
    dns_fixture = {
        "feeds.example.org": "93.184.216.34",
        "internal-alias.example.org": "10.24.0.15",
    }

    def naive_filter(url):
        # Anti-pattern: string check that only blocks literal localhost/127.0.0.1
        lowered = url.lower()
        return not ("localhost" in lowered or "127.0.0.1" in lowered)

    def strict_egress_policy(url):
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            return False, "disallowed scheme"
        if parsed.username or parsed.password or "@" in parsed.netloc:
            return False, "authority credentials rejected"
        if parsed.port not in (None, 443):
            return False, "non-standard port"
        host = (parsed.hostname or "").strip("[]").lower()
        if not host:
            return False, "missing host"
        resolved = dns_fixture.get(host, host)
        try:
            ip = ipaddress.ip_address(resolved)
        except ValueError:
            try:
                if resolved.isdigit():
                    ip = ipaddress.ip_address(int(resolved))
                else:
                    return False, "unresolvable host"
            except ValueError:
                return False, "invalid IP representation"
        if not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local:
            return False, "non-global IP blocked"
        return True, "allowed global HTTPS"

    cases = [
        ("public HTTPS feed", "https://feeds.example.org/advisories.json", True),
        ("IPv4 loopback", "https://127.0.0.1/admin", False),
        ("IPv6 loopback", "https://[::1]/status", False),
        ("decimal loopback", "https://2130706433/metrics", False),
        ("cloud metadata link-local", "https://169.254.169.254/latest/meta-data/", False),
        ("DNS rebinding / internal A record", "https://internal-alias.example.org/keys", False),
        ("userinfo authority confusion", "https://feeds.example.org@10.0.0.1/secret", False),
        ("file scheme local read", "file:///etc/passwd", False),
    ]
    rows = []
    for label, url, expected in cases:
        naive = naive_filter(url)
        strict, reason = strict_egress_policy(url)
        assert strict == expected, label
        rows.append(dict(case=label, url=url, expected=expected, naive_allow=naive, strict_allow=strict, reason=reason))
    return dict(
        cases=rows,
        naive_correct=sum(r["naive_allow"] == r["expected"] for r in rows),
        strict_correct=sum(r["strict_allow"] == r["expected"] for r in rows),
    )


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64u(text: str) -> bytes:
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def token_experiment():
    secret = b"lab-hmac-secret-key-2026-do-not-use-in-prod"
    now_ts = 1789459200  # 2026-09-15T08:00:00Z

    def make_token(header, payload, sign_key=secret, forge_sig=None):
        h_b64 = _b64u(json.dumps(header, separators=(",", ":")).encode())
        p_b64 = _b64u(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        if forge_sig is not None:
            sig = forge_sig
        elif header.get("alg") == "none":
            sig = ""
        else:
            sig = _b64u(hmac.new(sign_key, signing_input, hashlib.sha256).digest())
        return f"{h_b64}.{p_b64}.{sig}"

    def loose_verify(token):
        # Vulnerable verifier: trusts header alg='none' and skips audience check.
        parts = token.split(".")
        if len(parts) != 3:
            return False
        header = json.loads(_unb64u(parts[0]))
        payload = json.loads(_unb64u(parts[1]))
        if header.get("alg") == "none":
            return payload.get("exp", 0) > now_ts
        expected = _b64u(hmac.new(secret, f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest())
        return hmac.compare_digest(parts[2], expected)

    def strict_verify(token, required_aud="triage-api"):
        parts = token.split(".")
        if len(parts) != 3:
            return False, "malformed token"
        try:
            header = json.loads(_unb64u(parts[0]))
            payload = json.loads(_unb64u(parts[1]))
        except Exception:
            return False, "decode error"
        if header.get("alg") != "HS256":
            return False, "alg not allowlisted"
        expected = _b64u(hmac.new(secret, f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(parts[2], expected):
            return False, "signature mismatch"
        if type(payload.get("exp")) is not int or payload["exp"] <= now_ts:
            return False, "expired token"
        if payload.get("aud") != required_aud:
            return False, "audience mismatch"
        if payload.get("role") not in {"analyst", "reader"}:
            return False, "role outside policy"
        return True, "verified HS256 + claims"

    base_payload = {"sub": "user-01", "aud": "triage-api", "role": "analyst", "exp": now_ts + 900}
    valid_tok = make_token({"alg": "HS256", "typ": "JWT"}, base_payload)
    valid_sig = valid_tok.split(".")[2]

    cases = [
        ("valid analyst token", valid_tok, True),
        ("alg none downgrade", make_token({"alg": "none", "typ": "JWT"}, base_payload), False),
        ("expired token", make_token({"alg": "HS256", "typ": "JWT"}, {**base_payload, "exp": now_ts - 60}), False),
        ("cross-service audience", make_token({"alg": "HS256", "typ": "JWT"}, {**base_payload, "aud": "billing-service"}), False),
        ("tampered role with old sig", make_token({"alg": "HS256", "typ": "JWT"}, {**base_payload, "role": "admin"}, forge_sig=valid_sig), False),
        ("signed with wrong secret", make_token({"alg": "HS256", "typ": "JWT"}, base_payload, sign_key=b"wrong-key"), False),
    ]
    rows = []
    for label, tok, expected in cases:
        loose = loose_verify(tok)
        strict, reason = strict_verify(tok)
        assert strict == expected, label
        rows.append(dict(case=label, expected=expected, loose_accept=loose, strict_accept=strict, decision=reason))
    return dict(
        cases=rows,
        loose_correct=sum(r["loose_accept"] == r["expected"] for r in rows),
        strict_correct=sum(r["strict_accept"] == r["expected"] for r in rows),
    )


def sbom_experiment():
    # Six synthetic embedded build package records comparing version-only vs context-aware CVE triage.
    components = [
        dict(case="unpatched network daemon", pkg="curl", version="7.82.0", cve_version_match=True,
             backport_patch=False, reachable_in_image=True, expected_action="patch required"),
        dict(case="backported recipe patch", pkg="openssl", version="3.0.7", cve_version_match=True,
             backport_patch=True, reachable_in_image=True, expected_action="mitigated by backport"),
        dict(case="host-only build tool", pkg="cmake-native", version="3.24.2", cve_version_match=True,
             backport_patch=False, reachable_in_image=False, expected_action="not in target rootfs"),
        dict(case="disabled optional feature", pkg="libxml2", version="2.9.14", cve_version_match=True,
             backport_patch=True, reachable_in_image=True, expected_action="mitigated by backport"),
        dict(case="missing version metadata", pkg="custom-ipc", version="", cve_version_match=False,
             backport_patch=False, reachable_in_image=True, expected_action="manual audit required"),
        dict(case="upgraded upstream release", pkg="zlib", version="1.3.1", cve_version_match=False,
             backport_patch=False, reachable_in_image=True, expected_action="clean"),
    ]
    rows = []
    for item in components:
        version_only = "patch required" if item["cve_version_match"] else "clean"
        if not item["version"]:
            context_decision = "manual audit required"
        elif not item["reachable_in_image"]:
            context_decision = "not in target rootfs"
        elif item["cve_version_match"] and item["backport_patch"]:
            context_decision = "mitigated by backport"
        elif item["cve_version_match"]:
            context_decision = "patch required"
        else:
            context_decision = "clean"
        assert context_decision == item["expected_action"], item["case"]
        rows.append(dict(
            case=item["case"], pkg=item["pkg"], version=item["version"] or "unknown",
            version_only=version_only, context_triage=context_decision, expected=item["expected_action"],
        ))
    return dict(
        cases=rows,
        version_only_accurate=sum(r["version_only"] == r["expected"] for r in rows),
        context_accurate=sum(r["context_triage"] == r["expected"] for r in rows),
    )


def netfilter_experiment():
    # Seven synthetic packet flows testing PREROUTING spoofing visibility vs INPUT-only logging.
    packets = [
        dict(case="whitelisted IPv4 unicast", src="192.168.10.5", dst="192.168.10.1", proto="TCP/443", spoofed=False, allowed=True),
        dict(case="LAND spoof (src == dst)", src="192.168.10.1", dst="192.168.10.1", proto="TCP/80", spoofed=True, allowed=False),
        dict(case="RFC1918 martian source", src="127.0.0.5", dst="192.168.10.1", proto="UDP/53", spoofed=True, allowed=False),
        dict(case="unlisted IPv4 source", src="192.168.10.99", dst="192.168.10.1", proto="TCP/22", spoofed=False, allowed=False),
        dict(case="approved IPv6 multicast", src="fe80::10", dst="ff02::1:ff00:1", proto="ICMPv6", spoofed=False, allowed=True),
        dict(case="unapproved multicast group", src="fe80::10", dst="ff05::99", proto="UDP/1900", spoofed=False, allowed=False),
    ]
    rows = []
    for pkt in packets:
        # Pipeline A: rp_filter drops spoofed traffic in routing before INPUT; NFLOG only in INPUT.
        input_only_logged = (not pkt["spoofed"]) and (not pkt["allowed"])
        # Pipeline B: mangle/PREROUTING logs spoofed frames to NFLOG group 110 before drop; INPUT logs policy drops to group 100.
        dual_hook_logged = not pkt["allowed"]
        verdict = "accept" if pkt["allowed"] else "drop"
        rows.append(dict(
            case=pkt["case"], proto=pkt["proto"], verdict=verdict,
            input_only_evidence="logged" if input_only_logged else ("allowed" if pkt["allowed"] else "silent drop"),
            dual_hook_evidence="nflog-prerouting" if pkt["spoofed"] else ("nflog-input" if not pkt["allowed"] else "allowed"),
        ))
    dropped = [r for r in rows if r["verdict"] == "drop"]
    assert sum(r["input_only_evidence"] == "logged" for r in dropped) == 2
    assert sum(r["dual_hook_evidence"].startswith("nflog") for r in dropped) == 4
    return dict(cases=rows, total_dropped=len(dropped), input_only_observed=2, dual_hook_observed=4)


def correlation_experiment():
    # Compare per-IP fixed 60s bucket (>=5 failures) vs sliding 60s window with account + spray rules.
    scenarios = [
        dict(
            case="single-IP burst (6 fails in 12s)",
            events=[(10, "10.0.0.9", "alice"), (12, "10.0.0.9", "alice"), (14, "10.0.0.9", "alice"),
                    (16, "10.0.0.9", "alice"), (18, "10.0.0.9", "alice"), (20, "10.0.0.9", "alice")],
            expected_detect=True,
        ),
        dict(
            case="boundary-split burst (3 at 58s, 3 at 62s)",
            events=[(57, "10.0.0.8", "bob"), (58, "10.0.0.8", "bob"), (59, "10.0.0.8", "bob"),
                    (61, "10.0.0.8", "bob"), (62, "10.0.0.8", "bob"), (63, "10.0.0.8", "bob")],
            expected_detect=True,
        ),
        dict(
            case="distributed spray (6 IPs -> 6 users in 15s)",
            events=[(10 + i * 2, f"10.0.1.{i}", f"user-{i}") for i in range(6)],
            expected_detect=True,
        ),
        dict(
            case="normal typo (2 fails by 1 user)",
            events=[(10, "10.0.2.5", "carol"), (14, "10.0.2.5", "carol")],
            expected_detect=False,
        ),
    ]
    rows = []
    for sc in scenarios:
        ev = sc["events"]
        # Fixed 60s bucket per IP (bucket = t // 60)
        buckets = {}
        for t, ip, _u in ev:
            buckets[(t // 60, ip)] = buckets.get((t // 60, ip), 0) + 1
        fixed_ip_detected = any(count >= 5 for count in buckets.values())

        # Sliding 60s window checking per-IP >= 5 OR distinct users failed >= 5 across service
        sliding_detected = False
        for i, (t_end, _ip, _u) in enumerate(ev):
            window = [item for item in ev[: i + 1] if t_end - item[0] <= 60]
            ip_counts = {}
            users = set()
            for _t, wip, wuser in window:
                ip_counts[wip] = ip_counts.get(wip, 0) + 1
                users.add(wuser)
            if any(c >= 5 for c in ip_counts.values()) or len(users) >= 5:
                sliding_detected = True
                break
        assert sliding_detected == sc["expected_detect"], sc["case"]
        rows.append(dict(
            case=sc["case"], expected=sc["expected_detect"],
            fixed_bucket=fixed_ip_detected, sliding_multi_entity=sliding_detected,
        ))
    return dict(
        cases=rows,
        fixed_correct=sum(r["fixed_bucket"] == r["expected"] for r in rows),
        sliding_correct=sum(r["sliding_multi_entity"] == r["expected"] for r in rows),
    )


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = {}
    for b in data:
        counts[b] = counts.get(b, 0) + 1
    n = len(data)
    return round(-sum((c / n) * math.log2(c / n) for c in counts.values()), 2)


def entropy_experiment():
    # Deterministic byte fixtures illustrating why entropy alone is insufficient for malware triage.
    pseudo_random = bytes((i * 73 + 19) % 256 for i in range(512))
    samples = [
        dict(case="standard code section", data=(b"MOV EAX, EBX\nCALL 0x401000\nRET\n" * 16), imports=42, rwx_section=False, expected_review=False),
        dict(case="packed RWX stub", data=pseudo_random, imports=3, rwx_section=True, expected_review=True),
        dict(case="benign compressed resource", data=pseudo_random, imports=58, rwx_section=False, expected_review=False),
        dict(case="null-padded packed payload", data=pseudo_random[:256] + (b"\x00" * 512), imports=2, rwx_section=True, expected_review=True),
        dict(case="plain string table", data=(b"https://updates.example.org/status\x00" * 14), imports=35, rwx_section=False, expected_review=False),
    ]
    rows = []
    for item in samples:
        ent = _shannon_entropy(item["data"])
        entropy_only_flag = ent >= 7.2
        multi_signal_flag = (ent >= 7.2 and item["imports"] < 10) or (item["rwx_section"] and item["imports"] < 10)
        assert multi_signal_flag == item["expected_review"], item["case"]
        rows.append(dict(
            case=item["case"], entropy=ent, imports=item["imports"], rwx=item["rwx_section"],
            entropy_only=entropy_only_flag, multi_signal=multi_signal_flag, expected=item["expected_review"],
        ))
    return dict(
        cases=rows,
        entropy_only_correct=sum(r["entropy_only"] == r["expected"] for r in rows),
        multi_signal_correct=sum(r["multi_signal"] == r["expected"] for r in rows),
    )


def main():
    results = dict(
        run_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(),
        sqlite=sqlite3.sqlite_version,
        platform=platform.system(),
        provenance="Executed offline teaching fixtures; AI-assisted preparation. No live Wazuh or LLM.",
        sql=sql_experiment(),
        dedup=dedup_experiment(),
        ai=ai_experiment(),
        ssrf=ssrf_experiment(),
        token=token_experiment(),
        sbom=sbom_experiment(),
        netfilter=netfilter_experiment(),
        correlation=correlation_experiment(),
        entropy=entropy_experiment(),
    )
    results["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        f"Run UTC: {results['run_utc']}",
        f"Python {results['python']} | SQLite {results['sqlite']} | {results['platform']}",
        f"Source SHA-256: {results['source_sha256']}",
        "Scope: offline synthetic fixtures; no LLM or Wazuh service",
        "",
        "1. SQL query tests: concatenation 3/6 correct; parameters 6/6 correct",
    ]
    lines += [f"  {r['case']}: unsafe={r['concatenation']}; parameterized={r['parameterized']}; expected={r['expected']}" for r in results["sql"]["cases"]]
    lines += [
        "",
        "2. Dedup: 12 deliveries / 8 unique source events",
        "  content key: 1 retained / 7 distinct events lost",
        "  source identity: 8 retained / 4 duplicate deliveries removed",
        "",
        "3. AI output boundary: 8 handcrafted responses; 6 rejected / 2 accepted as text",
    ]
    lines += [f"  {r['case']}: {r['decision']}" for r in results["ai"]["cases"]]
    lines += [
        "  IMPORTANT: malicious prose passed schema; no action executor exists.",
        "",
        f"4. SSRF egress policy: naive substring {results['ssrf']['naive_correct']}/8 vs strict canonical {results['ssrf']['strict_correct']}/8",
        f"5. Token verification: loose {results['token']['loose_correct']}/6 vs strict {results['token']['strict_correct']}/6",
        f"6. SBOM & backport triage: version-only {results['sbom']['version_only_accurate']}/6 vs context-aware {results['sbom']['context_accurate']}/6",
        f"7. Netfilter hook visibility: INPUT-only logged {results['netfilter']['input_only_observed']}/4 drops vs dual-hook {results['netfilter']['dual_hook_observed']}/4 drops",
        f"8. Log correlation windows: fixed bucket {results['correlation']['fixed_correct']}/4 vs sliding dual-entity {results['correlation']['sliding_correct']}/4",
        f"9. Static binary triage: entropy-only {results['entropy']['entropy_only_correct']}/5 vs multi-signal {results['entropy']['multi_signal_correct']}/5",
        "",
        "All 9 experiment suites passed assertions.",
    ]
    transcript = "\n".join(lines) + "\n"
    (HERE / "transcript.txt").write_text(transcript, encoding="utf-8")
    print(transcript)


if __name__ == "__main__":
    main()
