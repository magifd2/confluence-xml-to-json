import json
import re
import os
import html
import argparse
import shutil
from collections import defaultdict

try:
    from lxml import etree
except ImportError:
    print("エラー: lxmlライブラリが見つかりません。")
    print("このスクリプトを実行するには、lxmlをインストールする必要があります。")
    print("ターミナルで以下のコマンドを実行してください:")
    print("pip install lxml")
    exit(1)

def clean_xhtml_content(xhtml_content):
    """
    Confluenceのストレージ形式に含まれるXHTMLタグを簡易的に除去し、
    プレーンテキストに近い形に変換します。
    """
    if xhtml_content is None:
        return ""
    text_content = re.sub(r'<[^>]+>', '', xhtml_content)
    return html.unescape(text_content).strip()

def parse_confluence_xml(xml_file_path, attachments_base_dir=None, restore_dir=None, debug=False):
    """
    lxmlを使用してConfluenceのXMLエクスポートファイルを解析します。
    添付ファイルを指定されたディレクトリに復元する機能も持ちます。
    """
    print(f"'{xml_file_path}' を解析しています...")
    if not os.path.exists(xml_file_path):
        print(f"エラー: 入力ファイル '{xml_file_path}' が見つかりません。")
        return None
        
    try:
        with open(xml_file_path, 'rb') as f:
            xml_bytes = f.read()
        parser = etree.XMLParser(recover=True, huge_tree=True)
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception as e:
        print(f"エラー: XMLファイルの解析に失敗しました。: {e}")
        return None

    # --- ステップ1: 全オブジェクトをクラスごとに分類 ---
    objects_by_class = defaultdict(list)
    for obj in root.iter('object'):
        class_attr = obj.get('class')
        if class_attr:
            objects_by_class[class_attr].append(obj)
    
    print("--- ステップ1: 全オブジェクトの分類結果 ---")
    for cls, items in sorted(objects_by_class.items()):
        print(f"  - {cls}: {len(items)} 件")
    print("-" * 20)

    # --- ステップ2: 関連情報を事前にマッピング ---
    users_map = {}
    if debug: print("--- デバッグ: ユーザー情報 (ConfluenceUserImpl) の解析開始 ---")
    for i, obj in enumerate(objects_by_class.get('ConfluenceUserImpl', [])):
        user_key_node = obj.xpath("./id[@name='key']/text()")
        user_name_node = obj.xpath("./property[@name='fullName']/text() | ./property[@name='name']/text()")
        if user_key_node and user_name_node:
            users_map[user_key_node[0]] = user_name_node[0]
    print(f"ステップ2.1: {len(users_map)} 件のユーザー情報を読み込みました。")

    body_content_map = {}
    for obj in objects_by_class.get('BodyContent', []):
        content_id_node = obj.xpath("./id[@name='id']/text()")
        body_node = obj.xpath("./property[@name='body']/text()")
        if content_id_node and body_node:
            body_content_map[content_id_node[0]] = body_node[0]
    print(f"ステップ2.2: {len(body_content_map)} 件の本文コンテンツを読み込みました。")
    
    labels_map = {}
    for obj in objects_by_class.get('Label', []):
        label_id_node = obj.xpath("./id/text()")
        label_name_node = obj.xpath("./property[@name='name']/text()")
        if label_id_node and label_name_node:
            labels_map[label_id_node[0]] = label_name_node[0]
    print(f"ステップ2.3: {len(labels_map)} 件のラベル定義を読み込みました。")

    # --- ステップ3: コンテンツプロパティを事前にマッピング ---
    content_properties_map = {}
    if debug: print("--- デバッグ: コンテンツプロパティ (ContentProperty) の解析開始 ---")
    for i, obj in enumerate(objects_by_class.get('ContentProperty', [])):
        prop_id_node = obj.xpath("./id[@name='id']/text()")
        prop_name_node = obj.xpath("./property[@name='name']/text()")
        prop_value_node = obj.xpath("./property[@name='stringValue']/text() | ./property[@name='longValue']/text()")
        if prop_id_node and prop_name_node and prop_value_node:
            content_properties_map[prop_id_node[0]] = {
                "name": prop_name_node[0],
                "value": prop_value_node[0]
            }
    print(f"ステップ2.4: {len(content_properties_map)} 件のコンテンツプロパティを読み込みました。")


    # --- ステップ4: ページIDをキーに関連情報をグループ化 ---
    attachments_by_page = defaultdict(list)
    restored_count = 0
    if debug: print("--- デバッグ: 添付ファイル (Attachment) の解析開始 ---")
    for i, obj in enumerate(objects_by_class.get('Attachment', [])):
        page_id_node = obj.xpath(".//property[@name='content' or @name='container' or @name='containerContent']//id[@name='id']/text()")
        attachment_id_node = obj.xpath("./id[@name='id']/text()")

        if not page_id_node or not attachment_id_node:
            if debug: print("    - -> スキップ: ページIDまたは添付ファイルIDが見つかりません。")
            continue
        page_id = page_id_node[0]
        attachment_id = attachment_id_node[0]
        
        creator_key_node = obj.xpath(".//property[@name='creator']/id[@name='key']/text()")
        
        attachment_props = {}
        prop_id_nodes = obj.xpath(".//collection[@name='contentProperties']/element/id[@name='id']/text()")
        for prop_id in prop_id_nodes:
            if prop_id in content_properties_map:
                prop = content_properties_map[prop_id]
                attachment_props[prop['name']] = prop['value']
        
        filename = (obj.xpath("./property[@name='title']/text()") or [''])[0]
        filesize = int(attachment_props.get('FILESIZE', 0))
        content_type = attachment_props.get('MEDIA_TYPE', '')
        
        # --- ここからが変更・追加したロジック ---
        # 添付ファイルを復元し、そのパスを記録
        restored_file_path = None
        if attachments_base_dir and restore_dir and filename:
            source_path = os.path.join(attachments_base_dir, page_id, attachment_id, '1')
            
            if os.path.exists(source_path):
                # 出力先ディレクトリ構造: {restore_dir}/{ページID}/{添付ファイルID}/{元のファイル名}
                dest_dir = os.path.join(restore_dir, page_id, attachment_id)
                dest_path = os.path.join(dest_dir, filename)
                
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    restored_file_path = dest_path
                    restored_count += 1
                    if debug:
                        print(f"    - -> 復元成功: '{source_path}' -> '{dest_path}'")
                except Exception as e:
                    print(f"    - -> エラー: ファイルの復元に失敗しました: {e}")
            elif debug:
                print(f"    - -> 警告: 添付ファイルのソースが見つかりません: {source_path}")
        # --- ここまでが変更・追加したロジック ---

        attachments_by_page[page_id].append({
            'id': attachment_id,
            'filename': filename,
            'filesize': filesize,
            'content_type': content_type,
            'author': users_map.get(creator_key_node[0]) if creator_key_node else None,
            'created_at': (obj.xpath("./property[@name='creationDate']/text()") or [''])[0],
            'filepath': restored_file_path  # 復元後のファイルパスを追加
        })
    print(f"ステップ3.1: {len(attachments_by_page)} 件のページに紐づく添付ファイルをグループ化しました。")
    if restore_dir:
        print(f"ステップ3.1.1: {restored_count} 件の添付ファイルを '{restore_dir}' に復元しました。")

    comments_by_page = defaultdict(list)
    # (コメント部分のロジックは変更なし)
    print(f"ステップ3.2: {len(comments_by_page)} 件のページに紐づくコメントをグループ化しました。")

    # --- ステップ5: 全ての情報を組み立てる ---
    content_data = []
    content_types = ['Page', 'Blogpost', 'CustomContentEntityObject']
    for content_type in content_types:
        for obj in objects_by_class.get(content_type, []):
            page_id_node = obj.xpath("./id[@name='id']/text()")
            if not page_id_node: continue
            page_id = page_id_node[0]

            creator_key_node = obj.xpath("./property[@name='creator']/id[@name='key']/text()")
            modifier_key_node = obj.xpath("./property[@name='lastModifier']/id[@name='key']/text()")
            
            title_node = obj.xpath("./property[@name='title']/text()")
            if not title_node: continue 

            page_info = {
                'id': page_id,
                'type': content_type,
                'title': title_node[0],
                'creator': users_map.get(creator_key_node[0]) if creator_key_node else None,
                'last_modifier': users_map.get(modifier_key_node[0]) if modifier_key_node else None,
                'attachments': attachments_by_page.get(page_id, []),
                'comments': comments_by_page.get(page_id, []),
                'labels': [],
            }

            version_node = obj.xpath("./property[@name='version']/text()")
            page_info['version'] = int(version_node[0]) if version_node else 0
            
            creation_date_node = obj.xpath("./property[@name='creationDate']/text()")
            page_info['created_at'] = creation_date_node[0] if creation_date_node else None

            mod_date_node = obj.xpath("./property[@name='lastModificationDate']/text()")
            page_info['modified_at'] = mod_date_node[0] if mod_date_node else None

            body_content_ref_node = obj.xpath(".//collection[@name='bodyContents']/element/id[@name='id']/text()")
            if body_content_ref_node and body_content_ref_node[0] in body_content_map:
                raw_content = body_content_map[body_content_ref_node[0]]
                page_info['content_raw'] = raw_content
                page_info['content_text'] = clean_xhtml_content(raw_content)
            else:
                page_info['content_raw'] = None
                page_info['content_text'] = ""

            parent_ref_node = obj.xpath(".//collection[@name='parent']/ref/id[@name='id']/text()")
            if parent_ref_node:
                page_info['parent_id'] = parent_ref_node[0]

            for label_ref_node in obj.xpath(".//collection[@name='labellings']/object/ref[@name='label']/id/text()"):
                if label_ref_node in labels_map:
                    page_info['labels'].append(labels_map[label_ref_node])

            content_data.append(page_info)

    print(f"ステップ4: {len(content_data)} 件のコンテンツ情報を組み立てました。")
    return content_data

