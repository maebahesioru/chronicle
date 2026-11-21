"""One-folder player: index.html with inline CSS and JS, relative audio only.

The build is deliberately network-free. Every byte the page needs ships in
the folder: styles, script, chapter data, and the narration files. Commit
messages that happen to contain a URL are defanged (a zero-width space after
the scheme colon) so a release folder contains no fetchable external
reference at all.
"""

from __future__ import annotations

import json
import os
from html import escape

from .i18n import t

ZWSP = chr(8203)


def _defang(text: str) -> str:
    text = str(text)
    text = text.replace("https://", "https:" + ZWSP + "//")
    text = text.replace("http://", "http:" + ZWSP + "//")
    return text


def _esc(text) -> str:
    return _defang(escape(str(text), quote=True))


def _chip(kind: str, value: str, href: str) -> str:
    return (
        '<a class="cite cite-' + kind + '" href="' + href + '">' + _esc(value) + "</a>"
    )


def _sentence_html(pairs, chapter_index: int, anchors: dict) -> str:
    parts: list[str] = []
    for text, kind, value in pairs:
        if not kind:
            parts.append(_esc(text))
            continue
        value = str(value)
        if kind == "sha":
            href = anchors.get(("sha", value.lower())) or anchors.get(("sha", value))
        elif kind == "path":
            href = anchors.get(("path", value))
        else:
            href = anchors.get(("issue", value))
        if href:
            parts.append(_chip(kind, value, href))
        else:
            parts.append(_esc(value))
    return "".join(parts)


def _file_rows(chapter: dict, chapter_index: int) -> str:
    rows: list[str] = []
    for pos, item in enumerate(chapter.get("files") or []):
        added, deleted = item.get("added") or 0, item.get("deleted") or 0
        total = max(1, added + deleted)
        width_add = int(round(100.0 * added / total))
        rows.append(
            '<tr id="fv-%d-%d"><td class="path">%s</td>'
            '<td class="num add">+%d</td><td class="num del">-%d</td>'
            '<td class="bar"><span class="bar-add" style="width:%d%%"></span>'
            '<span class="bar-del" style="width:%d%%"></span></td>'
            '<td class="num">%d</td></tr>'
            % (
                chapter_index,
                pos,
                _esc(item.get("path", "")),
                added,
                deleted,
                width_add,
                100 - width_add,
                item.get("commits") or 0,
            )
        )
    if not rows:
        return ""
    head = (
        "<table class=\"files\"><thead><tr><th>%s</th><th>+</th><th>-</th>"
        "<th></th><th>%s</th></tr></thead><tbody>" % (t("files", chapter.get("lang", "en")), t("commits", chapter.get("lang", "en")))
    )
    return head + "".join(rows) + "</tbody></table>"


def _commit_rows(chapter: dict) -> str:
    rows: list[str] = []
    for commit in chapter.get("commits") or []:
        rows.append(
            '<li id="cm-%s"><code class="sha">%s</code>'
            '<span class="subject">%s</span>'
            '<span class="who">%s</span><span class="when">%s</span></li>'
            % (
                _esc(commit.get("short", "")),
                _esc(commit.get("short", "")),
                _esc(commit.get("subject", "")),
                _esc(commit.get("author", "")),
                _esc((commit.get("date") or "")[:10]),
            )
        )
    return '<ol class="commits">' + "".join(rows) + "</ol>" if rows else ""


def _diff_line(line: str) -> str:
    if line.startswith("+++") or line.startswith("---"):
        cls = "meta"
    elif line.startswith("+"):
        cls = "add"
    elif line.startswith("-"):
        cls = "del"
    elif line.startswith("@@"):
        cls = "hunk"
    elif line.startswith("diff ") or line.startswith("index "):
        cls = "meta"
    else:
        cls = "ctx"
    return '<span class="l ' + cls + '">' + _esc(line) + "</span>"


