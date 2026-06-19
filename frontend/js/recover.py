import re

log_path = r"C:\Users\ASUS\.gemini\antigravity-ide\brain\812984bd-bfad-4fff-8c39-98bd8a9682cf\.system_generated\logs\transcript.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We just need to extract the lines that start with numbers followed by a colon and a space
# and build app.js.
# But we must only grab lines from the view_file tool output for app.js.
# Let's find "File Path: `file:///d:/FDM/frontend/js/app.js`"
chunks = content.split('File Path: `file:///d:/FDM/frontend/js/app.js`')
if len(chunks) < 3:
    print("Could not find both chunks!")
    exit(1)

full_lines = []
for chunk in chunks[1:]:
    # Find the block of code
    lines = chunk.split('\\n')
    for l in lines:
        match = re.search(r'^(\d+):\s(.*)', l.strip())
        if match:
            # unescape the string from json
            text = match.group(2).replace('\\"', '"').replace('\\\\', '\\')
            full_lines.append((int(match.group(1)), text))

# sort by line number and remove duplicates
full_lines = sorted(list(set(full_lines)), key=lambda x: x[0])

# check if we have all 1085 lines
if len(full_lines) == 1085:
    with open('d:/FDM/frontend/js/app.js_restored', 'w', encoding='utf-8') as f:
        for idx, text in full_lines:
            f.write(text + '\n')
    print("Successfully restored 1085 lines!")
else:
    print(f"Found {len(full_lines)} lines.")
