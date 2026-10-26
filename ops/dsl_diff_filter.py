#!/usr/bin/env python3
"""Dify DSL(YAML)からレイアウト項目を落として、意味のある差分だけを見るための textconv。

git の diff ドライバとして使う(ops/gitattributes.example を参照)。
    git config diff.dify-dsl.textconv "python3 ops/dsl_diff_filter.py"

落とすもの(キャンバス上の見た目にしか影響しないキー。Dify 1.17.1 でノードを動かすと position / positionAbsolute だけが変わることを実測した):
  nodes[]: position, positionAbsolute, width, height, selected, sourcePosition, targetPosition, zIndex
  nodes[].data: selected
  edges[]: zIndex
  graph: viewport
出力はキーをソートした YAML。リポジトリに置く DSL 自体は書き換えない。

依存: PyYAML(python/requirements.txt で固定)
"""
import sys

import yaml

NODE_LAYOUT_KEYS = {
    "position",
    "positionAbsolute",
    "width",
    "height",
    "selected",
    "sourcePosition",
    "targetPosition",
    "zIndex",
}
NODE_DATA_LAYOUT_KEYS = {"selected"}
EDGE_LAYOUT_KEYS = {"zIndex"}


def strip_layout(doc: dict) -> dict:
    graph = doc.get("workflow", {}).get("graph")
    if not isinstance(graph, dict):
        return doc
    graph.pop("viewport", None)
    for node in graph.get("nodes", []):
        for key in NODE_LAYOUT_KEYS:
            node.pop(key, None)
        data = node.get("data")
        if isinstance(data, dict):
            for key in NODE_DATA_LAYOUT_KEYS:
                data.pop(key, None)
    for edge in graph.get("edges", []):
        for key in EDGE_LAYOUT_KEYS:
            edge.pop(key, None)
    return doc


def main(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        sys.stdout.write(open(path, encoding="utf-8").read())
        return
    yaml.safe_dump(strip_layout(doc), sys.stdout, allow_unicode=True, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1])
