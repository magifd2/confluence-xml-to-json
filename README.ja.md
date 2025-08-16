# Confluence XML to JSON Converter

ConfluenceからエクスポートされたXMLデータをJSON形式に変換し、必要に応じて添付ファイルを復元するPythonスクリプトです。

## 機能

- Confluence XMLエクスポートファイル (`entities.xml` など) の解析
- ページ、ブログ投稿、カスタムコンテンツの抽出
- ユーザー、ラベル、コンテンツプロパティなどの関連情報のマッピング
- 添付ファイルの復元と、JSONデータへのパスの記録
- 構造化されたJSON形式での出力

## インストール

このスクリプトを実行するには、`lxml` ライブラリが必要です。以下のコマンドでインストールできます。

```bash
pip3 install lxml
```

**macOSユーザーへの注意:**
macOSでは、`python` コマンドがPython 2を指す場合があります。Python 3を使用するには `python3` および `pip3` を使うことを推奨します。また、システム全体のPythonインストールとの競合を避けるため、仮想環境（`venv` など）の使用を強く推奨します。

`venv` を使用した例:
```bash
python3 -m venv venv
source venv/bin/activate
pip3 install lxml
```

## 使用方法

スクリプトはコマンドライン引数を受け付けます。

```bash
python conv.py <入力XMLファイル> [オプション]
```

### 引数

- `<入力XMLファイル>`: 必須。解析するConfluenceのXMLエクスポートファイル (例: `entities.xml`)

### オプション

- `-o`, `--output <ファイル名>`: 出力するJSONファイル名 (デフォルト: `confluence_data.json`)
- `-a`, `--attachments-dir <ディレクトリパス>`: Confluenceからエクスポートされた添付ファイルが格納されているディレクトリのパス。通常はXMLファイルと同じ階層にある `attachments` ディレクトリなどを指定します。
- `-r`, `--restore-dir <ディレクトリパス>`: 添付ファイルを復元して格納する先のディレクトリパス。このオプションを使用するには `--attachments-dir` も指定する必要があります。
- `--debug`: デバッグ情報を有効にします。

### 例

1. **XMLをJSONに変換するだけの場合:**
   ```bash
   python conv.py entities.xml
   ```

2. **出力ファイル名を指定する場合:**
   ```bash
   python conv.py entities.xml -o my_confluence_data.json
   ```

3. **添付ファイルを復元する場合:**
   Confluenceのエクスポートデータに `attachments` ディレクトリが含まれている場合、そのパスを指定します。
   ```bash
   python conv.py entities.xml -a ./attachments -r ./restored_attachments
   ```
   これにより、`./attachments` ディレクトリ内の添付ファイルが `./restored_attachments` ディレクトリに復元されます。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細については [LICENSE](LICENSE) ファイルを参照してください。
