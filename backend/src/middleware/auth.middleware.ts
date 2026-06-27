import { FastifyRequest, FastifyReply } from 'fastify';
import { verifyToken } from '../utils/jwt';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export async function getCurrentUser(request: FastifyRequest, reply: FastifyReply) {
  const authHeader = request.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return reply.status(401).send({ detail: 'Not authenticated' });
  }

  const token = authHeader.substring(7);
  
  try {
    const payload = verifyToken(token);
    
    // Check if token is revoked
    if (payload.jti) {
      const revoked = await prisma.revokedToken.findUnique({
        where: { jti: payload.jti }
      });
      if (revoked) {
        return reply.status(401).send({ detail: 'Token has been revoked' });
      }
    }
    
    // Extract user ID
    const userId = parseInt(payload.sub, 10);
    if (isNaN(userId)) {
      return reply.status(401).send({ detail: 'Invalid token payload' });
    }
    
    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      return reply.status(401).send({ detail: 'User not found' });
    }
    
    request.user = user;
  } catch (error) {
    return reply.status(401).send({ detail: 'Invalid token' });
  }
}

export async function getAdminUser(request: FastifyRequest, reply: FastifyReply) {
  await getCurrentUser(request, reply);
  
  if (reply.sent) return;
  
  if (request.user?.role !== 'admin') {
    return reply.status(403).send({ detail: 'Not enough permissions' });
  }
}

// Extend FastifyRequest to include user
declare module 'fastify' {
  interface FastifyRequest {
    user?: any; // Replace with proper User type from Prisma
  }
}
