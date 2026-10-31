#!/usr/bin/env python3
"""瀬戸内市例規集テキスト版の検索ツール（例規Q&Aスキル用）

setouchi_reiki.py が作った setouchi_reiki_out/reiki/ 以下の Markdown を、
条（または附則・別表などの見出し）単位で検索します。標準ライブラリのみ。

使い方:
    python search_reiki.py 育児休業 給与          # 条単位のキーワード検索（すべて含むもの）
    python search_reiki.py --any 公印 印章        # どれかを含むもの
    python search_reiki.py --titles 公印          # 例規名で探す
    python search_reiki.py --show r057RG00000845  # 1つの例規を全文表示
    python search_reiki.py --show 845 --article 第4条   # 特定の条だけ表示（附則 も指定可）
    python search_reiki.py --stats                # データの件数と内容現在

全角・半角の違い（数字・括弧など）は区別せずに検索します。
"""

import argparse
import glob
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
# スキルに同梱したときは data/、PCのフォルダでは setouchi_reiki_out/ を使う
DEFAULT_DATA = next((p for p in (os.path.join(HERE, "data"), os.path.join(HERE, "setouchi_reiki_out"))
                     if os.path.isdir(p)), os.path.join(HERE, "setouchi_reiki_out"))
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def nk(s):
    return unicodedata.normalize("NFKC", s).lower()


INDEX_NAME = "_search_index.json"


def _index_candidates(data_dir):
    """インデックスの置き場所。データフォルダが読み取り専用なら一時フォルダを使う。"""
    import hashlib
    import tempfile
    tag = hashlib.sha1(os.path.abspath(data_dir).encode("utf-8")).hexdigest()[:10]
    return [os.path.join(data_dir, INDEX_NAME),
            os.path.join(tempfile.gettempdir(), "setouchi_reiki_%s%s" % (tag, INDEX_NAME))]


