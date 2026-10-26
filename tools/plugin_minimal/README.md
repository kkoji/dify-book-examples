# plugin_minimal: ツールプラグインの最小例

`dify plugin init --quick --category tool --language python` の雛形を元に、拠点の受付時間を返すツール `office_hours` を 1 つだけ持たせたもの。構成は `manifest.yaml`、`provider/`、`tools/`、`main.py`、`requirements.txt`。

## パッケージ化

```bash
cd examples/dify-for-code-first-engineers/tools
dify plugin package ./plugin_minimal -o office_hours.difypkg
```

`dify` CLI は macOS なら `brew tap langgenius/dify && brew install dify`、または dify-plugin-daemon の Releases にあるバイナリ(`dify-plugin-darwin-arm64` など)を使う。生成した `.difypkg` はリポジトリに含めない(scratchpad など別の場所に出力する)。

## インストール

セルフホストは `FORCE_VERIFYING_SIGNATURE=true` が既定なので、未署名の `.difypkg` はそのままでは拒否される。検証環境で試すなら `docker/.env` で `FORCE_VERIFYING_SIGNATURE=false` にするか、第三者署名を設定する(本文を参照)。

## 検証

- 2026-10-03、dify CLI v0.6.10(dify-plugin-daemon 0.6.10 の Releases バイナリ)、dify_plugin 0.9.1、Python 3.12.10
- `dify plugin package` でパッケージ化できることまで確認。Dify へのインストールと実行は著者確認待ち
