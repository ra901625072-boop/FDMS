import os, re

content = open("d:/FDM/frontend/js/app.js.bak", "r", encoding="utf-8").read()
# Normalize newlines just in case
content = content.replace("\r\n", "\n")

# Split by the comment header lines
parts = re.split(r"// ==========================================\n// (.+?)\n// ==========================================", content)

# parts[0] will be everything before the first header (state)
state_code = parts[0].strip()

sections = {}
for i in range(1, len(parts), 2):
    header = parts[i]
    code = parts[i+1]
    sections[header] = code

# The headers in the file based on the first view:
# 1. Toast Alerts
# 2. Routing and Screen Controls
# 3. Core Views & API Rendering Controllers
# 4. Dashboard View Metrics Loader
# 5. Settings Views Loaders
# 6. File Preview Logic
# 7. Family Members Management Screen
# 8. Drag & Drop File Upload Handler
# 9. Authentication Submission Listeners
# 10. Core Hash Router
# 11. Initialization & Mounting Setup

ui_js = "// ==========================================\n// Toast Alerts\n// ==========================================\n" + sections.get("Toast Alerts", "") + "\n\n" + \
        "// ==========================================\n// Routing and Screen Controls\n// ==========================================\n" + sections.get("Routing and Screen Controls", "")

# Core Views & API Rendering Controllers has fetchCurrentUser, folders, files, dropdowns, breadcrumbs, vault view.
core_code = sections.get("Core Views & API Rendering Controllers", "")

# I'll split core_code manually.
auth_fetch_me = re.search(r"(// 1\. Fetch current user.*?)(?=// 2\. Fetch folders)", core_code, re.DOTALL).group(1)
files_code1 = re.search(r"(// 2\. Fetch folders.*?)(?=\n// 5\. Build Breadcrumbs)", core_code, re.DOTALL).group(1)
ui_breadcrumbs = re.search(r"(// 5\. Build Breadcrumbs.*?)(?=// Load vault dashboard parameters)", core_code, re.DOTALL).group(1)
dashboard_vault = re.search(r"(// Load vault dashboard parameters.*)", core_code, re.DOTALL).group(1)

ui_js += "\n\n" + ui_breadcrumbs

auth_js = auth_fetch_me + "\n\n" + "// ==========================================\n// Authentication Submission Listeners\n// ==========================================\n" + sections.get("Authentication Submission Listeners", "")

files_js = files_code1 + "\n\n" + \
           "// ==========================================\n// File Preview Logic\n// ==========================================\n" + sections.get("File Preview Logic", "") + "\n\n" + \
           "// ==========================================\n// Drag & Drop File Upload Handler\n// ==========================================\n" + sections.get("Drag & Drop File Upload Handler", "")

dashboard_js = dashboard_vault + "\n\n" + \
               "// ==========================================\n// Dashboard View Metrics Loader\n// ==========================================\n" + sections.get("Dashboard View Metrics Loader", "") + "\n\n" + \
               "// ==========================================\n// Settings Views Loaders\n// ==========================================\n" + sections.get("Settings Views Loaders", "") + "\n\n" + \
               "// ==========================================\n// Family Members Management Screen\n// ==========================================\n" + sections.get("Family Members Management Screen", "")

app_js = "// ==========================================\n// Core Hash Router\n// ==========================================\n" + sections.get("Core Hash Router", "") + "\n\n" + \
         "// ==========================================\n// Initialization & Mounting Setup\n// ==========================================\n" + sections.get("Initialization & Mounting Setup", "")

base_dir = "d:/FDM/frontend/js"
with open(f"{base_dir}/state.js", "w", encoding="utf-8") as f: f.write(state_code)
with open(f"{base_dir}/ui.js", "w", encoding="utf-8") as f: f.write(ui_js)
with open(f"{base_dir}/auth.js", "w", encoding="utf-8") as f: f.write(auth_js)
with open(f"{base_dir}/files.js", "w", encoding="utf-8") as f: f.write(files_js)
with open(f"{base_dir}/dashboard.js", "w", encoding="utf-8") as f: f.write(dashboard_js)
with open(f"{base_dir}/app.js", "w", encoding="utf-8") as f: f.write(app_js)

print("Split completed successfully!")
