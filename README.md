Discord Role Assignment Bot

Overview
- A Discord bot that lets designated moderators assign or remove predefined roles from members, on behalf of server staff.
- On each new member join, the bot posts a private, persistent control message (in a private channel) for admins/moderators with buttons to toggle allowed roles for that specific member.
- The first user to interact with the bot in a guild becomes the bot admin. The admin can assign a moderator role or grant moderator rights to specific users in-app.
- Only roles explicitly allowed by the admin can be assigned by the bot.
- Production-ready: Docker and Swarm compatible, CI/CD to GHCR, minimal intents, simple healthcheck, singleton-safe rolling updates.

Key Features
- Admin bootstrap: The first user who runs a command becomes the admin for that server.
- Moderator controls: Use a dedicated Discord role or assign individual users as moderators via slash commands.
- Allowed roles: Admin curates a list of roles permitted for assignment.
- New member panel: On member join, bot posts a private pinned message with role-toggle buttons for quick assignment/removal.
- Manual commands: Moderators can run /assign and /remove to manage allowed roles on members.
- Private control channel: Auto-created if not configured; visible to admin and moderator role only.
- Ephemeral responses for sensitive operations.
- Minimal gateway intents (Guilds, Members) and slash-commands only.
- Auto-sync of commands on startup; admin resync command.
- Singleton lock with wait-and-retry to avoid duplicate replies during rolling updates.

Security, Privacy, and Behavior
- Slash commands only to reduce spam; most responses are ephemeral.
- No user data beyond Discord IDs is stored; config is per-guild in JSON files.
- Auto-delete: Discord does not support forced non-removable messages; bot pins control messages but cannot prevent deletion by those with permissions.
- The bot requires its highest role to be above all roles it must manage.

Environment Variables
- DISCORD_TOKEN (required): The Discord Bot Token from the Developer Portal.
- DATA_DIR (optional): Path for persistent data (default: /data). Alias: DATA_PATH is also accepted.
- LOG_LEVEL (optional): Python logging level (e.g., INFO, DEBUG). Default: INFO.
- ALLOWED_GUILDS (optional): Comma-separated guild IDs. If set, the bot only operates and syncs commands for these guilds.

Getting Started (Local)
1. Prerequisites
   - Python 3.11+
   - A Discord Bot application and Bot Token
   - Enable Privileged Gateway Intents: SERVER MEMBERS INTENT (Members) in the Discord Developer Portal.
2. Install and run
   - pip install -r requirements.txt
   - export DISCORD_TOKEN=your_token_here
   - python -m src.bot

Docker Usage
Build and run locally
- docker build -t discord-role-bot:latest .
- docker run --rm \
    -e DISCORD_TOKEN=your_token \
    -e LOG_LEVEL=INFO \
    -e ALLOWED_GUILDS=1234567890,987654321 \
    -v rolebot-data:/data \
    --name rolebot discord-role-bot:latest

Docker Swarm (stack)
- Ensure a Swarm is initialized: docker swarm init
- Deploy: export DISCORD_TOKEN=your_token; docker stack deploy -c stack.yml rolebot
- Check logs: docker service logs -f rolebot_discord-role-bot

Compose (Swarm-compatible)
- See docker-compose.yml. Example: DISCORD_TOKEN=your_token docker stack deploy -c docker-compose.yml rolebot

CI/CD and Registry
- Images are published to GHCR at: ghcr.io/<owner>/discord-role-bot
- Tags include: branch name, semantic version tags (vX.Y.Z), commit SHA, and latest on the default branch.

Documentation
- Discord app setup: docs/SETUP_DISCORD_APP.md
- Usage and commands: docs/USAGE.md

Usage Guide (Slash Commands)
Setup commands (admin only)
- /setup set_moderator_role role:<Role>
  - Defines a Discord Role whose members are considered moderators by the bot.
- /setup set_assignment_channel [channel:<TextChannel>]
  - Sets an existing text channel for control panels, or auto-creates a private one if omitted.

Admin commands
- /admin add_moderator user:<User>
- /admin remove_moderator user:<User>
- /admin list_moderators
- /admin resync

Allowed roles management (admin only)
- /roles_allow add role:<Role>
- /roles_allow remove role:<Role>
- /roles_allow list (visible to moderators/admin)

Moderator commands
- /assign member:<Member> role:<Allowed Role>
- /remove member:<Member> role:<Allowed Role>
- /simulate_rejoin member:<Member>

New member workflow
- When a new member joins, the bot posts a pinned message in the private assignment channel with buttons for each allowed role.
- Each button shows a checkmark if the member currently has that role (✅) or an empty box if not (☐), and updates live after changes.
- Moderators/Admins can click buttons to toggle roles on the new member. The action result is acknowledged via ephemeral replies.

Notes and Limitations
- Hidden message not removable: Discord does not allow completely non-removable messages. The bot pins the control message and will recreate panels for future joins. Server admins could still delete the message; consider locking down the channel permissions.
- Managed roles (integration roles) cannot be assigned by bots; such roles are rejected from the allowed list.
- The first user to use a command becomes the admin; you can later transfer by adding another moderator or editing data files.
- Intents: Ensure SERVER MEMBERS INTENT is enabled or member join events won't trigger.

Data Persistence
- The bot stores per-guild configurations in DATA_DIR/guilds/<guild_id>.json
- Do not share or delete these files while the bot is running.

Troubleshooting
- Commands not appearing: wait a few minutes or use /admin resync; ensure applications.commands scope and permissions.
- Cannot assign a role: move the bot's role higher; ensure role is in allowed list and is not managed.
- Member panel not posted: verify Members intent is enabled; check channel permissions; ensure the /data volume is writable.
- Duplicate messages after updates: ensure only one replica is running (replicas: 1). A simple singleton lock is used to reduce duplicates during rolling updates.

Roadmap / Future ideas
- Recreate control panel if deleted (background watcher).
- Multi-message pagination for more than 25 allowed roles.
- Audit log integration.

License
- See LICENSE file. This project is open-source, shareable with contribution, non-commercial, and requires attribution.
