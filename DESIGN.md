# Design direction: a field notebook

The portfolio should feel like a student's carefully maintained research notebook.

- **Paper and ink.** Warm off-white (#f8f7f3), near-black text (#222722), one muted green accent (#405d47).
- **Typography carries the hierarchy.** Noto Serif titles bring the rhythm of an essay; Noto Sans body text keeps reading comfortable. Both are self-hosted with full Vietnamese letter and diacritic coverage. Vietnamese headings use gentle tracking and extra line height. Monospace is reserved for dates, labels and code.
- **Structure before decoration.** Thin rules, generous margins, numbered project entries, no ornamental dashboard or looping motion.
- **Each subject has an address.** Projects, Research, Certifications, About and Contact are separate HTML documents. Experience and Skills & labs have their own pages. In-article contents links may jump to headings within a long document.
- **Language is an address, too.** English stays at the root; Vietnamese mirrors every route under `/vi/`. A compact EN/VI control switches to the exact counterpart without hiding content behind JavaScript.
- **A personal voice.** Vietnamese prose uses “mình”, with direct descriptions of what was learned and tested. Project and credential names retain their English spelling. A short practice line highlights the 171 completed PortSwigger labs; certification goals are clearly separated from earned credentials.
- **Evidence is part of the reading experience.** Project context and contributions are kept explicit. Research notes include an English abstract, Vietnamese body, method, results, limitations, source code and references.
- **Progressive enhancement.** Content and navigation work without JavaScript. JavaScript adds mobile menu controls, the three latest database posts, code/email copy and editor conveniences.
- **Responsive reading.** Two-column desktop compositions become a single reading column on small screens. Long code blocks and data tables scroll within their own containers.
- **Accessible by default.** Visible keyboard focus, skip links, active navigation states, descriptive image text, readable contrast and print styles.

## CMS extension

The public profile remains a quiet paper-and-ink portfolio. Research is rendered
server-side so a new post feels like part of the same notebook and remains useful
to search engines. Search and filters use ordinary forms. Labels distinguish
personal lab evidence from reference walkthroughs without scores, streaks, public
view counters or decorative motion.

The admin interface follows the same typography but acts as a workbench: metadata
above, Markdown and sanitized preview side by side, then an explicit publish
checklist. Operational UI stays under `/admin` and is excluded from indexing and
analytics. Umami is optional, self-hosted and cookie-free; the portfolio remains
fully readable when its script is unavailable.

Fonts and core assets remain self-hosted. The only optional browser script outside
the portfolio origin is the configured self-hosted Umami endpoint.
