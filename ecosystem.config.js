module.exports = {
  apps: [
    {
      name: 'maxwell-bot',
      script: 'bot.py',
      interpreter: 'python3',
      cwd: process.env.MAXWELL_APP_ROOT || __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true
    },
    {
      name: 'maxwell-api',
      script: 'api/api_server.py',
      interpreter: 'python3',
      cwd: process.env.MAXWELL_APP_ROOT || __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true
    }
  ]
};
