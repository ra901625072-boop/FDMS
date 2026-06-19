// ==========================================
// Files and Folders Management
// ==========================================

async function fetchFolders() {
  try {
    const folders = await api.get("/api/folders");
    state.folders = folders;
    return folders;
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Render Folder Grid
function renderFolders(parentFolderId) {
  const container = document.getElementById("folders-container");
  const wrapper = document.getElementById("folders-section-wrapper");
  container.innerHTML = "";
  
  // Filter folders matching current parent
  const filtered = state.folders.filter(f => f.parent_id === parentFolderId);
  
  if (filtered.length === 0) {
    wrapper.style.display = "none";
    return;
  }
  wrapper.style.display = "block";

  filtered.forEach(folder => {
    const card = document.createElement("div");
    card.className = "folder-card glass-card";
    
    const lastModDate = new Date(folder.last_modified).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });

    card.innerHTML = `
      <div class="folder-info">
        <div class="folder-icon">
          <i data-lucide="folder" size="32" fill="#fbbf24"></i>
        </div>
        <div class="folder-details">
          <div class="folder-name" title="${folder.name}">${folder.name}</div>
          <div class="folder-meta">${folder.file_count} files • ${formatBytes(folder.total_size_bytes)}</div>
        </div>
      </div>
      <button class="item-actions-trigger" onclick="event.stopPropagation(); toggleDropdown(event, 'folder', ${folder.id}, '${folder.name.replace(/'/g, "\\'")}')">
        <i data-lucide="more-vertical" size="18"></i>
      </button>
      <div class="actions-dropdown" id="dropdown-folder-${folder.id}">
        <button class="dropdown-item" onclick="event.stopPropagation(); triggerRename('folder', ${folder.id}, '${folder.name.replace(/'/g, "\\'")}')">
          <i data-lucide="edit" size="14"></i> Rename
        </button>
        <button class="dropdown-item dropdown-item-delete" onclick="event.stopPropagation(); triggerDelete('folder', ${folder.id}, '${folder.name.replace(/'/g, "\\'")}')">
          <i data-lucide="trash-2" size="14"></i> Delete
        </button>
      </div>
    `;
    
    // Click navigates into subfolder
    card.onclick = () => {
      navigateTo(`#vault?folder=${folder.id}`);
    };
    
    container.appendChild(card);
  });
  
  lucide.createIcons();
}

