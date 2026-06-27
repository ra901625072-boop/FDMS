import Fastify from 'fastify';
import cors from '@fastify/cors';
import multipart from '@fastify/multipart';
import fastifyStatic from '@fastify/static';
import path from 'path';
import { config } from './config';

import authRoutes from './routes/auth.routes';
import familyRoutes from './routes/family.routes';

export function buildApp() {
  const app = Fastify({
    logger: true,
  });

  // Plugins
  app.register(cors, {
    origin: config.corsOrigins,
    credentials: true,
  });

  app.register(multipart, {
    limits: {
      fileSize: 50 * 1024 * 1024, // 50MB
    },
  });

  // Serve static files from the public directory
  app.register(fastifyStatic, {
    root: path.resolve(__dirname, '../public'),
    prefix: '/',
  });

  // Setup Routes
  app.register(authRoutes, { prefix: '/api/auth' });
  app.register(familyRoutes, { prefix: '/api/family' });

  // Error handling
  app.setErrorHandler((error, request, reply) => {
    app.log.error(error);
    reply.status(error.statusCode || 500).send({
      detail: error.message || 'Internal Server Error',
    });
  });

  return app;
}
