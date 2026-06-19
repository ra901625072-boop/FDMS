// ==========================================
// Authentication & User Data
// ==========================================

async function fetchCurrentUser() {
  try {
    const user = await api.get("/api/auth/me");
    state.user = user;
    localStorage.setItem("user", JSON.stringify(user));
    
    // Render sidebar details
    document.getElementById("user-email-display").innerText = user.email;
    document.getElementById("user-role-display").innerText = user.role === "admin" ? "Admin" : "Member";
    document.getElementById("user-avatar-char").innerText = user.username ? user.username.charAt(0).toUpperCase() : "U";
    
    // Profile view details
    const profileUsername = document.getElementById("profile-username-display");
    if(profileUsername) profileUsername.innerText = user.username;
    const profileEmail = document.getElementById("profile-email-display");
    if(profileEmail) profileEmail.innerText = user.email;
    const profileRole = document.getElementById("profile-role-display");
    if(profileRole) profileRole.innerText = user.role;

    // Show/hide Create Family Login button
    const btnCreateFamily = document.getElementById("btn-create-family-login");
    if(btnCreateFamily) {
        btnCreateFamily.style.display = user.role === "admin" ? "block" : "none";
    }

    // Hide/show admin specific fields
    const adminFields = document.querySelectorAll(".admin-only");
    if (user.role === "admin") {
      adminFields.forEach(f => f.style.display = "block");
    } else {
      adminFields.forEach(f => f.style.display = "none");
    }
    
    return user;
  } catch (err) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigateTo("#login");
  }
}

// ==========================================
// Form Submission & Logic
// ==========================================

