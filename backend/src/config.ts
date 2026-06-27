import dotenv from 'dotenv';
dotenv.config();

function parseCorsOrigins(): string[] {
  const origins = process.env.CORS_ORIGINS ?? 'http://localhost:8000,http://localhost:5173';
  return origins.split(',').map(o => o.trim());
}

function fixPostgresUrl(url: string): string {
  if (url.startsWith('postgres://')) {
    return url.replace('postgres://', 'postgresql://');
  }
  return url;
}

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
  storageConfigEncryptionKey: process.env.STORAGE_CONFIG_ENCRYPTION_KEY ?? 'default-encryption-key-12345678',
};
