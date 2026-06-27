import { z } from 'zod';

export const UserCreateSchema = z.object({
  username: z.string().min(3).max(50),
  email: z.string().email(),
  password: z.string().min(8),
});

export const UserLoginSchema = z.object({
  email: z.string().email(),
  password: z.string(),
});

export const FamilyLoginSchema = z.object({
  secret_code: z.string().length(9), // XXXX-XXXX
});

export const UserUpdateSchema = z.object({
  username: z.string().min(3).max(50).optional(),
  password: z.string().min(8).optional(),
});
