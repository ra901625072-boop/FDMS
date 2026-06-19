// ==========================================
// Toast Alerts
// ==========================================
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  let iconName = "info";
  if (type === "success") iconName = "check-circle";
  if (type === "error") iconName = "alert-circle";
  
  toast.innerHTML = `<i data-lucide="${iconName}" size="18"></i> <span>${message}</span>`;
  container.appendChild(toast);
  lucide.createIcons();
  
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(20px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Copy to Clipboard Utility
function copyToClipboard(text) {
  navigator.clipboard.writeText(text)
    .then(() => showToast("Family ID copied to clipboard!", "success"))
    .catch(() => showToast("Failed to copy text", "error"));
}

// ==========================================
// Routing and Screen Controls
// ==========================================
function navigateTo(hash) {
  window.location.hash = hash;
}

function showScreen(screenId) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(screenId).classList.add("active");
}

function showView(viewId) {
  document.querySelectorAll(".view-container").forEach(v => v.classList.remove("active"));
  document.getElementById(viewId).classList.add("active");
  
  // Highlight active sidebar item
  document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
  const viewName = viewId.replace("-view", "");
  const navItem = document.getElementById(`nav-${viewName}`);
  if (navItem) navItem.classList.add("active");

  // Highlight active mobile bottom nav item
  document.querySelectorAll(".mobile-bottom-nav a").forEach(item => item.classList.remove("active"));
  const mobileNavItem = document.getElementById(`mobile-nav-${viewName}`);
  if (mobileNavItem) mobileNavItem.classList.add("active");
}

// Modal open/close helpers
function openModal(modalId) {
  document.getElementById(modalId).classList.add("active");
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.remove("active");
  if (modalId === "folder-modal") {
    document.getElementById("folder-create-form").reset();
  }
}

// File size formatter
function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// ==========================================
// Build Breadcrumbs
// ==========================================
function updateBreadcrumbs() {
  const container = document.getElementById("breadcrumbs-container");
  container.innerHTML = "";
  
  const rootSpan = document.createElement("span");
  rootSpan.className = "breadcrumb-item";
  rootSpan.innerText = "Vault";
  rootSpan.onclick = () => navigateTo("#vault");
  container.appendChild(rootSpan);
  
  const path = [];
  let currentId = state.currentFolderId;
  
  while (currentId !== null) {
    const folder = state.folders.find(f => f.id === currentId);
    if (!folder) break;
    path.unshift(folder);
    currentId = folder.parent_id;
  }
  
  path.forEach((folder, idx) => {
    const sep = document.createElement("span");
    sep.className = "breadcrumb-separator";
    sep.innerText = ">";
    container.appendChild(sep);
    
    const span = document.createElement("span");
    span.className = "breadcrumb-item";
    span.innerText = folder.name;
    
    if (idx === path.length - 1) {
      span.style.color = "var(--text-primary)";
      span.style.fontWeight = "600";
    } else {
      span.onclick = () => navigateTo(`#vault?folder=${folder.id}`);
    }
    container.appendChild(span);
  });
  
  const activeFolderName = path.length > 0 ? path[path.length - 1].name : "Shared Vault";
  document.getElementById("page-title-txt").innerText = activeFolderName;
}

// ==========================================
// Dropdowns actions managers
// ==========================================
function toggleDropdown(event, type, id, name) {
  event.stopPropagation();
  const dropdownId = `dropdown-${type}-${id}`;
  const target = document.getElementById(dropdownId);
  
  const isCurrentlyOpen = target.classList.contains("active");
  closeActiveDropdown();
  
  if (!isCurrentlyOpen) {
    target.classList.add("active");
    state.activeDropdown = target;
    document.addEventListener("click", closeActiveDropdown);
  }
}

function closeActiveDropdown() {
  if (state.activeDropdown) {
    state.activeDropdown.classList.remove("active");
    state.activeDropdown = null;
    document.removeEventListener("click", closeActiveDropdown);
  }
}

// Rename Actions Triggers
function triggerRename(type, id, name) {
  closeActiveDropdown();
  document.getElementById("rename-item-type").value = type;
  document.getElementById("rename-item-id").value = id;
  document.getElementById("rename-item-name").value = name;
  document.getElementById("rename-title-txt").innerText = `Rename ${type.charAt(0).toUpperCase() + type.slice(1)}`;
  openModal("rename-modal");
}

// Delete Actions Triggers
function triggerDelete(type, id, name) {
  closeActiveDropdown();
  document.getElementById("confirm-delete-btn").onclick = () => confirmDeletion(type, id);
  document.getElementById("delete-item-name-txt").innerText = name;
  
  const warningText = document.getElementById("delete-warning-subtext");
  if (type === "folder") {
    warningText.style.display = "block";
  } else {
    warningText.style.display = "none";
  }
  
  openModal("delete-modal");
}
