import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { PrismaClient } from '@prisma/client';
import { getCurrentUser, getAdminUser } from '../middleware/auth.middleware';
import { generateFamilyCode, sha256, hashPassword } from '../utils/crypto';
import crypto from 'crypto';

const prisma = new PrismaClient();

export default async function familyRoutes(fastify: FastifyInstance) {
  // Family Setup (Admin creates a family if they don't have one)
  fastify.post('/setup', { preHandler: [getCurrentUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const user = request.user;

    const existingAdmin = await prisma.family.findFirst({
      where: { adminId: user.id }
    });
    
    if (existingAdmin) {
      return reply.status(400).send({ detail: 'User is already an admin of a family' });
    }

    const familyId = crypto.randomUUID();
    const rawCode = generateFamilyCode();
    const codeSha256 = sha256(rawCode.replace('-', ''));
    const codeBcrypt = await hashPassword(rawCode);

    const family = await prisma.$transaction(async (tx) => {
      const f = await tx.family.create({
        data: {
          id: familyId,
          name: `${user.username}'s Vault`,
          adminId: user.id,
          secretCodeHash: codeBcrypt,
          secretCodeSha256: codeSha256,
          maxMembers: 10,
        }
      });

      await tx.familyMember.create({
        data: {
          familyId: f.id,
          userId: user.id,
          role: 'admin'
        }
      });
      
      // Update user role to admin if not already
      if (user.role !== 'admin') {
        await tx.user.update({
          where: { id: user.id },
          data: { role: 'admin' }
        });
      }

      return f;
    });

    return {
      family: {
        id: family.id,
        name: family.name,
        secret_code: rawCode
      }
    };
  });

  // List all members (Any member can view)
  fastify.get('/members', { preHandler: [getCurrentUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const user = request.user;
    
    const membership = await prisma.familyMember.findFirst({
      where: { userId: user.id }
    });

    if (!membership) {
      return reply.status(403).send({ detail: 'Not a member of any family' });
    }

    const members = await prisma.familyMember.findMany({
      where: { familyId: membership.familyId },
      include: { user: true },
      orderBy: { joinedAt: 'asc' }
    });

    return members.map(m => ({
      id: m.userId,
      username: m.user.username,
      email: m.user.email,
      role: m.role,
      joinedAt: m.joinedAt
    }));
  });

  // Remove member (Admin only)
  fastify.delete('/members/:userId', { preHandler: [getAdminUser] }, async (request: FastifyRequest<{ Params: { userId: string } }>, reply: FastifyReply) => {
    const targetUserId = parseInt(request.params.userId, 10);
    const adminUser = request.user;

    const adminMembership = await prisma.familyMember.findFirst({
      where: { userId: adminUser.id }
    });

    if (!adminMembership) {
      return reply.status(403).send({ detail: 'Not a member of any family' });
    }

    if (targetUserId === adminUser.id) {
      return reply.status(400).send({ detail: 'Cannot remove yourself' });
    }

    const targetMembership = await prisma.familyMember.findFirst({
      where: { userId: targetUserId, familyId: adminMembership.familyId }
    });

    if (!targetMembership) {
      return reply.status(404).send({ detail: 'User is not a member of your family' });
    }

    await prisma.familyMember.delete({
      where: { id: targetMembership.id }
    });

    return { message: 'Member removed successfully' };
  });

  // Get current family details (Admin only)
  fastify.get('/details', { preHandler: [getAdminUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const adminUser = request.user;

    const family = await prisma.family.findFirst({
      where: { adminId: adminUser.id }
    });

    if (!family) {
      return reply.status(404).send({ detail: 'Family not found' });
    }

    return {
      id: family.id,
      name: family.name,
      createdAt: family.createdAt,
      maxMembers: family.maxMembers,
      expiresAt: family.expiresAt,
      storageProvider: family.storageProvider,
    };
  });

  // Regenerate secret code (Admin only)
  fastify.post('/regenerate-code', { preHandler: [getAdminUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const adminUser = request.user;

    const family = await prisma.family.findFirst({
      where: { adminId: adminUser.id }
    });

    if (!family) {
      return reply.status(404).send({ detail: 'Family not found' });
    }

    const rawCode = generateFamilyCode();
    const codeSha256 = sha256(rawCode.replace('-', ''));
    const codeBcrypt = await hashPassword(rawCode);

    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7); // Extend expiry by 7 days

    await prisma.family.update({
      where: { id: family.id },
      data: {
        secretCodeHash: codeBcrypt,
        secretCodeSha256: codeSha256,
        expiresAt: expiresAt
      }
    });

    return { secret_code: rawCode, expires_at: expiresAt };
  });
}