def _load_packed(data_dir):
    """スキル同梱用の圧縮データ（data/reiki_XX.json.gz）を読む。"""
    import gzip
    docs = []
    for path in sorted(glob.glob(os.path.join(data_dir, "reiki_*.json.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for d in json.load(f):
                docs.append({"meta": d["meta"], "body": d["body"], "chunks": split_chunks(d["body"])})
    return docs


def load_docs(data_dir, rebuild=False):
    """検索用インデックス（1ファイル）があればそれを読む。無いか古ければ作り直す。"""
    if glob.glob(os.path.join(data_dir, "reiki_*.json.gz")):
        docs = _load_packed(data_dir)
        for d in docs:
            for c in d["chunks"]:
                c["norm"] = nk(c["text"])
        return docs
    csv_path = os.path.join(data_dir, "index.csv")
    csv_time = os.path.getmtime(csv_path) if os.path.exists(csv_path) else 0
    docs = None
    if not rebuild:
        for index_path in _index_candidates(data_dir):
            if os.path.exists(index_path) and os.path.getmtime(index_path) >= csv_time:
                try:
                    with open(index_path, encoding="utf-8") as f:
                        docs = json.load(f)
                    break
                except (OSError, ValueError):
                    docs = None
    if docs is None:
        docs = _read_markdown(data_dir)
        for index_path in (_index_candidates(data_dir) if docs else []):
            try:
                with open(index_path, "w", encoding="utf-8") as f:
                    json.dump(docs, f, ensure_ascii=False)
                break
            except OSError:
                continue  # 書き込めなくても検索はできる
    for d in docs:
        for c in d["chunks"]:
            c["norm"] = nk(c["text"])
    return docs


def _read_markdown(data_dir):
    docs = []
    for path in sorted(glob.glob(os.path.join(data_dir, "reiki", "*", "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        meta, body = {}, text
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                for line in text[4:end].splitlines():
                    m = re.match(r"^(\w+):\s*(.*)$", line)
                    if m and m.group(2) and m.group(2) != "[]":
                        try:
                            meta[m.group(1)] = json.loads(m.group(2))
                        except ValueError:
                            meta[m.group(1)] = m.group(2)
                body = text[end + 5:]
        meta["file"] = os.path.relpath(path, data_dir).replace(os.sep, "/")
        docs.append({"meta": meta, "body": body, "chunks": split_chunks(body)})
    return docs


def split_chunks(body):
    """本文を見出しごとのかたまりに分ける。親の見出し（章・節・附則）も path に持つ。"""
    chunks, stack = [], {}
    cur = {"heading": "（冒頭）", "path": [], "lines": []}
    in_toc = False
    for line in body.splitlines():
        m = HEADING.match(line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1:
                continue
            if cur["lines"] or cur["heading"] != "（冒頭）":
                chunks.append(cur)
            in_toc = text == "目次"
            stack = {k: v for k, v in stack.items() if k < level}
            cur = {"heading": text, "path": [stack[k] for k in sorted(stack)], "lines": []}
            if not in_toc:
                stack[level] = text
            continue
        if in_toc or not line.strip():
            continue
        cur["lines"].append(line)
    chunks.append(cur)
    return [{"heading": c["heading"], "path": c["path"], "text": "\n".join(c["lines"])}
            for c in chunks if c["heading"] != "目次"]


def label(doc, chunk):
    m = doc["meta"]
    where = " / ".join(chunk["path"] + [chunk["heading"]])
    return "%s（%s）%s" % (m.get("title", ""), m.get("number", ""), where)


def print_header(doc):
    m = doc["meta"]
    print("  種別: %s　施行: %s　体系: %s" % (m.get("kind", ""), m.get("effective", ""), m.get("taikei", "")))
    print("  URL: %s" % m.get("source", ""))
    print("  file: %s　id: %s" % (m.get("file", ""), m.get("id", "")))


def search(docs, terms, any_mode=False, limit=8, per_doc=3, chars=500):
    nterms = [nk(t) for t in terms if t.strip()]
    hits = []
    for d in docs:
        title = nk(d["meta"].get("title", ""))
        for c in d["chunks"]:
            head = nk(" ".join(c["path"] + [c["heading"]]))
            found = [t for t in nterms if t in c["norm"] or t in title or t in head]
            if not found or (not any_mode and len(found) < len(nterms)):
                continue
            score = sum(c["norm"].count(t) for t in nterms)
            score += sum(3 for t in nterms if t in title) + sum(5 for t in nterms if t in head)
            score += len(found) * 10  # --any のとき、多くの語を含むものを上に
            hits.append((score, d, c))
    hits.sort(key=lambda h: -h[0])
    shown, count = {}, 0
    total_docs = len({id(h[1]) for h in hits})
    print("検索語: %s（%s）→ %d箇所 / %d例規" % (" ".join(terms), "いずれか" if any_mode else "すべて",
                                              len(hits), total_docs))
    for score, d, c in hits:
        key = id(d)
        if shown.get(key, 0) >= per_doc:
            continue
        shown[key] = shown.get(key, 0) + 1
        count += 1
        print("\n[%d] %s" % (count, label(d, c)))
        print_header(d)
        text = c["text"]
        if chars and len(text) > chars:
            text = text[:chars] + "…（続きは --show %s --article で表示）" % d["meta"].get("id", "")
        print("  " + text.replace("\n", "\n  "))
        if count >= limit:
            break
    if len(hits) > count:
        print("\n（ほかに %d箇所あります。--limit を増やすか、語を足して絞り込んでください）" % (len(hits) - count))


def find_doc(docs, key):
    k = nk(key)
    exact = [d for d in docs if nk(d["meta"].get("id", "")) == k or nk(d["meta"].get("title", "")) == k]
    if exact:
        return exact
    if k.isdigit():
        return [d for d in docs if d["meta"].get("id", "").endswith(k.zfill(5)) or d["meta"].get("id", "").endswith(k)]
    return [d for d in docs if k in nk(d["meta"].get("title", ""))]


def show(docs, key, article=None):
    found = find_doc(docs, key)
    if not found:
        print("見つかりません: %s（--titles で例規名を探してください）" % key)
        return
    if len(found) > 1:
        print("候補が複数あります。id で指定してください:")
        for d in found[:30]:
            print("  %s　%s（%s）" % (d["meta"].get("id"), d["meta"].get("title"), d["meta"].get("number")))
        return
    d = found[0]
    m = d["meta"]
    print("%s（%s　%s）" % (m.get("title"), m.get("enacted"), m.get("number")))
    print_header(d)
    if m.get("history"):
        print("  沿革: " + " / ".join(m["history"]))
    if not article:
        print("\n" + d["body"].strip())
        return
    a = nk(article)
    pat = re.compile("^" + re.escape(a) + r"(?![の0-9])") if re.match(r"^第\d+条", a) else None
    sel = [c for c in d["chunks"]
           if (pat.match(nk(c["heading"])) if pat else a in nk(" ".join(c["path"] + [c["heading"]])))]
    if not sel:
        print("\n「%s」に当たる見出しがありません。見出し一覧:" % article)
        for c in d["chunks"]:
            print("  - " + " / ".join(c["path"] + [c["heading"]]))
        return
    for c in sel:
        print("\n■ " + " / ".join(c["path"] + [c["heading"]]))
        print(c["text"])


def titles(docs, terms):
    nterms = [nk(t) for t in terms]
    rows = [d for d in docs if all(t in nk(d["meta"].get("title", "")) for t in nterms)]
    print("例規名に「%s」を含むもの: %d件" % (" ".join(terms), len(rows)))
    for d in rows:
        m = d["meta"]
        print("  %s　%s（%s）施行:%s　%s" % (m.get("id"), m.get("title"), m.get("number"),
                                         m.get("effective", ""), m.get("taikei", "")))


def stats(docs, data_dir):
    as_of = next((d["meta"].get("as_of") for d in docs if d["meta"].get("as_of")), "不明")
    kinds = {}
    for d in docs:
        kinds[d["meta"].get("kind", "")] = kinds.get(d["meta"].get("kind", ""), 0) + 1
    print("データ: %s" % os.path.abspath(data_dir))
    print("収録: %d件　内容現在: %s" % (len(docs), as_of))
    print("種別: " + "、".join("%s %d" % (k or "不明", v) for k, v in sorted(kinds.items(), key=lambda x: -x[1])))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="瀬戸内市例規集テキスト版を検索します")
    ap.add_argument("terms", nargs="*", help="検索語（空白区切り）")
    ap.add_argument("--any", action="store_true", help="どれか1語を含めば対象にする")
    ap.add_argument("--titles", action="store_true", help="例規名だけを検索")
    ap.add_argument("--show", metavar="ID", help="例規を表示（id・id末尾の番号・例規名）")
    ap.add_argument("--article", help="--show と一緒に: 表示する条や見出し（例: 第4条、附則、別表）")
    ap.add_argument("--stats", action="store_true", help="件数と内容現在を表示")
    ap.add_argument("--limit", type=int, default=8, help="表示する箇所数（既定 8）")
    ap.add_argument("--per-doc", type=int, default=3, help="1つの例規から表示する最大箇所数（既定 3）")
    ap.add_argument("--chars", type=int, default=500, help="1箇所あたりの表示文字数（0で全文）")
    ap.add_argument("--data", default=DEFAULT_DATA, help="setouchi_reiki_out フォルダの場所")
    ap.add_argument("--rebuild", action="store_true", help="検索用インデックスを作り直す")
    a = ap.parse_args(argv)
    docs = load_docs(a.data, a.rebuild)
    if not docs:
        print("データが見つかりません: %s" % os.path.abspath(a.data))
        return 1
    if a.stats:
        stats(docs, a.data)
    elif a.show:
        show(docs, a.show, a.article)
    elif a.titles:
        titles(docs, a.terms)
    elif a.terms:
        search(docs, a.terms, a.any, a.limit, a.per_doc, a.chars)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # head などで出力を途中で切ったとき
        sys.exit(0)
