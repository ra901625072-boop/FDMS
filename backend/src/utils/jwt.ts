import jwt from 'jsonwebtoken';
import { config } from '../config';

export interface TokenPayload {
  sub: string;
  jti: string;
  type?: string;
  [key: string]: any;
}

export function signToken(payload: object, expiresInMinutes: number = config.accessTokenExpireMinutes): string {
  return jwt.sign(payload, config.jwtSecret, {
    algorithm: config.jwtAlgorithm as jwt.Algorithm,
    expiresIn: `${expiresInMinutes}m`,
  });
}

export function verifyToken(token: string): TokenPayload {
  return jwt.verify(token, config.jwtSecret, {
    algorithms: [config.jwtAlgorithm as jwt.Algorithm],
  }) as TokenPayload;
}

export function createFileAccessToken(fileId: number, userId: number): string {
  return jwt.sign({ fileId, userId }, config.jwtSecret, {
    expiresIn: '5m',
    algorithm: config.jwtAlgorithm as jwt.Algorithm,
  });
}
