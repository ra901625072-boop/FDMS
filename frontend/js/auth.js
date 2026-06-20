/**
 * FamDoc Authentication & Layout Manager
 */
document.addEventListener("DOMContentLoaded", async () => {
  // Determine page type
  const path = window.location.pathname;
  const isSharedPage = path.includes("shared.html");
  const isGuestPage = path.includes("index.html") || 
                      path.includes("login.html") || 
                      path.includes("register.html") || 
                      path.includes("join.html") ||
                      path === "/" ||
                      path === "";

  const token = localStorage.getItem("famdoc_token");

  // Public shared link page doesn't require session redirects
  if (isSharedPage) {
    return;
  }

  if (isGuestPage) {
    // If logged in, redirect away from guest pages to dashboard
    if (token) {
      window.location.href = "/dashboard.html";
    }
    return;
  }

  // Auth pages require token
  if (!token) {
    window.location.href = "/index.html";
    return;
  }

  // Load user profile
  let user = null;
  try {
    user = await FamDocAPI.auth.me();
  } catch (error) {
    // Session expired or invalid
    FamDocAPI.utils.showToast("Your session has expired. Please log in again.", "error");
    setTimeout(() => {
      FamDocAPI.auth.logout();
    }, 1500);
    return;
  }

  // Check family setup requirement
  const isSetupPage = path.includes("family-setup.html");
  if (!user.family_id) {
    if (user.role === "admin") {
      if (!isSetupPage) {
        window.location.href = "/family-setup.html";
        return;
      }
    } else {
      // Members must always belong to a family (registered via code)
      FamDocAPI.utils.showToast("Account error: No family associated.", "error");
      FamDocAPI.auth.logout();
      return;
    }
  } else {
    // If family is already set up and user goes to setup page, redirect to dashboard
    if (isSetupPage) {
      window.location.href = "/dashboard.html";
      return;
    }
  }

  // Dynamic layout injection
  injectLayout(user);
});

function injectLayout(user) {
  const container = document.getElementById("famdoc-layout-container");
  if (!container) return;

  const currentPath = window.location.pathname;
  const isActive = (page) => currentPath.includes(page) ? "active" : "";

  // 1. Create Layout Wrapper
  const layoutWrapper = document.createElement("div");
  layoutWrapper.className = "layout-wrapper";

  // 2. Create Mobile Header
  const mobileHeader = document.createElement("div");
  mobileHeader.className = "mobile-header";
  mobileHeader.style.cssText = "display: none; width: 100%; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; background-color: var(--bg-linen); border-bottom: 1px solid var(--border-paper); position: fixed; top: 0; left: 0; z-index: 999;";
  mobileHeader.innerHTML = `
    <a href="/dashboard.html" class="sidebar-logo" style="margin-bottom: 0; font-size: 1.25rem;">
      <i class="fas fa-box-archive"></i>
      <span>FamDoc</span>
    </a>
    <button class="hamburger" id="hamburgerToggle">
      <i class="fas fa-bars"></i>
    </button>
  `;

  // 3. Create Sidebar
  const sidebar = document.createElement("nav");
  sidebar.className = "sidebar";
  sidebar.id = "sidebarMenu";
  sidebar.innerHTML = `
    <a href="/dashboard.html" class="sidebar-logo">
      <i class="fas fa-box-archive"></i>
      <span>FamDoc</span>
    </a>
    
    <div class="sidebar-nav">
      <a href="/dashboard.html" class="nav-item ${isActive('dashboard.html')}">
        <i class="fas fa-th-large"></i>
        <span>Dashboard</span>
      </a>
      <a href="/files.html" class="nav-item ${isActive('files.html')}">
        <i class="fas fa-archive"></i>
        <span>Shared Vault</span>
      </a>
      <a href="/recycle-bin.html" class="nav-item ${isActive('recycle-bin.html')}">
        <i class="fas fa-trash-alt"></i>
        <span>Recycle Bin</span>
      </a>
      <a href="/family.html" class="nav-item ${isActive('family.html')}">
        <i class="fas fa-users"></i>
        <span>Family Group</span>
      </a>
    </div>

    <div class="sidebar-footer">
      <div class="user-profile-badge" onclick="window.location.href='/profile.html'" style="cursor: pointer;">
        <div class="user-avatar">
          ${user.username ? user.username.substring(0, 2).toUpperCase() : "U"}
        </div>
        <div class="user-info">
          <span class="user-name">${user.username}</span>
          <span class="user-role">${user.role}</span>
        </div>
      </div>
      <button id="logoutBtn" class="btn btn-secondary" style="width: 100%; justify-content: center; gap: 0.5rem;">
        <i class="fas fa-sign-out-alt"></i>
        <span>Sign Out</span>
      </button>
    </div>
  `;

  // 4. Create Main Content element
  const mainContent = document.createElement("main");
  mainContent.className = "main-content";
  mainContent.id = "mainContent";

  // Move all existing children of container into mainContent (preserves event listeners!)
  while (container.firstChild) {
    mainContent.appendChild(container.firstChild);
  }

  // 5. Append to layout wrapper
  layoutWrapper.appendChild(mobileHeader);
  layoutWrapper.appendChild(sidebar);
  layoutWrapper.appendChild(mainContent);

  // 6. Put layoutWrapper back into container
  container.appendChild(layoutWrapper);

  // Attach logout handler
  document.getElementById("logoutBtn").addEventListener("click", () => {
    FamDocAPI.auth.logout();
  });

  // Mobile menu toggle
  const hamburger = document.getElementById("hamburgerToggle");
  const sidebarMenu = document.getElementById("sidebarMenu");
  
  if (hamburger && sidebarMenu) {
    hamburger.addEventListener("click", (e) => {
      e.stopPropagation();
      sidebarMenu.classList.toggle("open");
      const icon = hamburger.querySelector("i");
      if (sidebarMenu.classList.contains("open")) {
        icon.className = "fas fa-times";
      } else {
        icon.className = "fas fa-bars";
      }
    });

    // Close sidebar on tapping main content on mobile
    mainContent.addEventListener("click", () => {
      if (sidebarMenu.classList.contains("open")) {
        sidebarMenu.classList.remove("open");
        hamburger.querySelector("i").className = "fas fa-bars";
      }
    });
  }

  // Inject responsive header css helper
  const responsiveStyles = document.createElement("style");
  responsiveStyles.textContent = `
    @media (max-width: 768px) {
      .mobile-header {
        display: flex !important;
      }
      .sidebar {
        top: 60px;
        height: calc(100vh - 60px);
      }
      .main-content {
        margin-top: 60px;
      }
    }
  `;
  document.head.appendChild(responsiveStyles);
}
