"""Render standalone SVG result tables and technical architecture diagrams."""
from pathlib import Path
from html import escape
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'research/labs/results.json').read_text(encoding='utf-8'))
OUT = ROOT / 'assets/research'
OUT.mkdir(parents=True, exist_ok=True)


def figure(name, title, subtitle, headings, rows, footer, badge='LAB NOTE / EXECUTED RESULTS'):
    xs = [36, 465, 675]
    height = max(460, 235 + len(rows) * 32)
    desc = subtitle + '; ' + '; '.join(' / '.join(map(str, r)) for r in rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>'
        f'<rect width="900" height="{height}" fill="#f0f1ea"/>'
        f'<rect x="18" y="18" width="864" height="{height - 36}" fill="none" stroke="#d9dcd2" stroke-width="1"/>'
    ]

    def text(x, y, value, size=15, color='#222722', family='Arial, sans-serif', weight='normal'):
        w_attr = f' font-weight="{weight}"' if weight != 'normal' else ''
        parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-family="{family}"{w_attr}>{escape(str(value))}</text>')

    text(36, 46, badge, 12, '#405d47', 'Consolas, monospace', '600')
    text(36, 84, title, 28, family='Georgia, serif')
    text(36, 114, subtitle, 14, '#60665e')
    parts.append('<rect x="36" y="138" width="828" height="32" fill="#e4e7dd"/>')
    for x, heading in zip(xs, headings):
        text(x + 8, 159, heading.upper(), 12, '#405d47', 'Consolas, monospace', '600')
    for i, row in enumerate(rows):
        y = 194 + i * 32
        if i > 0:
            parts.append(f'<path d="M36 {y - 20} H864" stroke="#d0d5ca"/>')
        for col_idx, (x, value) in enumerate(zip(xs, row)):
            val_str = str(value)
            color = '#222722'
            if col_idx > 0 and any(tok in val_str.lower() for tok in ('error', 'bypass', 'lost', 'silent', 'unrequested', 'mismatch')):
                color = '#875149'
            elif col_idx > 0 and any(tok in val_str.lower() for tok in ('verified', 'parameters', 'mitigated', 'nflog', 'detected', 'retained')):
                color = '#405d47'
            text(x + 8, y + 2, val_str, 14, color)
    text(36, height - 34, footer, 12, '#405d47', 'Consolas, monospace')
    parts.append('</svg>')
    (OUT / name).write_text(''.join(parts), encoding='utf-8')


