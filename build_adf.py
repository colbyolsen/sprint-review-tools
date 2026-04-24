#!/usr/bin/env python3
"""Sprint Review ADF generator.

Consumes a compact JSON describing current/next-sprint tickets and emits a
full Atlassian Document Format document matching the Conservice Billing + Automations
sprint review template.

Usage: python3 build_adf.py <sprint_data.json> <out_adf.json>
"""
import json
import sys

d = json.loads(open(sys.argv[1]).read())
es, ns, rd = d["ending_sprint"], d["next_sprint"], d["review_date"]
cur, nxt = d["current_sprint_tickets"], d["next_sprint_tickets"]


def T(s, m=None):
    n = {"type": "text", "text": s}
    if m:
        n["marks"] = m
    return n


def P(c=None):
    p = {"type": "paragraph"}
    if c:
        p["content"] = c
    return p


def H(l, s, bold=False):
    return {
        "type": "heading",
        "attrs": {"level": l},
        "content": [T(s, [{"type": "strong"}]) if bold else T(s)],
    }


def TH(s):
    return {"type": "tableHeader", "content": [P([T(s, [{"type": "strong"}])])]}


def TC(c, bg=None):
    r = {"type": "tableCell"}
    if bg:
        r["attrs"] = {"background": bg}
    r["content"] = c
    return r


def row(cells):
    return {"type": "tableRow", "content": cells}


def tbl(rows):
    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": rows,
    }


def stat(txt, color):
    return {
        "type": "status",
        "attrs": {"text": txt, "color": color, "style": "bold"},
    }


def pan(title):
    return {
        "type": "panel",
        "attrs": {"panelType": "info"},
        "content": [H(3, title, bold=True)],
    }


def bl(items):
    return {"type": "bulletList", "content": items}


def li(para_c, nested=None):
    out = [P(para_c) if para_c else P()]
    if nested:
        out.append(nested)
    return {"type": "listItem", "content": out}


def link_text(key):
    return T(
        key,
        [
            {
                "type": "link",
                "attrs": {"href": f"https://conservice.atlassian.net/browse/{key}"},
            },
            {"type": "em"},
        ],
    )


TEAM_BG = {"Billing 1": "#DEEBFF", "Automations": "#E3FCEF"}
JSC = {
    "Complete": "green",
    "Testing": "yellow",
    "Code Review & Security": "blue",
    "Development": "purple",
    "Design": "purple",
    "Backlog": "neutral",
}
RTC = {"YES": "green", "NO": "red", "N/A": "neutral"}


def cur_row(t):
    done_text = "DONE" if t["status_name"] == "Complete" else "NOT DONE"
    done_color = "green" if t["status_name"] == "Complete" else "red"
    jc = JSC.get(t["status_name"], "neutral")
    sp = t.get("speaker", "")
    return row(
        [
            TC([P([T(t["goal_text"], [{"type": "strong"}])])]),
            TC([P([T(t["team"])])], bg=TEAM_BG[t["team"]]),
            TC([P([T(sp)]) if sp else P()]),
            TC([P([T(t["outcome"], [{"type": "em"}])])]),
            TC([P([link_text(t["key"])])]),
            TC(
                [
                    P([stat(done_text, done_color)]),
                    P([stat(t["status_name"], jc)]),
                ]
            ),
            TC([P()]),
            TC(
                [
                    P(
                        [
                            stat(
                                t["released_to_prod"],
                                RTC.get(t["released_to_prod"], "neutral"),
                            )
                        ]
                    )
                ]
            ),
        ]
    )


def nxt_row(t):
    if isinstance(t.get("outcome_nodes"), list):
        oc = t["outcome_nodes"]
    else:
        oc = [P([T(t["outcome"], [{"type": "em"}])])]
    return row(
        [
            TC([P([T(t["goal_text"], [{"type": "strong"}])])]),
            TC([P([T(t["team"])])], bg=TEAM_BG[t["team"]]),
            TC(oc),
            TC([P([link_text(t["key"])])]),
            TC([P()]),
        ]
    )