def _diff_block(chapter: dict, chapter_index: int, lang: str) -> str:
    blocks = chapter.get("diff") or []
    if not blocks:
        return ""
    tabs: list[str] = []
    panes: list[str] = []
    for pos, block in enumerate(blocks):
        active = " is-active" if pos == 0 else ""
        tabs.append(
            '<button class="tab%s" data-pane="dv-%d-%d" type="button">%s</button>'
            % (active, chapter_index, pos, _esc(block.get("path", "")))
        )
        lines = "".join(_diff_line(line) for line in block.get("lines") or [])
        panes.append(
            '<pre class="diff%s" id="dv-%d-%d" data-sha="%s"><code>%s</code></pre>'
            % (active, chapter_index, pos, _esc(block.get("sha", "")), lines)
        )
    return (
        '<div class="diffwrap"><div class="tabs">'
        + "".join(tabs)
        + '</div><div class="panes">'
        + "".join(panes)
        + "</div></div>"
    )


def _chapter_html(chapter: dict, lang: str) -> str:
    index = chapter["index"]
    anchors: dict = {}
    for pos, item in enumerate(chapter.get("files") or []):
        anchors[("path", item.get("path", ""))] = "#fv-%d-%d" % (index, pos)
    for commit in chapter.get("commits") or []:
        short = (commit.get("short") or "").lower()
        anchors[("sha", short)] = "#cm-" + (commit.get("short") or "")
        anchors[("sha", commit.get("sha", "").lower())] = "#cm-" + (commit.get("short") or "")
    for issue in chapter.get("issues") or []:
        anchors[("issue", "#" + str(issue))] = "#ev-issues-%d" % index

    summary_items: list[str] = []
    for sentence in chapter.get("sentences_annotated") or []:
        summary_items.append("<li>" + _sentence_html(sentence, index, anchors) + "</li>")

    audio = chapter.get("audio")
    if audio:
        play = (
            '<button class="play" type="button" data-chapter="%d" aria-label="%s">'
            '<span class="glyph">&#9654;</span></button>' % (index, _esc(t("play", lang)))
        )
        badge = ""
        if chapter.get("audio_engine") == "silence":
            badge = '<span class="badge warn">' + _esc(t("no_audio", lang)) + "</span>"
    else:
        play = ""
        badge = '<span class="badge warn">' + _esc(t("no_audio", lang)) + "</span>"

    source_label = chapter.get("source_label") or chapter.get("source") or ""
    kind = chapter.get("kind") or "other"
    meta_bits = [
        '<span class="badge kind">' + _esc(kind) + "</span>",
        '<span class="badge src">' + _esc(source_label) + "</span>",
        '<span class="badge">' + _esc(t("commits", lang)) + ": " + str(len(chapter.get("commits") or [])) + "</span>",
        '<span class="badge">+' + str(chapter.get("added") or 0) + " / -" + str(chapter.get("deleted") or 0) + "</span>",
    ]
    if chapter.get("audio") and chapter.get("audio_duration"):
        meta_bits.append('<span class="badge">' + str(chapter.get("audio_duration")) + "s</span>")

    issues_block = ""
    issues = chapter.get("issues") or []
    if issues:
        issues_block = (
            '<div class="issues" id="ev-issues-%d"><span class="label">%s</span> %s</div>'
            % (index, _esc(t("issues", lang)), " ".join(_esc("#" + str(i)) for i in issues))
        )

    why = chapter.get("why") or ""
    why_block = (
        '<details class="why"><summary>' + _esc(t("why", lang)) + "</summary><p>"
        + _esc(why) + "</p></details>"
        if why else ""
    )

    return (
        '<section class="chapter" id="ch-%d" data-index="%d" data-audio="%s">'
        '<div class="ch-head"><div class="ch-num">%02d</div><div class="ch-title">'
        "<h2>%s</h2><p class=\"ch-meta\">%s</p></div></div>"
        '<div class="say">%s%s<div class="prose"><ol class="summary">%s</ol></div></div>'
        "%s"
        '<div class="evidence"><h3>%s</h3>%s<h3>%s</h3>%s%s</div>'
        '<div class="diffs"><h3>%s</h3>%s</div>'
        "</section>"
        % (
            index,
            index,
            _esc(audio or ""),
            index,
            _esc(chapter.get("title", "")),
            "".join(meta_bits),
            play,
            badge,
            "".join(summary_items),
            why_block,
            _esc(t("evidence", lang)),
            _file_rows(chapter, index),
            _esc(t("commits", lang)),
            _commit_rows(chapter),
            issues_block,
            _esc(t("diff", lang)),
            _diff_block(chapter, index, lang),
        )
    )