async function handleLoginSubmit(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  
  try {
    const res = await api.post("/api/auth/login", { email, password });
    if (res.access_token) {
      localStorage.setItem("token", res.access_token);
      showToast("Logged in successfully", "success");
      await fetchCurrentUser();
      navigateTo("#dashboard");
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleFamilyLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("family-login-username").value.trim();
  const email = document.getElementById("family-login-email").value.trim();
  const secretCode = document.getElementById("family-login-secret").value.trim();
  const errorMsg = document.getElementById("family-login-error");
  errorMsg.innerText = "";
  
  try {
    const res = await api.post("/api/auth/family-login", { username, email, secret_code: secretCode });
    if (res.access_token) {
      localStorage.setItem("token", res.access_token);
      showToast("Family Login successful", "success");
      await fetchCurrentUser();
      navigateTo("#dashboard");
    }
  } catch (err) {
    errorMsg.innerText = err.message;
  }
}

function validateSignupField(fieldId) {
  const field = document.getElementById(`signup-${fieldId}`);
  const errorDiv = document.getElementById(`error-${fieldId}`);
  if (!field || !errorDiv) return true;

  errorDiv.innerText = "";
  field.style.borderColor = "";

  if (!field.value) {
    errorDiv.innerText = "This field is required.";
    field.style.borderColor = "var(--danger)";
    return false;
  }

  if (fieldId === 'username') {
    if (field.value.length < 3 || field.value.length > 20) {
      errorDiv.innerText = "Username must be 3-20 characters.";
      field.style.borderColor = "var(--danger)";
      return false;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(field.value)) {
      errorDiv.innerText = "Only alphanumeric characters and underscores allowed.";
      field.style.borderColor = "var(--danger)";
      return false;
    }
  }

  if (fieldId === 'password') {
    if (field.value.length < 8) {
      errorDiv.innerText = "Password must be at least 8 characters.";
      field.style.borderColor = "var(--danger)";
      return false;
    }
    if (!/[A-Z]/.test(field.value)) {
      errorDiv.innerText = "Password must contain at least one uppercase letter.";
      field.style.borderColor = "var(--danger)";
      return false;
    }
    if (!/[0-9]/.test(field.value)) {
      errorDiv.innerText = "Password must contain at least one number.";
      field.style.borderColor = "var(--danger)";
      return false;
    }
  }

  if (fieldId === 'confirm-password') {
    const pwd = document.getElementById("signup-password").value;
    if (field.value !== pwd) {
      errorDiv.innerText = "Passwords do not match.";
      field.style.borderColor = "var(--danger)";
      return false;
    }
  }

  // Clear styles on success
  field.style.borderColor = "var(--success)";
  return true;
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  
  const fields = ['username', 'email', 'password', 'confirm-password'];
  let isValid = true;
  for (let f of fields) {
    if (!validateSignupField(f)) isValid = false;
  }
  
  if (!isValid) return;

  const username = document.getElementById("signup-username").value.trim();
  const email = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  
  try {
    await api.post("/api/auth/register", { username, email, password });
    showToast("Registration successful! You can now log in.", "success");
    document.getElementById("signup-form").reset();
    document.querySelectorAll(".input-field").forEach(f => f.style.borderColor = "");
    navigateTo("#login");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleFamilySetupSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("family-setup-name").value.trim();
  const maxMembers = parseInt(document.getElementById("family-setup-max").value);

  try {
    const res = await api.post("/api/family/setup", { name, max_members: maxMembers });
    closeModal("family-setup-modal");
    
    // Display the Secret Code
    document.getElementById("display-secret-code").innerText = res.secret_code;
    openModal("secret-code-modal");
    
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================
// UI Bindings
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
  // Login Tabs switching
  const tabPersonal = document.getElementById("tab-personal-login");
  const tabFamily = document.getElementById("tab-family-login");
  const formPersonal = document.getElementById("login-form");
  const formFamily = document.getElementById("family-login-form");

  if(tabPersonal && tabFamily) {
    tabPersonal.onclick = () => {
      tabPersonal.classList.add("active");
      tabFamily.classList.remove("active");
      formPersonal.style.display = "block";
      formFamily.style.display = "none";
    };
    tabFamily.onclick = () => {
      tabFamily.classList.add("active");
      tabPersonal.classList.remove("active");
      formFamily.style.display = "block";
      formPersonal.style.display = "none";
    };
  }

  // Family secret code auto-hyphenation & toggle
  const secretInput = document.getElementById("family-login-secret");
  if(secretInput) {
    secretInput.addEventListener("input", function (e) {
      let target = e.target;
      let val = target.value.replace(/-/g, '').toUpperCase();
      if (val.length > 4) {
        val = val.substring(0, 4) + '-' + val.substring(4, 8);
      }
      target.value = val;
    });
  }

  const toggleSecret = document.getElementById("toggle-secret-visibility");
  if(toggleSecret) {
    toggleSecret.onclick = () => {
      const type = secretInput.getAttribute("type") === "password" ? "text" : "password";
      secretInput.setAttribute("type", type);
      const icon = document.getElementById("eye-icon-secret");
      if (type === "text") {
        icon.setAttribute("data-lucide", "eye-off");
      } else {
        icon.setAttribute("data-lucide", "eye");
      }
      lucide.createIcons();
    };
  }

  // Signup Inline validation blur events
  ['username', 'email', 'password', 'confirm-password'].forEach(f => {
    const el = document.getElementById(`signup-${f}`);
    if(el) el.addEventListener('blur', () => validateSignupField(f));
  });

  // Family Setup & Secret Code Modals
  const familySetupForm = document.getElementById("family-setup-form");
  if(familySetupForm) familySetupForm.onsubmit = handleFamilySetupSubmit;

  const copyBtn = document.getElementById("btn-copy-code");
  if(copyBtn) {
    copyBtn.onclick = () => {
      const code = document.getElementById("display-secret-code").innerText;
      copyToClipboard(code);
    };
  }

  const shareBtn = document.getElementById("btn-share-code");
  if(shareBtn) {
    shareBtn.onclick = async () => {
      const code = document.getElementById("display-secret-code").innerText;
      if (navigator.share) {
        try {
          await navigator.share({
            title: 'FamilyVault Secret Code',
            text: `Join our FamilyVault! Our secret code is: ${code}\nThis code expires in 30 days.`,
          });
        } catch (err) {
          console.error("Share failed:", err);
        }
      } else {
        showToast("Web Share API not supported on this browser.", "info");
      }
    };
  }
});
