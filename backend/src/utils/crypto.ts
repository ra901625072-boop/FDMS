import crypto from 'crypto';
import { config } from '../config';

function getEncryptionKey(): Buffer {
  return crypto.createHash('sha256').update(config.storageConfigEncryptionKey).digest();
}

export function encryptConfig(data: object): string {
  const key = getEncryptionKey();
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  
  const payload = JSON.stringify(data);
  const encrypted = Buffer.concat([cipher.update(payload, 'utf8'), cipher.final()]);
  const tag = cipher.getAuthTag();
  
  return Buffer.concat([iv, tag, encrypted]).toString('base64');
}

export function decryptConfig(token: string): object {
  const key = getEncryptionKey();
  const buf = Buffer.from(token, 'base64');
  
  const iv = buf.subarray(0, 12);
  const tag = buf.subarray(12, 28);
  const data = buf.subarray(28);
  
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(tag);
  
  const decrypted = Buffer.concat([decipher.update(data), decipher.final()]).toString('utf8');
  return JSON.parse(decrypted);
}

export function hashPassword(password: string): Promise<string> {
  const bcrypt = require('@node-rs/bcrypt');
  return bcrypt.hash(password, 12);
}

export function verifyPassword(password: string, hash: string): Promise<boolean> {
  const bcrypt = require('@node-rs/bcrypt');
  return bcrypt.compare(password, hash);
}

export function generateFamilyCode(): string {
  let code = crypto.randomBytes(6).toString('base64').replace(/[^A-Z0-9]/gi, '').toUpperCase();
  while (code.length < 8) {
    code += crypto.randomBytes(1).toString('base64').replace(/[^A-Z0-9]/gi, '').toUpperCase();
  }
  code = code.substring(0, 8);
  return `${code.substring(0, 4)}-${code.substring(4)}`;
}

export function sha256(data: string): string {
  return crypto.createHash('sha256').update(data).digest('hex');
}