def render_html(payload: dict, lang: str = "en") -> str:
    meta = payload.get("meta") or {}
    chapters = payload.get("chapters") or []
    toc: list[str] = []
    for chapter in chapters:
        toc.append(
            '<li><a href="#ch-%d"><span class="n">%02d</span>'
            '<span class="ttl">%s</span><span class="k">%s</span></a></li>'
            % (
                chapter["index"],
                chapter["index"],
                _esc(chapter.get("title", "")),
                _esc(chapter.get("kind", "")),
            )
        )
    body = "".join(_chapter_html(chapter, lang) for chapter in chapters)
    if not body:
        body = '<p class="empty">' + _esc(t("empty", lang)) + "</p>"

    range_bits = []
    if meta.get("since"):
        range_bits.append(_esc(t("since", lang)) + " " + _esc(meta["since"]))
    if meta.get("first_date"):
        range_bits.append(_esc(meta["first_date"]) + " &rarr; " + _esc(meta.get("last_date", "")))
    if meta.get("head"):
        range_bits.append(_esc(t("head", lang)) + " " + _esc(meta["head"]))

    data = json.dumps(payload, ensure_ascii=False).replace("</", "<" + chr(92) + "/")
    data = _defang(data)

    html = TEMPLATE
    replacements = {
        "__LANG__": _defang(lang),
        "__TITLE__": _esc(meta.get("title", "Chronicle")),
        "__TAGLINE__": _esc(meta.get("tagline", "")),
        "__REPO__": _esc(meta.get("repo", "")),
        "__RANGE__": " ・ ".join(range_bits) if lang == "ja" else " ・ ".join(range_bits),
        "__COUNTS__": _esc(
            t("chapters", lang) + " " + str(len(chapters)) + " ・ " + t("commits", lang) + " " + str(meta.get("commits", 0))
        ),
        "__ENGINE__": _esc(meta.get("engine_label", "")),
        "__BUILT__": _esc(t("built", lang) + " " + str(meta.get("generated", ""))),
        "__TOC__": "".join(toc),
        "__BODY__": body,
        "__PLAY_ALL__": _esc(t("play_all", lang)),
        "__FOOTER__": _esc(meta.get("footer", "")),
        "__DATA__": data,
        "__CH__": _esc(t("chapters", lang)),
        "__LANG_LABEL__": "JA" if lang == "ja" else "EN",
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


def write_site(payload: dict, out_dir: str, lang: str = "en") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_html(payload, lang))
    return path


