// Global application state
const state = {
  user: null,            // Logged in user profile
  currentFolderId: null, // null means root vault folder
  folderPath: [],        // Breadcrumbs trail: Array of {id, name}
  folders: [],           // All folders for the family
  files: [],             // Files in current folder
  fileFilter: "all",     // File type filter: 'all', 'image', 'pdf', 'document', 'text'
  activeDropdown: null   // Reference to active actions dropdown
};
