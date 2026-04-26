module.exports = {
  apps: [
    {
      name: "market-stream",
      script: "python",
      args: "-m app.workers.market_stream",
      cwd: "/app",
      autorestart: true,
      restart_delay: 1000,
      max_restarts: 100,
    },
    {
      name: "brain-track-worker",
      script: "python",
      args: "-m app.workers.brain_track_worker",
      cwd: "/app",
      autorestart: true,
      restart_delay: 1000,
      max_restarts: 100,
    },
  ],
};
