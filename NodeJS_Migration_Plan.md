# FDMS — Python to Node.js Migration Plan

> **Project:** Family Document Management System (FDMS)  
> **Current Stack:** Python 3.12 · FastAPI · SQLAlchemy · SQLite/PostgreSQL  
> **Target Stack:** Node.js (Express/Fastify) · Prisma ORM · SQLite/PostgreSQL  
> **Total Python Source Files:** 24 files · ~3,900 lines  
> **Prepared:** June 2026

---

## Table of Contents

1. [Project Architecture Overview](#1-project-architecture-overview)
2. [Technology Mapping](#2-technology-mapping)
3. [Database & ORM Migration](#3-database--orm-migration)
4. [Module-by-Module Migration Plan](#4-module-by-module-migration-plan)
5. [Storage Layer Migration](#5-storage-layer-migration)
6. [Background Workers Migration](#6-background-workers-migration)
7. [Security & Auth Migration](#7-security--auth-migration)
8. [Frontend Integration](#8-frontend-integration)
9. [Environment & Configuration](#9-environment--configuration)
10. [Dependency Mapping](#10-dependency-mapping)
11. [Recommended Project Structure](#11-recommended-project-structure)
12. [Migration Phases & Timeline](#12-migration-phases--timeline)
13. [Risk Register](#13-risk-register)
14. [Testing Strategy](#15-testing-strategy)

---

## 1. Project Architecture Overview

### Current Python Architecture

```
FDMS/
├── backend/
│   ├── main.py                  # FastAPI app entry point + background workers
│   ├── config.py                # All env-based configuration
│   ├── database.py              # SQLAlchemy engine + session + migrations
│   ├── models.py                # ORM models (7 tables)
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── auth.py                  # JWT + bcrypt auth utilities
│   ├── serializers.py           # DB → response shape helpers
│   ├── logging_config.py        # Logger setup
│   ├── routers/
│   │   ├── auth.py              # /api/auth (register, login, family-login, me, logout)
│   │   ├── family.py            # /api/family (setup, members, regenerate-code)
│   │   ├── files.py             # /api/files (upload, download, preview, rename, delete, move)
│   │   ├── folders.py           # /api/folders (CRUD, move, soft-delete)
│   │   ├── recycle_bin.py       # /api/recycle-bin (restore, purge)
│   │   ├── search.py            # /api/search
│   │   ├── share.py             # /api/files/:id/share, /api/shared/:token
│   │   ├── storage_config.py    # /api/storage (config, Google OAuth, Mega)
│   │   ├── dashboard.py         # /api/dashboard/stats
│   │   └── views.py             # HTML page serving via Jinja2
│   ├── storage/
│   │   ├── base.py              # Abstract StorageProvider base class
│   │   ├── local.py             # Local disk storage
│   │   ├── google_drive_provider.py  # Google Drive integration
│   │   ├── mega_provider.py     # Mega.nz integration
│   │   └── storage_manager.py   # Local-first + sync coordinator
│   └── utils/
│       ├── audit.py             # Audit log writer
│       ├── cleanup.py           # 30-day recycle bin purge worker
│       ├── crypto.py            # Fernet encrypt/decrypt for storage configs
│       └── virus_scan.py        # VirusTotal SHA-256 hash check
└── frontend/                    # Vanilla HTML/CSS/JS (unchanged)
```

### Key Behaviours to Preserve

- **Local-first uploads** — Files always write to local disk first; a background worker promotes them to Google Drive or Mega asynchronously.
- **Dual DB support** — SQLite in dev, PostgreSQL on Render in prod.
- **Family vault model** — One admin creates a family; members join with a one-time 8-character secret code.
- **Soft delete + recycle bin** — Files and folders are soft-deleted (`deleted_at`) and auto-purged after 30 days.
- **JWT token revocation** — JTI stored in `revoked_tokens` table on logout.
- **Scoped file-access tokens** — Short-lived 5-minute tokens for file preview/download endpoints.
- **Storage config encryption** — Fernet (AES-128-CBC) over JSON stored in the DB column.
- **VirusTotal scanning** — SHA-256 hash lookup before accepting uploads.
- **Google OAuth2 flow** — Full OAuth redirect + callback for Google Drive setup.
- **In-memory IP rate limiting** — 5 attempts per 10 minutes for auth endpoints.

---

## 2. Technology Mapping

| Python / FastAPI | Node.js Equivalent | Notes |
|---|---|---|
| FastAPI | **Fastify** (recommended) or Express | Fastify is closer to FastAPI: schema-first, fast, plugins |
| SQLAlchemy ORM | **Prisma ORM** | Best TypeScript DX; handles SQLite + PostgreSQL |
| Pydantic schemas | **Zod** (runtime validation) + TypeScript types | Zod = runtime; TS types = compile time |
| `python-jose` JWT | **jsonwebtoken** (`jsonwebtoken`) | Same HS256 algorithm, compatible tokens |
| `bcrypt` | **bcryptjs** or `@node-rs/bcrypt` | `@node-rs/bcrypt` is faster (native bindings) |
| `cryptography` Fernet | **Custom AES-256-GCM** via Node `crypto` module | Fernet is Python-only; re-encrypt at migration time |
| `httpx` async HTTP | **axios** or `node-fetch` / `undici` | `undici` is Node's built-in fast HTTP client |
| `python-multipart` | **fastify-multipart** or `multer` (Express) | Handles file upload streams |
| `threading.Thread` workers | **`node-cron`** + worker threads or `setInterval` | cron for scheduled jobs; worker_threads for CPU work |
| Jinja2 templates | Static file serving (no change needed) | Frontend is plain HTML — just serve the folder |
| `uvicorn` ASGI server | **Node built-in** + `cluster` or **PM2** | No separate server needed |
| `python-dotenv` | **dotenv** | Same concept |
| VirusTotal `httpx` | **axios** / `undici` | Same REST API |
| Google Drive SDK | **googleapis** npm package | Official Google API client for Node |
| `mega.py` | **megajs** or **mega** npm package | Community packages; verify maintenance status |

---

## 3. Database & ORM Migration

### 3.1 Prisma Schema

The 7 SQLAlchemy models map cleanly to Prisma. Create `prisma/schema.prisma`:

```prisma
datasource db {
  provider = "sqlite"   // switch to "postgresql" for production
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id           Int      @id @default(autoincrement())
  username     String   @unique @db.VarChar(50)
  email        String   @unique @db.VarChar(255)
  passwordHash String?  @db.VarChar(255)
  role         String   @default("member") @db.VarChar(50)
  createdAt    DateTime @default(now())

  familiesAdministered Family[]
  memberships          FamilyMember[]
  uploadedFiles        File[]         @relation("uploader")
  auditLogs            AuditLog[]
  sharedLinks          SharedLink[]   @relation("creator")
}

model Family {
  id               String    @id @db.VarChar(36)
  name             String    @db.VarChar(255)
  adminId          Int
  secretCodeHash   String    @db.VarChar(255)
  secretCodeSha256 String?   @unique @db.VarChar(64)
  maxMembers       Int       @default(10)
  createdAt        DateTime  @default(now())
  expiresAt        DateTime?
  storageProvider  String?   @db.VarChar(50)
  storageConfig    String?   @db.VarChar(2048)  // Encrypted JSON
  vaultFolderId    String?   @db.VarChar(255)

  admin    User           @relation(fields: [adminId], references: [id], onDelete: Cascade)
  members  FamilyMember[]
  folders  Folder[]
  files    File[]
}

model FamilyMember {
  id       Int      @id @default(autoincrement())
  familyId String   @db.VarChar(36)
  userId   Int
  role     String   @default("member") @db.VarChar(50)
  joinedAt DateTime @default(now())

  family Family @relation(fields: [familyId], references: [id], onDelete: Cascade)
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model Folder {
  id              Int       @id @default(autoincrement())
  name            String    @db.VarChar(255)
  parentId        Int?
  familyId        String    @db.VarChar(36)
  createdAt       DateTime  @default(now())
  deletedAt       DateTime?
  deletionBatchId String?   @db.VarChar(36)

  family     Family   @relation(fields: [familyId], references: [id], onDelete: Cascade)
  parent     Folder?  @relation("FolderParent", fields: [parentId], references: [id])
  subfolders Folder[] @relation("FolderParent")
  files      File[]
}

model File {
  id              Int       @id @default(autoincrement())
  filename        String    @db.VarChar(255)
  fileType        String    @db.VarChar(100)
  sizeBytes       Int
  uploaderId      Int?
  folderId        Int?
  familyId        String    @db.VarChar(36)
  uploadDate      DateTime  @default(now())
  deletedAt       DateTime?
  deletionBatchId String?   @db.VarChar(36)
  storageProvider String    @default("local") @db.VarChar(50)
  fileId          String    @db.VarChar(255)
  cloudLink       String?   @db.VarChar(1024)
  pendingSync     Boolean   @default(true)
  pendingSyncAt   DateTime?
  syncedTo        String?   @db.VarChar(50)

  family   Family  @relation(fields: [familyId], references: [id], onDelete: Cascade)
  uploader User?   @relation("uploader", fields: [uploaderId], references: [id], onDelete: SetNull)
  folder   Folder? @relation(fields: [folderId], references: [id], onDelete: Cascade)
  SharedLink SharedLink[]
}

model AuditLog {
  id        Int      @id @default(autoincrement())
  action    String   @db.VarChar(50)
  timestamp DateTime @default(now())
  userId    Int?
  familyId  String?  @db.VarChar(36)
  ipAddress String?  @db.VarChar(45)
  details   String?  @db.VarChar(1024)

  user User? @relation(fields: [userId], references: [id], onDelete: SetNull)
}

model SharedLink {
  id            String    @id @db.VarChar(32)
  fileId        Int
  familyId      String    @db.VarChar(36)
  passwordHash  String?   @db.VarChar(255)
  expiresAt     DateTime?
  maxDownloads  Int?
  downloadCount Int       @default(0)
  createdAt     DateTime  @default(now())
  createdBy     Int?

  file    File  @relation(fields: [fileId], references: [id], onDelete: Cascade)
  creator User? @relation("creator", fields: [createdBy], references: [id], onDelete: SetNull)
}

model RevokedToken {
  jti       String   @id @db.VarChar(64)
  revokedAt DateTime @default(now())
}
```

### 3.2 Manual Migrations vs. Prisma Migrate

- Use `prisma migrate dev` in development.
- Use `prisma migrate deploy` in production (Render, Docker).
- The existing SQLite DB (`family_documents.db`) can be kept as-is; use `prisma db pull` to introspect if you want Prisma to adopt the existing schema instead of creating fresh.

### 3.3 Storage Config Encryption Migration

Python uses **Fernet** (AES-128-CBC + HMAC-SHA256). Node.js's `crypto` module does not have a Fernet library.

**Migration strategy:**

1. Write a one-shot Python script that decrypts all `storage_config` values in the DB and re-encrypts them using AES-256-GCM (Node-friendly).
2. Implement Node.js encrypt/decrypt helpers using `crypto.createCipheriv('aes-256-gcm', ...)`.
3. Derive the key from `STORAGE_CONFIG_ENCRYPTION_KEY` (same env variable) using `crypto.createHash('sha256')`.

---

## 4. Module-by-Module Migration Plan

### 4.1 `config.py` → `src/config.ts`

**What it does:** Reads all env vars, derives CORS origins, fixes `postgres://` URL prefix.

**Node.js equivalent:**

```typescript
// src/config.ts
import dotenv from 'dotenv';
dotenv.config();

export const config = {
  backendUrl: process.env.BACKEND_URL ?? process.env.RENDER_EXTERNAL_URL ?? 'http://localhost:8000',
  frontendUrl: process.env.FRONTEND_URL ?? process.env.RENDER_EXTERNAL_URL ?? 'http://localhost:8000',
  corsOrigins: parseCorsOrigins(),
  databaseUrl: fixPostgresUrl(process.env.DATABASE_URL ?? 'file:./family_documents.db'),
  jwtSecret: process.env.JWT_SECRET ?? 'super-secret-family-document-vault-key-1234567890',
  jwtAlgorithm: 'HS256',
  accessTokenExpireMinutes: parseInt(process.env.ACCESS_TOKEN_EXPIRE_MINUTES ?? '1440'),
  googleClientId: process.env.GOOGLE_CLIENT_ID ?? '',
  googleClientSecret: process.env.GOOGLE_CLIENT_SECRET ?? '',
  megaEmail: process.env.MEGA_EMAIL ?? '',
  megaPassword: process.env.MEGA_PASSWORD ?? '',
  virusTotalApiKey: process.env.VIRUSTOTAL_API_KEY ?? '',
  syncPollIntervalSeconds: parseInt(process.env.SYNC_POLL_INTERVAL_SECONDS ?? '60'),
  syncBatchSize: parseInt(process.env.SYNC_BATCH_SIZE ?? '50'),
  healthCheckCacheTtl: parseInt(process.env.HEALTH_CHECK_CACHE_TTL ?? '30'),
  isDefaultJwtSecret: (process.env.JWT_SECRET ?? '') === 'super-secret-family-document-vault-key-1234567890',
  appEnv: process.env.APP_ENV ?? 'production',
};
```

**Migration notes:**
- The startup JWT secret check (`raise RuntimeError(...)`) becomes a guard at app boot in `src/app.ts`.
- `postgres://` → `postgresql://` prefix fix is handled by Prisma natively.

---

### 4.2 `auth.py` → `src/middleware/auth.ts` + `src/utils/jwt.ts`

**What it does:** bcrypt hashing, JWT creation/verification, `get_current_user` dependency, `get_admin_user` dependency, JTI revocation check.

**Key mappings:**

| Python | Node.js |
|--------|---------|
| `bcrypt.hashpw(...)` | `bcrypt.hash(password, 12)` |
| `bcrypt.checkpw(...)` | `bcrypt.compare(plain, hash)` |
| `jwt.encode(payload, secret, algorithm)` | `jwt.sign(payload, secret, { algorithm: 'HS256', expiresIn: '...' })` |
| `jwt.decode(token, secret, algorithms=[...])` | `jwt.verify(token, secret)` |
| FastAPI `Depends(get_current_user)` | Fastify preHandler middleware |
| `create_file_access_token(file_id, user_id)` | `jwt.sign({ fileId, userId }, secret, { expiresIn: '5m' })` |

**Rate limiter:** The in-memory `rate_limit_store` dict becomes a `Map<string, number[]>` in Node.js. Use `@fastify/rate-limit` for a proper plugin, or port the manual logic directly.

---

### 4.3 `routers/auth.py` → `src/routes/auth.routes.ts`

**Endpoints to migrate:**

| Method | Path | Action |
|--------|------|--------|
| POST | `/api/auth/register` | Create user + auto-create family + auto-init storage |
| POST | `/api/auth/login` | Email/password login → JWT |
| POST | `/api/auth/family-login` | Secret code join flow → JWT |
| GET | `/api/auth/me` | Return current user |
| PUT | `/api/auth/profile` | Update username/password |
| POST | `/api/auth/logout` | Revoke JWT via JTI |

**Migration notes:**
- `family-login` has a **SHA-256 fast path** for recent records + a **bcrypt fallback** for legacy records that auto-upgrades them. Port both paths.
- The register endpoint auto-creates a family and calls `StorageManager.initialize_family_storage()`. This call must be non-fatal in Node.js too (try/catch, non-blocking).
- Family code format is `XXXX-XXXX` (dash-separated 8-char code). Strip the dash before SHA-256 hashing.

---

### 4.4 `routers/family.py` → `src/routes/family.routes.ts`

**Endpoints to migrate:**

| Method | Path | Action |
|--------|------|--------|
| POST | `/api/family/setup` | Admin creates family (only if they don't have one) |
| GET | `/api/family/members` | List all members |
| DELETE | `/api/family/members/:userId` | Remove member (admin only) |
| GET | `/api/family/details` | Get current family info |
| POST | `/api/family/regenerate-code` | New secret code + extend expiry 7 days |

**Migration notes:**
- Secret code generation: `crypto.randomBytes` + `toString('base64')` filtered to `[A-Z0-9]`, 8 chars.
- SHA-256 of code: `crypto.createHash('sha256').update(code).digest('hex')`.
- bcrypt hash of code: same `bcrypt.hash(code, 12)`.

---

### 4.5 `routers/files.py` → `src/routes/files.routes.ts`

This is the most complex router (~374 lines). Migration notes per endpoint:

**GET `/api/files`** — List files, join uploader, filter by `folder_id`, annotate `is_shared`. Port the `folder_id === 'root'` string check.

**POST `/api/files/upload`** — Critical multi-step flow:
1. Validate MIME extension (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.txt`).
2. Validate filename regex: `/^[\w\-. ()\[\]]+$/u` — the Unicode flag must be preserved.
3. Enforce 50 MB limit.
4. Call VirusTotal SHA-256 check (async HTTP to `virustotal.com/api/v3/files/{hash}`).
5. Write to local storage via `StorageManager.write_file()`.
6. Persist DB record with `pendingSync: true`.
7. Audit log.

In Node.js: use `fastify-multipart` to stream the file into a `Buffer`, then process. Do **not** stream directly to disk — the size check and virus scan need the content in memory first.

**GET `/:fileId/preview-token`** — Issue a scoped 5-minute JWT containing `{ fileId, userId }`.

**GET `/:fileId/download`** and **GET `/:fileId/preview`** — Read via `StorageManager.read_file()`, stream bytes. In Node.js use `reply.send(buffer)` with appropriate headers.

**PUT `/:fileId`** — Rename file. Call `provider.rename_file(config, fileId, newName)`. Update DB.

**DELETE `/:fileId`** — Soft delete via `StorageManager.delete_file()`.

**PATCH `/:fileId/move`** — Update `folder_id` in DB.

---

### 4.6 `routers/folders.py` → `src/routes/folders.routes.ts`

**Migration notes:**
- `soft_delete_folder_recursive` → recursive Prisma transaction or manual recursion. Use `prisma.$transaction([...])` to batch the updates.
- Move validation must check for circular references by walking the parent chain — port the while-loop logic exactly.
- `deletion_batch_id` is a UUID v4; use Node's `crypto.randomUUID()`.

---

### 4.7 `routers/recycle_bin.py` → `src/routes/recycleBin.routes.ts`

**Migration notes:**
- `restore_folder_recursive` uses `deletion_batch_id` to restore exactly the items that were deleted together. Port this batch-matching logic.
- `purge_folder_recursive` physically deletes from cloud and DB. Wrap in a transaction.
- `purge_item` is admin-only.

---

### 4.8 `routers/search.py` → `src/routes/search.routes.ts`

**Migration notes:**
- Prisma uses `contains` for `LIKE` queries: `{ filename: { contains: query } }`.
- File type filter maps `pdf`, `image`, `document`, `text` to substring checks — use Prisma `OR` conditions.
- Date range filters: use `{ gte: startDate }` and `{ lte: endDate }`.

---

### 4.9 `routers/share.py` → `src/routes/share.routes.ts`

**Migration notes:**
- Share token: `crypto.randomBytes(16).toString('hex')` — 32 hex chars, same as Python `secrets.token_hex(16)`.
- Public download endpoint (`POST /api/shared/:token/download`) reuses the rate limiter.
- Password for shared link is bcrypt hashed.
- Increment `downloadCount` atomically: `prisma.sharedLink.update({ where: { id: token }, data: { downloadCount: { increment: 1 } } })`.

---

### 4.10 `routers/storage_config.py` → `src/routes/storageConfig.routes.ts`

**Migration notes:**
- Google OAuth flow: build auth URL with `googleapis` (`google.auth.OAuth2`), store pending credentials in DB, handle the `/oauth2callback` redirect.
- The `state` JWT for OAuth is signed with the app's JWT secret — same pattern as regular JWTs.
- Mega setup: call `provider.verify_credentials(config)` then `provider.ensure_vault_folder(familyId, config)`.

---

### 4.11 `routers/dashboard.py` → `src/routes/dashboard.routes.ts`

Pure aggregation queries. Prisma equivalents:

```typescript
// total_files
const totalFiles = await prisma.file.count({
  where: { familyId, deletedAt: null }
});

// total_size_bytes
const sizeAgg = await prisma.file.aggregate({
  where: { familyId, deletedAt: null },
  _sum: { sizeBytes: true }
});

// recent_uploads
const recentFiles = await prisma.file.findMany({
  where: { familyId, deletedAt: null },
  orderBy: { uploadDate: 'desc' },
  take: 5,
  include: { uploader: true }
});
```

---

### 4.12 `serializers.py` → `src/utils/serializers.ts`

```typescript
export function serializeFile(file: File & { uploader?: User | null }, isShared = false) {
  return {
    id: file.id,
    filename: file.filename,
    fileType: file.fileType,
    sizeBytes: file.sizeBytes,
    uploaderId: file.uploaderId,
    uploaderEmail: file.uploader?.email ?? null,
    folderId: file.folderId,
    familyId: file.familyId,
    uploadDate: file.uploadDate,
    storageProvider: file.storageProvider,
    cloudFileId: file.fileId,
    cloudLink: file.cloudLink,
    isShared,
  };
}
```

---

## 5. Storage Layer Migration

### 5.1 Abstract Interface → TypeScript Interface

```typescript
// src/storage/StorageProvider.ts
export interface StorageProvider {
  healthCheck(config: StorageConfig): Promise<boolean>;
  verifyCredentials(config: StorageConfig): Promise<boolean>;
  ensureVaultFolder(familyId: string, config: StorageConfig): Promise<string>;
  uploadFile(config: StorageConfig, vaultFolderId: string, filename: string, content: Buffer, mimetype: string): Promise<{ cloudFileId: string; cloudLink?: string }>;
  downloadFile(config: StorageConfig, cloudFileId: string): Promise<Buffer>;
  deleteFile(config: StorageConfig, cloudFileId: string): Promise<boolean>;
  renameFile(config: StorageConfig, cloudFileId: string, newName: string): Promise<boolean>;
  getDirectDownloadUrl?(config: StorageConfig, cloudFileId: string): string | null;
}
```

### 5.2 Local Storage Provider (`storage/local.py` → `src/storage/local.provider.ts`)

Straightforward port using `fs/promises`:
- `upload_file` → `fs.writeFile(path.join(vaultDir, uuid + '_' + filename), content)`
- `download_file` → `fs.readFile(filePath)`
- `delete_file` → `fs.unlink(filePath)` (catch ENOENT)
- `rename_file` → `fs.rename(oldPath, newPath)`

### 5.3 Google Drive Provider (`google_drive_provider.py` → `src/storage/googleDrive.provider.ts`)

Use the `googleapis` npm package:

```typescript
import { google } from 'googleapis';

const drive = google.drive({ version: 'v3', auth: oauth2Client });
// upload: drive.files.create({ ... })
// download: drive.files.get({ fileId, alt: 'media' })
// delete: drive.files.delete({ fileId })
// rename: drive.files.update({ fileId, requestBody: { name: newName } })
```

**Key concern:** The Python provider uses `google-api-python-client`. The Node.js `googleapis` package has an identical REST surface.

### 5.4 Mega Provider (`mega_provider.py` → `src/storage/mega.provider.ts`)

**High-risk item.** The Python `mega.py` library is mature. For Node.js:
- **Option A:** `megajs` — actively maintained, promises-based. Recommended.
- **Option B:** `mega` — older package, less active.

Evaluate `megajs` API surface against the Python provider methods before committing:
- `mega.login(email, password)` → session
- `session.upload(...)` / `session.download(...)` / etc.

The Mega provider also has a **caching layer** (`_mega_client`, `_mega_client_key`, `_mega_client_lock`) to avoid re-login on every request. Port this as a module-level singleton `Map<string, MegaStorage>`.

### 5.5 StorageManager (`storage_manager.py` → `src/storage/StorageManager.ts`)

The storage manager is 364 lines. Key behaviours to preserve:

1. **`write_file()`** — Write to local only; return `{ fileId, pendingSync: true }`.
2. **`read_file()`** — Try primary provider first, then cascade to local fallback.
3. **`delete_file()`** — Soft-delete by setting `deletedAt` in DB (don't call provider yet).
4. **`sync_pending_files()`** — Called by the background worker. For each family with pending files, upload to the configured cloud provider and update DB records.
5. **Availability cache** — Module-level `Map` with TTL, protected by a mutex (use `async-mutex` npm package).

---

## 6. Background Workers Migration

Python uses `threading.Thread` (daemon threads). Node.js equivalent:

### 6.1 Cleanup Worker (30-day purge)

```typescript
// src/workers/cleanup.worker.ts
import cron from 'node-cron';
import { purgeOldRecycleBinItems } from '../utils/cleanup';

// Run once at startup after 10s delay, then every 24 hours
setTimeout(async () => {
  await purgeOldRecycleBinItems(30);
  cron.schedule('0 2 * * *', () => purgeOldRecycleBinItems(30)); // 2am daily
}, 10_000);
```

### 6.2 Storage Sync Worker

```typescript
// src/workers/sync.worker.ts
import { StorageManager } from '../storage/StorageManager';

let manager: StorageManager | null = null;

setTimeout(async () => {
  manager = new StorageManager();
  
  const run = async () => {
    const pendingFamilyIds = await prisma.file.findMany({
      where: { pendingSync: true, deletedAt: null },
      distinct: ['familyId'],
      select: { familyId: true }
    });
    
    if (pendingFamilyIds.length > 0) {
      const result = await manager!.syncPendingFiles(pendingFamilyIds.map(f => f.familyId));
      if (result.total > 0) console.log('Sync completed:', result);
    }
    
    setTimeout(run, config.syncPollIntervalSeconds * 1000);
  };
  
  run();
}, 15_000);
```

---

## 7. Security & Auth Migration

### 7.1 JWT

| Python | Node.js |
|--------|---------|
| `python-jose` HS256 | `jsonwebtoken` HS256 |
| `jti` field in payload | same `jti` field |
| `RevokedToken` DB check on each request | Same — check `revokedTokens` table in auth middleware |
| File access token (`file_id`, `user_id`, 5-min TTL) | `jwt.sign({ fileId, userId }, secret, { expiresIn: '5m' })` |

**Compatibility note:** Tokens issued by the Python backend will NOT be valid in Node.js if you change the secret or algorithm. Plan a forced re-login at cutover (clear all sessions), or keep the same `JWT_SECRET` and `HS256` algorithm to maintain compatibility.

### 7.2 Crypto / Config Encryption

Python Fernet ≠ any Node.js built-in. **Migration steps:**

1. Before cutover, run a Python migration script:
   ```python
   # decrypt all storage_config values using old Fernet key
   # re-encrypt using AES-256-GCM with same key material
   # update DB in place
   ```
2. In Node.js, implement:
   ```typescript
   import crypto from 'crypto';
   
   function encryptConfig(data: object, key: Buffer): string {
     const iv = crypto.randomBytes(12);
     const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
     const encrypted = Buffer.concat([cipher.update(JSON.stringify(data), 'utf8'), cipher.final()]);
     const tag = cipher.getAuthTag();
     return Buffer.concat([iv, tag, encrypted]).toString('base64');
   }
   
   function decryptConfig(token: string, key: Buffer): object {
     const buf = Buffer.from(token, 'base64');
     const iv = buf.subarray(0, 12);
     const tag = buf.subarray(12, 28);
     const data = buf.subarray(28);
     const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
     decipher.setAuthTag(tag);
     return JSON.parse(Buffer.concat([decipher.update(data), decipher.final()]).toString('utf8'));
   }
   ```

### 7.3 Password Hashing

`@node-rs/bcrypt` (Rust native binding) — drop-in replacement with same hash format as Python's `bcrypt`. Hashes produced by Python bcrypt are fully compatible.

### 7.4 Rate Limiting

Port the in-memory `rate_limit_store` to a `Map<string, number[]>` with the same 10-minute window / 5-attempt logic, or use `@fastify/rate-limit` with `keyGenerator: (req) => req.ip`.

---

## 8. Frontend Integration

The frontend is **100% vanilla HTML/CSS/JS** — no framework, no build step. It communicates with the backend over REST and expects JSON responses.

**No frontend changes are required**, provided:
- All API paths remain identical (e.g. `/api/auth/login`, `/api/files`, etc.)
- Response JSON shape matches exactly (field names, types, nesting)
- The `Content-Disposition` header format for downloads is preserved
- CORS headers allow the same origins

**Static file serving in Node.js:**

```typescript
// Fastify
import fastifyStatic from '@fastify/static';
import path from 'path';

app.register(fastifyStatic, {
  root: path.resolve(__dirname, '../../frontend'),
  prefix: '/',
});
```

---

## 9. Environment & Configuration

The `.env` file structure is identical. No changes needed:

```env
DATABASE_URL=sqlite:///./family_documents.db   # same for dev
JWT_SECRET=your-secret-here
APP_ENV=development

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MEGA_EMAIL=...
MEGA_PASSWORD=...
VIRUSTOTAL_API_KEY=...

BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:8000,http://localhost:5173

SYNC_POLL_INTERVAL_SECONDS=60
SYNC_BATCH_SIZE=50
HEALTH_CHECK_CACHE_TTL=30
STORAGE_CONFIG_ENCRYPTION_KEY=...
```

**Difference:** `DATABASE_URL` for SQLite in Prisma uses `file:./family_documents.db` (not `sqlite:///./`). Add logic to rewrite the URL if needed, or document the difference.

---

## 10. Dependency Mapping

### Python `requirements.txt` → Node.js `package.json`

| Python Package | Node.js Package | Purpose |
|---|---|---|
| `fastapi>=0.111.0` | `fastify` + `@fastify/cors` + `@fastify/multipart` + `@fastify/static` | Web framework + plugins |
| `uvicorn>=0.30.1` | _(built into Node.js)_ | ASGI/HTTP server |
| `sqlalchemy>=2.0.31` | `@prisma/client` + `prisma` | ORM |
| `pydantic>=2.7.4` | `zod` | Schema validation |
| `python-multipart>=0.0.9` | `@fastify/multipart` | File upload parsing |
| `python-jose[cryptography]>=3.3.0` | `jsonwebtoken` + `@types/jsonwebtoken` | JWT |
| `bcrypt>=4.1.3` | `@node-rs/bcrypt` | Password hashing |
| `mega.py>=1.0.8` | `megajs` | Mega.nz storage |
| `python-dotenv>=1.0.1` | `dotenv` | Env file loading |
| `email-validator>=2.0.0` | `zod` (built-in `.email()`) | Email validation |
| `google-api-python-client>=2.120.0` | `googleapis` | Google Drive API |
| `google-auth>=2.28.0` | `google-auth-library` | Google OAuth |
| `psycopg2-binary>=2.9.9` | Prisma handles PostgreSQL natively | PG driver |
| `jinja2>=3.1.2` | `@fastify/static` (plain HTML) | Template / static serving |
| `httpx` (implicit) | `undici` or `axios` | HTTP client for VirusTotal |
| `cryptography` (Fernet) | Node `crypto` built-in (AES-256-GCM) | Storage config encryption |
| `tenacity<6.0.0` | Custom retry loop or `async-retry` | Retry logic in storage |
| `node-cron` _(new)_ | `node-cron` | Scheduled cleanup job |
| `async-mutex` _(new)_ | `async-mutex` | Mutex for availability cache |
| `uuid` _(new)_ | Node `crypto.randomUUID()` (built-in) | UUID v4 generation |

---

## 11. Recommended Project Structure

```
fdms-node/
├── prisma/
│   ├── schema.prisma
│   └── migrations/
├── src/
│   ├── app.ts                    # Fastify app factory
│   ├── server.ts                 # Entry point, starts workers
│   ├── config.ts                 # All env config
│   ├── middleware/
│   │   └── auth.middleware.ts    # JWT verify, get_current_user, get_admin_user
│   ├── routes/
│   │   ├── auth.routes.ts
│   │   ├── family.routes.ts
│   │   ├── files.routes.ts
│   │   ├── folders.routes.ts
│   │   ├── recycleBin.routes.ts
│   │   ├── search.routes.ts
│   │   ├── share.routes.ts
│   │   ├── storageConfig.routes.ts
│   │   └── dashboard.routes.ts
│   ├── storage/
│   │   ├── StorageProvider.ts    # Interface
│   │   ├── local.provider.ts
│   │   ├── googleDrive.provider.ts
│   │   ├── mega.provider.ts
│   │   └── StorageManager.ts
│   ├── utils/
│   │   ├── jwt.ts
│   │   ├── crypto.ts             # AES-256-GCM encrypt/decrypt
│   │   ├── audit.ts
│   │   ├── virusScan.ts
│   │   ├── cleanup.ts
│   │   └── serializers.ts
│   ├── validators/
│   │   └── schemas.ts            # Zod schemas (mirror Pydantic schemas)
│   └── workers/
│       ├── cleanup.worker.ts
│       └── sync.worker.ts
├── frontend/                     # Unchanged vanilla HTML/CSS/JS
├── .env
├── .env.example
├── package.json
├── tsconfig.json
└── README.md
```

---

## 12. Migration Phases & Timeline

### Phase 1 — Foundation (Week 1–2)

- [ ] Set up Node.js + Fastify + TypeScript project skeleton
- [ ] Configure Prisma with `schema.prisma`; run `prisma migrate dev` on a fresh DB
- [ ] Implement `config.ts`
- [ ] Implement JWT utils (`jwt.ts`): `signToken`, `verifyToken`, `createFileAccessToken`
- [ ] Implement bcrypt utils in `auth.middleware.ts`
- [ ] Implement AES-256-GCM crypto utils (`crypto.ts`)
- [ ] Write the one-shot **Fernet → AES migration script** (Python) and test it against the existing DB

### Phase 2 — Core Auth & Family (Week 2–3)

- [ ] Implement `auth.routes.ts` (register, login, family-login, me, profile, logout)
- [ ] Implement `auth.middleware.ts` (`getCurrentUser`, `getAdminUser`)
- [ ] Implement rate limiter (in-memory Map)
- [ ] Implement `family.routes.ts`
- [ ] Write integration tests for all auth + family endpoints against SQLite

### Phase 3 — Storage Layer (Week 3–4)

- [ ] Implement `local.provider.ts`
- [ ] Implement `StorageManager.ts` (`write_file`, `read_file`, `delete_file`, `get_family_config`)
- [ ] Implement `googleDrive.provider.ts` using `googleapis`
- [ ] Implement `mega.provider.ts` using `megajs` (spike first — confirm API surface)
- [ ] Implement `sync.worker.ts` (`sync_pending_files`)
- [ ] Test local storage end-to-end with file upload + download

### Phase 4 — File & Folder Routes (Week 4–5)

- [ ] Implement `files.routes.ts` (all 7 endpoints)
- [ ] Implement `folders.routes.ts` (CRUD, soft-delete recursive, move with circular-check)
- [ ] Implement `recycleBin.routes.ts` (restore + purge)
- [ ] Implement `virusScan.ts` + integrate into upload handler

### Phase 5 — Search, Share, Storage Config, Dashboard (Week 5–6)

- [ ] Implement `search.routes.ts`
- [ ] Implement `share.routes.ts` (create link, list links, revoke, public download)
- [ ] Implement `storageConfig.routes.ts` (config GET, Google OAuth flow, Mega setup)
- [ ] Implement `dashboard.routes.ts`
- [ ] Implement `cleanup.worker.ts`

### Phase 6 — Hardening & Cutover (Week 6–7)

- [ ] Static file serving for the frontend (verify all HTML pages load correctly)
- [ ] Run the crypto migration script on a copy of the production DB
- [ ] End-to-end manual smoke test of every feature
- [ ] Performance test: upload 50 MB file, concurrent user simulation
- [ ] Deploy to Render (or Docker) in shadow mode (side by side with Python)
- [ ] Route a small % of traffic to Node.js; monitor logs
- [ ] Full cutover; decommission Python service

---

## 13. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| `mega.py` → `megajs` API incompatibility | **High** | Spike `megajs` in Week 3. If blocked, write a thin Python micro-service wrapper for Mega only |
| Fernet → AES-GCM re-encryption corrupts existing configs | **High** | Run migration on a copy of DB first; write a reversal script; test all storage providers post-migration |
| JWT token format change breaks active user sessions | **Medium** | Keep same `JWT_SECRET` + `HS256`; tokens will be forward-compatible. Force re-login at cutover as fallback |
| Prisma `contains` case-sensitivity differs by DB engine | **Medium** | SQLite `LIKE` is case-insensitive by default; PostgreSQL is not. Use `mode: 'insensitive'` in Prisma for PG |
| Concurrent sync worker race conditions | **Medium** | Use `async-mutex` for the availability cache; Prisma transactions for batch DB updates |
| `threading.Thread` daemon behaviour loss | **Low** | Node.js process exits cleanly; `setInterval`/`setTimeout` workers stop with the process automatically |
| Recursive folder operations (soft-delete, restore) | **Medium** | Test deeply nested folder hierarchies; consider Prisma's `$transaction` with rollback on partial failure |
| VirusTotal API rate limits in Node (no `tenacity` retry) | **Low** | Port `SimpleRetry` logic from `base.py`; or use `async-retry` npm package |

---

## 14. Testing Strategy

### Unit Tests (Jest)

Test each utility in isolation:
- `jwt.ts` — sign + verify + expiry + revoked JTI
- `crypto.ts` — encrypt then decrypt round-trip; legacy fallback
- `virusScan.ts` — mock `undici`, test clean/flagged/unknown paths
- `serializers.ts` — shape of output for files and folders

### Integration Tests (Supertest or Fastify inject)

Test each router against a real SQLite in-memory DB (Prisma + SQLite):
- Auth: register → login → get me → logout → verify token revoked
- Family: register → setup family → regenerate code → add member via family-login → remove member
- Files: upload → list → download → rename → move → soft-delete → restore → purge
- Folders: create → rename → move → delete recursive → restore batch
- Search: filename query + type filter + date range
- Share: create link → get info (public) → download (public) → revoke

### E2E Test

Spin up the full Fastify server + a real SQLite DB and run the same flows via HTTP. Verify the frontend HTML pages load and JS `api.js` calls succeed.

---

*End of migration plan.*
