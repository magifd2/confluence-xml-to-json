# Confluence XML to JSON Converter

This Python script converts XML data exported from Confluence into JSON format, with the option to restore attachments.

## Features

- Parses Confluence XML export files (e.g., `entities.xml`)
- Extracts pages, blog posts, and custom content
- Maps related information such as users, labels, and content properties
- Restores attachments and records their paths in the JSON data
- Outputs data in a structured JSON format

## Installation

This script requires the `lxml` library. You can install it using the following command:

```bash
pip install lxml
```

## Usage

The script accepts command-line arguments.

```bash
python conv.py <input_xml_file> [options]
```

### Arguments

- `<input_xml_file>`: Required. The Confluence XML export file to parse (e.g., `entities.xml`)

### Options

- `-o`, `--output <filename>`: Name of the output JSON file (default: `confluence_data.json`)
- `-a`, `--attachments-dir <directory_path>`: Path to the directory containing attachments exported from Confluence. Typically, this is a directory like `attachments` located at the same level as the XML file.
- `-r`, `--restore-dir <directory_path>`: Path to the directory where attachments will be restored. This option requires `--attachments-dir` to be specified.
- `--debug`: Enables debug information.

### Examples

1. **To convert XML to JSON only:**
   ```bash
   python conv.py entities.xml
   ```

2. **To specify an output filename:**
   ```bash
   python conv.py entities.xml -o my_confluence_data.json
   ```

3. **To restore attachments:**
   If your Confluence export data includes an `attachments` directory, specify its path.
   ```bash
   python conv.py entities.xml -a ./attachments -r ./restored_attachments
   ```
   This will restore attachments from `./attachments` to `./restored_attachments`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.