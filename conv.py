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
    print("Error: lxml library not found.")
    print("To run this script, you need to install lxml.")
    print("Please run the following command in your terminal:")
    print("pip install lxml")
    exit(1)

def clean_xhtml_content(xhtml_content):
    """
    Simplifies XHTML tags found in Confluence storage format,
    converting them to a form closer to plain text.
    """
    if xhtml_content is None:
        return ""
    text_content = re.sub(r'<[^>]+>', '', xhtml_content)
    return html.unescape(text_content).strip()

def parse_confluence_xml(xml_file_path, attachments_base_dir=None, restore_dir=None, debug=False):
    """
    Parses a Confluence XML export file using lxml.
    It also includes functionality to restore attachments to a specified directory.
    """
    print(f"Parsing '{xml_file_path}'...")
    if not os.path.exists(xml_file_path):
        print(f"Error: Input file '{xml_file_path}' not found.")
        return None
        
    try:
        with open(xml_file_path, 'rb') as f:
            xml_bytes = f.read()
        parser = etree.XMLParser(recover=True, huge_tree=True)
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception as e:
        print(f"Error: Failed to parse XML file: {e}")
        return None

    # --- Step 1: Classify all objects by class ---
    objects_by_class = defaultdict(list)
    for obj in root.iter('object'):
        class_attr = obj.get('class')
        if class_attr:
            objects_by_class[class_attr].append(obj)
    
    print("--- Step 1: Classification results of all objects ---")
    for cls, items in sorted(objects_by_class.items()):
        print(f"  - {cls}: {len(items)} items")
    print("-" * 20)

    # --- Step 2: Pre-map related information ---
    users_map = {}
    if debug: print("--- Debug: Starting parsing of user information (ConfluenceUserImpl) ---")
    for i, obj in enumerate(objects_by_class.get('ConfluenceUserImpl', [])):
        user_key_node = obj.xpath("./id[@name='key']/text()")
        user_name_node = obj.xpath("./property[@name='fullName']/text() | ./property[@name='name']/text()")
        if user_key_node and user_name_node:
            users_map[user_key_node[0]] = user_name_node[0]
    print(f"Step 2.1: Loaded {len(users_map)} user information entries.")

    body_content_map = {}
    for obj in objects_by_class.get('BodyContent', []):
        content_id_node = obj.xpath("./id[@name='id']/text()")
        body_node = obj.xpath("./property[@name='body']/text()")
        if content_id_node and body_node:
            body_content_map[content_id_node[0]] = body_node[0]
    print(f"Step 2.2: Loaded {len(body_content_map)} body content entries.")
    
    labels_map = {}
    for obj in objects_by_class.get('Label', []):
        label_id_node = obj.xpath("./id/text()")
        label_name_node = obj.xpath("./property[@name='name']/text()")
        if label_id_node and label_name_node:
            labels_map[label_id_node[0]] = label_name_node[0]
    print(f"Step 2.3: Loaded {len(labels_map)} label definitions.")

    # --- Step 3: Pre-map content properties ---
    content_properties_map = {}
    if debug: print("--- Debug: Starting parsing of content properties (ContentProperty) ---")
    for i, obj in enumerate(objects_by_class.get('ContentProperty', [])):
        prop_id_node = obj.xpath("./id[@name='id']/text()")
        prop_name_node = obj.xpath("./property[@name='name']/text()")
        prop_value_node = obj.xpath("./property[@name='stringValue']/text() | ./property[@name='longValue']/text()")
        if prop_id_node and prop_name_node and prop_value_node:
            content_properties_map[prop_id_node[0]] = {
                "name": prop_name_node[0],
                "value": prop_value_node[0]
            }
    print(f"Step 2.4: Loaded {len(content_properties_map)} content properties.")


    # --- Step 4: Group related information by page ID ---
    attachments_by_page = defaultdict(list)
    restored_count = 0
    if debug: print("--- Debug: Starting parsing of attachments (Attachment) ---")
    for i, obj in enumerate(objects_by_class.get('Attachment', [])):
        page_id_node = obj.xpath(".//property[@name='content' or @name='container' or @name='containerContent']//id[@name='id']/text()")
        attachment_id_node = obj.xpath("./id[@name='id']/text()")

        if not page_id_node or not attachment_id_node:
            if debug: print("    - -> Skipping: Page ID or attachment ID not found.")
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
        
        # --- Start of modified/added logic ---
        # Restore attachment and record its path
        restored_file_path = None
        if attachments_base_dir and restore_dir and filename:
            source_path = os.path.join(attachments_base_dir, page_id, attachment_id, '1')
            
            if os.path.exists(source_path):
                # Output directory structure: {restore_dir}/{page_id}/{attachment_id}/{original_filename}
                dest_dir = os.path.join(restore_dir, page_id, attachment_id)
                dest_path = os.path.join(dest_dir, filename)
                
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    restored_file_path = dest_path
                    restored_count += 1
                    if debug:
                        print(f"    - -> Restore successful: '{source_path}' -> '{dest_path}'")
                except Exception as e:
                    print(f"    - -> Error: Failed to restore file: {e}")
            elif debug:
                print(f"    - -> Warning: Attachment source not found: {source_path}")
        # --- End of modified/added logic ---

        attachments_by_page[page_id].append({
            'id': attachment_id,
            'filename': filename,
            'filesize': filesize,
            'content_type': content_type,
            'author': users_map.get(creator_key_node[0]) if creator_key_node else None,
            'created_at': (obj.xpath("./property[@name='creationDate']/text()") or [''])[0],
            'filepath': restored_file_path  # Add restored file path
        })
    print(f"Step 3.1: Grouped {len(attachments_by_page)} attachments linked to pages.")
    if restore_dir:
        print(f"Step 3.1.1: Restored {restored_count} attachments to '{restore_dir}'.")

    comments_by_page = defaultdict(list)
    # (Comment logic remains unchanged)
    print(f"Step 3.2: Grouped {len(comments_by_page)} comments linked to pages.")

    # --- Step 5: Assemble all information ---
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

    print(f"Step 4: Assembled {len(content_data)} content entries.")
    return content_data

def save_as_json(data, output_file_path):
    if not data:
        print("No content found for processing, so no file was output.")
        return
    print(f"Saving data to '{output_file_path}'...")
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("JSON file saved successfully.")
    except IOError as e:
        print(f"Error: Failed to write file: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Converts a Confluence XML export to JSON and restores attachments.')
    parser.add_argument('input_file', help='The Confluence XML file to input (e.g., entities.xml)')
    parser.add_argument('-o', '--output', default='confluence_data.json',
                        help='Name of the output JSON file (default: confluence_data.json)')
    parser.add_argument('-a', '--attachments-dir',
                        help='Path to the directory containing attachments exported from Confluence')
    parser.add_argument('-r', '--restore-dir',
                        help='Path to the directory where attachments will be restored')
    parser.add_argument('--debug', action='store_true', help='Enables debug information')
    
    args = parser.parse_args()
    
    if args.restore_dir and not args.attachments_dir:
        parser.error("'--restore-dir' requires '--attachments-dir' to be specified as well.")
    
    pages = parse_confluence_xml(
        args.input_file,
        attachments_base_dir=args.attachments_dir,
        restore_dir=args.restore_dir,
        debug=args.debug
    )
    if pages is not None:
        save_as_json(pages, args.output)
