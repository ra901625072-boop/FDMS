import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { PrismaClient } from '@prisma/client';
import { UserCreateSchema, UserLoginSchema, FamilyLoginSchema, UserUpdateSchema } from '../validators/schemas';
import { hashPassword, verifyPassword, generateFamilyCode, sha256 } from '../utils/crypto';
import { signToken } from '../utils/jwt';
import { getCurrentUser } from '../middleware/auth.middleware';
import crypto from 'crypto';

const prisma = new PrismaClient();

// Note: In-memory rate limiting should be applied here

export default async function authRoutes(fastify: FastifyInstance) {
  fastify.post('/register', async (request: FastifyRequest, reply: FastifyReply) => {
    const parsed = UserCreateSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.status(422).send({ detail: parsed.error.errors });
    }
    const data = parsed.data;

    const existingUser = await prisma.user.findFirst({
      where: { OR: [{ email: data.email }, { username: data.username }] }
    });
    if (existingUser) {
      return reply.status(400).send({ detail: 'Email or username already registered' });
    }

    const hashedPwd = await hashPassword(data.password);
    
    // Transaction to create user, family, and family member
    const result = await prisma.$transaction(async (tx) => {
      const user = await tx.user.create({
        data: {
          username: data.username,
          email: data.email,
          passwordHash: hashedPwd,
          role: 'admin',
        }
      });

      const familyId = crypto.randomUUID();
      const rawCode = generateFamilyCode();
      const codeSha256 = sha256(rawCode.replace('-', ''));
      const codeBcrypt = await hashPassword(rawCode);

      const family = await tx.family.create({
        data: {
          id: familyId,
          name: `${user.username}'s Family`,
          adminId: user.id,
          secretCodeHash: codeBcrypt,
          secretCodeSha256: codeSha256,
          maxMembers: 10,
        }
      });

      await tx.familyMember.create({
        data: {
          familyId: family.id,
          userId: user.id,
          role: 'admin'
        }
      });

      return { user, family, rawCode };
    });

    const token = signToken({ sub: result.user.id.toString(), jti: crypto.randomUUID() });
    
    return {
      access_token: token,
      token_type: 'bearer',
      user: {
        id: result.user.id,
        username: result.user.username,
        email: result.user.email,
        role: result.user.role
      },
      family: {
        id: result.family.id,
        name: result.family.name,
        secret_code: result.rawCode
      }
    };
  });

  fastify.post('/login', async (request: FastifyRequest, reply: FastifyReply) => {
    const parsed = UserLoginSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.status(422).send({ detail: parsed.error.errors });
    }
    const data = parsed.data;

    const user = await prisma.user.findUnique({ where: { email: data.email } });
    if (!user || !user.passwordHash) {
      return reply.status(400).send({ detail: 'Incorrect email or password' });
    }

    const isValid = await verifyPassword(data.password, user.passwordHash);
    if (!isValid) {
      return reply.status(400).send({ detail: 'Incorrect email or password' });
    }

    const token = signToken({ sub: user.id.toString(), jti: crypto.randomUUID() });
    return { access_token: token, token_type: 'bearer' };
  });

  fastify.post('/family-login', async (request: FastifyRequest, reply: FastifyReply) => {
    const parsed = FamilyLoginSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.status(422).send({ detail: parsed.error.errors });
    }
    const data = parsed.data;
    
    const codePlain = data.secret_code.replace('-', '');
    const codeHash = sha256(codePlain);

    let family = await prisma.family.findUnique({
      where: { secretCodeSha256: codeHash }
    });

    if (!family) {
      // Legacy bcrypt fallback
      const families = await prisma.family.findMany();
      for (const f of families) {
        if (await verifyPassword(data.secret_code, f.secretCodeHash)) {
          family = f;
          // Auto-upgrade
          await prisma.family.update({
            where: { id: f.id },
            data: { secretCodeSha256: codeHash }
          });
          break;
        }
      }
    }

    if (!family) {
      return reply.status(400).send({ detail: 'Invalid secret code' });
    }

    if (family.expiresAt && family.expiresAt < new Date()) {
      return reply.status(400).send({ detail: 'Secret code has expired' });
    }

    const memberCount = await prisma.familyMember.count({ where: { familyId: family.id } });
    if (memberCount >= family.maxMembers) {
      return reply.status(400).send({ detail: 'Family has reached max members' });
    }

    // Create placeholder user
    const username = `Member_${crypto.randomBytes(2).toString('hex')}`;
    const email = `${username}@family.local`;

    const result = await prisma.$transaction(async (tx) => {
      const user = await tx.user.create({
        data: {
          username,
          email,
          role: 'member'
        }
      });
      await tx.familyMember.create({
        data: {
          familyId: family.id,
          userId: user.id,
          role: 'member'
        }
      });
      return user;
    });

    const token = signToken({ sub: result.id.toString(), jti: crypto.randomUUID() });
    return {
      access_token: token,
      token_type: 'bearer',
      user: {
        id: result.id,
        username: result.username,
        email: result.email,
        role: result.role
      }
    };
  });

  fastify.get('/me', { preHandler: [getCurrentUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const user = request.user;
    return {
      id: user.id,
      username: user.username,
      email: user.email,
      role: user.role
    };
  });

  fastify.put('/profile', { preHandler: [getCurrentUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const parsed = UserUpdateSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.status(422).send({ detail: parsed.error.errors });
    }
    const data = parsed.data;
    
    const updateData: any = {};
    if (data.username) updateData.username = data.username;
    if (data.password) updateData.passwordHash = await hashPassword(data.password);

    const updated = await prisma.user.update({
      where: { id: request.user.id },
      data: updateData
    });

    return {
      id: updated.id,
      username: updated.username,
      email: updated.email,
      role: updated.role
    };
  });

  fastify.post('/logout', { preHandler: [getCurrentUser] }, async (request: FastifyRequest, reply: FastifyReply) => {
    const authHeader = request.headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      const payload = require('../utils/jwt').verifyToken(token);
      if (payload.jti) {
        await prisma.revokedToken.create({
          data: { jti: payload.jti }
        });
      }
    }
    return { message: 'Successfully logged out' };
  });
}
