#!/usr/bin/env python3
"""Generic sprint review ADF generator.

Consumes a JSON data file describing per-sprint content and emits an Atlassian
Document Format (ADF) document. All domain-specific text (category names,
panel content, URL patterns, color maps) is carried in the data file so this
generator can be reused across teams.

Usage:
    python3 build_adf.py <data.json> <out_adf.json>

Data JSON schema (top-level keys):
    ending_sprint              str  e.g. "26.08"
    next_sprint                str  e.g. "26.09"
    review_date                str  free-form, displayed bold under H1
    config                     obj  rendering config (see below)
    intro_panels               list rich info panels rendered before current-sprint section
    outro_panels               list rich info panels rendered after next-sprint section
    current_sprint_tickets     list ticket rows for current-sprint tables
    next_sprint_tickets        list ticket rows for next-sprint tables

config object:
    jira_base_url                       str
    team_backgrounds                    map team -> hex color
    status_colors                       map jira status -> adf status color
    released_to_prod_colors             map "YES"|"NO"|"N/A" -> adf status color
    current_sprint_h2                   str
    next_sprint_h2_fmt                  str with a single {} placeholder for the next sprint name
    spotlight_heading                   str (panel heading before the spotlight table)
    current_sprint_category_order       list of category names in render order
    next_sprint_category_order          list of category names in render order

rich panel body node types (used in intro_panels/outro_panels body arrays):
    {"type": "paragraph", "text": "...", "bold": true|false}
    {"type": "bullet",    "text": "...", "sub": ["..."]}   # sub items optional

current-sprint ticket schema:
    {"key":"...", "team":"...", "speaker":"...", "category":"...",
     "goal_text":"...", "outcome":"...",
     "status_name":"...", "released_to_prod":"YES"|"NO"|"N/A"}

next-sprint ticket schema:
    {"key":"...", "team":"...", "category":"...",
     "goal_text":"...", "outcome":"..."}
   or if the outcome is multi-rule / structured:
    {"key":"...", "team":"...", "category":"...",
     "goal_text":"...", "outcome_nodes":[<adf nodes>]}
"""
import json
import sys


# ---------- ADF node helpers ----------

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


def H(level, s, bold=False):
    marks = [{"type": "strong"}] if bold else None
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [T(s, marks)],
    }


def TH(s, colwidth=None):
    attrs = {"colspan": 1, "rowspan": 1}
    if colwidth is not None:
        attrs["colwidth"] = [colwidth]
    return {"type": "tableHeader", "attrs": attrs, "content": [P([T(s, [{"type": "strong"}])])]}


def TC(c, bg=None, colwidth=None):
    attrs = {"colspan": 1, "rowspan": 1}
    if bg:
        attrs["background"] = bg
    if colwidth is not None:
        attrs["colwidth"] = [colwidth]
    return {"type": "tableCell", "attrs": attrs, "content": c}


def row(cells):
    return {"type": "tableRow", "content": cells}


def tbl(rows, width=None):
    attrs = {"isNumberColumnEnabled": False, "layout": "default"}
    if width is not None:
        attrs["width"] = width
    return {
        "type": "table",
        "attrs": attrs,
        "content": rows,
    }


def stat(txt, color):
    return {"type": "status", "attrs": {"text": txt, "color": color, "style": "bold"}}


def info_panel(content):
    return {"type": "panel", "attrs": {"panelType": "info"}, "content": content}


def heading_only_panel(title):
    return info_panel([H(3, title, bold=True)])


def bullet_list(items):
    return {"type": "bulletList", "content": items}


def list_item(paragraph_content, nested=None):
    out = [P(paragraph_content) if paragraph_content else P()]
    if nested:
        out.append(nested)
    return {"type": "listItem", "content": out}


# ---------- rich panel body expansion ----------

def expand_body_nodes(body):
    """Expand a list of rich-panel body descriptors into ADF nodes."""
    out = []
    for item in body:
        kind = item["type"]
        if kind == "paragraph":
            marks = [{"type": "strong"}] if item.get("bold") else None
            out.append(P([T(item["text"], marks)]))
        elif kind == "bullet":
            sub = item.get("sub") or []
            nested = (
                bullet_list([list_item([T(s)]) for s in sub]) if sub else None
            )
            out.append(bullet_list([list_item([T(item["text"])], nested)]))
        else:
            raise ValueError(f"unknown body node type: {kind}")
    return out


def rich_panel(panel):
    content = [H(3, panel["heading"], bold=True)]
    content.extend(expand_body_nodes(panel.get("body", [])))
    return info_panel(content)


# ---------- ticket row renderers ----------

def ticket_link(key, jira_base_url):
    return T(
        key,
        [
            {"type": "link", "attrs": {"href": f"{jira_base_url}{key}"}},
            {"type": "em"},
        ],
    )


CURRENT_COL_WIDTHS = [231, 119, 149, 536, 119, 125, 139, 150]
NEXT_COL_WIDTHS = [360, 150, 779, 149, 360]
TABLE_WIDTH = 1800


def current_row(t, cfg):
    done_text = "DONE" if t["status_name"] == "Complete" else "NOT DONE"
    done_color = "green" if t["status_name"] == "Complete" else "red"
    jc = cfg["status_colors"].get(t["status_name"], "neutral")
    rtc = cfg["released_to_prod_colors"].get(t["released_to_prod"], "neutral")
    speaker = t.get("speaker", "")
    team_bg = cfg["team_backgrounds"].get(t["team"])
    w = CURRENT_COL_WIDTHS
    return row(
        [
            TC([P([T(t["goal_text"], [{"type": "strong"}])])], colwidth=w[0]),
            TC([P([T(t["team"])])], bg=team_bg, colwidth=w[1]),
            TC([P([T(speaker)]) if speaker else P()], colwidth=w[2]),
            TC([P([T(t["outcome"], [{"type": "em"}])])], colwidth=w[3]),
            TC([P([ticket_link(t["key"], cfg["jira_base_url"])])], colwidth=w[4]),
            TC([P([stat(done_text, done_color)]), P([stat(t["status_name"], jc)])], colwidth=w[5]),
            TC([P()], colwidth=w[6]),
            TC([P([stat(t["released_to_prod"], rtc)])], colwidth=w[7]),
        ]
    )


