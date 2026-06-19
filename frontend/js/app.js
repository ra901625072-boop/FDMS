// ==========================================
// Core Hash Router
// ==========================================
function parseHashRoute() {
  const hash = window.location.hash || "#dashboard";
  const parts = hash.split("?");
  const route = parts[0];
  const params = {};
  
  if (parts[1]) {
    const searchParams = new URLSearchParams(parts[1]);
    for (const [key, value] of searchParams.entries()) {
      params[key] = value;
    }
  }
  return { route, params };
}

async function router() {
  const { route, params } = parseHashRoute();
  const token = localStorage.getItem("token");
  
  closeActiveDropdown();
  
  const isAuthRoute = route === "#login" || route === "#register";
  if (!token && !isAuthRoute) {
    navigateTo("#login");
    return;
  }
  if (token && isAuthRoute) {
    navigateTo("#dashboard");
    return;
  }
  
  if (route === "#login") {
    showScreen("login-screen");
    return;
  }
  if (route === "#register") {
    showScreen("signup-screen");
    return;
  }
  
  showScreen("dashboard-screen");
  
  if (!state.user) {
    await fetchCurrentUser();
  }
  
  if (route === "#dashboard") {
    await loadDashboardView();
  } else if (route === "#vault") {
    await loadVaultView(params);
  } else if (route === "#members") {
    await loadMembersView();
  } else if (route === "#settings") {
    await loadSettingsView();
  } else if (route === "#storage") {
    if (params.status === "success") {
      showToast("Google Drive configuration verified and authorized!", "success");
    } else if (params.status === "error") {
      showToast(`Google Auth failed: ${params.message || "Unknown error"}`, "error");
    }
    navigateTo("#settings");
  } else {
    navigateTo("#dashboard");
  }
}

// ==========================================
// Initialization & Mounting Setup
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  // Bind form submissions
  document.getElementById("login-form").onsubmit = handleLoginSubmit;
  document.getElementById("signup-form").onsubmit = handleRegisterSubmit;
  document.getElementById("folder-create-form").onsubmit = async (e) => {
    e.preventDefault();
    const name = document.getElementById("new-folder-name").value.trim();
    if (!name) return;
    try {
      await api.post("/api/folders", {
        name,
        parent_id: state.currentFolderId
      });
      showToast("Folder created successfully", "success");
      closeModal("folder-modal");
      await fetchFolders();
      renderFolders(state.currentFolderId);
    } catch (err) {
      showToast(err.message, "error");
    }
  };
  
  document.getElementById("rename-submit-form").onsubmit = submitRename;
  
  document.getElementById("settings-profile-form").onsubmit = handleProfileSave;
  document.getElementById("settings-password-form").onsubmit = handlePasswordSave;

  document.getElementById("family-login-form").onsubmit = handleFamilyLoginSubmit;

  // Vault File type filters setup
  document.querySelectorAll(".filter-badge").forEach(badge => {
    badge.onclick = () => {
      document.querySelectorAll(".filter-badge").forEach(b => b.classList.remove("active"));
      badge.classList.add("active");
      state.fileFilter = badge.getAttribute("data-filter");
      renderFiles();
    };
  });
  
  document.getElementById("new-folder-btn").onclick = () => openModal("folder-modal");
  
  document.getElementById("family-id-box").onclick = () => copyToClipboard(state.user.family_id);
  document.getElementById("members-id-copy").onclick = () => copyToClipboard(state.user.family_id);
  
  document.getElementById("logout-btn").onclick = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    state.user = null;
    showToast("Logged out successfully", "success");
    navigateTo("#login");
  };
  
  document.getElementById("search-query").oninput = renderFiles;
  setupUploadListeners();
  
  window.addEventListener("hashchange", router);
  router();
});
