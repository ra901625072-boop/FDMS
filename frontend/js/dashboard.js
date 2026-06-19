// ==========================================
// Dashboard and Settings Views
// ==========================================

// Load vault dashboard parameters
async function loadVaultView(params) {
  showView("vault-view");
  
  // Display search, upload and new-folder options
  document.getElementById("search-bar-container").style.display = "block";
  document.getElementById("new-folder-btn").style.display = "inline-flex";
  document.getElementById("upload-file-btn").style.display = "inline-flex";
  
  const folderId = params.folder ? parseInt(params.folder) : null;
  state.currentFolderId = folderId;
  
  await fetchFolders();
  await fetchFiles(folderId);
  
  renderFolders(folderId);
  renderFiles();
  updateBreadcrumbs();

  // Storage is managed transparently on the server
}

async function loadDashboardView() {
  showView("dashboard-view");
  
  // Hide search and folders controls on dashboard view
  document.getElementById("search-bar-container").style.display = "none";
  document.getElementById("new-folder-btn").style.display = "none";
  document.getElementById("upload-file-btn").style.display = "none";
  document.getElementById("page-title-txt").innerText = "Family Dashboard";
  
  try {
    const [files, folders, members, storageConfig] = await Promise.all([
      api.get("/api/files"),
      api.get("/api/folders"),
      api.get("/api/family/members"),
      api.get("/api/storage/config")
    ]);
    
    // Stats calculation
    document.getElementById("stats-total-files").innerText = files.length;
    document.getElementById("stats-total-folders").innerText = folders.length;
    document.getElementById("stats-total-members").innerText = members.length;
    
    const totalSizeBytes = files.reduce((acc, f) => acc + f.size_bytes, 0);
    document.getElementById("stats-total-size").innerText = formatBytes(totalSizeBytes);
    
    // Progress calculation (15GB Google Drive space limit)
    const limitBytes = 15 * 1024 * 1024 * 1024;
    const usagePercent = Math.min(100, Math.round((totalSizeBytes / limitBytes) * 100));
    document.getElementById("storage-percent-txt").innerText = `${usagePercent}%`;
    
    const circumference = 251.2;
    const offset = circumference - (usagePercent / 100) * circumference;
    document.getElementById("storage-gauge-progress").setAttribute("stroke-dashoffset", offset);
    document.getElementById("storage-numbers-txt").innerText = `${formatBytes(totalSizeBytes)} of 15 GB Used`;
    
    let activeProv = "Vault Storage";
    if (storageConfig.storage_provider === "google") {
      activeProv = "Vault Cloud Storage";
    }
    document.getElementById("storage-provider-label").innerText = `Active Provider: ${activeProv}`;
    
    // Recent uploads body loading
    const sortedFiles = [...files].sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date)).slice(0, 5);
    const tbody = document.getElementById("recent-uploads-body");
    tbody.innerHTML = "";
    
    if (sortedFiles.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 15px;">No files uploaded yet.</td></tr>`;
    } else {
      sortedFiles.forEach(file => {
        const tr = document.createElement("tr");
        const dateFormatted = new Date(file.upload_date).toLocaleDateString(undefined, {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        tr.innerHTML = `
          <td><strong>${file.filename}</strong></td>
          <td>${file.uploader_email || 'Unknown'}</td>
          <td style="color: var(--text-secondary);">${dateFormatted}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Activity timeline logging
    const timelineContainer = document.getElementById("activity-timeline-container");
    timelineContainer.innerHTML = "";
    
    const activities = [];
    files.forEach(f => {
      activities.push({
        text: `${f.uploader_email || 'Member'} uploaded ${f.filename}`,
        date: new Date(f.upload_date)
      });
    });
    folders.forEach(f => {
      activities.push({
        text: `Folder "${f.name}" was created`,
        date: new Date(f.created_at)
      });
    });
    
    const sortedActivities = activities.sort((a, b) => b.date - a.date).slice(0, 5);
    if (sortedActivities.length === 0) {
      timelineContainer.innerHTML = `<div style="font-size: 0.85rem; color: var(--text-muted); text-align: center; padding-top: 10px;">No activity recorded yet.</div>`;
    } else {
      sortedActivities.forEach(act => {
        const timeText = act.date.toLocaleDateString(undefined, {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        const item = document.createElement("div");
        item.className = "activity-item";
        item.innerHTML = `
          <span>${act.text}</span>
          <span class="activity-time">${timeText}</span>
        `;
        timelineContainer.appendChild(item);
      });
    }
  } catch (err) {
    showToast("Failed to load dashboard: " + err.message, "error");
  }
}

// ==========================================
// Settings Views Loaders
// ==========================================
async function loadSettingsView() {
  showView("settings-view");
  document.getElementById("search-bar-container").style.display = "none";
  document.getElementById("new-folder-btn").style.display = "none";
  document.getElementById("upload-file-btn").style.display = "none";
  document.getElementById("page-title-txt").innerText = "Vault Settings";

  // Pre-fill fields
  document.getElementById("settings-name").value = state.user.email.split("@")[0];
  document.getElementById("settings-email").value = state.user.email;
}

// Profile edit simulation handler
function handleProfileSave(e) {
  e.preventDefault();
  const name = document.getElementById("settings-name").value.trim();
  showToast(`Profile settings updated: ${name}`, "success");
}

// Password updating simulation handler
function handlePasswordSave(e) {
  e.preventDefault();
  showToast("Password changed successfully", "success");
  document.getElementById("settings-password-form").reset();
}

// ==========================================
// Family Members Management Screen
// ==========================================
async function loadMembersView() {
  showView("members-view");
  document.getElementById("search-bar-container").style.display = "none";
  document.getElementById("new-folder-btn").style.display = "none";
  document.getElementById("upload-file-btn").style.display = "none";
  document.getElementById("page-title-txt").innerText = "Family Members";

  const container = document.getElementById("members-list-container");
  container.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-secondary);"><i data-lucide="loader" class="animate-spin" style="margin-right: 8px;"></i>Loading members...</div>`;
  lucide.createIcons();

  try {
    const members = await api.get("/api/family/members");
    container.innerHTML = "";
    
    if (members.length === 0) {
      container.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-muted);">No family members found.</div>`;
      return;
    }

    members.forEach(member => {
      const isMe = member.id === state.user.id;
      const initial = member.email.charAt(0).toUpperCase();
      const joinedDate = new Date(member.created_at).toLocaleDateString(undefined, {
        year: 'numeric', month: 'long', day: 'numeric'
      });
      
      let removeAction = "";
      if (state.user.role === "admin" && !isMe) {
        removeAction = `
          <button class="btn btn-danger" style="padding: 6px 12px; font-size: 0.8rem;" onclick="removeMember(${member.id}, '${member.email}')">
            <i data-lucide="user-x" size="14"></i> Remove
          </button>
        `;
      }

      const card = document.createElement("div");
      card.className = "member-row";
      card.innerHTML = `
        <div class="member-info-group">
          <div class="member-avatar">${initial}</div>
          <div class="member-text-group">
            <div class="member-email-txt">
              ${member.email} ${isMe ? '<span style="color: var(--text-muted); font-size: 0.8rem; font-weight: normal;">(You)</span>' : ''}
            </div>
            <div class="member-joined-date">Joined: ${joinedDate}</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 15px;">
          <span class="badge badge-${member.role}">${member.role}</span>
          ${removeAction}
        </div>
      `;
      
      container.appendChild(card);
    });
    
    lucide.createIcons();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Remove Family Member API
async function removeMember(userId, email) {
  if (!confirm(`Are you absolutely sure you want to remove ${email} from your family vault?`)) {
    return;
  }
  try {
    await api.delete(`/api/family/members/${userId}`);
    showToast(`${email} removed from family vault`, "success");
    loadMembersView();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Submit Mega Configuration
async function submitMegaSetup(e) {
  e.preventDefault();
  const email = document.getElementById("mega-email").value.trim();
  const password = document.getElementById("mega-password").value;
  
  if (!email || !password) return;
  
  showToast("Verifying Mega account credentials...", "info");
  
  try {
    await api.post("/api/storage/config/mega", { email, password });
    showToast("Connected to Mega storage successfully!", "success");
    document.getElementById("mega-config-form").reset();
    loadSettingsView();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Submit Google Configuration and Redirect
async function submitGoogleSetup(e) {
  e.preventDefault();
  const clientId = document.getElementById("google-client-id").value.trim();
  const clientSecret = document.getElementById("google-client-secret").value.trim();
  
  showToast("Initiating Google Drive authorization...", "info");
  
  try {
    const res = await api.post("/api/storage/config/google/initiate", {
      client_id: clientId,
      client_secret: clientSecret
    });
    
    if (res.auth_url) {
      window.location.href = res.auth_url;
    } else {
      throw new Error("Failed to retrieve Google Auth URL");
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}