async function fetchFiles(folderId) {
  try {
    const fidParam = folderId === null ? "root" : folderId;
    const files = await api.get(`/api/files?folder_id=${fidParam}`);
    state.files = files;
    return files;
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Render Files Table List
function renderFiles() {
  const tbody = document.getElementById("files-list-body");
  const emptyState = document.getElementById("vault-empty-state");
  
  tbody.innerHTML = "";
  
  // Apply text filtering if query exists
  const query = document.getElementById("search-query").value.toLowerCase().trim();
  let filtered = state.files.filter(file => file.filename.toLowerCase().includes(query));

  // Apply file type category filtering
  if (state.fileFilter !== "all") {
    filtered = filtered.filter(file => {
      const mime = file.file_type.toLowerCase();
      if (state.fileFilter === "image") return mime.startsWith("image/");
      if (state.fileFilter === "pdf") return mime === "application/pdf";
      if (state.fileFilter === "text") return mime.startsWith("text/") || mime === "application/json";
      if (state.fileFilter === "document") return mime.includes("word") || mime.includes("officedocument") || mime.includes("excel");
      return true;
    });
  }

  const totalFoldersCount = state.folders.filter(f => f.parent_id === state.currentFolderId).length;
  
  if (filtered.length === 0) {
    if (totalFoldersCount === 0) {
      emptyState.style.display = "flex";
    } else {
      emptyState.style.display = "none";
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No matching files found.</td></tr>`;
    }
    return;
  }

  emptyState.style.display = "none";

  filtered.forEach(file => {
    let iconClass = "file-icon-other";
    let iconName = "file";
    const mime = file.file_type.toLowerCase();
    
    if (mime.startsWith("image/")) {
      iconClass = "file-icon-image";
      iconName = "file-image";
    } else if (mime === "application/pdf") {
      iconClass = "file-icon-pdf";
      iconName = "file-text";
    } else if (mime.startsWith("text/") || mime === "application/json") {
      iconClass = "file-icon-text";
      iconName = "file-code";
    } else if (mime.includes("word") || mime.includes("officedocument")) {
      iconClass = "file-icon-word";
      iconName = "file-text";
    }

    const uploadDateFormatted = new Date(file.upload_date).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <div class="file-name-col">
          <div class="file-icon ${iconClass}">
            <i data-lucide="${iconName}" size="18"></i>
          </div>
          <div class="file-name-txt" title="${file.filename}" onclick="openFilePreview(${file.id}, '${file.filename.replace(/'/g, "\\'")}', '${file.file_type}')">
            ${file.filename}
          </div>
        </div>
      </td>
      <td>${formatBytes(file.size_bytes)}</td>
      <td class="uploader-email-cell">${file.uploader_email || 'Unknown Member'}</td>
      <td style="color: var(--text-secondary);">${uploadDateFormatted}</td>
      <td class="actions-cell">
        <button class="item-actions-trigger" onclick="toggleDropdown(event, 'file', ${file.id}, '${file.filename.replace(/'/g, "\\'")}')">
          <i data-lucide="more-vertical" size="18"></i>
        </button>
        <div class="actions-dropdown" id="dropdown-file-${file.id}">
          <button class="dropdown-item" onclick="openFilePreview(${file.id}, '${file.filename.replace(/'/g, "\\'")}', '${file.file_type}')">
            <i data-lucide="eye" size="14"></i> Open
          </button>
          <a class="dropdown-item" href="/api/files/${file.id}/download?token=${encodeURIComponent(localStorage.getItem("token"))}" download>
            <i data-lucide="download" size="14"></i> Download
          </a>
          <button class="dropdown-item" onclick="triggerRename('file', ${file.id}, '${file.filename.replace(/'/g, "\\'")}')">
            <i data-lucide="edit" size="14"></i> Rename
          </button>
          <button class="dropdown-item dropdown-item-delete" onclick="triggerDelete('file', ${file.id}, '${file.filename.replace(/'/g, "\\'")}')">
            <i data-lucide="trash-2" size="14"></i> Delete
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
  
  lucide.createIcons();
}

// Perform Rename API
async function submitRename(e) {
  e.preventDefault();
  const type = document.getElementById("rename-item-type").value;
  const id = document.getElementById("rename-item-id").value;
  const newName = document.getElementById("rename-item-name").value.trim();
  
  if (!newName) return;
  
  try {
    if (type === "folder") {
      await api.put(`/api/folders/${id}`, { name: newName });
      showToast("Folder renamed successfully", "success");
    } else {
      await api.put(`/api/files/${id}`, { filename: newName });
      showToast("File renamed successfully", "success");
    }
    closeModal("rename-modal");
    await fetchFolders();
    await fetchFiles(state.currentFolderId);
    renderFolders(state.currentFolderId);
    renderFiles();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Perform Deletion API
async function confirmDeletion(type, id) {
  try {
    if (type === "folder") {
      await api.delete(`/api/folders/${id}`);
      showToast("Folder deleted successfully", "success");
    } else {
      await api.delete(`/api/files/${id}`);
      showToast("File deleted successfully", "success");
    }
    closeModal("delete-modal");
    await fetchFolders();
    await fetchFiles(state.currentFolderId);
    renderFolders(state.currentFolderId);
    renderFiles();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================
// File Preview Logic
// ==========================================
async function openFilePreview(fileId, filename, mimetype) {
  const modal = document.getElementById("preview-modal");
  const title = document.getElementById("preview-file-title");
  const container = document.getElementById("preview-body-container");
  const downloadBtn = document.getElementById("preview-download-direct");
  
  title.innerText = filename;
  const token = encodeURIComponent(localStorage.getItem("token"));
  downloadBtn.href = `/api/files/${fileId}/download?token=${token}`;
  container.innerHTML = `<div class="preview-placeholder"><i data-lucide="loader-2" class="animate-spin" size="32"></i><span>Loading preview...</span></div>`;
  lucide.createIcons();
  
  openModal("preview-modal");
  
  const mime = mimetype.toLowerCase();
  
  try {
    if (mime.startsWith("image/")) {
      container.innerHTML = `<img src="/api/files/${fileId}/preview?token=${token}" class="preview-img" alt="${filename}">`;
    } 
    else if (mime === "application/pdf") {
      container.innerHTML = `<iframe src="/api/files/${fileId}/preview?token=${token}" class="preview-iframe"></iframe>`;
    } 
    else if (mime.startsWith("text/")) {
      const text = await api.get(`/api/files/${fileId}/preview`);
      const safeText = typeof text === "string" ? text : JSON.stringify(text, null, 2);
      const pre = document.createElement("pre");
      pre.className = "preview-text";
      pre.innerText = safeText;
      container.innerHTML = "";
      container.appendChild(pre);
    } 
    else {
      let icon = "file-text";
      let detail = "This file type cannot be previewed natively in the browser.";
      if (mime.includes("word") || mime.includes("officedocument")) {
        detail = "Word documents cannot be previewed directly. Please download the file to view its full content.";
      }
      
      container.innerHTML = `
        <div class="preview-placeholder">
          <i data-lucide="${icon}" size="64" style="color: var(--text-secondary);"></i>
          <span style="font-weight: 500; font-size: 1.1rem; color: var(--text-primary);">${filename}</span>
          <span style="font-size: 0.9rem; color: var(--text-secondary); max-width: 320px; text-align: center;">${detail}</span>
          <a href="/api/files/${fileId}/download" class="btn btn-primary" style="margin-top: 10px;">
            <i data-lucide="download"></i> Download to View
          </a>
        </div>
      `;
      lucide.createIcons();
    }
  } catch (err) {
    container.innerHTML = `
      <div class="preview-placeholder">
        <i data-lucide="alert-circle" size="48" style="color: var(--danger);"></i>
        <span style="color: var(--danger); font-weight: 500;">Failed to load preview</span>
        <span style="font-size: 0.85rem; color: var(--text-secondary);">${err.message}</span>
      </div>
    `;
    lucide.createIcons();
  }
}

// ==========================================
// Drag & Drop File Upload Handler
// ==========================================
function setupUploadListeners() {
  const dropzone = document.getElementById("drop-zone");
  const filePicker = document.getElementById("file-picker");
  const uploadBtn = document.getElementById("upload-file-btn");
  
  uploadBtn.onclick = () => openModal("upload-modal");
  
  filePicker.onchange = (e) => {
    handleFileUpload(e.target.files);
  };
  
  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    }, false);
  });
  
  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    }, false);
  });
  
  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFileUpload(files);
  }, false);
}

function handleFileUpload(fileList) {
  if (fileList.length === 0) return;
  
  const queueContainer = document.getElementById("upload-queue-list");
  
  Array.from(fileList).forEach(file => {
    const fileItem = document.createElement("div");
    fileItem.className = "upload-file-item";
    
    const randomId = "upload-" + Math.random().toString(36).substring(2, 9);
    fileItem.id = randomId;
    
    fileItem.innerHTML = `
      <div style="flex-grow: 1; margin-right: 15px; max-width: calc(100% - 70px);">
        <div style="font-weight: 550; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${file.name}
        </div>
        <div class="upload-file-progress">
          <div class="upload-file-progress-bar" id="progress-bar-${randomId}"></div>
        </div>
      </div>
      <div id="status-txt-${randomId}" style="font-size: 0.8rem; color: var(--text-secondary); width: 50px; text-align: right;">
        0%
      </div>
    `;
    
    queueContainer.appendChild(fileItem);
    
    const formData = new FormData();
    formData.append("file", file);
    if (state.currentFolderId !== null) {
      formData.append("folder_id", state.currentFolderId);
    }
    
    api.upload(
      "/api/files/upload",
      formData,
      (percent) => {
        document.getElementById(`progress-bar-${randomId}`).style.width = `${percent}%`;
        document.getElementById(`status-txt-${randomId}`).innerText = `${percent}%`;
      },
      async (result) => {
        document.getElementById(`status-txt-${randomId}`).innerHTML = `<i data-lucide="check" style="color: var(--success);" size="14"></i>`;
        document.getElementById(`progress-bar-${randomId}`).style.backgroundColor = "var(--success)";
        lucide.createIcons();
        showToast(`Uploaded: ${file.name}`, "success");
        
        setTimeout(() => fileItem.remove(), 2500);
        await fetchFiles(state.currentFolderId);
        renderFiles();
      },
      (error) => {
        document.getElementById(`status-txt-${randomId}`).innerHTML = `<i data-lucide="x" style="color: var(--danger);" size="14"></i>`;
        document.getElementById(`progress-bar-${randomId}`).style.backgroundColor = "var(--danger)";
        lucide.createIcons();
        showToast(`Failed to upload ${file.name}: ${error.message}`, "error");
      }
    );
  });
}