def flow_diagram(name, kicker, title, subtitle, nodes, comparisons, footer):
    """Render a clean architectural/attack-chain SVG diagram in the field-notebook palette."""
    height = 480
    desc = f"{subtitle}. Flow: " + " -> ".join(f"{n[0]} ({n[1]})" for n in nodes)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>',
        f'<rect width="900" height="{height}" fill="#f0f1ea"/>',
        f'<rect x="18" y="18" width="864" height="{height - 36}" fill="none" stroke="#d9dcd2" stroke-width="1"/>',
    ]

    def text(x, y, value, size=14, color='#222722', family='Arial, sans-serif', weight='normal'):
        w_attr = f' font-weight="{weight}"' if weight != 'normal' else ''
        parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-family="{family}"{w_attr}>{escape(str(value))}</text>')

    text(36, 46, kicker, 12, '#405d47', 'Consolas, monospace', '600')
    text(36, 82, title, 27, family='Georgia, serif')
    text(36, 110, subtitle, 14, '#60665e')

    # Render 4 horizontal pipeline boxes
    box_w = 192
    box_h = 98
    gap = 20
    start_x = 36
    box_y = 136
    for idx, (step_label, heading, detail) in enumerate(nodes[:4]):
        bx = start_x + idx * (box_w + gap)
        fill = '#fbfaf7' if idx < 3 else '#e6ece5'
        stroke = '#c5c9c0' if idx < 3 else '#405d47'
        parts.append(f'<rect x="{bx}" y="{box_y}" width="{box_w}" height="{box_h}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        text(bx + 12, box_y + 24, step_label, 11, '#405d47', 'Consolas, monospace', '600')
        text(bx + 12, box_y + 50, heading, 15, '#222722', 'Georgia, serif', '600')
        # Wrap detail into two lines if needed
        words = detail.split()
        line1, line2 = [], []
        for w in words:
            if len(' '.join(line1 + [w])) <= 26:
                line1.append(w)
            else:
                line2.append(w)
        text(bx + 12, box_y + 72, ' '.join(line1), 12, '#60665e')
        if line2:
            text(bx + 12, box_y + 88, ' '.join(line2)[:28], 12, '#60665e')
        if idx < len(nodes[:4]) - 1:
            ax = bx + box_w + 4
            ay = box_y + box_h // 2
            parts.append(f'<path d="M{ax} {ay} H{ax + gap - 8}" stroke="#405d47" stroke-width="1.5"/>')
            parts.append(f'<polygon points="{ax + gap - 8},{ay - 4} {ax + gap - 2},{ay} {ax + gap - 8},{ay + 4}" fill="#405d47"/>')

    # Render two-column comparison / evidence panel below
    panel_y = 258
    col_w = 404
    for c_idx, (col_tag, col_title, bullets) in enumerate(comparisons[:2]):
        cx = 36 + c_idx * (col_w + 20)
        accent = '#875149' if c_idx == 0 else '#405d47'
        bg = '#f6efec' if c_idx == 0 else '#ebf0ea'
        parts.append(f'<rect x="{cx}" y="{panel_y}" width="{col_w}" height="156" fill="{bg}" stroke="#d0d5ca"/>')
        parts.append(f'<rect x="{cx}" y="{panel_y}" width="4" height="156" fill="{accent}"/>')
        text(cx + 16, panel_y + 24, col_tag, 11, accent, 'Consolas, monospace', '600')
        text(cx + 16, panel_y + 48, col_title, 16, '#222722', 'Georgia, serif', '600')
        for b_idx, bullet in enumerate(bullets[:3]):
            text(cx + 16, panel_y + 78 + b_idx * 24, f"• {bullet}", 13, '#222722')

    text(36, height - 30, footer, 12, '#405d47', 'Consolas, monospace')
    parts.append('</svg>')
    (OUT / name).write_text(''.join(parts), encoding='utf-8')


def outcome(value):
    return 'SQL error' if value == 'SQL error' else ('Allow' if value else 'Deny')


# 1. SQL
figure(
    'sql-results.svg',
    'Data stays data.',
    'SQLite in-memory fixture / six test cases / no network target',
    ['Test case', 'Concatenation', 'Parameters'],
    [(r['case'], outcome(r['concatenation']), outcome(r['parameterized'])) for r in DATA['sql']['cases']],
    f"Correct outcomes: {DATA['sql']['unsafe_correct']}/6 vs {DATA['sql']['safe_correct']}/6 | See raw JSON for inputs",
)

# 2. Dedup
d = DATA['dedup']
figure(
    'dedup-results.svg',
    'Similar text. Distinct events.',
    'Synthetic event replay / one manager / two agents',
    ['Observation', 'Count', 'Meaning'],
    [
        ('Incoming deliveries', d['raw_deliveries'], '8 events + 4 retries'),
        ('Ground truth', d['ground_truth'], 'Distinct source IDs'),
        ('Content-key retention', d['naive_retained'], '7 events lost'),
        ('Identity-key retention', d['identity_retained'], 'No fixture event lost'),
        ('Duplicate deliveries removed', d['raw_deliveries'] - d['identity_retained'], 'Source identity key'),
    ],
    'Ground truth is constructed, not a production measurement.',
)

# 3. AI
a = DATA['ai']
figure(
    'ai-results.svg',
    'A schema is only one boundary.',
    'Handcrafted responses / no LLM calls / no action executor',
    ['Observation', 'Count', 'Interpretation'],
    [
        ('Candidate responses', len(a['cases']), 'Hand-authored'),
        ('Rejected by policy', a['rejected'], 'Schema / ID / priority'),
        ('Accepted as text', a['accepted'], 'Analyst review only'),
        ('Malicious prose accepted', 1, 'Known limitation'),
        ('Actions executed', a['executed_actions'], 'No executor present'),
    ],
    'This test does not measure model resistance to prompt injection.',
)

# 4. SSRF
if 'ssrf' in DATA:
    s = DATA['ssrf']
    figure(
        'ssrf-results.svg',
        'Resolve before connecting.',
        'Eight URL fixtures / offline DNS table / canonical IP validation',
        ['Test case', 'Naive substring', 'Canonical IP policy'],
        [
            (r['case'], 'Allow' if r['naive_allow'] else 'Block', 'Allow' if r['strict_allow'] else f"Block ({r['reason']})")
            for r in s['cases']
        ],
        f"Correct policy decisions: {s['naive_correct']}/8 naive vs {s['strict_correct']}/8 strict canonical",
    )

# 5. Token / JWT
if 'token' in DATA:
    t = DATA['token']
    figure(
        'jwt-results.svg',
        'Verify algorithm, signature, and context.',
        'Six signed token fixtures / HMAC-SHA256 / explicit audience & expiration',
        ['Token fixture', 'Loose decoder', 'Strict verifier'],
        [
            (r['case'], 'Accept' if r['loose_accept'] else 'Reject', 'Accept' if r['strict_accept'] else f"Reject ({r['decision']})")
            for r in t['cases']
        ],
        f"Correct verification decisions: {t['loose_correct']}/6 loose vs {t['strict_correct']}/6 strict",
    )

# 6. SBOM
if 'sbom' in DATA:
    sb = DATA['sbom']
    figure(
        'sbom-results.svg',
        'Version strings are not patch state.',
        'Six embedded package records / CPE version match vs recipe patch provenance',
        ['Package case', 'Version-only scan', 'Context-aware triage'],
        [(f"{r['pkg']} ({r['version']})", r['version_only'], r['context_triage']) for r in sb['cases']],
        f"Aligned with build ground truth: {sb['version_only_accurate']}/6 version-only vs {sb['context_accurate']}/6 context-aware",
    )

# 7. Netfilter
if 'netfilter' in DATA:
    nf = DATA['netfilter']
    figure(
        'netfilter-results.svg',
        'Log spoofing before routing drops it.',
        'Six packet profiles / INPUT-only logging vs PREROUTING + INPUT NFLOG groups',
        ['Packet profile', 'INPUT-only log', 'Dual-hook NFLOG'],
        [(f"{r['case']} ({r['proto']})", r['input_only_evidence'], r['dual_hook_evidence']) for r in nf['cases']],
        f"Dropped packets with audit trail: {nf['input_only_observed']}/{nf['total_dropped']} INPUT-only vs {nf['dual_hook_observed']}/{nf['total_dropped']} dual-hook",
    )

# 8. Correlation
if 'correlation' in DATA:
    co = DATA['correlation']
    figure(
        'correlation-results.svg',
        'Sliding windows catch split and distributed bursts.',
        'Four authentication event streams / fixed 60s IP bucket vs sliding multi-entity window',
        ['Traffic scenario', 'Fixed IP bucket', 'Sliding multi-entity'],
        [
            (r['case'], 'Detected' if r['fixed_bucket'] else 'Missed / Quiet', 'Detected' if r['sliding_multi_entity'] else 'Quiet (Expected)')
            for r in co['cases']
        ],
        f"Scenario accuracy: {co['fixed_correct']}/4 fixed bucket vs {co['sliding_correct']}/4 sliding dual-entity",
    )

# 9. Entropy
if 'entropy' in DATA:
    en = DATA['entropy']
    figure(
        'entropy-results.svg',
        'High entropy is not proof of malice.',
        'Five binary section fixtures / Shannon entropy (bits/byte) + import & permission heuristics',
        ['Section profile (H bits/B)', 'Entropy >= 7.2 only', 'Multi-signal triage'],
        [
            (
                f"{r['case']} (H={r['entropy']})",
                'Flagged' if r['entropy_only'] else 'Clean',
                'Flagged (Review)' if r['multi_signal'] else 'Benign / Normal',
            )
            for r in en['cases']
        ],
        f"Triage accuracy: {en['entropy_only_correct']}/5 entropy-only vs {en['multi_signal_correct']}/5 multi-signal heuristic",
    )

# Render architectural & walkthrough diagrams
flow_diagram(
    'htb-appointment-flow.svg',
    'WALKTHROUGH DIAGRAM / HTB APPOINTMENT',
    'SQL injection login bypass & prepared statement fix',
    'How unparameterized string interpolation allows comment truncation in authentication queries',
    [
        ('STEP 01', 'HTTP Login POST', 'username=admin\'# & password=lab'),
        ('STEP 02', 'String Concat', 'Quote closes literal; # starts SQL comment'),
        ('STEP 03', 'Query Evaluation', 'AND password=... is ignored by parser'),
        ('STEP 04', 'Remediation', 'Bind parameters (?, ?) + hash check'),
    ],
    [
        ('VULNERABLE PATH', 'Concatenated SQL string', [
            "WHERE username='admin'#' AND password='...'",
            'Input data alters SQL syntax tree directly',
            'Returns admin row without password match',
        ]),
        ('VERIFIED REMEDIATION', 'Parameterized query + password hash', [
            'SELECT id, hash FROM users WHERE username = ?',
            'Quote & # treated strictly as literal characters',
            'Regression test: valid names with apostrophes work',
        ]),
    ],
    'Teaching diagram for authorized lab study | No live HTB flag or proprietary source claimed',
)

flow_diagram(
    'htb-fawn-flow.svg',
    'WALKTHROUGH DIAGRAM / HTB FAWN',
    'Anonymous FTP exposure: separating reachability from read access',
    'Structured verification from service discovery to directory listing and file retrieval',
    [
        ('STEP 01', 'Service Discovery', 'nmap -sV -p 21 confirms vsftpd'),
        ('STEP 02', 'Auth Check', 'USER anonymous / PASS guest accepted (230)'),
        ('STEP 03', 'Data Channel', 'PASV/LIST enumerates public directory'),
        ('STEP 04', 'Hardening', 'anonymous_enable=NO or strict chroot'),
    ],
    [
        ('OBSERVED EXPOSURE', 'Misconfigured public root', [
            'TCP/21 allows unauthenticated anonymous login',
            'Sensitive file placed inside readable FTP directory',
            'Transport encryption alone would not block access',
        ]),
        ('DEFENSIVE CONTROL', 'Access control + audit verification', [
            'Disable anonymous access when public share is unneeded',
            'Separate public dropbox from internal files',
            'Verify with post-change nmap ftp-anon retest',
        ]),
    ],
    'Reference walkthrough diagram | Separates network reachability, authentication, and file permissions',
)

flow_diagram(
    'htb-redeemer-flow.svg',
    'WALKTHROUGH DIAGRAM / HTB REDEEMER',
    'Unauthenticated Redis: incremental keyspace discovery',
    'Evaluating network-exposed in-memory data stores with non-blocking commands',
    [
        ('STEP 01', 'Port & Protocol', 'TCP/6379 responds PONG to PING'),
        ('STEP 02', 'Keyspace Scope', 'INFO keyspace & DBSIZE check volume'),
        ('STEP 03', 'Safe Iteration', 'SCAN 0 MATCH * avoids blocking KEYS *'),
        ('STEP 04', 'Type-Aware Read', 'TYPE key -> GET + Redis ACL fix'),
    ],
    [
        ('EXPOSURE CHAIN', 'Network bind without authentication', [
            'Redis bound to 0.0.0.0 without requirepass / ACL',
            'Any reachable client can enumerate keyspace in db0',
            'Data read proven; OS command execution not implied',
        ]),
        ('HARDENING BOUNDARY', 'Network isolation + Redis ACLs', [
            'Bind only to loopback or private application subnet',
            'Define per-service ACL users with restricted commands',
            'Enable TLS when traffic crosses untrusted links',
        ]),
    ],
    'Reference walkthrough diagram | Illustrates non-destructive Redis assessment & ACL remediation',
)

flow_diagram(
    'htb-vaccine-flow.svg',
    'WALKTHROUGH DIAGRAM / HTB VACCINE',
    'From SQL injection to OS command execution & privilege boundary review',
    'Chaining web database misconfiguration with overly permissive local sudo rules',
    [
        ('STAGE 01', 'Session & SQLi', 'Weak cookie/login -> GET search parameter'),
        ('STAGE 02', 'DB Role Check', 'PostgreSQL superuser allows COPY PROGRAM'),
        ('STAGE 03', 'Foothold Audit', 'Service shell runs under postgres/www user'),
        ('STAGE 04', 'Privilege Review', 'sudo -l permits editor escape (GTFOBins)'),
    ],
    [
        ('CHAINED WEAKNESSES', 'Why one bug became full compromise', [
            'Web query concatenated raw GET filter parameter',
            'Web app connected as PostgreSQL superuser role',
            'Sudoers allowed interactive vi without shell restriction',
        ]),
        ('DEFENSE IN DEPTH', 'Breaking the chain at every layer', [
            'Parameterize search queries in application code',
            'Run DB connection with least-privilege SELECT/INSERT role',
            'Use sudoedit / noexec instead of unrestricted binary sudo',
        ]),
    ],
    'Reference study note | Focuses on multi-layer blast radius containment and least privilege',
)

flow_diagram(
    'htb-archetype-flow.svg',
    'WALKTHROUGH DIAGRAM / HTB ARCHETYPE',
    'SMB configuration leak to MSSQL command execution',
    'How readable deployment artifacts expose database credentials and administrative procedures',
    [
        ('STAGE 01', 'SMB Share Audit', 'Anonymous read on \\\\target\\backups'),
        ('STAGE 02', 'Artifact Review', 'prod.dtsConfig exposes SQL password'),
        ('STAGE 03', 'MSSQL Auth', 'Valid login holds sysadmin privileges'),
        ('STAGE 04', 'Host Boundary', 'xp_cmdshell enabled -> OS command run'),
    ],
    [
        ('OPERATIONAL FAILURE', 'Credential reuse & excessive DB privileges', [
            'Deployment share readable by unauthenticated guests',
            'Plaintext connection string stored in backup artifact',
            'Database service account granted sysadmin + xp_cmdshell',
        ]),
        ('REMEDIATION CONTROLS', 'Secret hygiene & service hardening', [
            'Restrict SMB shares to authenticated deployment principals',
            'Remove plaintext secrets from config/backup repositories',
            'Disable xp_cmdshell and run SQL service under low-priv account',
        ]),
    ],
    'Reference study note | Connects secret management, network share ACLs, and database hardening',
)

flow_diagram(
    'dfir-timeline.svg',
    'DFIR CASE NOTE / INCIDENT TIMELINE',
    'Correlating web access logs, authentication events, and host persistence',
    'Reconstructing an intrusion path across three independent telemetry sources',
    [
        ('08:12:04Z', 'Nginx access.log', 'Scanner 404 burst -> upload POST 200'),
        ('08:14:19Z', 'Process / Subshell', 'www-data spawns sh -c id; whoami'),
        ('08:16:42Z', 'Linux auth.log', 'Accepted publickey for deploy user'),
        ('08:18:05Z', 'Persistence Check', 'authorized_keys & /etc/cron.d modified'),
    ],
    [
        ('SINGLE-LOG BLIND SPOT', 'Why isolated logs mislead', [
            'HTTP 200 on file upload looks benign without child-process trace',
            'SSH login looks legitimate without preceding web-shell write',
            'Clock skew between services breaks naive timestamp sorting',
        ]),
        ('TRIAGE CORRELATION', 'Normalized UTC timeline + entity pivot', [
            'Pivot from source IP -> uploaded filename -> worker PID',
            'Correlate file mtime with auth.log session open',
            'Scope remediation: rotate keys, remove cron, patch upload',
        ]),
    ],
    'Synthetic DFIR lab reconstruction | Demonstrates multi-source timeline correlation',
)

flow_diagram(
    'lg-netfilter-arch.svg',
    'CASE STUDY DIAGRAM / EMBEDDED LINUX SECURITY',
    'webOS OSE packet validation & dual-group NFLOG telemetry',
    'End-to-end verification loop from Scapy packet synthesis to structured JSON audit logs',
    [
        ('GENERATOR', 'Windows + Scapy', 'IPv4/IPv6, VLAN, SYN flood, LAND'),
        ('EARLY HOOK', 'mangle PREROUTING', 'Detect & log spoofed frames (NFLOG 110)'),
        ('POLICY HOOK', 'filter INPUT', 'Whitelist, multicast & rate-limit rules'),
        ('TELEMETRY', 'ulogd2 Pipeline', 'Parallel LOGEMU text + JSON audit output'),
    ],
    [
        ('ENGINEERING EDGE CASES', 'Why naive firewall testing fails', [
            'rp_filter drops spoofed LAND packets before INPUT chain',
            'Two ulogd2 stacks cannot bind the same NFLOG group',
            'Missing IFINDEX/HWHDR plugins omit interface metadata',
        ]),
        ('VALIDATED ARCHITECTURE', 'Observable enforcement on Raspberry Pi 4', [
            '10/10 non-whitelisted IPv4 unicast packets dropped',
            '29 IPv6 anycast packets counted and logged accurately',
            'JSON = TEXT + 100 group split preserves both log formats',
        ]),
    ],
    'Team deliverable at LG Electronics R&D Vietnam | Baseline -> Control -> Capture -> Verify',
)

flow_diagram(
    'ossvs-pipeline-arch.svg',
    'CASE STUDY DIAGRAM / SUPPLY-CHAIN ASSURANCE',
    'Yocto OSS inventory, CVE triage, and two-stage backport verification',
    'Moving from 1,375 scanned source records to verified recipe patches in webOS OSE',
    [
        ('INVENTORY', 'FOSSLight Yocto', '1,375 records / 444 components (99.4% ID)'),
        ('TRIAGE', 'CPE/PURL + Context', 'Filter 4 high/critical CVEs by reachability'),
        ('REMEDIATION', 'Targeted Backport', 'Apply CVE patch in recipe (0 version bumps)'),
        ('VALIDATION', '2-Stage Rebuild', 'Component build -> full raspberrypi4 image'),
    ],
    [
        ('SCANNER LIMITATION', 'Why CVSS and version strings are not enough', [
            '8 records lacked version strings -> explicit uncertainty gap',
            'Backported fixes keep original upstream version (e.g. 3.0.7)',
            'Version-only re-scans still flag already-patched recipes',
        ]),
        ('AUDITABLE EVIDENCE', 'Traceable patch provenance', [
            'Validated fixes for OpenSSL, libxml2, and curl (CVE-2023-38545)',
            'Component build provides fast feedback before image build',
            'Build metadata + recipe patch list serve as source of truth',
        ]),
    ],
    'Individual OSSVS technical report | Sanitized architecture & verification metrics',
)

flow_diagram(
    'wazuh-triage-arch.svg',
    'CASE STUDY DIAGRAM / SOC AUTOMATION',
    'AI-assisted Wazuh alert prioritization with deterministic guardrails',
    'Combining repeatable heuristic baselines with optional, schema-bounded LLM enrichment',
    [
        ('COLLECTION', 'Wazuh Collector', 'Cursor pagination + identity deduplication'),
        ('PRIVACY GATE', 'PII Redactor', 'Mask sensitive tokens/IPs before external call'),
        ('SCORING', 'Heuristic + LLM', 'Rule baseline always active; LLM optional'),
        ('DISPATCH', 'Policy & Webhook', 'Correlated high-priority cases -> Telegram/n8n'),
    ],
    [
        ('TRUST BOUNDARIES', 'Failure modes addressed by design', [
            'Duplicate alert deliveries -> source-identity deduplication',
            'External LLM outage -> seamless deterministic heuristic fallback',
            'Untrusted model prose -> strict schema & priority floor check',
        ]),
        ('OPERATIONAL READINESS', 'Testable backend & container workflow', [
            'Covers SQLi, XSS, brute force, LFI, and DoS alert families',
            'Separate /health/live and /health/ready endpoints',
            'Structured JSON logging for pipeline observability',
        ]),
    ],
    'Public Flask/Docker implementation | Designed for analyst verification, not blind automation',
)

print('Rendered 9 data-driven SVG result figures and 9 technical architecture diagrams.')