TEMPLATE = r"""<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chronicle &mdash; hear why your code exists</title>
<style>
:root{--ink:#12100e;--paper:#1b1714;--paper2:#241f1a;--line:#3a322a;--text:#efe6d8;
--dim:#b3a693;--gold:#d9a441;--green:#79c07a;--red:#e07a6a;--blue:#7fa9d9}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--ink);color:var(--text);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans","Noto Sans JP",sans-serif;
line-height:1.6;font-size:16px}
code,.sha,.diff{font-family:"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}
a{color:var(--gold);text-decoration:none}
a:hover{text-decoration:underline}
header.top{border-bottom:1px solid var(--line);padding:28px 32px 20px;
background:linear-gradient(180deg,#191512,#12100e)}
.brand{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.brand h1{margin:0;font-size:26px;letter-spacing:.12em;text-transform:uppercase;font-weight:600}
.brand .tag{color:var(--dim);font-size:14px;font-style:italic}
.meta{display:flex;flex-wrap:wrap;gap:8px 22px;margin:16px 0 0;padding:0;list-style:none;
color:var(--dim);font-size:13px}
.meta li code{color:var(--text);background:var(--paper2);padding:1px 6px;border-radius:4px}
main{display:grid;grid-template-columns:300px minmax(0,1fr);gap:0;align-items:start}
nav.rail{position:sticky;top:0;max-height:100vh;overflow:auto;border-right:1px solid var(--line);
padding:22px 18px;background:#151210}
nav.rail .railhead{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);
margin-bottom:12px}
ol.toc{list-style:none;margin:0;padding:0}
ol.toc a{display:grid;grid-template-columns:30px 1fr auto;gap:8px;align-items:baseline;
padding:10px 8px;border-left:2px solid transparent;color:var(--text);font-size:14px}
ol.toc a:hover,ol.toc a.is-current{background:var(--paper2);border-left-color:var(--gold);text-decoration:none}
ol.toc .n{color:var(--gold);font-weight:600}
ol.toc .ttl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
ol.toc .k{font-size:11px;color:var(--dim);border:1px solid var(--line);border-radius:10px;padding:0 7px}
#playall{margin-top:18px;width:100%;padding:10px;border:1px solid var(--gold);border-radius:6px;
background:transparent;color:var(--gold);cursor:pointer;font-size:13px;letter-spacing:.08em}
#playall:hover{background:var(--gold);color:#171410}
.story{padding:28px 40px 80px;max-width:980px}
.chapter{border-bottom:1px solid var(--line);padding:26px 0 34px;scroll-margin-top:12px}
.chapter.is-active{background:linear-gradient(90deg,rgba(217,164,65,.05),transparent 60%)}
.ch-head{display:flex;gap:16px;align-items:flex-start}
.ch-num{font-size:34px;line-height:1;color:var(--gold);opacity:.5;font-weight:600;
min-width:56px;text-align:right;padding-top:2px}
.ch-title h2{margin:0 0 6px;font-size:22px;font-weight:600}
.ch-meta{display:flex;gap:8px;flex-wrap:wrap;margin:0}
.badge{font-size:11px;letter-spacing:.06em;border:1px solid var(--line);border-radius:10px;
padding:1px 8px;color:var(--dim);text-transform:uppercase}
.badge.kind{color:var(--gold);border-color:var(--gold)}
.badge.src{color:var(--blue);border-color:var(--blue)}
.badge.warn{color:var(--dim)}
.say{display:grid;grid-template-columns:46px 1fr;gap:14px;margin-top:20px}
.play{width:46px;height:46px;border-radius:50%;border:1px solid var(--gold);background:transparent;
color:var(--gold);font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.play:hover{background:var(--gold);color:#171410}
.play.playing{background:var(--gold);color:#171410}
.badge.warn{align-self:start;margin-top:2px;grid-column:1;font-size:10px;text-align:center}
.prose{grid-column:2}
ol.summary{list-style:none;margin:0;padding:0;font-size:18px;line-height:1.75}
ol.summary li{margin-bottom:8px}
.cite{display:inline-block;padding:0 5px;margin:0 1px;border-radius:4px;font-size:.82em;
font-family:"SF Mono",Menlo,Consolas,monospace;background:rgba(217,164,65,.12);
border:1px solid rgba(217,164,65,.35);color:#f0c472;vertical-align:baseline}
.cite-path{border-color:rgba(127,169,217,.4);background:rgba(127,169,217,.12);color:#a9c8ea}
.cite-issue{border-color:rgba(121,192,122,.4);background:rgba(121,192,122,.12);color:#a5d6a5}
.why{margin:16px 0 0;border-left:2px solid var(--line);padding-left:14px;color:var(--dim);font-size:14px}
.why summary{cursor:pointer;color:var(--dim);letter-spacing:.04em}
.why p{margin:8px 0 0;color:var(--text)}
.evidence h3,.diffs h3{font-size:12px;letter-spacing:.18em;text-transform:uppercase;
color:var(--dim);margin:26px 0 10px;font-weight:600}
table.files{width:100%;border-collapse:collapse;font-size:13px}
table.files th{text-align:left;color:var(--dim);font-weight:500;border-bottom:1px solid var(--line);
padding:4px 8px;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
table.files td{border-bottom:1px dotted #2c2620;padding:6px 8px;vertical-align:middle}
table.files td.path{font-family:"SF Mono",Menlo,Consolas,monospace;word-break:break-all}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;width:70px}
td.add{color:var(--green)}td.del{color:var(--red)}
td.bar{width:120px}
td.bar span{display:inline-block;height:6px;vertical-align:middle;border-radius:2px}
.bar-add{background:var(--green)}.bar-del{background:var(--red)}
ol.commits{list-style:none;margin:0;padding:0;font-size:13px}
ol.commits li{display:grid;grid-template-columns:90px 1fr auto 90px;gap:10px;padding:5px 0;
border-bottom:1px dotted #2c2620}
ol.commits .sha{color:var(--gold)}
ol.commits .who{color:var(--dim)}
ol.commits .when{color:var(--dim);text-align:right}
.issues{font-size:13px;color:var(--dim);margin-top:12px}
.issues .label{letter-spacing:.12em;text-transform:uppercase;font-size:11px;margin-right:8px}
.tabs{display:flex;gap:2px;overflow:auto;border-bottom:1px solid var(--line)}
.tab{background:transparent;border:0;border-bottom:2px solid transparent;color:var(--dim);
padding:8px 10px;cursor:pointer;font-size:12px;font-family:"SF Mono",Menlo,Consolas,monospace;
white-space:nowrap}
.tab.is-active{color:var(--gold);border-bottom-color:var(--gold)}
pre.diff{display:none;margin:0;padding:12px 14px;background:#0d0b0a;border:1px solid var(--line);
border-top:0;overflow:auto;font-size:12.5px;line-height:1.55;max-height:420px}
pre.diff.is-active{display:block}
pre.diff .l{display:block;white-space:pre}
.l.add{color:var(--green);background:rgba(121,192,122,.07)}
.l.del{color:var(--red);background:rgba(224,122,106,.07)}
.l.hunk{color:var(--blue);margin-top:6px}
.l.meta{color:#7d7264}
.l.ctx{color:#cfc4b4}
footer{border-top:1px solid var(--line);color:var(--dim);font-size:12px;padding:22px 32px;
display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap}
.empty{color:var(--dim);font-style:italic}
@media (max-width:860px){
main{grid-template-columns:1fr}
nav.rail{position:static;max-height:none;border-right:0;border-bottom:1px solid var(--line)}
.story{padding:20px 18px 60px}
.say{grid-template-columns:1fr}
.prose{grid-column:1}
ol.commits li{grid-template-columns:70px 1fr}
ol.commits .who,ol.commits .when{display:none}
}
@media print{nav.rail{display:none}body{background:#fff;color:#000}}
</style>
</head>
<body>
<header class="top">
<div class="brand"><h1>Chronicle</h1><span class="tag">__TAGLINE__</span></div>
<ul class="meta">
<li><code>__REPO__</code></li>
<li>__COUNTS__</li>
<li>__RANGE__</li>
<li>__ENGINE__</li>
<li>__BUILT__</li>
</ul>
</header>
<main>
<nav class="rail" aria-label="__CH__">
<div class="railhead">__CH__</div>
<ol class="toc">__TOC__</ol>
<button id="playall" type="button">&#9654; __PLAY_ALL__</button>
</nav>
<div class="story">__BODY__</div>
</main>
<footer><span>__FOOTER__</span><span>Chronicle &mdash; offline folder, no network, no tracking.</span></footer>
<audio id="player" preload="none"></audio>
<script type="application/json" id="chronicle-data">__DATA__</script>
<script>
(function(){
"use strict";
var player=document.getElementById("player");
var chapters=Array.prototype.slice.call(document.querySelectorAll(".chapter"));
var tocLinks=Array.prototype.slice.call(document.querySelectorAll("ol.toc a"));
var playAll=document.getElementById("playall");
var current=-1,queue=false;
function chapterByIndex(i){return chapters[i]||null;}
function setCurrent(i){
  current=i;
  chapters.forEach(function(el,pos){el.classList.toggle("is-active",pos===i);});
  tocLinks.forEach(function(el,pos){el.classList.toggle("is-current",pos===i);});
}
function play(i,chain){
  var el=chapterByIndex(i);
  if(!el){queue=false;playAll.textContent="\u25B6 "+playAll.getAttribute("data-label");return;}
  var src=el.getAttribute("data-audio");
  if(!src){play(i+1,chain);return;}
  queue=!!chain;
  setCurrent(i);
  player.src=src;
  var button=el.querySelector(".play");
  chapters.forEach(function(other){var b=other.querySelector(".play");if(b){b.classList.remove("playing");b.querySelector(".glyph").innerHTML="&#9654;";}});
  if(button){button.classList.add("playing");button.querySelector(".glyph").innerHTML="&#10074;&#10074;";}
  player.play().catch(function(){});
  el.scrollIntoView({behavior:"smooth",block:"start"});
}
function stop(){
  player.pause();
  queue=false;
  chapters.forEach(function(el){var b=el.querySelector(".play");if(b){b.classList.remove("playing");b.querySelector(".glyph").innerHTML="&#9654;";}});
  playAll.textContent="\u25B6 "+playAll.getAttribute("data-label");
  setCurrent(-1);
}
chapters.forEach(function(el,pos){
  var button=el.querySelector(".play");
  if(button){button.addEventListener("click",function(){
    if(current===pos&&!player.paused){stop();}else{play(pos,false);}
  });}
});
if(playAll){
  playAll.setAttribute("data-label",playAll.textContent.replace(/^\u25B6\s*/,""));
  playAll.addEventListener("click",function(){
    if(!player.paused){stop();return;}
    var first=chapters.findIndex(function(el){return !!el.getAttribute("data-audio");});
    if(first<0){return;}
    playAll.textContent="\u25A0 stop";
    play(first,true);
  });
}
player.addEventListener("ended",function(){
  if(queue){play(current+1,true);}
  else{stop();}
});
document.querySelectorAll(".tabs").forEach(function(group){
  var tabs=Array.prototype.slice.call(group.querySelectorAll(".tab"));
  var panes=Array.prototype.slice.call(group.parentNode.querySelectorAll("pre.diff"));
  tabs.forEach(function(tab){
    tab.addEventListener("click",function(){
      tabs.forEach(function(other){other.classList.remove("is-active");});
      panes.forEach(function(pane){pane.classList.remove("is-active");});
      tab.classList.add("is-active");
      var target=document.getElementById(tab.getAttribute("data-pane"));
      if(target){target.classList.add("is-active");}
    });
  });
});
document.addEventListener("keydown",function(event){
  if(event.target&&/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)){return;}
  var key=event.key;
  if(key==="j"||key==="ArrowDown"){event.preventDefault();var next=Math.min(chapters.length-1,current+1);setCurrent(next);if(chapters[next]){chapters[next].scrollIntoView({behavior:"smooth",block:"start"});}}
  if(key==="k"||key==="ArrowUp"){event.preventDefault();var prev=Math.max(0,current-1);setCurrent(prev);if(chapters[prev]){chapters[prev].scrollIntoView({behavior:"smooth",block:"start"});}}
  if(key===" "){event.preventDefault();if(current<0){return;}if(player.paused){play(current,false);}else{stop();}}
});
var observer=new IntersectionObserver(function(entries){
  entries.forEach(function(entry){
    if(entry.isIntersecting&&!player.paused===false){}
  });
},{threshold:0.6});
chapters.forEach(function(el){observer.observe(el);});
setCurrent(chapters.length?0:-1);
})();
</script>
</body>
</html>
"""