CUR_HDR = [
    "Goal",
    "Team",
    "Speaker",
    "Impact / Outcome",
    "Ticket #",
    "Goal Status",
    "Target Release",
    "Released to Prod",
]
NXT_HDR = ["Goal", "Team", "Outcome", "Ticket #", "Feedback"]

CUR_ORDER = [
    "Long Tail",
    "Subs on Skywalker",
    "NAS on Skywalker",
    "QC Task Optimization",
    "Online Prebill",
    "Incremental and Legacy Enhancements",
    "Tech Debt",
    "Move Outs",
    "Single Family Bill Estimator",
]
NXT_ORDER = [
    "Long Tail",
    "Subs on Skywalker",
    "NAS on Skywalker",
    "QC Task Optimization",
    "Online Prebill",
    "Incremental Enhancements",
    "Tech Debt",
    "Move Outs",
    "Single Family Bill Estimator",
]


def group(tickets):
    g = {}
    for t in tickets:
        g.setdefault(t["category"], []).append(t)
    return g


cur_g, nxt_g = group(cur), group(nxt)

CORE_DATA = {
    "type": "panel",
    "attrs": {"panelType": "info"},
    "content": [
        H(3, "Core Data Adoption", bold=True),
        P([T('How will we, as a domain, use "Core Data"?', [{"type": "strong"}])]),
        bl(
            [
                li(
                    [
                        T(
                            "Although we see some areas where we may be able to introduce Core Data to ourselves, the primary uses which are documented so far seem to be Synergy based."
                        )
                    ],
                    bl(
                        [
                            li(
                                [
                                    T(
                                        "We need to see more documentation and have more discussions."
                                    )
                                ]
                            )
                        ]
                    ),
                )
            ]
        ),
        P(
            [
                T(
                    'What is our current status of using "Core Data"?',
                    [{"type": "strong"}],
                )
            ]
        ),
        bl(
            [
                li(
                    [
                        T(
                            "Billing is dependent on the creation of unit, building groups, and building objects in core data, which is dependent on Onboarding Transformation. The timeline and prioritization of that transformation is TBD."
                        )
                    ]
                )
            ]
        ),
    ],
}

SEVERITY = {
    "type": "panel",
    "attrs": {"panelType": "info"},
    "content": [H(3, "Severity Incidents", bold=True), bl([li([T("None")])])],
}


def stubs():
    return bl(
        [
            li([T("Demo:")], bl([li([])])),
            li([T("Feedback:")], bl([li([])])),
        ]
    )


content = [
    H(1, f"Sprint {es}"),
    P([T(rd, [{"type": "strong"}])]),
    CORE_DATA,
    pan("Spotlight Demo"),
    tbl(
        [
            row([TH(h) for h in CUR_HDR]),
            row([TC([P()]) for _ in range(8)]),
        ]
    ),
    H(2, "Current Sprint Goals (45 min)"),
]

for cat in CUR_ORDER:
    if cat not in cur_g:
        continue
    content.append(pan(cat))
    content.append(
        tbl([row([TH(h) for h in CUR_HDR])] + [cur_row(t) for t in cur_g[cat]])
    )
    content.append(stubs())

content.append({"type": "rule"})
content.append(H(2, f"Looking Ahead to Next Sprint - {ns} (10 min)"))

for cat in NXT_ORDER:
    if cat not in nxt_g:
        continue
    content.append(pan(cat))
    content.append(
        tbl([row([TH(h) for h in NXT_HDR])] + [nxt_row(t) for t in nxt_g[cat]])
    )

content.append({"type": "rule"})
content.append(SEVERITY)

doc = {"type": "doc", "version": 1, "content": content}
open(sys.argv[2], "w").write(json.dumps(doc))
print(
    f"Wrote {sys.argv[2]}, {len(content)} nodes, {len(cur)} cur tickets, {len(nxt)} nxt tickets"
)
