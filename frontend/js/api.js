const BASE_API_URL = ""; // Since files are served from the same server port, relative path is correct.

const getAuthHeaders = () => {
  const token = localStorage.getItem("token");
  return token ? { "Authorization": `Bearer ${token}` } : {};
};

const handleResponse = async (response) => {
  if (response.status === 204) {
    return null;
  }
  
  const contentType = response.headers.get("content-type");
  let data;
  if (contentType && contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    // If token is invalid or expired, automatically clear session and redirect to login
    if (response.status === 401 && !window.location.hash.includes("login") && !window.location.hash.includes("register")) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.hash = "#login";
    }
    const errorMessage = (data && data.detail) ? data.detail : "An error occurred on the server";
    throw new Error(errorMessage);
  }
  return data;
};

const api = {
  get: async (endpoint) => {
    const response = await fetch(`${BASE_API_URL}${endpoint}`, {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
    });
    return handleResponse(response);
  },

  post: async (endpoint, payload) => {
    const response = await fetch(`${BASE_API_URL}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  put: async (endpoint, payload) => {
    const response = await fetch(`${BASE_API_URL}${endpoint}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  delete: async (endpoint) => {
    const response = await fetch(`${BASE_API_URL}${endpoint}`, {
      method: "DELETE",
      headers: {
        ...getAuthHeaders(),
      },
    });
    return handleResponse(response);
  },

  // Upload file with progress monitoring using XMLHttpRequests
  upload: (endpoint, formData, onProgress, onLoad, onError) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_API_URL}${endpoint}`);
    
    // Attach auth header
    const token = localStorage.getItem("token");
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    // Monitor progress
    if (xhr.upload && onProgress) {
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percentComplete = Math.round((e.loaded / e.total) * 100);
          onProgress(percentComplete);
        }
      });
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        let result;
        try {
          result = JSON.parse(xhr.responseText);
        } catch (err) {
          result = xhr.responseText;
        }
        onLoad(result);
      } else {
        let errDetail = "Upload failed";
        try {
          const errRes = JSON.parse(xhr.responseText);
          errDetail = errRes.detail || errDetail;
        } catch (err) {}
        onError(new Error(errDetail));
      }
    };

    xhr.onerror = () => {
      onError(new Error("Network connection error during upload."));
    };

    xhr.send(formData);
    
    // Return abort function in case we want to cancel the request
    return () => xhr.abort();
  }
};
