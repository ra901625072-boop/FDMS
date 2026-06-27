import { buildApp } from './app';
import { config } from './config';

const server = buildApp();

const start = async () => {
  try {
    if (config.isDefaultJwtSecret) {
      server.log.warn('Using default JWT secret. THIS IS INSECURE FOR PRODUCTION!');
    }
    
    const port = process.env.PORT ? parseInt(process.env.PORT, 10) : 8000;
    const host = process.env.HOST ?? '0.0.0.0';
    
    await server.listen({ port, host });
    
    server.log.info(`Server running at http://${host}:${port}`);
    
    // Background workers will be started here eventually
  } catch (err) {
    server.log.error(err);
    process.exit(1);
  }
};

start();
