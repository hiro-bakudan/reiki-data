# 瀬戸内市例規集 テキストデータ（Claudeスキル用）

瀬戸内市例規集（Reiki-Base インターネット版）で公開されている例規を、条単位で検索できるように
テキスト化したデータです。Claude のスキル「setouchi-reiki-qa」が参照します。

- 出典: [瀬戸内市例規集](https://www1.g-reiki.net/setouchi/reiki_menu.html)
- 内容現在: 令和7年12月31日（収録 1,196件）
- 条例・規則等の本文は、著作権法第13条により著作権の対象外です。

## ファイル

| ファイル | 内容 |
| --- | --- |
| `reiki_01.json.gz` 〜 `reiki_13.json.gz` | 編ごとの例規データ（各例規の制定日・種別番号・沿革・元URLと本文Markdown） |
| `search_reiki.py` | 検索ツール（Python標準ライブラリのみ） |

```
python3 search_reiki.py --data . --stats
python3 search_reiki.py --data . 市営住宅 家賃 減免
python3 search_reiki.py --data . --show r057RG00000466 --article 第17条
```

## 注意

- 取得時点のデータです。それ以降の改正は反映されていません。正式な内容は必ず元URLの原本で確認してください。
- 別表は表の文字だけを簡略に残しています。様式・図はリンクのみです。
- 本データは非公式のものです。