def next_row(t, cfg):
    team_bg = cfg["team_backgrounds"].get(t["team"])
    if isinstance(t.get("outcome_nodes"), list):
        outcome_content = t["outcome_nodes"]
    else:
        outcome_content = [P([T(t["outcome"], [{"type": "em"}])])]
    w = NEXT_COL_WIDTHS
    return row(
        [
            TC([P([T(t["goal_text"], [{"type": "strong"}])])], colwidth=w[0]),
            TC([P([T(t["team"])])], bg=team_bg, colwidth=w[1]),
            TC(outcome_content, colwidth=w[2]),
            TC([P([ticket_link(t["key"], cfg["jira_base_url"])])], colwidth=w[3]),
            TC([P()], colwidth=w[4]),
        ]
    )


CURRENT_HEADERS = [
    "Goal",
    "Team",
    "Speaker",
    "Impact / Outcome",
    "Ticket #",
    "Goal Status",
    "Target Release",
    "Released to Prod",
]
NEXT_HEADERS = ["Goal", "Team", "Outcome", "Ticket #", "Feedback"]


def stubs_block():
    return bullet_list(
        [
            list_item([T("Demo:")], bullet_list([list_item([])])),
            list_item([T("Feedback:")], bullet_list([list_item([])])),
        ]
    )


def group_by_category(tickets):
    g = {}
    for t in tickets:
        g.setdefault(t["category"], []).append(t)
    return g


# ---------- document assembly ----------

def build_document(data):
    cfg = data["config"]
    es = data["ending_sprint"]
    ns = data["next_sprint"]
    rd = data["review_date"]
    cur = data["current_sprint_tickets"]
    nxt = data["next_sprint_tickets"]

    cur_g = group_by_category(cur)
    nxt_g = group_by_category(nxt)

    content = [
        H(1, f"Sprint {es}"),
        P([T(rd, [{"type": "strong"}])]),
    ]

    for panel in data.get("intro_panels", []):
        content.append(rich_panel(panel))

    def current_header_row():
        return row(
            [TH(h, colwidth=CURRENT_COL_WIDTHS[i]) for i, h in enumerate(CURRENT_HEADERS)]
        )

    def next_header_row():
        return row(
            [TH(h, colwidth=NEXT_COL_WIDTHS[i]) for i, h in enumerate(NEXT_HEADERS)]
        )

    content.append(heading_only_panel(cfg["spotlight_heading"]))
    content.append(
        tbl(
            [
                current_header_row(),
                row(
                    [
                        TC([P()], colwidth=CURRENT_COL_WIDTHS[i])
                        for i in range(len(CURRENT_HEADERS))
                    ]
                ),
            ],
            width=TABLE_WIDTH,
        )
    )

    content.append(H(2, cfg["current_sprint_h2"]))
    for cat in cfg["current_sprint_category_order"]:
        if cat not in cur_g:
            continue
        content.append(heading_only_panel(cat))
        content.append(
            tbl(
                [current_header_row()] + [current_row(t, cfg) for t in cur_g[cat]],
                width=TABLE_WIDTH,
            )
        )
        content.append(stubs_block())

    content.append({"type": "rule"})
    content.append(H(2, cfg["next_sprint_h2_fmt"].format(ns)))

    for cat in cfg["next_sprint_category_order"]:
        if cat not in nxt_g:
            continue
        content.append(heading_only_panel(cat))
        content.append(
            tbl(
                [next_header_row()] + [next_row(t, cfg) for t in nxt_g[cat]],
                width=TABLE_WIDTH,
            )
        )

    if data.get("outro_panels"):
        content.append({"type": "rule"})
        for panel in data["outro_panels"]:
            content.append(rich_panel(panel))

    return {"type": "doc", "version": 1, "content": content}


def main():
    # Two invocation modes:
    #   build_adf.py <data.json> <out.json>
    #     - Single combined input file.
    #   build_adf.py --parts <meta.json> <current.json> <next.json> <out.json>
    #     - Split inputs. meta.json holds everything except the two ticket arrays;
    #       current.json and next.json each hold a bare array of ticket dicts.
    argv = sys.argv[1:]
    if len(argv) == 2:
        data = json.loads(open(argv[0]).read())
        out_path = argv[1]
    elif len(argv) == 5 and argv[0] == "--parts":
        meta = json.loads(open(argv[1]).read())
        current = json.loads(open(argv[2]).read())
        nxt = json.loads(open(argv[3]).read())
        data = dict(meta)
        data["current_sprint_tickets"] = current
        data["next_sprint_tickets"] = nxt
        out_path = argv[4]
    else:
        print(
            "usage:\n"
            "  build_adf.py <data.json> <out.json>\n"
            "  build_adf.py --parts <meta.json> <current.json> <next.json> <out.json>",
            file=sys.stderr,
        )
        sys.exit(2)

    doc = build_document(data)
    with open(out_path, "w") as f:
        f.write(json.dumps(doc))
    print(
        f"Wrote {out_path}: {len(doc['content'])} nodes, "
        f"{len(data['current_sprint_tickets'])} cur, "
        f"{len(data['next_sprint_tickets'])} nxt"
    )


if __name__ == "__main__":
    main()