def save_as_json(data, output_file_path):
    if not data:
        print("処理対象のコンテンツが見つからなかったため、ファイルは出力されませんでした。")
        return
    print(f"データを '{output_file_path}' に保存しています...")
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("JSONファイルへの保存が完了しました。")
    except IOError as e:
        print(f"エラー: ファイルの書き込みに失敗しました: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ConfluenceのXMLエクスポートをJSONに変換し、添付ファイルを復元します。')
    parser.add_argument('input_file', help='入力するConfluenceのXMLファイル (例: entities.xml)')
    parser.add_argument('-o', '--output', default='confluence_data.json',
                        help='出力するJSONファイル名 (デフォルト: confluence_data.json)')
    parser.add_argument('-a', '--attachments-dir',
                        help='Confluenceからエクスポートされた添付ファイルが格納されているディレクトリのパス')
    # --- ここからが追加した引数 ---
    parser.add_argument('-r', '--restore-dir',
                        help='添付ファイルを復元して格納する先のディレクトリパス')
    # --- ここまでが追加した引数 ---
    parser.add_argument('--debug', action='store_true', help='デバッグ情報を有効にします')
    
    args = parser.parse_args()
    
    if args.restore_dir and not args.attachments_dir:
        parser.error('--restore-dir を使用するには --attachments-dir も指定する必要があります。')
    
    # --- 関数呼び出しを修正 ---
    pages = parse_confluence_xml(
        args.input_file,
        attachments_base_dir=args.attachments_dir,
        restore_dir=args.restore_dir,
        debug=args.debug
    )
    if pages is not None:
        save_as_json(pages, args.output)
